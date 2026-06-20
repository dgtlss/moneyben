import importlib
import os
import unittest
from unittest import mock


def load_config(env: dict[str, str]):
    with mock.patch.dict(os.environ, env, clear=True):
        import app.config

        return importlib.reload(app.config).Config()


class ConfigTests(unittest.TestCase):
    def test_demo_env_uses_demo_specific_credentials(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "alpha-key",
                "T212_ENV": "demo",
                "T212_DEMO_API_KEY": "demo-only-key",
                "T212_DEMO_API_SECRET": "demo-only-secret",
                "T212_API_KEY": "live-key",
                "T212_API_SECRET": "live-secret",
            }
        )

        self.assertEqual(cfg.t212_api_key, "demo-only-key")
        self.assertEqual(cfg.t212_api_secret, "demo-only-secret")

    def test_read_only_flag_is_loaded(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "T212_API_KEY": "live-key",
                "T212_API_SECRET": "live-secret",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "alpha-key",
                "READ_ONLY": "true",
            }
        )

        self.assertTrue(cfg.read_only)

    def test_tickers_preserve_case(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "T212_API_KEY": "demo-key",
                "T212_API_SECRET": "demo-secret",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "alpha-key",
                "TICKERS": "HASl_EQ,AAPL_US_EQ",
            }
        )

        self.assertEqual(cfg.tickers, ["HASl_EQ", "AAPL_US_EQ"])

    def test_validate_requires_trading212_credentials(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "alpha-key",
                "T212_API_KEY": "",
                "T212_API_SECRET": "",
            }
        )

        self.assertIn(
            "T212_API_KEY and T212_API_SECRET are required.",
            cfg.validate(),
        )

    def test_validate_requires_market_data_credentials(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "T212_API_KEY": "demo-key",
                "T212_API_SECRET": "demo-secret",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "",
            }
        )

        self.assertIn(
            "MARKET_DATA_API_KEY is required for MARKET_DATA_PROVIDER=alpha_vantage.",
            cfg.validate(),
        )

    def test_validate_rejects_invalid_t212_env(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "T212_API_KEY": "demo-key",
                "T212_API_SECRET": "demo-secret",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "alpha-key",
                "T212_ENV": "sandbox",
            }
        )

        self.assertIn("T212_ENV must be either 'demo' or 'live'.", cfg.validate())

    def test_validate_rejects_empty_tickers(self):
        cfg = load_config(
            {
                "OPENROUTER_API_KEY": "sk-or-test",
                "T212_API_KEY": "demo-key",
                "T212_API_SECRET": "demo-secret",
                "MARKET_DATA_PROVIDER": "alpha_vantage",
                "MARKET_DATA_API_KEY": "alpha-key",
                "TICKERS": " , ",
            }
        )

        self.assertIn("TICKERS is empty.", cfg.validate())


if __name__ == "__main__":
    unittest.main()
