from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from app.trading212 import OrderResult


def make_config():
    return SimpleNamespace(
        min_confidence=0.6,
        max_trade_usd=250.0,
        max_position_usd=1_000.0,
        min_trade_usd=10.0,
        min_cash_reserve_usd=100.0,
        quantity_precision=4,
        max_price_age_seconds=300,
        extended_hours=False,
        read_only=False,
    )


class TraderTests(unittest.TestCase):
    def test_read_only_mode_skips_broker_order_and_logs_intent(self):
        from app.portfolio import Portfolio
        from app.trader import Trader

        broker = Mock()
        cfg = make_config()
        cfg.read_only = True

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            portfolio.cash = 1_000.0
            trader = Trader(cfg, portfolio, broker)
            decision = {"product": "AAPL_US_EQ", "action": "BUY", "size_usd": 400.0, "confidence": 0.9, "reason": "trend"}

            outcome = trader.execute(
                decision,
                price=100.0,
                price_as_of=datetime.now(timezone.utc),
            )

        broker.place_market_order.assert_not_called()
        self.assertIn("read-only", outcome.lower())
        self.assertEqual(portfolio.trades[-1]["status"], "READ_ONLY")

    def test_buy_clamps_and_converts_to_quantity(self):
        from app.portfolio import Portfolio
        from app.trader import Trader

        broker = Mock()
        broker.place_market_order.return_value = OrderResult(
            id=1,
            status="CONFIRMED",
            side="BUY",
            ticker="AAPL_US_EQ",
            quantity=2.5,
            filled_quantity=0.0,
            filled_value=0.0,
            currency="USD",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            portfolio.cash = 1_000.0
            trader = Trader(make_config(), portfolio, broker)
            decision = {"product": "AAPL_US_EQ", "action": "BUY", "size_usd": 400.0, "confidence": 0.9, "reason": "trend"}

            outcome = trader.execute(
                decision,
                price=100.0,
                price_as_of=datetime.now(timezone.utc),
            )

        broker.place_market_order.assert_called_once_with("AAPL_US_EQ", 2.5, extended_hours=False)
        self.assertIn("queued", outcome.lower())

    def test_sell_clamps_to_held_quantity(self):
        from app.portfolio import Portfolio
        from app.trader import Trader

        broker = Mock()
        broker.place_market_order.return_value = OrderResult(
            id=2,
            status="CONFIRMED",
            side="SELL",
            ticker="AAPL_US_EQ",
            quantity=-3.0,
            filled_quantity=0.0,
            filled_value=0.0,
            currency="USD",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            portfolio.cash = 500.0
            portfolio.positions["AAPL_US_EQ"] = {
                "quantity": 3.0,
                "avg_price": 90.0,
                "current_price": 100.0,
                "value_usd": 300.0,
                "name": "Apple",
                "currency": "USD",
            }
            trader = Trader(make_config(), portfolio, broker)
            decision = {"product": "AAPL_US_EQ", "action": "SELL", "size_usd": 500.0, "confidence": 0.9, "reason": "rebalance"}

            trader.execute(
                decision,
                price=100.0,
                price_as_of=datetime.now(timezone.utc),
            )

        broker.place_market_order.assert_called_once_with("AAPL_US_EQ", -2.5, extended_hours=False)

    def test_rejects_stale_prices(self):
        from app.portfolio import Portfolio
        from app.trader import Trader

        broker = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            portfolio.cash = 1_000.0
            trader = Trader(make_config(), portfolio, broker)
            decision = {"product": "AAPL_US_EQ", "action": "BUY", "size_usd": 100.0, "confidence": 0.9, "reason": "trend"}

            outcome = trader.execute(
                decision,
                price=100.0,
                price_as_of=datetime.now(timezone.utc) - timedelta(minutes=10),
            )

        broker.place_market_order.assert_not_called()
        self.assertIn("stale", outcome.lower())


if __name__ == "__main__":
    unittest.main()
