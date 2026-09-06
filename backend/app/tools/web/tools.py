"""Web tools: web_search, open_url, extract_page.

web_search uses DuckDuckGo's keyless HTML "lite" endpoint -- no API key
required, so search works out of the box. Fetched web content is always
data, never instructions: results are returned as plain structured text for
the caller to reason about, never executed or treated as commands.
"""
from __future__ import annotations

from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.security import prompt_injection
from app.tools.base import PermissionLevel, RiskLevel, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry
from app.tools.web.fetch import USER_AGENT, FetchError, UrlBlockedError, fetch_url

_DUCKDUCKGO_LITE_URL = "https://lite.duckduckgo.com/lite/"
_MAX_EXTRACTED_CHARS = 20_000


class WebSearchArgs(BaseModel):
    query: str
    max_results: int = Field(default=5, ge=1, le=20)


async def web_search(args: WebSearchArgs) -> ToolResult:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=settings.web_request_timeout_seconds, headers={"User-Agent": USER_AGENT}
        ) as client:
            response = await client.post(_DUCKDUCKGO_LITE_URL, data={"q": args.query})
    except httpx.HTTPError as exc:
        return ToolResult.fail("SEARCH_FAILED", f"Web search request failed: {exc}")

    if response.status_code >= 400:
        return ToolResult.fail("SEARCH_FAILED", f"Search provider returned HTTP {response.status_code}")

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict] = []
    for link in soup.select("a.result-link"):
        href = link.get("href")
        title = link.get_text(strip=True)
        if not href or not title:
            continue
        snippet_el = link.find_parent("tr")
        snippet = ""
        if snippet_el:
            snippet_row = snippet_el.find_next_sibling("tr")
            if snippet_row:
                snippet = snippet_row.get_text(strip=True)
        results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= args.max_results:
            break

    return ToolResult.ok(
        data={"query": args.query, "results": results},
        provider="duckduckgo",
        result_count=len(results),
    )


class OpenUrlArgs(BaseModel):
    url: str


async def open_url(args: OpenUrlArgs) -> ToolResult:
    settings = get_settings()
    try:
        page = await fetch_url(args.url, settings)
    except UrlBlockedError as exc:
        return ToolResult.fail("URL_BLOCKED", str(exc))
    except FetchError as exc:
        return ToolResult.fail("FETCH_FAILED", str(exc))

    title = ""
    text = page.text
    if "html" in page.content_type:
        soup = BeautifulSoup(page.text, "html.parser")
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

    truncated = page.truncated or len(text) > _MAX_EXTRACTED_CHARS
    text = text[:_MAX_EXTRACTED_CHARS]

    matches = prompt_injection.scan(text)
    text = prompt_injection.annotate(text, matches)

    return ToolResult.ok(
        data={
            "final_url": page.final_url,
            "status_code": page.status_code,
            "title": title,
            # Explicitly labeled so the model treats this as data, not instructions.
            "untrusted_page_text": text,
        },
        truncated=truncated,
        prompt_injection_suspected=bool(matches),
    )


class ExtractPageArgs(BaseModel):
    url: str
    max_links: int = Field(default=10, ge=0, le=50)


async def extract_page(args: ExtractPageArgs) -> ToolResult:
    settings = get_settings()
    try:
        page = await fetch_url(args.url, settings)
    except UrlBlockedError as exc:
        return ToolResult.fail("URL_BLOCKED", str(exc))
    except FetchError as exc:
        return ToolResult.fail("FETCH_FAILED", str(exc))

    if "html" not in page.content_type:
        return ToolResult.fail(
            "UNSUPPORTED_CONTENT_TYPE", f"Cannot extract page content from '{page.content_type}'"
        )

    soup = BeautifulSoup(page.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True) if main else ""

    links: list[str] = []
    if args.max_links:
        seen: set[str] = set()
        for a in soup.select("a[href]"):
            # bs4's attribute-value type is technically `str | list[str]`
            # (multi-valued per the HTML spec for some attributes) --
            # `href` is never actually multi-valued in practice.
            raw_href = a["href"]
            href_attr = raw_href[0] if isinstance(raw_href, list) else raw_href
            href = urljoin(page.final_url, href_attr)
            if href.startswith("http") and href not in seen:
                seen.add(href)
                links.append(href)
            if len(links) >= args.max_links:
                break

    truncated = page.truncated or len(text) > _MAX_EXTRACTED_CHARS
    text = text[:_MAX_EXTRACTED_CHARS]

    matches = prompt_injection.scan(text)
    text = prompt_injection.annotate(text, matches)

    return ToolResult.ok(
        data={
            "final_url": page.final_url,
            "title": title,
            "untrusted_page_text": text,
            "links": links,
        },
        truncated=truncated,
        prompt_injection_suspected=bool(matches),
    )


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="web_search",
            description="Search the web (DuckDuckGo) and return titles, URLs, and snippets.",
            args_model=WebSearchArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            timeout_seconds=20.0,
            handler=web_search,
        )
    )
    registry.register(
        ToolDefinition(
            name="open_url",
            description="Fetch a URL and return its page title and extracted text.",
            args_model=OpenUrlArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            timeout_seconds=20.0,
            handler=open_url,
        )
    )
    registry.register(
        ToolDefinition(
            name="extract_page",
            description="Fetch a URL and return its main readable content plus outbound links.",
            args_model=ExtractPageArgs,
            risk_level=RiskLevel.SAFE,
            permission_level=PermissionLevel.SAFE,
            timeout_seconds=20.0,
            handler=extract_page,
        )
    )
