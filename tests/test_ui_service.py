"""Offline tests for the UI research service."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from historical.storage import HistoricalStorage
from models.bar import Bar
from server import research_service as service


def _bars(count: int = 300, symbol: str = "EURUSD") -> list[Bar]:
    start = datetime(2024, 1, 2, 0, 0)
    bars: list[Bar] = []
    price = 1.1000
    for index in range(count):
        # Alternate small ranges so the sweep rule has data to inspect.
        open_ = price
        close = price + (0.0002 if index % 2 == 0 else -0.0002)
        bars.append(
            Bar(
                symbol,
                start + timedelta(minutes=index),
                open_,
                max(open_, close) + 0.0003,
                min(open_, close) - 0.0003,
                close,
            )
        )
        price = close
    return bars


class UIServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name) / "data"
        self.runs_dir = Path(self.temp.name) / "runs"
        self.keys_file = Path(self.temp.name) / "keys" / "provider_keys.json"
        self.env = patch.dict(
            os.environ,
            {
                "REX_DATA_DIR": str(self.data_dir),
                "REX_RUNS_DIR": str(self.runs_dir),
                "REX_KEYS_FILE": str(self.keys_file),
            },
            clear=False,
        )
        self.env.start()
        storage = HistoricalStorage(self.data_dir)
        storage.write_year(
            "EURUSD",
            "M1",
            2024,
            _bars(),
            date(2024, 1, 1),
            date(2024, 12, 31),
            provider="dukascopy",
            bar_count=300,
            requested_start=date(2024, 1, 1),
            requested_end=date(2024, 12, 31),
            retrieved_at=datetime(2024, 12, 31, 23, 59),
            duplicate_count=0,
            invalid_bar_count=0,
            timestamp_gap_count=0,
            quality_notes=("fixture",),
        )

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_overview_reports_real_dataset(self) -> None:
        overview = service.overview()
        self.assertEqual([item["id"] for item in overview["datasets"]], ["EURUSD/M1/2024"])
        dataset = overview["datasets"][0]
        self.assertEqual(dataset["provider"], "dukascopy")
        self.assertEqual(dataset["bar_count"], 300)
        self.assertEqual(dataset["coverage"]["requested_start"], "2024-01-01")
        self.assertEqual(
            {item["id"] for item in overview["strategies"]},
            {"CORE_ZONE_BREAKOUT", "S002", "S008"},
        )

    def test_multiple_pair_discovery_and_backtest(self) -> None:
        storage = HistoricalStorage(self.data_dir)
        storage.write_year(
            "GBPUSD",
            "M1",
            2024,
            _bars(symbol="GBPUSD"),
            date(2024, 1, 1),
            date(2024, 12, 31),
            provider="twelve_data",
            bar_count=300,
        )
        ids = {item["id"] for item in service.list_datasets()}
        self.assertIn("EURUSD/M1/2024", ids)
        self.assertIn("GBPUSD/M1/2024", ids)

        run = service.run_backtest(
            dataset_id="GBPUSD/M1/2024",
            strategy_id="S008",
            timeframe="M5",
            parameters={"lookback": 5},
            start=date(2024, 1, 2),
            end=date(2024, 1, 2),
        )
        self.assertEqual(run["dataset"]["symbol"], "GBPUSD")
        self.assertEqual(run["dataset"]["timeframe"], "M5")
        self.assertEqual(run["bar_count"], 60)

    def test_dataset_detail_and_bars(self) -> None:
        detail = service.dataset_detail("EURUSD/M1/2024")
        self.assertEqual(detail["metadata"]["provider"], "dukascopy")
        bars = service.dataset_bars("EURUSD/M1/2024", limit=10)
        self.assertEqual(len(bars), 10)
        self.assertIn("time", bars[0])
        self.assertEqual(bars[-1]["close"], _bars()[-1].close)

    def test_backtest_persists_run_and_metrics(self) -> None:
        run = service.run_backtest(
            dataset_id="EURUSD/M1/2024",
            strategy_id="S008",
            parameters={"lookback": 5, "min_wick_ratio": 0.5},
        )
        self.assertTrue(run["simulated"])
        self.assertEqual(run["bar_count"], 300)
        self.assertIn("total_trades", run["metrics"])
        self.assertTrue(any("Transaction costs" in item for item in run["warnings"]))
        path = self.runs_dir / f"{run['id']}.json"
        self.assertTrue(path.is_file())
        self.assertEqual(service.get_run(run["id"])["id"], run["id"])
        self.assertEqual(service.list_runs()[0]["id"], run["id"])

        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("apikey", json.dumps(saved).lower())
        self.assertNotIn("api_key", json.dumps(saved).lower())

    def test_signal_study_is_marked_as_not_simulated(self) -> None:
        run = service.run_backtest(
            dataset_id="EURUSD/M1/2024",
            strategy_id="CORE_ZONE_BREAKOUT",
            parameters={},
        )
        self.assertFalse(run["simulated"])
        self.assertEqual(run["metrics"]["total_trades"], 0)
        self.assertTrue(any("Signal study" in item for item in run["warnings"]))

    def test_unknown_parameter_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            service.run_backtest(
                dataset_id="EURUSD/M1/2024",
                strategy_id="S008",
                parameters={"not_a_parameter": 1},
            )

    def test_download_refuses_cross_provider_partition(self) -> None:
        with self.assertRaises(ValueError):
            service.download_dataset(
                provider="twelve_data",
                symbol="EURUSD",
                timeframe="M1",
                start=date(2024, 1, 1),
                end=date(2024, 1, 2),
            )

    def test_derived_frame_and_range_validation(self) -> None:
        frame = service.frame_detail("EURUSD/M1/2024", timeframe="M5")
        self.assertTrue(frame["derived"])
        self.assertEqual(frame["timeframe"], "M5")
        self.assertEqual(frame["bar_count"], 60)

        summary = service.range_summary(
            "EURUSD/M1/2024",
            timeframe="M5",
            start=date(2024, 1, 2),
            end=date(2024, 1, 2),
        )
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["bar_count"], 60)

        outside = service.range_summary(
            "EURUSD/M1/2024",
            timeframe="M5",
            start=date(2023, 12, 1),
            end=date(2024, 1, 2),
        )
        self.assertFalse(outside["valid"])
        self.assertIn("before the first available bar", outside["error"])

    def test_backtest_on_derived_frame(self) -> None:
        run = service.run_backtest(
            dataset_id="EURUSD/M1/2024",
            strategy_id="S008",
            timeframe="M5",
            parameters={"lookback": 5},
            start=date(2024, 1, 2),
            end=date(2024, 1, 2),
        )
        self.assertEqual(run["request"]["timeframe"], "M5")
        self.assertEqual(run["range"]["bar_count"], 60)
        self.assertEqual(run["dataset"]["timeframe"], "M5")
        self.assertTrue(run["dataset"]["derived"])
        self.assertTrue(any("derived from stored M1" in item for item in run["warnings"]))

    def test_download_validation(self) -> None:
        with self.assertRaises(ValueError):
            service.download_dataset(
                provider="twelve_data",
                symbol="USDJPY",
                timeframe="M1",
                start=date(2024, 1, 1),
                end=date(2024, 1, 2),
            )
        with self.assertRaises(ValueError):
            service.download_dataset(
                provider="twelve_data",
                symbol="EURUSD",
                timeframe="M1",
                start=date(2024, 1, 1),
                end=date(2024, 3, 1),
            )


if __name__ == "__main__":
    unittest.main()
