"""Portfolio state + persistence.

In paper mode this is the source of truth (a JSON file under DATA_DIR).
In real mode, cash/positions are re-synced from Coinbase each cycle, but the
trade log is still appended here for an auditable history.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

log = logging.getLogger("portfolio")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Portfolio:
    def __init__(self, path: str, start_cash: float, quote_currency: str = "USD"):
        self.path = path
        self.quote_currency = quote_currency
        self.cash: float = start_cash
        self.positions: dict[str, dict] = {}  # product -> {"base": float, "avg_price": float}
        self.trades: list[dict] = []
        self.start_value: float | None = None  # baseline for profit/loss; set on first cycle
        self._load(start_cash)

    # --- persistence ---
    def _load(self, start_cash: float) -> None:
        if not os.path.exists(self.path):
            log.info("  Starting a brand-new account with %s.", f"${start_cash:,.2f}")
            self.save()
            return
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.cash = data.get("cash", start_cash)
            self.positions = data.get("positions", {})
            self.trades = data.get("trades", [])
            self.start_value = data.get("start_value")
            owned = sum(1 for p in self.positions.values() if p.get("base", 0) > 0)
            log.info("  Picking up where you left off: %s in cash, %d coin(s) held, %d past trades.",
                     f"${self.cash:,.2f}", owned, len(self.trades))
        except (json.JSONDecodeError, OSError):
            log.info("  Couldn't read the saved account file; starting fresh with %s.", f"${start_cash:,.2f}")
            self.cash = start_cash

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = {
            "updated": _now(),
            "start_value": self.start_value,
            "cash": round(self.cash, 2),
            "positions": self.positions,
            "trades": self.trades[-1000:],  # keep the file bounded
        }
        # Atomic write so a crash mid-write can't corrupt the ledger.
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def ensure_baseline(self, total: float) -> None:
        """Remember the starting value the first time we know it (for P&L)."""
        if self.start_value is None:
            self.start_value = total

    # --- queries ---
    def base_held(self, product: str) -> float:
        return self.positions.get(product, {}).get("base", 0.0)

    def position_value(self, product: str, price: float) -> float:
        return self.base_held(product) * price

    def total_value(self, prices: dict[str, float]) -> float:
        total = self.cash
        for product, pos in self.positions.items():
            total += pos.get("base", 0.0) * prices.get(product, pos.get("avg_price", 0.0))
        return total

    def snapshot(self, prices: dict[str, float]) -> dict:
        return {
            "cash_usd": round(self.cash, 2),
            "positions": {
                p: {
                    "base": round(pos.get("base", 0.0), 8),
                    "avg_price": round(pos.get("avg_price", 0.0), 6),
                    "value_usd": round(pos.get("base", 0.0) * prices.get(p, pos.get("avg_price", 0.0)), 2),
                }
                for p, pos in self.positions.items()
                if pos.get("base", 0.0) > 0
            },
            "total_value_usd": round(self.total_value(prices), 2),
        }

    # --- mutations (paper mode) ---
    def apply_buy(self, product: str, quote_usd: float, price: float) -> None:
        base = quote_usd / price
        pos = self.positions.setdefault(product, {"base": 0.0, "avg_price": 0.0})
        old_base, old_avg = pos["base"], pos["avg_price"]
        new_base = old_base + base
        pos["avg_price"] = ((old_base * old_avg) + quote_usd) / new_base if new_base else 0.0
        pos["base"] = new_base
        self.cash -= quote_usd
        self._log_trade(product, "BUY", quote_usd, base, price)

    def apply_sell(self, product: str, base: float, price: float) -> None:
        pos = self.positions.setdefault(product, {"base": 0.0, "avg_price": 0.0})
        base = min(base, pos["base"])
        proceeds = base * price
        pos["base"] -= base
        if pos["base"] <= 1e-12:
            pos["base"] = 0.0
        self.cash += proceeds
        self._log_trade(product, "SELL", proceeds, base, price)

    def _log_trade(self, product: str, action: str, quote_usd: float, base: float, price: float) -> None:
        self.trades.append({
            "ts": _now(),
            "product": product,
            "action": action,
            "usd": round(quote_usd, 2),
            "base": round(base, 8),
            "price": round(price, 6),
        })

    # --- real mode sync ---
    def sync_from_balances(self, balances: dict[str, float], prices: dict[str, float], products: list[str]) -> None:
        """Overwrite cash/positions from live Coinbase balances (real mode)."""
        self.cash = balances.get(self.quote_currency, 0.0)
        for product in products:
            base_ccy = product.split("-")[0]
            held = balances.get(base_ccy, 0.0)
            pos = self.positions.setdefault(product, {"base": 0.0, "avg_price": prices.get(product, 0.0)})
            pos["base"] = held
            if not pos.get("avg_price"):
                pos["avg_price"] = prices.get(product, 0.0)
