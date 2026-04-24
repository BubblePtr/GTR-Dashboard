"""Tests for ProjectProfilerAgent — degradation and context building."""

import pytest

from gtrdashboard.agents.profiler import ProjectProfilerAgent
from gtrdashboard.models import RawProject


@pytest.fixture
def profiler() -> ProjectProfilerAgent:
    return ProjectProfilerAgent()


@pytest.fixture
def sample_project() -> RawProject:
    return RawProject(
        id=1,
        github_url="https://github.com/test/repo",
        name="awesome-repo",
        owner="test",
        language="Python",
        stars=1500,
        description="A very useful tool for local AI",
    )


class TestProfilerDegradation:
    def test_degraded_scores_conservative(self, profiler: ProjectProfilerAgent, sample_project: RawProject) -> None:
        profile = profiler._degraded_profile(sample_project, "LLM timeout")

        assert profile.novelty_score == 5  # stars > 1000
        assert profile.utility_score == 6  # stars > 500
        assert profile.doc_quality_score == 3
        assert profile.local_ai_relevance == 5
        assert profile.analysis_status == "degraded"
        assert "timeout" in profile.analysis_reason

    def test_degraded_low_stars(self, profiler: ProjectProfilerAgent) -> None:
        project = RawProject(
            id=2,
            github_url="https://github.com/test/small",
            name="small-repo",
            owner="test",
            stars=100,
        )
        profile = profiler._degraded_profile(project, "error")

        assert profile.novelty_score == 4
        assert profile.utility_score == 5

    def test_degraded_no_stars(self, profiler: ProjectProfilerAgent) -> None:
        project = RawProject(
            id=3,
            github_url="https://github.com/test/new",
            name="new-repo",
            owner="test",
            stars=None,
        )
        profile = profiler._degraded_profile(project, "error")

        assert profile.novelty_score == 4
        assert profile.utility_score == 5

    def test_degraded_summary_truncation(self, profiler: ProjectProfilerAgent) -> None:
        long_desc = "x" * 300
        project = RawProject(
            id=4,
            github_url="https://github.com/test/long",
            name="long-repo",
            owner="test",
            description=long_desc,
        )
        profile = profiler._degraded_profile(project, "error")
        assert len(profile.summary) <= 200
        assert profile.summary.endswith("...")


class TestProfilerContextBuilding:
    def test_context_with_readme(self, profiler: ProjectProfilerAgent, sample_project: RawProject) -> None:
        readme = "# Awesome Repo\n\nThis is the best repo."
        context = profiler._build_context(sample_project, readme)

        assert "test/awesome-repo" in context
        assert "1500" in context
        assert "Awesome Repo" in context
        assert "README Content:" in context

    def test_context_without_readme(self, profiler: ProjectProfilerAgent, sample_project: RawProject) -> None:
        context = profiler._build_context(sample_project, None)

        assert "README: Not available" in context
        assert "metadata only" in context

    def test_context_readme_truncation(self, profiler: ProjectProfilerAgent, sample_project: RawProject) -> None:
        long_readme = "x" * 6000
        context = profiler._build_context(sample_project, long_readme)

        # README content itself is truncated to 5000 chars in context
        assert "README Content:" in context
        # The full context should not contain all 6000 chars of the README
        assert context.count("x") <= 5005
