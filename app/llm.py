"""OpenRouter decision engine.

Sends a compact market + portfolio snapshot and asks for one structured
trading decision per product. We never trust the model blindly — the trader
re-validates every decision against the risk limits in config.
"""
from __future__ import annotations

import json
import logging

import requests

log = logging.getLogger("llm")

SYSTEM_PROMPT = """You are a disciplined short-term crypto trading assistant.
Every minute you receive technical indicators for several products and the
current portfolio. Decide an action for EACH product: BUY, SELL, or HOLD.

Guidelines:
- Prefer HOLD. Only BUY or SELL when indicators give a clear edge.
- Buy weakness with momentum turning up (e.g. RSI recovering from oversold,
  price reclaiming short EMAs). Sell into strength or to cut losers.
- size_usd is how much USD to move on this action. The system enforces hard
  caps, so request what you think is right and it will be clamped.
- confidence is 0.0-1.0; low-confidence actions will be ignored by the system.
- Be concise in `reason` (one sentence).

Respond with ONLY a JSON object of this exact shape, no prose, no markdown:
{"decisions": [
  {"product": "BTC-USD", "action": "HOLD", "size_usd": 0, "confidence": 0.0, "reason": "..."}
]}
Include exactly one entry per product you were given."""


class Decision(dict):
    """Thin typed accessor over the raw decision dict."""

    @property
    def product(self) -> str:
        return self.get("product", "")

    @property
    def action(self) -> str:
        return str(self.get("action", "HOLD")).upper()

    @property
    def size_usd(self) -> float:
        try:
            return float(self.get("size_usd", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def confidence(self) -> float:
        try:
            return float(self.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def reason(self) -> str:
        return str(self.get("reason", ""))


class LLMClient:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def decide(self, market: dict, portfolio: dict) -> list[Decision]:
        user_payload = {
            "portfolio": portfolio,
            "market": market,
            "instructions": "One decision per product. Default to HOLD.",
        }
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
        }
        resp = self.session.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/moneyben",
                "X-Title": "moneyben",
            },
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return self._parse(content)

    @staticmethod
    def _parse(content: str) -> list[Decision]:
        content = content.strip()
        # Strip accidental ```json fences.
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            log.warning("LLM returned non-JSON; treating as all-HOLD. Raw: %s", content[:300])
            return []
        decisions = data.get("decisions", data if isinstance(data, list) else [])
        return [Decision(d) for d in decisions if isinstance(d, dict)]
