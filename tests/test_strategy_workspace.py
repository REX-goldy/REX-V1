"""Tests for the additive strategy research workspace."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import strategy_workspace as workspace


RUN_ID = "20260101T000000Z_workspace"
SECOND_RUN_ID = "20260102T000000Z_workspace"


def _run(run_id: str, strategy_id: str = "S008", trades: int = 10) -> dict:
    return {
        "id": run_id,
        "created_at": "2026-01-01T00:00:00+00:00",
        "strategy": {"id": strategy_id, "name": "Liquidity Sweep"},
        "dataset_id": "EURUSD/M1/2026",
        "dataset": {"symbol": "EURUSD", "timeframe": "M1"},
        "request": {
            "start": "2026-06-01",
            "end": "2026-06-30",
            "timeframe": "M1",
            "r_multiple": 2.0,
            "equity": 100000.0,
            "risk_fraction": 0.01,
        },
        "parameters": {"lookback": 10, "min_wick_ratio": 0.6, "tolerance": 0.0},
        "metrics": {
            "total_signals": trades,
            "total_trades": trades,
            "wins": 4,
            "losses": trades - 4,
            "win_rate": 40.0,
            "profit_factor": 1.2,
            "expectancy": 0.1,
            "max_drawdown_r": 2.0,
            "largest_win": 2.0,
            "largest_loss": -1.0,
            "ambiguous_exits": 0,
            "avg_holding_duration": 3.0,
        },
        "trades": [],
        "warnings": [],
        "assumptions": {"entry_model": "next candle open", "costs_applied": False},
        "bar_count": 100,
        "trades_truncated": False,
    }


class StrategyWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace_file = self.root / "data" / "workspace.json"
        self.runs_dir = self.root / "runs"
        self.runs_dir.mkdir(parents=True)
        self.env = patch.dict(
            os.environ,
            {
                "REX_WORKSPACE_FILE": str(self.workspace_file),
                "REX_RUNS_DIR": str(self.runs_dir),
            },
            clear=False,
        )
        self.env.start()
        (self.runs_dir / f"{RUN_ID}.json").write_text(json.dumps(_run(RUN_ID)))
        (self.runs_dir / f"{SECOND_RUN_ID}.json").write_text(
            json.dumps(_run(SECOND_RUN_ID))
        )
        self.s008 = next(
            item
            for item in workspace.list_strategies()
            if item["registry_strategy_id"] == "S008"
        )
        self.detail = workspace.get_strategy(self.s008["id"])
        self.baseline = next(
            item for item in self.detail["variations"] if item["is_baseline"]
        )

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_seeded_real_strategies_and_documents(self) -> None:
        rows = workspace.list_strategies()
        self.assertEqual(
            {item["registry_strategy_id"] for item in rows},
            {"CORE_ZONE_BREAKOUT", "S002", "S008"},
        )
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(item["variation_count"] == 1 for item in rows))
        self.assertIn("implemented", self.detail["rules"])
        self.assertEqual(self.baseline["implementation_status"], "implemented")
        self.assertEqual(self.baseline["configuration_version"], 1)

    def test_create_edit_archive_and_duplicate_title(self) -> None:
        created = workspace.create_strategy(
            {
                "title": "Custom Research Hypothesis",
                "short_description": "A documentation-only strategy.",
                "category": "Custom",
                "status": "Draft",
                "tags": ["custom"],
            }
        )
        self.assertEqual(created["status"], "Draft")
        self.assertEqual(created["variations"][0]["implementation_status"], "documentation_only")
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.create_strategy(
                {"title": "custom research hypothesis", "short_description": "duplicate"}
            )
        updated = workspace.update_strategy(
            created["id"], {"status": "Research", "hypothesis": "Testable."}
        )
        self.assertEqual(updated["status"], "Research")
        archived = workspace.archive_strategy(created["id"])
        self.assertEqual(archived["status"], "Archived")
        self.assertEqual(len(workspace.list_strategies(query="custom")), 1)

    def test_search_status_and_title_sort(self) -> None:
        self.assertEqual(len(workspace.list_strategies(query="liquidity")), 1)
        self.assertEqual(workspace.list_strategies(query="liquidity")[0]["id"], self.s008["id"])
        self.assertEqual(workspace.list_strategies(status="Draft"), [])
        titles = [item["title"] for item in workspace.list_strategies(sort="title")]
        self.assertEqual(titles, sorted(titles))

    def test_notes_are_timestamped_and_editable(self) -> None:
        note = workspace.add_note(self.s008["id"], "Observe the retest close.")
        self.assertTrue(note["created_at"])
        updated = workspace.update_note(self.s008["id"], note["id"], "Updated observation.")
        self.assertEqual(updated["body"], "Updated observation.")
        detail = workspace.get_strategy(self.s008["id"])
        self.assertEqual(detail["notes"][0]["body"], "Updated observation.")
        workspace.delete_note(self.s008["id"], note["id"])
        self.assertEqual(workspace.get_strategy(self.s008["id"])["notes"], [])

    def test_multiple_variations_and_configuration_version(self) -> None:
        updated = workspace.create_variation(
            self.s008["id"],
            {
                "title": "V2 — Stronger confirmation",
                "description": "Require a stronger wick.",
                "parameter_config": {"min_wick_ratio": 0.8},
                "instruments": ["EURUSD"],
                "timeframes": ["M1", "M5"],
            },
        )
        self.assertEqual(len(updated["variations"]), 2)
        new_variation = updated["variations"][-1]
        self.assertFalse(new_variation["is_baseline"])
        self.assertEqual(new_variation["parameter_config"]["min_wick_ratio"], 0.8)
        edited = workspace.update_variation(
            self.s008["id"],
            new_variation["id"],
            {"parameter_config": {"min_wick_ratio": 0.9}},
        )
        changed = next(
            item for item in edited["variations"] if item["id"] == new_variation["id"]
        )
        self.assertEqual(changed["configuration_version"], 2)

    def test_invalid_parameters_and_docs_only_cannot_run(self) -> None:
        with self.assertRaises(workspace.WorkspaceValidationError):
            workspace.create_variation(
                self.s008["id"], {"title": "Bad", "parameter_config": {"unknown": 1}}
            )
        docs = workspace.create_strategy(
            {"title": "Docs Only", "short_description": "No implementation."}
        )
        docs_variation = docs["variations"][0]
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.record_experiment(
                docs["id"],
                {"variation_id": docs_variation["id"], "run_id": RUN_ID},
            )

    def test_record_experiment_links_real_run_and_keeps_metrics(self) -> None:
        detail = workspace.record_experiment(
            self.s008["id"],
            {
                "variation_id": self.baseline["id"],
                "run_id": RUN_ID,
                "name": "Baseline run",
            },
        )
        self.assertEqual(detail["linked_run_count"], 1)
        experiment = detail["experiments"][0]
        self.assertEqual(experiment["strategy_id"], self.s008["id"])
        self.assertEqual(experiment["variation_id"], self.baseline["id"])
        self.assertEqual(experiment["run_id"], RUN_ID)
        self.assertEqual(experiment["experiment_kind"], "baseline")
        self.assertEqual(experiment["metrics"]["total_trades"], 10)
        self.assertEqual(experiment["result_reference"]["run_id"], RUN_ID)
        self.assertTrue(experiment["run_available"])

    def test_experiment_rejects_duplicate_missing_and_wrong_strategy(self) -> None:
        workspace.record_experiment(
            self.s008["id"],
            {"variation_id": self.baseline["id"], "run_id": RUN_ID},
        )
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.record_experiment(
                self.s008["id"],
                {"variation_id": self.baseline["id"], "run_id": RUN_ID},
            )
        with self.assertRaises(workspace.WorkspaceValidationError):
            workspace.record_experiment(
                self.s008["id"],
                {"variation_id": self.baseline["id"], "run_id": "missing-run"},
            )
        wrong_path = self.runs_dir / "wrong.json"
        wrong_path.write_text(json.dumps(_run("wrong", strategy_id="S002")))
        with self.assertRaises(workspace.WorkspaceValidationError):
            workspace.record_experiment(
                self.s008["id"],
                {"variation_id": self.baseline["id"], "run_id": "wrong"},
            )

    def test_baseline_locks_after_experiment_and_clone_is_independent(self) -> None:
        workspace.record_experiment(
            self.s008["id"],
            {"variation_id": self.baseline["id"], "run_id": RUN_ID},
        )
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.update_variation(
                self.s008["id"], self.baseline["id"], {"title": "Changed baseline"}
            )
        cloned = workspace.clone_variation(
            self.s008["id"], self.baseline["id"], {"title": "V2 — Versioned baseline"}
        )
        source = next(item for item in cloned["variations"] if item["id"] == self.baseline["id"])
        copy = next(item for item in cloned["variations"] if item["title"] == "V2 — Versioned baseline")
        self.assertFalse(copy["is_baseline"])
        self.assertEqual(copy["cloned_from"], source["id"])
        self.assertEqual(copy["parameter_config"], source["parameter_config"])
        with self.assertRaises(workspace.WorkspaceConflict):
            workspace.archive_variation(self.s008["id"], self.baseline["id"])

    def test_comparison_requires_comparable_conditions(self) -> None:
        created = workspace.create_variation(
            self.s008["id"],
            {
                "title": "V2",
                "parameter_config": {"min_wick_ratio": 0.8},
                "instruments": ["EURUSD"],
                "timeframes": ["M1"],
            },
        )
        variation = created["variations"][-1]
        workspace.record_experiment(
            self.s008["id"],
            {"variation_id": self.baseline["id"], "run_id": RUN_ID},
        )
        detail = workspace.record_experiment(
            self.s008["id"],
            {"variation_id": variation["id"], "run_id": SECOND_RUN_ID},
        )
        self.assertEqual(len(detail["comparison"]), 1)
        group = detail["comparison"][0]
        self.assertEqual(group["dataset_id"], "EURUSD/M1/2026")
        self.assertEqual(len(group["rows"]), 2)
        self.assertIn("profit_factor", group["rows"][0])

    def test_invalid_store_version_fails_closed(self) -> None:
        self.workspace_file.write_text('{"version": 99, "strategies": []}')
        with self.assertRaises(workspace.WorkspaceStoreError):
            workspace.list_strategies()
        self.assertIn("99", self.workspace_file.read_text())


class WorkspaceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace_file = self.root / "workspace.json"
        self.env = patch.dict(
            os.environ,
            {"REX_WORKSPACE_FILE": str(self.workspace_file)},
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_live_route_functions(self) -> None:
        from server import main as api

        rows = api.workspace_strategies()
        self.assertEqual(len(rows), 3)
        detail = api.workspace_strategy(rows[0]["id"])
        self.assertIn("variations", detail)
        note = api.add_workspace_note(
            detail["id"], api.WorkspacePayload(body="API note")
        )
        self.assertEqual(note["body"], "API note")
        with self.assertRaises(Exception) as raised:
            api.workspace_strategy("missing")
        self.assertEqual(getattr(raised.exception, "status_code", 404), 404)


if __name__ == "__main__":
    unittest.main()
