"""Tests for SearchCollectorAgent (Tavily) — parsing logic, no live API calls."""

import pytest

from gtrdashboard.agents.search_collector import SearchCollectorAgent, SearchCollectorConfig
from gtrdashboard.models import RawProject


class TestSearchCollectorParseResult:
    def test_parse_valid_github_url(self) -> None:
        agent = SearchCollectorAgent()
        item = {
            "url": "https://github.com/owner/repo",
            "title": "repo - a cool project",
            "content": "This is the description of the project.",
        }
        project = agent._parse_result(item)

        assert project is not None
        assert project.owner == "owner"
        assert project.name == "repo"
        assert project.github_url == "https://github.com/owner/repo"
        assert "description of the project" in project.description

    def test_parse_non_github_url(self) -> None:
        agent = SearchCollectorAgent()
        item = {"url": "https://example.com/something"}
        assert agent._parse_result(item) is None

    def test_parse_github_org_only(self) -> None:
        agent = SearchCollectorAgent()
        item = {"url": "https://github.com/owner"}
        assert agent._parse_result(item) is None

    def test_parse_long_description_truncated(self) -> None:
        agent = SearchCollectorAgent()
        item = {
            "url": "https://github.com/o/r",
            "content": "x" * 600,
        }
        project = agent._parse_result(item)
        assert project is not None
        assert len(project.description) <= 500
        assert project.description.endswith("...")

    def test_parse_empty_content_uses_title(self) -> None:
        agent = SearchCollectorAgent()
        item = {
            "url": "https://github.com/o/r",
            "title": "Fallback title",
            "content": "",
        }
        project = agent._parse_result(item)
        assert project.description == "Fallback title"

    def test_parse_no_stars_no_language(self) -> None:
        agent = SearchCollectorAgent()
        item = {"url": "https://github.com/o/r", "content": "desc"}
        project = agent._parse_result(item)
        assert project.stars is None
        assert project.language is None


class TestSearchCollectorConfig:
    def test_default_domains(self) -> None:
        config = SearchCollectorConfig(languages=["python"])
        assert config.include_domains == ["github.com"]

    def test_custom_domains(self) -> None:
        config = SearchCollectorConfig(
            languages=["python"],
            include_domains=["github.com", "gitlab.com"],
        )
        assert config.include_domains == ["github.com", "gitlab.com"]
