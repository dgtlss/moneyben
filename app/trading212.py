"""Trading 212 broker client and normalized response models."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime

from .http import SimpleSession


def _parse_dt(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


@dataclass(frozen=True)
class AccountSummary:
    currency: str
    cash_available: float
    cash_reserved: float
    investments_value: float
    total_value: float


@dataclass(frozen=True)
class Instrument:
    ticker: str
    name: str
    instrument_type: str
    currency_code: str
    working_schedule_id: int | None
    max_open_quantity: float | None


@dataclass(frozen=True)
class ScheduleEvent:
    when: datetime
    event_type: str


@dataclass(frozen=True)
class WorkingSchedule:
    id: int
    exchange_name: str
    events: list[ScheduleEvent]


@dataclass(frozen=True)
class Position:
    ticker: str
    name: str
    currency: str
    quantity: float
    quantity_available: float
    average_price_paid: float
    current_price: float
    current_value: float


@dataclass(frozen=True)
class OrderResult:
    id: int
    status: str
    side: str
    ticker: str
    quantity: float
    filled_quantity: float
    filled_value: float
    currency: str


class Trading212Broker:
    def __init__(
        self,
        environment: str,
        api_key: str,
        api_secret: str,
        session=None,
    ):
        self.base_url = f"https://{environment}.trading212.com/api/v0"
        self.session = session or SimpleSession()
        self.session.headers.update(
            {
                "Authorization": self._basic_auth(api_key, api_secret),
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _basic_auth(api_key: str, api_secret: str) -> str:
        token = base64.b64encode(f"{api_key}:{api_secret}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"

    def account_summary(self) -> AccountSummary:
        response = self.session.get(f"{self.base_url}/equity/account/summary", timeout=20)
        response.raise_for_status()
        payload = response.json()
        return AccountSummary(
            currency=payload.get("currency", ""),
            cash_available=float(payload.get("cash", {}).get("availableToTrade", 0.0) or 0.0),
            cash_reserved=float(payload.get("cash", {}).get("reservedForOrders", 0.0) or 0.0),
            investments_value=float(payload.get("investments", {}).get("currentValue", 0.0) or 0.0),
            total_value=float(payload.get("totalValue", 0.0) or 0.0),
        )

    def instruments(self) -> dict[str, Instrument]:
        response = self.session.get(f"{self.base_url}/equity/metadata/instruments", timeout=20)
        response.raise_for_status()
        instruments: dict[str, Instrument] = {}
        for item in response.json():
            instrument = Instrument(
                ticker=item.get("ticker", ""),
                name=item.get("name", ""),
                instrument_type=item.get("type", ""),
                currency_code=item.get("currencyCode", ""),
                working_schedule_id=item.get("workingScheduleId"),
                max_open_quantity=float(item["maxOpenQuantity"]) if item.get("maxOpenQuantity") is not None else None,
            )
            instruments[instrument.ticker] = instrument
        return instruments

    def exchanges(self) -> dict[int, WorkingSchedule]:
        response = self.session.get(f"{self.base_url}/equity/metadata/exchanges", timeout=20)
        response.raise_for_status()
        schedules: dict[int, WorkingSchedule] = {}
        for exchange in response.json():
            exchange_name = exchange.get("name", "")
            for raw_schedule in exchange.get("workingSchedules", []):
                events = [
                    ScheduleEvent(when=_parse_dt(event["date"]), event_type=event["type"])
                    for event in raw_schedule.get("timeEvents", [])
                    if event.get("date") and event.get("type")
                ]
                schedules[int(raw_schedule["id"])] = WorkingSchedule(
                    id=int(raw_schedule["id"]),
                    exchange_name=exchange_name,
                    events=sorted(events, key=lambda event: event.when),
                )
        return schedules

    def positions(self) -> dict[str, Position]:
        response = self.session.get(f"{self.base_url}/equity/positions", timeout=20)
        response.raise_for_status()
        positions: dict[str, Position] = {}
        for item in response.json():
            instrument = item.get("instrument", {})
            ticker = instrument.get("ticker", "")
            position = Position(
                ticker=ticker,
                name=instrument.get("name", ""),
                currency=instrument.get("currency", ""),
                quantity=float(item.get("quantity", 0.0) or 0.0),
                quantity_available=float(item.get("quantityAvailableForTrading", 0.0) or 0.0),
                average_price_paid=float(item.get("averagePricePaid", 0.0) or 0.0),
                current_price=float(item.get("currentPrice", 0.0) or 0.0),
                current_value=float(item.get("walletImpact", {}).get("currentValue", 0.0) or 0.0),
            )
            positions[ticker] = position
        return positions

    def place_market_order(self, ticker: str, quantity: float, extended_hours: bool = False) -> OrderResult:
        response = self.session.post(
            f"{self.base_url}/equity/orders/market",
            json={"ticker": ticker, "quantity": quantity, "extendedHours": extended_hours},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        return OrderResult(
            id=int(payload.get("id", 0) or 0),
            status=payload.get("status", ""),
            side=payload.get("side", ""),
            ticker=payload.get("ticker", ticker),
            quantity=float(payload.get("quantity", quantity) or quantity),
            filled_quantity=float(payload.get("filledQuantity", 0.0) or 0.0),
            filled_value=float(payload.get("filledValue", 0.0) or 0.0),
            currency=payload.get("currency", ""),
        )
