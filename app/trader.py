"""Risk enforcement + Trading 212 order execution."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from .portfolio import Portfolio

log = logging.getLogger("trader")


class Trader:
    def __init__(self, cfg, portfolio: Portfolio, broker):
        self.cfg = cfg
        self.pf = portfolio
        self.broker = broker

    def execute(self, decision, price: float, price_as_of: datetime | None = None) -> str:
        product = decision.get("product", "")
        action = str(decision.get("action", "HOLD")).upper()
        confidence = float(decision.get("confidence", 0.0) or 0.0)
        reason = str(decision.get("reason", ""))
        requested = float(decision.get("size_usd", 0.0) or 0.0)

        if action == "HOLD":
            return "waiting — no clear opportunity right now"
        if confidence < self.cfg.min_confidence:
            return "waiting — not confident enough to trade yet"
        if price <= 0:
            return "waiting — couldn't get a usable price"
        if self._is_stale(price_as_of):
            return "waiting — price data is stale, so no order was sent"
        if action == "BUY":
            return self._buy(product, requested, price, reason)
        if action == "SELL":
            return self._sell(product, requested, price, reason)
        return "waiting — no action"

    def _is_stale(self, price_as_of: datetime | None) -> bool:
        if price_as_of is None:
            return False
        now = datetime.now(timezone.utc)
        return (now - price_as_of).total_seconds() > self.cfg.max_price_age_seconds

    def _buy(self, ticker: str, requested_usd: float, price: float, reason: str) -> str:
        spend = min(requested_usd, self.cfg.max_trade_usd)
        spend = min(spend, max(0.0, self.cfg.max_position_usd - self.pf.position_value(ticker, price)))
        spend = min(spend, max(0.0, self.pf.cash - self.cfg.min_cash_reserve_usd))
        if spend < self.cfg.min_trade_usd:
            return "wanted to BUY, but a safety limit stopped it"

        quantity = self._rounded_quantity(spend / price)
        if quantity <= 0:
            return "wanted to BUY, but the share quantity rounded to zero"

        if self.cfg.read_only:
            self.pf.record_order(
                ticker=ticker,
                side="BUY",
                quantity=quantity,
                requested_value=spend,
                price=price,
                status="READ_ONLY",
                reason=reason,
                order_id=None,
            )
            return f"READ-ONLY — would BUY about ${spend:,.2f} ({quantity:.4f} shares) ({reason})"

        result = self.broker.place_market_order(ticker, quantity, extended_hours=self.cfg.extended_hours)
        self.pf.record_order(
            ticker=ticker,
            side="BUY",
            quantity=quantity,
            requested_value=spend,
            price=price,
            status=result.status,
            reason=reason,
            order_id=result.id,
        )
        return self._describe_result("BUY", spend, quantity, result, reason)

    def _sell(self, ticker: str, requested_usd: float, price: float, reason: str) -> str:
        held_qty = self.pf.quantity_held(ticker)
        if held_qty <= 0:
            return "wanted to SELL, but you don't own any right now"

        held_value = held_qty * price
        sell_usd = min(requested_usd or held_value, self.cfg.max_trade_usd, held_value)
        if sell_usd < self.cfg.min_trade_usd and sell_usd < held_value:
            return "wanted to SELL, but the amount was too small"

        quantity = self._rounded_quantity(min(sell_usd / price, held_qty))
        if quantity <= 0:
            return "wanted to SELL, but the share quantity rounded to zero"

        if self.cfg.read_only:
            self.pf.record_order(
                ticker=ticker,
                side="SELL",
                quantity=-quantity,
                requested_value=sell_usd,
                price=price,
                status="READ_ONLY",
                reason=reason,
                order_id=None,
            )
            return f"READ-ONLY — would SELL about ${sell_usd:,.2f} ({quantity:.4f} shares) ({reason})"

        result = self.broker.place_market_order(ticker, -quantity, extended_hours=self.cfg.extended_hours)
        self.pf.record_order(
            ticker=ticker,
            side="SELL",
            quantity=-quantity,
            requested_value=sell_usd,
            price=price,
            status=result.status,
            reason=reason,
            order_id=result.id,
        )
        return self._describe_result("SELL", sell_usd, quantity, result, reason)

    def _rounded_quantity(self, quantity: float) -> float:
        precision = 10 ** self.cfg.quantity_precision
        return math.trunc(quantity * precision) / precision

    @staticmethod
    def _describe_result(action: str, usd_value: float, quantity: float, result, reason: str) -> str:
        status = (result.status or "").upper()
        if status in {"REJECTED", "CANCELLED"}:
            return f"{action} failed at the broker — nothing happened ({status})"
        if status in {"FILLED", "PARTIALLY_FILLED"}:
            return f"{action} order filled for about ${usd_value:,.2f} ({quantity:.4f} shares) ({reason})"
        return f"{action} order queued for about ${usd_value:,.2f} ({quantity:.4f} shares) ({reason})"
