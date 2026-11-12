"""P2 API contract tests for zones, dashboard and experiment planning."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import main as api


class P2ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                "REX_ZONES_FILE": str(self.root / "zones.json"),
                "REX_WORKSPACE_FILE": str(self.root / "workspace.json"),
                "REX_RUNS_DIR": str(self.root / "runs"),
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_zone_crud_through_api(self) -> None:
        initial = api.zones(symbol="EURUSD")
        self.assertTrue(any(item["legacy"] for item in initial))
        created = api.create_zone(
            api.ZonePayload(
                dataset_id="EURUSD/M1/2026",
                source_timeframe="H1",
                zone_type="demand",
                low=1.10,
                high=1.11,
                effective_timestamp="2026-01-01T00:00:00Z",
                strength=6,
                notes="api",
                historical_import=True,
                import_source="api-test",
                import_operator="tester",
            )
        )
        self.assertEqual(created["version"], 1)
        updated = api.update_zone(
            created["id"], api.ZonePayload(high=1.12, notes="updated")
        )
        self.assertEqual(updated["version"], 2)
        archived = api.archive_zone(created["id"])
        self.assertEqual(archived["status"], "archived")

    def test_dashboard_and_planned_experiment(self) -> None:
        strategies = api.workspace_strategies()
        s008 = next(item for item in strategies if item["registry_strategy_id"] == "S008")
        detail = api.workspace_strategy(s008["id"])
        variation = detail["variations"][0]
        planned = api.plan_workspace_experiment(
            s008["id"],
            api.WorkspacePayload(
                variation_id=variation["id"],
                dataset_id="EURUSD/M1/2026",
                timeframe="M1",
                name="Planned API experiment",
                hypothesis="API planning",
                expected_outcome="A result.",
            ),
        )
        self.assertEqual(planned["experiments"][0]["status"], "Planned")
        dashboard = api.workspace_dashboard()
        self.assertGreaterEqual(dashboard["strategy_count"], 3)
        self.assertGreaterEqual(dashboard["experiment_count"], 1)
        self.assertIn("Planned", dashboard["experiment_status_counts"])
