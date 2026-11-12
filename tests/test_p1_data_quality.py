"""P1 dataset-quality report tests against the real stored partitions."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from historical.quality import build_dataset_quality_report

ROOT = Path(__file__).resolve().parents[1]


class DatasetQualityTests(unittest.TestCase):
    def _hash(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_eurusd_known_gaps_are_reported_without_mutation(self) -> None:
        path = ROOT / "data" / "historical" / "EURUSD" / "M1" / "2026.csv"
        before = self._hash(path)
        report = build_dataset_quality_report("EURUSD/M1/2026")
        after = self._hash(path)
        self.assertEqual(before, after)
        self.assertEqual(report["counts"]["bar_count"], 184_963)
        self.assertEqual(report["counts"]["duplicate_timestamp_count"], 0)
        self.assertEqual(report["counts"]["invalid_bar_count"], 0)
        self.assertEqual(report["counts"]["unexpected_gap_count"], 10)
        self.assertEqual(report["counts"]["missing_open_minutes"], 17)
        self.assertEqual(report["quality"]["status"], "warning")
        self.assertTrue(any("unexpected" in item for item in report["quality"]["warnings"]))
        self.assertEqual(report["derived"]["M5"]["status"], "ok")
        self.assertGreater(report["derived"]["M5"]["skipped_incomplete_buckets"], 0)

    def test_clean_partition_has_no_unexpected_gaps(self) -> None:
        report = build_dataset_quality_report("GBPUSD/M1/2026")
        self.assertEqual(report["counts"]["bar_count"], 93_600)
        self.assertEqual(report["counts"]["unexpected_gap_count"], 0)
        self.assertEqual(report["counts"]["missing_open_minutes"], 0)
        self.assertEqual(report["counts"]["bars_in_closure"], 0)
        self.assertEqual(report["quality"]["status"], "ok")

    def test_missing_dataset_is_explicit(self) -> None:
        from historical.quality import DatasetQualityError

        with self.assertRaises(DatasetQualityError):
            build_dataset_quality_report("NOPE/M1/2026")
