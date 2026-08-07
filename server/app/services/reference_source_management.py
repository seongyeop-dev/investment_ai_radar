from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.database import (
    SourceGrade,
    SourceRecord,
)
from app.models.reference_subscriptions import (
    ReferenceSubscriptionRecord,
)
from app.schemas.reference_source_management import (
    ReferenceSourceDuplicateRead,
    ReferenceSourceImportConfirmed,
    ReferenceSourceImportPreview,
    ReferenceSourceImportRequest,
    ReferenceSourceInput,
    ReferenceSourceList,
    ReferenceSourceRead,
    ReferenceSourceUpdateRequest,
)
from app.services.reference_source_history import (
    MANAGED_REFERENCE_SOURCE_FIELDS,
    create_reference_source_change,
    reference_source_snapshot,
)
from app.services.sqlite_backup import create_sqlite_backup

MAX_REFERENCE_SOURCE_LIMIT = 100


class ReferenceSourceImportConfirmationRequiredError(ValueError):
    pass


class ReferenceSourceImportBlockedError(ValueError):
    def __init__(
        self,
        preview: ReferenceSourceImportPreview,
    ) -> None:
        self.preview = preview
        super().__init__("Reference source import cannot be confirmed.")


class ReferenceSourceUpdateError(ValueError):
    pass


class ReferenceSourceUpdateConflictError(ReferenceSourceUpdateError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "REFERENCE_SOURCE_UPDATE_CONFLICT",
    ) -> None:
        self.code = code
        super().__init__(message)


