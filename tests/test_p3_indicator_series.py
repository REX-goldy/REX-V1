"""P3.1 indicator-series, provenance and causality tests."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from core.features import (
    FeatureRepository,
    PACK_INDICATORS,
    default_feature_config,
)
from core.features.packs.base import IndicatorPack
from core.features.versioning import (
    INDICATOR_IMPLEMENTATION_VERSIONS,
    feature_config_hash,
    feature_schema_hash,
)
from core.indicators import IndicatorEngine, PandasTAProvider
from models.bar import Bar


def _bars(count: int = 80, *, symbol: str = "EURUSD") -> list[Bar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 1.1000
    out: list[Bar] = []
    for index in range(count):
        close = price + 0.0002 * (index % 9 - 4)
        out.append(
            Bar(
                symbol=symbol,
                timestamp=start + timedelta(minutes=index),
                open=price,
                high=max(price, close) + 0.0004,
                low=min(price, close) - 0.0004,
                close=close,
            )
        )
        price = close
    return out


class IndicatorSeriesTests(unittest.TestCase):
    def test_series_are_timestamp_aligned_and_match_scalar_last(self) -> None:
        bars = _bars()
        context = FeatureRepository().materialize(
            "EURUSD", {"M1": bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        self.assertTrue(pack.series)
        for series in pack.series.values():
            self.assertEqual(len(series.timestamps), len(bars))
            self.assertEqual(len(series.values), len(bars))
            self.assertEqual(series.timestamps, tuple(bar.timestamp for bar in bars))
        self.assertAlmostEqual(pack.ema_fast_last or 0.0, pack.series["ema_fast"].values[-1] or 0.0)
        self.assertAlmostEqual(pack.rsi_last or 0.0, pack.series["rsi"].values[-1] or 0.0)
        self.assertEqual(pack.series["relative_volume"].values[-1], None)
        self.assertGreater(pack.series["sma"].warmup_bars, 0)

    def test_custom_parameters_change_hash_and_metadata(self) -> None:
        config = default_feature_config()
        changed = replace(
            config,
            indicators=replace(config.indicators, rsi_period=9, sma_period=10),
        )
        self.assertNotEqual(feature_config_hash(config), feature_config_hash(changed))
        context = FeatureRepository(config=changed).materialize(
            "EURUSD", {"M1": _bars()}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        self.assertEqual(pack.series["rsi"].parameters["length"], 9)
        self.assertEqual(pack.series["sma"].parameters["length"], 10)
        self.assertEqual(
            context.provenance.config_hash, feature_config_hash(changed)
        )

    def test_asof_and_future_prefix_invariance(self) -> None:
        bars = _bars()
        cutoff = bars[39].timestamp
        repo = FeatureRepository()
        prefix = repo.materialize(
            "EURUSD",
            {"M1": bars[:40]},
            entry_timeframe="M1",
            asof=cutoff,
            pack_ids=(PACK_INDICATORS,),
        )
        full = repo.materialize(
            "EURUSD",
            {"M1": bars},
            entry_timeframe="M1",
            asof=cutoff,
            pack_ids=(PACK_INDICATORS,),
        )
        prefix_pack = prefix.require_pack(PACK_INDICATORS, IndicatorPack)
        full_pack = full.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(prefix_pack, IndicatorPack) and isinstance(full_pack, IndicatorPack)
        for key in ("sma", "ema_fast", "ema_slow", "rsi", "atr", "macd"):
            self.assertEqual(prefix_pack.series[key].values, full_pack.series[key].values)
        self.assertEqual(full.asof, cutoff)
        self.assertTrue(all(bar.timestamp <= cutoff for bar in full.bars_by_timeframe["M1"]))

    def test_series_window_is_bounded_and_source_aligned(self) -> None:
        config = default_feature_config()
        changed = replace(
            config,
            indicators=replace(config.indicators, series_window=10),
        )
        context = FeatureRepository(config=changed).materialize(
            "EURUSD", {"M1": _bars()}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        series = pack.series["ema_fast"]
        self.assertEqual(len(series.values), 10)
        self.assertEqual(series.source_bar_count, 80)
        self.assertEqual(series.start_index, 70)
        self.assertEqual(series.timestamps[-1], context.bars_by_timeframe["M1"][-1].timestamp)
        self.assertEqual(context.provenance.indicator_parameters["ema_fast"]["length"], 20)

    def test_version_and_method_changes_change_schema_hash(self) -> None:
        config = default_feature_config()
        base = feature_schema_hash(
            pack_ids=(PACK_INDICATORS,), config=config, timeframe="M1"
        )
        changed_versions = dict(INDICATOR_IMPLEMENTATION_VERSIONS)
        changed_versions["rsi"] = "rsi_v2"
        changed = feature_schema_hash(
            pack_ids=(PACK_INDICATORS,),
            config=config,
            timeframe="M1",
            indicator_versions=changed_versions,
        )
        self.assertNotEqual(base, changed)
        self.assertEqual(
            base,
            feature_schema_hash(
                pack_ids=(PACK_INDICATORS,), config=config, timeframe="M1"
            ),
        )
        method_changed = feature_schema_hash(
            pack_ids=(PACK_INDICATORS,),
            config=config,
            timeframe="M1",
            method_ids={"trend": "market_structure_v2"},
        )
        self.assertNotEqual(base, method_changed)

    def test_scalar_provider_outputs_unchanged(self) -> None:
        bars = _bars()
        engine = IndicatorEngine(PandasTAProvider())
        context = FeatureRepository(indicator_engine=engine).materialize(
            "EURUSD", {"M1": bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        self.assertAlmostEqual(pack.ema_fast_last or 0.0, float(engine.ema(bars, length=20).iloc[-1]))
        self.assertAlmostEqual(pack.rsi_last or 0.0, float(engine.rsi(bars, length=14).iloc[-1]))


if __name__ == "__main__":
    unittest.main()
