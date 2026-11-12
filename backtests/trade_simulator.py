"""REX backtest trade executor (causal fill simulation)."""

from collections.abc import Sequence
from datetime import datetime
from math import isfinite

from backtests.costs import CostModelError, TransactionCostModel
from backtests.fill_models import ConservativeOHLCFillModel, FillModel
from models.bar import Bar
from models.closed_trade import ClosedTrade
from models.position import Position
from models.terminated_setup import TerminatedSetup
from models.trade_direction import TradeDirection
from models.trade_plan import TradePlan
from execution.sizers import PositionSizer
from models.account_context import AccountContext


def calculate_pnl_r(
    direction: TradeDirection,
    entry_price: float,
    sl_price: float,
    exit_price: float,
) -> float:
    """Calculate realized gain or loss in units of risk (R-multiples)."""
    risk = (
        sl_price - entry_price
        if direction == TradeDirection.SHORT
        else entry_price - sl_price
    )
    if risk == 0:
        return 0.0
    diff = (
        entry_price - exit_price
        if direction == TradeDirection.SHORT
        else exit_price - entry_price
    )
    return diff / risk


class TradeSimulator:
    """
    Backtest executor: causally updates pending TradePlans and open positions.

    Fill/cost estimates on TradePlan are not applied here; OHLC fill model owns
    entry/exit prices. Paper/live executors will consume the same TradePlan type.
    """

    def __init__(
        self,
        max_hold_candles: int = 60,
        fill_model: FillModel | None = None,
        position_sizer: PositionSizer | None = None,
        account: AccountContext | None = None,
        min_position_size: float = 0.0,
        max_position_size: float | None = None,
        cost_model: TransactionCostModel | None = None,
    ) -> None:
        self.max_hold_candles = max_hold_candles
        self.fill_model = (
            fill_model if fill_model is not None else ConservativeOHLCFillModel()
        )
        if min_position_size < 0:
            raise ValueError("min_position_size cannot be negative")
        if max_position_size is not None and max_position_size <= min_position_size:
            raise ValueError("max_position_size must exceed min_position_size")
        self.position_sizer = position_sizer
        self.account = account or AccountContext()
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size
        self.cost_model = cost_model

        self.pending_plans: dict[tuple[str, str], list[tuple[TradePlan, int]]] = {}
        self.open_positions: dict[tuple[str, str], list[Position]] = {}
        self.closed_trades: dict[tuple[str, str], list[ClosedTrade]] = {}
        self.terminated_setups: list[TerminatedSetup] = []

        self.ambiguous_trades_count = 0
        self.total_trades_count = 0

    def reset(self) -> None:
        """Reset all state to prevent data leaking between runs."""
        self.pending_plans.clear()
        self.open_positions.clear()
        self.closed_trades.clear()
        self.terminated_setups.clear()
        self.ambiguous_trades_count = 0
        self.total_trades_count = 0

    def has_active_lifecycle(self, strategy_id: str, symbol: str) -> bool:
        """Return True if there is a pending plan or open position for the key."""
        key = (strategy_id, symbol)
        if key in self.pending_plans and self.pending_plans[key]:
            return True
        if key in self.open_positions and self.open_positions[key]:
            return True
        return False

    def add_plan(self, plan: TradePlan) -> None:
        """Queue a planned trade for future fill processing (elapsed wait = 0)."""
        key = (plan.strategy_id, plan.symbol)
        if key not in self.pending_plans:
            self.pending_plans[key] = []
        self.pending_plans[key].append((plan, 0))

    def update(self, bar: Bar) -> None:
        """Update active positions and pending plans against the current bar."""
        self._update_open_positions(bar)
        new_positions = self._process_pending_plans(bar)
        self._evaluate_new_positions(new_positions, bar)

    def finalize_backtest(
        self, symbols: Sequence[str], final_bars: dict[str, Bar]
    ) -> None:
        """Cancel pending plans and force-close open positions at data end."""
        for key, plans in list(self.pending_plans.items()):
            _strat_id, symbol = key
            if symbol in symbols and plans:
                final_bar = final_bars.get(symbol)
                for plan, _elapsed in plans:
                    # Prefer causal bar time; fall back to plan timestamps (never wall clock).
                    term_time = (
                        final_bar.timestamp
                        if final_bar is not None
                        else plan.planned_at
                    )
                    self._record_plan_termination(
                        plan, term_time, "CANCELLED_END_OF_DATA"
                    )
                plans.clear()

        for key, active_positions in list(self.open_positions.items()):
            _strat_id, symbol = key
            if symbol in symbols and active_positions:
                final_bar = final_bars.get(symbol)
                if final_bar is not None:
                    for pos in list(active_positions):
                        self._close_position(
                            pos, final_bar, final_bar.close, "FORCE_CLOSE_END_OF_DATA"
                        )
                    active_positions.clear()

    def get_all_closed_trades(self) -> list[ClosedTrade]:
        """Return a flat list of all recorded closed trades."""
        trades: list[ClosedTrade] = []
        for key in self.closed_trades:
            trades.extend(self.closed_trades[key])
        return sorted(trades, key=lambda t: t.exit_time)

    def get_currently_active_count(self) -> int:
        """Return total pending plans and open positions remaining."""
        plan_count = sum(len(plans) for plans in self.pending_plans.values())
        position_count = sum(len(positions) for positions in self.open_positions.values())
        return plan_count + position_count

    def _record_plan_termination(
        self, plan: TradePlan, termination_time: datetime, reason: str
    ) -> None:
        term = TerminatedSetup(
            symbol=plan.symbol,
            direction=plan.direction,
            strategy_id=plan.strategy_id,
            timestamp=plan.timestamp,
            termination_time=termination_time,
            reason=reason,
            signal_id=plan.setup_id,
        )
        self.terminated_setups.append(term)

    def _update_open_positions(self, bar: Bar) -> None:
        symbol = bar.symbol
        for key, active_positions in list(self.open_positions.items()):
            _strat_id, sym = key
            if sym != symbol or not active_positions:
                continue

            remaining = []
            for pos in active_positions:
                result = self.fill_model.check_exit(pos, bar)
                if result is not None:
                    exit_price, reason = result
                    if reason == "AMBIGUITY":
                        self.ambiguous_trades_count += 1
                    self._close_position(pos, bar, exit_price, reason)
                elif pos.elapsed_candles + 1 >= pos.max_hold_candles:
                    pos.elapsed_candles += 1
                    self._close_position(pos, bar, bar.close, "TIMEOUT")
                else:
                    pos.elapsed_candles += 1
                    remaining.append(pos)

            self.open_positions[key] = remaining

    def _size_at_fill(
        self, plan: TradePlan, entry_price: float, stop_price: float
    ) -> tuple[float, float] | None:
        """Re-size at the actual fill so realised risk matches the risk target.

        The policy's entry estimate is causal but the fill is the next candle
        open. Keeping the planned size would make realised currency risk depend
        on entry slippage; this method recomputes units from the actual stop
        distance. Returns ``(position_size, risk_amount)`` or ``None`` when the
        plan cannot be sized safely.
        """
        risk_distance = abs(entry_price - stop_price)
        if risk_distance <= 1e-12 or not isfinite(risk_distance):
            return None
        if self.position_sizer is not None:
            sized = self.position_sizer.size(
                plan.setup, entry_price, stop_price, self.account
            )
            if sized is None:
                return None
            position_size = sized.position_size
            risk_amount = sized.risk_amount
        else:
            risk_amount = plan.risk_amount
            if not isfinite(risk_amount) or risk_amount <= 0:
                return None
            position_size = risk_amount / risk_distance
        if not isfinite(position_size) or position_size <= 0:
            return None
        if position_size < self.min_position_size:
            return None
        if self.max_position_size is not None and position_size > self.max_position_size:
            return None
        if not isfinite(risk_amount) or risk_amount <= 0:
            return None
        return position_size, risk_amount

    def _process_pending_plans(self, bar: Bar) -> list[Position]:
        """
        Attempt entries for pending plans; expire unfilled plans after timeout_candles.

        Elapsed counts bars on which the plan was pending and did not fill
        (deterministic candle count, not wall clock).
        """
        symbol = bar.symbol
        new_positions: list[Position] = []

        for key, plans in list(self.pending_plans.items()):
            _strat_id, sym = key
            if sym != symbol or not plans:
                continue

            remaining: list[tuple[TradePlan, int]] = []
            for plan, elapsed in plans:
                entry_price = self.fill_model.check_entry(plan, bar)
                if entry_price is not None:
                    sl_price = plan.sl_price
                    risk_distance = abs(entry_price - sl_price)

                    is_valid = True
                    if risk_distance <= 1e-7:
                        is_valid = False
                    elif (
                        plan.direction == TradeDirection.LONG
                        and sl_price >= entry_price
                    ):
                        is_valid = False
                    elif (
                        plan.direction == TradeDirection.SHORT
                        and sl_price <= entry_price
                    ):
                        is_valid = False

                    if not is_valid:
                        self._record_plan_termination(
                            plan, bar.timestamp, "REJECTED_INVALID_ENTRY"
                        )
                        continue

                    sized = self._size_at_fill(plan, entry_price, sl_price)
                    if sized is None:
                        self._record_plan_termination(
                            plan, bar.timestamp, "REJECTED_SIZE_INVALID"
                        )
                        continue
                    position_size, risk_amount = sized

                    # Recalculate TP from actual fill (planned TP used estimate entry).
                    if plan.direction == TradeDirection.LONG:
                        tp_price = entry_price + risk_distance * plan.r_multiple
                    else:
                        tp_price = entry_price - risk_distance * plan.r_multiple

                    new_pos = Position(
                        symbol=plan.symbol,
                        direction=plan.direction,
                        entry_price=entry_price,
                        entry_time=bar.timestamp,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        max_hold_candles=self.max_hold_candles,
                        signal_id=plan.setup_id,
                        strategy_id=plan.strategy_id,
                        elapsed_candles=0,
                        planned_entry_price=plan.entry_price,
                        planned_position_size=plan.position_size,
                        planned_risk_amount=plan.risk_amount,
                        position_size=position_size,
                        risk_amount=risk_amount,
                        entry_slippage=entry_price - plan.entry_price,
                    )
                    new_positions.append(new_pos)
                else:
                    waited = elapsed + 1
                    if waited >= plan.timeout_candles:
                        self._record_plan_termination(
                            plan, bar.timestamp, "EXPIRED"
                        )
                    else:
                        remaining.append((plan, waited))

            self.pending_plans[key] = remaining
        return new_positions

    def _evaluate_new_positions(
        self, new_positions: list[Position], bar: Bar
    ) -> None:
        if not new_positions:
            return

        for pos in new_positions:
            result = self.fill_model.check_exit(pos, bar)
            pos.elapsed_candles += 1

            key = (pos.strategy_id, pos.symbol)
            if key not in self.open_positions:
                self.open_positions[key] = []

            if result is not None:
                exit_price, reason = result
                if reason == "AMBIGUITY":
                    self.ambiguous_trades_count += 1
                self._close_position(pos, bar, exit_price, reason)
            else:
                self.open_positions[key].append(pos)

    @staticmethod
    def _execution_assumption(
        pos: Position, exit_price: float, reason: str
    ) -> str:
        if reason == "AMBIGUITY":
            if abs(exit_price - pos.sl_price) > 1e-12:
                return "both_levels_touched_gap_through_stop_at_open"
            return "both_levels_touched_stop_first_conservative"
        if reason == "SL":
            if abs(exit_price - pos.sl_price) > 1e-12:
                return "gap_through_stop_at_open"
            return "stop_at_level"
        if reason == "TP":
            return "target_at_level"
        if reason == "TIMEOUT":
            return "timeout_at_close"
        if reason == "FORCE_CLOSE_END_OF_DATA":
            return "force_close_at_final_close"
        return "unknown"

    def _close_position(
        self, pos: Position, exit_bar: Bar, exit_price: float, reason: str
    ) -> None:
        key = (pos.strategy_id, pos.symbol)
        if key not in self.closed_trades:
            self.closed_trades[key] = []

        # Ambiguity is a fill-resolution label, not a license to rewrite PnL.
        # If the bar gapped through the stop, the actual fill loss is recorded;
        # if both levels were touched inside the bar, the conservative SL fill
        # naturally produces -1R.
        pnl_r = calculate_pnl_r(
            pos.direction, pos.entry_price, pos.sl_price, exit_price
        )
        assumption = self._execution_assumption(pos, exit_price, reason)
        cost_breakdown = None
        if self.cost_model is not None:
            try:
                cost_breakdown = self.cost_model.calculate(
                    symbol=pos.symbol,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    risk_distance=abs(pos.entry_price - pos.sl_price),
                    risk_amount=float(pos.risk_amount or 0.0),
                    gross_pnl_r=pnl_r,
                    holding_days=max(
                        0, (exit_bar.timestamp.date() - pos.entry_time.date()).days
                    ),
                )
            except CostModelError:
                cost_breakdown = None

        self.total_trades_count += 1

        closed_trade = ClosedTrade(
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            entry_time=pos.entry_time,
            exit_price=exit_price,
            exit_time=exit_bar.timestamp,
            sl_price=pos.sl_price,
            tp_price=pos.tp_price,
            pnl_r=pnl_r,
            close_reason=reason,
            holding_duration_candles=pos.elapsed_candles,
            signal_id=pos.signal_id,
            strategy_id=pos.strategy_id,
            planned_entry_price=pos.planned_entry_price,
            planned_position_size=pos.planned_position_size,
            planned_risk_amount=pos.planned_risk_amount,
            position_size=pos.position_size,
            realized_risk_amount=pos.risk_amount,
            entry_slippage=pos.entry_slippage,
            execution_assumption=assumption,
            spread_cost_r=cost_breakdown.spread_r if cost_breakdown else 0.0,
            slippage_cost_r=cost_breakdown.slippage_r if cost_breakdown else 0.0,
            commission_cost_r=cost_breakdown.commission_r if cost_breakdown else 0.0,
            swap_cost_r=cost_breakdown.swap_r if cost_breakdown else 0.0,
            total_cost_r=cost_breakdown.total_r if cost_breakdown else 0.0,
            net_pnl_r=cost_breakdown.net_pnl_r if cost_breakdown else pnl_r,
            cost_profile_id=cost_breakdown.profile_id if cost_breakdown else None,
        )
        self.closed_trades[key].append(closed_trade)
