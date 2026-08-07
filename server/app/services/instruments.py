from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.errors import (
    instrument_market_mismatch,
    instrument_not_found,
    portfolio_not_found,
)
from app.core.time import SystemClock
from app.models.database import (
    Currency,
    HoldingStatus,
    PortfolioItemRecord,
    PositionStatus,
    TrackingStatus,
)
from app.models.disclosures import (
    AssetType,
    CollectionRunRecord,
    CollectionRunType,
    CollectionStatus,
    InstrumentRecord,
    InstrumentVerificationStatus,
    MappingMatchMethod,
    MappingStatus,
    ProviderCursorRecord,
    ProviderName,
)
from app.providers.common import ProviderCompany, ProviderFetchResult
from app.repositories.instruments import InstrumentRepository
from app.repositories.portfolio import PortfolioRepository

US_MARKETS = {"US", "NASDAQ", "NYSE", "NYSEARCA", "AMEX"}
KR_MARKETS = {"KR", "KRX", "KOSPI", "KOSDAQ"}


class InstrumentService:
    def __init__(
        self,
        repository: InstrumentRepository,
        portfolio_repository: PortfolioRepository | None = None,
    ) -> None:
        self.repository = repository
        self.portfolios = portfolio_repository

    def get(self, instrument_id: str) -> InstrumentRecord:
        record = self.repository.get(instrument_id)
        if record is None:
            raise instrument_not_found()
        return record

    def available_providers(self, instrument_id: str) -> list[ProviderName]:
        return sorted(
            {mapping.provider for mapping in self.repository.mappings(instrument_id)},
            key=str,
        )

    def map_portfolio(self, portfolio_id: str, instrument_id: str) -> PortfolioItemRecord:
        if self.portfolios is None:
            raise RuntimeError("Portfolio repository is required")
        item = self.portfolios.get_by_id(portfolio_id)
        if item is None:
            raise portfolio_not_found()
        instrument = self.get(instrument_id)
        if not self._compatible(item.market, instrument.market, instrument.exchange):
            raise instrument_market_mismatch()
        if item.instrument_id != instrument.id:
            item.instrument_id = instrument.id
            self.repository.session.flush()
        return item

    def unmap_portfolio(self, portfolio_id: str) -> PortfolioItemRecord:
        if self.portfolios is None:
            raise RuntimeError("Portfolio repository is required")
        item = self.portfolios.get_by_id(portfolio_id)
        if item is None:
            raise portfolio_not_found()
        if item.instrument_id is not None:
            item.instrument_id = None
            self.repository.session.flush()
        return item

    def sync_companies(
        self,
        result: ProviderFetchResult,
        *,
        dry_run: bool = False,
        limit: int = 1000,
        portfolio_id: str | None = None,
        symbol: str | None = None,
    ) -> dict[str, object]:
        if result.error_code or result.status.value != "READY":
            return {
                "status": result.status.value,
                "fetched": 0,
                "created": 0,
                "updated": 0,
                "ambiguous": 0,
                "requestCount": result.request_count,
            }
        counts = {
            "created": 0,
            "updated": 0,
            "ambiguous": 0,
            "verified": 0,
            "unresolved": 0,
            "conflicting": 0,
            "unsupported": 0,
        }
        portfolios = list(
            self.repository.session.scalars(
                select(PortfolioItemRecord).where(PortfolioItemRecord.archived_at.is_(None))
            )
        )
        eligible = [
            item
            for item in portfolios
            if (
                item.position_status is PositionStatus.HOLDING
                or item.tracking_status
                in {TrackingStatus.REENTRY_WATCH, TrackingStatus.WATCHLIST}
                or item.holding_status
                in {
                    HoldingStatus.HOLDING,
                    HoldingStatus.REENTRY_WATCH,
                    HoldingStatus.WATCHLIST,
                }
            )
            and not (
                item.position_status is PositionStatus.CLOSED
                and item.tracking_status is TrackingStatus.NONE
            )
            and (
                result.provider is ProviderName.OPENDART
                and item.market.upper() in KR_MARKETS
                or result.provider is ProviderName.SEC_EDGAR
                and item.market.upper() in US_MARKETS
            )
        ]
        if portfolio_id:
            eligible = [item for item in eligible if item.id == portfolio_id]
        if symbol:
            normalized_symbol = symbol.strip().upper()
            eligible = [item for item in eligible if item.symbol.upper() == normalized_symbol]
        eligible.sort(
            key=lambda item: (
                0
                if item.position_status is PositionStatus.HOLDING
                else 1
                if item.tracking_status is TrackingStatus.REENTRY_WATCH
                or item.holding_status is HoldingStatus.REENTRY_WATCH
                else 2,
                item.market,
                item.symbol,
            )
        )
        eligible = eligible[: min(max(limit, 1), 50)]
        candidate_details: list[dict[str, object]] = []
        for item in eligible:
            candidates = [
                company
                for company in result.companies
                if self._exact_portfolio_match(item, company)
            ]
            status = (
                MappingStatus.VERIFIED
                if len(candidates) == 1
                else MappingStatus.CONFLICTING
                if len(candidates) > 1
                else MappingStatus.UNSUPPORTED
                if item.asset_type is AssetType.ADR
                else MappingStatus.UNRESOLVED
            )
            company = candidates[0] if len(candidates) == 1 else None
            candidate_details.append(
                {
                    "portfolioName": item.name,
                    "symbol": item.symbol,
                    "market": item.market,
                    "officialName": company.company_name if company else None,
                    "corpCode": company.corp_code if company else None,
                    "cik": company.cik if company else None,
                    "matchMethod": (
                        MappingMatchMethod.EXACT_STOCK_CODE.value
                        if company and result.provider is ProviderName.OPENDART
                        else MappingMatchMethod.EXACT_TICKER_EXCHANGE.value
                        if company
                        else MappingMatchMethod.NONE.value
                    ),
                    "status": status.value,
                    "conflictReason": (
                        "MULTIPLE_OFFICIAL_CANDIDATES"
                        if status is MappingStatus.CONFLICTING
                        else "NO_EXACT_OFFICIAL_MATCH"
                        if status is MappingStatus.UNRESOLVED
                        else "ADR_OFFICIAL_IDENTIFIER_NOT_EXACT"
                        if status is MappingStatus.UNSUPPORTED
                        else None
                    ),
                }
            )
            self._sync_portfolio_mapping(
                item,
                result.provider,
                candidates,
                counts,
                dry_run=dry_run,
            )
        output = {
            "status": "DRY_RUN" if dry_run else "SUCCEEDED",
            "fetched": len(result.companies),
            "requestCount": result.request_count,
            "portfolioCandidates": len(eligible),
            "candidateDetails": candidate_details,
            **counts,
        }
        if not dry_run:
            now = max(
                (company.fetched_at for company in result.companies[:limit]),
                default=SystemClock().now(),
            )
            cursor = self.repository.session.get(
                ProviderCursorRecord,
                {
                    "provider": result.provider,
                    "scope": "instrument-master",
                },
            )
            before = cursor.cursor_value if cursor else None
            if cursor is None:
                cursor = ProviderCursorRecord(
                    provider=result.provider,
                    scope="instrument-master",
                )
                self.repository.session.add(cursor)
            cursor.cursor_value = now.isoformat()
            cursor.last_attempt_at = now
            cursor.last_successful_at = now
            cursor.overlap_window_start = now
            self.repository.session.add(
                CollectionRunRecord(
                    provider=result.provider,
                    run_type=CollectionRunType.INSTRUMENT_SYNC,
                    started_at=now,
                    finished_at=now,
                    status=CollectionStatus.SUCCEEDED,
                    fetched_count=int(output["fetched"]),
                    created_count=counts["created"],
                    updated_count=counts["updated"],
                    error_count=counts["ambiguous"],
                    cursor_before=before,
                    cursor_after=cursor.cursor_value,
                    result_details=output,
                )
            )
            self.repository.session.flush()
        return output

    def _sync_portfolio_mapping(
        self,
        portfolio: PortfolioItemRecord,
        provider: ProviderName,
        candidates: list[ProviderCompany],
        counts: dict[str, int],
        *,
        dry_run: bool,
    ) -> None:
        status = (
            MappingStatus.VERIFIED
            if len(candidates) == 1
            else MappingStatus.CONFLICTING
            if len(candidates) > 1
            else MappingStatus.UNSUPPORTED
            if portfolio.asset_type is AssetType.ADR
            else MappingStatus.UNRESOLVED
        )
        counts[status.value.lower()] += 1
        if dry_run or status is MappingStatus.UNSUPPORTED:
            return
        instrument = self.repository.get_active(portfolio.market, portfolio.symbol)
        now = candidates[0].fetched_at if candidates else SystemClock().now()
        if instrument is None:
            instrument = self.repository.create(
                {
                    "canonical_symbol": portfolio.symbol,
                    "display_name": portfolio.name,
                    "exchange": portfolio.market,
                    "market": portfolio.market,
                    "country": "KR" if provider is ProviderName.OPENDART else "US",
                    "currency": portfolio.currency,
                    "asset_type": portfolio.asset_type,
                    "verification_status": (
                        InstrumentVerificationStatus.VERIFIED
                        if status is MappingStatus.VERIFIED
                        else InstrumentVerificationStatus.AMBIGUOUS
                        if status is MappingStatus.CONFLICTING
                        else InstrumentVerificationStatus.UNVERIFIED
                    ),
                    "verification_source": (
                        provider.value if status is MappingStatus.VERIFIED else None
                    ),
                    "verified_at": now if status is MappingStatus.VERIFIED else None,
                }
            )
            counts["created"] += 1
        else:
            counts["updated"] += 1
        company = candidates[0] if len(candidates) == 1 else None
        company_id = (
            company.provider_company_id
            if company
            else f"{status.value}:{portfolio.market}:{portfolio.symbol}"
        )
        mapping = self.repository.mapping_by_company(provider, company_id)
        values = {
            "instrument_id": instrument.id,
            "provider": provider,
            "provider_symbol": company.symbol if company else portfolio.symbol,
            "provider_company_id": company_id,
            "cik": company.cik if company else None,
            "corp_code": company.corp_code if company else None,
            "stock_code": company.stock_code if company else None,
            "official_name": company.company_name if company else None,
            "source_url": company.source_url
            if company
            else (
                "https://opendart.fss.or.kr/guide/main.do"
                if provider is ProviderName.OPENDART
                else "https://www.sec.gov/about/developer-resources"
            ),
            "source_updated_at": company.source_updated_at if company else None,
            "fetched_at": now,
            "verified_at": now if company else None,
            "mapping_status": status,
            "match_method": (
                MappingMatchMethod.EXACT_STOCK_CODE
                if company and provider is ProviderName.OPENDART
                else MappingMatchMethod.EXACT_TICKER_EXCHANGE
                if company
                else MappingMatchMethod.NONE
            ),
            "confidence": 100 if company else 0,
            "last_checked_at": now,
            "conflict_reason": (
                "MULTIPLE_OFFICIAL_CANDIDATES"
                if status is MappingStatus.CONFLICTING
                else "NO_EXACT_OFFICIAL_MATCH"
                if status is MappingStatus.UNRESOLVED
                else None
            ),
        }
        if mapping is None:
            self.repository.create_mapping(values)
        else:
            self.repository.update_mapping(mapping, values)

    @staticmethod
    def _exact_portfolio_match(
        portfolio: PortfolioItemRecord, company: ProviderCompany
    ) -> bool:
        if company.provider is ProviderName.OPENDART:
            return bool(company.stock_code and company.stock_code == portfolio.symbol)
        exchange = (company.exchange or "").upper()
        market = portfolio.market.upper()
        return company.symbol.upper() == portfolio.symbol.upper() and (
            exchange == market
            or market == "NASDAQ"
            and exchange in {"NASDAQ", "NASDAQ GLOBAL SELECT"}
            or market == "NYSE"
            and exchange.startswith("NYSE")
            or market == "AMEX"
            and exchange in {"AMEX", "NYSE AMERICAN"}
        )

    def _sync_company(
        self, company: ProviderCompany, counts: dict[str, int], *, dry_run: bool
    ) -> None:
        market = self._market(company)
        symbol = company.symbol.upper()
        existing = self.repository.get_active(market, symbol)
        mapped = self.repository.mapping_by_company(
            company.provider, company.provider_company_id
        )
        if mapped and mapped.instrument_id != (existing.id if existing else None):
            if not dry_run:
                target = self.repository.get(mapped.instrument_id)
                if target:
                    self.repository.update(
                        target,
                        {"verification_status": InstrumentVerificationStatus.AMBIGUOUS},
                    )
            counts["ambiguous"] += 1
            return
        now = company.fetched_at
        if existing is None:
            counts["created"] += 1
            if dry_run:
                return
            try:
                existing = self.repository.create(
                    {
                        "canonical_symbol": symbol,
                        "display_name": company.company_name,
                        "exchange": company.exchange,
                        "market": market,
                        "country": "KR" if company.provider is ProviderName.OPENDART else "US",
                        "currency": (
                            Currency.KRW
                            if company.provider is ProviderName.OPENDART
                            else Currency.USD
                        ),
                        "asset_type": AssetType.EQUITY,
                        "verification_status": InstrumentVerificationStatus.VERIFIED,
                        "verification_source": company.provider.value,
                        "verified_at": now,
                    }
                )
            except IntegrityError:
                counts["ambiguous"] += 1
                return
        else:
            counts["updated"] += 1
            if dry_run:
                return
            self.repository.update(
                existing,
                {
                    "display_name": company.company_name,
                    "exchange": company.exchange,
                    "verification_status": InstrumentVerificationStatus.VERIFIED,
                    "verification_source": company.provider.value,
                    "verified_at": now,
                },
            )
        if mapped is None:
            self.repository.create_mapping(
                {
                    "instrument_id": existing.id,
                    "provider": company.provider,
                    "provider_symbol": symbol,
                    "provider_company_id": company.provider_company_id,
                    "cik": company.cik,
                    "corp_code": company.corp_code,
                    "stock_code": company.stock_code,
                    "source_url": company.source_url,
                    "source_updated_at": company.source_updated_at,
                    "fetched_at": now,
                    "verified_at": now,
                }
            )

    @staticmethod
    def _market(company: ProviderCompany) -> str:
        if company.provider is ProviderName.OPENDART:
            return (company.exchange or "KRX").upper()
        return (company.exchange or "US").upper()

    @staticmethod
    def _compatible(left: str, right: str, exchange: str | None) -> bool:
        values = {left.upper(), right.upper(), (exchange or "").upper()}
        return (
            left.upper() == right.upper()
            or bool(values & US_MARKETS)
            and bool({left.upper(), right.upper()} <= US_MARKETS)
            or bool(values & KR_MARKETS)
            and bool({left.upper(), right.upper()} <= KR_MARKETS)
        )
