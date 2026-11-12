"""PositionSizer: risk amount and position size from account context."""

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from core.market.instrument import get_instrument
from models.account_context import AccountContext
from models.trade_setup import TradeSetup


@dataclass(frozen=True)
class SizeResult:
    """Sizing outcome for a planned trade."""

    position_size: float
    risk_amount: float


class PositionSizer(Protocol):
    """Compute position size and risk amount from entry, stop, and account."""

    def size(
        self,
        setup: TradeSetup,
        entry: float,
        stop: float,
        account: AccountContext,
    ) -> SizeResult | None:
        """Return size parameters, or None when sizing is impossible."""
        ...


class FixedRiskSizer:
    """Size so that stop distance risks a fixed fraction of account equity.

    ``contract_size`` converts a price distance into account-currency risk per
    position unit. The default 1.0 preserves the existing research convention
    (position units are price units). Currency conversion is intentionally not
    invented here; callers that need a different quote/account currency should
    supply a contract size reflecting that conversion.

    Optional min/max position bounds fail closed by returning None when the
    computed size is outside the permitted range.
    """

    def __init__(
        self,
        *,
        contract_size: float | None = None,
        min_position_size: float = 0.0,
        max_position_size: float | None = None,
    ) -> None:
        if contract_size is not None and contract_size <= 0:
            raise ValueError("contract_size must be positive")
        if min_position_size < 0:
            raise ValueError("min_position_size cannot be negative")
        if max_position_size is not None and max_position_size <= min_position_size:
            raise ValueError("max_position_size must exceed min_position_size")
        self.contract_size = contract_size
        self.min_position_size = min_position_size
        self.max_position_size = max_position_size

    def size(
        self,
        setup: TradeSetup,
        entry: float,
        stop: float,
        account: AccountContext,
    ) -> SizeResult | None:
        stop_distance = abs(entry - stop)
        if stop_distance <= 1e-12:
            return None
        if account.equity <= 0 or account.risk_fraction <= 0:
            return None

        risk_amount = account.equity * account.risk_fraction
        contract_size = self.contract_size
        if contract_size is None:
            instrument = get_instrument(setup.symbol)
            contract_size = instrument.contract_size if instrument is not None else 1.0
        position_size = risk_amount / (stop_distance * contract_size)
        if not isfinite(position_size) or position_size <= 0:
            return None
        if position_size < self.min_position_size:
            return None
        if (
            self.max_position_size is not None
            and position_size > self.max_position_size
        ):
            return None
        return SizeResult(position_size=position_size, risk_amount=risk_amount)
