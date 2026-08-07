from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.database import SourceRecord
from app.models.reference_subscriptions import (
    ReferenceMatchMode,
    ReferenceSubscriptionRecord,
)
from app.repositories.reference_subscriptions import (
    ReferenceSubscriptionRepository,
)
from app.schemas.reference_subscriptions import (
    ReferenceSubscriptionImportConfirmed,
    ReferenceSubscriptionImportDuplicateRead,
    ReferenceSubscriptionImportPreview,
    ReferenceSubscriptionImportRequest,
    ReferenceSubscriptionRead,
    ReferenceSubscriptionSourceRead,
    ReferenceSubscriptionUpdateRequest,
)


class ReferenceSubscriptionImportConfirmationRequiredError(ValueError):
    pass


class ReferenceSubscriptionImportBlockedError(ValueError):
    def __init__(
        self,
        preview: ReferenceSubscriptionImportPreview,
    ) -> None:
        self.preview = preview
        super().__init__("Reference subscription import cannot be confirmed.")


class ReferenceSubscriptionImportService:
    def __init__(
        self,
        session: Session,
        repository: ReferenceSubscriptionRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = (
            repository if repository is not None else ReferenceSubscriptionRepository(session)
        )

    def preview(
        self,
        payload: ReferenceSubscriptionImportRequest,
    ) -> ReferenceSubscriptionImportPreview:
        normalized_display_name = self._normalize_display_name(payload.display_name)
        normalized_match_terms = self._normalize_match_terms(payload.match_terms)

        source = self.repository.source_for(str(payload.source_id))

        warnings: list[str] = []

        if source is None:
            warnings.append("SOURCE_NOT_FOUND")
        else:
            if not source.official:
                warnings.append("SOURCE_NOT_OFFICIAL")

            if not source.enabled:
                warnings.append("SOURCE_DISABLED")

        duplicate = self.repository.by_identity(
            source_id=str(payload.source_id),
            subject_type=payload.subject_type,
            display_name=normalized_display_name,
        )

        if duplicate is not None:
            warnings.append("DUPLICATE_SUBSCRIPTION")

        blocking_warnings = {
            "SOURCE_NOT_FOUND",
            "SOURCE_NOT_OFFICIAL",
            "SOURCE_DISABLED",
            "DUPLICATE_SUBSCRIPTION",
        }

        would_create = not any(warning in blocking_warnings for warning in warnings)

        return ReferenceSubscriptionImportPreview(
            normalized_display_name=(normalized_display_name),
            normalized_match_terms=(normalized_match_terms),
            source=(self._source_read(source) if source is not None else None),
            validation_warnings=warnings,
            duplicate=(
                ReferenceSubscriptionImportDuplicateRead(
                    duplicate=duplicate is not None,
                    existing_subscription_id=(duplicate.id if duplicate is not None else None),
                )
            ),
            would_create=would_create,
            confirmed=False,
        )

    def confirm(
        self,
        payload: ReferenceSubscriptionImportRequest,
    ) -> ReferenceSubscriptionImportConfirmed:
        if not payload.confirm:
            raise (
                ReferenceSubscriptionImportConfirmationRequiredError(
                    "confirm must be true to create a subscription"
                )
            )

        preview = self.preview(payload)

        if not preview.would_create:
            raise ReferenceSubscriptionImportBlockedError(preview)

        if preview.source is None:
            raise ReferenceSubscriptionImportBlockedError(preview)

        subscription = ReferenceSubscriptionRecord(
            source_id=str(payload.source_id),
            subject_type=payload.subject_type,
            display_name=(preview.normalized_display_name),
            match_mode=payload.match_mode,
            match_terms=(preview.normalized_match_terms),
            enabled=True,
        )

        self.session.add(subscription)
        self.session.flush()
        self.session.refresh(subscription)

        return ReferenceSubscriptionImportConfirmed(
            normalized_display_name=(preview.normalized_display_name),
            normalized_match_terms=(preview.normalized_match_terms),
            source=preview.source,
            validation_warnings=(preview.validation_warnings),
            subscription=self._subscription_read(
                subscription,
                preview.source,
            ),
            confirmed=True,
        )

    @staticmethod
    def _normalize_display_name(
        value: str,
    ) -> str:
        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError("display_name must not be empty")

        if len(normalized) > 200:
            raise ValueError("display_name must not exceed 200 characters")

        return normalized

    @staticmethod
    def _normalize_match_terms(
        values: list[str],
    ) -> list[str]:
        normalized_terms: list[str] = []
        seen: set[str] = set()

        for value in values:
            if not isinstance(value, str):
                raise ValueError("match_terms must contain strings")

            normalized = " ".join(value.split())

            if not normalized:
                continue

            if len(normalized) > 200:
                raise ValueError("match term must not exceed 200 characters")

            key = normalized.casefold()

            if key in seen:
                continue

            seen.add(key)
            normalized_terms.append(normalized)

        return normalized_terms

    @staticmethod
    def _source_read(
        source: SourceRecord,
    ) -> ReferenceSubscriptionSourceRead:
        return ReferenceSubscriptionSourceRead.model_validate(source)

    @staticmethod
    def _subscription_read(
        subscription: ReferenceSubscriptionRecord,
        source: ReferenceSubscriptionSourceRead,
    ) -> ReferenceSubscriptionRead:
        return ReferenceSubscriptionRead(
            id=subscription.id,
            source_id=subscription.source_id,
            subject_type=subscription.subject_type,
            display_name=subscription.display_name,
            match_mode=subscription.match_mode,
            match_terms=subscription.match_terms,
            enabled=subscription.enabled,
            created_at=subscription.created_at,
            updated_at=subscription.updated_at,
            source=source,
        )


class ReferenceSubscriptionUpdateError(ValueError):
    """Raised when subscription management input is invalid."""


class ReferenceSubscriptionUpdateConflictError(ReferenceSubscriptionUpdateError):
    """Raised when an update conflicts with another subscription."""


class ReferenceSubscriptionManagementService:
    def __init__(
        self,
        session: Session,
        repository: ReferenceSubscriptionRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = (
            repository if repository is not None else ReferenceSubscriptionRepository(session)
        )

    def update(
        self,
        subscription_id: str,
        payload: ReferenceSubscriptionUpdateRequest,
    ) -> ReferenceSubscriptionRecord | None:
        subscription = self.repository.get(subscription_id)

        if subscription is None:
            return None

        fields = payload.model_fields_set

        if not fields:
            raise ReferenceSubscriptionUpdateError("At least one update field is required.")

        display_name = subscription.display_name

        if "display_name" in fields:
            if payload.display_name is None:
                raise ReferenceSubscriptionUpdateError("display_name must not be null.")

            display_name = ReferenceSubscriptionImportService._normalize_display_name(
                payload.display_name
            )

        match_mode = subscription.match_mode

        if "match_mode" in fields:
            if payload.match_mode is None:
                raise ReferenceSubscriptionUpdateError("match_mode must not be null.")

            match_mode = payload.match_mode

        match_terms = list(subscription.match_terms)

        if "match_terms" in fields:
            if payload.match_terms is None:
                raise ReferenceSubscriptionUpdateError("match_terms must not be null.")

            match_terms = ReferenceSubscriptionImportService._normalize_match_terms(
                payload.match_terms
            )

        if match_mode is ReferenceMatchMode.ALL_SOURCE:
            match_terms = []
        elif not match_terms:
            raise ReferenceSubscriptionUpdateError(
                "AUTHOR and KEYWORD subscriptions require at least one match term."
            )

        enabled = subscription.enabled

        if "enabled" in fields:
            if payload.enabled is None:
                raise ReferenceSubscriptionUpdateError("enabled must not be null.")

            enabled = payload.enabled

        if enabled:
            source = self.repository.source_for(subscription.source_id)

            if source is None:
                raise ReferenceSubscriptionUpdateError("Subscription source was not found.")

            if not source.official:
                raise ReferenceSubscriptionUpdateError("Subscription source is not official.")

            if not source.enabled:
                raise ReferenceSubscriptionUpdateError("Subscription source is disabled.")

        if display_name != subscription.display_name:
            duplicate = self.repository.by_identity(
                source_id=subscription.source_id,
                subject_type=subscription.subject_type,
                display_name=display_name,
            )

            if duplicate is not None and duplicate.id != subscription.id:
                raise (
                    ReferenceSubscriptionUpdateConflictError(
                        "Another subscription already uses "
                        "the same source, subject type, "
                        "and display name."
                    )
                )

        subscription.display_name = display_name
        subscription.match_mode = match_mode
        subscription.match_terms = match_terms
        subscription.enabled = enabled

        self.session.flush()
        self.session.refresh(subscription)

        return subscription
