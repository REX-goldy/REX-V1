"""Tests for strategy discovery and implemented strategy metadata."""

import unittest

from strategies.registry import build_default_registry


class StrategyRegistryTests(unittest.TestCase):
    def test_discovers_implemented_strategies(self) -> None:
        registry = build_default_registry()
        self.assertEqual(
            set(registry.ids()),
            {"CORE_ZONE_BREAKOUT", "S002", "S008"},
        )

    def test_every_registered_strategy_has_metadata(self) -> None:
        for strategy_id, strategy_class in build_default_registry().items():
            self.assertTrue(strategy_id)
            self.assertTrue(strategy_class.strategy_name)
            self.assertTrue(strategy_class.description)


if __name__ == "__main__":
    unittest.main()
