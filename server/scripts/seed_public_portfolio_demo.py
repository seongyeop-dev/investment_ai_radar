#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.models.analysis import (
    DecisionReviewRecord,
    EconomicEventRecord,
    InvestmentThesisRecord,
    PortfolioImpactRecord,
)
from app.models.analyst_references import (
    AnalystAccessType,
    AnalystDocumentType,
    AnalystFreshnessStatus,
    AnalystIngestMode,
    AnalystMappingConfidence,
    AnalystPublisherType,
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
    AnalystRelationType,
    AnalystTranslationStatus,
    AnalystUserState,
    ReferenceDiscoveryCandidateRecord,
    ReferenceDiscoveryCandidateReviewAction,
    ReferenceDiscoveryCandidateReviewRecord,
    ReferenceDiscoveryCandidateStatus,
)
from app.models.contracts import SourceGrade, VerificationStatus
from app.models.database import (
    AssetType,
    AveragingDownPolicy,
    Currency,
    HoldingStatus,
    InvestmentHorizon,
    PortfolioItemRecord,
    PositionStatus,
    PositionTransactionRecord,
    PositionTransactionStatus,
    PositionTransactionType,
    PrimaryGoal,
    RecommendationMode,
    RiskProfileRecord,
    RiskProfileSource,
    RiskStyle,
    SaleTransactionRecord,
    SaleTransactionStatus,
    SaleTransactionType,
    SourceRecord,
    TrackingStatus,
    TransactionSide,
    TransactionSourceType,
)
from app.models.disclosures import (
    CertaintyLevel,
    DisclosureRecord,
    InformationEventRecord,
    InstrumentRecord,
    LifecycleStatus,
    NewsClaimRecord,
    NewsProviderType,
    NewsReferenceRecord,
    NewsSummaryStatus,
    ProviderName,
    SummaryStatus,
)
from app.models.market_data import MarketSessionCacheRecord, ProviderSyncStateRecord
from app.models.operations import (
    BriefingItemRecord,
    BriefingRecord,
    BriefingStatus,
    BriefingType,
)
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubjectType,
    ReferenceSubscriptionRecord,
)

EXPECTED_REVISION = "20260803_0017"
DEMO_FILE_NAME = "public_demo.db"
DEMO_MARKER_DOMAIN = "public-demo.example.invalid"
DEMO_NAMESPACE = f"https://{DEMO_MARKER_DOMAIN}/investment-ai-radar"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed an isolated public portfolio demo database."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--expected-demo-root", required=True)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required confirmation for writing the public demo database.",
    )
    return parser.parse_args()


def stable_id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{DEMO_NAMESPACE}/{name}"))


