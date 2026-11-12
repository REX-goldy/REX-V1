"""P1 transaction-cost model and BacktestRunner integration tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backtests.costs import (
    CostModelError,
    TransactionCostModel,
    get_cost_profile,
    get_cost_profiles,
)
from backtests.trade_simulator import TradeSimulator
from execution.sizers import FixedRiskSizer
from models.account_context import AccountContext
from models.bar import Bar
from models.entry_model import EntryModel
from models.trade_direction import TradeDirection
from models.trade_plan import TradePlan
from models.trade_setup import TradeSetup

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _plan() -> TradePlan:
    setup = TradeSetup(
        "p1", "EURUSD", TradeDirection.LONG, "P1", T0, "p1",
        stop_hint=1.14, entry_hint=1.15, entry_model_hint=EntryModel.NEXT_CANDLE_OPEN,
    )
    return TradePlan(
        setup, EntryModel.NEXT_CANDLE_OPEN, 1.15, 1.14, 1.17, 2.0, 1.0, 100.0, 5, T0
    )


class CostProfileTests(unittest.TestCase):
    def test_default_profiles_are_explicit(self) -> None:
        profiles = {item.id: item for item in get_cost_profiles()}
        self.assertIn("zero_costs", profiles)
        self.assertIn("proxy_forex_v1", profiles)
        self.assertFalse(profiles["zero_costs"].estimated)
        self.assertTrue(profiles["proxy_forex_v1"].estimated)
        self.assertIn("not observed", profiles["proxy_forex_v1"].description.lower())

    def test_instrument_override_and_breakdown(self) -> None:
        profile = get_cost_profile("proxy_forex_v1")
        eur = TransactionCostModel(profile).calculate(
            symbol="EURUSD", entry_price=1.15, exit_price=1.17,
            risk_distance=0.01, risk_amount=1000.0, gross_pnl_r=2.0,
        )
        jpy = TransactionCostModel(profile).calculate(
            symbol="USDJPY", entry_price=150.0, exit_price=151.0,
            risk_distance=1.0, risk_amount=1000.0, gross_pnl_r=1.0,
        )
        self.assertAlmostEqual(eur.spread_r, 0.012)
        self.assertAlmostEqual(eur.slippage_r, 0.004)
        self.assertAlmostEqual(eur.net_pnl_r, 1.984)
        self.assertAlmostEqual(jpy.spread_r, 0.012)
        self.assertGreater(jpy.total_r, 0.0)

    def test_invalid_cost_inputs_fail_closed(self) -> None:
        with self.assertRaises(CostModelError):
            TransactionCostModel(get_cost_profile("zero_costs")).calculate(
                symbol="EURUSD", entry_price=1.15, exit_price=1.15,
                risk_distance=0.0, risk_amount=100.0, gross_pnl_r=0.0,
            )


class CostedSimulatorTests(unittest.TestCase):
    def test_gross_unchanged_and_net_separate(self) -> None:
        profile = get_cost_profile("proxy_forex_v1")
        sim = TradeSimulator(
            position_sizer=FixedRiskSizer(),
            account=AccountContext(10_000.0, 0.01),
            cost_model=TransactionCostModel(profile),
        )
        sim.add_plan(_plan())
        sim.update(Bar("EURUSD", T0, 1.15, 1.155, 1.149, 1.15))
        sim.update(Bar("EURUSD", T0 + timedelta(minutes=1), 1.16, 1.18, 1.155, 1.17))
        trade = sim.get_all_closed_trades()[0]
        self.assertEqual(trade.close_reason, "TP")
        self.assertAlmostEqual(trade.pnl_r, 2.0)
        self.assertGreater(trade.total_cost_r or 0.0, 0.0)
        self.assertAlmostEqual(trade.net_pnl_r or 0.0, 2.0 - (trade.total_cost_r or 0.0))
        self.assertEqual(trade.cost_profile_id, "proxy_forex_v1")

    def test_zero_profile_is_explicit_gross(self) -> None:
        sim = TradeSimulator(
            position_sizer=FixedRiskSizer(),
            account=AccountContext(10_000.0, 0.01),
            cost_model=TransactionCostModel(get_cost_profile("zero_costs")),
        )
        sim.add_plan(_plan())
        sim.update(Bar("EURUSD", T0, 1.15, 1.155, 1.149, 1.15))
        sim.update(Bar("EURUSD", T0 + timedelta(minutes=1), 1.16, 1.18, 1.155, 1.17))
        trade = sim.get_all_closed_trades()[0]
        self.assertEqual(trade.total_cost_r, 0.0)
        self.assertEqual(trade.net_pnl_r, trade.pnl_r)
