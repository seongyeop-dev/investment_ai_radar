from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

DEFAULT_MAX_HTML_BYTES = 2_000_000
DEFAULT_MAX_REDIRECTS = 3


def _decode_html_bytes(
    content: bytes,
    declared_encoding: str | None,
) -> str:
    if content.startswith(
        (
            b"\xff\xfe",
            b"\xfe\xff",
        )
    ):
        return content.decode(
            "utf-16",
            errors="replace",
        )

    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode(
            "utf-8-sig",
            errors="replace",
        )

    sample = content[:2048]

    if sample:
        even_bytes = sample[0::2]
        odd_bytes = sample[1::2]

        even_null_ratio = even_bytes.count(0) / max(len(even_bytes), 1)
        odd_null_ratio = odd_bytes.count(0) / max(len(odd_bytes), 1)

        if odd_null_ratio >= 0.25 and even_null_ratio <= 0.05:
            return content.decode(
                "utf-16-le",
                errors="replace",
            )

        if even_null_ratio >= 0.25 and odd_null_ratio <= 0.05:
            return content.decode(
                "utf-16-be",
                errors="replace",
            )

    encodings = [
        declared_encoding,
        "utf-8",
        "windows-1252",
    ]

    checked: set[str] = set()

    for encoding in encodings:
        if not encoding:
            continue

        normalized = encoding.casefold()

        if normalized in checked:
            continue

        checked.add(normalized)

        try:
            return content.decode(encoding)
        except (
            LookupError,
            UnicodeDecodeError,
        ):
            continue

    return content.decode(
        "utf-8",
        errors="replace",
    )


class ReferenceHttpError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceHttpResponse:
    requested_url: str
    final_url: str
    html: str
    status_code: int
    content_length: int


class ReferenceHttpProvider:
    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        timeout_seconds: float = 15.0,
        max_html_bytes: int = DEFAULT_MAX_HTML_BYTES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized_hosts = {
            host.strip().lower().rstrip(".") for host in allowed_hosts if host.strip()
        }

        if not normalized_hosts:
            raise ValueError("allowed_hosts must not be empty")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        if max_html_bytes <= 0:
            raise ValueError("max_html_bytes must be positive")

        if max_redirects < 0:
            raise ValueError("max_redirects must not be negative")

        self.allowed_hosts = normalized_hosts
        self.timeout_seconds = timeout_seconds
        self.max_html_bytes = max_html_bytes
        self.max_redirects = max_redirects
        self.transport = transport

    def fetch_html(
        self,
        url: str,
    ) -> ReferenceHttpResponse:
        requested_url = self._validate_url(url)
        current_url = requested_url

        headers = {
            "Accept": ("text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"),
            "Accept-Language": "en-US,en;q=0.8",
            "User-Agent": ("InvestmentAIRadar/0.1 (public-metadata-validation)"),
        }

        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
            headers=headers,
        ) as client:
            for redirect_count in range(self.max_redirects + 1):
                try:
                    response = client.get(current_url)
                except httpx.HTTPError as exc:
                    raise ReferenceHttpError("reference HTTP request failed") from exc

                if response.status_code in {
                    301,
                    302,
                    303,
                    307,
                    308,
                }:
                    if redirect_count >= self.max_redirects:
                        raise ReferenceHttpError("reference redirect limit exceeded")

                    location = response.headers.get("location")

                    if not location:
                        raise ReferenceHttpError("reference redirect has no location")

                    redirected_url = urljoin(
                        current_url,
                        location,
                    )

                    current_url = self._validate_url(redirected_url)
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise ReferenceHttpError(
                        f"reference HTTP status {response.status_code}"
                    ) from exc

                content_type = (
                    response.headers.get(
                        "content-type",
                        "",
                    )
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )

                if content_type not in {
                    "text/html",
                    "application/xhtml+xml",
                }:
                    raise ReferenceHttpError(
                        f"reference response is not HTML: {content_type or 'missing'}"
                    )

                declared_length = response.headers.get("content-length")

                if declared_length:
                    try:
                        parsed_length = int(declared_length)
                    except ValueError as exc:
                        raise ReferenceHttpError("invalid content-length") from exc

                    if parsed_length > self.max_html_bytes:
                        raise ReferenceHttpError("reference HTML exceeds size limit")

                content = response.content

                if len(content) > self.max_html_bytes:
                    raise ReferenceHttpError("reference HTML exceeds size limit")

                html = _decode_html_bytes(
                    content,
                    response.encoding,
                )

                return ReferenceHttpResponse(
                    requested_url=requested_url,
                    final_url=str(response.url),
                    html=html,
                    status_code=response.status_code,
                    content_length=len(content),
                )

        raise ReferenceHttpError("reference HTTP request did not complete")

    def _validate_url(
        self,
        value: str,
    ) -> str:
        parsed = urlsplit(value.strip())

        if parsed.scheme.lower() != "https":
            raise ReferenceHttpError("reference URL must use HTTPS")

        hostname = (parsed.hostname or "").lower().rstrip(".")

        if not hostname:
            raise ReferenceHttpError("reference URL has no hostname")

        if hostname not in self.allowed_hosts:
            raise ReferenceHttpError(f"reference hostname is not allowed: {hostname}")

        if parsed.username or parsed.password:
            raise ReferenceHttpError("reference URL credentials are not allowed")

        if parsed.port is not None and parsed.port != 443:
            raise ReferenceHttpError("reference URL port is not allowed")

        return value.strip()
