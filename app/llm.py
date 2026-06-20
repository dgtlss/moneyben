"""OpenRouter decision engine."""
from __future__ import annotations

import json
import logging

from .http import SimpleSession

log = logging.getLogger("llm")

SYSTEM_PROMPT = """You are a disciplined short-term stock and ETF trading assistant.
Each cycle you receive technical indicators for several Trading 212 instruments
and the current portfolio snapshot. Decide an action for EACH ticker: BUY,
SELL, or HOLD.

Guidelines:
- Prefer HOLD. Only BUY or SELL when indicators give a clear edge.
- size_usd is how much account-currency value to move on this action. The
  system enforces hard caps and converts value into share quantity safely.
- confidence is 0.0-1.0; low-confidence actions will be ignored by the system.
- Be concise in `reason` (one sentence).

Respond with ONLY a JSON object of this exact shape, no prose, no markdown:
{"decisions": [
  {"product": "AAPL_US_EQ", "action": "HOLD", "size_usd": 0, "confidence": 0.0, "reason": "..."}
]}
Include exactly one entry per ticker you were given."""


class Decision(dict):
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
        self.session = SimpleSession()

    def decide(self, market: dict, portfolio: dict) -> list[Decision]:
        body = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "portfolio": portfolio,
                            "market": market,
                            "instructions": "One decision per ticker. Default to HOLD.",
                        }
                    ),
                },
            ],
        }
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/moneyben",
                "X-Title": "moneyben",
            }
        )
        response = self.session.post(f"{self.base_url}/chat/completions", json=body, timeout=60)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self._parse(content)

    @staticmethod
    def _parse(content: str) -> list[Decision]:
        content = content.strip()
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
        return [Decision(item) for item in decisions if isinstance(item, dict)]
