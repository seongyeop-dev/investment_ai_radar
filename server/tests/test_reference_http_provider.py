from __future__ import annotations

import httpx
import pytest

from app.providers.reference_http import (
    ReferenceHttpError,
    ReferenceHttpProvider,
)


def _provider(
    handler,
    *,
    max_html_bytes: int = 2_000_000,
) -> ReferenceHttpProvider:
    return ReferenceHttpProvider(
        allowed_hosts={
            "example.test",
        },
        max_html_bytes=max_html_bytes,
        transport=httpx.MockTransport(handler),
    )


def test_reference_http_provider_returns_html() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.host == "example.test"

        return httpx.Response(
            200,
            headers={
                "content-type": ("text/html; charset=utf-8"),
            },
            content=b"<html><body>ok</body></html>",
            request=request,
        )

    result = _provider(handler).fetch_html("https://example.test/index")

    assert result.status_code == 200
    assert result.final_url == ("https://example.test/index")
    assert "<body>ok</body>" in result.html
    assert result.content_length > 0


def test_reference_http_provider_allows_safe_redirect() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(
                302,
                headers={
                    "location": "/final",
                },
                request=request,
            )

        return httpx.Response(
            200,
            headers={
                "content-type": "text/html",
            },
            content=b"<html>final</html>",
            request=request,
        )

    result = _provider(handler).fetch_html("https://example.test/start")

    assert result.final_url == ("https://example.test/final")


def test_reference_http_provider_blocks_external_redirect() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            302,
            headers={
                "location": ("https://attacker.test/page"),
            },
            request=request,
        )

    with pytest.raises(
        ReferenceHttpError,
        match="hostname is not allowed",
    ):
        _provider(handler).fetch_html("https://example.test/start")


def test_reference_http_provider_rejects_non_html() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "application/pdf",
            },
            content=b"%PDF",
            request=request,
        )

    with pytest.raises(
        ReferenceHttpError,
        match="not HTML",
    ):
        _provider(handler).fetch_html("https://example.test/document")


def test_reference_http_provider_enforces_size_limit() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html",
            },
            content=b"x" * 101,
            request=request,
        )

    with pytest.raises(
        ReferenceHttpError,
        match="size limit",
    ):
        _provider(
            handler,
            max_html_bytes=100,
        ).fetch_html("https://example.test/large")


def test_reference_http_provider_requires_https() -> None:
    provider = _provider(
        lambda request: httpx.Response(
            200,
            request=request,
        )
    )

    with pytest.raises(
        ReferenceHttpError,
        match="must use HTTPS",
    ):
        provider.fetch_html("http://example.test/index")


def test_reference_http_provider_decodes_utf16_le_html() -> None:
    html = '<html><body><a href="/letters/2024ltr.pdf">2024</a></body></html>'

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html",
            },
            content=html.encode("utf-16-le"),
            request=request,
        )

    result = _provider(handler).fetch_html("https://example.test/letters")

    assert 'href="/letters/2024ltr.pdf"' in result.html
    assert ">2024<" in result.html


def test_reference_http_provider_decodes_brotli_html() -> None:
    import brotli

    html = '<html><body><a href="/letters/2024ltr.pdf">2024</a></body></html>'

    compressed = brotli.compress(html.encode("utf-8"))

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html",
                "content-encoding": "br",
                "content-length": str(len(compressed)),
            },
            content=compressed,
            request=request,
        )

    result = _provider(handler).fetch_html("https://example.test/letters")

    assert result.status_code == 200
    assert "<html>" in result.html
    assert 'href="/letters/2024ltr.pdf"' in result.html
    assert ">2024<" in result.html
