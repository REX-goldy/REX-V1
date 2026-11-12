"""P1 independent trade/run validation tests."""

from __future__ import annotations

import unittest

from backtests.validation import validate_run
from backtests.costs import get_cost_profile


def _run() -> dict:
    profile = get_cost_profile("proxy_forex_v1")
    cost = 0.016
    trade = {
        "symbol": "EURUSD",
        "direction": "LONG",
        "entry_time": "2026-01-01T12:01:00",
        "exit_time": "2026-01-01T12:02:00",
        "entry_price": 1.15,
        "exit_price": 1.17,
        "sl_price": 1.14,
        "tp_price": 1.17,
        "pnl_r": 2.0,
        "close_reason": "TP",
        "holding_duration_candles": 1,
        "planned_entry_price": 1.15,
        "planned_position_size": 10000.0,
        "planned_risk_amount": 100.0,
        "position_size": 10000.0,
        "realized_risk_amount": 100.0,
        "total_cost_r": cost,
        "net_pnl_r": 2.0 - cost,
    }
    return {
        "id": "synthetic-validation-run",
        "strategy": {"id": "S008"},
        "cost_profile": profile.to_dict(),
        "trades": [trade],
        "metrics": {
            "total_trades": 1,
            "wins": 1,
            "losses": 0,
            "win_rate": 100.0,
            "profit_factor": None,
            "expectancy": 2.0,
            "max_drawdown": 0.0,
            "largest_win": 2.0,
            "largest_loss": 0.0,
        },
        "net_metrics": {
            "total_trades": 1,
            "expectancy": 2.0 - cost,
            "max_drawdown": 0.0,
            "profit_factor": None,
        },
    }


class IndependentValidationTests(unittest.TestCase):
    def test_valid_trade_and_cost_reconcile(self) -> None:
        result = validate_run(_run())
        self.assertTrue(result["valid"])
        self.assertEqual(result["checked_trades"], 1)
        self.assertEqual(result["error_count"], 0)

    def test_pnl_formula_mismatch_is_detected(self) -> None:
        run = _run()
        run["trades"][0]["pnl_r"] = 9.99
        result = validate_run(run)
        self.assertFalse(result["valid"])
        self.assertIn("PNL_FORMULA_MISMATCH", [item["code"] for item in result["findings"]])

    def test_realised_risk_mismatch_is_detected(self) -> None:
        run = _run()
        run["trades"][0]["realized_risk_amount"] = 500.0
        result = validate_run(run)
        self.assertIn("REALISED_RISK_MISMATCH", [item["code"] for item in result["findings"]])

    def test_cost_mismatch_is_detected(self) -> None:
        run = _run()
        run["trades"][0]["total_cost_r"] = 0.5
        result = validate_run(run)
        self.assertIn("COST_TOTAL_MISMATCH", [item["code"] for item in result["findings"]])

    def test_net_metric_mismatch_is_detected(self) -> None:
        run = _run()
        run["net_metrics"]["expectancy"] = 1.0
        result = validate_run(run)
        self.assertIn("NET_METRIC_EXPECTANCY", [item["code"] for item in result["findings"]])

    def test_ambiguous_favourable_is_rejected(self) -> None:
        run = _run()
        run["trades"][0].update(
            {
                "close_reason": "AMBIGUITY",
                "entry_price": 1.15,
                "exit_price": 1.16,
                "sl_price": 1.14,
                "pnl_r": 1.0,
                "total_cost_r": 0.0,
                "net_pnl_r": 1.0,
            }
        )
        result = validate_run(run)
        self.assertIn("AMBIGUITY_FAVOURABLE", [item["code"] for item in result["findings"]])

    def test_missing_trade_fields_are_explicit(self) -> None:
        run = _run()
        del run["trades"][0]["entry_price"]
        result = validate_run(run)
        self.assertFalse(result["valid"])
        self.assertIn("PRICE_INVALID", [item["code"] for item in result["findings"]])