def fingerprint(*parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sqlite_path(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        raise RuntimeError("Public demo seed accepts SQLite only.")

    raw = url.database
    if not raw or raw == ":memory:":
        raise RuntimeError("A file-backed SQLite demo database is required.")

    return Path(unquote(raw)).expanduser().resolve()


def validate_target(database_url: str, expected_root: Path) -> Path:
    database_path = sqlite_path(database_url)
    expected_root = expected_root.expanduser().resolve()

    if database_path.name != DEMO_FILE_NAME:
        raise RuntimeError(f"Unexpected demo database name: {database_path.name!r}")

    if database_path.parent != expected_root:
        raise RuntimeError(
            "The demo database must be created directly under the expected demo root."
        )

    return database_path


def check_revision(session: Session) -> None:
    revision = session.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one_or_none()

    if revision != EXPECTED_REVISION:
        raise RuntimeError(
            f"Unexpected Alembic revision: {revision!r}; expected {EXPECTED_REVISION!r}."
        )


def require_empty_or_seeded(session: Session) -> str:
    marker = session.scalar(
        select(SourceRecord).where(SourceRecord.domain == DEMO_MARKER_DOMAIN)
    )
    if marker is not None:
        return "already_seeded"

    guarded_models = (
        PortfolioItemRecord,
        InstrumentRecord,
        SourceRecord,
        InformationEventRecord,
        DisclosureRecord,
        NewsReferenceRecord,
        AnalystReferenceRecord,
        ReferenceDiscoveryCandidateRecord,
        BriefingRecord,
    )

    populated = [
        model.__tablename__
        for model in guarded_models
        if session.scalar(select(model.id).limit(1)) is not None
    ]
    if populated:
        raise RuntimeError(
            "The target database contains non-demo data. "
            f"Refusing to seed tables: {', '.join(populated)}"
        )

    return "empty"


def seed(session: Session) -> dict[str, int]:
    now = datetime.now(UTC).replace(microsecond=0)
    day = timedelta(days=1)

    ids = {
        name: stable_id(name)
        for name in (
            "instrument-semiconductor",
            "instrument-mobility",
            "instrument-space",
            "portfolio-semiconductor",
            "portfolio-mobility",
            "portfolio-space",
            "tx-semiconductor-buy",
            "tx-semiconductor-sell",
            "tx-mobility-buy",
            "sale-semiconductor",
            "source-public-research",
            "source-demo-ir",
            "subscription-public-research",
            "reference-promoted",
            "reference-manual",
            "coverage-promoted",
            "candidate-promoted",
            "candidate-unverified",
            "candidate-dismissed",
            "history-promoted-verify",
            "history-promoted-promote",
            "history-dismissed",
            "event-semiconductor",
            "event-mobility",
            "disclosure-semiconductor",
            "news-semiconductor",
            "news-mobility",
            "claim-semiconductor",
            "claim-mobility",
            "thesis-semiconductor",
            "thesis-mobility",
            "impact-semiconductor",
            "impact-mobility",
            "decision-semiconductor",
            "decision-mobility",
            "briefing-krx",
            "briefing-daily",
            "briefing-item-semiconductor",
            "briefing-item-mobility",
            "economic-rate",
            "economic-export",
            "market-session-krx",
            "market-session-nasdaq",
        )
    }

    instruments = [
        InstrumentRecord(
            id=ids["instrument-semiconductor"],
            canonical_symbol="DEMO-KR1",
            display_name="Demo Semiconductor Holdings",
            local_name="공개 데모 반도체",
            exchange="KRX",
            market="KRX",
            country="KR",
            currency=Currency.KRW,
            asset_type=AssetType.EQUITY,
            active=True,
            verification_status="VERIFIED",
            verification_source="PUBLIC_DEMO_FIXTURE",
            verified_at=now - 30 * day,
            created_at=now - 60 * day,
            updated_at=now,
        ),
        InstrumentRecord(
            id=ids["instrument-mobility"],
            canonical_symbol="DEMO-KR2P",
            display_name="Demo Mobility Preferred",
            local_name="공개 데모 모빌리티 우선주",
            exchange="KRX",
            market="KRX",
            country="KR",
            currency=Currency.KRW,
            asset_type=AssetType.EQUITY,
            active=True,
            verification_status="VERIFIED",
            verification_source="PUBLIC_DEMO_FIXTURE",
            verified_at=now - 30 * day,
            created_at=now - 60 * day,
            updated_at=now,
        ),
        InstrumentRecord(
            id=ids["instrument-space"],
            canonical_symbol="DEMO-US1",
            display_name="Demo Space Systems",
            local_name="공개 데모 우주 시스템",
            exchange="NASDAQ",
            market="NASDAQ",
            country="US",
            currency=Currency.USD,
            asset_type=AssetType.EQUITY,
            active=True,
            verification_status="VERIFIED",
            verification_source="PUBLIC_DEMO_FIXTURE",
            verified_at=now - 30 * day,
            created_at=now - 60 * day,
            updated_at=now,
        ),
    ]
    session.add_all(instruments)
    session.flush()

    portfolios = [
        PortfolioItemRecord(
            id=ids["portfolio-semiconductor"],
            instrument_id=ids["instrument-semiconductor"],
            symbol="DEMO-KR1",
            name="공개 데모 반도체",
            market="KRX",
            currency=Currency.KRW,
            asset_type=AssetType.EQUITY,
            holding_status=HoldingStatus.HOLDING,
            position_status=PositionStatus.HOLDING,
            tracking_status=TrackingStatus.NONE,
            quantity=Decimal("10"),
            average_price=Decimal("70000"),
            investment_horizon=InvestmentHorizon.MEDIUM,
            strategy="공식 공시와 수요 지표를 함께 확인하는 공개 데모 전략",
            target_allocation=Decimal("35"),
            max_loss_percent=Decimal("12"),
            notes="공개 예시 데이터입니다.",
            created_at=now - 45 * day,
            updated_at=now,
        ),
        PortfolioItemRecord(
            id=ids["portfolio-mobility"],
            instrument_id=ids["instrument-mobility"],
            symbol="DEMO-KR2P",
            name="공개 데모 모빌리티 우선주",
            market="KRX",
            currency=Currency.KRW,
            asset_type=AssetType.EQUITY,
            holding_status=HoldingStatus.HOLDING,
            position_status=PositionStatus.HOLDING,
            tracking_status=TrackingStatus.NONE,
            quantity=Decimal("5"),
            average_price=Decimal("110000"),
            investment_horizon=InvestmentHorizon.LONG,
            strategy="배당과 산업 전환 이벤트를 점검하는 공개 데모 전략",
            target_allocation=Decimal("25"),
            max_loss_percent=Decimal("15"),
            notes="공개 예시 데이터입니다.",
            created_at=now - 35 * day,
            updated_at=now,
        ),
        PortfolioItemRecord(
            id=ids["portfolio-space"],
            instrument_id=ids["instrument-space"],
            symbol="DEMO-US1",
            name="공개 데모 우주 시스템",
            market="NASDAQ",
            currency=Currency.USD,
            asset_type=AssetType.EQUITY,
            holding_status=HoldingStatus.WATCHLIST,
            position_status=PositionStatus.EMPTY,
            tracking_status=TrackingStatus.WATCHLIST,
            quantity=Decimal("0"),
            average_price=None,
            investment_horizon=InvestmentHorizon.LONG,
            strategy="고변동성 자산의 이벤트와 현금흐름을 검토하는 공개 데모 전략",
            target_allocation=Decimal("10"),
            max_loss_percent=Decimal("20"),
            notes="실제 종목이 아닌 공개 예시 데이터입니다.",
            created_at=now - 20 * day,
            updated_at=now,
        ),
    ]
    session.add_all(portfolios)
    session.flush()

    transactions = [
        PositionTransactionRecord(
            id=ids["tx-semiconductor-buy"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            transaction_side=TransactionSide.BUY,
            transaction_type=PositionTransactionType.OPENING_BALANCE,
            traded_at=now - 40 * day,
            quantity=Decimal("12"),
            unit_price=Decimal("70000"),
            currency=Currency.KRW,
            fee_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            gross_amount=Decimal("840000"),
            quantity_before=Decimal("0"),
            quantity_after=Decimal("12"),
            average_price_before=None,
            average_price_after=Decimal("70000"),
            realized_pnl=None,
            realized_return_percent=None,
            sequence_number=1,
            source_type=TransactionSourceType.USER_ENTRY,
            status=PositionTransactionStatus.ACTIVE,
            voided_at=None,
            void_reason=None,
            notes="공개 데모 최초 매수",
            idempotency_key=fingerprint("demo", "semiconductor", "buy", 1),
            created_at=now - 40 * day,
            updated_at=now - 40 * day,
        ),
        PositionTransactionRecord(
            id=ids["tx-semiconductor-sell"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            transaction_side=TransactionSide.SELL,
            transaction_type=PositionTransactionType.NORMAL,
            traded_at=now - 10 * day,
            quantity=Decimal("2"),
            unit_price=Decimal("82000"),
            currency=Currency.KRW,
            fee_amount=Decimal("100"),
            tax_amount=Decimal("200"),
            gross_amount=Decimal("164000"),
            quantity_before=Decimal("12"),
            quantity_after=Decimal("10"),
            average_price_before=Decimal("70000"),
            average_price_after=Decimal("70000"),
            realized_pnl=Decimal("23700"),
            realized_return_percent=Decimal("16.93"),
            sequence_number=2,
            source_type=TransactionSourceType.USER_ENTRY,
            status=PositionTransactionStatus.ACTIVE,
            voided_at=None,
            void_reason=None,
            notes="공개 데모 일부 매도",
            idempotency_key=fingerprint("demo", "semiconductor", "sell", 2),
            created_at=now - 10 * day,
            updated_at=now - 10 * day,
        ),
        PositionTransactionRecord(
            id=ids["tx-mobility-buy"],
            portfolio_item_id=ids["portfolio-mobility"],
            transaction_side=TransactionSide.BUY,
            transaction_type=PositionTransactionType.OPENING_BALANCE,
            traded_at=now - 30 * day,
            quantity=Decimal("5"),
            unit_price=Decimal("110000"),
            currency=Currency.KRW,
            fee_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            gross_amount=Decimal("550000"),
            quantity_before=Decimal("0"),
            quantity_after=Decimal("5"),
            average_price_before=None,
            average_price_after=Decimal("110000"),
            realized_pnl=None,
            realized_return_percent=None,
            sequence_number=1,
            source_type=TransactionSourceType.USER_ENTRY,
            status=PositionTransactionStatus.ACTIVE,
            voided_at=None,
            void_reason=None,
            notes="공개 데모 최초 매수",
            idempotency_key=fingerprint("demo", "mobility", "buy", 1),
            created_at=now - 30 * day,
            updated_at=now - 30 * day,
        ),
    ]
    session.add_all(transactions)
    session.flush()

    session.add(
        SaleTransactionRecord(
            id=ids["sale-semiconductor"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            ledger_transaction_id=ids["tx-semiconductor-sell"],
            transaction_type=SaleTransactionType.PARTIAL_SALE,
            sold_at=now - 10 * day,
            quantity=Decimal("2"),
            sale_price=Decimal("82000"),
            purchase_average_price_snapshot=Decimal("70000"),
            currency=Currency.KRW,
            fee_amount=Decimal("100"),
            tax_amount=Decimal("200"),
            gross_proceeds=Decimal("164000"),
            cost_basis=Decimal("140000"),
            realized_pnl=Decimal("23700"),
            realized_return_percent=Decimal("16.93"),
            quantity_before=Decimal("12"),
            quantity_after=Decimal("10"),
            historical_import=False,
            notes="공개 데모 일부 매도 원장",
            status=SaleTransactionStatus.ACTIVE,
            voided_at=None,
            void_reason=None,
            created_at=now - 10 * day,
            updated_at=now - 10 * day,
        )
    )

    sources = [
        SourceRecord(
            id=ids["source-public-research"],
            name="Public Demo Research Lab",
            source_type="PUBLIC_RESEARCH",
            source_grade=SourceGrade.B,
            domain=DEMO_MARKER_DOMAIN,
            official=False,
            enabled=True,
            feed_url=f"https://{DEMO_MARKER_DOMAIN}/research/feed.xml",
            provider_type="RSS",
            language="ko",
            request_interval_seconds=3600,
            timeout_seconds=10,
            max_items=20,
            original_source_name="Public Demo Research Lab",
            created_at=now - 20 * day,
            updated_at=now,
        ),
        SourceRecord(
            id=ids["source-demo-ir"],
            name="Public Demo Official IR",
            source_type="OFFICIAL_IR",
            source_grade=SourceGrade.A,
            domain="ir.public-demo.example.invalid",
            official=True,
            enabled=True,
            feed_url="https://ir.public-demo.example.invalid/feed.xml",
            provider_type="OFFICIAL_IR_FEED",
            language="ko",
            request_interval_seconds=3600,
            timeout_seconds=10,
            max_items=20,
            original_source_name="Public Demo Official IR",
            created_at=now - 20 * day,
            updated_at=now,
        ),
    ]
    session.add_all(sources)
    session.flush()

    subscription = ReferenceSubscriptionRecord(
        id=ids["subscription-public-research"],
        source_id=ids["source-public-research"],
        subject_type=ReferenceSubjectType.INSTITUTION,
        display_name="Public Demo Research Lab",
        match_mode=ReferenceMatchMode.KEYWORD,
        match_terms=["DEMO-KR1", "DEMO-KR2P", "반도체", "모빌리티"],
        enabled=True,
        created_at=now - 15 * day,
        updated_at=now,
    )
    session.add(subscription)
    session.flush()

    promoted_reference = AnalystReferenceRecord(
        id=ids["reference-promoted"],
        source_id=ids["source-public-research"],
        subscription_id=ids["subscription-public-research"],
        provider_item_id="public-demo-reference-001",
        ingest_mode=AnalystIngestMode.AUTOMATIC,
        user_state=AnalystUserState.READ,
        discovered_at=now - 7 * day,
        publisher_name="Public Demo Research Lab",
        publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
        title="공개 데모 반도체 수요 점검",
        analyst_name="Demo Analyst",
        published_at=now - 8 * day,
        canonical_url=f"https://{DEMO_MARKER_DOMAIN}/research/semiconductor-demand",
        access_type=AnalystAccessType.PUBLIC,
        document_type=AnalystDocumentType.REPORT,
        publisher_rating_raw="관찰",
        publisher_target_price_raw=None,
        target_currency="KRW",
        public_abstract="공개 예시 데이터로 작성한 반도체 수요 점검 자료입니다.",
        source_language="ko",
        translated_title_ko=None,
        translated_abstract_ko=None,
        translation_status=AnalystTranslationStatus.NOT_NEEDED,
        translation_provider=None,
        translation_error=None,
        translated_at=None,
        source_retrieved_at=now - 7 * day,
        source_fingerprint=fingerprint("reference", "semiconductor-demand"),
        freshness_status=AnalystFreshnessStatus.CURRENT,
        is_active=True,
        created_at=now - 7 * day,
        updated_at=now,
    )
    manual_reference = AnalystReferenceRecord(
        id=ids["reference-manual"],
        source_id=None,
        subscription_id=None,
        provider_item_id=None,
        ingest_mode=AnalystIngestMode.MANUAL,
        user_state=AnalystUserState.NEW,
        discovered_at=now - 4 * day,
        publisher_name="Public Demo Official IR",
        publisher_type=AnalystPublisherType.INSTITUTION,
        title="공개 데모 모빌리티 사업 업데이트",
        analyst_name=None,
        published_at=now - 4 * day,
        canonical_url="https://ir.public-demo.example.invalid/mobility-update",
        access_type=AnalystAccessType.PUBLIC,
        document_type=AnalystDocumentType.COMMENTARY,
        publisher_rating_raw=None,
        publisher_target_price_raw=None,
        target_currency=None,
        public_abstract="실제 기업 자료가 아닌 공개 데모용 사업 업데이트입니다.",
        source_language="ko",
        translated_title_ko=None,
        translated_abstract_ko=None,
        translation_status=AnalystTranslationStatus.NOT_NEEDED,
        translation_provider=None,
        translation_error=None,
        translated_at=None,
        source_retrieved_at=now - 4 * day,
        source_fingerprint=fingerprint("reference", "mobility-update"),
        freshness_status=AnalystFreshnessStatus.CURRENT,
        is_active=True,
        created_at=now - 4 * day,
        updated_at=now,
    )
    session.add_all([promoted_reference, manual_reference])
    session.flush()

    session.add(
        AnalystReferenceCoverageRecord(
            id=ids["coverage-promoted"],
            analyst_reference_id=ids["reference-promoted"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            relation_type=AnalystRelationType.PRIMARY,
            mapping_confidence=AnalystMappingConfidence.VERIFIED,
            human_review_required=False,
            created_at=now - 7 * day,
        )
    )

    candidates = [
        ReferenceDiscoveryCandidateRecord(
            id=ids["candidate-promoted"],
            source_id=ids["source-public-research"],
            subscription_id=ids["subscription-public-research"],
            provider_item_id="candidate-promoted-001",
            publisher_name="Public Demo Research Lab",
            title="공개 데모 반도체 수요 점검",
            analyst_name="Demo Analyst",
            canonical_url=f"https://{DEMO_MARKER_DOMAIN}/research/semiconductor-demand",
            published_at=now - 8 * day,
            verification_status=ReferenceDiscoveryCandidateStatus.PROMOTED,
            first_seen_at=now - 9 * day,
            last_seen_at=now - 7 * day,
            seen_count=2,
            public_abstract="검토 후 정식 참고자료로 승격된 공개 데모 후보입니다.",
            publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
            access_type=AnalystAccessType.PUBLIC,
            document_type=AnalystDocumentType.REPORT,
            promoted_reference_id=ids["reference-promoted"],
            reviewed_at=now - 7 * day,
            created_at=now - 9 * day,
            updated_at=now - 7 * day,
        ),
        ReferenceDiscoveryCandidateRecord(
            id=ids["candidate-unverified"],
            source_id=ids["source-public-research"],
            subscription_id=ids["subscription-public-research"],
            provider_item_id="candidate-unverified-002",
            publisher_name="Public Demo Research Lab",
            title="공개 데모 모빌리티 공급망 메모",
            analyst_name="Demo Analyst B",
            canonical_url=f"https://{DEMO_MARKER_DOMAIN}/research/mobility-supply-chain",
            published_at=None,
            verification_status=ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED,
            first_seen_at=now - 2 * day,
            last_seen_at=now - 1 * day,
            seen_count=2,
            public_abstract="발행일 확인이 필요한 공개 데모 후보입니다.",
            publisher_type=AnalystPublisherType.RESEARCH_HOUSE,
            access_type=AnalystAccessType.PUBLIC,
            document_type=AnalystDocumentType.COMMENTARY,
            promoted_reference_id=None,
            reviewed_at=None,
            created_at=now - 2 * day,
            updated_at=now - 1 * day,
        ),
        ReferenceDiscoveryCandidateRecord(
            id=ids["candidate-dismissed"],
            source_id=ids["source-public-research"],
            subscription_id=ids["subscription-public-research"],
            provider_item_id="candidate-dismissed-003",
            publisher_name="Public Demo Research Lab",
            title="공개 데모 중복 자료",
            analyst_name=None,
            canonical_url=f"https://{DEMO_MARKER_DOMAIN}/research/duplicate-note",
            published_at=now - 6 * day,
            verification_status=ReferenceDiscoveryCandidateStatus.DISMISSED,
            first_seen_at=now - 6 * day,
            last_seen_at=now - 5 * day,
            seen_count=1,
            public_abstract="중복으로 검토 제외된 공개 데모 후보입니다.",
            publisher_type=AnalystPublisherType.INSTITUTION,
            access_type=AnalystAccessType.PUBLIC,
            document_type=AnalystDocumentType.OTHER,
            promoted_reference_id=None,
            reviewed_at=now - 5 * day,
            created_at=now - 6 * day,
            updated_at=now - 5 * day,
        ),
    ]
    session.add_all(candidates)
    session.flush()

    session.add_all(
        [
            ReferenceDiscoveryCandidateReviewRecord(
                id=ids["history-promoted-verify"],
                candidate_id=ids["candidate-promoted"],
                action=ReferenceDiscoveryCandidateReviewAction.VERIFY_DATE,
                previous_status=ReferenceDiscoveryCandidateStatus.DATE_UNVERIFIED,
                new_status=ReferenceDiscoveryCandidateStatus.DATE_VERIFIED,
                verified_published_at=now - 8 * day,
                promoted_reference_id=None,
                reason=None,
                created_at=now - 7 * day - timedelta(minutes=2),
            ),
            ReferenceDiscoveryCandidateReviewRecord(
                id=ids["history-promoted-promote"],
                candidate_id=ids["candidate-promoted"],
                action=ReferenceDiscoveryCandidateReviewAction.PROMOTE,
                previous_status=ReferenceDiscoveryCandidateStatus.DATE_VERIFIED,
                new_status=ReferenceDiscoveryCandidateStatus.PROMOTED,
                verified_published_at=now - 8 * day,
                promoted_reference_id=ids["reference-promoted"],
                reason=None,
                created_at=now - 7 * day,
            ),
            ReferenceDiscoveryCandidateReviewRecord(
                id=ids["history-dismissed"],
                candidate_id=ids["candidate-dismissed"],
                action=ReferenceDiscoveryCandidateReviewAction.DISMISS,
                previous_status=ReferenceDiscoveryCandidateStatus.DATE_VERIFIED,
                new_status=ReferenceDiscoveryCandidateStatus.DISMISSED,
                verified_published_at=now - 6 * day,
                promoted_reference_id=None,
                reason="공개 데모 중복 자료",
                created_at=now - 5 * day,
            ),
        ]
    )

    events = [
        InformationEventRecord(
            id=ids["event-semiconductor"],
            event_key="PUBLIC_DEMO_SEMICONDUCTOR_EVENT",
            instrument_id=ids["instrument-semiconductor"],
            event_type="OFFICIAL_DISCLOSURE",
            normalized_claim="공개 데모 반도체 설비 투자 계획이 발표되었습니다.",
            claim_fingerprint=fingerprint("event", "semiconductor"),
            first_seen_at=now - 5 * day,
            last_seen_at=now - 3 * day,
            latest_material_change_at=now - 3 * day,
            lifecycle_status=LifecycleStatus.ACTIVE,
            verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
            source_count=2,
            official_source_count=1,
            news_reference_count=1,
            independent_origin_count=2,
            stale_reuse_count=0,
            latest_news_at=now - 3 * day,
            latest_official_at=now - 5 * day,
            changed_facts=[{"field": "investment_plan", "before": "검토", "after": "발표"}],
            corrected_at=None,
            denied_at=None,
            current_summary="설비 투자 계획이 공식 확인된 공개 데모 사건입니다.",
            material_change=True,
            pinned=True,
            created_at=now - 5 * day,
            updated_at=now,
        ),
        InformationEventRecord(
            id=ids["event-mobility"],
            event_key="PUBLIC_DEMO_MOBILITY_EVENT",
            instrument_id=ids["instrument-mobility"],
            event_type="SUPPLY_CHAIN",
            normalized_claim="공개 데모 모빌리티 공급망 비용 변동 가능성이 제기되었습니다.",
            claim_fingerprint=fingerprint("event", "mobility"),
            first_seen_at=now - 3 * day,
            last_seen_at=now - 1 * day,
            latest_material_change_at=None,
            lifecycle_status=LifecycleStatus.ACTIVE,
            verification_status=VerificationStatus.NEEDS_VERIFICATION,
            source_count=1,
            official_source_count=0,
            news_reference_count=1,
            independent_origin_count=1,
            stale_reuse_count=0,
            latest_news_at=now - 1 * day,
            latest_official_at=None,
            changed_facts=[],
            corrected_at=None,
            denied_at=None,
            current_summary="공식 확인이 필요한 공개 데모 공급망 사건입니다.",
            material_change=False,
            pinned=False,
            created_at=now - 3 * day,
            updated_at=now,
        ),
    ]
    session.add_all(events)
    session.flush()

    disclosure = DisclosureRecord(
        id=ids["disclosure-semiconductor"],
        instrument_id=ids["instrument-semiconductor"],
        event_id=ids["event-semiconductor"],
        provider=ProviderName.OPENDART,
        provider_document_id="PUBLIC-DEMO-DART-001",
        accession_number=None,
        receipt_number="PUBLIC-DEMO-RECEIPT-001",
        form_type=None,
        report_type="주요사항보고서",
        title="[공개 데모] 설비 투자 계획",
        company_name="Demo Semiconductor Holdings",
        official_url="https://disclosure.public-demo.example.invalid/semiconductor-investment",
        published_at=now - 5 * day,
        source_updated_at=now - 4 * day,
        first_seen_at=now - 5 * day,
        fetched_at=now - 5 * day,
        verified_at=now - 5 * day,
        verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
        source_grade=SourceGrade.A,
        content_fingerprint=fingerprint("disclosure", "semiconductor"),
        metadata_hash=fingerprint("metadata", "semiconductor"),
        summary="실제 공시가 아닌 공개 데모용 설비 투자 계획입니다.",
        summary_status=SummaryStatus.STRUCTURED,
        key_facts=[
            {"label": "상태", "value": "공개 데모"},
            {"label": "검증", "value": "fixture"},
        ],
        material_change=True,
        correction_of_id=None,
        lifecycle_status=LifecycleStatus.ACTIVE,
        pinned=True,
        created_at=now - 5 * day,
        updated_at=now,
    )
    session.add(disclosure)
    session.flush()

    news = [
        NewsReferenceRecord(
            id=ids["news-semiconductor"],
            instrument_id=ids["instrument-semiconductor"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            source_id=ids["source-demo-ir"],
            provider=NewsProviderType.MANUAL_REFERENCE,
            provider_item_id="public-demo-news-001",
            title="[공개 데모] 반도체 투자 계획 후속 점검",
            normalized_title="공개 데모 반도체 투자 계획 후속 점검",
            source_name="Public Demo Official IR",
            source_domain="ir.public-demo.example.invalid",
            canonical_url="https://ir.public-demo.example.invalid/news/semiconductor-follow-up",
            canonical_url_hash=fingerprint("url", "semiconductor-follow-up"),
            original_url="https://ir.public-demo.example.invalid/news/semiconductor-follow-up",
            published_at=now - 3 * day,
            source_updated_at=None,
            first_seen_at=now - 3 * day,
            last_seen_at=now - 3 * day,
            fetched_at=now - 3 * day,
            verified_at=now - 3 * day,
            language="ko",
            snippet="공식 발표 이후 점검을 위한 공개 데모 뉴스입니다.",
            short_summary="공식 발표와 일치하는 후속 공개 데모 자료입니다.",
            summary_status=NewsSummaryStatus.OFFICIAL_REFERENCE_BASED,
            primary_claim="설비 투자 계획이 유지되고 있습니다.",
            claim_fingerprint=fingerprint("claim", "semiconductor"),
            content_fingerprint=fingerprint("content", "semiconductor-news"),
            verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
            source_grade=SourceGrade.A,
            trust_score=92,
            certainty_level=CertaintyLevel.CONFIRMED,
            independent_origin=True,
            original_origin_key="PUBLIC_DEMO_IR_SEMICONDUCTOR",
            duplicate_of_id=None,
            information_event_id=ids["event-semiconductor"],
            material_change=True,
            stale_reused=False,
            lifecycle_status=LifecycleStatus.ACTIVE,
            official_reference_ids=[ids["disclosure-semiconductor"]],
            changed_facts=[{"field": "status", "value": "유지"}],
            pinned=True,
            created_at=now - 3 * day,
            updated_at=now,
        ),
        NewsReferenceRecord(
            id=ids["news-mobility"],
            instrument_id=ids["instrument-mobility"],
            portfolio_item_id=ids["portfolio-mobility"],
            source_id=ids["source-public-research"],
            provider=NewsProviderType.MANUAL_REFERENCE,
            provider_item_id="public-demo-news-002",
            title="[공개 데모] 모빌리티 공급망 비용 점검",
            normalized_title="공개 데모 모빌리티 공급망 비용 점검",
            source_name="Public Demo Research Lab",
            source_domain=DEMO_MARKER_DOMAIN,
            canonical_url=f"https://{DEMO_MARKER_DOMAIN}/news/mobility-cost",
            canonical_url_hash=fingerprint("url", "mobility-cost"),
            original_url=f"https://{DEMO_MARKER_DOMAIN}/news/mobility-cost",
            published_at=now - 1 * day,
            source_updated_at=None,
            first_seen_at=now - 1 * day,
            last_seen_at=now - 1 * day,
            fetched_at=now - 1 * day,
            verified_at=None,
            language="ko",
            snippet="공급망 비용 변동 가능성을 다룬 공개 데모 뉴스입니다.",
            short_summary="공식 확인 전 단계의 공개 데모 자료입니다.",
            summary_status=NewsSummaryStatus.MANUAL_REVIEW_REQUIRED,
            primary_claim="공급망 비용이 변동할 가능성이 있습니다.",
            claim_fingerprint=fingerprint("claim", "mobility"),
            content_fingerprint=fingerprint("content", "mobility-news"),
            verification_status=VerificationStatus.NEEDS_VERIFICATION,
            source_grade=SourceGrade.B,
            trust_score=68,
            certainty_level=CertaintyLevel.POSSIBLE,
            independent_origin=True,
            original_origin_key="PUBLIC_DEMO_RESEARCH_MOBILITY",
            duplicate_of_id=None,
            information_event_id=ids["event-mobility"],
            material_change=False,
            stale_reused=False,
            lifecycle_status=LifecycleStatus.ACTIVE,
            official_reference_ids=[],
            changed_facts=[],
            pinned=False,
            created_at=now - 1 * day,
            updated_at=now,
        ),
    ]
    session.add_all(news)
    session.flush()

    session.add_all(
        [
            NewsClaimRecord(
                id=ids["claim-semiconductor"],
                news_reference_id=ids["news-semiconductor"],
                event_id=ids["event-semiconductor"],
                claim_type="STATUS",
                claim_text="설비 투자 계획이 유지되고 있습니다.",
                normalized_claim="설비 투자 계획 유지",
                claim_fingerprint=fingerprint("news-claim", "semiconductor"),
                certainty_level=CertaintyLevel.CONFIRMED,
                supports_official_record_id=ids["disclosure-semiconductor"],
                contradicts_official_record_id=None,
                verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
                created_at=now - 3 * day,
            ),
            NewsClaimRecord(
                id=ids["claim-mobility"],
                news_reference_id=ids["news-mobility"],
                event_id=ids["event-mobility"],
                claim_type="RISK",
                claim_text="공급망 비용이 변동할 가능성이 있습니다.",
                normalized_claim="공급망 비용 변동 가능성",
                claim_fingerprint=fingerprint("news-claim", "mobility"),
                certainty_level=CertaintyLevel.POSSIBLE,
                supports_official_record_id=None,
                contradicts_official_record_id=None,
                verification_status=VerificationStatus.NEEDS_VERIFICATION,
                created_at=now - 1 * day,
            ),
        ]
    )

    theses = [
        InvestmentThesisRecord(
            id=ids["thesis-semiconductor"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            thesis_summary="공식 수요 지표와 투자 집행을 함께 확인합니다.",
            investment_purpose="중기 성장 관찰",
            investment_horizon="MEDIUM",
            original_reasons=["설비 투자", "수요 회복 가능성"],
            expected_catalysts=["공식 수주 공시", "가동률 개선"],
            key_risks=["수요 지연", "투자 비용 증가"],
            conditions_to_add=["공식 수주와 현금흐름 개선 동시 확인"],
            conditions_to_hold=["투자 계획 유지"],
            conditions_to_reduce=["수요 지연과 비용 증가 동시 발생"],
            conditions_to_exit=["핵심 투자 계획 철회"],
            invalidation_conditions=["공식 계획 취소"],
            questions_to_verify=["투자 집행 속도는 유지되는가?"],
            user_conviction="MEDIUM",
            thesis_status="ACTIVE",
            created_at=now - 20 * day,
            updated_at=now,
            last_reviewed_at=now - 1 * day,
        ),
        InvestmentThesisRecord(
            id=ids["thesis-mobility"],
            portfolio_item_id=ids["portfolio-mobility"],
            thesis_summary="배당과 공급망 비용을 함께 점검합니다.",
            investment_purpose="장기 인컴과 산업 전환 관찰",
            investment_horizon="LONG",
            original_reasons=["배당", "산업 전환"],
            expected_catalysts=["비용 안정", "신규 사업 진척"],
            key_risks=["원가 상승", "수요 둔화"],
            conditions_to_add=["공식 비용 개선 확인"],
            conditions_to_hold=["배당 정책 유지"],
            conditions_to_reduce=["비용 악화가 장기화"],
            conditions_to_exit=["핵심 배당 정책 훼손"],
            invalidation_conditions=["배당 정책 중단"],
            questions_to_verify=["공급망 비용이 일시적인가?"],
            user_conviction="MEDIUM",
            thesis_status="REVIEW_REQUIRED",
            created_at=now - 18 * day,
            updated_at=now,
            last_reviewed_at=now - 1 * day,
        ),
    ]
    session.add_all(theses)
    session.flush()

    impacts = [
        PortfolioImpactRecord(
            id=ids["impact-semiconductor"],
            event_id=ids["event-semiconductor"],
            portfolio_item_id=ids["portfolio-semiconductor"],
            thesis_id=ids["thesis-semiconductor"],
            relevance="DIRECT",
            impact_direction="POSITIVE",
            impact_strength="MEDIUM",
            impact_horizon="MEDIUM_TERM",
            thesis_effect="STRENGTHENS",
            confidence="HIGH",
            evidence_strength="HIGH",
            one_line_summary="공식 투자 계획이 기존 투자 근거를 보강합니다.",
            impact_path=["공식 발표", "설비 투자", "중기 공급 능력"],
            supporting_factors=["공식 공시", "후속 IR 자료"],
            opposing_factors=["투자 집행 비용"],
            conditions_to_watch=["수요 회복", "가동률"],
            invalidation_conditions=["투자 계획 철회"],
            missing_information=["실제 집행률"],
            source_links=[
                {
                    "title": "[공개 데모] 설비 투자 계획",
                    "url": "https://disclosure.public-demo.example.invalid/semiconductor-investment",
                }
            ],
            verification_status="OFFICIAL_CONFIRMED",
            generated_by="RULE_BASED",
            generated_at=now - 1 * day,
            valid_until=now + 14 * day,
            human_decision_required=True,
        ),
        PortfolioImpactRecord(
            id=ids["impact-mobility"],
            event_id=ids["event-mobility"],
            portfolio_item_id=ids["portfolio-mobility"],
            thesis_id=ids["thesis-mobility"],
            relevance="SUPPLY_CHAIN",
            impact_direction="MIXED",
            impact_strength="MEDIUM",
            impact_horizon="SHORT_TERM",
            thesis_effect="SLIGHTLY_WEAKENS",
            confidence="MEDIUM",
            evidence_strength="LOW",
            one_line_summary="공급망 비용 가능성은 확인 전까지 관찰이 필요합니다.",
            impact_path=["비용 가능성", "마진 압력", "배당 여력 점검"],
            supporting_factors=["산업 전환 수요"],
            opposing_factors=["원가 변동 가능성"],
            conditions_to_watch=["공식 비용 안내"],
            invalidation_conditions=["공식 비용 안정 확인"],
            missing_information=["공식 수치"],
            source_links=[
                {
                    "title": "[공개 데모] 모빌리티 공급망 비용 점검",
                    "url": f"https://{DEMO_MARKER_DOMAIN}/news/mobility-cost",
                }
            ],
            verification_status="NEEDS_VERIFICATION",
            generated_by="RULE_BASED",
            generated_at=now - 1 * day,
            valid_until=now + 7 * day,
            human_decision_required=True,
        ),
    ]
    session.add_all(impacts)
    session.flush()

    risk_snapshot = {
        "risk_style": "BALANCED",
        "max_single_position_percent": "35",
        "minimum_cash_percent": "20",
        "source": "PUBLIC_DEMO_FIXTURE",
    }
    session.add_all(
        [
            DecisionReviewRecord(
                id=ids["decision-semiconductor"],
                portfolio_item_id=ids["portfolio-semiconductor"],
                thesis_id=ids["thesis-semiconductor"],
                direction="HOLD",
                thesis_status="STRENGTHENED",
                confidence="HIGH",
                evidence_strength="HIGH",
                why_now=(
                    "공식 발표가 기존 투자 근거를 보강했지만 실제 집행률 확인이 필요합니다."
                ),
                supporting_evidence=["공식 설비 투자 계획", "후속 IR 자료"],
                contrary_evidence=["투자 비용 증가 가능성"],
                positive_factors=["공식 확인", "중기 공급 능력"],
                negative_factors=["단기 비용 부담"],
                conditions_to_add=["수요 회복과 집행률 확인"],
                conditions_to_hold=["계획 유지"],
                conditions_to_reduce=["수요 지연"],
                conditions_to_exit=["계획 철회"],
                invalidation_conditions=["공식 취소"],
                missing_information=["실제 집행률"],
                manual_reference_price=None,
                average_cost_snapshot=Decimal("70000"),
                quantity_snapshot=Decimal("10"),
                risk_profile_snapshot=risk_snapshot,
                based_on_event_ids=[ids["event-semiconductor"]],
                generated_by="RULE_BASED",
                generated_at=now,
                valid_until=now + 14 * day,
                acknowledged_at=None,
                user_decision=None,
                human_decision_required=True,
            ),
            DecisionReviewRecord(
                id=ids["decision-mobility"],
                portfolio_item_id=ids["portfolio-mobility"],
                thesis_id=ids["thesis-mobility"],
                direction="WAIT",
                thesis_status="REVIEW_REQUIRED",
                confidence="MEDIUM",
                evidence_strength="LOW",
                why_now=(
                    "공급망 비용 정보가 공식 확인 전 단계이므로 "
                    "추가 매수보다 확인이 우선입니다."
                ),
                supporting_evidence=["산업 전환 수요"],
                contrary_evidence=["비용 변동 가능성"],
                positive_factors=["배당 정책"],
                negative_factors=["원가 불확실성"],
                conditions_to_add=["공식 비용 안정 확인"],
                conditions_to_hold=["배당 정책 유지"],
                conditions_to_reduce=["비용 악화 장기화"],
                conditions_to_exit=["배당 정책 훼손"],
                invalidation_conditions=["공식 비용 안정"],
                missing_information=["공식 수치"],
                manual_reference_price=None,
                average_cost_snapshot=Decimal("110000"),
                quantity_snapshot=Decimal("5"),
                risk_profile_snapshot=risk_snapshot,
                based_on_event_ids=[ids["event-mobility"]],
                generated_by="RULE_BASED",
                generated_at=now,
                valid_until=now + 7 * day,
                acknowledged_at=None,
                user_decision=None,
                human_decision_required=True,
            ),
        ]
    )

    session.add(
        RiskProfileRecord(
            id="default",
            max_position_percent=Decimal("35"),
            max_portfolio_loss_percent=Decimal("15"),
            default_stop_loss_percent=Decimal("12"),
            default_take_profit_percent=Decimal("20"),
            max_single_trade_amount=Decimal("1000000"),
            cash_reserve_percent=Decimal("20"),
            allow_averaging_down=False,
            recommendation_mode=RecommendationMode.BALANCED,
            risk_style=RiskStyle.BALANCED,
            primary_goal=PrimaryGoal.BALANCED_GROWTH,
            default_investment_horizon=InvestmentHorizon.MEDIUM,
            max_single_position_percent=Decimal("35"),
            portfolio_loss_review_percent=Decimal("15"),
            default_loss_review_percent=Decimal("12"),
            default_profit_review_percent=Decimal("20"),
            minimum_cash_percent=Decimal("20"),
            max_single_additional_buy_percent=Decimal("10"),
            averaging_down_policy=AveragingDownPolicy.CONDITIONAL,
            max_averaging_down_count=1,
            require_official_evidence_for_averaging_down=True,
            high_volatility_asset_limit_percent=Decimal("15"),
            crypto_asset_limit_percent=Decimal("5"),
            notes="공개 데모용 균형형 위험 기준입니다.",
            acknowledged_at=now,
            source=RiskProfileSource.CUSTOM,
            portfolio_fingerprint=fingerprint("public-demo", "portfolio"),
            recommendation_version="public-demo-v1",
            created_at=now - 10 * day,
            updated_at=now,
        )
    )

    briefings = [
        BriefingRecord(
            id=ids["briefing-krx"],
            briefing_type=BriefingType.KRX_PRE_OPEN,
            status=BriefingStatus.READY,
            period_start=now - 1 * day,
            period_end=now,
            generated_at=now,
            title="[공개 데모] KRX 장전 브리핑",
            compact_summary="공식 투자 계획과 공급망 비용 이슈를 함께 확인합니다.",
            item_count=2,
            material_change_count=1,
            correction_count=0,
            denial_count=0,
            official_confirmed_count=1,
            needs_verification_count=1,
            related_instrument_ids=[
                ids["instrument-semiconductor"],
                ids["instrument-mobility"],
            ],
            content_fingerprint=fingerprint("briefing", "krx", now.date()),
            idempotency_key=fingerprint("briefing-idempotency", "krx", now.date()),
            valid_until=now + timedelta(hours=12),
            created_at=now,
            updated_at=now,
        ),
        BriefingRecord(
            id=ids["briefing-daily"],
            briefing_type=BriefingType.DAILY_DIGEST,
            status=BriefingStatus.READY,
            period_start=now - 7 * day,
            period_end=now,
            generated_at=now,
            title="[공개 데모] 주간 변화 요약",
            compact_summary="공개 예시 종목의 공식 확인과 검증 대기 항목을 구분합니다.",
            item_count=2,
            material_change_count=1,
            correction_count=0,
            denial_count=0,
            official_confirmed_count=1,
            needs_verification_count=1,
            related_instrument_ids=[
                ids["instrument-semiconductor"],
                ids["instrument-mobility"],
            ],
            content_fingerprint=fingerprint("briefing", "daily", now.date()),
            idempotency_key=fingerprint("briefing-idempotency", "daily", now.date()),
            valid_until=now + 1 * day,
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(briefings)
    session.flush()

    session.add_all(
        [
            BriefingItemRecord(
                id=ids["briefing-item-semiconductor"],
                briefing_id=ids["briefing-krx"],
                information_event_id=ids["event-semiconductor"],
                priority=90,
                category="OFFICIAL_DISCLOSURE",
                headline="공개 데모 반도체 설비 투자 계획",
                short_summary="공식 확인된 공개 데모 사건입니다.",
                verification_status=VerificationStatus.OFFICIAL_CONFIRMED,
                trust_score=92,
                material_change=True,
                changed_facts=[{"field": "status", "value": "공식 확인"}],
                source_links=[
                    {
                        "title": "Public Demo Official IR",
                        "url": "https://ir.public-demo.example.invalid/",
                    }
                ],
                official_reference_links=[
                    {
                        "title": "[공개 데모] 설비 투자 계획",
                        "url": "https://disclosure.public-demo.example.invalid/semiconductor-investment",
                    }
                ],
                published_at=now - 5 * day,
                state_fingerprint=fingerprint("briefing-item", "semiconductor"),
                created_at=now,
            ),
            BriefingItemRecord(
                id=ids["briefing-item-mobility"],
                briefing_id=ids["briefing-krx"],
                information_event_id=ids["event-mobility"],
                priority=65,
                category="NEEDS_VERIFICATION",
                headline="공개 데모 모빌리티 공급망 비용",
                short_summary="공식 확인 전 단계의 공개 데모 사건입니다.",
                verification_status=VerificationStatus.NEEDS_VERIFICATION,
                trust_score=68,
                material_change=False,
                changed_facts=[],
                source_links=[
                    {
                        "title": "Public Demo Research Lab",
                        "url": f"https://{DEMO_MARKER_DOMAIN}/",
                    }
                ],
                official_reference_links=[],
                published_at=now - 1 * day,
                state_fingerprint=fingerprint("briefing-item", "mobility"),
                created_at=now,
            ),
        ]
    )

    session.add_all(
        [
            EconomicEventRecord(
                id=ids["economic-rate"],
                event_type="RATE_DECISION",
                title="[공개 데모] 기준금리 결정 일정",
                scheduled_at=now + 2 * day,
                official_source_name="Public Demo Central Bank",
                official_source_url="https://macro.public-demo.example.invalid/rate-decision",
                related_portfolio_item_ids=[
                    ids["portfolio-semiconductor"],
                    ids["portfolio-mobility"],
                ],
                expected_impact_path=["금리", "할인율", "성장주 평가"],
                pre_release_checks=["공식 일정 확인", "시장 기대 확인"],
                actual_result=None,
                changed=False,
                created_at=now,
                updated_at=now,
            ),
            EconomicEventRecord(
                id=ids["economic-export"],
                event_type="EXPORT_DATA",
                title="[공개 데모] 수출 지표 발표 일정",
                scheduled_at=now + 5 * day,
                official_source_name="Public Demo Statistics Office",
                official_source_url="https://macro.public-demo.example.invalid/export-data",
                related_portfolio_item_ids=[ids["portfolio-semiconductor"]],
                expected_impact_path=["수출", "반도체 수요", "실적 기대"],
                pre_release_checks=["공식 일정 확인"],
                actual_result=None,
                changed=False,
                created_at=now,
                updated_at=now,
            ),
        ]
    )

    session.add_all(
        [
            MarketSessionCacheRecord(
                id=ids["market-session-krx"],
                market="KRX",
                session_date=str(now.date()),
                market_timezone="Asia/Seoul",
                open_at=now.replace(hour=0, minute=0) + timedelta(hours=9),
                close_at=now.replace(hour=0, minute=0) + timedelta(hours=15, minutes=30),
                holiday=False,
                early_close=False,
                schedule_status="DEMO",
                source="PUBLIC_DEMO_FIXTURE",
                library_version="public-demo-v1",
                generated_at=now,
                verified_at=now,
            ),
            MarketSessionCacheRecord(
                id=ids["market-session-nasdaq"],
                market="NASDAQ",
                session_date=str(now.date()),
                market_timezone="America/New_York",
                open_at=now + timedelta(hours=2),
                close_at=now + timedelta(hours=8, minutes=30),
                holiday=False,
                early_close=False,
                schedule_status="DEMO",
                source="PUBLIC_DEMO_FIXTURE",
                library_version="public-demo-v1",
                generated_at=now,
                verified_at=now,
            ),
        ]
    )

    session.add_all(
        [
            ProviderSyncStateRecord(
                provider="OPENDART",
                capability="DISCLOSURE",
                configured=False,
                status="NOT_CONFIGURED",
                last_attempt_at=None,
                last_success_at=None,
                last_error_code=None,
                consecutive_failures=0,
                request_count=0,
                success_count=0,
                updated_at=now,
            ),
            ProviderSyncStateRecord(
                provider="SEC_EDGAR",
                capability="DISCLOSURE",
                configured=False,
                status="NOT_CONFIGURED",
                last_attempt_at=None,
                last_success_at=None,
                last_error_code=None,
                consecutive_failures=0,
                request_count=0,
                success_count=0,
                updated_at=now,
            ),
        ]
    )

    session.commit()

    return {
        "instruments": len(instruments),
        "portfolio_items": len(portfolios),
        "position_transactions": len(transactions),
        "sale_transactions": 1,
        "sources": len(sources),
        "subscriptions": 1,
        "analyst_references": 2,
        "reference_candidates": len(candidates),
        "information_events": len(events),
        "disclosures": 1,
        "news_references": len(news),
        "portfolio_impacts": len(impacts),
        "decision_reviews": 2,
        "briefings": len(briefings),
        "economic_events": 2,
    }


def main() -> int:
    args = parse_args()
    if not args.confirm:
        raise SystemExit("Refusing to write without --confirm.")

    expected_root = Path(args.expected_demo_root)
    database_path = validate_target(args.database_url, expected_root)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(args.database_url, future=True)
    try:
        with Session(engine) as session:
            check_revision(session)
            state = require_empty_or_seeded(session)
            if state == "already_seeded":
                print(
                    json.dumps(
                        {
                            "status": "already_seeded",
                            "database": str(database_path),
                            "revision": EXPECTED_REVISION,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 0

            counts = seed(session)
    except Exception:
        raise
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "status": "seeded",
                "database": str(database_path),
                "revision": EXPECTED_REVISION,
                "counts": counts,
                "live_provider_requests": 0,
                "personal_investment_data": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
