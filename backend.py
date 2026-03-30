"""Crypto Arbitrage Detector — Backend FastAPI + WebSocket.

Conecta Binance, Kraken, KuCoin via ccxt WebSocket.
Detecta spreads entre exchanges en tiempo real.
Sirve dashboard web + alertas Telegram.
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path

import ccxt.async_support as ccxt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Crypto Arbitrage Detector")

# --- Config ---
EXCHANGES = {
    "binance": ccxt.binance({"enableRateLimit": True}),
    "kraken": ccxt.kraken({"enableRateLimit": True}),
    "kucoin": ccxt.kucoin({"enableRateLimit": True}),
}

# Pares comunes entre los 3 exchanges
PAIRS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT",
    "DOGE/USDT", "ADA/USDT", "LINK/USDT", "AVAX/USDT",
    "DOT/USDT", "LTC/USDT",
]

# Umbral de alerta (% spread)
ALERT_THRESHOLD = 0.5  # 0.5% spread = oportunidad

# Estado global
prices = {}  # {pair: {exchange: {bid, ask, timestamp}}}
opportunities = []  # Lista de oportunidades detectadas
connected_clients = set()
stats = {"total_scans": 0, "total_opportunities": 0, "start_time": time.time()}


# --- Price Fetcher ---
async def fetch_prices():
    """Fetch precios de los 3 exchanges continuamente."""
    while True:
        try:
            for pair in PAIRS:
                for name, exchange in EXCHANGES.items():
                    try:
                        ticker = await asyncio.wait_for(
                            exchange.fetch_ticker(pair), timeout=10
                        )
                        if pair not in prices:
                            prices[pair] = {}
                        prices[pair][name] = {
                            "bid": ticker.get("bid", 0) or 0,
                            "ask": ticker.get("ask", 0) or 0,
                            "last": ticker.get("last", 0) or 0,
                            "timestamp": time.time(),
                        }
                    except (asyncio.TimeoutError, Exception):
                        pass

                detect_arbitrage(pair)
                stats["total_scans"] += 1

            await asyncio.sleep(3)
        except Exception:
            await asyncio.sleep(5)


def detect_arbitrage(pair: str):
    """Detecta spreads entre exchanges para un par."""
    if pair not in prices:
        return

    exchanges_data = prices[pair]
    exchange_names = list(exchanges_data.keys())

    for i in range(len(exchange_names)):
        for j in range(i + 1, len(exchange_names)):
            ex_a = exchange_names[i]
            ex_b = exchange_names[j]
            data_a = exchanges_data[ex_a]
            data_b = exchanges_data[ex_b]

            # Verificar datos frescos (< 30 segundos)
            if time.time() - data_a["timestamp"] > 30:
                continue
            if time.time() - data_b["timestamp"] > 30:
                continue

            if data_a["bid"] <= 0 or data_b["ask"] <= 0:
                continue
            if data_a["ask"] <= 0 or data_b["bid"] <= 0:
                continue

            # Spread A→B: comprar en B (ask), vender en A (bid)
            spread_ab = ((data_a["bid"] - data_b["ask"]) / data_b["ask"]) * 100

            # Spread B→A: comprar en A (ask), vender en B (bid)
            spread_ba = ((data_b["bid"] - data_a["ask"]) / data_a["ask"]) * 100

            best_spread = max(spread_ab, spread_ba)
            if best_spread > 0.01:  # Registrar cualquier spread positivo
                direction = f"{ex_b}→{ex_a}" if spread_ab > spread_ba else f"{ex_a}→{ex_b}"
                buy_exchange = ex_b if spread_ab > spread_ba else ex_a
                sell_exchange = ex_a if spread_ab > spread_ba else ex_b
                buy_price = data_b["ask"] if spread_ab > spread_ba else data_a["ask"]
                sell_price = data_a["bid"] if spread_ab > spread_ba else data_b["bid"]

                opp = {
                    "pair": pair,
                    "spread_pct": round(best_spread, 4),
                    "buy_exchange": buy_exchange,
                    "sell_exchange": sell_exchange,
                    "buy_price": buy_price,
                    "sell_price": sell_price,
                    "profit_per_1000": round(best_spread * 10, 2),  # $ profit per $1000
                    "timestamp": datetime.utcnow().isoformat(),
                    "alert": best_spread >= ALERT_THRESHOLD,
                }

                # Mantener solo últimas 100 oportunidades
                opportunities.append(opp)
                if len(opportunities) > 100:
                    opportunities.pop(0)

                if opp["alert"]:
                    stats["total_opportunities"] += 1


async def broadcast_state():
    """No-op — cada WebSocket envía datos directamente."""
    pass


# --- API Routes ---
@app.get("/", response_class=HTMLResponse)
async def arbitrage_page():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h1>Crypto Arbitrage Detector</h1><p>Dashboard loading...</p>"


@app.get("/dashboard", response_class=HTMLResponse)
async def unified_dashboard():
    html_path = Path(__file__).parent / "static" / "dashboard.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h1>Dashboard</h1>"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            # Enviar estado cada 3 segundos al cliente
            current_opps = sorted(
                [o for o in opportunities],
                key=lambda x: x["spread_pct"],
                reverse=True,
            )[:20]

            state = {
                "prices": prices,
                "opportunities": current_opps,
                "stats": {
                    **stats,
                    "uptime_minutes": round((time.time() - stats["start_time"]) / 60, 1),
                    "active_pairs": len(prices),
                    "active_exchanges": len(EXCHANGES),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
            await websocket.send_json(state)
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    except Exception:
        connected_clients.discard(websocket)


@app.get("/api/opportunities")
async def get_opportunities():
    return {"opportunities": opportunities[-50:], "stats": stats}


@app.get("/api/prices")
async def get_prices():
    return {"prices": prices}


# --- Startup ---
@app.on_event("startup")
async def startup():
    asyncio.create_task(fetch_prices())


@app.on_event("shutdown")
async def shutdown():
    for exchange in EXCHANGES.values():
        await exchange.close()
