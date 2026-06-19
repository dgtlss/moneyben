"""Coinbase Advanced Trade access.

Market data comes from the *public* brokerage endpoints (no auth needed), so
paper mode works with zero Coinbase credentials. Order placement and balance
sync use the official `coinbase-advanced-py` SDK and only run in real mode.
"""
from __future__ import annotations

import logging
import time
import uuid

import requests

log = logging.getLogger("coinbase")

PUBLIC_BASE = "https://api.coinbase.com/api/v3/brokerage/market"


class MarketData:
    """Public, unauthenticated market data."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def candles(self, product_id: str, minutes: int) -> list[dict]:
        """Return up to `minutes` of ONE_MINUTE candles, oldest -> newest.

        Each candle: {start, low, high, open, close, volume} (floats).
        """
        end = int(time.time())
        start = end - minutes * 60
        url = f"{PUBLIC_BASE}/products/{product_id}/candles"
        params = {"start": str(start), "end": str(end), "granularity": "ONE_MINUTE", "limit": 350}
        resp = self.session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw = resp.json().get("candles", [])
        candles = [
            {
                "start": int(c["start"]),
                "low": float(c["low"]),
                "high": float(c["high"]),
                "open": float(c["open"]),
                "close": float(c["close"]),
                "volume": float(c["volume"]),
            }
            for c in raw
        ]
        # Coinbase returns newest-first; we want chronological order.
        candles.sort(key=lambda c: c["start"])
        return candles

    def price(self, product_id: str) -> float | None:
        url = f"{PUBLIC_BASE}/products/{product_id}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        p = data.get("price")
        return float(p) if p is not None else None


class TradeClient:
    """Authenticated client for balances and order placement (real mode only)."""

    def __init__(self, api_key: str, api_secret: str):
        # Imported lazily so paper mode never needs the SDK / credentials.
        from coinbase.rest import RESTClient

        self.client = RESTClient(api_key=api_key, api_secret=api_secret)

    def balances(self) -> dict[str, float]:
        """Map of currency code -> available balance (e.g. {'USD': 950.0, 'BTC': 0.01})."""
        out: dict[str, float] = {}
        accounts = self.client.get_accounts()
        for acct in getattr(accounts, "accounts", []) or []:
            currency = acct["currency"] if isinstance(acct, dict) else acct.currency
            avail = acct["available_balance"] if isinstance(acct, dict) else acct.available_balance
            value = avail["value"] if isinstance(avail, dict) else avail.value
            out[currency] = float(value)
        return out

    def market_buy(self, product_id: str, quote_size_usd: float) -> dict:
        """Spend `quote_size_usd` to buy. Returns a normalized fill summary."""
        order = self.client.market_order_buy(
            client_order_id=str(uuid.uuid4()),
            product_id=product_id,
            quote_size=f"{quote_size_usd:.2f}",
        )
        return self._summarize_order(order)

    def market_sell(self, product_id: str, base_size: float) -> dict:
        """Sell `base_size` units of the base currency."""
        order = self.client.market_order_sell(
            client_order_id=str(uuid.uuid4()),
            product_id=product_id,
            base_size=f"{base_size:.8f}",
        )
        return self._summarize_order(order)

    @staticmethod
    def _summarize_order(order) -> dict:
        d = order if isinstance(order, dict) else getattr(order, "__dict__", {})
        success = d.get("success", False)
        return {"success": bool(success), "raw": str(d)[:500]}
