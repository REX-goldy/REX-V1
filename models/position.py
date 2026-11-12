"""Position model to represent open positions."""

from dataclasses import dataclass
from datetime import datetime

from models.trade_direction import TradeDirection


@dataclass
class Position:
    """An active, open market position."""

    symbol: str
    direction: TradeDirection
    entry_price: float
    entry_time: datetime
    sl_price: float
    tp_price: float
    max_hold_candles: int
    signal_id: str
    strategy_id: str
    elapsed_candles: int = 0
    planned_entry_price: float | None = None
    planned_position_size: float | None = None
    planned_risk_amount: float | None = None
    position_size: float | None = None
    risk_amount: float | None = None
    entry_slippage: float | None = None
