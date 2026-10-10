"""
Smart BethG - Web Search (T1001)

Real search via the Brave Search API - not a scrape of a search engine's
results page (unreliable and against most engines' terms), and not
faked. If BRAVE_SEARCH_API_KEY isn't set, search() raises RuntimeError
with an honest message rather than returning fabricated results.
"""
import requests

import config
from logging_setup import get_logger

logger = get_logger("task")

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class SearchService:
    def __init__(self, api_key=None):
        self.api_key = api_key if api_key is not None else config.BRAVE_SEARCH_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, count: int = 5):
        if not self.api_key:
            raise RuntimeError(
                "Web search isn't configured on this deployment "
                "(set BRAVE_SEARCH_API_KEY)."
            )
        query = (query or "").strip()
        if not query:
            raise ValueError("Search query must not be empty.")

        response = requests.get(
            BRAVE_ENDPOINT,
            params={"q": query, "count": count},
            headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for item in (data.get("web", {}) or {}).get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        logger.info("Web search: query=%r results=%d", query, len(results))
        return results
