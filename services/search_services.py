"""
Smart BethG
Web Search Service

This is the first external knowledge connector.

It uses DuckDuckGo's non-JavaScript HTML search interface as a
basic search connector. It returns links and snippets to the
application; the AI runtime can later use those results as
research context.

This is deliberately kept separate from the AI runtime so that
another search provider can be added later without rewriting
the agent system.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from typing import Any


SEARCH_URL = (
    "https://html.duckduckgo.com/html/"
)


class SearchServiceError(Exception):
    """Raised when web search cannot be completed."""


def _clean_text(value: str) -> str:
    """
    Remove HTML markup and normalise whitespace.
    """

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = html.unescape(value)

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _extract_results(
    page: str,
    limit: int,
) -> list[dict[str, str]]:
    """
    Extract basic search results from the HTML page.

    The parser intentionally returns only the information that
    Smart BethG needs at this stage.
    """

    results: list[dict[str, str]] = []

    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"'
        r'[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    matches = pattern.findall(page)

    for raw_url, raw_title in matches:

        if len(results) >= limit:
            break

        url = html.unescape(
            raw_url
        )

        title = _clean_text(
            raw_title
        )

        if not url or not title:
            continue

        results.append(
            {
                "title": title,
                "url": url,
                "snippet": "",
            }
        )

    snippet_pattern = re.compile(
        r'<a[^>]+class="result__snippet"[^>]*>'
        r'(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )

    snippets = [
        _clean_text(item)
        for item in snippet_pattern.findall(page)
    ]

    for index, result in enumerate(results):

        if index < len(snippets):
            result["snippet"] = snippets[index]

    return results


def search_web(
    query: str,
    limit: int = 8,
    timeout: int = 20,
) -> dict[str, Any]:
    """
    Search the public web.

    Returns a normalized result structure.
    """

    query = query.strip()

    if not query:
        raise ValueError(
            "Search query cannot be empty."
        )

    limit = max(
        1,
        min(limit, 15),
    )

    params = urllib.parse.urlencode(
        {
            "q": query,
        }
    )

    url = (
        f"{SEARCH_URL}?{params}"
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "SmartBethG/1.0 "
                "(research workspace)"
            ),
            "Accept": "text/html",
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            page = response.read().decode(
                "utf-8",
                errors="replace",
            )

    except Exception as exc:

        raise SearchServiceError(
            f"Web search failed: {exc}"
        ) from exc

    results = _extract_results(
        page,
        limit,
    )

    return {
        "ok": True,
        "query": query,
        "provider": "duckduckgo-html",
        "results": results,
        "count": len(results),
    }
