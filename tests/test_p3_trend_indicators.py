"""P3.1 Stage 2A trend-family numerical, causality and provenance tests.

The reference functions below are deliberately independent of the production
provider: they are small Python EMA/WMA loops written directly from the public
formula definitions, not calls into pandas-ta-classic or IndicatorEngine.
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.features import (
    FeatureRepository,
    PACK_INDICATORS,
    default_feature_config,
    load_feature_config,
)
from core.features.packs.base import IndicatorPack
from core.features.versioning import (
    INDICATOR_IMPLEMENTATION_VERSIONS,
    INDICATOR_METHOD_IDS,
    feature_config_hash,
    feature_schema_hash,
)
from core.indicators import IndicatorEngine, PandasTAProvider
from models.bar import Bar


def _bars(count: int = 120, *, constant: float | None = None) -> list[Bar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = constant if constant is not None else 1.1000
    out: list[Bar] = []
    for index in range(count):
        if constant is None:
            close = price + 0.00017 * ((index * 7) % 13 - 6)
        else:
            close = constant
        out.append(
            Bar(
                symbol="EURUSD",
                timestamp=start + timedelta(minutes=index),
                open=price,
                high=max(price, close) + 0.0002,
                low=min(price, close) - 0.0002,
                close=close,
            )
        )
        price = close
    return out


def _sma_reference(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    for index in range(length - 1, len(values)):
        out[index] = sum(values[index - length + 1 : index + 1]) / length
    return out


def _wma_reference(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    denominator = length * (length + 1) / 2.0
    for index in range(length - 1, len(values)):
        window = values[index - length + 1 : index + 1]
        out[index] = sum((weight + 1) * value for weight, value in enumerate(window)) / denominator
    return out


def _hma_reference(values: list[float], length: int) -> list[float | None]:
    half = int(length / 2)
    root = int(math.sqrt(length))
    fast = _wma_reference(values, half)
    slow = _wma_reference(values, length)
    combined = [
        None if fast_value is None or slow_value is None else 2 * fast_value - slow_value
        for fast_value, slow_value in zip(fast, slow)
    ]
    # WMA over a series that begins with None.
    out: list[float | None] = [None] * len(values)
    denominator = root * (root + 1) / 2.0
    for index in range(root - 1, len(values)):
        window = combined[index - root + 1 : index + 1]
        if any(value is None for value in window):
            continue
        out[index] = sum(
            (weight + 1) * float(value)
            for weight, value in enumerate(window)
        ) / denominator
    return out


def _ema_reference(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < length:
        return out
    out[length - 1] = sum(values[:length]) / length
    alpha = 2.0 / (length + 1.0)
    for index in range(length, len(values)):
        previous = out[index - 1]
        if previous is not None:
            out[index] = alpha * values[index] + (1.0 - alpha) * previous
    return out


def _ema_chain_reference(
    values: list[float], length: int, depth: int
) -> list[list[float | None]]:
    stages: list[list[float | None]] = []
    feed = values
    start = 0
    for _ in range(depth):
        stage = _ema_reference(feed, length)
        padded: list[float | None] = [None] * len(values)
        padded[start : start + len(stage)] = stage
        stages.append(padded)
        first = next((i for i, value in enumerate(stage) if value is not None), None)
        if first is None:
            break
        start += first
        feed = stage[first:]
    return stages


def _dema_reference(values: list[float], length: int) -> list[float | None]:
    first, second = _ema_chain_reference(values, length, 2)
    return [
        None if a is None or b is None else 2 * a - b
        for a, b in zip(first, second)
    ]


def _tema_reference(values: list[float], length: int) -> list[float | None]:
    first, second, third = _ema_chain_reference(values, length, 3)
    return [
        None if a is None or b is None or c is None else 3 * (a - b) + c
        for a, b, c in zip(first, second, third)
    ]


def _values(series: object) -> list[float | None]:
    out: list[float | None] = []
    for value in series:  # type: ignore[union-attr]
        numeric = float(value)
        out.append(None if math.isnan(numeric) else numeric)
    return out


class TrendNumericalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bars = _bars()
        self.closes = [bar.close for bar in self.bars]
        self.engine = IndicatorEngine(PandasTAProvider())

    def _assert_reference(
        self,
        actual: list[float | None],
        expected: list[float | None],
        label: str,
    ) -> None:
        self.assertEqual(len(actual), len(expected), label)
        for index, (got, want) in enumerate(zip(actual, expected)):
            if want is None:
                self.assertIsNone(got, f"{label}[{index}] should be unavailable")
            else:
                self.assertIsNotNone(got, f"{label}[{index}] unexpectedly unavailable")
                self.assertAlmostEqual(got, want, places=11, msg=f"{label}[{index}]")

    def test_wma_matches_independent_reference(self) -> None:
        actual = _values(self.engine.wma(self.bars, length=20))
        self._assert_reference(actual, _wma_reference(self.closes, 20), "WMA")

    def test_hma_matches_independent_reference(self) -> None:
        actual = _values(self.engine.hma(self.bars, length=20))
        self._assert_reference(actual, _hma_reference(self.closes, 20), "HMA")

    def test_dema_matches_independent_reference(self) -> None:
        actual = _values(self.engine.dema(self.bars, length=20))
        self._assert_reference(actual, _dema_reference(self.closes, 20), "DEMA")

    def test_tema_matches_independent_reference(self) -> None:
        actual = _values(self.engine.tema(self.bars, length=20))
        self._assert_reference(actual, _tema_reference(self.closes, 20), "TEMA")

    def test_custom_parameters_match_reference_and_metadata(self) -> None:
        config = default_feature_config()
        changed = replace(
            config,
            indicators=replace(
                config.indicators,
                wma_period=7,
                hma_period=9,
                dema_period=8,
                tema_period=6,
            ),
        )
        engine = IndicatorEngine(PandasTAProvider())
        context = FeatureRepository(config=changed, indicator_engine=engine).materialize(
            "EURUSD", {"M1": self.bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)

        expected = {
            "wma": _wma_reference(self.closes, 7),
            "hma": _hma_reference(self.closes, 9),
            "dema": _dema_reference(self.closes, 8),
            "tema": _tema_reference(self.closes, 6),
        }
        periods = {"wma": 7, "hma": 9, "dema": 8, "tema": 6}
        for indicator_id, reference in expected.items():
            series = pack.series[indicator_id]
            self._assert_reference(
                list(series.values), reference[series.start_index :], indicator_id
            )
            self.assertEqual(series.parameters["length"], periods[indicator_id])
            self.assertEqual(
                series.method_id, INDICATOR_METHOD_IDS[indicator_id]
            )
            self.assertEqual(
                series.implementation_version,
                INDICATOR_IMPLEMENTATION_VERSIONS[indicator_id],
            )

        self.assertNotEqual(feature_config_hash(config), feature_config_hash(changed))
        self.assertEqual(context.provenance.config_hash, feature_config_hash(changed))
        self.assertNotEqual(
            feature_schema_hash(
                pack_ids=(PACK_INDICATORS,), config=config, timeframe="M1"
            ),
            feature_schema_hash(
                pack_ids=(PACK_INDICATORS,), config=changed, timeframe="M1"
            ),
        )


class TrendWarmupAndEdgeTests(unittest.TestCase):
    def test_warmup_is_explicit_and_deterministic(self) -> None:
        bars = _bars()
        context = FeatureRepository().materialize(
            "EURUSD", {"M1": bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        self.assertEqual(pack.series["wma"].warmup_bars, 19)
        self.assertEqual(pack.series["hma"].warmup_bars, 22)
        self.assertEqual(pack.series["dema"].warmup_bars, 38)
        self.assertEqual(pack.series["tema"].warmup_bars, 57)
        for indicator_id in ("wma", "hma", "dema", "tema"):
            values = pack.series[indicator_id].values
            warmup = pack.series[indicator_id].warmup_bars
            self.assertTrue(all(value is None for value in values[:warmup]))
            self.assertIsNotNone(values[warmup])

    def test_insufficient_history_returns_unavailable_for_all_series(self) -> None:
        bars = _bars(10)
        engine = IndicatorEngine(PandasTAProvider())
        context = FeatureRepository(indicator_engine=engine).materialize(
            "EURUSD", {"M1": bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        for indicator_id in ("wma", "hma", "dema", "tema"):
            series = pack.series[indicator_id]
            self.assertEqual(series.warmup_bars, len(bars))
            self.assertTrue(all(value is None for value in series.values))

    def test_constant_price_is_safe_and_has_no_fabricated_zero(self) -> None:
        bars = _bars(100, constant=1.1)
        context = FeatureRepository().materialize(
            "EURUSD", {"M1": bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        for indicator_id in ("wma", "hma", "dema", "tema"):
            series = pack.series[indicator_id]
            for value in series.values[series.warmup_bars :]:
                self.assertIsNotNone(value)
                self.assertAlmostEqual(value, 1.1, places=12)

    def test_invalid_hma_period_is_rejected(self) -> None:
        engine = IndicatorEngine(PandasTAProvider())
        with self.assertRaisesRegex(ValueError, "hma length"):
            engine.hma(_bars(30), length=1)

    def test_insufficient_provider_history_does_not_raise(self) -> None:
        engine = IndicatorEngine(PandasTAProvider())
        bars = _bars(8)
        for indicator_id in ("wma", "hma", "dema", "tema"):
            values = _values(getattr(engine, indicator_id)(bars, length=20))
            self.assertTrue(all(value is None for value in values))


class TrendCausalityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bars = _bars(160)
        self.repo = FeatureRepository()
        self.cutoff = self.bars[119].timestamp

    def _context(self, bars: list[Bar]):
        return self.repo.materialize(
            "EURUSD",
            {"M1": bars},
            entry_timeframe="M1",
            asof=self.cutoff,
            pack_ids=(PACK_INDICATORS,),
        )

    def test_timestamp_alignment_with_canonical_bars(self) -> None:
        context = self._context(self.bars)
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        expected = tuple(
            bar.timestamp
            for bar in context.bars_by_timeframe["M1"]
        )
        for indicator_id in ("wma", "hma", "dema", "tema"):
            self.assertEqual(pack.series[indicator_id].timestamps, expected)

    def test_as_of_excludes_future_bars_and_future_changes(self) -> None:
        base = self._context(self.bars)
        future_changed = list(self.bars)
        for index in range(120, len(future_changed)):
            bar = future_changed[index]
            future_changed[index] = replace(
                bar,
                open=bar.open + 10.0,
                high=bar.high + 10.0,
                low=bar.low + 10.0,
                close=bar.close + 10.0,
            )
        changed = self._context(future_changed)
        base_pack = base.require_pack(PACK_INDICATORS, IndicatorPack)
        changed_pack = changed.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(base_pack, IndicatorPack) and isinstance(changed_pack, IndicatorPack)
        self.assertTrue(
            all(bar.timestamp <= self.cutoff for bar in changed.bars_by_timeframe["M1"])
        )
        for indicator_id in ("wma", "hma", "dema", "tema"):
            self.assertEqual(
                base_pack.series[indicator_id].values,
                changed_pack.series[indicator_id].values,
            )
            self.assertEqual(
                base_pack.series[indicator_id].timestamps,
                changed_pack.series[indicator_id].timestamps,
            )

    def test_prefix_invariance_at_provider_and_repository_levels(self) -> None:
        prefix_bars = self.bars[:120]
        prefix = self.repo.materialize(
            "EURUSD", {"M1": prefix_bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        full = self._context(self.bars)
        prefix_pack = prefix.require_pack(PACK_INDICATORS, IndicatorPack)
        full_pack = full.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(prefix_pack, IndicatorPack) and isinstance(full_pack, IndicatorPack)
        closes = [bar.close for bar in self.bars]
        for indicator_id in ("wma", "hma", "dema", "tema"):
            self.assertEqual(
                prefix_pack.series[indicator_id].values,
                full_pack.series[indicator_id].values,
            )

        engine = IndicatorEngine(PandasTAProvider())
        for indicator_id, reference in (
            ("wma", _wma_reference(closes, 20)),
            ("hma", _hma_reference(closes, 20)),
            ("dema", _dema_reference(closes, 20)),
            ("tema", _tema_reference(closes, 20)),
        ):
            actual = _values(getattr(engine, indicator_id)(prefix_bars, length=20))
            for index, (got, want) in enumerate(zip(actual, reference[:120])):
                if want is None:
                    self.assertIsNone(got, f"{indicator_id}[{index}]")
                else:
                    self.assertIsNotNone(got, f"{indicator_id}[{index}]")
                    self.assertAlmostEqual(got, want, places=11)


class TrendProvenanceAndRegressionTests(unittest.TestCase):
    def test_indicator_versions_and_parameters_are_recorded(self) -> None:
        context = FeatureRepository().materialize(
            "EURUSD", {"M1": _bars()}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        assert context.provenance is not None
        for indicator_id in ("wma", "hma", "dema", "tema"):
            self.assertEqual(
                context.provenance.indicator_versions[indicator_id],
                INDICATOR_IMPLEMENTATION_VERSIONS[indicator_id],
            )
            self.assertEqual(
                context.provenance.indicator_parameters[indicator_id]["length"], 20
            )
        base = feature_schema_hash(
            pack_ids=(PACK_INDICATORS,),
            config=default_feature_config(),
            timeframe="M1",
        )
        changed_versions = dict(INDICATOR_IMPLEMENTATION_VERSIONS)
        changed_versions["wma"] = "wma_v2"
        self.assertNotEqual(
            base,
            feature_schema_hash(
                pack_ids=(PACK_INDICATORS,),
                config=default_feature_config(),
                timeframe="M1",
                indicator_versions=changed_versions,
            ),
        )

    def test_json_config_loads_and_validates_trend_periods(self) -> None:
        source = Path("config/market_structure.json")
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["indicators"].update(
            {
                "wma_period": 7,
                "hma_period": 9,
                "dema_period": 8,
                "tema_period": 6,
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feature.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_feature_config(path)
        self.assertEqual(config.indicators.wma_period, 7)
        self.assertEqual(config.indicators.hma_period, 9)
        self.assertEqual(config.indicators.dema_period, 8)
        self.assertEqual(config.indicators.tema_period, 6)

        payload["indicators"]["hma_period"] = 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feature.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "HMA period"):
                load_feature_config(path)

    def test_hash_is_deterministic_for_same_configuration(self) -> None:
        config = default_feature_config()
        first = feature_schema_hash(
            pack_ids=(PACK_INDICATORS,), config=config, timeframe="M1"
        )
        second = feature_schema_hash(
            pack_ids=(PACK_INDICATORS,), config=config, timeframe="M1"
        )
        self.assertEqual(first, second)

    def test_existing_sma_and_ema_outputs_are_unchanged(self) -> None:
        bars = _bars()
        closes = [bar.close for bar in bars]
        engine = IndicatorEngine(PandasTAProvider())
        sma = _values(engine.sma(bars, length=20))
        ema = _values(engine.ema(bars, length=20))
        for indicator_id, actual, reference in (
            ("sma", sma, _sma_reference(closes, 20)),
            ("ema", ema, _ema_reference(closes, 20)),
        ):
            for index, (got, want) in enumerate(zip(actual, reference)):
                if want is None:
                    self.assertIsNone(got, f"{indicator_id}[{index}]")
                else:
                    self.assertAlmostEqual(got, want, places=11, msg=f"{indicator_id}[{index}]")

        context = FeatureRepository(indicator_engine=engine).materialize(
            "EURUSD", {"M1": bars}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
        )
        pack = context.require_pack(PACK_INDICATORS, IndicatorPack)
        assert isinstance(pack, IndicatorPack)
        self.assertAlmostEqual(pack.ema_fast_last or 0.0, ema[-1] or 0.0)
        self.assertEqual(pack.series["sma"].values[-1], sma[-1])

    def test_duplicate_timestamps_are_still_rejected(self) -> None:
        bars = _bars(30)
        duplicate = list(bars)
        duplicate[1] = replace(duplicate[1], timestamp=duplicate[0].timestamp)
        with self.assertRaisesRegex(ValueError, "Duplicate timestamps"):
            FeatureRepository().materialize(
                "EURUSD", {"M1": duplicate}, entry_timeframe="M1", pack_ids=(PACK_INDICATORS,)
            )


if __name__ == "__main__":
    unittest.main()
