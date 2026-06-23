# moneyben

A Dockerized Trading 212 stock/ETF bot. Each cycle it syncs your Trading 212
account, pulls watchlist market data from a configurable provider such as Twelve Data, asks an LLM (via
[OpenRouter](https://openrouter.ai)) for a buy/sell/hold decision per ticker,
and then clamps every trade through hard risk limits before sending a broker
order.

**Defaults to Trading 212 demo mode** via `T212_ENV=demo`, so the same broker
flow can be exercised without touching live funds.
Set `READ_ONLY=true` if you want full decision-making and logging without
placing even demo orders.

## How it works

```text
 every INTERVAL_SECONDS:
   Trading 212 demo/live ──► account summary + positions + instrument metadata
   Twelve Data / provider ──► candles + latest price
                              │
                              ▼
                       indicators (SMA/EMA/RSI/volatility/momentum)
                              │
          portfolio snapshot ─┤
                              ▼
                     OpenRouter LLM ──► {action, size_usd, confidence} per ticker
                              │
                              ▼
                     Trader: clamp risk -> convert USD to share quantity
                              │
                              ▼
                     Trading 212 market order + local audit log
```

- Trading is **market-hours aware** using Trading 212 exchange metadata.
- The LLM gets **one batched call per cycle** for all configured tickers.
- The LLM never has final say. `app/trader.py` enforces `MAX_POSITION_USD`,
  `MAX_TRADE_USD`, `MIN_CASH_RESERVE_USD`, confidence thresholds, and stale-price
  checks before any order is sent.

## Quick start

```bash
cp .env.example .env
# edit .env with your OpenRouter, Trading 212, and market-data keys
# set READ_ONLY=true for the safest first run

docker compose up --build
docker compose logs -f
```

The local file at `./data/portfolio.json` is an audit/cache artifact. Trading
212 demo/live remains the source of truth for balances and positions.

## Going live

> This places real market orders with real funds. Start tiny and stay in demo
> until you trust the behavior.

1. Create a Trading 212 API key/secret for an eligible `Invest` or `Stocks ISA`
   account.
2. Update `.env`:
   ```bash
   T212_ENV=live
   READ_ONLY=false
   MAX_TRADE_USD=20
   MAX_POSITION_USD=50
   ```
3. Restart the container:
   ```bash
   docker compose up --build -d
   ```

## Configuration

Key environment variables:

| Var | Default | Meaning |
|-----|---------|---------|
| `T212_ENV` | `demo` | Trading 212 environment: `demo` or `live` |
| `TICKERS` | `AAPL_US_EQ,MSFT_US_EQ,SPY_US_EQ` | Trading 212 instruments to watch/trade |
| `READ_ONLY` | `false` | Run the full strategy loop without placing broker orders |
| `MARKET_DATA_PROVIDER` | `twelve_data` | External market data backend |
| `INTERVAL_SECONDS` | `60` | Cycle cadence (minimum 10 seconds) |
| `MAX_POSITION_USD` | `1000` | Cap on dollar exposure per ticker |
| `MAX_TRADE_USD` | `250` | Cap on dollar value per order |
| `MIN_CASH_RESERVE_USD` | `100` | Cash floor never spent below |
| `MIN_CONFIDENCE` | `0.6` | Ignore lower-confidence LLM actions |
| `EXTENDED_HOURS` | `false` | Allow pre/post-market orders when available |
| `LIQUIDATE_ON_SHUTDOWN` | `false` | Reserved for future flatten-on-stop behavior |

## Running without Docker

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...
export T212_DEMO_API_KEY=...
export T212_DEMO_API_SECRET=...
export MARKET_DATA_API_KEY=...
export READ_ONLY=true
DATA_DIR=./data python3 -m app.main
```

## Notes

- Trading 212’s public API covers account summary, instruments, exchanges,
  positions, and orders.
- This repo uses a separate market-data provider because the published Trading
  212 docs do not expose the candle pipeline this bot uses for indicators.
- Some non-US Trading 212 tickers may need `MARKET_DATA_SYMBOLS` overrides to
  match the provider's symbol naming, for example `HASl_EQ:HAS.LON`.

## Disclaimer

This is experimental software for education and research. Trading stocks and
ETFs is risky and you can lose money. An LLM is not a financial advisor. Run in
demo mode for a long time before risking real funds, and use small limits. No
warranty.
