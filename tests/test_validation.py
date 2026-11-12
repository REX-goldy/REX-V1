"""Tests for zone configuration validation."""

import unittest
from core.validation import (
    DuplicateZoneIdError,
    InvalidZoneError,
    OverlappingZoneError,
    validate_zone_entries,
)


def valid_zone(zone_id: int, low: float, high: float) -> dict[str, object]:
    return {
        "id": zone_id,
        "name": f"zone_{zone_id}",
        "low": low,
        "high": high,
        "timeframe": "daily",
        "strength": 5,
    }


class ValidationTests(unittest.TestCase):
    def test_duplicate_zone_ids(self) -> None:
        with self.assertRaises(DuplicateZoneIdError):
            validate_zone_entries(
                "EURUSD",
                [valid_zone(1, 1.1, 1.2), valid_zone(1, 1.3, 1.4)],
            )

    def test_invalid_and_overlapping_zones(self) -> None:
        with self.assertRaises(InvalidZoneError):
            validate_zone_entries("EURUSD", [valid_zone(1, 1.2, 1.1)])
        with self.assertRaises(OverlappingZoneError):
            validate_zone_entries(
                "EURUSD",
                [valid_zone(1, 1.1, 1.2), valid_zone(2, 1.19, 1.3)],
            )



if __name__ == "__main__":
    unittest.main()

