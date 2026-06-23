from types import SimpleNamespace
import unittest
from unittest.mock import Mock


def make_cfg():
    return SimpleNamespace(
        market_data_base_url="https://www.alphavantage.co/query",
        candle_interval="1min",
        extended_hours=False,
        market_data_api_key="alpha-key",
        market_symbol_for=lambda ticker: ticker.split("_", 1)[0],
    )


class MarketDataTests(unittest.TestCase):
    def test_twelve_data_candles_parse_values_array(self):
        from app.market_data import TwelveDataMarketData

        session = Mock()
        response = Mock()
        response.json.return_value = {
            "meta": {"symbol": "AAPL", "interval": "1min"},
            "values": [
                {"datetime": "2026-06-23 14:31:00", "open": "200.0", "high": "201.0", "low": "199.5", "close": "200.5", "volume": "1000"},
                {"datetime": "2026-06-23 14:32:00", "open": "200.5", "high": "201.5", "low": "200.0", "close": "201.0", "volume": "1500"},
            ],
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response

        client = TwelveDataMarketData(
            SimpleNamespace(
                market_data_base_url="https://api.twelvedata.com",
                candle_interval="1min",
                market_data_api_key="twelve-key",
                market_symbol_for=lambda ticker: ticker.split("_", 1)[0],
            ),
            session=session,
        )

        candles = client.candles("AAPL_US_EQ", 120)

        self.assertEqual(candles[-1]["close"], 201.0)
        session.get.assert_called_once()

    def test_twelve_data_price_uses_quote_close(self):
        from app.market_data import TwelveDataMarketData

        session = Mock()
        response = Mock()
        response.json.return_value = {
            "symbol": "AAPL",
            "close": "201.25",
            "datetime": "2026-06-23 14:32:00",
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response

        client = TwelveDataMarketData(
            SimpleNamespace(
                market_data_base_url="https://api.twelvedata.com",
                candle_interval="1min",
                market_data_api_key="twelve-key",
                market_symbol_for=lambda ticker: ticker.split("_", 1)[0],
            ),
            session=session,
        )

        price, as_of = client.price("AAPL_US_EQ")

        self.assertEqual(price, 201.25)
        self.assertIsNotNone(as_of)

    def test_twelve_data_raises_provider_message(self):
        from app.market_data import TwelveDataMarketData

        session = Mock()
        response = Mock()
        response.json.return_value = {"code": 429, "message": "API credits exhausted"}
        response.raise_for_status.return_value = None
        session.get.return_value = response

        client = TwelveDataMarketData(
            SimpleNamespace(
                market_data_base_url="https://api.twelvedata.com",
                candle_interval="1min",
                market_data_api_key="twelve-key",
                market_symbol_for=lambda ticker: ticker.split("_", 1)[0],
            ),
            session=session,
        )

        with self.assertRaises(RuntimeError) as ctx:
            client.candles("AAPL_US_EQ", 120)

        self.assertIn("API credits exhausted", str(ctx.exception))

    def test_candles_raises_provider_message_when_time_series_missing(self):
        from app.market_data import AlphaVantageMarketData

        session = Mock()
        response = Mock()
        response.json.return_value = {
            "Information": "The TIME_SERIES_INTRADAY API is a premium endpoint."
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response

        client = AlphaVantageMarketData(make_cfg(), session=session)

        with self.assertRaises(RuntimeError) as ctx:
            client.candles("AAPL_US_EQ", 120)

        self.assertIn("AAPL_US_EQ", str(ctx.exception))
        self.assertIn("premium endpoint", str(ctx.exception))

    def test_price_raises_provider_message_when_quote_missing(self):
        from app.market_data import AlphaVantageMarketData

        session = Mock()
        response = Mock()
        response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage. Please visit premium."
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response

        client = AlphaVantageMarketData(make_cfg(), session=session)

        with self.assertRaises(RuntimeError) as ctx:
            client.price("AAPL_US_EQ")

        self.assertIn("AAPL_US_EQ", str(ctx.exception))
        self.assertIn("Please visit premium", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
