from datetime import datetime, timezone
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from app.trading212 import AccountSummary, Instrument, Position, ScheduleEvent, WorkingSchedule


def make_cfg():
    return SimpleNamespace(
        tickers=["AAPL_US_EQ"],
        extended_hours=False,
        candle_lookback=120,
        quote_currency="USD",
    )


class MainCycleTests(unittest.TestCase):
    def test_run_cycle_skips_llm_and_orders_when_market_closed(self):
        from app.main import run_cycle
        from app.portfolio import Portfolio

        closed_schedule = WorkingSchedule(
            id=100,
            exchange_name="NASDAQ",
            events=[
                ScheduleEvent(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc), "OPEN"),
                ScheduleEvent(datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc), "CLOSE"),
            ],
        )
        instruments = {
            "AAPL_US_EQ": Instrument("AAPL_US_EQ", "Apple", "STOCK", "USD", 100, 10.0)
        }
        broker = Mock()
        broker.account_summary.return_value = AccountSummary("USD", 1000.0, 0.0, 0.0, 1000.0)
        broker.positions.return_value = {}
        market_data = Mock()
        llm = Mock()
        trader = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            run_cycle(
                make_cfg(),
                broker,
                market_data,
                llm,
                portfolio,
                trader,
                instruments,
                {100: closed_schedule},
                now=datetime(2026, 6, 19, 21, 0, tzinfo=timezone.utc),
            )

        llm.decide.assert_not_called()
        trader.execute.assert_not_called()

    def test_run_cycle_trades_when_market_is_open(self):
        from app.main import run_cycle
        from app.portfolio import Portfolio

        open_schedule = WorkingSchedule(
            id=100,
            exchange_name="NASDAQ",
            events=[
                ScheduleEvent(datetime(2026, 6, 19, 13, 30, tzinfo=timezone.utc), "OPEN"),
                ScheduleEvent(datetime(2026, 6, 19, 20, 0, tzinfo=timezone.utc), "CLOSE"),
            ],
        )
        instruments = {
            "AAPL_US_EQ": Instrument("AAPL_US_EQ", "Apple", "STOCK", "USD", 100, 10.0)
        }
        broker = Mock()
        broker.account_summary.return_value = AccountSummary("USD", 1000.0, 0.0, 300.0, 1300.0)
        broker.positions.return_value = {
            "AAPL_US_EQ": Position("AAPL_US_EQ", "Apple", "USD", 2.0, 2.0, 140.0, 150.0, 300.0)
        }
        market_data = Mock()
        market_data.candles.return_value = [
            {"close": 149.0},
            {"close": 150.0},
            {"close": 151.0},
        ]
        market_data.price.return_value = (151.0, datetime(2026, 6, 19, 15, 0, tzinfo=timezone.utc))
        llm = Mock()
        llm.decide.return_value = [{"product": "AAPL_US_EQ", "action": "HOLD", "size_usd": 0.0, "confidence": 0.0, "reason": ""}]
        trader = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            portfolio = Portfolio(f"{tmpdir}/portfolio.json", quote_currency="USD")
            run_cycle(
                make_cfg(),
                broker,
                market_data,
                llm,
                portfolio,
                trader,
                instruments,
                {100: open_schedule},
                now=datetime(2026, 6, 19, 15, 0, tzinfo=timezone.utc),
            )

        llm.decide.assert_called_once()
        trader.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
