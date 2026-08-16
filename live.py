from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import httpx
import websockets
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .engine import AnalyticsProcess
from .models import LiveEvent, point

REST_URL = "https://external-api.kalshi.com/trade-api/v2"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"
COINBASE_WS = "wss://advanced-trade-ws.coinbase.com"


def dollars_to_cents(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value) * 100.0
    except (TypeError, ValueError):
        return fallback


def parse_time(value: object) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


class LiveMarket:
    def __init__(self, engine: AnalyticsProcess, publish: Callable[[dict], Awaitable[None]], root: Path):
        self.engine = engine
        self.publish = publish
        self.root = root
        self.lock = asyncio.Lock()
        self.history: deque[dict] = deque(maxlen=1800)
        self.candles: deque[dict] = deque(maxlen=240)
        self.market: dict = {}
        self.btc_price = 0.0
        self.coinbase_prices = {"BTC-USD": 0.0, "ETH-USD": 0.0, "SOL-USD": 0.0}
        self.yes_bid = 0.0
        self.yes_ask = 0.0
        self.volume = 0.0
        self.started_at = time.time()
        self.source = {"kalshi_benchmark": "connecting", "coinbase": "connecting", "kalshi_ws": "connecting", "kalshi_rest": "connecting"}
        self.updated = {"kalshi_benchmark": 0, "coinbase": 0, "kalshi_ws": 0, "kalshi_rest": 0}
        self.errors: deque[str] = deque(maxlen=4)
        self.last_spot_publish = 0.0
        self.last_coinbase_publish = 0.0

    def snapshot(self) -> dict:
        now = time.time()
        return {
            "mode": "live",
            "market": self.market,
            "latest": self.history[-1] if self.history else None,
            "history": list(self.history),
            "candles": list(self.candles),
            "sources": {
                key: {"status": status, "age_ms": round((now - self.updated[key]) * 1000) if self.updated[key] else None}
                for key, status in self.source.items()
            },
            "errors": list(self.errors),
        }

    async def run(self) -> None:
        await asyncio.gather(self.coinbase_loop(), self.discovery_loop(), self.kalshi_loop(), self.sample_loop())

    async def coinbase_loop(self) -> None:
        delay = 1
        while True:
            try:
                self.source["coinbase"] = "connecting"
                async with websockets.connect(COINBASE_WS, ping_interval=20, ping_timeout=20) as ws:
                    await ws.send(json.dumps({"type": "subscribe", "product_ids": list(self.coinbase_prices), "channel": "ticker"}))
                    await ws.send(json.dumps({"type": "subscribe", "channel": "heartbeats"}))
                    self.source["coinbase"] = "live"
                    delay = 1
                    async for raw in ws:
                        data = json.loads(raw)
                        if data.get("channel") != "ticker":
                            continue
                        for event in data.get("events", []):
                            for ticker in event.get("tickers", []):
                                product = ticker.get("product_id")
                                if product not in self.coinbase_prices:
                                    continue
                                now = time.time()
                                self.coinbase_prices[product] = float(ticker["price"])
                                self.updated["coinbase"] = now
                                if product == "BTC-USD" and now - self.last_coinbase_publish >= 0.04:
                                    self.last_coinbase_publish = now
                                    await self.publish({"type": "coinbase", "price": self.coinbase_prices[product], "timestamp_ms": int(now * 1000)})
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.source["coinbase"] = "reconnecting"
                self.errors.append(f"Coinbase comparison: {error}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 20)

    async def discovery_loop(self) -> None:
        async with httpx.AsyncClient(timeout=8) as client:
            while True:
                try:
                    response = await client.get(f"{REST_URL}/markets", params={"series_ticker": "KXBTC15M", "status": "open", "limit": 100})
                    response.raise_for_status()
                    now = time.time()
                    markets = response.json().get("markets", [])
                    active = [item for item in markets if parse_time(item.get("close_time") or item.get("expiration_time")) > now]
                    if active:
                        chosen = min(active, key=lambda item: parse_time(item.get("close_time") or item.get("expiration_time")))
                        ticker = chosen.get("ticker", "")
                        previous = self.market.get("ticker")
                        self.market = {
                            "ticker": ticker,
                            "title": chosen.get("title") or "Bitcoin above the opening price?",
                            "target_price": float(chosen.get("floor_strike") or chosen.get("functional_strike") or 0),
                            "open_time": chosen.get("open_time"),
                            "close_time": chosen.get("close_time") or chosen.get("expiration_time"),
                            "close_ts": parse_time(chosen.get("close_time") or chosen.get("expiration_time")),
                        }
                        ws_stale = now - self.updated["kalshi_ws"] > 10
                        if previous != ticker or ws_stale:
                            self.yes_bid = dollars_to_cents(chosen.get("yes_bid_dollars"), self.yes_bid)
                            self.yes_ask = dollars_to_cents(chosen.get("yes_ask_dollars"), self.yes_ask)
                            self.volume = float(chosen.get("volume_fp") or self.volume)
                        if previous and previous != ticker:
                            self.history.clear()
                            self.candles.clear()
                            await self.engine.reset()
                            await self.publish({"type": "snapshot", "data": self.snapshot()})
                    self.source["kalshi_rest"] = "live"
                    self.updated["kalshi_rest"] = now
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.source["kalshi_rest"] = "reconnecting"
                    self.errors.append(f"Kalshi REST: {error}")
                await asyncio.sleep(5)

    def credentials(self) -> tuple[str, bytes] | None:
        key_id = os.getenv("KALSHI_KEY_ID", "").strip()
        pem_text = os.getenv("KALSHI_PRIVATE_KEY", "")
        key_path = Path(os.getenv("KALSHI_PRIVATE_KEY_PATH", "")) if os.getenv("KALSHI_PRIVATE_KEY_PATH") else None
        if not key_id:
            candidate = self.root.parent / "kalshi_key_id.txt"
            if candidate.exists():
                key_id = candidate.read_text().strip()
        if pem_text:
            pem = pem_text.encode()
        else:
            candidate = key_path or self.root.parent / "kalshi_private.pem"
            pem = candidate.read_bytes() if candidate.exists() else b""
        return (key_id, pem) if key_id and pem else None

    def auth_headers(self, key_id: str, pem: bytes) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        private_key = serialization.load_pem_private_key(pem, password=None)
        signature = private_key.sign(
            (timestamp + "GET" + "/trade-api/ws/v2").encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {"KALSHI-ACCESS-KEY": key_id, "KALSHI-ACCESS-TIMESTAMP": timestamp, "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode()}

    async def kalshi_loop(self) -> None:
        delay = 1
        while True:
            credentials = self.credentials()
            ticker = self.market.get("ticker")
            if not credentials or not ticker:
                self.source["kalshi_ws"] = "credentials required" if not credentials else "waiting for market"
                self.source["kalshi_benchmark"] = self.source["kalshi_ws"]
                await asyncio.sleep(1)
                continue
            try:
                self.source["kalshi_ws"] = "connecting"
                headers = self.auth_headers(*credentials)
                async with websockets.connect(WS_URL, additional_headers=headers, ping_interval=20, ping_timeout=20) as ws:
                    await ws.send(json.dumps({"id": 1, "cmd": "subscribe", "params": {"channels": ["ticker"], "market_tickers": [ticker]}}))
                    await ws.send(json.dumps({"id": 2, "cmd": "subscribe", "params": {"channels": ["cfbenchmarks_value"], "index_ids": ["BRTI"]}}))
                    self.source["kalshi_ws"] = "live"
                    delay = 1
                    while self.market.get("ticker") == ticker:
                        raw = await asyncio.wait_for(ws.recv(), timeout=15)
                        data = json.loads(raw)
                        if data.get("type") == "cfbenchmarks_value":
                            msg = data.get("msg", {})
                            upstream = msg.get("data") or {}
                            if isinstance(upstream, str):
                                try:
                                    upstream = json.loads(upstream)
                                except json.JSONDecodeError:
                                    upstream = {}
                            value = upstream.get("value") or (msg.get("avg_60s_data") or {}).get("value")
                            if value is None:
                                continue
                            self.btc_price = float(value)
                            now = time.time()
                            self.updated["kalshi_benchmark"] = now
                            self.source["kalshi_benchmark"] = "live"
                            self.update_candle(int(now * 1000), self.btc_price)
                            if now - self.last_spot_publish >= 0.04:
                                self.last_spot_publish = now
                                await self.publish({"type": "spot", "price": self.btc_price, "timestamp_ms": int(now * 1000), "candle": dict(self.candles[-1])})
                            continue
                        if data.get("type") != "ticker":
                            continue
                        msg = data.get("msg", {})
                        if msg.get("market_ticker") != ticker:
                            continue
                        self.yes_bid = dollars_to_cents(msg.get("yes_bid_dollars"), self.yes_bid)
                        self.yes_ask = dollars_to_cents(msg.get("yes_ask_dollars"), self.yes_ask)
                        self.volume = float(msg.get("volume_fp") or self.volume)
                        self.updated["kalshi_ws"] = time.time()
                        await self.publish({
                            "type": "quote",
                            "yes_bid_c": self.yes_bid,
                            "yes_ask_c": self.yes_ask,
                            "volume": self.volume,
                            "timestamp_ms": int(self.updated["kalshi_ws"] * 1000),
                        })
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.source["kalshi_ws"] = "reconnecting"
                self.source["kalshi_benchmark"] = "reconnecting"
                self.errors.append(f"Kalshi WS: {error}")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 20)

    def update_candle(self, now_ms: int, price: float) -> None:
        bucket = now_ms // 5000 * 5000
        if not self.candles or self.candles[-1]["time"] != bucket:
            self.candles.append({"time": bucket, "open": price, "high": price, "low": price, "close": price})
        else:
            candle = self.candles[-1]
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

    async def sample_loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            if not self.btc_price or not self.market or not self.yes_ask:
                await self.publish({"type": "status", "data": self.snapshot()})
                continue
            now = time.time()
            open_ts = parse_time(self.market.get("open_time")) or now
            elapsed = max(0, min(900, int(now - open_ts)))
            event = LiveEvent(
                elapsed, datetime.now(timezone.utc).isoformat(), self.yes_bid, self.yes_ask,
                self.btc_price, float(self.market.get("target_price") or 0), self.volume,
                self.coinbase_prices["ETH-USD"], self.coinbase_prices["SOL-USD"],
            )
            analytics = await self.engine.analyze(event)
            value = point(event, analytics)
            self.history.append(value)
            await self.publish({
                "type": "tick",
                "data": value,
                "market": self.market,
                "sources": self.snapshot()["sources"],
                "errors": list(self.errors),
            })
