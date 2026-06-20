import unittest
from unittest.mock import Mock


class Trading212BrokerTests(unittest.TestCase):
    def test_builds_basic_auth_header_from_key_and_secret(self):
        from app.trading212 import Trading212Broker

        broker = Trading212Broker("demo", "key-123", "secret-456")

        self.assertEqual(
            broker.session.headers["Authorization"],
            "Basic a2V5LTEyMzpzZWNyZXQtNDU2",
        )

    def test_parses_account_summary(self):
        from app.trading212 import Trading212Broker

        session = Mock()
        response = Mock()
        response.json.return_value = {
            "cash": {"availableToTrade": 950.25, "reservedForOrders": 12.5},
            "currency": "USD",
            "investments": {"currentValue": 400.75, "totalCost": 350.0},
            "totalValue": 1351.0,
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response

        broker = Trading212Broker("demo", "key", "secret", session=session)
        summary = broker.account_summary()

        self.assertEqual(summary.currency, "USD")
        self.assertAlmostEqual(summary.cash_available, 950.25)
        self.assertAlmostEqual(summary.cash_reserved, 12.5)
        self.assertAlmostEqual(summary.investments_value, 400.75)
        self.assertAlmostEqual(summary.total_value, 1351.0)

    def test_parses_instruments(self):
        from app.trading212 import Trading212Broker

        session = Mock()
        response = Mock()
        response.json.return_value = [
            {
                "ticker": "AAPL_US_EQ",
                "name": "Apple",
                "type": "STOCK",
                "currencyCode": "USD",
                "workingScheduleId": 100,
                "maxOpenQuantity": 10,
            }
        ]
        response.raise_for_status.return_value = None
        session.get.return_value = response

        broker = Trading212Broker("demo", "key", "secret", session=session)
        instruments = broker.instruments()

        self.assertIn("AAPL_US_EQ", instruments)
        instrument = instruments["AAPL_US_EQ"]
        self.assertEqual(instrument.name, "Apple")
        self.assertEqual(instrument.instrument_type, "STOCK")
        self.assertEqual(instrument.currency_code, "USD")
        self.assertEqual(instrument.working_schedule_id, 100)

    def test_parses_exchanges(self):
        from app.trading212 import Trading212Broker

        session = Mock()
        response = Mock()
        response.json.return_value = [
            {
                "id": 7,
                "name": "NASDAQ",
                "workingSchedules": [
                    {
                        "id": 100,
                        "timeEvents": [
                            {"date": "2026-06-19T13:30:00+00:00", "type": "OPEN"},
                            {"date": "2026-06-19T20:00:00+00:00", "type": "CLOSE"},
                        ],
                    }
                ],
            }
        ]
        response.raise_for_status.return_value = None
        session.get.return_value = response

        broker = Trading212Broker("demo", "key", "secret", session=session)
        schedules = broker.exchanges()

        self.assertIn(100, schedules)
        schedule = schedules[100]
        self.assertEqual(schedule.exchange_name, "NASDAQ")
        self.assertEqual([event.event_type for event in schedule.events], ["OPEN", "CLOSE"])

    def test_parses_positions(self):
        from app.trading212 import Trading212Broker

        session = Mock()
        response = Mock()
        response.json.return_value = [
            {
                "averagePricePaid": 180.5,
                "currentPrice": 182.1,
                "quantity": 3,
                "quantityAvailableForTrading": 3,
                "walletImpact": {"currentValue": 546.3},
                "instrument": {
                    "ticker": "AAPL_US_EQ",
                    "name": "Apple",
                    "currency": "USD",
                },
            }
        ]
        response.raise_for_status.return_value = None
        session.get.return_value = response

        broker = Trading212Broker("demo", "key", "secret", session=session)
        positions = broker.positions()

        self.assertIn("AAPL_US_EQ", positions)
        position = positions["AAPL_US_EQ"]
        self.assertAlmostEqual(position.quantity, 3)
        self.assertAlmostEqual(position.average_price_paid, 180.5)
        self.assertAlmostEqual(position.current_price, 182.1)
        self.assertAlmostEqual(position.current_value, 546.3)

    def test_places_market_order_with_signed_quantity(self):
        from app.trading212 import Trading212Broker

        session = Mock()
        response = Mock()
        response.json.return_value = {
            "id": 99,
            "status": "CONFIRMED",
            "side": "SELL",
            "ticker": "AAPL_US_EQ",
            "quantity": -1.25,
            "filledQuantity": 0,
            "filledValue": 0,
            "currency": "USD",
        }
        response.raise_for_status.return_value = None
        session.post.return_value = response

        broker = Trading212Broker("demo", "key", "secret", session=session)
        result = broker.place_market_order("AAPL_US_EQ", -1.25, extended_hours=True)

        session.post.assert_called_once_with(
            "https://demo.trading212.com/api/v0/equity/orders/market",
            json={"ticker": "AAPL_US_EQ", "quantity": -1.25, "extendedHours": True},
            timeout=20,
        )
        self.assertEqual(result.status, "CONFIRMED")
        self.assertEqual(result.side, "SELL")


if __name__ == "__main__":
    unittest.main()
