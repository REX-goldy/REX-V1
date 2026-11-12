"""P1 API contract tests for cost, quality, preflight and validation."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from server import main as api
from server import research_service as service


class P1ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {"REX_RUNS_DIR": str(self.root / "runs")},
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_cost_profiles_are_available(self) -> None:
        profiles = api.cost_profiles()
        ids = {item["id"] for item in profiles}
        self.assertIn("zero_costs", ids)
        self.assertIn("proxy_forex_v1", ids)
        proxy = next(item for item in profiles if item["id"] == "proxy_forex_v1")
        self.assertTrue(proxy["estimated"])
        self.assertIn("not observed", proxy["description"].lower())

    def test_dataset_quality_endpoint(self) -> None:
        report = api.dataset_quality("EURUSD/M1/2026")
        self.assertEqual(report["counts"]["unexpected_gap_count"], 10)
        self.assertEqual(report["counts"]["missing_open_minutes"], 17)

    def test_preflight_endpoint_rejects_audusd_zones(self) -> None:
        result = api.validate_backtest_endpoint(
            api.BacktestRequest(
                dataset_id="AUDUSD/M1/2026",
                strategy_id="S002",
                timeframe="M1",
                start_date=date(2026, 5, 4),
                end_date=date(2026, 5, 5),
            )
        )
        self.assertFalse(result["valid"])
        self.assertIn(
            "ZONE_BOOK_MISSING", [item["code"] for item in result["errors"]]
        )

    def test_costed_backtest_exposes_gross_net_and_validation(self) -> None:
        result = service.run_backtest(
            dataset_id="EURUSD/M1/2026",
            strategy_id="S008",
            timeframe="M1",
            start=date(2026, 5, 1),
            end=date(2026, 5, 3),
            parameters={},
            cost_profile_id="proxy_forex_v1",
        )
        self.assertEqual(result["cost_profile"]["id"], "proxy_forex_v1")
        self.assertIsNotNone(result["net_metrics"])
        self.assertNotEqual(
            result["metrics"]["expectancy"], result["net_metrics"]["expectancy"]
        )
        self.assertEqual(result["dataset_quality"]["counts"]["unexpected_gap_count"], 10)
        if result["trades"]:
            trade = result["trades"][0]
            self.assertIsNotNone(trade["net_pnl_r"])
            self.assertIsNotNone(trade["total_cost_r"])
            self.assertEqual(trade["cost_profile_id"], "proxy_forex_v1")
        validation = api.validate_run_endpoint(result["id"])
        self.assertTrue(validation["valid"], validation["findings"][:3])
