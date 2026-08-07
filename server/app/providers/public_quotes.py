from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.core.time import Clock, SystemClock
from app.models.disclosures import ProviderStatus

UPBIT_TICKER_URL = "https://api.upbit.com/v1/ticker"
BINANCE_AVERAGE_PRICE_URL = "https://data-api.binance.vision/api/v3/avgPrice"


@dataclass(frozen=True, slots=True)
class PublicQuote:
    provider: str
    provider_symbol: str
    price: Decimal
    quote_currency: str
    provider_event_at: datetime
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class PublicQuoteResult:
    provider: str
    status: ProviderStatus
    quote: PublicQuote | None = None
    error_code: str | None = None
    request_count: int = 0


class PublicQuoteProvider:
    def __init__(
        self,
        provider: str,
        *,
        enabled: bool,
        client: httpx.Client | None = None,
        clock: Clock | None = None,
    ) -> None:
        normalized = provider.strip().upper()
        if normalized not in {"UPBIT", "BINANCE"}:
            raise ValueError("unsupported public quote provider")
        self.provider = normalized
        self.enabled = enabled
        self._client = client
        self._clock = clock or SystemClock()

    @property
    def status(self) -> ProviderStatus:
        return ProviderStatus.READY if self.enabled else ProviderStatus.NOT_CONFIGURED

    def fetch_btc(self) -> PublicQuoteResult:
        if not self.enabled:
            return PublicQuoteResult(self.provider, ProviderStatus.NOT_CONFIGURED)
        try:
            with self._client_context() as client:
                response = (
                    client.get(
                        UPBIT_TICKER_URL,
                        params={"markets": "KRW-BTC"},
                        headers={"Accept": "application/json"},
                        timeout=10,
                    )
                    if self.provider == "UPBIT"
                    else client.get(
                        BINANCE_AVERAGE_PRICE_URL,
                        params={"symbol": "BTCUSDT"},
                        headers={"Accept": "application/json"},
                        timeout=10,
                    )
                )
            if response.status_code == 429:
                return PublicQuoteResult(
                    self.provider,
                    ProviderStatus.RATE_LIMITED,
                    error_code="HTTP_429",
                    request_count=1,
                )
            response.raise_for_status()
            quote = (
                self._parse_upbit(response.json())
                if self.provider == "UPBIT"
                else self._parse_binance(response.json())
            )
            return PublicQuoteResult(
                self.provider,
                ProviderStatus.READY,
                quote=quote,
                request_count=1,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            return PublicQuoteResult(
                self.provider,
                ProviderStatus.NETWORK_UNAVAILABLE,
                error_code="NETWORK_UNAVAILABLE",
                request_count=1,
            )
        except (httpx.HTTPStatusError, InvalidOperation, KeyError, TypeError, ValueError):
            return PublicQuoteResult(
                self.provider,
                ProviderStatus.FAILED,
                error_code="INVALID_PROVIDER_RESPONSE",
                request_count=1,
            )

    def _parse_upbit(self, body: object) -> PublicQuote:
        if not isinstance(body, list) or len(body) != 1 or not isinstance(body[0], dict):
            raise ValueError("invalid Upbit ticker response")
        item = body[0]
        if str(item.get("market", "")).upper() != "KRW-BTC":
            raise ValueError("unexpected Upbit symbol")
        event_milliseconds = int(item["timestamp"])
        return self._quote(
            symbol="KRW-BTC",
            price=Decimal(str(item["trade_price"])),
            quote_currency="KRW",
            event_milliseconds=event_milliseconds,
        )

    def _parse_binance(self, body: object) -> PublicQuote:
        if not isinstance(body, dict):
            raise ValueError("invalid Binance price response")
        return self._quote(
            symbol="BTCUSDT",
            price=Decimal(str(body["price"])),
            quote_currency="USDT",
            event_milliseconds=int(body["closeTime"]),
        )

    def _quote(
        self,
        *,
        symbol: str,
        price: Decimal,
        quote_currency: str,
        event_milliseconds: int,
    ) -> PublicQuote:
        if not price.is_finite() or price <= 0 or event_milliseconds <= 0:
            raise ValueError("invalid public quote")
        return PublicQuote(
            provider=self.provider,
            provider_symbol=symbol,
            price=price,
            quote_currency=quote_currency,
            provider_event_at=datetime.fromtimestamp(event_milliseconds / 1000, tz=UTC),
            fetched_at=self._clock.now(),
        )

    def _client_context(self):
        return nullcontext(self._client) if self._client is not None else httpx.Client()
