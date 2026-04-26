"""Tests for ContentStrategistAgent — batch context and degradation."""

import json

import pytest

from gtrdashboard.agents.strategist import ContentStrategistAgent
from gtrdashboard.models import ProjectProfile


@pytest.fixture
def strategist() -> ContentStrategistAgent:
    return ContentStrategistAgent()


@pytest.fixture
def sample_profiles() -> list[ProjectProfile]:
    return [
        ProjectProfile(
            id=1,
            raw_project_id=1,
            novelty_score=8,
            utility_score=7,
            doc_quality_score=6,
            local_ai_relevance=9,
            tags=json.dumps(["llm", "local"]),
            summary="A local LLM runner",
        ),
        ProjectProfile(
            id=2,
            raw_project_id=2,
            novelty_score=5,
            utility_score=5,
            doc_quality_score=5,
            local_ai_relevance=5,
            tags=json.dumps(["tool"]),
            summary="A generic tool",
        ),
    ]


class TestStrategistDegradation:
    def test_degraded_topic(self, strategist: ContentStrategistAgent, sample_profiles: list[ProjectProfile]) -> None:
        profile = sample_profiles[0]
        topic = strategist._degraded_topic(profile)

        assert topic.profile_id == profile.id
        assert topic.generation_status == "degraded"
        assert "failed" in topic.generation_reason.lower()
        assert topic.engagement_estimate == "low"
        assert "local LLM runner" in topic.draft_tweet

    def test_degraded_no_summary(self, strategist: ContentStrategistAgent) -> None:
        profile = ProjectProfile(
            id=3,
            raw_project_id=3,
            novelty_score=5,
            utility_score=5,
            doc_quality_score=5,
            local_ai_relevance=5,
        )
        topic = strategist._degraded_topic(profile)
        assert "一个有趣的项目" in topic.draft_tweet


class TestStrategistContextBuilding:
    def test_batch_context_format(self, strategist: ContentStrategistAgent, sample_profiles: list[ProjectProfile]) -> None:
        context = strategist._build_batch_context(sample_profiles)

        assert "Generate content strategy for 2 projects" in context
        assert "--- Project 1 ---" in context
        assert "--- Project 2 ---" in context
        assert "Novelty: 8/10" in context
        assert "Local AI Relevance: 9/10" in context
        assert "llm, local" in context

    def test_batch_context_empty_tags(self, strategist: ContentStrategistAgent) -> None:
        profile = ProjectProfile(
            id=4,
            raw_project_id=4,
            novelty_score=5,
            utility_score=5,
            doc_quality_score=5,
            local_ai_relevance=5,
            tags="[]",
            summary="Test",
        )
        context = strategist._build_batch_context([profile])
        assert "Tags: N/A" in context

    def test_batch_context_invalid_tags_json(self, strategist: ContentStrategistAgent) -> None:
        profile = ProjectProfile(
            id=5,
            raw_project_id=5,
            novelty_score=5,
            utility_score=5,
            doc_quality_score=5,
            local_ai_relevance=5,
            tags="not valid json",
            summary="Test",
        )
        context = strategist._build_batch_context([profile])
        assert "Tags: N/A" in context
