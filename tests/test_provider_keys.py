"""Offline tests for the server-side provider credential store."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

from historical import downloader as downloader_module
from historical.config import load_historical_config
from historical.exceptions import HistoricalConfigurationError
from server import provider_keys
from server import research_service as service


class ProviderKeyStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.keys_file = self.root / "keys" / "provider_keys.json"
        self.env = patch.dict(
            os.environ,
            {
                "REX_KEYS_FILE": str(self.keys_file),
                "REX_DATA_DIR": str(self.root / "historical"),
                "TWELVE_DATA_API_KEY": "",
                "DUKASCOPY_API_KEY": "",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_save_list_delete_and_mask_secret(self) -> None:
        secret = "secret-value-9876"
        saved = provider_keys.set_provider_key("twelve_data", secret)

        self.assertTrue(saved["configured"])
        self.assertEqual(saved["source"], "stored")
        self.assertEqual(saved["hint"], "9876")
        self.assertNotIn("api_key", saved)
        self.assertNotIn(secret, json.dumps(saved))
        self.assertIsNotNone(saved["updated_at"])

        credentials = provider_keys.list_provider_credentials()
        self.assertEqual(
            [item["id"] for item in credentials], ["twelve_data", "dukascopy"]
        )
        rendered = json.dumps(credentials)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("api_key", rendered)
        twelve = next(item for item in credentials if item["id"] == "twelve_data")
        self.assertEqual(twelve["hint"], "9876")
        self.assertEqual(twelve["source"], "stored")

        self.assertEqual(
            provider_keys.get_provider_key("twelve_data"), secret
        )
        self.assertTrue(provider_keys.has_provider_key("twelve_data"))

        deleted = provider_keys.delete_provider_key("twelve_data")
        self.assertFalse(deleted["configured"])
        self.assertEqual(deleted["source"], "none")
        self.assertEqual(deleted["hint"], provider_keys._MASK)
        self.assertIsNone(provider_keys.get_provider_key("twelve_data"))
        self.assertNotIn(
            "twelve_data",
            json.loads(self.keys_file.read_text(encoding="utf-8"))["providers"],
        )

    def test_store_file_is_owner_only_on_posix(self) -> None:
        if os.name != "posix":
            self.skipTest("POSIX permissions only")
        provider_keys.set_provider_key("twelve_data", "abc-1234")
        self.assertTrue(self.keys_file.is_file())
        mode = stat.S_IMODE(self.keys_file.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_environment_fallback_and_stored_precedence(self) -> None:
        with patch.dict(
            os.environ, {"TWELVE_DATA_API_KEY": "environment-key-4321"}, clear=False
        ):
            credentials = provider_keys.list_provider_credentials()
            twelve = next(
                item for item in credentials if item["id"] == "twelve_data"
            )
            self.assertEqual(twelve["source"], "environment")
            self.assertEqual(twelve["hint"], "4321")
            self.assertEqual(
                provider_keys.get_provider_key("twelve_data"),
                "environment-key-4321",
            )

            provider_keys.set_provider_key("twelve_data", "stored-key-8765")
            twelve = next(
                item
                for item in provider_keys.list_provider_credentials()
                if item["id"] == "twelve_data"
            )
            self.assertEqual(twelve["source"], "stored")
            self.assertEqual(twelve["hint"], "8765")
            self.assertEqual(
                provider_keys.get_provider_key("twelve_data"), "stored-key-8765"
            )

            provider_keys.delete_provider_key("twelve_data")
            twelve = next(
                item
                for item in provider_keys.list_provider_credentials()
                if item["id"] == "twelve_data"
            )
            self.assertEqual(twelve["source"], "environment")
            self.assertEqual(
                provider_keys.get_provider_key("twelve_data"),
                "environment-key-4321",
            )

    def test_short_key_hint_is_fully_masked(self) -> None:
        saved = provider_keys.set_provider_key("dukascopy", "abc")
        self.assertEqual(saved["hint"], provider_keys._MASK)
        self.assertNotIn("abc", saved["hint"])

    def test_four_and_five_character_hints_never_reveal_full_secret(self) -> None:
        for secret in ("abcd", "abcde"):
            with self.subTest(length=len(secret), source="stored"):
                saved = provider_keys.set_provider_key("twelve_data", secret)
                self.assertEqual(saved["source"], "stored")
                self.assertNotIn(secret, json.dumps(saved))
                if len(secret) <= 4:
                    self.assertEqual(saved["hint"], provider_keys._MASK)
                else:
                    self.assertEqual(saved["hint"], secret[-4:])
                    self.assertNotEqual(saved["hint"], secret)
                provider_keys.delete_provider_key("twelve_data")

            with self.subTest(length=len(secret), source="environment"):
                with patch.dict(
                    os.environ, {"TWELVE_DATA_API_KEY": secret}, clear=False
                ):
                    twelve = next(
                        item
                        for item in provider_keys.list_provider_credentials()
                        if item["id"] == "twelve_data"
                    )
                self.assertEqual(twelve["source"], "environment")
                self.assertNotIn(secret, json.dumps(twelve))
                if len(secret) <= 4:
                    self.assertEqual(twelve["hint"], provider_keys._MASK)
                else:
                    self.assertEqual(twelve["hint"], secret[-4:])
                    self.assertNotEqual(twelve["hint"], secret)

    def test_unknown_provider_is_rejected(self) -> None:
        for operation in (
            lambda: provider_keys.set_provider_key("unknown", "value"),
            lambda: provider_keys.get_provider_key("unknown"),
            lambda: provider_keys.delete_provider_key("unknown"),
        ):
            with self.assertRaises(provider_keys.UnknownProviderError):
                operation()

    def test_invalid_keys_are_rejected(self) -> None:
        for value in ("", "   ", "x" * 513, "abc\ndef", "abc\tdef"):
            with self.subTest(value=repr(value)):
                with self.assertRaises(provider_keys.InvalidProviderKeyError):
                    provider_keys.set_provider_key("twelve_data", value)
        self.assertFalse(self.keys_file.exists())

    def test_corrupt_store_raises_instead_of_wiping(self) -> None:
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        self.keys_file.write_text("{not valid json", encoding="utf-8")
        with self.assertRaises(provider_keys.ProviderKeyStoreError):
            provider_keys.list_provider_credentials()
        self.assertEqual(
            self.keys_file.read_text(encoding="utf-8"), "{not valid json"
        )

        self.keys_file.write_text("[]", encoding="utf-8")
        with self.assertRaises(provider_keys.ProviderKeyStoreError):
            provider_keys.get_provider_key("twelve_data")

    def test_has_twelve_data_key_uses_stored_key(self) -> None:
        self.assertFalse(service.has_twelve_data_key())
        provider_keys.set_provider_key("twelve_data", "stored-key-1111")
        self.assertTrue(service.has_twelve_data_key())

    def test_overview_reports_stored_capability(self) -> None:
        warning_text = " ".join(service.overview()["warnings"])
        self.assertIn("System → Key handling", warning_text)
        self.assertFalse(service.overview()["capabilities"]["twelve_data"])

        provider_keys.set_provider_key("twelve_data", "stored-key-2222")
        overview = service.overview()
        self.assertTrue(overview["capabilities"]["twelve_data"])
        self.assertNotIn("System → Key handling", " ".join(overview["warnings"]))

    def test_download_uses_stored_key_without_network(self) -> None:
        secret = "stored-key-3333"
        provider_keys.set_provider_key("twelve_data", secret)
        sentinel = object()
        with patch.dict(
            os.environ, {"TWELVE_DATA_API_KEY": "environment-key-unchanged"},
            clear=False,
        ):
            environment_before = os.environ.get("TWELVE_DATA_API_KEY")
            with patch.object(
                service, "build_source", return_value=sentinel
            ) as build_source, patch.object(
                service, "HistoricalDownloader"
            ) as downloader:
                downloader.return_value.download.return_value = ()
                result = service.download_dataset(
                    provider="twelve_data",
                    symbol="EURUSD",
                    timeframe="M1",
                    start=date(2024, 1, 2),
                    end=date(2024, 1, 2),
                )

            self.assertEqual(
                os.environ.get("TWELVE_DATA_API_KEY"), environment_before
            )
            self.assertEqual(
                os.environ.get("TWELVE_DATA_API_KEY"), "environment-key-unchanged"
            )

        self.assertEqual(result, [])
        build_source.assert_called_once()
        self.assertEqual(build_source.call_args.kwargs["api_key"], secret)
        downloader.assert_called_once()
        self.assertIs(downloader.call_args.kwargs["adapter"], sentinel)

    def test_download_without_key_raises_configuration_error(self) -> None:
        with patch.object(service, "build_source") as build_source:
            with self.assertRaises(HistoricalConfigurationError) as raised:
                service.download_dataset(
                    provider="twelve_data",
                    symbol="EURUSD",
                    timeframe="M1",
                    start=date(2024, 1, 2),
                    end=date(2024, 1, 2),
                )
        self.assertIn("System → Key handling", str(raised.exception))
        build_source.assert_not_called()

    def test_build_source_passes_explicit_key(self) -> None:
        config = replace(
            load_historical_config(), provider="twelve_data", symbols=("EURUSD",)
        )
        with patch.object(downloader_module, "TwelveDataAdapter") as adapter:
            downloader_module.build_source(config, api_key="explicit-key")
        adapter.assert_called_once()
        self.assertEqual(adapter.call_args.kwargs["api_key"], "explicit-key")


if __name__ == "__main__":
    unittest.main()
