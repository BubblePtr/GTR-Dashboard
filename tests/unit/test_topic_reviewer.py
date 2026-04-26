"""Tests for TopicReviewerAgent fallback behavior."""

from __future__ import annotations

import pytest

from gtrdashboard.agents.topic_reviewer import TopicReviewerAgent
from gtrdashboard.models import ProjectProfile, RawProject, TopicSuggestion, UserPreference


@pytest.mark.asyncio
async def test_topic_reviewer_returns_contextual_fallback_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    agent = TopicReviewerAgent()

    result = await agent.chat(
        topic=TopicSuggestion(
            why_post="适合做成本地 AI 实战演示。",
            differentiation_angle="用 60 秒演示部署路径。",
            target_audience="独立开发者",
            engagement_estimate="high",
            final_score=8.5,
        ),
        profile=ProjectProfile(
            novelty_score=8,
            utility_score=9,
            local_ai_relevance=9,
            doc_quality_score=7,
        ),
        project=RawProject(
            github_url="https://github.com/acme/demo",
            owner="acme",
            name="demo",
            description="Local AI workflow demo",
        ),
        preferences=UserPreference(positioning="本地AI实战派"),
        user_message="这个选题为什么适合我的账号？",
        history=[],
    )

    assert result.action == "general"
    assert "acme/demo" in result.response
    assert "适合" in result.response
