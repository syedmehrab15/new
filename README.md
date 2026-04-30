# FX Trading Agent

A production-grade multi-strategy FX analysis agent powered by Claude AI and Twelve Data.

## Architecture

```
app.py          — Flask HTTP API + background scheduler
agent.py        — Orchestrator: runs Claude strategies, aggregates signals
tools.py        — Live market data via Twelve Data API
models.py       — Pydantic schemas (TradeBrief, Signal, TradeSetup, KeyLevels)
database.py     — SQLite persistence (WAL mode, thread-safe)
config.py       — Centralised config via environment variables
prompts.py      — System prompt + default pair list
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export TWELVE_DATA_API_KEY=your_key_here
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...   # optional
export SCAN_INTERVAL_SECONDS=3600                      # default: 1 hour
export ATR_STOP_MULTIPLIER=1.5                         # default
export ATR_TARGET_MULTIPLIER=3.0                       # default (1:2 RR)
```

### 3. Run locally
```bash
# One-shot scan
python agent.py

# Full server with scheduler
python app.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| GET | `/briefs` | Latest 20 briefs (all pairs) |
| GET | `/briefs/EUR-USD` | Last 10 briefs for EUR/USD |

## Deploy to Render

1. Push to a **private** GitHub repository
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set environment variables in the Render dashboard
4. Render auto-detects the `Procfile` and runs gunicorn

## Strategy Details

| Strategy | Weight | Logic |
|----------|--------|-------|
| TrendFollowing_EMA | 60% | Uses EMA 50 / EMA 200 crossover + price position |
| MeanReversion_RSI  | 40% | RSI overbought/oversold mean-reversion signals |

Signals are aggregated by a confidence-weighted consensus:
- Each signal is weighted by `strategy_weight × (confidence / 100)`
- Normalised score < 0.2 → Neutral (no trade)

## Risk Management

- Stop-loss and take-profit are ATR-based (not fixed-pip)
- Default: SL = 1.5× ATR, TP = 3.0× ATR → 1:2 RR
- Override via `ATR_STOP_MULTIPLIER` and `ATR_TARGET_MULTIPLIER` env vars

## Security

- Never commit API keys to Git
- Always use a **private** repository
- Keys are read from environment variables only
