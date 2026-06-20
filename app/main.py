"""Entry point for the Trading 212 stock/ETF bot."""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

from .config import Config
from .indicators import summarize
from .llm import LLMClient
from .market_data import AlphaVantageMarketData
from .portfolio import Portfolio
from .schedules import instrument_is_tradable
from .trader import Trader
from .trading212 import Trading212Broker

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(message)s",
)
log = logging.getLogger("moneyben")

_running = True


def fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _stop(_signum, _frame):
    global _running
    log.info("\nStopping after this round.")
    _running = False


def validate_instruments(cfg: Config, instruments: dict) -> list[str]:
    errors: list[str] = []
    allowed = set(cfg.allowed_instrument_types)
    for ticker in cfg.tickers:
        instrument = instruments.get(ticker)
        if instrument is None:
            errors.append(f"Configured ticker {ticker} is not available in Trading 212 metadata.")
            continue
        if instrument.instrument_type not in allowed:
            errors.append(
                f"{ticker} is type {instrument.instrument_type}, which is outside ALLOWED_INSTRUMENT_TYPES."
            )
    return errors


def gather_market(cfg, market_data, open_tickers: list[str]) -> tuple[dict, dict[str, tuple[float, datetime | None]]]:
    market: dict = {}
    prices: dict[str, tuple[float, datetime | None]] = {}
    for ticker in open_tickers:
        candles = market_data.candles(ticker, cfg.candle_lookback)
        if not candles:
            continue
        closes = [float(candle["close"]) for candle in candles]
        price, price_as_of = market_data.price(ticker)
        spot = price or closes[-1]
        summary = summarize(closes)
        summary["spot"] = round(spot, 6)
        market[ticker] = summary
        prices[ticker] = (spot, price_as_of)
    return market, prices


def run_cycle(cfg, broker, market_data, llm, pf, trader, instruments, schedules, now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)

    summary = broker.account_summary()
    positions = broker.positions()
    pf.sync_from_broker(summary, positions)
    pf.ensure_baseline(summary.total_value)

    open_tickers = [
        ticker
        for ticker in cfg.tickers
        if instrument_is_tradable(ticker, instruments, schedules, now, cfg.extended_hours)
    ]
    if not open_tickers:
        log.info("  All configured markets are closed right now. Standing by.")
        pf.save()
        return

    market, prices = gather_market(cfg, market_data, open_tickers)
    if not market:
        log.info("  Couldn't get enough market data right now. Trying again next round.")
        pf.save()
        return

    decisions = llm.decide(market, pf.snapshot())
    by_ticker = {decision.get("product", ""): decision for decision in decisions}

    for ticker in open_tickers:
        if ticker not in prices:
            continue
        decision = by_ticker.get(ticker, {"product": ticker, "action": "HOLD", "size_usd": 0, "confidence": 0, "reason": ""})
        price, price_as_of = prices[ticker]
        outcome = trader.execute(decision, price=price, price_as_of=price_as_of)
        log.info("  %-12s %s", ticker, outcome)

    pf.save()


def main() -> int:
    cfg = Config()
    errors = cfg.validate()
    if errors:
        for error in errors:
            log.error("CONFIG: %s", error)
        return 1

    broker = Trading212Broker(cfg.t212_env, cfg.t212_api_key, cfg.t212_api_secret)
    instruments = broker.instruments()
    schedules = broker.exchanges()

    instrument_errors = validate_instruments(cfg, instruments)
    if instrument_errors:
        for error in instrument_errors:
            log.error("CONFIG: %s", error)
        return 1

    market_data = AlphaVantageMarketData(cfg)
    llm = LLMClient(cfg.openrouter_api_key, cfg.openrouter_model, cfg.openrouter_base_url)
    portfolio = Portfolio(os.path.join(cfg.data_dir, "portfolio.json"), quote_currency=cfg.quote_currency)
    trader = Trader(cfg, portfolio, broker)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info("============================================================")
    log.info("  moneyben — Trading 212 stock/ETF trader")
    log.info("============================================================")
    log.info("  Environment:   %s", cfg.t212_env.upper())
    log.info("  Read-only:     %s", "ON — no orders will be sent" if cfg.read_only else "OFF — broker orders enabled")
    log.info("  Watching:      %s", ", ".join(cfg.tickers))
    log.info("  Checks every:  %d seconds", cfg.interval_seconds)
    log.info("  Safety rules:  trades at most %s at a time", fmt_money(cfg.max_trade_usd))
    log.info("                 holds at most %s per ticker", fmt_money(cfg.max_position_usd))
    log.info("                 keeps at least %s in cash", fmt_money(cfg.min_cash_reserve_usd))
    log.info("============================================================")

    while _running:
        started = time.time()
        try:
            run_cycle(cfg, broker, market_data, llm, portfolio, trader, instruments, schedules)
        except Exception as exc:  # pragma: no cover - defensive runtime logging
            log.exception("Unexpected error in cycle: %s", exc)
        elapsed = time.time() - started
        sleep_for = max(0.0, cfg.interval_seconds - elapsed)
        slept = 0.0
        while _running and slept < sleep_for:
            time.sleep(min(1.0, sleep_for - slept))
            slept += 1.0

    return 0


if __name__ == "__main__":
    sys.exit(main())
