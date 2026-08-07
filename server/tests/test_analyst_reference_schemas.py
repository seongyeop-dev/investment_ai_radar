from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.analyst_references import (
    AnalystReferenceImportLinkPreview,
    AnalystReferenceImportLinkRequest,
)

PORTFOLIO_ID = "00000000-0000-0000-0000-000000000001"


def _request_payload() -> dict[str, object]:
    return {
        "sourceUrl": (" https://example.com/research/schema-validation?document=1 "),
        "publisherName": " Schema Validation Publisher ",
        "publisherType": "RESEARCH_HOUSE",
        "title": " Schema Validation Title ",
        "analystName": " Validation Analyst ",
        "publishedAt": "2026-07-29T09:00:00+09:00",
        "accessType": "PUBLIC",
        "documentType": "REPORT",
        "publisherRatingRaw": " Published rating metadata ",
        "publisherTargetPriceRaw": " Published target metadata ",
        "targetCurrency": " krw ",
        "publicAbstract": " Public metadata validation text. ",
        "portfolioItemIds": [PORTFOLIO_ID],
    }


def test_import_link_request_normalizes_metadata() -> None:
    request = AnalystReferenceImportLinkRequest.model_validate(_request_payload())

    assert request.source_url == ("https://example.com/research/schema-validation?document=1")
    assert request.publisher_name == "Schema Validation Publisher"
    assert request.title == "Schema Validation Title"
    assert request.analyst_name == "Validation Analyst"
    assert request.target_currency == "KRW"
    assert request.public_abstract == ("Public metadata validation text.")
    assert request.portfolio_item_ids == [UUID(PORTFOLIO_ID)]
    assert request.published_at.utcoffset() is not None
    assert request.confirm is False


@pytest.mark.parametrize(
    "source_url",
    [
        "javascript:alert(1)",
        "file:///tmp/report.pdf",
        "data:text/plain,metadata",
        "ftp://example.com/report",
        "/relative/report",
    ],
)
def test_import_link_request_rejects_non_http_urls(
    source_url: str,
) -> None:
    payload = _request_payload()
    payload["sourceUrl"] = source_url

    with pytest.raises(
        ValidationError,
        match=r"absolute HTTP\(S\) URL",
    ):
        AnalystReferenceImportLinkRequest.model_validate(payload)


def test_import_link_request_rejects_url_credentials() -> None:
    payload = _request_payload()
    payload["sourceUrl"] = "https://user:secret@example.com/research/report"

    with pytest.raises(
        ValidationError,
        match="must not include URL credentials",
    ):
        AnalystReferenceImportLinkRequest.model_validate(payload)


def test_import_link_request_requires_published_timezone() -> None:
    payload = _request_payload()
    payload["publishedAt"] = "2026-07-29T09:00:00"

    with pytest.raises(
        ValidationError,
        match="must include timezone information",
    ):
        AnalystReferenceImportLinkRequest.model_validate(payload)


def test_import_link_request_rejects_oversized_abstract() -> None:
    payload = _request_payload()
    payload["publicAbstract"] = "a" * 301

    with pytest.raises(ValidationError) as exc_info:
        AnalystReferenceImportLinkRequest.model_validate(payload)

    error_locations = {error["loc"][-1] for error in exc_info.value.errors()}

    assert "publicAbstract" in error_locations


def test_import_link_request_keeps_duplicate_portfolio_ids() -> None:
    payload = _request_payload()
    payload["portfolioItemIds"] = [
        PORTFOLIO_ID,
        PORTFOLIO_ID,
    ]

    request = AnalystReferenceImportLinkRequest.model_validate(payload)

    assert request.portfolio_item_ids == [
        UUID(PORTFOLIO_ID),
        UUID(PORTFOLIO_ID),
    ]


def test_import_link_preview_uses_camel_case_response() -> None:
    preview = AnalystReferenceImportLinkPreview.model_validate(
        {
            "normalizedUrl": ("https://example.com/research/schema-validation?document=1"),
            "sourceFingerprint": "a" * 64,
            "portfolioItems": [
                {
                    "id": PORTFOLIO_ID,
                    "symbol": "SCHEMA",
                    "name": "Schema Validation Item",
                    "market": "TEST",
                    "isArchived": False,
                }
            ],
            "validationWarnings": [],
            "duplicate": {
                "canonicalUrlDuplicate": False,
                "sourceFingerprintDuplicate": False,
                "canonicalUrlReferenceId": None,
                "sourceFingerprintReferenceId": None,
            },
            "wouldCreate": True,
            "confirmed": False,
        }
    )

    response = preview.model_dump(
        mode="json",
        by_alias=True,
    )

    assert response["normalizedUrl"].startswith("https://")
    assert response["sourceFingerprint"] == "a" * 64
    assert response["portfolioItems"][0]["isArchived"] is False
    assert response["duplicate"]["canonicalUrlDuplicate"] is False
    assert response["wouldCreate"] is True
    assert response["confirmed"] is False