class ReferenceSourceManagementService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session

    def list(
        self,
        *,
        query: str | None = None,
        official: bool | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ReferenceSourceList:
        filters = [
            SourceRecord.source_type == "EXPERT_REFERENCE",
        ]

        if official is not None:
            filters.append(SourceRecord.official.is_(official))

        if enabled is not None:
            filters.append(SourceRecord.enabled.is_(enabled))

        if query and query.strip():
            term = query.strip()

            filters.append(
                or_(
                    SourceRecord.name.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.domain.contains(
                        term,
                        autoescape=True,
                    ),
                    SourceRecord.provider_type.contains(
                        term,
                        autoescape=True,
                    ),
                )
            )

        count_statement = select(func.count()).select_from(SourceRecord).where(*filters)

        total = int(self.session.scalar(count_statement) or 0)

        rows = list(
            self.session.scalars(
                select(SourceRecord)
                .where(*filters)
                .order_by(
                    SourceRecord.enabled.desc(),
                    SourceRecord.official.desc(),
                    SourceRecord.name.asc(),
                    SourceRecord.id.asc(),
                )
                .limit(
                    min(
                        max(limit, 1),
                        MAX_REFERENCE_SOURCE_LIMIT,
                    )
                )
                .offset(max(offset, 0))
            )
        )

        return ReferenceSourceList(
            items=[self._source_read(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def get(
        self,
        source_id: str,
    ) -> ReferenceSourceRead | None:
        source = self.session.get(
            SourceRecord,
            source_id,
        )

        if source is None:
            return None

        if source.source_type != "EXPERT_REFERENCE":
            return None

        return self._source_read(source)

    def preview(
        self,
        payload: ReferenceSourceImportRequest,
    ) -> ReferenceSourceImportPreview:
        normalized, warnings = self._normalize_source_values(
            name=payload.name,
            source_grade=payload.source_grade,
            domain=payload.domain,
            official=payload.official,
            enabled=payload.enabled,
            feed_url=payload.feed_url,
            provider_type=payload.provider_type,
            language=payload.language,
            request_interval_seconds=(payload.request_interval_seconds),
            timeout_seconds=(payload.timeout_seconds),
            max_items=payload.max_items,
            original_source_name=(payload.original_source_name),
        )

        duplicate, duplicate_warnings = self._duplicate_source(
            name=normalized.name,
            feed_url=normalized.feed_url,
        )

        warnings.extend(duplicate_warnings)
        warnings = self._deduplicate(warnings)

        blocking_warnings = {
            "INVALID_DOMAIN",
            "INVALID_FEED_URL",
            "INSECURE_FEED_URL",
            "UNSAFE_FEED_HOST",
            "FEED_DOMAIN_MISMATCH",
            "FEED_URL_REQUIRED",
            "PROVIDER_TYPE_REQUIRED",
            "DUPLICATE_SOURCE_NAME",
            "DUPLICATE_FEED_URL",
        }

        would_create = not any(warning in blocking_warnings for warning in warnings)

        return ReferenceSourceImportPreview(
            normalized_source=normalized,
            validation_warnings=warnings,
            duplicate=duplicate,
            would_create=would_create,
            confirmed=False,
        )

    def confirm(
        self,
        payload: ReferenceSourceImportRequest,
    ) -> ReferenceSourceImportConfirmed:
        if not payload.confirm:
            raise (
                ReferenceSourceImportConfirmationRequiredError(
                    "confirm must be true to create a source"
                )
            )

        preview = self.preview(payload)

        if not preview.would_create:
            raise ReferenceSourceImportBlockedError(preview)

        normalized = preview.normalized_source

        backup_path = create_sqlite_backup(
            self.session,
            operation="source_create",
        )

        source = SourceRecord(
            name=normalized.name,
            source_type="EXPERT_REFERENCE",
            source_grade=normalized.source_grade,
            domain=normalized.domain,
            official=normalized.official,
            enabled=normalized.enabled,
            feed_url=normalized.feed_url,
            provider_type=normalized.provider_type,
            language=normalized.language,
            request_interval_seconds=(normalized.request_interval_seconds),
            timeout_seconds=(normalized.timeout_seconds),
            max_items=normalized.max_items,
            original_source_name=(normalized.original_source_name),
        )

        self.session.add(source)
        self.session.flush()
        self.session.refresh(source)

        create_reference_source_change(
            self.session,
            source_id=source.id,
            operation="CREATE",
            changed_fields=list(MANAGED_REFERENCE_SOURCE_FIELDS),
            before_values=None,
            after_values=(reference_source_snapshot(source)),
            backup_path=backup_path,
        )

        return ReferenceSourceImportConfirmed(
            source=self._source_read(source),
            validation_warnings=(preview.validation_warnings),
            confirmed=True,
        )

    def update(
        self,
        source_id: str,
        payload: ReferenceSourceUpdateRequest,
    ) -> ReferenceSourceRead | None:
        source = self.session.get(
            SourceRecord,
            source_id,
        )

        if source is None:
            return None

        if source.source_type != "EXPERT_REFERENCE":
            return None

        fields = payload.model_fields_set

        if not fields:
            raise ReferenceSourceUpdateError("At least one update field is required.")

        values: dict[str, object] = {
            "name": source.name,
            "source_grade": source.source_grade,
            "domain": source.domain,
            "official": source.official,
            "enabled": source.enabled,
            "feed_url": source.feed_url,
            "provider_type": source.provider_type,
            "language": source.language,
            "request_interval_seconds": (source.request_interval_seconds),
            "timeout_seconds": source.timeout_seconds,
            "max_items": source.max_items,
            "original_source_name": (source.original_source_name),
        }

        required_non_null = {
            "name",
            "source_grade",
            "domain",
            "official",
            "enabled",
            "language",
            "request_interval_seconds",
            "timeout_seconds",
            "max_items",
        }

        for field in fields:
            value = getattr(payload, field)

            if field in required_non_null and value is None:
                raise ReferenceSourceUpdateError(f"{field} must not be null.")

            values[field] = value

        normalized, warnings = self._normalize_source_values(
            name=str(values["name"]),
            source_grade=values["source_grade"],
            domain=str(values["domain"]),
            official=bool(values["official"]),
            enabled=bool(values["enabled"]),
            feed_url=values["feed_url"],
            provider_type=values["provider_type"],
            language=str(values["language"]),
            request_interval_seconds=int(values["request_interval_seconds"]),
            timeout_seconds=int(values["timeout_seconds"]),
            max_items=int(values["max_items"]),
            original_source_name=values["original_source_name"],
        )

        blocking_warnings = {
            "INVALID_DOMAIN",
            "INVALID_FEED_URL",
            "INSECURE_FEED_URL",
            "UNSAFE_FEED_HOST",
            "FEED_DOMAIN_MISMATCH",
            "FEED_URL_REQUIRED",
            "PROVIDER_TYPE_REQUIRED",
        }

        blocked = [warning for warning in warnings if warning in blocking_warnings]

        if blocked:
            raise ReferenceSourceUpdateError("Invalid source settings: " + ", ".join(blocked))

        duplicate, duplicate_warnings = self._duplicate_source(
            name=normalized.name,
            feed_url=normalized.feed_url,
            exclude_source_id=source.id,
        )

        if duplicate.duplicate:
            raise ReferenceSourceUpdateConflictError(
                "Another source already uses " + ", ".join(duplicate.matched_fields) + ".",
                code="REFERENCE_SOURCE_DUPLICATE",
            )

        if duplicate_warnings:
            raise ReferenceSourceUpdateConflictError(
                "Another source conflicts with the updated source settings.",
                code="REFERENCE_SOURCE_DUPLICATE",
            )

        protected_fields = {
            "name",
            "domain",
            "official",
            "enabled",
            "feed_url",
            "provider_type",
        }

        changed_protected_fields = {
            field
            for field in protected_fields
            if field in fields and getattr(source, field) != getattr(normalized, field)
        }

        active_subscription_count = self._active_subscription_count(source.id)

        if active_subscription_count > 0 and changed_protected_fields:
            raise ReferenceSourceUpdateConflictError(
                "Pause every active subscription "
                "for this source before changing "
                "identity, provider, official, or "
                "enabled settings.",
                code=("REFERENCE_SOURCE_ACTIVE_SUBSCRIPTIONS"),
            )

        before_snapshot = reference_source_snapshot(source)
        after_snapshot = reference_source_snapshot(normalized)
        changed_fields = [
            field
            for field in (MANAGED_REFERENCE_SOURCE_FIELDS)
            if (before_snapshot[field] != after_snapshot[field])
        ]

        backup_path = None

        if changed_fields:
            backup_path = create_sqlite_backup(
                self.session,
                operation="source_update",
            )

        source.name = normalized.name
        source.source_grade = normalized.source_grade
        source.domain = normalized.domain
        source.official = normalized.official
        source.enabled = normalized.enabled
        source.feed_url = normalized.feed_url
        source.provider_type = normalized.provider_type
        source.language = normalized.language
        source.request_interval_seconds = normalized.request_interval_seconds
        source.timeout_seconds = normalized.timeout_seconds
        source.max_items = normalized.max_items
        source.original_source_name = normalized.original_source_name

        self.session.flush()
        self.session.refresh(source)

        if changed_fields:
            create_reference_source_change(
                self.session,
                source_id=source.id,
                operation="UPDATE",
                changed_fields=changed_fields,
                before_values={field: before_snapshot[field] for field in changed_fields},
                after_values={field: after_snapshot[field] for field in changed_fields},
                backup_path=backup_path,
            )

        return self._source_read(source)

    def _source_read(
        self,
        source: SourceRecord,
    ) -> ReferenceSourceRead:
        return ReferenceSourceRead.model_validate(source).model_copy(
            update={
                "active_subscription_count": (self._active_subscription_count(source.id)),
                "total_subscription_count": (self._total_subscription_count(source.id)),
            }
        )

    def _active_subscription_count(
        self,
        source_id: str,
    ) -> int:
        value = self.session.scalar(
            select(func.count())
            .select_from(ReferenceSubscriptionRecord)
            .where(
                ReferenceSubscriptionRecord.source_id == source_id,
                ReferenceSubscriptionRecord.enabled.is_(True),
            )
        )

        return int(value or 0)

    def _total_subscription_count(
        self,
        source_id: str,
    ) -> int:
        value = self.session.scalar(
            select(func.count())
            .select_from(ReferenceSubscriptionRecord)
            .where(ReferenceSubscriptionRecord.source_id == source_id)
        )

        return int(value or 0)

    def _duplicate_source(
        self,
        *,
        name: str,
        feed_url: str | None,
        exclude_source_id: str | None = None,
    ) -> tuple[
        ReferenceSourceDuplicateRead,
        list[str],
    ]:
        name_statement = select(SourceRecord).where(
            func.lower(SourceRecord.name) == name.casefold()
        )

        if exclude_source_id is not None:
            name_statement = name_statement.where(SourceRecord.id != exclude_source_id)

        name_duplicate = self.session.scalar(name_statement)

        feed_duplicate = None

        if feed_url:
            feed_statement = select(SourceRecord).where(SourceRecord.feed_url == feed_url)

            if exclude_source_id is not None:
                feed_statement = feed_statement.where(SourceRecord.id != exclude_source_id)

            feed_duplicate = self.session.scalar(feed_statement)

        matched_fields: list[str] = []
        warnings: list[str] = []

        if name_duplicate is not None:
            matched_fields.append("name")
            warnings.append("DUPLICATE_SOURCE_NAME")

        if feed_duplicate is not None:
            matched_fields.append("feedUrl")
            warnings.append("DUPLICATE_FEED_URL")

        existing = name_duplicate if name_duplicate is not None else feed_duplicate

        return (
            ReferenceSourceDuplicateRead(
                duplicate=existing is not None,
                existing_source_id=(existing.id if existing is not None else None),
                matched_fields=matched_fields,
            ),
            warnings,
        )

    @classmethod
    def _normalize_source_values(
        cls,
        *,
        name: str,
        source_grade: SourceGrade,
        domain: str,
        official: bool,
        enabled: bool,
        feed_url: object,
        provider_type: object,
        language: str,
        request_interval_seconds: int,
        timeout_seconds: int,
        max_items: int,
        original_source_name: object,
    ) -> tuple[
        ReferenceSourceInput,
        list[str],
    ]:
        warnings: list[str] = []

        normalized_name = cls._normalize_text(name)

        try:
            normalized_domain = cls._normalize_domain(domain)
        except ValueError:
            normalized_domain = domain.strip().casefold()
            warnings.append("INVALID_DOMAIN")

        normalized_feed_url: str | None = None

        if feed_url is not None:
            raw_feed_url = str(feed_url).strip()

            if raw_feed_url:
                try:
                    normalized_feed_url = cls._normalize_feed_url(raw_feed_url)
                except ValueError as exc:
                    normalized_feed_url = raw_feed_url
                    warnings.append(str(exc))

        if enabled and not normalized_feed_url:
            warnings.append("FEED_URL_REQUIRED")

        normalized_provider_type: str | None = None

        if provider_type is not None:
            normalized_provider_type = cls._normalize_provider_type(str(provider_type))

        if enabled and not normalized_provider_type:
            warnings.append("PROVIDER_TYPE_REQUIRED")

        normalized_language = language.strip().replace("_", "-").casefold()

        if not normalized_language:
            normalized_language = "und"

        normalized_original_name = None

        if original_source_name is not None:
            value = cls._normalize_text(str(original_source_name))

            if value:
                normalized_original_name = value

        if normalized_feed_url:
            host = (urlsplit(normalized_feed_url).hostname or "").casefold()

            if not cls._host_matches_domain(
                host,
                normalized_domain,
            ):
                warnings.append("FEED_DOMAIN_MISMATCH")

        if not official:
            warnings.append("SOURCE_NOT_OFFICIAL")

        if not enabled:
            warnings.append("SOURCE_DISABLED")

        normalized = ReferenceSourceInput(
            name=normalized_name,
            source_grade=source_grade,
            domain=normalized_domain,
            official=official,
            enabled=enabled,
            feed_url=normalized_feed_url,
            provider_type=(normalized_provider_type),
            language=normalized_language,
            request_interval_seconds=(request_interval_seconds),
            timeout_seconds=timeout_seconds,
            max_items=max_items,
            original_source_name=(normalized_original_name),
        )

        return (
            normalized,
            cls._deduplicate(warnings),
        )

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError("Text value must not be empty.")

        return normalized

    @staticmethod
    def _normalize_domain(
        value: str,
    ) -> str:
        candidate = value.strip().casefold().rstrip(".")

        if not candidate or "://" in candidate or "/" in candidate or "@" in candidate:
            raise ValueError("Domain must be a hostname.")

        try:
            ascii_domain = candidate.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Domain is invalid.") from exc

        if (
            ascii_domain == "localhost"
            or ascii_domain.endswith(".localhost")
            or ascii_domain.endswith(".local")
        ):
            raise ValueError("Domain must be a public hostname.")

        try:
            ipaddress.ip_address(ascii_domain)
        except ValueError:
            pass
        else:
            raise ValueError("Domain must not be an IP address.")

        labels = ascii_domain.split(".")

        if len(labels) < 2 or any(
            not re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}"
                r"[a-z0-9])?",
                label,
            )
            for label in labels
        ):
            raise ValueError("Domain is invalid.")

        return ascii_domain

    @staticmethod
    def _normalize_feed_url(
        value: str,
    ) -> str:
        parsed = urlsplit(value)

        if parsed.scheme.casefold() != "https":
            raise ValueError("INSECURE_FEED_URL")

        if not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError("INVALID_FEED_URL")

        host = parsed.hostname.casefold()

        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            raise ValueError("UNSAFE_FEED_HOST")

        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None

        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError("UNSAFE_FEED_HOST")

        netloc = host

        if parsed.port is not None:
            netloc = f"{host}:{parsed.port}"

        path = parsed.path or "/"

        if path != "/":
            path = path.rstrip("/")

        return urlunsplit(
            (
                "https",
                netloc,
                path,
                parsed.query,
                "",
            )
        )

    @staticmethod
    def _normalize_provider_type(
        value: str,
    ) -> str | None:
        normalized = re.sub(
            r"[^A-Z0-9]+",
            "_",
            value.strip().upper(),
        ).strip("_")

        return normalized or None

    @staticmethod
    def _host_matches_domain(
        host: str,
        domain: str,
    ) -> bool:
        return host == domain or host.endswith("." + domain)

    @staticmethod
    def _deduplicate(
        values: list[str],
    ) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()

        for value in values:
            if value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result
