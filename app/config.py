"""Configuration loaded from environment variables.

All knobs live here so the rest of the app never reads os.environ directly.
Values are read once at startup into a frozen dataclass.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load a local .env if present (no-op in Docker where env is injected directly).
load_dotenv()


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default
    return [p.strip().upper() for p in raw.split(",") if p.strip()]


@dataclass(frozen=True)
class Config:
    # --- What to trade ---
    products: list[str] = field(default_factory=lambda: _list("PRODUCTS", ["BTC-USD", "ETH-USD", "SOL-USD"]))
    quote_currency: str = os.environ.get("QUOTE_CURRENCY", "USD")

    # --- Cadence ---
    interval_seconds: int = _int("INTERVAL_SECONDS", 60)
    candle_lookback: int = _int("CANDLE_LOOKBACK", 120)  # minutes of 1m candles to fetch

    # --- Risk controls (enforced in code, independent of the LLM) ---
    real_trading: bool = _bool("REAL_TRADING", False)
    paper_start_cash: float = _float("PAPER_START_CASH", 10_000.0)
    max_position_usd: float = _float("MAX_POSITION_USD", 1_000.0)   # cap on $ held in any one product
    max_trade_usd: float = _float("MAX_TRADE_USD", 250.0)           # cap on $ moved in a single order
    min_trade_usd: float = _float("MIN_TRADE_USD", 10.0)            # skip dust trades
    min_cash_reserve_usd: float = _float("MIN_CASH_RESERVE_USD", 100.0)  # never spend below this
    min_confidence: float = _float("MIN_CONFIDENCE", 0.6)          # ignore low-conviction LLM calls
    liquidate_on_shutdown: bool = _bool("LIQUIDATE_ON_SHUTDOWN", True)  # sell all to cash when stopping

    # --- Coinbase (only required when real_trading is True) ---
    # The EC private key is often pasted with literal "\n"; normalize to real
    # newlines so the SDK can parse the PEM regardless of how it was stored.
    coinbase_api_key: str = os.environ.get("COINBASE_API_KEY", "")
    coinbase_api_secret: str = os.environ.get("COINBASE_API_SECRET", "").replace("\\n", "\n")

    # --- OpenRouter ---
    openrouter_api_key: str = os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")
    openrouter_base_url: str = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # --- Persistence ---
    data_dir: str = os.environ.get("DATA_DIR", "/data")

    def validate(self) -> list[str]:
        """Return a list of fatal configuration errors (empty == OK)."""
        errors: list[str] = []
        if not self.products:
            errors.append("PRODUCTS is empty.")
        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY is required.")
        if self.real_trading and not (self.coinbase_api_key and self.coinbase_api_secret):
            errors.append("REAL_TRADING=true but COINBASE_API_KEY / COINBASE_API_SECRET are missing.")
        if self.interval_seconds < 10:
            errors.append("INTERVAL_SECONDS must be >= 10 to respect rate limits.")
        return errors
