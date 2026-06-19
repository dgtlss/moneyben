"""Risk enforcement + execution.

The LLM proposes; the Trader disposes. Every decision is clamped against the
config risk limits here, so a hallucinated 'BUY $1,000,000' becomes a safe,
bounded order (or a no-op). This is the only place orders are placed.
"""
from __future__ import annotations

import logging

from .config import Config
from .coinbase_client import TradeClient
from .llm import Decision
from .portfolio import Portfolio

log = logging.getLogger("trader")


class Trader:
    def __init__(self, cfg: Config, portfolio: Portfolio, trade_client: TradeClient | None):
        self.cfg = cfg
        self.pf = portfolio
        self.trade_client = trade_client  # None in paper mode

    def execute(self, decision: Decision, price: float) -> str:
        """Validate, clamp, and (maybe) place an order.

        Returns a short, plain-English phrase describing what happened (the
        caller prepends the coin name and price).
        """
        product = decision.product
        action = decision.action
        cfg = self.cfg

        if action == "HOLD":
            return "waiting — no clear opportunity right now"

        if decision.confidence < cfg.min_confidence:
            return "waiting — not confident enough to trade yet"

        if price <= 0:
            return "waiting — couldn't get a price"

        if action == "BUY":
            return self._buy(product, decision, price)
        if action == "SELL":
            return self._sell(product, decision, price)
        return "waiting — no action"

    def _buy(self, product: str, decision: Decision, price: float) -> str:
        cfg = self.cfg
        requested = decision.size_usd

        # Clamp to per-trade cap.
        spend = min(requested, cfg.max_trade_usd)

        # Respect the per-position cap.
        room = cfg.max_position_usd - self.pf.position_value(product, price)
        spend = min(spend, max(0.0, room))

        # Respect cash + reserve.
        spendable_cash = self.pf.cash - cfg.min_cash_reserve_usd
        spend = min(spend, max(0.0, spendable_cash))

        if spend < cfg.min_trade_usd:
            return "wanted to BUY, but a safety limit stopped it (your cash is untouched)"

        if self.trade_client:  # real mode
            result = self.trade_client.market_buy(product, spend)
            if not result["success"]:
                return f"BUY failed at the exchange — nothing happened ({result['raw']})"
        self.pf.apply_buy(product, spend, price)
        return f"BOUGHT ${spend:,.2f} worth ✅  ({decision.reason})"

    def _sell(self, product: str, decision: Decision, price: float) -> str:
        cfg = self.cfg
        held_base = self.pf.base_held(product)
        if held_base <= 0:
            return "wanted to SELL, but you don't own any right now"

        held_usd = held_base * price
        # How many USD of the position to sell, clamped to per-trade cap.
        sell_usd = min(decision.size_usd or held_usd, cfg.max_trade_usd, held_usd)
        if sell_usd < cfg.min_trade_usd and sell_usd < held_usd:
            return "wanted to SELL, but the amount was too small (a safety limit)"

        base_to_sell = min(sell_usd / price, held_base)

        if self.trade_client:  # real mode
            result = self.trade_client.market_sell(product, base_to_sell)
            if not result["success"]:
                return f"SELL failed at the exchange — nothing happened ({result['raw']})"
        self.pf.apply_sell(product, base_to_sell, price)
        return f"SOLD ${base_to_sell * price:,.2f} worth 💵  ({decision.reason})"

    def liquidate(self, product: str, price: float) -> str:
        """Sell the entire position back to cash, ignoring per-trade/confidence caps.

        Used on shutdown so nothing is left held while the bot is offline.
        Returns a short phrase, or "" if there was nothing to sell.
        """
        held_base = self.pf.base_held(product)
        if held_base <= 0:
            return ""
        if price <= 0:
            return "couldn't sell — no price available (still held)"

        if self.trade_client:  # real mode
            result = self.trade_client.market_sell(product, held_base)
            if not result["success"]:
                return f"SELL failed at the exchange — still held ({result['raw']})"
        proceeds = held_base * price
        self.pf.apply_sell(product, held_base, price)
        return f"SOLD everything — ${proceeds:,.2f} back to cash 💵"
