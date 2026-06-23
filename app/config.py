"""Configuration loaded from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in local dev shells
    def load_dotenv() -> None:
        return None


load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _list_upper(name: str, default: list[str]) -> list[str]:
    return [item.upper() for item in _list(name, default)]


def _mapping(name: str) -> dict[str, str]:
    raw = os.environ.get(name, "")
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        if ":" not in pair:
            continue
        left, right = pair.split(":", 1)
        if left.strip() and right.strip():
            mapping[left.strip()] = right.strip()
    return mapping


def _t212_credential(kind: str) -> str:
    env = os.environ.get("T212_ENV", "demo").strip().lower()
    if env == "demo":
        return os.environ.get(f"T212_DEMO_{kind}", "") or os.environ.get(f"T212_{kind}", "")
    if env == "live":
        return os.environ.get(f"T212_LIVE_{kind}", "") or os.environ.get(f"T212_{kind}", "")
    return os.environ.get(f"T212_{kind}", "")


def _default_market_data_base_url() -> str:
    provider = os.environ.get("MARKET_DATA_PROVIDER", "alpha_vantage").strip().lower()
    if provider == "twelve_data":
        return "https://api.twelvedata.com"
    return "https://www.alphavantage.co/query"


@dataclass(frozen=True)
class Config:
    tickers: list[str] = field(default_factory=lambda: _list("TICKERS", ["AAPL_US_EQ", "MSFT_US_EQ", "SPY_US_EQ"]))
    allowed_instrument_types: list[str] = field(default_factory=lambda: _list_upper("ALLOWED_INSTRUMENT_TYPES", ["STOCK", "ETF"]))
    quote_currency: str = field(default_factory=lambda: os.environ.get("QUOTE_CURRENCY", "USD").upper())

    interval_seconds: int = field(default_factory=lambda: _int("INTERVAL_SECONDS", 60))
    candle_lookback: int = field(default_factory=lambda: _int("CANDLE_LOOKBACK", 120))
    candle_interval: str = field(default_factory=lambda: os.environ.get("CANDLE_INTERVAL", "1min"))
    max_price_age_seconds: int = field(default_factory=lambda: _int("MAX_PRICE_AGE_SECONDS", 300))

    max_position_usd: float = field(default_factory=lambda: _float("MAX_POSITION_USD", 1_000.0))
    max_trade_usd: float = field(default_factory=lambda: _float("MAX_TRADE_USD", 250.0))
    min_trade_usd: float = field(default_factory=lambda: _float("MIN_TRADE_USD", 10.0))
    min_cash_reserve_usd: float = field(default_factory=lambda: _float("MIN_CASH_RESERVE_USD", 100.0))
    min_confidence: float = field(default_factory=lambda: _float("MIN_CONFIDENCE", 0.6))
    read_only: bool = field(default_factory=lambda: _bool("READ_ONLY", False))
    liquidate_on_shutdown: bool = field(default_factory=lambda: _bool("LIQUIDATE_ON_SHUTDOWN", False))
    extended_hours: bool = field(default_factory=lambda: _bool("EXTENDED_HOURS", False))
    quantity_precision: int = field(default_factory=lambda: _int("QUANTITY_PRECISION", 6))

    t212_env: str = field(default_factory=lambda: os.environ.get("T212_ENV", "demo").strip().lower())
    t212_api_key: str = field(default_factory=lambda: _t212_credential("API_KEY"))
    t212_api_secret: str = field(default_factory=lambda: _t212_credential("API_SECRET"))

    market_data_provider: str = field(default_factory=lambda: os.environ.get("MARKET_DATA_PROVIDER", "alpha_vantage").strip().lower())
    market_data_api_key: str = field(default_factory=lambda: os.environ.get("MARKET_DATA_API_KEY", ""))
    market_data_base_url: str = field(default_factory=lambda: os.environ.get("MARKET_DATA_BASE_URL", _default_market_data_base_url()).rstrip("/"))
    market_data_symbols: dict[str, str] = field(default_factory=lambda: _mapping("MARKET_DATA_SYMBOLS"))

    openrouter_api_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: os.environ.get("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5"))
    openrouter_base_url: str = field(default_factory=lambda: os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))

    data_dir: str = field(default_factory=lambda: os.environ.get("DATA_DIR", "/data"))

    def market_symbol_for(self, ticker: str) -> str:
        if ticker in self.market_data_symbols:
            return self.market_data_symbols[ticker]
        return ticker.split("_", 1)[0]

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.tickers:
            errors.append("TICKERS is empty.")
        if self.t212_env not in {"demo", "live"}:
            errors.append("T212_ENV must be either 'demo' or 'live'.")
        if not (self.t212_api_key and self.t212_api_secret):
            errors.append("T212_API_KEY and T212_API_SECRET are required.")
        if self.market_data_provider not in {"alpha_vantage", "twelve_data"}:
            errors.append("MARKET_DATA_PROVIDER must be 'alpha_vantage' or 'twelve_data'.")
        if self.market_data_provider in {"alpha_vantage", "twelve_data"} and not self.market_data_api_key:
            errors.append(f"MARKET_DATA_API_KEY is required for MARKET_DATA_PROVIDER={self.market_data_provider}.")
        if not self.openrouter_api_key:
            errors.append("OPENROUTER_API_KEY is required.")
        if self.interval_seconds < 10:
            errors.append("INTERVAL_SECONDS must be >= 10 to respect rate limits.")
        return errors
