"""Feature pack builders used by FeatureRepository."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from math import isfinite
from typing import TYPE_CHECKING

from core.features.config import FeatureConfig
from core.features.versioning import INDICATOR_IMPLEMENTATION_VERSIONS, INDICATOR_METHOD_IDS
from core.features.generators.range_expansion import RangeExpansionGenerator
from core.features.generators.returns import ReturnsGenerator
from core.features.generators.swings import SwingGenerator
from core.features.packs.base import (
    IndicatorPack,
    PricePack,
    SessionPack,
    StructurePack,
    VolatilityPack,
    ZonePack,
)
from core.features.types import (
    PACK_INDICATORS,
    PACK_PRICE,
    PACK_SESSION,
    PACK_STRUCTURE,
    PACK_VOLATILITY,
    PACK_ZONES,
)
from core.indicators.series import IndicatorSeries, series_metadata
from core.market import Instrument
from core.session_manager import SessionManager
from models.bar import Bar

if TYPE_CHECKING:
    from core.indicators.indicator_engine import IndicatorEngine
    from core.zones.engine import ZoneEngine


def build_price_pack(
    bars_by_timeframe: Mapping[str, Sequence[Bar]],
    instrument: Instrument,
    *,
    entry_timeframe: str,
) -> PricePack:
    returns = ReturnsGenerator().generate(
        bars_by_timeframe, instrument, entry_timeframe=entry_timeframe
    )
    recent_closes: dict[str, tuple[float, ...]] = {}
    for timeframe, bars in bars_by_timeframe.items():
        ordered = tuple(sorted(bars, key=lambda bar: bar.timestamp))
        recent_closes[timeframe] = tuple(bar.close for bar in ordered)
    return PricePack(
        pack_id=PACK_PRICE,
        returns=returns,
        recent_closes=recent_closes,
    )


def build_structure_pack(
    bars_by_timeframe: Mapping[str, Sequence[Bar]],
    instrument: Instrument,
    *,
    entry_timeframe: str,
    config: FeatureConfig,
    asof: datetime | None = None,
) -> StructurePack:
    swings = SwingGenerator(config.swing_detection).generate(
        bars_by_timeframe,
        instrument,
        entry_timeframe=entry_timeframe,
        asof=asof,
    )
    return StructurePack(pack_id=PACK_STRUCTURE, swings=swings)


def build_volatility_pack(
    bars_by_timeframe: Mapping[str, Sequence[Bar]],
    instrument: Instrument,
    *,
    entry_timeframe: str,
    config: FeatureConfig,
    indicator_engine: IndicatorEngine | None = None,
) -> VolatilityPack:
    range_expansion = RangeExpansionGenerator(config.range_expansion).generate(
        bars_by_timeframe, instrument, entry_timeframe=entry_timeframe
    )
    atr_last = _atr_last(
        bars_by_timeframe.get(entry_timeframe, ()),
        config.indicators.atr_period,
        indicator_engine,
    )
    return VolatilityPack(
        pack_id=PACK_VOLATILITY,
        range_expansion=range_expansion,
        atr_last=atr_last,
    )


def _indicator_series(
    series: object,
    bars: Sequence[Bar],
    *,
    indicator_id: str,
    timeframe: str,
    parameters: dict[str, object],
    series_window: int,
) -> IndicatorSeries:
    timestamps = tuple(bar.timestamp for bar in bars)
    all_values: list[float | None] = []
    for index in range(len(bars)):
        try:
            value = series.iloc[index]  # type: ignore[attr-defined]
        except Exception:
            all_values.append(None)
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            all_values.append(None)
            continue
        if numeric != numeric or not isfinite(numeric):
            all_values.append(None)
        else:
            all_values.append(numeric)
    start_index = max(0, len(all_values) - series_window)
    values = tuple(all_values[start_index:])
    timestamps = timestamps[start_index:]
    return series_metadata(
        indicator_id=indicator_id,
        method_id=INDICATOR_METHOD_IDS.get(indicator_id, f"{indicator_id}_v1"),
        timeframe=timeframe,
        timestamps=timestamps,
        parameters=parameters,
        implementation_version=INDICATOR_IMPLEMENTATION_VERSIONS.get(
            indicator_id, f"{indicator_id}_v1"
        ),
        values=values,
        start_index=start_index,
        source_bar_count=len(bars),
    )


def build_indicator_pack(
    bars_by_timeframe: Mapping[str, Sequence[Bar]],
    *,
    entry_timeframe: str,
    config: FeatureConfig,
    indicator_engine: IndicatorEngine | None = None,
) -> IndicatorPack:
    empty = IndicatorPack(
        pack_id=PACK_INDICATORS,
        ema_fast_last=None,
        ema_slow_last=None,
        atr_last=None,
        rsi_last=None,
        macd_last=None,
        macd_signal_last=None,
        macd_histogram_last=None,
        relative_volume_last=None,
    )
    try:
        engine = indicator_engine or _default_indicator_engine()
    except ImportError:
        return empty
    bars = list(bars_by_timeframe.get(entry_timeframe, ()))
    if not bars:
        return empty

    indicators = config.indicators
    timeframe = entry_timeframe
    engine.prepare(bars)

    sma = engine.sma(bars, length=indicators.sma_period)
    ema_fast = engine.ema(bars, length=indicators.ema_fast_period)
    ema_slow = engine.ema(bars, length=indicators.ema_slow_period)
    wma = engine.wma(bars, length=indicators.wma_period)
    hma = engine.hma(bars, length=indicators.hma_period)
    dema = engine.dema(bars, length=indicators.dema_period)
    tema = engine.tema(bars, length=indicators.tema_period)
    atr = engine.atr(bars, length=indicators.atr_period)
    rsi = engine.rsi(bars, length=indicators.rsi_period)
    macd_result = engine.macd(
        bars,
        fast=indicators.macd_fast_period,
        slow=indicators.macd_slow_period,
        signal=indicators.macd_signal_period,
    )
    bollinger = engine.bollinger_bands(
        bars, length=indicators.bollinger_period, std=indicators.bollinger_std
    )
    adx_result = engine.adx(bars, length=indicators.adx_period)
    relative_volume = engine.relative_volume(
        bars, length=indicators.relative_volume_period
    )

    series_map = {
        "sma": _indicator_series(
            sma, bars, indicator_id="sma", timeframe=timeframe,
            parameters={"length": indicators.sma_period}, series_window=indicators.series_window,
        ),
        "ema_fast": _indicator_series(
            ema_fast, bars, indicator_id="ema_fast", timeframe=timeframe,
            parameters={"length": indicators.ema_fast_period}, series_window=indicators.series_window,
        ),
        "ema_slow": _indicator_series(
            ema_slow, bars, indicator_id="ema_slow", timeframe=timeframe,
            parameters={"length": indicators.ema_slow_period}, series_window=indicators.series_window,
        ),
        "wma": _indicator_series(
            wma, bars, indicator_id="wma", timeframe=timeframe,
            parameters={"length": indicators.wma_period}, series_window=indicators.series_window,
        ),
        "hma": _indicator_series(
            hma, bars, indicator_id="hma", timeframe=timeframe,
            parameters={"length": indicators.hma_period}, series_window=indicators.series_window,
        ),
        "dema": _indicator_series(
            dema, bars, indicator_id="dema", timeframe=timeframe,
            parameters={"length": indicators.dema_period}, series_window=indicators.series_window,
        ),
        "tema": _indicator_series(
            tema, bars, indicator_id="tema", timeframe=timeframe,
            parameters={"length": indicators.tema_period}, series_window=indicators.series_window,
        ),
        "atr": _indicator_series(
            atr, bars, indicator_id="atr", timeframe=timeframe,
            parameters={"length": indicators.atr_period}, series_window=indicators.series_window,
        ),
        "rsi": _indicator_series(
            rsi, bars, indicator_id="rsi", timeframe=timeframe,
            parameters={"length": indicators.rsi_period}, series_window=indicators.series_window,
        ),
        "macd": _indicator_series(
            macd_result.macd, bars, indicator_id="macd", timeframe=timeframe,
            parameters={"fast": indicators.macd_fast_period, "slow": indicators.macd_slow_period, "signal": indicators.macd_signal_period}, series_window=indicators.series_window,
        ),
        "macd_signal": _indicator_series(
            macd_result.signal, bars, indicator_id="macd_signal", timeframe=timeframe,
            parameters={"fast": indicators.macd_fast_period, "slow": indicators.macd_slow_period, "signal": indicators.macd_signal_period}, series_window=indicators.series_window,
        ),
        "macd_histogram": _indicator_series(
            macd_result.histogram, bars, indicator_id="macd_histogram", timeframe=timeframe,
            parameters={"fast": indicators.macd_fast_period, "slow": indicators.macd_slow_period, "signal": indicators.macd_signal_period}, series_window=indicators.series_window,
        ),
        "bb_upper": _indicator_series(
            bollinger.upper, bars, indicator_id="bb_upper", timeframe=timeframe,
            parameters={"length": indicators.bollinger_period, "std": indicators.bollinger_std}, series_window=indicators.series_window,
        ),
        "bb_middle": _indicator_series(
            bollinger.middle, bars, indicator_id="bb_middle", timeframe=timeframe,
            parameters={"length": indicators.bollinger_period, "std": indicators.bollinger_std}, series_window=indicators.series_window,
        ),
        "bb_lower": _indicator_series(
            bollinger.lower, bars, indicator_id="bb_lower", timeframe=timeframe,
            parameters={"length": indicators.bollinger_period, "std": indicators.bollinger_std}, series_window=indicators.series_window,
        ),
        "adx": _indicator_series(
            adx_result.adx, bars, indicator_id="adx", timeframe=timeframe,
            parameters={"length": indicators.adx_period}, series_window=indicators.series_window,
        ),
        "plus_di": _indicator_series(
            adx_result.plus_di, bars, indicator_id="plus_di", timeframe=timeframe,
            parameters={"length": indicators.adx_period}, series_window=indicators.series_window,
        ),
        "minus_di": _indicator_series(
            adx_result.minus_di, bars, indicator_id="minus_di", timeframe=timeframe,
            parameters={"length": indicators.adx_period}, series_window=indicators.series_window,
        ),
        "relative_volume": _indicator_series(
            relative_volume, bars, indicator_id="relative_volume", timeframe=timeframe,
            parameters={"length": indicators.relative_volume_period}, series_window=indicators.series_window,
        ),
    }

    return IndicatorPack(
        pack_id=PACK_INDICATORS,
        ema_fast_last=_series_last(ema_fast),
        ema_slow_last=_series_last(ema_slow),
        atr_last=_series_last(atr),
        rsi_last=_series_last(rsi),
        macd_last=_series_last(macd_result.macd),
        macd_signal_last=_series_last(macd_result.signal),
        macd_histogram_last=_series_last(macd_result.histogram),
        relative_volume_last=_series_last(relative_volume),
        series=series_map,
    )


def build_zone_pack(
    instrument: Instrument,
    *,
    price: float | None,
    zone_engine: ZoneEngine | None,
) -> ZonePack:
    if zone_engine is None or price is None:
        return ZonePack(
            pack_id=PACK_ZONES,
            active_zones=(),
            nearest=None,
            inside_zone=False,
        )
    symbol = instrument.symbol
    return ZonePack(
        pack_id=PACK_ZONES,
        active_zones=zone_engine.active_zones(symbol, price),
        nearest=zone_engine.distance_to_nearest_zone(symbol, price),
        inside_zone=zone_engine.is_price_inside_zone(symbol, price),
    )


def build_session_pack(*, asof: datetime) -> SessionPack:
    info = SessionManager().get_current_session(asof)
    return SessionPack(
        pack_id=PACK_SESSION,
        session=info.session.value,
        overlap=info.overlap,
        high_liquidity=info.high_liquidity,
        active_sessions=tuple(session.value for session in info.active_sessions),
    )


def _default_indicator_engine() -> IndicatorEngine:
    from core.indicators.indicator_engine import IndicatorEngine
    from core.indicators.pandas_provider import PandasTAProvider

    return IndicatorEngine(PandasTAProvider())


def _atr_last(
    bars: Sequence[Bar],
    period: int,
    indicator_engine: IndicatorEngine | None,
) -> float | None:
    if not bars:
        return None
    try:
        engine = indicator_engine or _default_indicator_engine()
    except ImportError:
        return None
    return _series_last(engine.atr(list(bars), length=period))


def _series_last(series: object) -> float | None:
    try:
        if series is None or len(series) == 0:  # type: ignore[arg-type]
            return None
        value = series.iloc[-1]  # type: ignore[attr-defined]
        if value != value:  # NaN
            return None
        return float(value)
    except Exception:
        return None
