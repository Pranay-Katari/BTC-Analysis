import unittest

from kalshi_terminal.cli import build_parser
from kalshi_terminal.client import KalshiClient, Side


class LimitOrderMappingTests(unittest.TestCase):
    def test_buy_yes_uses_bid_at_economic_price(self):
        order = KalshiClient.build_limit_order("TEST", Side.YES, "buy", 3, 62, client_order_id="x")
        self.assertEqual(order["side"], "bid")
        self.assertEqual(order["price"], "0.6200")

    def test_buy_no_complements_price_and_uses_ask(self):
        order = KalshiClient.build_limit_order("TEST", Side.NO, "buy", 2.5, 63, client_order_id="x")
        self.assertEqual(order["side"], "ask")
        self.assertEqual(order["price"], "0.3700")
        self.assertEqual(order["count"], "2.50")

    def test_sell_no_uses_bid_at_complement(self):
        order = KalshiClient.build_limit_order("TEST", Side.NO, "sell", 1, 40, client_order_id="x")
        self.assertEqual(order["side"], "bid")
        self.assertEqual(order["price"], "0.6000")

    def test_invalid_price_rejected(self):
        with self.assertRaises(ValueError):
            KalshiClient.build_limit_order("TEST", Side.YES, "buy", 1, 100)

    def test_cli_defaults_to_preview_and_demo(self):
        args = build_parser().parse_args(["buy", "TEST", "yes", "4", "--limit", "51"])
        self.assertFalse(args.live)
        self.assertFalse(args.prod)


if __name__ == "__main__":
    unittest.main()
