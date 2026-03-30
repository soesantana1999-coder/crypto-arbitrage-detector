# Crypto Arbitrage Detector

Real-time cross-exchange cryptocurrency arbitrage opportunity detector.

Monitors price spreads between **Binance**, **Kraken**, and **KuCoin** across 10 trading pairs, displaying opportunities on a live web dashboard.

## What it does

- Connects to 3 major exchanges simultaneously via public APIs
- Scans 10 common trading pairs every ~2 seconds
- Calculates cross-exchange spreads in real-time
- Displays opportunities on a live WebSocket dashboard
- Alerts when spreads exceed configurable thresholds
- 100% free — uses only public API endpoints

## How it works

```
Binance ──┐
Kraken  ──┼── ccxt ── Spread Calculator ── FastAPI ── WebSocket ── Dashboard
KuCoin  ──┘
```

## Live Demo

**https://crypto-arbitrage-detector.onrender.com**

## Quick Start

```bash
# Clone
git clone https://github.com/santtana/crypto-arbitrage-detector.git
cd crypto-arbitrage-detector

# Install
pip install -r requirements.txt

# Run
uvicorn backend:app --host 0.0.0.0 --port 8080

# Open http://localhost:8080
```

## Docker

```bash
docker build -t arbitrage-detector .
docker run -p 8080:8080 arbitrage-detector
```

## Deploy to Fly.io

```bash
fly launch
fly deploy
```

## Monitored Pairs

BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT, DOGE/USDT, ADA/USDT, LINK/USDT, AVAX/USDT, DOT/USDT, LTC/USDT

## Tech Stack

- **Backend:** Python, FastAPI, WebSocket, ccxt
- **Frontend:** Vanilla HTML/JS (no framework)
- **Deploy:** Fly.io (free tier)
- **Data:** Public exchange APIs (no auth required)

## Limitations (honest)

- Detection only — does not execute trades
- Spreads may disappear before manual execution (latency)
- Real arbitrage requires funds on multiple exchanges + withdrawal fees
- Free exchange APIs have rate limits
- Not financial advice

## Built by

Santtana + Sil — 72-hour challenge. One person + AI, zero team.

## License

MIT
