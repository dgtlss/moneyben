"""Portfolio state + local audit persistence."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

from .trading212 import AccountSummary, Position

log = logging.getLogger("portfolio")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Portfolio:
    def __init__(self, path: str, start_cash: float = 0.0, quote_currency: str = "USD"):
        self.path = path
        self.quote_currency = quote_currency
        self.cash: float = start_cash
        self.cash_reserved: float = 0.0
        self.positions: dict[str, dict] = {}
        self.trades: list[dict] = []
        self.start_value: float | None = None
        self.total_value_usd: float = start_cash
        self._load(start_cash)

    def _load(self, start_cash: float) -> None:
        if not os.path.exists(self.path):
            self.save()
            return
        try:
            with open(self.path) as handle:
                data = json.load(handle)
            self.cash = float(data.get("cash", start_cash) or start_cash)
            self.cash_reserved = float(data.get("cash_reserved", 0.0) or 0.0)
            self.positions = data.get("positions", {})
            self.trades = data.get("trades", [])
            self.start_value = data.get("start_value")
            self.total_value_usd = float(data.get("total_value_usd", self.cash) or self.cash)
        except (OSError, json.JSONDecodeError, ValueError):
            log.info("  Couldn't read the saved portfolio file; starting fresh.")
            self.cash = start_cash
            self.cash_reserved = 0.0
            self.positions = {}
            self.trades = []
            self.start_value = None
            self.total_value_usd = start_cash

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = {
            "updated": _now(),
            "start_value": self.start_value,
            "cash": round(self.cash, 2),
            "cash_reserved": round(self.cash_reserved, 2),
            "total_value_usd": round(self.total_value_usd, 2),
            "positions": self.positions,
            "trades": self.trades[-1000:],
        }
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(payload, handle, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def ensure_baseline(self, total: float) -> None:
        if self.start_value is None:
            self.start_value = total

    def quantity_held(self, ticker: str) -> float:
        return float(self.positions.get(ticker, {}).get("quantity", 0.0) or 0.0)

    def position_value(self, ticker: str, price: float | None = None) -> float:
        position = self.positions.get(ticker, {})
        if price is None:
            return float(position.get("value_usd", 0.0) or 0.0)
        return self.quantity_held(ticker) * price

    def snapshot(self) -> dict:
        positions = {
            ticker: {
                "quantity": round(float(position.get("quantity", 0.0) or 0.0), 8),
                "avg_price": round(float(position.get("avg_price", 0.0) or 0.0), 6),
                "current_price": round(float(position.get("current_price", 0.0) or 0.0), 6),
                "value_usd": round(float(position.get("value_usd", 0.0) or 0.0), 2),
                "name": position.get("name", ""),
                "currency": position.get("currency", self.quote_currency),
            }
            for ticker, position in self.positions.items()
            if float(position.get("quantity", 0.0) or 0.0) > 0
        }
        return {
            "cash_usd": round(self.cash, 2),
            "cash_reserved_usd": round(self.cash_reserved, 2),
            "positions": positions,
            "total_value_usd": round(self.total_value_usd, 2),
        }

    def sync_from_broker(self, summary: AccountSummary, positions: dict[str, Position]) -> None:
        self.cash = summary.cash_available
        self.cash_reserved = summary.cash_reserved
        self.total_value_usd = summary.total_value
        self.positions = {
            ticker: {
                "quantity": position.quantity,
                "avg_price": position.average_price_paid,
                "current_price": position.current_price,
                "value_usd": position.current_value,
                "name": position.name,
                "currency": position.currency,
            }
            for ticker, position in positions.items()
            if position.quantity > 0
        }

    def record_order(
        self,
        *,
        ticker: str,
        side: str,
        quantity: float,
        requested_value: float,
        price: float,
        status: str,
        reason: str,
        order_id: int | None = None,
    ) -> None:
        self.trades.append(
            {
                "ts": _now(),
                "ticker": ticker,
                "side": side,
                "quantity": round(quantity, 8),
                "requested_value": round(requested_value, 2),
                "price": round(price, 6),
                "status": status,
                "reason": reason,
                "order_id": order_id,
            }
        )
