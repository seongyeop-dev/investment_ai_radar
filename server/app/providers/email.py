from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.core.config import Settings
from app.models.disclosures import ProviderStatus
from app.models.operations import NotificationProvider


@dataclass(frozen=True, slots=True)
class EmailSendResult:
    success: bool
    provider_message_id: str | None = None
    error_code: str | None = None


class EmailProvider(Protocol):
    provider: NotificationProvider

    @property
    def status(self) -> ProviderStatus: ...

    def send(
        self, *, sender: str, recipient: str, subject: str, content: str
    ) -> EmailSendResult: ...


class DisabledEmailProvider:
    provider = NotificationProvider.DISABLED
    status = ProviderStatus.NOT_CONFIGURED

    def send(
        self, *, sender: str, recipient: str, subject: str, content: str
    ) -> EmailSendResult:
        del sender, recipient, subject, content
        return EmailSendResult(success=False, error_code="NOT_CONFIGURED")


class SmtpEmailProvider:
    provider = NotificationProvider.SMTP

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def status(self) -> ProviderStatus:
        return (
            ProviderStatus.READY
            if self.settings.email_configured and self.settings.email_provider == "SMTP"
            else ProviderStatus.NOT_CONFIGURED
        )

    def send(
        self, *, sender: str, recipient: str, subject: str, content: str
    ) -> EmailSendResult:
        if self.status is not ProviderStatus.READY:
            return EmailSendResult(False, error_code="NOT_CONFIGURED")
        message = EmailMessage()
        message["From"] = sender
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(content)
        with smtplib.SMTP(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.email_timeout_seconds,
        ) as client:
            if self.settings.smtp_use_tls:
                client.starttls()
            client.login(self.settings.smtp_username, self.settings.smtp_password)
            response = client.send_message(message)
        return EmailSendResult(
            success=not response,
            provider_message_id="smtp-accepted" if not response else None,
            error_code=None if not response else "SMTP_REJECTED",
        )


class ResendEmailProvider:
    provider = NotificationProvider.RESEND

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client

    @property
    def status(self) -> ProviderStatus:
        return (
            ProviderStatus.READY
            if self.settings.email_configured and self.settings.email_provider == "RESEND"
            else ProviderStatus.NOT_CONFIGURED
        )

    def send(
        self, *, sender: str, recipient: str, subject: str, content: str
    ) -> EmailSendResult:
        if self.status is not ProviderStatus.READY:
            return EmailSendResult(False, error_code="NOT_CONFIGURED")
        owns_client = self.client is None
        client = self.client or httpx.Client()
        try:
            response = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": sender,
                    "to": [recipient],
                    "subject": subject,
                    "text": content,
                },
                timeout=float(self.settings.email_timeout_seconds),
            )
            response.raise_for_status()
            return EmailSendResult(True, provider_message_id=response.json().get("id"))
        except (httpx.HTTPError, ValueError):
            return EmailSendResult(False, error_code="RESEND_REQUEST_FAILED")
        finally:
            if owns_client:
                client.close()


class FakeEmailProvider:
    provider = NotificationProvider.FAKE
    status = ProviderStatus.READY

    def __init__(self, *, failures_before_success: int = 0) -> None:
        self.failures_before_success = failures_before_success
        self.attempts = 0
        self.messages: list[dict[str, str]] = []

    def send(
        self, *, sender: str, recipient: str, subject: str, content: str
    ) -> EmailSendResult:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            return EmailSendResult(False, error_code="FAKE_FAILURE")
        self.messages.append(
            {
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "content": content,
            }
        )
        return EmailSendResult(True, provider_message_id=f"fake-{self.attempts}")


def email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "SMTP":
        return SmtpEmailProvider(settings)
    if settings.email_provider == "RESEND":
        return ResendEmailProvider(settings)
    return DisabledEmailProvider()
