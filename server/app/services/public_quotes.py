from __future__ import annotations

from datetime import timedelta
from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.freshness import FreshnessStatus, classify_freshness
from app.models.database import AssetType, Currency, PortfolioItemRecord
from app.models.disclosures import (
    InstrumentProviderMappingRecord,
    InstrumentRecord,
    InstrumentVerificationStatus,
    MappingMatchMethod,
    MappingStatus,
    ProviderName,
    ProviderStatus,
)
from app.models.market_data import ProviderSyncStateRecord, QuoteSnapshotRecord
from app.providers.public_quotes import PublicQuote, PublicQuoteProvider


def quote_freshness(quote: PublicQuote) -> str:
    result = classify_freshness(
        observed_at=quote.provider_event_at,
        current_time=quote.fetched_at,
        live_threshold=120,
        delayed_threshold=3600,
    )
    if result.status is FreshnessStatus.LIVE:
        return "LIVE"
    if result.age_seconds is not None and result.age_seconds <= 900:
        return "RECENT"
    return result.status.value


class PublicQuoteService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def sync(
        self,
        *,
        provider: str | None = None,
        dry_run: bool,
        confirm: bool,
        clients: dict[str, object] | None = None,
    ) -> dict[str, object]:
        if not dry_run and not confirm:
            return {"status": "CONFIRM_REQUIRED", "requestCount": 0}
        requested = [provider.upper()] if provider else ["UPBIT", "BINANCE"]
        totals = {
            "requestCount": 0,
            "created": 0,
            "duplicates": 0,
            "notApplicable": 0,
        }
        results: list[dict[str, object]] = []
        for name in requested:
            portfolio = self.session.scalar(
                select(PortfolioItemRecord).where(
                    PortfolioItemRecord.archived_at.is_(None),
                    PortfolioItemRecord.asset_type == AssetType.CRYPTO,
                    PortfolioItemRecord.market == name,
                    PortfolioItemRecord.symbol == "BTC",
                )
            )
            enabled = (
                self.settings.upbit_public_market_enabled
                if name == "UPBIT"
                else self.settings.binance_public_market_enabled
            )
            if portfolio is None:
                totals["notApplicable"] += 1
                results.append({"provider": name, "status": "NOT_APPLICABLE"})
                continue
            client = (clients or {}).get(name)
            result = PublicQuoteProvider(
                name,
                enabled=enabled,
                client=client,  # type: ignore[arg-type]
            ).fetch_btc()
            totals["requestCount"] += result.request_count
            results.append({"provider": name, "status": result.status.value})
            if not dry_run:
                self._record_state(
                    name,
                    result.status,
                    result.error_code,
                    result.request_count,
                    configured=enabled,
                )
            if result.quote is None:
                continue
            if dry_run:
                continue
            instrument = self._ensure_instrument(portfolio, result.quote)
            fingerprint = self._fingerprint(instrument.id, result.quote)
            exists = self.session.scalar(
                select(QuoteSnapshotRecord.id).where(
                    QuoteSnapshotRecord.fingerprint == fingerprint
                )
            )
            if exists:
                totals["duplicates"] += 1
                continue
            sequence = (
                int(
                    self.session.scalar(
                        select(func.max(QuoteSnapshotRecord.sequence)).where(
                            QuoteSnapshotRecord.provider == name,
                            QuoteSnapshotRecord.instrument_id == instrument.id,
                        )
                    )
                    or 0
                )
                + 1
            )
            quote = result.quote
            self.session.add(
                QuoteSnapshotRecord(
                    instrument_id=instrument.id,
                    provider=name,
                    provider_symbol=quote.provider_symbol,
                    price=quote.price,
                    quote_currency=quote.quote_currency,
                    provider_event_at=quote.provider_event_at,
                    fetched_at=quote.fetched_at,
                    freshness_status=quote_freshness(quote),
                    source_status="READY",
                    sequence=sequence,
                    fingerprint=fingerprint,
                    expires_at=quote.fetched_at + timedelta(days=30),
                )
            )
            totals["created"] += 1
        if not dry_run:
            self.session.flush()
        return {
            "status": "DRY_RUN" if dry_run else "SUCCEEDED",
            **totals,
            "providers": results,
        }

    def _ensure_instrument(
        self, portfolio: PortfolioItemRecord, quote: PublicQuote
    ) -> InstrumentRecord:
        instrument = self.session.scalar(
            select(InstrumentRecord).where(
                InstrumentRecord.market == portfolio.market,
                InstrumentRecord.canonical_symbol == portfolio.symbol,
                InstrumentRecord.active.is_(True),
            )
        )
        if instrument is None:
            instrument = InstrumentRecord(
                canonical_symbol="BTC",
                display_name=portfolio.name,
                exchange=portfolio.market,
                market=portfolio.market,
                country="XX",
                currency=(Currency.KRW if portfolio.market == "UPBIT" else Currency.USDT),
                asset_type=AssetType.CRYPTO,
                verification_status=InstrumentVerificationStatus.VERIFIED,
                verification_source=quote.provider,
                verified_at=quote.fetched_at,
            )
            self.session.add(instrument)
            self.session.flush()
        provider = ProviderName(quote.provider)
        mapping = self.session.scalar(
            select(InstrumentProviderMappingRecord).where(
                InstrumentProviderMappingRecord.provider == provider,
                InstrumentProviderMappingRecord.provider_company_id == quote.provider_symbol,
            )
        )
        if mapping is None:
            self.session.add(
                InstrumentProviderMappingRecord(
                    instrument_id=instrument.id,
                    provider=provider,
                    provider_symbol=quote.provider_symbol,
                    provider_company_id=quote.provider_symbol,
                    official_name="Bitcoin",
                    source_url=(
                        "https://docs.upbit.com/kr/reference/ticker"
                        if provider is ProviderName.UPBIT
                        else "https://developers.binance.com/"
                    ),
                    fetched_at=quote.fetched_at,
                    verified_at=quote.fetched_at,
                    mapping_status=MappingStatus.VERIFIED,
                    match_method=MappingMatchMethod.EXACT_PROVIDER_SYMBOL,
                    confidence=100,
                    last_checked_at=quote.fetched_at,
                )
            )
        return instrument

    def _record_state(
        self,
        provider: str,
        status: ProviderStatus,
        error_code: str | None,
        request_count: int,
        *,
        configured: bool,
    ) -> None:
        from app.core.time import SystemClock

        now = SystemClock().now()
        state = self.session.get(
            ProviderSyncStateRecord,
            {"provider": provider, "capability": "PUBLIC_QUOTE"},
        )
        if state is None:
            state = ProviderSyncStateRecord(
                provider=provider,
                capability="PUBLIC_QUOTE",
                configured=configured,
                status=status.value,
                consecutive_failures=0,
                request_count=0,
                success_count=0,
            )
            self.session.add(state)
        state.configured = configured
        state.status = status.value
        state.last_attempt_at = now
        state.request_count += request_count
        if status is ProviderStatus.READY:
            state.last_success_at = now
            state.last_error_code = None
            state.consecutive_failures = 0
            state.success_count += 1
        else:
            state.last_error_code = error_code
            state.consecutive_failures += 1

    @staticmethod
    def _fingerprint(instrument_id: str, quote: PublicQuote) -> str:
        value = "|".join(
            [
                instrument_id,
                quote.provider,
                quote.provider_symbol,
                format(quote.price, "f"),
                quote.provider_event_at.isoformat(),
            ]
        )
        return sha256(value.encode()).hexdigest()
