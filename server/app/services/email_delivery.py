from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.backoff import ReconnectBackoff
from app.core.config import Settings
from app.models.disclosures import ProviderStatus
from app.models.operations import (
    BriefingRecord,
    BriefingStatus,
    DeliveryStatus,
    NotificationDeliveryRecord,
)
from app.providers.email import EmailProvider, email_provider
from app.services.briefings import BriefingService

TRUST_EXPLANATION = "사실일 확률이 아니라 현재 확보된 증거 강도입니다."


def mask_email(value: str | None) -> str | None:
    if not value or "@" not in value:
        return None
    local, domain = value.rsplit("@", 1)
    visible = local[:2] if len(local) > 2 else local[:1]
    return f"{visible}***@{domain}"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: DeliveryStatus
    delivery: NotificationDeliveryRecord | None
    duplicate: bool = False


class EmailDeliveryService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        provider: EmailProvider | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider or email_provider(settings)
        self.sleep = sleep or time.sleep
        self.backoff = ReconnectBackoff(jitter_ratio=0, maximum_seconds=4)

    def send(
        self,
        briefing: BriefingRecord,
        *,
        recipient: str | None = None,
        now: datetime,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> DeliveryResult:
        resolved_recipient = (recipient or self.settings.email_to).strip()
        recipient_hash = hashlib.sha256(
            (resolved_recipient or "not-configured").encode()
        ).hexdigest()
        key = hashlib.sha256(
            f"{briefing.id}|{recipient_hash}|{self.provider.provider.value}".encode()
        ).hexdigest()
        existing = self.session.scalar(
            select(NotificationDeliveryRecord).where(
                NotificationDeliveryRecord.idempotency_key == key
            )
        )
        if existing is not None:
            return DeliveryResult(existing.status, existing, duplicate=True)
        if dry_run:
            return DeliveryResult(DeliveryStatus.PENDING, None)
        if (
            not confirm
            or not self.settings.email_configured
            or not resolved_recipient
            or self.provider.status is not ProviderStatus.READY
        ):
            delivery = NotificationDeliveryRecord(
                briefing_id=briefing.id,
                provider=self.provider.provider,
                recipient_hash=recipient_hash,
                status=DeliveryStatus.NOT_CONFIGURED,
                attempted_at=now,
                error_code="NOT_CONFIGURED",
                error_summary="Email provider is not fully configured.",
                idempotency_key=key,
            )
            self.session.add(delivery)
            self.session.flush()
            return DeliveryResult(delivery.status, delivery)

        content = self.render(briefing)
        delivery = NotificationDeliveryRecord(
            briefing_id=briefing.id,
            provider=self.provider.provider,
            recipient_hash=recipient_hash,
            status=DeliveryStatus.PENDING,
            attempted_at=now,
            idempotency_key=key,
        )
        self.session.add(delivery)
        self.session.flush()
        last_code = "EMAIL_FAILED"
        for attempt in range(self.settings.email_max_retries):
            try:
                result = self.provider.send(
                    sender=self.settings.email_from,
                    recipient=resolved_recipient,
                    subject=briefing.title,
                    content=content,
                )
            except (OSError, TimeoutError):
                result = None
            delivery.retry_count = attempt
            if result and result.success:
                delivery.status = DeliveryStatus.SENT
                delivery.provider_message_id = result.provider_message_id
                delivery.delivered_at = now
                briefing.status = BriefingStatus.SENT
                self.session.flush()
                return DeliveryResult(delivery.status, delivery)
            if result and result.error_code:
                last_code = result.error_code
            if attempt + 1 < self.settings.email_max_retries:
                self.sleep(self.backoff.delay(attempt))
        delivery.status = DeliveryStatus.FAILED
        delivery.failed_at = now
        delivery.error_code = last_code
        delivery.error_summary = "Provider delivery failed without credential details."
        briefing.status = BriefingStatus.FAILED
        self.session.flush()
        return DeliveryResult(delivery.status, delivery)

    def render(self, briefing: BriefingRecord) -> str:
        items = BriefingService(self.session).items(briefing.id)
        lines = [
            briefing.title,
            briefing.compact_summary,
            "",
            TRUST_EXPLANATION,
        ]
        for item in items:
            lines.extend(
                [
                    "",
                    f"[{item.category}] {item.headline}",
                    item.short_summary,
                    f"검증 상태: {item.verification_status.value}",
                    f"증거 강도: {item.trust_score}",
                    (
                        f"사건 상세: {self.settings.app_public_base_url}"
                        f"/events/{item.information_event_id}"
                    ),
                ]
            )
            lines.extend(f"원문 참조: {link['url']}" for link in item.source_links)
            lines.extend(f"공식 자료: {link['url']}" for link in item.official_reference_links)
        lines.extend(
            [
                "",
                "상세 내용은 원문·공식 자료·Web 사건 상세에서 확인하십시오.",
                "최종 투자 판단과 책임은 사용자에게 있습니다.",
                "이 브리핑은 매수·매도 추천이나 자동 주문이 아닙니다.",
            ]
        )
        return "\n".join(lines)
