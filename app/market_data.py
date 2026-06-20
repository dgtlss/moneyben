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
        payload = response.json().get("Global Quote", {})
        price = float(payload.get("05. price", 0.0) or 0.0)
        as_of = datetime.now(timezone.utc) if price else None
        return price, as_of
