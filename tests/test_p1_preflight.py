"""P1 structured pre-backtest validation tests."""

from __future__ import annotations

import unittest
from datetime import date

from server.preflight import validate_backtest


class PreflightTests(unittest.TestCase):
    def test_valid_s008_has_no_blocking_errors(self) -> None:
        result = validate_backtest(
            dataset_id="EURUSD/M1/2026",
            strategy_id="S008",
            timeframe="M1",
            start=date(2026, 5, 1),
            end=date(2026, 5, 5),
            cost_profile_id="zero_costs",
        )
        self.assertTrue(result["valid"])
        self.assertFalse(result["errors"])
        self.assertGreaterEqual(len(result["warnings"]), 0)

    def test_audusd_zone_strategy_is_blocked(self) -> None:
        result = validate_backtest(
            dataset_id="AUDUSD/M1/2026",
            strategy_id="S002",
            timeframe="M1",
            start=date(2026, 5, 4),
            end=date(2026, 5, 5),
        )
        self.assertFalse(result["valid"])
        self.assertIn(
            "ZONE_BOOK_MISSING", [item["code"] for item in result["errors"]]
        )

    def test_unknown_dataset_strategy_and_cost_profile(self) -> None:
        result = validate_backtest(
            dataset_id="NOPE/M1/2026",
            strategy_id="NOPE",
            timeframe="M1",
            cost_profile_id="missing-profile",
        )
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("DATASET_NOT_FOUND", codes)
        self.assertIn("STRATEGY_NOT_AVAILABLE", codes)
        self.assertIn("COST_PROFILE_INVALID", codes)

    def test_invalid_range_and_risk(self) -> None:
        result = validate_backtest(
            dataset_id="EURUSD/M1/2026",
            strategy_id="S008",
            timeframe="M1",
            start=date(2026, 7, 1),
            end=date(2026, 7, 2),
            r_multiple=0,
            risk_fraction=0.5,
        )
        codes = {item["code"] for item in result["errors"]}
        self.assertIn("RANGE_INVALID", codes)
        self.assertIn("R_MULTIPLE_INVALID", codes)
        self.assertIn("RISK_FRACTION_INVALID", codes)

    def test_proxy_cost_warning_is_present(self) -> None:
        result = validate_backtest(
            dataset_id="EURUSD/M1/2026",
            strategy_id="S008",
            timeframe="M1",
            start=date(2026, 5, 1),
            end=date(2026, 5, 5),
            cost_profile_id="proxy_forex_v1",
        )
        self.assertIn("ESTIMATED_COSTS", [item["code"] for item in result["warnings"]])
