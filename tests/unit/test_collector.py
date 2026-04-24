"""Tests for TrendingCollectorAgent — HTML parsing, no live HTTP."""

import pytest
from bs4 import BeautifulSoup

from gtrdashboard.agents.collector import TrendingCollectorAgent
from gtrdashboard.models import RawProject


SAMPLE_HTML = """
<article class="Box-row">
    <h2><a href="/owner1/repo1">owner1 / repo1</a></h2>
    <p class="col-9 color-fg-muted my-1 pr-4">A cool project</p>
    <a class="Link" href="/owner1/repo1/stargazers">1,234</a>
    <span itemprop="programmingLanguage">Python</span>
</article>
<article class="Box-row">
    <h2><a href="/owner2/repo2">owner2 / repo2</a></h2>
    <p class="col-9 color-fg-muted my-1 pr-4">Another project</p>
    <a class="Link" href="/owner2/repo2/stargazers">5.6k</a>
    <span itemprop="programmingLanguage">TypeScript</span>
</article>
<article class="Box-row">
    <h2><a href="/owner3/repo3">owner3 / repo3</a></h2>
</article>
"""


@pytest.fixture
def collector() -> TrendingCollectorAgent:
    return TrendingCollectorAgent()


class TestCollectorParseHTML:
    def test_parse_sample(self, collector: TrendingCollectorAgent) -> None:
        projects = collector._parse_html(SAMPLE_HTML, "python")

        assert len(projects) == 3

        p0 = projects[0]
        assert p0.owner == "owner1"
        assert p0.name == "repo1"
        assert p0.github_url == "https://github.com/owner1/repo1"
        assert p0.description == "A cool project"
        assert p0.stars == 1234
        assert p0.language == "Python"

        p1 = projects[1]
        assert p1.stars == 5600  # "5.6k" -> 5600
        assert p1.language == "TypeScript"

    def test_parse_empty(self, collector: TrendingCollectorAgent) -> None:
        projects = collector._parse_html("<html></html>", "go")
        assert projects == []

    def test_parse_malformed_article(self, collector: TrendingCollectorAgent) -> None:
        html = """
        <article class="Box-row">
            <p>Missing h2 and link</p>
        </article>
        """
        projects = collector._parse_html(html, "rust")
        assert projects == []

    def test_star_parsing_decimal_k(self, collector: TrendingCollectorAgent) -> None:
        html = """
        <article class="Box-row">
            <h2><a href="/o/r">o / r</a></h2>
            <a class="Link" href="/o/r/stargazers">2.5k</a>
        </article>
        """
        projects = collector._parse_html(html, "python")
        assert projects[0].stars == 2500


class TestCollectorParseArticle:
    def test_valid_article(self, collector: TrendingCollectorAgent) -> None:
        html = """
        <article class="Box-row">
            <h2><a href="/test/repo">test / repo</a></h2>
            <p class="col-9 color-fg-muted my-1 pr-4">Description here</p>
            <a class="Link" href="/test/repo/stargazers">999</a>
            <span itemprop="programmingLanguage">Go</span>
        </article>
        """
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article")
        result = collector._parse_article(article, "go")

        assert result is not None
        assert result.owner == "test"
        assert result.name == "repo"
        assert result.stars == 999
        assert result.language == "Go"

    def test_missing_h2(self, collector: TrendingCollectorAgent) -> None:
        html = '<article class="Box-row"><p>no h2</p></article>'
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article")
        assert collector._parse_article(article, "python") is None

    def test_invalid_href(self, collector: TrendingCollectorAgent) -> None:
        html = '<article class="Box-row"><h2><a href="not-starting-with-slash">x</a></h2></article>'
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article")
        assert collector._parse_article(article, "python") is None


class TestCollectorDeduplication:
    def test_dedup_across_languages(self) -> None:
        """Same repo appearing in multiple language trending pages."""
        html = """
        <article class="Box-row">
            <h2><a href="/dup/repo">dup / repo</a></h2>
            <a class="Link" href="/dup/repo/stargazers">100</a>
        </article>
        """
        collector = TrendingCollectorAgent()
        # Simulate two languages returning the same repo
        p1 = collector._parse_html(html, "python")
        p2 = collector._parse_html(html, "javascript")

        combined = p1 + p2
        seen = set()
        deduped = []
        for p in combined:
            if p.github_url not in seen:
                seen.add(p.github_url)
                deduped.append(p)

        assert len(deduped) == 1
