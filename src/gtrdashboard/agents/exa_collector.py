"""ExaCollectorAgent — semantic discovery for "hidden gem" projects.

Data flow:
    Exa semantic search (natural language query)
        → results from across the web (HN, Reddit, blogs, GitHub)
        → filter to GitHub URLs
        → List[RawProject]

Use cases:
    - Find projects discussed on HN/Reddit but not yet on GitHub Trending
    - Discover side projects mentioned in blog posts
    - Semantic targeting: "run LLMs on a laptop without GPU"

Failure modes:
    - API key missing → raise immediately
    - No GitHub URLs in results → return empty list
    - Exa returns non-repo pages → filter gracefully
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from exa_py import Exa

from gtrdashboard.models import RawProject


_GITHUB_URL_RE = re.compile(r"https://github\.com/([^/]+)/([^/]+)")


@dataclass
class ExaCollectorConfig:
    """Configuration for ExaCollector."""

    limit: int = 20
    search_type: str = "auto"  # instant | fast | auto | deep-lite | deep | deep-reasoning
    highlights: bool = True
    num_highlights: int = 3
    query: str = (
        "open source project for running large language models locally "
        "on personal computer without internet connection"
    )


class ExaCollectorAgent:
    """Discovers GitHub projects via Exa semantic search."""

    def __init__(self, config: Optional[ExaCollectorConfig] = None) -> None:
        self.config = config or ExaCollectorConfig()
        self._client: Optional[Exa] = None

    def _get_client(self) -> Exa:
        """Lazy-init Exa client with API key validation."""
        if self._client is not None:
            return self._client

        api_key = os.environ.get("EXA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "EXA_API_KEY environment variable is required. "
                "Get one at https://exa.ai"
            )
        self._client = Exa(api_key=api_key)
        return self._client

    async def collect(self) -> list[RawProject]:
        """Run semantic search and return GitHub projects.

        Exa is synchronous; we wrap in async for interface consistency.
        """
        import asyncio

        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> list[RawProject]:
        """Synchronous Exa search wrapped for async compat."""
        client = self._get_client()
        projects: list[RawProject] = []
        seen_urls: set[str] = set()

        try:
            response = client.search(
                self.config.query,
                num_results=self.config.limit,
                type=self.config.search_type,
                highlights={
                    "num_highlights": self.config.num_highlights,
                } if self.config.highlights else None,
            )
        except Exception as e:
            print(f"[ExaCollector] Search failed: {e}")
            return []

        for result in response.results:
            url = getattr(result, "url", "")
            match = _GITHUB_URL_RE.match(url)
            if not match:
                continue

            if url in seen_urls:
                continue
            seen_urls.add(url)

            owner, name = match.group(1), match.group(2)

            # Use highlight snippets or title as description
            title = getattr(result, "title", "")
            hl_list = getattr(result, "highlights", []) or []
            description = " ".join(hl_list) if hl_list else title
            if len(description) > 500:
                description = description[:497] + "..."

            projects.append(
                RawProject(
                    github_url=url,
                    name=name,
                    owner=owner,
                    language=None,
                    stars=None,
                    description=description,
                )
            )

        return projects

    async def fetch_readme(self, _owner: str, _name: str) -> Optional[str]:
        """Exa does not support per-URL extraction; return None.

        README content should be fetched via SearchCollectorAgent.fetch_readme
        or by the profiler using Tavily Extract.
        """
        return None

    async def close(self) -> None:
        """Exa client is stateless; nothing to close."""
        pass
