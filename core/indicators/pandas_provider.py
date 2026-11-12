"""Pandas-ta-classic backed IndicatorProvider.

This is the only module in REX allowed to import the third-party TA library.
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

# pandas-ta-classic (PyPI) exposes the module ``pandas_ta_classic``.
# The unmaintained ``pandas-ta`` package used ``pandas_ta``; do not use it.
import pandas_ta_classic as ta

from core.indicators.models import ADXResult, BollingerBands, MACDResult
from models.bar import Bar


class PandasTAProvider:
    """Indicator calculations via pandas-ta-classic."""

    def __init__(self) -> None:
        self._prepared_bars: object | None = None
        self._prepared_frame: pd.DataFrame | None = None

    def prepare(self, bars: Sequence[Bar]) -> None:
        """Build once per materialization for reuse by subsequent calls."""
        if not bars:
            raise ValueError("bars must be a non-empty sequence")
        self._prepared_bars = bars
        self._prepared_frame = self._build_ohlc(bars)

    def sma(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        close = self._close(bars, length)
        return self._series_or_nan(ta.sma(close, length=length), close.index, "SMA")

    def ema(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        close = self._close(bars, length)
        return self._series_or_nan(ta.ema(close, length=length), close.index, "EMA")

    def wma(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        """Linearly weighted moving average (most recent value has largest weight)."""
        close = self._close(bars, length)
        return self._series_or_nan(
            ta.wma(close, length=length, asc=True), close.index, "WMA"
        )

    def hma(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        """Hull moving average: WMA(2*WMA(n/2) - WMA(n), sqrt(n))."""
        self._validate_length(length)
        if length < 2:
            raise ValueError(f"hma length must be >= 2, got {length}")
        close = self._close(bars, length)
        return self._series_or_nan(ta.hma(close, length=length), close.index, "HMA")

    def dema(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        """Double exponential moving average: 2*EMA(close) - EMA(EMA(close))."""
        close = self._close(bars, length)
        return self._series_or_nan(ta.dema(close, length=length), close.index, "DEMA")

    def tema(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        """Triple exponential moving average: 3*(EMA1 - EMA2) + EMA3."""
        close = self._close(bars, length)
        return self._series_or_nan(ta.tema(close, length=length), close.index, "TEMA")

    def rsi(self, bars: Sequence[Bar], length: int = 14) -> pd.Series:
        close = self._close(bars, length)
        return self._series_or_nan(ta.rsi(close, length=length), close.index, "RSI")

    def atr(self, bars: Sequence[Bar], length: int = 14) -> pd.Series:
        frame = self._ohlc(bars, length)
        return self._series_or_nan(
            ta.atr(frame["high"], frame["low"], frame["close"], length=length),
            frame.index,
            "ATR",
        )

    def macd(
        self,
        bars: Sequence[Bar],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> MACDResult:
        self._validate_length(fast, name="fast")
        self._validate_length(slow, name="slow")
        self._validate_length(signal, name="signal")
        if fast >= slow:
            raise ValueError(f"macd fast ({fast}) must be < slow ({slow})")
        close = self._close(bars, length=1)
        raw = ta.macd(close, fast=fast, slow=slow, signal=signal)
        if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
            nan = self._nan_series(close.index)
            return MACDResult(macd=nan.rename("MACD"), signal=nan.rename("MACDs"), histogram=nan.rename("MACDh"))
        return MACDResult(
            macd=self._column_starting_with(raw, "MACD_").rename("MACD"),
            signal=self._column_starting_with(raw, "MACDs_").rename("MACDs"),
            histogram=self._column_starting_with(raw, "MACDh_").rename("MACDh"),
        )

    def bollinger_bands(
        self,
        bars: Sequence[Bar],
        length: int = 20,
        std: float = 2.0,
    ) -> BollingerBands:
        if std <= 0:
            raise ValueError(f"std must be > 0, got {std}")
        close = self._close(bars, length)
        raw = ta.bbands(close, length=length, std=std)
        if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
            nan = self._nan_series(close.index)
            return BollingerBands(
                upper=nan.rename("BBU"),
                middle=nan.rename("BBM"),
                lower=nan.rename("BBL"),
            )
        return BollingerBands(
            upper=self._column_starting_with(raw, "BBU_").rename("BBU"),
            middle=self._column_starting_with(raw, "BBM_").rename("BBM"),
            lower=self._column_starting_with(raw, "BBL_").rename("BBL"),
        )

    def adx(self, bars: Sequence[Bar], length: int = 14) -> ADXResult:
        frame = self._ohlc(bars, length)
        raw = ta.adx(frame["high"], frame["low"], frame["close"], length=length)
        if raw is None or not isinstance(raw, pd.DataFrame) or raw.empty:
            nan = self._nan_series(frame.index)
            return ADXResult(
                adx=nan.rename("ADX"),
                plus_di=nan.rename("DMP"),
                minus_di=nan.rename("DMN"),
            )
        return ADXResult(
            adx=self._column_starting_with(raw, "ADX_").rename("ADX"),
            plus_di=self._column_starting_with(raw, "DMP_").rename("DMP"),
            minus_di=self._column_starting_with(raw, "DMN_").rename("DMN"),
        )

    def relative_volume(self, bars: Sequence[Bar], length: int = 20) -> pd.Series:
        """Current / mean(previous ``length`` completed bars). No TA library."""
        self._validate_length(length)
        if not bars:
            raise ValueError("bars must be a non-empty sequence")

        values: list[float] = []
        for index in range(len(bars)):
            if index < length:
                values.append(float("nan"))
                continue

            current_volume = bars[index].volume
            if current_volume is None:
                values.append(float("nan"))
                continue

            previous = bars[index - length : index]
            previous_volumes = [bar.volume for bar in previous]
            if any(volume is None for volume in previous_volumes):
                values.append(float("nan"))
                continue

            baseline = sum(float(volume) for volume in previous_volumes) / float(length)
            if baseline == 0.0:
                values.append(float("nan"))
                continue

            values.append(float(current_volume) / baseline)

        return pd.Series(values, dtype="float64", name="RVOL")

    def _close(self, bars: Sequence[Bar], length: int) -> pd.Series:
        self._validate_length(length)
        frame = self._ohlc(bars, min_length=1)
        return frame["close"]

    def _ohlc(self, bars: Sequence[Bar], min_length: int) -> pd.DataFrame:
        self._validate_length(min_length, name="length")
        if not bars:
            raise ValueError("bars must be a non-empty sequence")
        if bars is self._prepared_bars and self._prepared_frame is not None:
            return self._prepared_frame
        return self._build_ohlc(bars)

    @staticmethod
    def _build_ohlc(bars: Sequence[Bar]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": [bar.open for bar in bars],
                "high": [bar.high for bar in bars],
                "low": [bar.low for bar in bars],
                "close": [bar.close for bar in bars],
                "volume": [
                    0.0 if bar.volume is None else float(bar.volume) for bar in bars
                ],
            }
        )

    @staticmethod
    def _validate_length(length: int, *, name: str = "length") -> None:
        if not isinstance(length, int) or isinstance(length, bool) or length < 1:
            raise ValueError(f"{name} must be a positive integer, got {length!r}")

    @staticmethod
    def _nan_series(index: pd.Index) -> pd.Series:
        return pd.Series(float("nan"), index=index, dtype="float64")

    @classmethod
    def _series_or_nan(
        cls,
        result: pd.Series | None,
        index: pd.Index,
        name: str,
    ) -> pd.Series:
        if result is None:
            return cls._nan_series(index).rename(name)
        series = result.astype("float64")
        series.name = name
        return series

    @staticmethod
    def _column_starting_with(frame: pd.DataFrame, prefix: str) -> pd.Series:
        matches = [column for column in frame.columns if str(column).startswith(prefix)]
        # Prefer exact family: MACD_ before MACDh_/MACDs_ when prefix is MACD_
        if prefix == "MACD_":
            matches = [
                column
                for column in matches
                if not str(column).startswith("MACDh_")
                and not str(column).startswith("MACDs_")
            ]
        if not matches:
            raise KeyError(f"Expected column starting with {prefix!r} in {list(frame.columns)}")
        return frame[matches[0]].astype("float64")
