"""Shared, size- and target-restricted HTTP fetching for web tools."""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import Settings

USER_AGENT = "AuroraAssistant/0.1 (+personal AI assistant; see project README)"


class UrlBlockedError(Exception):
    """Raised when a URL fails scheme/host validation (SSRF-lite guard)."""


class FetchError(Exception):
    pass


@dataclass
class FetchedPage:
    final_url: str
    status_code: int
    content_type: str
    text: str
    truncated: bool


def _assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UrlBlockedError(f"Unsupported URL scheme: {parsed.scheme!r} (only http/https allowed)")
    if not parsed.hostname:
        raise UrlBlockedError("URL has no hostname")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise UrlBlockedError(f"Could not resolve host: {parsed.hostname}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise UrlBlockedError(
                f"URL resolves to a non-public address ({ip}); refusing to fetch internal/local network targets"
            )


async def fetch_url(url: str, settings: Settings) -> FetchedPage:
    """Fetch `url`, enforcing scheme/host safety, a timeout, and a size cap."""
    _assert_public_http_url(url)

    try:
        async with httpx.AsyncClient(
            timeout=settings.web_request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            async with client.stream("GET", url) as response:
                # Redirects are followed by httpx before we see the final
                # response, but the *final* destination must also be public --
                # re-validate it here to close the redirect-to-internal gap.
                _assert_public_http_url(str(response.url))

                chunks: list[bytes] = []
                total = 0
                truncated = False
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > settings.web_max_response_bytes:
                        truncated = True
                        break
                    chunks.append(chunk)

                body = b"".join(chunks)
                content_type = response.headers.get("content-type", "")
                encoding = response.encoding or "utf-8"
                text = body.decode(encoding, errors="replace")

                return FetchedPage(
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    text=text,
                    truncated=truncated,
                )
    except httpx.HTTPError as exc:
        raise FetchError(f"Request failed: {exc}") from exc
