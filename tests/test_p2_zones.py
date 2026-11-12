"""P2 manual zone store, versioning and temporal availability tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from server.zone_store import (
    ZoneNotFound,
    ZoneStoreError,
    archive_zone,
    build_zone_books,
    create_zone,
    list_zones,
    update_zone,
)


class ZoneStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "zones.json"
        self.env = patch.dict(os.environ, {"REX_ZONES_FILE": str(self.path)}, clear=False)
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def _create(self, **overrides):
        payload = {
            "dataset_id": "EURUSD/M1/2026",
            "source_timeframe": "H1",
            "zone_type": "demand",
            "low": 1.10,
            "high": 1.11,
            "start_timestamp": "2026-01-01T00:00:00Z",
            "effective_timestamp": "2026-01-01T00:00:00Z",
            "strength": 7,
            "notes": "test",
            "historical_import": True,
            "import_source": "audit-fixture",
            "import_operator": "tester",
        }
        payload.update(overrides)
        return create_zone(payload)

    def test_create_list_update_and_versioning(self) -> None:
        created = self._create()
        self.assertEqual(created["version"], 1)
        self.assertEqual(created["status"], "active")
        self.assertIn(created["id"], [item["id"] for item in list_zones()])
        updated = update_zone(created["id"], {"high": 1.12, "notes": "updated"})
        self.assertEqual(updated["version"], 2)
        self.assertEqual(len(updated["versions"]), 1)
        self.assertEqual(updated["versions"][0]["high"], 1.11)
        with self.assertRaises(ZoneNotFound):
            update_zone("missing", {"high": 1.2})

    def test_created_at_cannot_be_supplied(self) -> None:
        with self.assertRaises(ZoneStoreError):
            create_zone({
                "dataset_id": "EURUSD/M1/2026",
                "source_timeframe": "H1",
                "zone_type": "demand",
                "low": 1.10,
                "high": 1.11,
                "effective_timestamp": "2027-01-01T00:00:00Z",
                "created_at": "2020-01-01T00:00:00Z",
            })

    def test_backdated_manual_zone_is_rejected(self) -> None:
        with self.assertRaises(ZoneStoreError):
            create_zone({
                "dataset_id": "EURUSD/M1/2026",
                "source_timeframe": "H1",
                "zone_type": "demand",
                "low": 1.10,
                "high": 1.11,
                "effective_timestamp": "2026-01-01T00:00:00Z",
            })

    def test_archive_preserves_versions(self) -> None:
        created = self._create()
        archived = archive_zone(created["id"])
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(archived["version"], 2)
        self.assertEqual(len(archived["versions"]), 1)
        with self.assertRaises(ZoneStoreError):
            create_zone({"dataset_id": "EURUSD/M1/2026", "source_timeframe": "H1", "zone_type": "demand", "low": 1.2, "high": 1.1, "effective_timestamp": "2026-01-01T00:00:00Z"})

    def test_temporal_availability_prevents_future_and_invalidated_zones(self) -> None:
        self._create(low=1.10, high=1.11, effective_timestamp="2026-01-01T00:00:00Z")
        self._create(low=1.2060, high=1.2070, effective_timestamp="2026-06-01T00:00:00Z")
        self._create(low=1.30, high=1.31, effective_timestamp="2026-01-01T00:00:00Z", invalidation_timestamp="2026-02-01T00:00:00Z")
        books = build_zone_books(start=datetime(2026, 3, 1), end=datetime(2026, 3, 2))
        zones = books["EURUSD"].zones
        lows = [zone.low for zone in zones if zone.low < 1.5]
        self.assertIn(1.10, lows)
        self.assertNotIn(1.2060, lows)
        self.assertNotIn(1.30, lows)
        # Legacy config zones remain available without timestamps.
        self.assertTrue(any(zone.low == 1.14 for zone in zones))

    def test_selected_zone_ids_are_isolated(self) -> None:
        first = self._create(low=1.10, high=1.11)
        self._create(low=1.20, high=1.21)
        books = build_zone_books(
            start=datetime(2026, 3, 1),
            end=datetime(2026, 3, 2),
            zone_ids=[first["id"]],
        )
        zones = [zone for zone in books["EURUSD"].zones if zone.low < 1.5]
        self.assertEqual(len(zones), 1)
        self.assertAlmostEqual(zones[0].low, 1.10)
