from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .engine import AnalyticsProcess
from .live import LiveMarket

ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "build" / "btc_analytics"
ALLOWED_DASHBOARDS = ["http://localhost:3000", "http://127.0.0.1:3000"]

connected_dashboards: set[WebSocket] = set()


async def broadcast(message: dict) -> None:
    """Send the latest market state to every open dashboard."""
    stale: list[WebSocket] = []
    for client in connected_dashboards:
        try:
            await client.send_json(message)
        except Exception:
            stale.append(client)

    for client in stale:
        connected_dashboards.discard(client)


engine = AnalyticsProcess(ENGINE_PATH)
market = LiveMarket(engine, broadcast, ROOT)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the live feeds with the API and shut them down cleanly."""
    await engine.start()
    market_task = asyncio.create_task(market.run())
    try:
        yield
    finally:
        market_task.cancel()
        with suppress(asyncio.CancelledError):
            await market_task
        await engine.close()


app = FastAPI(title="BTC Live Market API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_DASHBOARDS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "engine": "cpp", "mode": "live-monitoring"}


@app.get("/api/state")
def state() -> dict:
    return market.snapshot()


@app.websocket("/ws")
async def websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    connected_dashboards.add(websocket)
    await websocket.send_json({"type": "snapshot", "data": market.snapshot()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_dashboards.discard(websocket)
