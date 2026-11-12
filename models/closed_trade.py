"""Closed trade model representing realized trade results."""

from dataclasses import dataclass
from datetime import datetime

from models.trade_direction import TradeDirection


@dataclass(frozen=True)
class ClosedTrade:
    """An immutable record of a completed trade."""

    symbol: str
    direction: TradeDirection
    entry_price: float
    entry_time: datetime
    exit_price: float
    exit_time: datetime
    sl_price: float
    tp_price: float
    pnl_r: float  # Profit or loss in risk units (R-multiples)
    close_reason: str  # "SL" | "TP" | "TIMEOUT" | "AMBIGUITY" | "FORCE_CLOSE_END_OF_DATA"
    holding_duration_candles: int
    signal_id: str
    strategy_id: str
    planned_entry_price: float | None = None
    planned_position_size: float | None = None
    planned_risk_amount: float | None = None
    position_size: float | None = None
    realized_risk_amount: float | None = None
    entry_slippage: float | None = None
    execution_assumption: str = ""
    spread_cost_r: float | None = None
    slippage_cost_r: float | None = None
    commission_cost_r: float | None = None
    swap_cost_r: float | None = None
    total_cost_r: float | None = None
    net_pnl_r: float | None = None
    cost_profile_id: str | None = None
