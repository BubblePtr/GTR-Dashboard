"""TrendingCollectorAgent — scrapes GitHub Trending for repository data.

Data flow:
    HTTP GET github.com/trending/{language}
        → BeautifulSoup parse
        → extract repository metadata
        → optional README fetch
        → List[RawProject]

Failure modes:
    - HTTP error → raise (orchestrator handles retry/fallback)
    - Parse error → log and skip malformed entries
    - Empty response → return empty list
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from gtrdashboard.models import RawProject


GITHUB_TRENDING_URL = "https://github.com/trending"
DEFAULT_TIMEOUT = 30.0


@dataclass
class CollectorConfig:
    """Configuration for TrendingCollector."""

    languages: list[str]
    limit: int = 50
    fetch_readme: bool = False
    timeout: float = DEFAULT_TIMEOUT


class TrendingCollectorAgent:
    """Scrapes GitHub Trending pages for repository metadata."""

    def __init__(self, config: Optional[CollectorConfig] = None) -> None:
        self.config = config or CollectorConfig(languages=["python", "typescript", "go"])
        self.client = httpx.AsyncClient(timeout=self.config.timeout, follow_redirects=True)

    async def collect(self) -> list[RawProject]:
        """Collect trending repositories from GitHub.

        Returns:
            List of RawProject objects, deduplicated across languages.
        """
        all_projects: list[RawProject] = []
        seen_urls: set[str] = set()

        for language in self.config.languages:
            # Empty string or "all" means overall trending (all languages)
            if not language or language.lower() == "all":
                url = GITHUB_TRENDING_URL
                lang_label = "all"
            else:
                url = f"{GITHUB_TRENDING_URL}/{language}"
                lang_label = language
            try:
                projects = await self._fetch_language(url, lang_label)
                for project in projects:
                    if project.github_url not in seen_urls:
                        seen_urls.add(project.github_url)
                        all_projects.append(project)
            except Exception as e:
                # Log but continue — partial data is better than no data
                print(f"[Collector] Failed to fetch {lang_label}: {e}")

        # Trim to limit
        return all_projects[: self.config.limit]

    async def _fetch_language(self, url: str, language: str) -> list[RawProject]:
        """Fetch and parse a single language's trending page."""
        response = await self.client.get(url)
        response.raise_for_status()
        return self._parse_html(response.text, language)

    def _parse_html(self, html: str, language: str) -> list[RawProject]:
        """Parse GitHub Trending HTML into RawProject objects."""
        soup = BeautifulSoup(html, "html.parser")
        projects: list[RawProject] = []

        # GitHub Trending uses article elements for each repo
        articles = soup.find_all("article", class_="Box-row")

        for article in articles:
            try:
                project = self._parse_article(article, language)
                if project:
                    projects.append(project)
            except Exception as e:
                print(f"[Collector] Failed to parse article: {e}")
                continue

        return projects

    def _parse_article(self, article, language: str) -> Optional[RawProject]:
        """Parse a single article element into a RawProject."""
        # Repository link: <h2><a href="/owner/repo">...</a></h2>
        h2 = article.find("h2")
        if not h2:
            return None

        link = h2.find("a")
        if not link or not link.get("href"):
            return None

        href = link.get("href", "").strip()
        if not href.startswith("/"):
            return None

        # Extract owner and name from /owner/repo
        parts = href.strip("/").split("/")
        if len(parts) != 2:
            return None

        owner, name = parts[0], parts[1]
        github_url = f"https://github.com{href}"

        # Description: <p class="col-9 color-fg-muted my-1 pr-4">
        description = ""
        desc_elem = article.find("p", class_=re.compile(r"color-fg-muted"))
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Stars: <a class="Link ..." href=".../stargazers"> 12,345 </a>
        stars = None
        star_link = article.find("a", href=re.compile(r"/stargazers$"))
        if star_link:
            stars_text = star_link.get_text(strip=True).replace(",", "")
            if stars_text.endswith("k"):
                # Handle decimal k (e.g., "1.2k" -> 1200, "5.6k" -> 5600)
                try:
                    stars = int(float(stars_text[:-1]) * 1000)
                except ValueError:
                    pass
            else:
                try:
                    stars = int(stars_text)
                except ValueError:
                    pass

        # Language: <span itemprop="programmingLanguage">Python</span>
        # or from the URL language parameter
        lang = language
        lang_elem = article.find("span", attrs={"itemprop": "programmingLanguage"})
        if lang_elem:
            lang = lang_elem.get_text(strip=True)

        return RawProject(
            github_url=github_url,
            name=name,
            owner=owner,
            language=lang,
            stars=stars,
            description=description,
        )

    async def fetch_readme(self, owner: str, name: str) -> Optional[str]:
        """Fetch README content for a repository.

        Uses GitHub's raw content API. Falls back to empty string on error.
        """
        # Try common README filenames
        readme_names = ["README.md", "readme.md", "Readme.md", "README.rst"]
        base_url = f"https://raw.githubusercontent.com/{owner}/{name}/main"

        for readme_name in readme_names:
            url = f"{base_url}/{readme_name}"
            try:
                response = await self.client.get(url)
                if response.status_code == 200:
                    # Truncate to avoid token explosion
                    text = response.text
                    if len(text) > 20000:
                        text = text[:20000] + "\n... [truncated]"
                    return text
            except Exception:
                continue

        # Try master branch if main fails
        base_url = f"https://raw.githubusercontent.com/{owner}/{name}/master"
        for readme_name in readme_names:
            url = f"{base_url}/{readme_name}"
            try:
                response = await self.client.get(url)
                if response.status_code == 200:
                    text = response.text
                    if len(text) > 20000:
                        text = text[:20000] + "\n... [truncated]"
                    return text
            except Exception:
                continue

        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
