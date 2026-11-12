"""P2 experiment persistence, status and traceability tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import strategy_workspace as workspace


RUN_ID = "20260101T000000Z_p2"


def _run() -> dict:
    return {
        "id": RUN_ID,
        "created_at": "2026-01-01T00:00:00+00:00",
        "strategy": {"id": "S008", "name": "Liquidity Sweep"},
        "dataset_id": "EURUSD/M1/2026",
        "dataset": {"symbol": "EURUSD", "timeframe": "M1"},
        "request": {"start": "2026-06-01", "end": "2026-06-02", "timeframe": "M1", "r_multiple": 2.0, "equity": 100000.0, "risk_fraction": 0.01},
        "parameters": {"lookback": 10, "min_wick_ratio": 0.6, "tolerance": 0.0},
        "metrics": {"total_signals": 2, "total_trades": 2, "wins": 1, "losses": 1, "win_rate": 50.0, "profit_factor": 1.0, "expectancy": 0.0, "max_drawdown_r": 1.0, "largest_win": 1.0, "largest_loss": -1.0, "ambiguous_exits": 0, "avg_holding_duration": 2.0},
        "net_metrics": {"total_signals": 2, "total_trades": 2, "wins": 1, "losses": 1, "win_rate": 50.0, "profit_factor": 0.968503937007874, "expectancy": -0.016, "max_drawdown_r": 1.016, "largest_win": 0.984, "largest_loss": -1.016, "ambiguous_exits": 0, "avg_holding_duration": 2.0},
        "trades": [
            {"symbol": "EURUSD", "direction": "LONG", "entry_time": "2026-01-01T00:01:00", "exit_time": "2026-01-01T00:02:00", "entry_price": 1.15, "exit_price": 1.16, "sl_price": 1.14, "tp_price": 1.16, "pnl_r": 1.0, "close_reason": "TP", "holding_duration_candles": 1, "planned_entry_price": 1.15, "planned_position_size": 10000.0, "planned_risk_amount": 100.0, "position_size": 10000.0, "realized_risk_amount": 100.0, "total_cost_r": 0.016, "net_pnl_r": 0.984},
            {"symbol": "EURUSD", "direction": "SHORT", "entry_time": "2026-01-01T01:01:00", "exit_time": "2026-01-01T01:02:00", "entry_price": 1.16, "exit_price": 1.17, "sl_price": 1.17, "tp_price": 1.15, "pnl_r": -1.0, "close_reason": "SL", "holding_duration_candles": 1, "planned_entry_price": 1.16, "planned_position_size": 10000.0, "planned_risk_amount": 100.0, "position_size": 10000.0, "realized_risk_amount": 100.0, "total_cost_r": 0.016, "net_pnl_r": -1.016},
        ],
        "cost_profile": {"id": "proxy_forex_v1", "estimated": True, "spread_price": 0.00012, "slippage_price_per_side": 0.00002, "commission_per_round_trip": 0.0, "swap_per_night_r": 0.0, "instrument_overrides": {}},
        "warnings": [],
        "assumptions": {"costs_applied": True},
        "bar_count": 100,
        "trades_truncated": False,
    }


class ExperimentPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runs = self.root / "runs"
        self.runs.mkdir()
        (self.runs / f"{RUN_ID}.json").write_text(json.dumps(_run()))
        self.env = patch.dict(
            os.environ,
            {
                "REX_WORKSPACE_FILE": str(self.root / "workspace.json"),
                "REX_RUNS_DIR": str(self.runs),
            },
            clear=False,
        )
        self.env.start()
        self.s008 = next(
            item for item in workspace.list_strategies()
            if item["registry_strategy_id"] == "S008"
        )
        self.detail = workspace.get_strategy(self.s008["id"])
        self.baseline = self.detail["variations"][0]

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_completed_experiment_has_full_traceability(self) -> None:
        detail = workspace.record_experiment(
            self.s008["id"],
            {
                "variation_id": self.baseline["id"],
                "run_id": RUN_ID,
                "expected_outcome": "Small positive net expectancy.",
                "actual_outcome": "Gross flat, net negative.",
                "hypothesis_supported": False,
                "next_steps": "Test a wider stop.",
            },
        )
        experiment = detail["experiments"][0]
        self.assertEqual(experiment["status"], "Completed")
        self.assertEqual(experiment["strategy_id"], self.s008["id"])
        self.assertEqual(experiment["cost_profile"]["id"], "proxy_forex_v1")
        self.assertEqual(experiment["validation_status"], "passed")
        self.assertIsNotNone(experiment["dataset_hash"])
        self.assertEqual(experiment["gross_results"]["expectancy"], 0.0)
        self.assertEqual(experiment["net_results"]["expectancy"], -0.016)
        self.assertEqual(experiment["hypothesis_supported"], False)
        self.assertEqual(experiment["next_steps"], "Test a wider stop.")

    def test_planned_running_archive_statuses(self) -> None:
        detail = workspace.create_planned_experiment(
            self.s008["id"],
            {
                "variation_id": self.baseline["id"],
                "dataset_id": "EURUSD/M1/2026",
                "timeframe": "M1",
                "name": "Planned P2",
                "hypothesis": "A planned experiment.",
                "expected_outcome": "See if it works.",
            },
        )
        experiment = detail["experiments"][0]
        self.assertEqual(experiment["status"], "Planned")
        self.assertIsNone(experiment["run_id"])
        running = workspace.update_experiment(
            self.s008["id"], experiment["id"], {"status": "Running"}
        )
        self.assertEqual(running["experiments"][0]["status"], "Running")
        archived = workspace.update_experiment(
            self.s008["id"], experiment["id"], {"status": "Archived"}
        )
        self.assertEqual(archived["experiments"][0]["status"], "Archived")
        with self.assertRaises(workspace.WorkspaceValidationError):
            workspace.update_experiment(
                self.s008["id"], experiment["id"], {"status": "Draft"}
            )

    def test_completed_requires_run_and_validation(self) -> None:
        detail = workspace.create_planned_experiment(
            self.s008["id"],
            {
                "variation_id": self.baseline["id"],
                "dataset_id": "EURUSD/M1/2026",
                "timeframe": "M1",
                "name": "Cannot complete",
            },
        )
        experiment = detail["experiments"][0]
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.update_experiment(
                self.s008["id"], experiment["id"], {"status": "Completed"}
            )

    def test_completed_narrative_requires_amendment(self) -> None:
        detail = workspace.record_experiment(
            self.s008["id"], {"variation_id": self.baseline["id"], "run_id": RUN_ID}
        )
        experiment = detail["experiments"][0]
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.update_experiment(
                self.s008["id"], experiment["id"], {"notes": "direct mutation"}
            )
        amended = workspace.amend_experiment(
            self.s008["id"],
            experiment["id"],
            {
                "notes": "amended note",
                "actual_outcome": "amended outcome",
                "hypothesis_supported": False,
                "author": "auditor",
                "reason": "corrected research note",
            },
        )
        changed = amended["experiments"][0]
        self.assertEqual(changed["notes"], "")
        self.assertEqual(len(changed["amendments"]), 3)
        self.assertEqual(changed["amendments"][0]["author"], "auditor")

    def test_missing_zone_reference_is_rejected(self) -> None:
        run = _run()
        run["zone_ids"] = ["missing-zone"]
        (self.runs / f"{RUN_ID}.json").write_text(json.dumps(run))
        with self.assertRaises(workspace.WorkspaceValidationError):
            workspace.record_experiment(
                self.s008["id"],
                {"variation_id": self.baseline["id"], "run_id": RUN_ID},
            )

    def test_dashboard_uses_real_experiments(self) -> None:
        workspace.record_experiment(
            self.s008["id"], {"variation_id": self.baseline["id"], "run_id": RUN_ID}
        )
        data = workspace.dashboard()
        self.assertGreaterEqual(data["strategy_count"], 3)
        self.assertEqual(data["experiment_count"], 1)
        self.assertEqual(data["recent_experiments"][0]["status"], "Completed")
