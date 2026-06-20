import tempfile
import unittest

from app.trading212 import AccountSummary, Position


class PortfolioTests(unittest.TestCase):
    def test_sync_from_broker_rebuilds_snapshot(self):
        from app.portfolio import Portfolio

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            portfolio.sync_from_broker(
                AccountSummary(
                    currency="USD",
                    cash_available=900.0,
                    cash_reserved=25.0,
                    investments_value=300.0,
                    total_value=1200.0,
                ),
                {
                    "AAPL_US_EQ": Position(
                        ticker="AAPL_US_EQ",
                        name="Apple",
                        currency="USD",
                        quantity=2.0,
                        quantity_available=2.0,
                        average_price_paid=140.0,
                        current_price=150.0,
                        current_value=300.0,
                    )
                },
            )

            snapshot = portfolio.snapshot()

            self.assertEqual(snapshot["cash_usd"], 900.0)
            self.assertEqual(snapshot["total_value_usd"], 1200.0)
            self.assertEqual(snapshot["positions"]["AAPL_US_EQ"]["quantity"], 2.0)
            self.assertEqual(snapshot["positions"]["AAPL_US_EQ"]["value_usd"], 300.0)


if __name__ == "__main__":
    unittest.main()
