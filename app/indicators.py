"""Pure-Python technical indicators.

Kept dependency-free (no numpy/pandas) so the Docker image stays small.
Every function takes a list of closing prices oldest->newest and returns a
single most-recent value, or None when there isn't enough data.
"""
from __future__ import annotations


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    # Seed with the SMA of the first `period` values, then walk forward.
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(-period, 0):
        change = values[i] - values[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def pct_change(values: list[float], lookback: int) -> float | None:
    if len(values) <= lookback or values[-1 - lookback] == 0:
        return None
    return (values[-1] / values[-1 - lookback] - 1) * 100


def volatility(values: list[float], period: int = 30) -> float | None:
    """Std-dev of minute-to-minute returns over `period`, as a percentage."""
    if len(values) < period + 1:
        return None
    rets = []
    for i in range(-period, 0):
        if values[i - 1] == 0:
            continue
        rets.append(values[i] / values[i - 1] - 1)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return (var ** 0.5) * 100


def summarize(closes: list[float], volumes: list[float] | None = None) -> dict:
    """Compact indicator bundle handed to the LLM (rounded to keep tokens low)."""

    def r(x, n=2):
        return round(x, n) if isinstance(x, (int, float)) else x

    last = closes[-1] if closes else None
    return {
        "price": r(last, 6),
        "sma_10": r(sma(closes, 10), 6),
        "sma_30": r(sma(closes, 30), 6),
        "ema_12": r(ema(closes, 12), 6),
        "ema_26": r(ema(closes, 26), 6),
        "rsi_14": r(rsi(closes, 14)),
        "pct_change_5m": r(pct_change(closes, 5)),
        "pct_change_15m": r(pct_change(closes, 15)),
        "pct_change_60m": r(pct_change(closes, 60)),
        "volatility_30m_pct": r(volatility(closes, 30), 3),
        "session_high": r(max(closes), 6) if closes else None,
        "session_low": r(min(closes), 6) if closes else None,
    }
