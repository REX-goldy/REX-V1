"""Twelve Data adapter and downloader integration tests (offline)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from historical.config import load_historical_config
from historical.downloader import HistoricalDownloader, build_source
from historical.exceptions import (
    HistoricalConfigurationError,
    HistoricalDownloadError,
    HistoricalParseError,
    UnsupportedHistoricalDataError,
)
from historical.storage import HistoricalStorage
from historical.twelve_data import TwelveDataAdapter, TwelveDataHTTPError
from models.bar import Bar
from research.free_ohlc.resampler import resample_bars


def _value(
    stamp: str,
    *,
    open_: str = "1.1000",
    high: str = "1.1010",
    low: str = "1.0990",
    close: str = "1.1005",
) -> dict[str, str]:
    return {
        "datetime": stamp,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
    }


def _page(*values: dict[str, str]) -> dict[str, object]:
    return {"status": "ok", "values": list(values)}


class FakeTransport:
    """Queue of payloads/exceptions; records parsed query strings."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.queries: list[dict[str, list[str]]] = []

    def __call__(self, url: str, timeout: float) -> dict[str, object]:
        self.queries.append(parse_qs(urlparse(url).query))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        assert isinstance(response, dict)
        return response


def _adapter(
    transport: FakeTransport,
    *,
    max_points: int = 5000,
    retries: int = 0,
    sleeper=None,
) -> TwelveDataAdapter:
    return TwelveDataAdapter(
        api_key="test-key",
        max_points_per_request=max_points,
        requests_per_minute=6000,
        retries=retries,
        retry_delay_seconds=0.01,
        sleeper=sleeper or (lambda _: None),
        fetch_json=transport,
    )


