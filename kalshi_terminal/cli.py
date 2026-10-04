from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .client import DEMO_BASE, PROD_BASE, KalshiClient, Side, load_credentials


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _client(production: bool) -> KalshiClient:
    key_id, private_key = load_credentials()
    if not key_id or not private_key:
        raise RuntimeError(
            "Missing Kalshi credentials. Set KALSHI_KEY_ID and KALSHI_PRIVATE_KEY, "
            "or provide kalshi_key_id.txt and kalshi_private.pem in the project root."
        )
    return KalshiClient(key_id, private_key, PROD_BASE if production else DEMO_BASE)


def _side(value: str) -> Side:
    return Side(value.lower())


def _print_order_preview(args: argparse.Namespace, body: dict) -> None:
    environment = "production" if args.prod else "demo"
    economic = {
        "environment": environment,
        "mode": "LIVE" if args.live else "PREVIEW — no order submitted",
        "action": args.command.upper(),
        "ticker": args.ticker.upper(),
        "contract_side": args.side.upper(),
        "contracts": args.count,
        "limit_price_cents": args.limit,
        "maximum_notional_dollars": round(args.count * args.limit / 100, 4),
        "time_in_force": body["time_in_force"],
        "reduce_only": args.reduce_only,
        "kalshi_yes_book_payload": body,
    }
    _json(economic)


def command_order(args: argparse.Namespace) -> int:
    tif = "immediate_or_cancel" if args.ioc else "good_till_canceled"
    body = KalshiClient.build_limit_order(
        args.ticker,
        _side(args.side),
        args.command,
        args.count,
        args.limit,
        time_in_force=tif,
        reduce_only=args.reduce_only,
    )
    _print_order_preview(args, body)
    if not args.live:
        print("\nPreview only. Add --live to submit this order.")
        return 0
    client = _client(args.prod)
    result = client.place_limit(
        args.ticker,
        _side(args.side),
        args.command,
        args.count,
        args.limit,
        time_in_force=tif,
        reduce_only=args.reduce_only,
        client_order_id=body["client_order_id"],
    )
    print("\nOrder submitted:")
    _json(result)
    return 0


def command_balance(args: argparse.Namespace) -> int:
    cents = _client(args.prod).get_balance_cents()
    print(f"${cents / 100:,.2f} ({cents} cents)")
    return 0


def command_quote(args: argparse.Namespace) -> int:
    client = _client(args.prod)
    market = client.get_market(args.ticker.upper())
    bid, ask = client.get_top_of_book(args.ticker.upper(), _side(args.side))
    _json({"ticker": args.ticker.upper(), "side": args.side, "bid_cents": bid, "ask_cents": ask, "market": market})
    return 0


def command_position(args: argparse.Namespace) -> int:
    position = _client(args.prod).get_position(args.ticker.upper())
    _json({"ticker": args.ticker.upper(), "position": position})
    return 0


def command_markets(args: argparse.Namespace) -> int:
    markets = _client(args.prod).list_markets(args.series.upper(), status=args.status)
    compact = [
        {
            "ticker": item.get("ticker"),
            "title": item.get("title"),
            "status": item.get("status"),
            "yes_bid": item.get("yes_bid_dollars", item.get("yes_bid")),
            "yes_ask": item.get("yes_ask_dollars", item.get("yes_ask")),
            "close_time": item.get("close_time"),
        }
        for item in markets
    ]
    _json(compact)
    return 0


def command_orders(args: argparse.Namespace) -> int:
    _json(_client(args.prod).list_orders(args.ticker.upper() if args.ticker else None, args.status))
    return 0


def command_order_status(args: argparse.Namespace) -> int:
    _json(_client(args.prod).get_order(args.order_id))
    return 0


def command_cancel(args: argparse.Namespace) -> int:
    if not args.live:
        _json({"mode": "PREVIEW — no cancellation submitted", "order_id": args.order_id})
        print("\nPreview only. Add --live to cancel this order.")
        return 0
    _json(_client(args.prod).cancel_order(args.order_id))
    return 0


def command_cancel_all(args: argparse.Namespace) -> int:
    client = _client(args.prod)
    orders = client.list_orders(args.ticker.upper(), "resting")
    ids = [order.get("order_id") or order.get("id") for order in orders]
    ids = [value for value in ids if value]
    if not args.live:
        _json({"mode": "PREVIEW — no cancellations submitted", "ticker": args.ticker.upper(), "order_ids": ids})
        print("\nPreview only. Add --live to cancel these orders.")
        return 0
    results = [client.cancel_order(order_id) for order_id in ids]
    _json({"cancelled": len(results), "results": results})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ktrade", description="Safe-by-default Kalshi terminal trading")
    parser.add_argument("--prod", action="store_true", help="use the production exchange (default: demo)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("balance", help="show available balance").set_defaults(func=command_balance)

    markets = sub.add_parser("markets", help="list markets in a series")
    markets.add_argument("series")
    markets.add_argument("--status", default="open")
    markets.set_defaults(func=command_markets)

    quote = sub.add_parser("quote", help="show a market and side-specific top of book")
    quote.add_argument("ticker")
    quote.add_argument("--side", choices=("yes", "no"), default="yes")
    quote.set_defaults(func=command_quote)

    position = sub.add_parser("position", help="show the signed market position")
    position.add_argument("ticker")
    position.set_defaults(func=command_position)

    orders = sub.add_parser("orders", help="list account orders")
    orders.add_argument("--ticker")
    orders.add_argument("--status", choices=("resting", "canceled", "executed"))
    orders.set_defaults(func=command_orders)

    status = sub.add_parser("order", help="show one order")
    status.add_argument("order_id")
    status.set_defaults(func=command_order_status)

    for action in ("buy", "sell"):
        order = sub.add_parser(action, help=f"preview or submit a {action} limit order")
        order.add_argument("ticker")
        order.add_argument("side", choices=("yes", "no"))
        order.add_argument("count", type=float)
        order.add_argument("--limit", type=float, required=True, metavar="CENTS")
        order.add_argument("--ioc", action="store_true", help="immediate-or-cancel instead of resting")
        order.add_argument("--reduce-only", action="store_true")
        order.add_argument("--live", action="store_true", help="submit the order; without this flag only preview")
        order.set_defaults(func=command_order)

    cancel = sub.add_parser("cancel", help="preview or cancel one order")
    cancel.add_argument("order_id")
    cancel.add_argument("--live", action="store_true")
    cancel.set_defaults(func=command_cancel)

    cancel_all = sub.add_parser("cancel-all", help="preview or cancel resting orders for a ticker")
    cancel_all.add_argument("ticker")
    cancel_all.add_argument("--live", action="store_true")
    cancel_all.set_defaults(func=command_cancel_all)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
