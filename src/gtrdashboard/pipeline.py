"""Pipeline orchestrator — wires all agents into a single execution flow.

Stages:
    1. Collect projects via AI search APIs (Tavily, Exa, or legacy BeautifulSoup)
    2. Profile each repo (with caching and optional README fetch)
    3. Generate content strategy for batches of profiles
    4. Curate and rank topics
    5. Emit Markdown report

Failure handling:
    - Partial collector failure → continue with what we got
    - Profile analysis failure → degrade, don't block pipeline
    - Strategist failure → degrade all topics in batch
    - Any exception → logged, pipeline run marked partial_failure
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from gtrdashboard.agents.collector import CollectorConfig, TrendingCollectorAgent
from gtrdashboard.agents.curator import CuratorAgent, DailyReport
from gtrdashboard.agents.exa_collector import ExaCollectorAgent, ExaCollectorConfig
from gtrdashboard.agents.profiler import ProfilerConfig, ProjectProfilerAgent
from gtrdashboard.agents.search_collector import SearchCollectorAgent, SearchCollectorConfig
from gtrdashboard.agents.strategist import StrategistConfig, ContentStrategistAgent
from gtrdashboard.database import (
    create_pipeline_run,
    create_pipeline_run_stage,
    finish_pipeline_run,
    finish_pipeline_run_stage,
    get_cached_profile,
    get_or_create_preferences,
    get_or_create_weights,
    get_session,
    init_db,
    save_profiles,
    save_raw_projects,
    save_topics,
)
from gtrdashboard.models import (
    PipelineRun,
    PipelineRunStage,
    ProjectProfile,
    RawProject,
    ScoringWeight,
    TopicSuggestion,
    UserPreference,
)

# Report output directory
REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


class PipelineConfig:
    """Configuration for the full pipeline."""

    def __init__(
        self,
        languages: Optional[list[str]] = None,
        limit: int = 50,
        fetch_readme: bool = True,
        profile_concurrency: int = 3,
        strategist_batch_size: int = 10,
        top_n: int = 10,
        positioning: str = "本地AI实战派",
        source: str = "legacy",  # legacy | tavily | exa | both
        exa_query: Optional[str] = None,
        model: str = "qwen3-max",
    ) -> None:
        self.languages = languages if languages is not None else [""]
        self.limit = limit
        self.fetch_readme = fetch_readme
        self.profile_concurrency = profile_concurrency
        self.strategist_batch_size = strategist_batch_size
        self.top_n = top_n
        self.positioning = positioning
        self.source = source
        self.exa_query = exa_query
        self.model = model


class PipelineOrchestrator:
    """Orchestrates the complete curation pipeline."""

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config = config or PipelineConfig()
        self._init_collectors()
        self.profiler = ProjectProfilerAgent(
            ProfilerConfig(
                positioning=self.config.positioning,
                model=self.config.model,
            )
        )
        self.strategist = ContentStrategistAgent(
            StrategistConfig(
                positioning=self.config.positioning,
                model=self.config.model,
                batch_size=self.config.strategist_batch_size,
            )
        )
        self.curator = CuratorAgent(top_n=self.config.top_n)
        self._profile_semaphore = asyncio.Semaphore(self.config.profile_concurrency)

    def _init_collectors(self) -> None:
        """Initialize collector(s) based on source config."""
        source = self.config.source

        if source == "legacy":
            self.primary_collector = TrendingCollectorAgent(
                CollectorConfig(
                    languages=self.config.languages,
                    limit=self.config.limit,
                    fetch_readme=self.config.fetch_readme,
                )
            )
            self.exa_collector: Optional[ExaCollectorAgent] = None

        elif source == "tavily":
            self.primary_collector = SearchCollectorAgent(
                SearchCollectorConfig(
                    languages=self.config.languages,
                    limit=self.config.limit,
                    search_depth="advanced",
                )
            )
            self.exa_collector = None

        elif source == "exa":
            self.primary_collector = ExaCollectorAgent(
                ExaCollectorConfig(
                    limit=self.config.limit,
                    query=self.config.exa_query or self._default_exa_query(),
                )
            )
            self.exa_collector = None

        elif source == "both":
            self.primary_collector = SearchCollectorAgent(
                SearchCollectorConfig(
                    languages=self.config.languages,
                    limit=self.config.limit,
                    search_depth="advanced",
                )
            )
            self.exa_collector = ExaCollectorAgent(
                ExaCollectorConfig(
                    limit=self.config.limit // 2,
                    query=self.config.exa_query or self._default_exa_query(),
                )
            )
        else:
            raise ValueError(f"Unknown source: {source}. Use tavily/exa/both/legacy")

    def _default_exa_query(self) -> str:
        """Build default semantic query from positioning."""
        return (
            "open source project for running large language models locally "
            "on personal computer without internet connection "
            "self-hosted AI tools"
        )

    async def run(
        self,
        existing_run_id: Optional[int] = None,
        triggered_by: str = "manual",
    ) -> tuple[DailyReport, Path]:
        """Execute the full pipeline and return the curated report.

        Args:
            existing_run_id: If provided, reuse this run record instead of creating new.
            triggered_by: Who triggered this run — manual | scheduled | api.

        Returns:
            (DailyReport, report_file_path)
        """
        # Initialize database
        init_db()

        session = get_session()
        preferences = get_or_create_preferences(session)

        # Start pipeline tracking
        if existing_run_id:
            run = session.get(PipelineRun, existing_run_id)
            if run is None:
                raise ValueError(f"PipelineRun {existing_run_id} not found")
            run.triggered_by = triggered_by
            session.add(run)
            session.commit()
        else:
            run = create_pipeline_run(session)
            run.triggered_by = triggered_by
            session.add(run)
            session.commit()
            session.refresh(run)
        print(f"[Pipeline] Started run #{run.id} at {run.started_at}")

        errors: list[str] = []

        # Helper to wrap each stage with progress tracking
        async def _tracked_stage(
            name: str,
            fn,
            *args,
            **kwargs,
        ):
            stage = create_pipeline_run_stage(session, run.id, name, "running")
            try:
                result = await fn(*args, **kwargs)
                finish_pipeline_run_stage(session, stage.id, "complete", 100)
                return result
            except Exception as e:
                finish_pipeline_run_stage(
                    session, stage.id, "failed", 0, message=str(e)
                )
                errors.append(f"{name}: {e}")
                raise

        try:
            # Stage 1: Collect
            projects = await _tracked_stage("collect", self._stage_collect, session)

            # Stage 2: Profile
            profiles = await _tracked_stage(
                "profile", self._stage_profile, session, projects
            )

            # Stage 3: Strategize
            topics = await _tracked_stage("strategize", self._stage_strategize, profiles)
            topics = save_topics(session, topics)

            # Stage 4: Curate
            report = self._stage_curate(topics, profiles, preferences, projects)
            stage_curate = create_pipeline_run_stage(session, run.id, "curate", "running")

            # Write final_score back to each topic
            topic_score_map = {c.topic.id: c.final_score for c in report.topics if c.topic.id}
            for topic in topics:
                if topic.id in topic_score_map:
                    topic.final_score = topic_score_map[topic.id]
            session.add_all(topics)
            session.commit()

            finish_pipeline_run_stage(session, stage_curate.id, "complete", 100)

            # Stage 5: Generate report
            stage_report = create_pipeline_run_stage(session, run.id, "report", "running")
            report_path = self._write_report(report)
            finish_pipeline_run_stage(session, stage_report.id, "complete", 100)

            # Update tracking
            status = "partial_failure" if errors else "success"
            finish_pipeline_run(
                session,
                run_id=run.id,
                status=status,
                projects_collected=len(projects),
                projects_analyzed=len(profiles),
                topics_generated=len(topics),
                error_log="\n".join(errors) if errors else None,
            )
            print(f"[Pipeline] Finished run #{run.id} — status: {status}")
            print(f"[Pipeline] Report saved to: {report_path}")

            return report, report_path

        except Exception as e:
            finish_pipeline_run(
                session,
                run_id=run.id,
                status="failed",
                error_log=str(e),
            )
            raise
        finally:
            await self.primary_collector.close()
            if self.exa_collector:
                await self.exa_collector.close()
            session.close()

    async def _stage_collect(self, session: Session) -> list[RawProject]:
        """Collect projects from configured sources."""
        all_projects: list[RawProject] = []
        seen_urls: set[str] = set()

        # Primary source
        print(f"[Pipeline] Collecting from primary source: {self.config.source}")
        try:
            primary_projects = await self.primary_collector.collect()
            for p in primary_projects:
                if p.github_url not in seen_urls:
                    seen_urls.add(p.github_url)
                    all_projects.append(p)
            print(f"[Pipeline] Primary source returned {len(primary_projects)} projects")
        except Exception as e:
            print(f"[Pipeline] Primary collector failed: {e}")

        # Exa supplement (when source=both)
        if self.exa_collector:
            print("[Pipeline] Collecting from Exa semantic search")
            try:
                exa_projects = await self.exa_collector.collect()
                for p in exa_projects:
                    if p.github_url not in seen_urls:
                        seen_urls.add(p.github_url)
                        all_projects.append(p)
                print(f"[Pipeline] Exa returned {len(exa_projects)} projects")
            except Exception as e:
                print(f"[Pipeline] Exa collector failed: {e}")

        projects = save_raw_projects(session, all_projects)
        print(f"[Pipeline] Collected {len(projects)} unique projects total")
        return projects

    async def _stage_profile(
        self, session: Session, projects: list[RawProject]
    ) -> list[ProjectProfile]:
        """Profile each project, using cache when available."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        profiles: list[ProjectProfile] = []
        tasks: list[asyncio.Task[ProjectProfile]] = []

        for project in projects:
            cached = get_cached_profile(session, project.github_url, today)
            if cached:
                print(f"[Pipeline] Cache hit: {project.owner}/{project.name}")
                profiles.append(cached)
                continue

            # Queue for analysis
            task = asyncio.create_task(self._analyze_one(project))
            tasks.append(task)

        if tasks:
            print(f"[Pipeline] Analyzing {len(tasks)} projects (cached: {len(profiles)})")
            analyzed = await asyncio.gather(*tasks, return_exceptions=True)
            for result in analyzed:
                if isinstance(result, Exception):
                    print(f"[Pipeline] Analysis error: {result}")
                else:
                    profiles.append(result)

            # Save newly analyzed profiles
            new_profiles = [p for p in analyzed if not isinstance(p, Exception)]
            if new_profiles:
                save_profiles(session, new_profiles)

        print(f"[Pipeline] Total profiles: {len(profiles)}")
        return profiles

    async def _analyze_one(self, project: RawProject) -> ProjectProfile:
        """Analyze a single project with concurrency control."""
        async with self._profile_semaphore:
            readme_text: Optional[str] = None
            if self.config.fetch_readme:
                try:
                    # Use Tavily Extract for README when available
                    readme_text = await self.primary_collector.fetch_readme(
                        project.owner, project.name
                    )
                except Exception as e:
                    print(f"[Pipeline] README fetch failed for {project.name}: {e}")

            profile = await self.profiler.analyze(project, readme_text)
            profile.raw_project_id = project.id
            return profile

    async def _stage_strategize(
        self, profiles: list[ProjectProfile]
    ) -> list[TopicSuggestion]:
        """Generate topic suggestions in batches."""
        if not profiles:
            return []

        batch_size = self.config.strategist_batch_size
        all_topics: list[TopicSuggestion] = []

        for i in range(0, len(profiles), batch_size):
            batch = profiles[i : i + batch_size]
            print(f"[Pipeline] Strategizing batch {i // batch_size + 1} ({len(batch)} projects)")
            try:
                batch_topics = await self.strategist.generate(batch)
                all_topics.extend(batch_topics)
            except Exception as e:
                print(f"[Pipeline] Strategist batch failed: {e}")
                # Degrade all in batch
                for profile in batch:
                    all_topics.append(self._degraded_topic(profile))

        print(f"[Pipeline] Generated {len(all_topics)} topics")
        return all_topics

    def _stage_curate(
        self,
        topics: list[TopicSuggestion],
        profiles: list[ProjectProfile],
        preferences: UserPreference,
        projects: list[RawProject],
    ) -> DailyReport:
        """Curate topics using weighted scoring."""
        # Build lookups
        profile_map = {p.id: p for p in profiles}
        project_map = {p.id: p for p in projects}

        # Pair topics with their profile scores, names, and URLs
        topics_with_scores: list[tuple[TopicSuggestion, dict[str, int]]] = []
        profile_project_names: dict[int, str] = {}
        profile_project_urls: dict[int, str] = {}
        for topic in topics:
            profile = profile_map.get(topic.profile_id)
            if profile:
                scores = {
                    "novelty": profile.novelty_score,
                    "utility": profile.utility_score,
                    "local_ai": profile.local_ai_relevance,
                    "doc_quality": profile.doc_quality_score,
                }
                topics_with_scores.append((topic, scores))
                # Attach project name and URL for display
                project = project_map.get(profile.raw_project_id)
                if project:
                    profile_project_names[profile.id] = f"{project.owner}/{project.name}"
                    profile_project_urls[profile.id] = project.github_url

        report = self.curator.rank_with_scores(
            topics_with_scores, preferences, profile_project_names, profile_project_urls
        )
        print(f"[Pipeline] Curated {report.total_selected} topics")
        return report

    def _write_report(self, report: DailyReport) -> Path:
        """Write the daily report as Markdown."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        report_path = REPORTS_DIR / f"daily_report_{date_str}.md"

        lines: list[str] = [
            f"# GitHub Trending 每日选题报告 — {date_str}",
            "",
            f"> {report.report_summary}",
            "",
            f"- **分析项目总数：** {report.total_analyzed}",
            f"- **入选选题：** {report.total_selected}",
            "",
            "---",
            "",
        ]

        for curated in report.topics:
            topic = curated.topic
            project_label = curated.project_name or "未知项目"
            project_url = curated.github_url or ""
            lines.extend([
                f"## 第{curated.rank}名 评分：{curated.final_score} — {project_label}",
                "",
                f"**仓库地址：** {project_url}" if project_url else "",
                "" if project_url else "",
                f"**选题理由：** {topic.why_post or '暂无'}",
                "",
                f"**差异化角度：** {topic.differentiation_angle or '暂无'}",
                "",
                f"**目标受众：** {topic.target_audience or '暂无'}",
                "",
                f"**互动预估：** {topic.engagement_estimate}",
                "",
                f"**入选原因：** {curated.selection_reason}",
                "",
            ])

            if topic.draft_tweet:
                lines.extend([
                    "### 推文草稿",
                    "",
                    f"{topic.draft_tweet}",
                    "",
                ])
            if topic.draft_script:
                lines.extend([
                    "### 视频脚本草稿",
                    "",
                    f"{topic.draft_script}",
                    "",
                ])
            if topic.draft_outline:
                lines.extend([
                    "### 文章大纲",
                    "",
                    f"{topic.draft_outline}",
                    "",
                ])

            lines.append("---")
            lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    def _degraded_topic(self, profile: ProjectProfile) -> TopicSuggestion:
        """Create a degraded topic when strategist fails."""
        summary = profile.summary or "一个有趣的项目"
        return TopicSuggestion(
            profile_id=profile.id,
            why_post="",
            differentiation_angle="",
            target_audience="",
            engagement_estimate="low",
            draft_tweet=f"值得关注：{summary[:200]}",
            draft_script="",
            draft_outline="",
            generation_status="degraded",
            generation_reason="批量生成失败",
        )
