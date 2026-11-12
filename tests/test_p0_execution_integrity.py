"""Regression tests for the P0 execution-integrity fixes.

Covers realised-risk sizing, gap/ambiguity execution, CORE close-outside
state transitions, and duplicate timestamp rejection. All fixtures here are
deterministic synthetic bars; real-data before/after evidence is in
docs/p0-execution-integrity/.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backtests.trade_simulator import TradeSimulator
from core.features import FeatureRepository
from core.features.timeframes import aggregate_completed_bars, ensure_utc
from execution.sizers import FixedRiskSizer
from models.account_context import AccountContext
from models.bar import Bar
from models.entry_model import EntryModel
from models.trade_direction import TradeDirection
from models.trade_plan import TradePlan
from models.trade_setup import TradeSetup
from models.zone import Zone, ZoneBook
from strategies.breakout import BreakoutStrategy

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _bar(
    minute: int,
    *,
    open_: float = 1.15,
    high: float = 1.151,
    low: float = 1.149,
    close: float = 1.15,
) -> Bar:
    return Bar("EURUSD", T0 + timedelta(minutes=minute), open_, high, low, close)


def _plan(
    *,
    entry: float = 1.15,
    stop: float = 1.14,
    direction: TradeDirection = TradeDirection.LONG,
    risk_amount: float = 100.0,
) -> TradePlan:
    risk = abs(entry - stop)
    target = entry + risk * 2 if direction == TradeDirection.LONG else entry - risk * 2
    setup = TradeSetup(
        setup_id="p0-setup",
        symbol="EURUSD",
        direction=direction,
        strategy_id="P0",
        timestamp=T0,
        reason="p0",
        entry_hint=entry,
        stop_hint=stop,
        entry_model_hint=EntryModel.NEXT_CANDLE_OPEN,
    )
    return TradePlan(
        setup=setup,
        entry_model=EntryModel.NEXT_CANDLE_OPEN,
        entry_price=entry,
        sl_price=stop,
        tp_price=target,
        r_multiple=2.0,
        position_size=1.0,
        risk_amount=risk_amount,
        timeout_candles=5,
        planned_at=T0,
    )


class RealisedRiskTests(unittest.TestCase):
    def test_fill_resizes_to_preserve_planned_risk(self) -> None:
        sim = TradeSimulator(
            position_sizer=FixedRiskSizer(),
            account=AccountContext(10_000.0, 0.01),
        )
        sim.add_plan(_plan(entry=1.15, stop=1.14))
        sim.update(_bar(0, open_=1.155, high=1.156, low=1.154, close=1.155))
        sim.finalize_backtest(["EURUSD"], {"EURUSD": _bar(0, open_=1.155, high=1.156, low=1.154, close=1.155)})
        self.assertEqual(len(sim.get_all_closed_trades()), 1)
        trade = sim.get_all_closed_trades()[0]
        self.assertAlmostEqual(trade.entry_price, 1.155)
        self.assertAlmostEqual(trade.realized_risk_amount or 0.0, 100.0, places=8)
        self.assertAlmostEqual(trade.planned_risk_amount or 0.0, 100.0, places=8)
        self.assertGreater(trade.position_size or 0.0, 0.0)
        self.assertAlmostEqual(trade.entry_slippage or 0.0, 0.005, places=8)

    def test_fixed_risk_sizer_contract_and_bounds(self) -> None:
        sizer = FixedRiskSizer(contract_size=1.0, min_position_size=1.0, max_position_size=20_000.0)
        sized = sizer.size(
            _plan().setup, 1.15, 1.14, AccountContext(10_000.0, 0.01)
        )
        assert sized is not None
        self.assertAlmostEqual(sized.risk_amount, 100.0)
        self.assertAlmostEqual(sized.position_size, 10_000.0)
        self.assertIsNone(
            FixedRiskSizer(max_position_size=1.0).size(
                _plan().setup, 1.15, 1.14, AccountContext(10_000.0, 0.01)
            )
        )
        self.assertIsNone(
            FixedRiskSizer(min_position_size=20_000.0).size(
                _plan().setup, 1.15, 1.14, AccountContext(10_000.0, 0.01)
            )
        )

    def test_simulator_can_reject_size_outside_bounds(self) -> None:
        sim = TradeSimulator(min_position_size=20_000.0)
        sim.add_plan(_plan(entry=1.15, stop=1.14))
        sim.update(_bar(0))
        self.assertEqual(len(sim.get_all_closed_trades()), 0)
        self.assertEqual(sim.terminated_setups[0].reason, "REJECTED_SIZE_INVALID")


class GapExecutionTests(unittest.TestCase):
    def _filled(self) -> TradeSimulator:
        sim = TradeSimulator(
            position_sizer=FixedRiskSizer(),
            account=AccountContext(10_000.0, 0.01),
        )
        sim.add_plan(_plan())
        sim.update(_bar(0, open_=1.15, high=1.155, low=1.149, close=1.15))
        return sim

    def test_gap_through_stop_records_actual_loss(self) -> None:
        sim = self._filled()
        sim.update(_bar(1, open_=1.10, high=1.18, low=1.09, close=1.15))
        trade = sim.get_all_closed_trades()[0]
        self.assertEqual(trade.close_reason, "AMBIGUITY")
        self.assertAlmostEqual(trade.exit_price, 1.10)
        self.assertAlmostEqual(trade.pnl_r, -5.0)
        self.assertEqual(
            trade.execution_assumption,
            "both_levels_touched_gap_through_stop_at_open",
        )

    def test_both_levels_inside_bar_remains_conservative_stop(self) -> None:
        sim = self._filled()
        sim.update(_bar(1, open_=1.15, high=1.18, low=1.13, close=1.15))
        trade = sim.get_all_closed_trades()[0]
        self.assertEqual(trade.close_reason, "AMBIGUITY")
        self.assertAlmostEqual(trade.exit_price, 1.14)
        self.assertAlmostEqual(trade.pnl_r, -1.0)
        self.assertEqual(
            trade.execution_assumption,
            "both_levels_touched_stop_first_conservative",
        )

    def test_gap_through_tp_does_not_assume_favourable_fill(self) -> None:
        sim = self._filled()
        sim.update(_bar(1, open_=1.20, high=1.21, low=1.16, close=1.20))
        trade = sim.get_all_closed_trades()[0]
        self.assertEqual(trade.close_reason, "TP")
        self.assertAlmostEqual(trade.exit_price, 1.17)
        self.assertAlmostEqual(trade.pnl_r, 2.0)

    def test_entry_and_exit_same_candle(self) -> None:
        sim = TradeSimulator(
            position_sizer=FixedRiskSizer(),
            account=AccountContext(10_000.0, 0.01),
        )
        sim.add_plan(_plan())
        sim.update(_bar(0, open_=1.15, high=1.18, low=1.145, close=1.16))
        trade = sim.get_all_closed_trades()[0]
        self.assertEqual(trade.close_reason, "TP")
        self.assertEqual(trade.entry_time, T0)
        self.assertEqual(trade.exit_time, T0)
        self.assertEqual(trade.holding_duration_candles, 1)

    def test_missing_candle_cancels_pending_plan(self) -> None:
        sim = TradeSimulator()
        sim.add_plan(_plan())
        sim.finalize_backtest(["EURUSD"], {})
        self.assertEqual(sim.terminated_setups[0].reason, "CANCELLED_END_OF_DATA")


class CloseOutsideTransitionTests(unittest.TestCase):
    def test_close_outside_emits_only_on_inside_to_outside_transition(self) -> None:
        book = ZoneBook(
            symbol="EURUSD",
            zones=(
                Zone(
                    id=1,
                    name="z",
                    low=1.150,
                    high=1.152,
                    timeframe="H1",
                    strength=5,
                ),
            ),
        )
        strategy = BreakoutStrategy(zone_book=book)
        closes = [1.153, 1.154, 1.151, 1.153, 1.154]
        counts = []
        for minute, close in enumerate(closes):
            signals = strategy.evaluate(
                Bar("EURUSD", T0 + timedelta(minutes=minute), close, close + 0.001, close - 0.001, close)
            )
            counts.append(sum(1 for s in signals if s.signal.value == "close_outside"))
        self.assertEqual(counts, [0, 0, 0, 1, 0])


class DuplicateTimestampTests(unittest.TestCase):
    def test_feature_repository_rejects_duplicate_entry_timestamp(self) -> None:
        bars = [_bar(0), _bar(1), _bar(1), _bar(2)]
        repo = FeatureRepository()
        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            repo.materialize("EURUSD", {"M1": bars}, entry_timeframe="M1")

    def test_causal_aggregation_rejects_duplicate_source_timestamp(self) -> None:
        bars = [
            Bar(
                "EURUSD",
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
                + timedelta(minutes=index),
                1.0,
                1.1,
                0.9,
                1.0,
            )
            for index in range(60)
        ]
        bars[30] = bars[29]
        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            aggregate_completed_bars(
                bars,
                source_timeframe="M1",
                target_timeframe="H1",
                asof=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
                symbol="EURUSD",
            )


if __name__ == "__main__":
    unittest.main()
