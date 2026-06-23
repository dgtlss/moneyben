"""External market-data providers."""
from __future__ import annotations

from datetime import datetime, timezone

from .http import SimpleSession


class AlphaVantageMarketData:
    def __init__(self, cfg, session=None):
        self.cfg = cfg
        self.session = session or SimpleSession()

    def _symbol(self, ticker: str) -> str:
        return self.cfg.market_symbol_for(ticker)

    @staticmethod
    def _provider_message(payload: dict, ticker: str, expected_key: str) -> str:
        for key in ("Error Message", "Information", "Note"):
            value = payload.get(key)
            if value:
                return f"{ticker}: {value}"
        return f"{ticker}: provider returned no {expected_key} data"

    def candles(self, ticker: str, lookback: int) -> list[dict]:
        response = self.session.get(
            self.cfg.market_data_base_url,
            params={
                "function": "TIME_SERIES_INTRADAY",
                "symbol": self._symbol(ticker),
                "interval": self.cfg.candle_interval,
                "outputsize": "compact",
                "extended_hours": str(self.cfg.extended_hours).lower(),
                "apikey": self.cfg.market_data_api_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        series_key = f"Time Series ({self.cfg.candle_interval})"
        raw_series = payload.get(series_key, {})
        if not raw_series:
            raise RuntimeError(self._provider_message(payload, ticker, "candles"))
        candles = []
        for timestamp, values in raw_series.items():
            candles.append(
                {
                    "start": timestamp,
                    "open": float(values["1. open"]),
                    "high": float(values["2. high"]),
                    "low": float(values["3. low"]),
                    "close": float(values["4. close"]),
                    "volume": float(values.get("5. volume", 0.0)),
                }
            )
        candles.sort(key=lambda candle: candle["start"])
        return candles[-lookback:]

    def price(self, ticker: str) -> tuple[float, datetime | None]:
        response = self.session.get(
            self.cfg.market_data_base_url,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": self._symbol(ticker),
                "apikey": self.cfg.market_data_api_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        quote = payload.get("Global Quote", {})
        if not quote:
            raise RuntimeError(self._provider_message(payload, ticker, "quote"))
        price = float(quote.get("05. price", 0.0) or 0.0)
        as_of = datetime.now(timezone.utc) if price else None
        return price, as_of


class TwelveDataMarketData:
    def __init__(self, cfg, session=None):
        self.cfg = cfg
        self.session = session or SimpleSession()

    def _symbol(self, ticker: str) -> str:
        return self.cfg.market_symbol_for(ticker)

    @staticmethod
    def _provider_message(payload: dict, ticker: str, expected_key: str) -> str:
        for key in ("message", "Message", "code", "status"):
            value = payload.get(key)
            if value and key in {"message", "Message"}:
                return f"{ticker}: {value}"
        return f"{ticker}: provider returned no {expected_key} data"

    @staticmethod
    def _parse_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        normalized = raw.replace(" ", "T")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def candles(self, ticker: str, lookback: int) -> list[dict]:
        response = self.session.get(
            f"{self.cfg.market_data_base_url}/time_series",
            params={
                "symbol": self._symbol(ticker),
                "interval": self.cfg.candle_interval,
                "outputsize": lookback,
                "order": "ASC",
                "apikey": self.cfg.market_data_api_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        values = payload.get("values", [])
        if not values:
            raise RuntimeError(self._provider_message(payload, ticker, "candles"))
        candles = []
        for item in values:
            candles.append(
                {
                    "start": item["datetime"],
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item.get("volume", 0.0) or 0.0),
                }
            )
        candles.sort(key=lambda candle: candle["start"])
        return candles[-lookback:]

    def price(self, ticker: str) -> tuple[float, datetime | None]:
        response = self.session.get(
            f"{self.cfg.market_data_base_url}/quote",
            params={
                "symbol": self._symbol(ticker),
                "apikey": self.cfg.market_data_api_key,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        close = payload.get("close")
        if close in (None, ""):
            raise RuntimeError(self._provider_message(payload, ticker, "quote"))
        price = float(close)
        return price, self._parse_datetime(payload.get("datetime")) or datetime.now(timezone.utc)


def build_market_data_client(cfg, session=None):
    if cfg.market_data_provider == "twelve_data":
        return TwelveDataMarketData(cfg, session=session)
    return AlphaVantageMarketData(cfg, session=session)
