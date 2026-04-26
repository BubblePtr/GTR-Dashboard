"""Eval tests — end-to-end pipeline validation with mocked external deps.

Mocks:
    - GitHub Trending HTML (collector.collect)
    - OpenAI LLM calls (profiler.analyze, strategist.generate)

Validates:
    - Data flows correctly through all stages
    - Degradation paths work when LLM fails
    - Report is generated with expected structure
    - Database state is consistent after run
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from gtrdashboard.database import save_raw_projects
from gtrdashboard.models import (
    ProjectProfile,
    RawProject,
    TopicSuggestion,
)
from gtrdashboard.pipeline import PipelineConfig, PipelineOrchestrator


@pytest.fixture
def mock_projects() -> list[RawProject]:
    """Simulate collector output."""
    return [
        RawProject(
            id=1,
            github_url="https://github.com/ai/local-llm",
            name="local-llm",
            owner="ai",
            language="Python",
            stars=5000,
            description="Run LLMs locally",
        ),
        RawProject(
            id=2,
            github_url="https://github.com/dev/toolkit",
            name="toolkit",
            owner="dev",
            language="TypeScript",
            stars=200,
            description="A dev toolkit",
        ),
    ]


@pytest.fixture
def mock_profiles(mock_projects: list[RawProject]) -> list[ProjectProfile]:
    """Simulate profiler output."""
    return [
        ProjectProfile(
            id=1,
            raw_project_id=1,
            novelty_score=9,
            utility_score=8,
            doc_quality_score=7,
            local_ai_relevance=10,
            tags=json.dumps(["llm", "local-ai", "python"]),
            summary="Best local LLM runner",
            analysis_status="complete",
        ),
        ProjectProfile(
            id=2,
            raw_project_id=2,
            novelty_score=5,
            utility_score=6,
            doc_quality_score=5,
            local_ai_relevance=3,
            tags=json.dumps(["dev-tools"]),
            summary="Generic toolkit",
            analysis_status="complete",
        ),
    ]


@pytest.fixture
def mock_topics() -> list[TopicSuggestion]:
    """Simulate strategist output."""
    return [
        TopicSuggestion(
            id=1,
            profile_id=1,
            why_post="Local AI is trending",
            differentiation_angle="The easiest way to run LLMs at home",
            target_audience="AI enthusiasts",
            engagement_estimate="high",
            draft_tweet="Check out this local LLM runner!",
            generation_status="complete",
        ),
        TopicSuggestion(
            id=2,
            profile_id=2,
            why_post="Useful for developers",
            differentiation_angle="A solid dev toolkit",
            target_audience="Developers",
            engagement_estimate="medium",
            draft_tweet="New dev toolkit looks useful",
            generation_status="complete",
        ),
    ]


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        languages=["python"],
        limit=10,
        fetch_readme=False,
        profile_concurrency=2,
        strategist_batch_size=10,
        top_n=10,
    )


class TestPipelineHappyPath:
    async def test_full_pipeline(
        self,
        pipeline_config: PipelineConfig,
        mock_projects: list[RawProject],
        mock_profiles: list[ProjectProfile],
        mock_topics: list[TopicSuggestion],
    ) -> None:
        """End-to-end: all stages succeed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{tmpdir}/test.db"
            reports_dir = Path(tmpdir) / "reports"
            test_engine = create_engine(db_url, echo=False)

            orchestrator = PipelineOrchestrator(pipeline_config)
            orchestrator.primary_collector.collect = AsyncMock(return_value=mock_projects)
            orchestrator.primary_collector.close = AsyncMock()
            orchestrator.profiler.analyze = AsyncMock(side_effect=mock_profiles)
            orchestrator.strategist.generate = AsyncMock(return_value=mock_topics)

            with (
                patch("gtrdashboard.database.engine", test_engine),
                patch("gtrdashboard.pipeline.REPORTS_DIR", reports_dir),
            ):
                report, report_path = await orchestrator.run()

            # Verify report structure
            assert report.total_analyzed == 2
            assert report.total_selected == 2
            assert len(report.topics) == 2

            # Top pick should be local-llm (higher local_ai_relevance)
            assert report.topics[0].topic.profile_id == 1
            assert report.topics[0].rank == 1

            # Report file should exist
            assert report_path.exists()
            content = report_path.read_text(encoding="utf-8")
            assert "GitHub Trending 每日选题报告" in content
            assert "LLMs at home" in content

    async def test_report_formatting(
        self,
        pipeline_config: PipelineConfig,
        mock_projects: list[RawProject],
        mock_profiles: list[ProjectProfile],
        mock_topics: list[TopicSuggestion],
    ) -> None:
        """Verify Markdown report contains all expected sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{tmpdir}/test.db"
            reports_dir = Path(tmpdir) / "reports"
            test_engine = create_engine(db_url, echo=False)

            orchestrator = PipelineOrchestrator(pipeline_config)
            orchestrator.primary_collector.collect = AsyncMock(return_value=mock_projects)
            orchestrator.primary_collector.close = AsyncMock()
            orchestrator.profiler.analyze = AsyncMock(side_effect=mock_profiles)
            orchestrator.strategist.generate = AsyncMock(return_value=mock_topics)

            with (
                patch("gtrdashboard.database.engine", test_engine),
                patch("gtrdashboard.pipeline.REPORTS_DIR", reports_dir),
            ):
                report, report_path = await orchestrator.run()

            content = report_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Should have headers for each topic
            topic_headers = [line for line in lines if line.startswith("## 第")]
            assert len(topic_headers) == 2

            # Should include draft content
            assert "推文草稿" in content
            assert "Check out this local LLM runner!" in content


class TestPipelineDegradation:
    async def test_profiler_degrades_on_failure(
        self,
        pipeline_config: PipelineConfig,
        mock_projects: list[RawProject],
    ) -> None:
        """When profiler fails, pipeline continues with degraded profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{tmpdir}/test.db"
            reports_dir = Path(tmpdir) / "reports"
            test_engine = create_engine(db_url, echo=False)

            orchestrator = PipelineOrchestrator(pipeline_config)
            orchestrator.primary_collector.collect = AsyncMock(return_value=mock_projects)
            orchestrator.primary_collector.close = AsyncMock()

            # First project succeeds, second fails
            success_profile = ProjectProfile(
                id=1,
                raw_project_id=1,
                novelty_score=8,
                utility_score=8,
                doc_quality_score=7,
                local_ai_relevance=9,
                analysis_status="complete",
            )
            orchestrator.profiler.analyze = AsyncMock(
                side_effect=[success_profile, Exception("LLM timeout")]
            )
            orchestrator.strategist.generate = AsyncMock(return_value=[
                TopicSuggestion(
                    profile_id=1,
                    why_post="Good project",
                    engagement_estimate="high",
                    generation_status="complete",
                ),
            ])

            with (
                patch("gtrdashboard.database.engine", test_engine),
                patch("gtrdashboard.pipeline.REPORTS_DIR", reports_dir),
            ):
                report, _ = await orchestrator.run()

            # Only 1 profile succeeded, so 1 topic
            assert report.total_analyzed == 1
            assert report.total_selected == 1

    async def test_strategist_degrades_on_failure(
        self,
        pipeline_config: PipelineConfig,
        mock_projects: list[RawProject],
        mock_profiles: list[ProjectProfile],
    ) -> None:
        """When strategist fails, all topics in batch are degraded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{tmpdir}/test.db"
            reports_dir = Path(tmpdir) / "reports"
            test_engine = create_engine(db_url, echo=False)

            orchestrator = PipelineOrchestrator(pipeline_config)
            orchestrator.primary_collector.collect = AsyncMock(return_value=mock_projects)
            orchestrator.primary_collector.close = AsyncMock()
            orchestrator.profiler.analyze = AsyncMock(side_effect=mock_profiles)
            orchestrator.strategist.generate = AsyncMock(
                side_effect=Exception("Strategist failed")
            )

            with (
                patch("gtrdashboard.database.engine", test_engine),
                patch("gtrdashboard.pipeline.REPORTS_DIR", reports_dir),
            ):
                report, _ = await orchestrator.run()

            # Both topics should be degraded but still present
            assert report.total_analyzed == 2
            assert report.total_selected == 2
            for topic in report.topics:
                assert topic.topic.generation_status == "degraded"


class TestPipelineCaching:
    async def test_cached_profiles_skipped(
        self,
        pipeline_config: PipelineConfig,
        mock_projects: list[RawProject],
    ) -> None:
        """Profiles analyzed today should not be re-analyzed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_url = f"sqlite:///{tmpdir}/test.db"
            reports_dir = Path(tmpdir) / "reports"
            test_engine = create_engine(db_url, echo=False)
            SQLModel.metadata.create_all(test_engine)

            with Session(test_engine, expire_on_commit=False) as session:
                saved_projects = save_raw_projects(session, mock_projects)
                cached_profile = ProjectProfile(
                    raw_project_id=saved_projects[0].id,
                    novelty_score=7,
                    utility_score=7,
                    doc_quality_score=7,
                    local_ai_relevance=7,
                    analysis_status="complete",
                    analyzed_at=datetime.utcnow(),
                )
                session.add(cached_profile)
                session.commit()
                session.refresh(cached_profile)

            orchestrator = PipelineOrchestrator(pipeline_config)
            orchestrator.primary_collector.collect = AsyncMock(return_value=mock_projects)
            orchestrator.primary_collector.close = AsyncMock()

            # Only second project should trigger analysis
            mock_profile = ProjectProfile(
                id=99,
                raw_project_id=2,
                novelty_score=5,
                utility_score=5,
                doc_quality_score=5,
                local_ai_relevance=5,
                analysis_status="complete",
            )
            orchestrator.profiler.analyze = AsyncMock(return_value=mock_profile)
            orchestrator.strategist.generate = AsyncMock(return_value=[])

            with (
                patch("gtrdashboard.database.engine", test_engine),
                patch("gtrdashboard.pipeline.REPORTS_DIR", reports_dir),
            ):
                report, _ = await orchestrator.run()

            # Profiler should only be called once (second project)
            assert orchestrator.profiler.analyze.call_count == 1
