"""Reusable indicator subsystem (Engine + Provider; library-agnostic API)."""

from core.indicators.indicator_engine import IndicatorEngine
from core.indicators.indicator_provider import IndicatorProvider
from core.indicators.models import ADXResult, BollingerBands, MACDResult
from core.indicators.series import IndicatorSeries, series_metadata
from core.indicators.pandas_provider import PandasTAProvider

__all__ = [
    "ADXResult",
    "BollingerBands",
    "IndicatorEngine",
    "IndicatorProvider",
    "IndicatorSeries",
    "MACDResult",
    "PandasTAProvider",
    "series_metadata",
]
