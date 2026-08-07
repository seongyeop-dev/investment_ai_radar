from __future__ import annotations

from datetime import UTC
from hashlib import sha256
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app.core.time import SystemClock
from app.models.analyst_references import (
    AnalystFreshnessStatus,
    AnalystIngestMode,
    AnalystMappingConfidence,
    AnalystReferenceCoverageRecord,
    AnalystReferenceRecord,
    AnalystRelationType,
    AnalystUserState,
)
from app.models.database import PortfolioItemRecord
from app.repositories.analyst_references import (
    AnalystReferenceRepository,
)
from app.schemas.analyst_references import (
    AnalystReferenceCoverageRead,
    AnalystReferenceImportDuplicateRead,
    AnalystReferenceImportLinkConfirmed,
    AnalystReferenceImportLinkPreview,
    AnalystReferenceImportLinkRequest,
    AnalystReferenceImportPortfolioItemRead,
    AnalystReferenceRead,
)


def normalize_analyst_reference_url(
    source_url: str,
) -> tuple[str, list[str]]:
    original = source_url.strip()
    parsed = urlsplit(original)

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname

    if scheme not in {"http", "https"} or hostname is None:
        raise ValueError("source_url must be an absolute HTTP(S) URL")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("source_url contains an invalid port") from exc

    normalized_hostname = hostname.lower()

    if ":" in normalized_hostname:
        normalized_hostname = f"[{normalized_hostname}]"

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)

    netloc = normalized_hostname

    if port is not None and not default_port:
        netloc = f"{normalized_hostname}:{port}"

    normalized = urlunsplit(
        (
            scheme,
            netloc,
            parsed.path or "/",
            parsed.query,
            "",
        )
    )

    warnings: list[str] = []

    if parsed.fragment:
        warnings.append("URL_FRAGMENT_REMOVED")

    if normalized != original:
        warnings.append("URL_NORMALIZED")

    return normalized, warnings


def analyst_reference_source_fingerprint(
    payload: AnalystReferenceImportLinkRequest,
) -> str:
    published_at = payload.published_at.astimezone(UTC)

    components = [
        "analyst-reference-v1",
        _fingerprint_text(payload.publisher_name),
        payload.publisher_type.value,
        _fingerprint_text(payload.title),
        _fingerprint_text(payload.analyst_name or ""),
        published_at.isoformat(timespec="seconds"),
        payload.document_type.value,
    ]

    fingerprint_input = "\n".join(components)

    return sha256(fingerprint_input.encode("utf-8")).hexdigest()


class AnalystReferenceImportConfirmationRequiredError(ValueError):
    pass


class AnalystReferenceImportBlockedError(ValueError):
    def __init__(
        self,
        preview: AnalystReferenceImportLinkPreview,
    ) -> None:
        self.preview = preview
        super().__init__("Analyst reference import cannot be confirmed.")


