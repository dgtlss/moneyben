# moneyben

A Dockerized crypto trading bot. Every minute it pulls live market data from
Coinbase, asks an LLM (via [OpenRouter](https://openrouter.ai)) for a buy/sell/hold
decision per market, then executes within hard-coded risk limits.

**Defaults to paper trading** — it simulates trades against real prices and places
no real orders until you explicitly enable `REAL_TRADING=true`.

## How it works

```
 every INTERVAL_SECONDS:
   Coinbase public API ──► 1m candles + spot price
                            │
                            ▼
                     indicators (SMA/EMA/RSI/volatility/momentum)
                            │
        portfolio snapshot ─┤
                            ▼
                   OpenRouter LLM ──► {action, size_usd, confidence} per product
                            │
                            ▼
                   Trader: clamp to risk limits ──► paper ledger OR real order
                            │
                            ▼
                   persist /data/portfolio.json + log P&L
```

- **Market data is public** — paper mode needs *zero* Coinbase credentials.
- **One LLM call per cycle** for all products, to keep cost predictable.
- **The LLM never has final say.** `app/trader.py` clamps every decision against
  `MAX_POSITION_USD`, `MAX_TRADE_USD`, `MIN_CASH_RESERVE_USD`, etc. A bogus
  "BUY $1,000,000" becomes a safe bounded order or a no-op.

## Quick start (paper trading)

```bash
cp .env.example .env
# edit .env: set OPENROUTER_API_KEY (leave REAL_TRADING=false)

docker compose up --build
docker compose logs -f         # watch decisions roll in
```

The simulated ledger persists to `./data/portfolio.json`.

## Going live (real money)

> ⚠️ This places real market orders with real funds. Start with tiny limits.

1. Create a Coinbase **Advanced Trade / CDP API key** with trade permission.
2. In `.env`:
   ```
   REAL_TRADING=true
   COINBASE_API_KEY=organizations/.../apiKeys/...
   COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n"
   MAX_TRADE_USD=20
   MAX_POSITION_USD=50
   ```
3. `docker compose up --build -d`

In real mode the bot syncs cash/positions from your live Coinbase balances each
cycle; the local file is just an audit log of trades it placed.

## Configuration

All knobs are environment variables (see `.env.example`). Key ones:

| Var | Default | Meaning |
|-----|---------|---------|
| `REAL_TRADING` | `false` | Place real orders vs. simulate |
| `PRODUCTS` | `BTC-USD,ETH-USD,SOL-USD` | Markets to trade |
| `OPENROUTER_MODEL` | `anthropic/claude-haiku-4.5` | Any OpenRouter model id |
| `INTERVAL_SECONDS` | `60` | Cycle cadence (min 10) |
| `MAX_POSITION_USD` | `1000` | Cap on $ held per product |
| `MAX_TRADE_USD` | `250` | Cap on $ per single order |
| `MIN_CASH_RESERVE_USD` | `100` | Cash floor never spent below |
| `MIN_CONFIDENCE` | `0.6` | Ignore lower-confidence LLM actions |
| `PAPER_START_CASH` | `10000` | Starting paper balance |

## Running without Docker

```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-...
DATA_DIR=./data python -m app.main
```

## Disclaimer

This is experimental software for education and research. Crypto trading is
risky and you can lose money. An LLM is not a financial advisor. Run paper mode
for a long time before risking real funds, and use small limits. No warranty.
