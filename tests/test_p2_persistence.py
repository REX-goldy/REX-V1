"""P2 cross-process locking and JSON backup/recovery tests."""

from __future__ import annotations

import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server import strategy_workspace as workspace
from server import zone_store


def _update_zone(zone_id: str, value: float) -> None:
    zone_store.update_zone(zone_id, {"low": 1.10 + value, "high": 1.11 + value})


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.env = patch.dict(
            os.environ,
            {
                "REX_WORKSPACE_FILE": str(self.root / "workspace.json"),
                "REX_ZONES_FILE": str(self.root / "zones.json"),
                "REX_RUNS_DIR": str(self.root / "runs"),
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_zone_backup_recovers_corrupt_file(self) -> None:
        zone = zone_store.create_zone(
            {
                "dataset_id": "EURUSD/M1/2026",
                "source_timeframe": "H1",
                "zone_type": "demand",
                "low": 1.10,
                "high": 1.11,
                "effective_timestamp": "2026-01-01T00:00:00Z",
                "historical_import": True,
                "import_source": "test",
                "import_operator": "tester",
            }
        )
        zone_store.update_zone(zone["id"], {"notes": "backup-state"})
        path = self.root / "zones.json"
        path.write_text("{broken", encoding="utf-8")
        recovered = zone_store.list_zones()
        self.assertTrue(any(item["id"] == zone["id"] for item in recovered))
        self.assertTrue(any(path.name in str(item) for item in path.parent.glob("zones.json.corrupt-*")))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_workspace_backup_recovers_corrupt_file(self) -> None:
        workspace.list_strategies()  # seed
        created = workspace.create_strategy(
            {"title": "Persistence probe", "short_description": "backup"}
        )
        path = self.root / "workspace.json"
        path.write_text("{broken", encoding="utf-8")
        rows = workspace.list_strategies()
        self.assertGreaterEqual(len(rows), 3)
        self.assertTrue(any(item["id"] == created["id"] for item in rows))
        self.assertTrue(any(path.name in str(item) for item in path.parent.glob("workspace.json.corrupt-*")))

    def test_two_processes_do_not_lose_zone_updates(self) -> None:
        zone = zone_store.create_zone(
            {
                "dataset_id": "EURUSD/M1/2026",
                "source_timeframe": "H1",
                "zone_type": "demand",
                "low": 1.10,
                "high": 1.11,
                "effective_timestamp": "2026-01-01T00:00:00Z",
                "historical_import": True,
                "import_source": "test",
                "import_operator": "tester",
            }
        )
        ctx = multiprocessing.get_context("fork")
        processes = [ctx.Process(target=_update_zone, args=(zone["id"], i)) for i in (1, 2)]
        [process.start() for process in processes]
        [process.join(timeout=10) for process in processes]
        current = zone_store.get_zone(zone["id"])
        self.assertEqual(current["version"], 3)
        self.assertEqual(len(current["versions"]), 2)