class AnalystReferenceImportService:
    def __init__(
        self,
        session: Session,
        repository: AnalystReferenceRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = (
            repository if repository is not None else AnalystReferenceRepository(session)
        )

    def preview(
        self,
        payload: AnalystReferenceImportLinkRequest,
    ) -> AnalystReferenceImportLinkPreview:
        normalized_url, warnings = normalize_analyst_reference_url(payload.source_url)

        source_fingerprint = analyst_reference_source_fingerprint(payload)

        requested_ids = [
            str(portfolio_item_id) for portfolio_item_id in payload.portfolio_item_ids
        ]
        unique_ids = list(dict.fromkeys(requested_ids))

        if len(unique_ids) != len(requested_ids):
            warnings.append("DUPLICATE_PORTFOLIO_ITEM_IDS_REMOVED")

        portfolio_rows = self.repository.portfolio_items(unique_ids)
        portfolio_by_id = {row.id: row for row in portfolio_rows}

        ordered_portfolios = [
            portfolio_by_id[portfolio_item_id]
            for portfolio_item_id in unique_ids
            if portfolio_item_id in portfolio_by_id
        ]

        missing_ids = [
            portfolio_item_id
            for portfolio_item_id in unique_ids
            if portfolio_item_id not in portfolio_by_id
        ]

        for portfolio_item_id in missing_ids:
            warnings.append(f"PORTFOLIO_ITEM_NOT_FOUND:{portfolio_item_id}")

        for row in ordered_portfolios:
            if row.archived_at is not None:
                warnings.append(f"ARCHIVED_PORTFOLIO_ITEM:{row.id}")

        canonical_duplicate = self.repository.by_canonical_url(normalized_url)
        fingerprint_duplicate = self.repository.by_source_fingerprint(source_fingerprint)

        if canonical_duplicate is not None:
            warnings.append("DUPLICATE_CANONICAL_URL")

        if fingerprint_duplicate is not None:
            warnings.append("DUPLICATE_SOURCE_FINGERPRINT")

        would_create = (
            not missing_ids and canonical_duplicate is None and fingerprint_duplicate is None
        )

        return AnalystReferenceImportLinkPreview(
            normalized_url=normalized_url,
            source_fingerprint=source_fingerprint,
            portfolio_items=[self._portfolio_read(row) for row in ordered_portfolios],
            validation_warnings=warnings,
            duplicate=AnalystReferenceImportDuplicateRead(
                canonical_url_duplicate=(canonical_duplicate is not None),
                source_fingerprint_duplicate=(fingerprint_duplicate is not None),
                canonical_url_reference_id=(
                    canonical_duplicate.id if canonical_duplicate is not None else None
                ),
                source_fingerprint_reference_id=(
                    fingerprint_duplicate.id if fingerprint_duplicate is not None else None
                ),
            ),
            would_create=would_create,
            confirmed=False,
        )

    def confirm(
        self,
        payload: AnalystReferenceImportLinkRequest,
    ) -> AnalystReferenceImportLinkConfirmed:
        if not payload.confirm:
            raise (
                AnalystReferenceImportConfirmationRequiredError(
                    "confirm must be true to create a reference"
                )
            )

        preview = self.preview(payload)

        if not preview.would_create:
            raise AnalystReferenceImportBlockedError(preview)

        recorded_at = SystemClock().now()

        reference = AnalystReferenceRecord(
            source_id=None,
            subscription_id=None,
            provider_item_id=None,
            ingest_mode=AnalystIngestMode.MANUAL,
            user_state=AnalystUserState.NEW,
            discovered_at=recorded_at,
            publisher_name=payload.publisher_name,
            publisher_type=payload.publisher_type,
            title=payload.title,
            analyst_name=payload.analyst_name,
            published_at=payload.published_at,
            canonical_url=preview.normalized_url,
            access_type=payload.access_type,
            document_type=payload.document_type,
            publisher_rating_raw=(payload.publisher_rating_raw),
            publisher_target_price_raw=(payload.publisher_target_price_raw),
            target_currency=payload.target_currency,
            public_abstract=payload.public_abstract,
            source_retrieved_at=recorded_at,
            source_fingerprint=(preview.source_fingerprint),
            freshness_status=(AnalystFreshnessStatus.UNKNOWN),
            is_active=True,
        )

        self.session.add(reference)
        self.session.flush()

        coverage_records = [
            AnalystReferenceCoverageRecord(
                analyst_reference_id=reference.id,
                portfolio_item_id=str(item.id),
                relation_type=(AnalystRelationType.PRIMARY),
                mapping_confidence=(AnalystMappingConfidence.VERIFIED),
                human_review_required=False,
            )
            for item in preview.portfolio_items
        ]

        self.session.add_all(coverage_records)
        self.session.flush()
        self.session.refresh(reference)

        coverage_reads = [
            AnalystReferenceCoverageRead.model_validate(coverage)
            for coverage in coverage_records
        ]

        reference_read = AnalystReferenceRead.model_validate(reference).model_copy(
            update={
                "coverages": coverage_reads,
            }
        )

        return AnalystReferenceImportLinkConfirmed(
            normalized_url=preview.normalized_url,
            source_fingerprint=(preview.source_fingerprint),
            portfolio_items=preview.portfolio_items,
            validation_warnings=(preview.validation_warnings),
            reference=reference_read,
            coverages=coverage_reads,
            confirmed=True,
        )

    @staticmethod
    def _portfolio_read(
        row: PortfolioItemRecord,
    ) -> AnalystReferenceImportPortfolioItemRead:
        return AnalystReferenceImportPortfolioItemRead(
            id=row.id,
            symbol=row.symbol,
            name=row.name,
            market=row.market,
            is_archived=row.archived_at is not None,
        )


def _fingerprint_text(value: str) -> str:
    return " ".join(value.split()).casefold()
