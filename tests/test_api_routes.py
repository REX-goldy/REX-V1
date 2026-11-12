"""Contract test for the terminal API route surface."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import server.main as api
from server.main import app


class ApiRouteContractTests(unittest.TestCase):
    def test_expected_routes_are_registered(self) -> None:
        paths = {route.path for route in app.routes}
        for path in (
            "/api/health",
            "/api/overview",
            "/api/strategies",
            "/api/datasets",
            "/api/dataset",
            "/api/frame",
            "/api/range",
            "/api/bars",
            "/api/runs",
            "/api/runs/{run_id}",
            "/api/backtests",
            "/api/downloads",
            "/api/settings/providers",
            "/api/settings/providers/{provider_id}",
            "/api/workspace/strategies",
            "/api/workspace/strategies/{strategy_id}",
            "/api/workspace/strategies/{strategy_id}/notes",
            "/api/workspace/strategies/{strategy_id}/notes/{note_id}",
            "/api/workspace/strategies/{strategy_id}/variations",
            "/api/workspace/strategies/{strategy_id}/variations/{variation_id}",
            "/api/workspace/strategies/{strategy_id}/variations/{variation_id}/clone",
            "/api/workspace/dashboard",
            "/api/workspace/strategies/{strategy_id}/experiments",
            "/api/workspace/strategies/{strategy_id}/experiments/plan",
            "/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}",
            "/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}/amendments",
            "/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}/reproduce",
            "/api/workspace/strategies/{strategy_id}/comparison",
            "/api/zones",
            "/api/zones/{zone_id}",
            "/api/cost-profiles",
            "/api/dataset-quality",
            "/api/validation/backtest",
            "/api/runs/{run_id}/validation",
        ):
            self.assertIn(path, paths)
        self.assertNotIn("/api/instruments", paths)


class ProviderCredentialRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.keys_file = self.root / "keys" / "provider_keys.json"
        self.env = patch.dict(
            os.environ,
            {
                "REX_KEYS_FILE": str(self.keys_file),
                "TWELVE_DATA_API_KEY": "",
                "DUKASCOPY_API_KEY": "",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_list_save_and_delete_masked_credentials(self) -> None:
        initial = api.settings_providers()
        self.assertEqual(
            [item["id"] for item in initial], ["twelve_data", "dukascopy"]
        )
        self.assertFalse(initial[0]["configured"])

        secret = "api-secret-value-2468"
        saved = api.save_settings_provider(
            "twelve_data", api.ProviderKeyRequest(api_key=secret)
        )
        self.assertTrue(saved["configured"])
        self.assertEqual(saved["source"], "stored")
        self.assertEqual(saved["hint"], "2468")
        self.assertNotIn("api_key", saved)
        self.assertNotIn(secret, json.dumps(saved))

        listed = api.settings_providers()
        rendered = json.dumps(listed)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("api_key", rendered)

        deleted = api.delete_settings_provider("twelve_data")
        self.assertFalse(deleted["configured"])
        self.assertEqual(deleted["source"], "none")
        self.assertNotIn(secret, json.dumps(deleted))

    def test_unknown_provider_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            api.save_settings_provider(
                "does_not_exist", api.ProviderKeyRequest(api_key="value")
            )
        self.assertEqual(raised.exception.status_code, 404)
        self.assertNotIn("value", str(raised.exception.detail))

    def test_invalid_key_returns_400_without_echoing_it(self) -> None:
        for secret in ("   ", "bad\nkey", "x" * 513):
            with self.subTest(secret=repr(secret)):
                with self.assertRaises(HTTPException) as raised:
                    api.save_settings_provider(
                        "twelve_data", api.ProviderKeyRequest(api_key=secret)
                    )
                self.assertEqual(raised.exception.status_code, 400)
                self.assertNotIn(secret, str(raised.exception.detail))

    def test_corrupt_store_returns_500_without_leaking_key(self) -> None:
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)
        self.keys_file.write_text("corrupt-secret-marker", encoding="utf-8")
        with self.assertRaises(HTTPException) as raised:
            api.settings_providers()
        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn("corrupt-secret-marker", str(raised.exception.detail))

        submitted = "submitted-secret-1357"
        with self.assertRaises(HTTPException) as raised:
            api.save_settings_provider(
                "twelve_data", api.ProviderKeyRequest(api_key=submitted)
            )
        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn(submitted, str(raised.exception.detail))


if __name__ == "__main__":
    unittest.main()
