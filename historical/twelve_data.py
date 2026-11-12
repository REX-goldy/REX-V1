"""Twelve Data historical Forex adapter.

Implements the existing ``HistoricalBarSource`` contract without introducing a
second storage or parsing pipeline: provider JSON -> canonical ``Bar`` list.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, time as clock_time, timedelta
from typing import Any

from historical.bar_contract import build_canonical_bar, validate_bar_sequence
from historical.calendar import is_fx_market_open_minute_utc
from historical.exceptions import (
    HistoricalConfigurationError,
    HistoricalDownloadError,
    HistoricalParseError,
    UnsupportedHistoricalDataError,
)
from models.bar import Bar

DEFAULT_BASE_URL = "https://api.twelvedata.com"
DEFAULT_API_KEY_ENV = "TWELVE_DATA_API_KEY"
SUPPORTED_SYMBOLS = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "AUDUSD": "AUD/USD",
    "USDCAD": "USD/CAD",
    "NZDUSD": "NZD/USD",
    "USDCHF": "USD/CHF",
}
SUPPORTED_TIMEFRAME = "M1"

FetchJson = Callable[[str, float], dict[str, Any]]


class TwelveDataHTTPError(Exception):
    """Internal transport/payload error with an optional HTTP status."""

    def __init__(self, status: int | None, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _default_fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rex-historical/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        message = _extract_error_message(raw) or f"HTTP {exc.code}"
        raise TwelveDataHTTPError(exc.code, message) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TwelveDataHTTPError(None, f"network error: {exc}") from exc

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise TwelveDataHTTPError(None, "provider returned non-JSON data") from exc
    if not isinstance(payload, dict):
        raise TwelveDataHTTPError(None, "provider returned an unexpected payload")
    return payload


def _extract_error_message(raw: bytes | str) -> str:
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return text.strip()[:300]
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("code") or "").strip()
    return ""


class TwelveDataAdapter:
    """Fetch M1 candles from Twelve Data and map them to canonical REX bars.

    The adapter intentionally:
    - uses only the public REST endpoint (no SDK dependency),
    - reads the key from ``api_key_env`` (never stores it in metadata),
    - pages through results deterministically with ``order=asc``,
    - validates actual coverage instead of trusting an HTTP 200.
    """

    provider_id = "twelve_data"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_key_env: str = DEFAULT_API_KEY_ENV,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 30.0,
        max_points_per_request: int = 5000,
        requests_per_minute: int = 8,
        retries: int = 3,
        retry_delay_seconds: float = 1.0,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        fetch_json: FetchJson | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.environ.get(api_key_env)
        if not resolved_key or not resolved_key.strip():
            raise HistoricalConfigurationError(
                f"{api_key_env} is not set; export the Twelve Data API key "
                "in the environment before downloading"
            )
        if max_points_per_request < 1 or max_points_per_request > 5000:
            raise HistoricalConfigurationError(
                "max_points_per_request must be between 1 and 5000"
            )
        if requests_per_minute < 1:
            raise HistoricalConfigurationError("requests_per_minute must be positive")
        if retries < 0 or retry_delay_seconds < 0:
            raise HistoricalConfigurationError(
                "retry settings cannot be negative"
            )

        self._api_key = resolved_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_points_per_request = max_points_per_request
        self.requests_per_minute = requests_per_minute
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds
        self._sleep = sleeper
        self._clock = clock
        self._fetch_json = fetch_json or _default_fetch_json

        self._min_request_interval = 60.0 / requests_per_minute
        self._last_request_at: float | None = None
        self.last_request_count = 0
        self.last_page_count = 0
        self.last_duplicate_count = 0

    def fetch_bars(
        self,
        instrument: str,
        timeframe: str,
        start: date,
        end: date,
    ) -> list[Bar]:
        """Fetch and validate M1 bars for ``start..end`` (inclusive dates)."""
        symbol = self._canonical_symbol(instrument)
        if timeframe.strip().upper() != SUPPORTED_TIMEFRAME:
            raise UnsupportedHistoricalDataError(
                f"Twelve Data adapter currently supports {SUPPORTED_TIMEFRAME} only, "
                f"got {timeframe}"
            )
        if start > end:
            raise ValueError("start cannot be after end")

        self.last_request_count = 0
        self.last_page_count = 0
        self.last_duplicate_count = 0

        range_start = datetime.combine(start, clock_time.min)
        end_dt = datetime.combine(end, clock_time.max)
        cursor_end = end_dt
        by_timestamp: dict[datetime, Bar] = {}
        max_pages = 10000

        # Twelve Data returns the **latest** N points inside the requested
        # boundaries, even when order=asc is supplied. Page backwards from the
        # end so no earlier data can be silently skipped.
        while cursor_end >= range_start:
            if self.last_page_count >= max_pages:
                raise HistoricalDownloadError(
                    f"Twelve Data pagination exceeded {max_pages} pages for "
                    f"{symbol} {start}..{end}"
                )
            values = self._fetch_page(symbol, range_start, cursor_end)
            self.last_page_count += 1
            if not values:
                break

            page_bars: list[Bar] = []
            for value in values:
                bar = self._parse_value(value, symbol)
                if range_start <= bar.timestamp <= cursor_end:
                    page_bars.append(bar)
            if not page_bars:
                break

            for bar in page_bars:
                self._merge_bar(by_timestamp, bar)

            first_ts = min(bar.timestamp for bar in page_bars)
            if len(values) < self.max_points_per_request:
                break

            next_end = first_ts - timedelta(minutes=1)
            if next_end >= cursor_end:
                raise HistoricalDownloadError(
                    "Twelve Data pagination did not advance; refusing to loop"
                )
            cursor_end = next_end

        if not by_timestamp:
            raise HistoricalDownloadError(
                f"Twelve Data returned no {SUPPORTED_TIMEFRAME} bars for "
                f"{symbol} {start}..{end}; check date coverage or plan limits"
            )

        bars = sorted(by_timestamp.values(), key=lambda bar: bar.timestamp)
        open_bars = [bar for bar in bars if is_fx_market_open_minute_utc(bar.timestamp)]
        self.last_filtered_count = len(bars) - len(open_bars)
        if not open_bars:
            raise HistoricalDownloadError(
                f"Twelve Data returned no bars inside the FX weekly session for "
                f"{symbol} {start}..{end}"
            )
        self._validate_coverage_resolved(open_bars, symbol, start, end)
        return validate_bar_sequence(open_bars)

    def _fetch_page(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        params = {
            "symbol": SUPPORTED_SYMBOLS[symbol],
            "interval": "1min",
            "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
            "outputsize": str(self.max_points_per_request),
            "order": "desc",
            "timezone": "UTC",
        }
        payload = self._request_with_retries(params)
        values = payload.get("values", [])
        if values is None:
            return []
        if not isinstance(values, list):
            raise HistoricalDownloadError("Twelve Data returned malformed values")
        return values

    def _request_with_retries(self, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}/time_series?" + urllib.parse.urlencode(
            {**params, "apikey": self._api_key}
        )
        last_error: TwelveDataHTTPError | None = None

        for attempt in range(self.retries + 1):
            self._throttle()
            self.last_request_count += 1
            try:
                payload = self._fetch_json(url, self.timeout_seconds)
            except TwelveDataHTTPError as exc:
                last_error = exc
                if exc.status is not None and exc.status not in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):
                    raise HistoricalDownloadError(
                        f"Twelve Data request failed (HTTP {exc.status}): "
                        f"{self._redact(exc.message)}"
                    ) from exc
            else:
                code, message = _payload_error(payload)
                if code is None:
                    return payload
                if code in (429, 500, 502, 503, 504):
                    last_error = TwelveDataHTTPError(code, message)
                else:
                    raise HistoricalDownloadError(
                        f"Twelve Data request failed (code {code}): "
                        f"{self._redact(message)}"
                    )

            if attempt < self.retries:
                self._sleep(self.retry_delay_seconds * (2**attempt))

        assert last_error is not None
        raise HistoricalDownloadError(
            "Twelve Data request failed after "
            f"{self.retries + 1} attempts: {self._redact(last_error.message)}"
        ) from last_error

    def _redact(self, message: str) -> str:
        """Never surface the API key in errors or logs."""
        return message.replace(self._api_key, "***")

    def _throttle(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            wait = self._min_request_interval - (now - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
        self._last_request_at = now

    @staticmethod
    def _canonical_symbol(instrument: str) -> str:
        normalized = (
            instrument.strip().upper().replace("/", "").replace("_", "").replace("-", "")
        )
        if normalized not in SUPPORTED_SYMBOLS:
            supported = ", ".join(sorted(SUPPORTED_SYMBOLS))
            raise UnsupportedHistoricalDataError(
                f"Twelve Data adapter does not support '{instrument}'. "
                f"Supported: {supported}"
            )
        return normalized

    @staticmethod
    def _parse_value(value: object, symbol: str) -> Bar:
        if not isinstance(value, dict):
            raise HistoricalParseError("Twelve Data returned a non-object candle")
        try:
            raw_timestamp = value["datetime"]
            open_ = value["open"]
            high = value["high"]
            low = value["low"]
            close = value["close"]
        except KeyError as exc:
            raise HistoricalParseError(
                f"Twelve Data candle is missing {exc.args[0]!r}"
            ) from exc
        volume = value.get("volume")
        return build_canonical_bar(
            symbol=symbol,
            timestamp=raw_timestamp,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )

    def _merge_bar(self, by_timestamp: dict[datetime, Bar], bar: Bar) -> None:
        existing = by_timestamp.get(bar.timestamp)
        if existing is None:
            by_timestamp[bar.timestamp] = bar
            return
        if _bar_values(existing) != _bar_values(bar):
            raise HistoricalParseError(
                f"Conflicting duplicate candle at {bar.timestamp.isoformat()}"
            )
        self.last_duplicate_count += 1

    @staticmethod
    def _validate_coverage_resolved(
        bars: list[Bar],
        symbol: str,
        start: date,
        end: date,
    ) -> None:
        requested_start = datetime.combine(start, clock_time.min)
        requested_end = datetime.combine(end, clock_time.max)
        tolerance = timedelta(days=4)
        first = bars[0].timestamp
        last = bars[-1].timestamp
        if first > requested_start + tolerance or last < requested_end - tolerance:
            raise HistoricalDownloadError(
                f"Twelve Data coverage for {symbol} is {first.isoformat()}.."
                f"{last.isoformat()}, which does not cover requested "
                f"{start.isoformat()}..{end.isoformat()}"
            )


def _payload_error(payload: dict[str, Any]) -> tuple[int | None, str]:
    code = payload.get("code")
    if code is None:
        if payload.get("status") != "error":
            return None, ""
        # A structured error without a numeric code is not retryable.
        return 400, str(payload.get("message") or "provider error")
    message = str(payload.get("message") or "provider error")
    try:
        return int(code), message
    except (TypeError, ValueError):
        return 400, f"{code}: {message}"


def _bar_values(bar: Bar) -> tuple[float, float, float, float, float | None]:
    return (bar.open, bar.high, bar.low, bar.close, bar.volume)
