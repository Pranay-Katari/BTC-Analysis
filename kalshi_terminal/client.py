from __future__ import annotations

import base64
import json
import os
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


DEMO_BASE = "https://demo-api.kalshi.co"
PROD_BASE = "https://api.elections.kalshi.com"
API_PREFIX = "/trade-api/v2"


class Side(str, Enum):
    YES = "yes"
    NO = "no"


def _to_cents(value: Any) -> float:
    if isinstance(value, int):
        return float(value)
    text = str(value)
    number = float(text)
    return round(number * 100 if "." in text and number <= 1 else number, 4)


def load_credentials(base_dir: str | None = None) -> tuple[str | None, str | None]:
    root = Path(base_dir) if base_dir else Path.cwd()
    key_id = os.getenv("KALSHI_KEY_ID")
    private_key = os.getenv("KALSHI_PRIVATE_KEY")
    if not key_id and (root / "kalshi_key_id.txt").exists():
        key_id = (root / "kalshi_key_id.txt").read_text().strip()
    if not private_key and (root / "kalshi_private.pem").exists():
        private_key = (root / "kalshi_private.pem").read_text()
    return key_id, private_key


class KalshiClient:
    def __init__(self, key_id: str, private_key_pem: str, base_url: str = DEMO_BASE, max_retries: int = 4):
        self.key_id = key_id
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
        self._session = requests.Session()

    def _sign(self, method: str, path: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        signature = self._key.sign(
            (timestamp + method.upper() + path.split("?")[0]).encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return {
            "KALSHI-ACCESS-KEY": self.key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode(),
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None) -> dict:
        for attempt in range(self.max_retries):
            response = self._session.request(
                method,
                self.base_url + path,
                headers=self._sign(method, path),
                params=params,
                data=json.dumps(body) if body is not None else None,
                timeout=10,
            )
            if response.status_code == 429 or response.status_code >= 500:
                time.sleep(min(0.25 * 2**attempt, 4))
                continue
            if not response.ok:
                raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text}")
            return response.json() if response.content else {}
        raise RuntimeError(f"{method} {path} failed after {self.max_retries} retries")

    def get_balance_cents(self) -> int:
        data = self._request("GET", f"{API_PREFIX}/portfolio/balance")
        return int(data["balance"]) if data.get("balance") is not None else round(float(data["balance_dollars"]) * 100)

    def get_position(self, ticker: str) -> float:
        data = self._request("GET", f"{API_PREFIX}/portfolio/positions", params={"ticker": ticker})
        for position in data.get("market_positions", []):
            if position.get("ticker") == ticker:
                return float(position.get("position_fp", position.get("position", 0)) or 0)
        return 0.0

    def list_markets(self, series_ticker: str, status: str | None = "open") -> list[dict]:
        result: list[dict] = []
        cursor = None
        while True:
            params = {"series_ticker": series_ticker, "limit": 100}
            if status:
                params["status"] = status
            if cursor:
                params["cursor"] = cursor
            data = self._request("GET", f"{API_PREFIX}/markets", params=params)
            result.extend(data.get("markets", []))
            cursor = data.get("cursor")
            if not cursor:
                return result

    def get_market(self, ticker: str) -> dict:
        return self._request("GET", f"{API_PREFIX}/markets/{ticker}")["market"]

    def get_top_of_book(self, ticker: str, side: Side) -> tuple[float | None, float | None]:
        market = self.get_market(ticker)
        prefix = "yes" if side == Side.YES else "no"
        bid_raw, ask_raw = market.get(f"{prefix}_bid_dollars"), market.get(f"{prefix}_ask_dollars")
        bid = _to_cents(bid_raw) if bid_raw not in (None, "") else None
        ask = _to_cents(ask_raw) if ask_raw not in (None, "") else None
        return (None if bid == 0 else bid), (None if ask == 0 else ask)

    @staticmethod
    def build_limit_order(
        ticker: str,
        side: Side,
        action: str,
        count: float,
        price_cents: float,
        *,
        time_in_force: str = "good_till_canceled",
        reduce_only: bool = False,
        client_order_id: str | None = None,
    ) -> dict:
        action = action.lower()
        if action not in {"buy", "sell"}:
            raise ValueError("action must be 'buy' or 'sell'")
        if float(count) <= 0:
            raise ValueError("count must be greater than zero")
        price_cents = float(price_cents)
        if not 0.1 <= price_cents <= 99.9:
            raise ValueError("price must be between 0.1 and 99.9 cents")
        if time_in_force not in {"good_till_canceled", "immediate_or_cancel"}:
            raise ValueError("invalid time in force")
        book_side = "bid" if ((side == Side.YES and action == "buy") or (side == Side.NO and action == "sell")) else "ask"
        yes_price = price_cents if side == Side.YES else 100 - price_cents
        return {
            "ticker": ticker.upper(),
            "client_order_id": client_order_id or uuid.uuid4().hex,
            "side": book_side,
            "count": f"{float(count):.2f}",
            "price": f"{yes_price / 100:.4f}",
            "time_in_force": time_in_force,
            "self_trade_prevention_type": "taker_at_cross",
            "reduce_only": bool(reduce_only),
        }

    def place_limit(self, ticker: str, side: Side, action: str, count: float, price_cents: float, **options: Any) -> dict:
        body = self.build_limit_order(ticker, side, action, count, price_cents, **options)
        return self._request("POST", f"{API_PREFIX}/portfolio/events/orders", body=body)

    def list_orders(self, ticker: str | None = None, status: str | None = None) -> list[dict]:
        params = {key: value for key, value in {"ticker": ticker, "status": status}.items() if value}
        return self._request("GET", f"{API_PREFIX}/portfolio/orders", params=params).get("orders", [])

    def get_order(self, order_id: str) -> dict:
        data = self._request("GET", f"{API_PREFIX}/portfolio/orders/{order_id}")
        return data.get("order", data)

    def cancel_order(self, order_id: str) -> dict:
        return self._request("DELETE", f"{API_PREFIX}/portfolio/orders/{order_id}")
