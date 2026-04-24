"""SearchCollectorAgent — uses Tavily API to discover and extract GitHub projects.

Data flow:
    Tavily Search (github.com domain)
        → extract repo metadata from results
        → Tavily Extract (individual repo URLs)
        → List[RawProject] with README content

Advantages over BeautifulSoup:
    - No HTML parsing maintenance
    - Returns structured results with title, URL, description
    - Extract API returns markdown content (README) directly
    - Search depth configurable (basic/advanced)

Failure modes:
    - API key missing → raise immediately with clear message
    - Search returns no results → return empty list
    - Extract fails for a URL → skip that project's README, continue with metadata
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from tavily import AsyncTavilyClient

from gtrdashboard.models import RawProject


_GITHUB_URL_RE = re.compile(r"https://github\.com/([^/]+)/([^/]+)")


@dataclass
class SearchCollectorConfig:
    """Configuration for SearchCollector."""

    languages: list[str]
    limit: int = 50
    search_depth: str = "advanced"  # basic | advanced
    include_domains: list[str] | None = None
    max_extract_chars: int = 20000

    def __post_init__(self) -> None:
        if self.include_domains is None:
            self.include_domains = ["github.com"]


class SearchCollectorAgent:
    """Discovers GitHub projects via Tavily Search + Extract."""

    def __init__(self, config: Optional[SearchCollectorConfig] = None) -> None:
        self.config = config or SearchCollectorConfig(languages=["python"])
        self._client: Optional[AsyncTavilyClient] = None

    def _get_client(self) -> AsyncTavilyClient:
        """Lazy-init Tavily client with API key validation."""
        if self._client is not None:
            return self._client

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "TAVILY_API_KEY environment variable is required. "
                "Get one at https://tavily.com"
            )
        self._client = AsyncTavilyClient(api_key=api_key)
        return self._client

    async def collect(self) -> list[RawProject]:
        """Discover trending/popular GitHub projects via Tavily Search.

        For each configured language, constructs a search query targeting
        github.com and returns deduplicated RawProject objects.
        """
        client = self._get_client()
        all_projects: list[RawProject] = []
        seen_urls: set[str] = set()

        for lang in self.config.languages:
            query = (
                f"github trending {lang} open source projects "
                f"local AI deployment tools"
            )
            try:
                results = await client.search(
                    query=query,
                    max_results=self.config.limit,
                    search_depth=self.config.search_depth,
                    include_domains=self.config.include_domains,
                )
                for item in results.get("results", []):
                    project = self._parse_result(item)
                    if project and project.github_url not in seen_urls:
                        seen_urls.add(project.github_url)
                        all_projects.append(project)
            except Exception as e:
                print(f"[SearchCollector] Tavily search failed for {lang}: {e}")
                continue

        return all_projects[: self.config.limit]

    def _parse_result(self, item: dict) -> Optional[RawProject]:
        """Map a single Tavily search result to RawProject."""
        url = item.get("url", "")
        match = _GITHUB_URL_RE.match(url)
        if not match:
            return None

        owner, name = match.group(1), match.group(2)

        # Tavily provides title and content snippet
        title = item.get("title", "")
        content = item.get("content", "")

        # Extract description from title or content
        description = content.strip() if content else title
        if len(description) > 500:
            description = description[:497] + "..."

        return RawProject(
            github_url=url,
            name=name,
            owner=owner,
            language=None,  # Will be filled by profiler or README analysis
            stars=None,     # Not available from search API; profiler estimates
            description=description,
        )

    async def fetch_readme(self, owner: str, name: str) -> Optional[str]:
        """Fetch README content for a repository via Tavily Extract.

        Returns markdown text, truncated to max_extract_chars.
        """
        client = self._get_client()
        repo_url = f"https://github.com/{owner}/{name}"

        try:
            result = await client.extract(
                urls=[repo_url],
                include_images=False,
            )
            # Extract API returns {"results": [{"url": ..., "raw_content": ...}]}
            for item in result.get("results", []):
                text = item.get("raw_content", "")
                if text:
                    if len(text) > self.config.max_extract_chars:
                        text = text[: self.config.max_extract_chars] + "\n... [truncated]"
                    return text
        except Exception as e:
            print(f"[SearchCollector] Extract failed for {owner}/{name}: {e}")

        return None

    async def close(self) -> None:
        """Tavily client is stateless; nothing to close."""
        pass