class TwelveDataAdapterTests(unittest.TestCase):
    def test_maps_symbols_and_normalizes_utc_bars(self) -> None:
        transport = FakeTransport(
            [_page(_value("2026-01-05 00:00:00"), _value("2026-01-05 00:01:00"))]
        )
        bars = _adapter(transport).fetch_bars(
            "eurusd", "M1", date(2026, 1, 5), date(2026, 1, 5)
        )

        self.assertEqual([bar.symbol for bar in bars], ["EURUSD", "EURUSD"])
        self.assertEqual(bars[0].timestamp, datetime(2026, 1, 5, 0, 0, 0))
        self.assertIsNone(bars[0].volume)
        query = transport.queries[0]
        self.assertEqual(query["symbol"], ["EUR/USD"])
        self.assertEqual(query["interval"], ["1min"])
        self.assertEqual(query["timezone"], ["UTC"])
        self.assertEqual(query["order"], ["desc"])

    def test_gbp_usd_mapping(self) -> None:
        transport = FakeTransport([_page(_value("2026-01-05 00:00:00"))])
        bars = _adapter(transport).fetch_bars(
            "GBP/USD", "M1", date(2026, 1, 5), date(2026, 1, 5)
        )
        self.assertEqual(bars[0].symbol, "GBPUSD")
        self.assertEqual(transport.queries[0]["symbol"], ["GBP/USD"])

    def test_additional_pair_mapping(self) -> None:
        for rex_symbol, provider_symbol in (
            ("USDJPY", "USD/JPY"),
            ("AUDUSD", "AUD/USD"),
            ("USDCAD", "USD/CAD"),
        ):
            transport = FakeTransport([_page(_value("2026-01-05 00:00:00"))])
            bars = _adapter(transport).fetch_bars(
                rex_symbol, "M1", date(2026, 1, 5), date(2026, 1, 5)
            )
            self.assertEqual(bars[0].symbol, rex_symbol)
            self.assertEqual(transport.queries[0]["symbol"], [provider_symbol])

    def test_paginates_backwards_without_duplicates(self) -> None:
        transport = FakeTransport(
            [
                _page(_value("2026-01-05 00:09:00"), _value("2026-01-05 00:10:00")),
                _page(_value("2026-01-05 00:07:00"), _value("2026-01-05 00:08:00")),
                _page(_value("2026-01-05 00:05:00")),
            ]
        )
        adapter = _adapter(transport, max_points=2)
        bars = adapter.fetch_bars("EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5))

        self.assertEqual(
            [bar.timestamp.strftime("%H:%M") for bar in bars],
            ["00:05", "00:07", "00:08", "00:09", "00:10"],
        )
        self.assertEqual(adapter.last_page_count, 3)
        self.assertEqual(adapter.last_duplicate_count, 0)
        self.assertEqual(
            transport.queries[1]["end_date"], ["2026-01-05 00:08:00"]
        )

    def test_filters_weekend_closure_bars(self) -> None:
        transport = FakeTransport(
            [
                _page(
                    _value("2026-01-03 12:00:00"),  # Saturday
                    _value("2026-01-04 21:59:00"),  # Sunday before open
                    _value("2026-01-04 22:00:00"),  # Sunday open
                    _value("2026-01-05 00:00:00"),  # Monday
                )
            ]
        )
        adapter = _adapter(transport)
        bars = adapter.fetch_bars(
            "EURUSD", "M1", date(2026, 1, 3), date(2026, 1, 5)
        )
        self.assertEqual(
            [bar.timestamp.strftime("%Y-%m-%d %H:%M") for bar in bars],
            ["2026-01-04 22:00", "2026-01-05 00:00"],
        )
        self.assertEqual(adapter.last_filtered_count, 2)

    def test_rejects_conflicting_duplicate_timestamp(self) -> None:
        transport = FakeTransport(
            [
                _page(
                    _value("2026-01-05 00:10:00"),
                    _value("2026-01-05 00:10:00", close="1.2000"),
                ),
            ]
        )
        adapter = _adapter(transport, max_points=2)
        with self.assertRaises(HistoricalParseError):
            adapter.fetch_bars("EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5))

    def test_identical_duplicate_is_deduplicated(self) -> None:
        transport = FakeTransport(
            [
                _page(_value("2026-01-05 00:10:00"), _value("2026-01-05 00:10:00")),
                _page(_value("2026-01-05 00:08:00")),
            ]
        )
        adapter = _adapter(transport, max_points=2)
        bars = adapter.fetch_bars("EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5))
        self.assertEqual(len(bars), 2)
        self.assertEqual(adapter.last_duplicate_count, 1)

    def test_rejects_invalid_ohlc(self) -> None:
        transport = FakeTransport(
            [_page(_value("2026-01-05 00:00:00", high="1.0000", low="1.2000"))]
        )
        with self.assertRaises(HistoricalParseError):
            _adapter(transport).fetch_bars(
                "EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5)
            )

    def test_empty_response_is_an_error(self) -> None:
        transport = FakeTransport([{"status": "ok", "values": []}])
        with self.assertRaises(HistoricalDownloadError):
            _adapter(transport).fetch_bars(
                "EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5)
            )

    def test_no_data_payload_is_not_retried(self) -> None:
        transport = FakeTransport(
            [
                {
                    "status": "error",
                    "code": 400,
                    "message": "No data is available on the specified dates.",
                }
            ]
        )
        adapter = _adapter(transport, retries=3)
        with self.assertRaises(HistoricalDownloadError):
            adapter.fetch_bars("EURUSD", "M1", date(2020, 2, 10), date(2020, 2, 12))
        self.assertEqual(len(transport.queries), 1)

    def test_coverage_gap_is_rejected(self) -> None:
        transport = FakeTransport(
            [_page(_value("2026-01-05 00:00:00"), _value("2026-01-05 00:01:00"))]
        )
        with self.assertRaises(HistoricalDownloadError):
            _adapter(transport).fetch_bars(
                "EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 18)
            )

    def test_retries_429_then_succeeds(self) -> None:
        sleeps: list[float] = []
        transport = FakeTransport(
            [
                TwelveDataHTTPError(429, "rate limited"),
                _page(_value("2026-01-05 00:00:00")),
            ]
        )
        bars = _adapter(transport, retries=1, sleeper=sleeps.append).fetch_bars(
            "EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5)
        )
        self.assertEqual(len(bars), 1)
        self.assertEqual(len(transport.queries), 2)
        self.assertTrue(sleeps)

    def test_auth_error_is_not_retried(self) -> None:
        transport = FakeTransport([TwelveDataHTTPError(401, "invalid key")])
        adapter = _adapter(transport, retries=3)
        with self.assertRaises(HistoricalDownloadError):
            adapter.fetch_bars("EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5))
        self.assertEqual(len(transport.queries), 1)

    def test_server_error_retries_are_bounded(self) -> None:
        transport = FakeTransport(
            [TwelveDataHTTPError(503, "unavailable") for _ in range(3)]
        )
        adapter = _adapter(transport, retries=2)
        with self.assertRaises(HistoricalDownloadError):
            adapter.fetch_bars("EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5))
        self.assertEqual(len(transport.queries), 3)

    def test_missing_api_key_is_a_configuration_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HistoricalConfigurationError):
                TwelveDataAdapter()

    def test_adapter_output_resamples_to_h1(self) -> None:
        values = [
            _value(
                f"2026-01-05 00:{minute:02d}:00",
                open_=f"{1.1000 + minute / 10000:.5f}",
                high=f"{1.1010 + minute / 10000:.5f}",
                low=f"{1.0990 + minute / 10000:.5f}",
                close=f"{1.1005 + minute / 10000:.5f}",
            )
            for minute in range(60)
        ]
        transport = FakeTransport([_page(*values)])
        bars = _adapter(transport).fetch_bars(
            "EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5)
        )
        result = resample_bars(bars, target_timeframe="H1")

        self.assertEqual(len(result.bars), 1)
        hourly = result.bars[0]
        self.assertEqual(hourly.timestamp, datetime(2026, 1, 5, 0, 0, 0))
        self.assertAlmostEqual(hourly.open, bars[0].open)
        self.assertAlmostEqual(hourly.close, bars[-1].close)
        self.assertAlmostEqual(hourly.high, max(bar.high for bar in bars))
        self.assertAlmostEqual(hourly.low, min(bar.low for bar in bars))
        self.assertIsNone(hourly.volume)

    def test_partial_hour_is_not_emitted(self) -> None:
        values = [
            _value(f"2026-01-05 00:{minute:02d}:00") for minute in range(59)
        ]
        transport = FakeTransport([_page(*values)])
        bars = _adapter(transport).fetch_bars(
            "EURUSD", "M1", date(2026, 1, 5), date(2026, 1, 5)
        )
        result = resample_bars(bars, target_timeframe="H1")
        self.assertEqual(len(result.bars), 0)

    def test_unsupported_symbol_and_timeframe(self) -> None:
        transport = FakeTransport([])
        with self.assertRaises(UnsupportedHistoricalDataError):
            _adapter(transport).fetch_bars(
                "EURGBP", "M1", date(2026, 1, 5), date(2026, 1, 5)
            )
        with self.assertRaises(UnsupportedHistoricalDataError):
            _adapter(transport).fetch_bars(
                "EURUSD", "H1", date(2026, 1, 5), date(2026, 1, 5)
            )


class TwelveDataDownloaderTests(unittest.TestCase):
    class FakeSource:
        provider_id = "twelve_data"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_bars(self, instrument, timeframe, start, end) -> list[Bar]:
            self.calls += 1
            return [
                Bar("EURUSD", datetime(2026, 1, 5, 0, 0), 1.10, 1.11, 1.09, 1.105),
                Bar("EURUSD", datetime(2026, 1, 5, 0, 1), 1.105, 1.115, 1.10, 1.11),
            ]

    def test_downloader_writes_provenance_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = replace(
                load_historical_config(),
                provider="twelve_data",
                symbols=("EURUSD",),
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 9),
                data_directory=Path(directory),
                retries=0,
                overwrite_existing_files=False,
            )
            source = self.FakeSource()
            downloader = HistoricalDownloader(config, adapter=source)
            path = downloader.download()[0]
            first_hash = path.read_bytes()

            metadata = json.loads(
                path.with_suffix(".meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual(metadata["provider"], "twelve_data")
            self.assertEqual(metadata["bar_count"], 2)
            self.assertEqual(metadata["requested_start_date"], "2026-01-05")
            self.assertEqual(metadata["requested_end_date"], "2026-01-09")
            self.assertEqual(metadata["actual_start_date"], "2026-01-05T00:00:00")
            self.assertIn("retrieved_at", metadata)
            self.assertEqual(metadata["duplicate_count"], 0)
            self.assertEqual(source.calls, 1)

            # Second download must skip the covered partition.
            downloader.download()
            self.assertEqual(source.calls, 1)
            self.assertEqual(path.read_bytes(), first_hash)

    def test_refuses_cross_provider_merge_in_same_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = HistoricalStorage(Path(directory))
            storage.write_year(
                "EURUSD",
                "M1",
                2026,
                [Bar("EURUSD", datetime(2026, 6, 1), 1.1, 1.2, 1.0, 1.15)],
                date(2026, 1, 1),
                date(2026, 6, 30),
                provider="dukascopy",
            )
            config = replace(
                load_historical_config(),
                provider="twelve_data",
                symbols=("EURUSD",),
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                data_directory=Path(directory),
                retries=0,
                overwrite_existing_files=False,
            )
            with self.assertRaises(HistoricalDownloadError):
                HistoricalDownloader(config, adapter=self.FakeSource()).download()

    def test_build_source_selects_configured_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = replace(
                load_historical_config(),
                provider="twelve_data",
                data_directory=Path(directory),
                symbols=("EURUSD",),
            )
            with patch.dict(
                os.environ, {"TWELVE_DATA_API_KEY": "test-key"}, clear=False
            ):
                source = build_source(config)
            self.assertIsInstance(source, TwelveDataAdapter)
            self.assertEqual(source.provider_id, "twelve_data")


class TwelveDataConfigTests(unittest.TestCase):
    def test_loads_twelve_data_config_with_defaults(self) -> None:
        payload = {
            "provider": "twelve_data",
            "symbols": ["EURUSD", "GBPUSD"],
            "timeframe": "M1",
            "start_date": "2020-04-07",
            "end_date": "2026-10-29",
            "timeout_seconds": 30,
            "retries": 3,
            "retry_delay_seconds": 2,
            "data_directory": "data/historical",
            "overwrite_existing_files": False,
            "duka_threads": 1,
            "include_header": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_historical_config(path)

        self.assertEqual(config.provider, "twelve_data")
        self.assertEqual(config.api_key_env, "TWELVE_DATA_API_KEY")
        self.assertEqual(config.max_points_per_request, 5000)
        self.assertEqual(config.requests_per_minute, 8)
