"""Database operations for GTR Dashboard.

All writes are batched through the orchestrator to avoid SQLite concurrency issues.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from gtrdashboard.models import (
    PipelineRun,
    PipelineRunStage,
    ProjectProfile,
    RawProject,
    ScoringWeight,
    TopicSuggestion,
    UserAction,
    UserPreference,
)

# Single database path — use project root adjacent to avoid path issues
DB_PATH = Path(__file__).parent.parent.parent / "gtrdashboard.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    """Create all tables if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Yield a database session."""
    return Session(engine, expire_on_commit=False)


def get_or_create_preferences(session: Session) -> UserPreference:
    """Get user preferences, creating defaults if none exist."""
    result = session.exec(select(UserPreference)).first()
    if result is None:
        result = UserPreference()
        session.add(result)
        session.commit()
        session.refresh(result)
    return result


def save_raw_projects(session: Session, projects: list[RawProject]) -> list[RawProject]:
    """Upsert raw projects. Returns saved projects with IDs."""
    saved = []
    for project in projects:
        existing = session.exec(
            select(RawProject).where(RawProject.github_url == project.github_url)
        ).first()
        if existing:
            # Update fields that may have changed
            existing.stars = project.stars
            existing.description = project.description
            existing.readme_text = project.readme_text or existing.readme_text
            existing.collected_at = datetime.utcnow()
            session.add(existing)
            saved.append(existing)
        else:
            session.add(project)
            saved.append(project)
    session.commit()
    for p in saved:
        session.refresh(p)
    return saved


def save_profiles(session: Session, profiles: list[ProjectProfile]) -> list[ProjectProfile]:
    """Save project profiles. Returns saved profiles with IDs."""
    for profile in profiles:
        session.add(profile)
    session.commit()
    for profile in profiles:
        session.refresh(profile)
    return profiles


def save_topics(session: Session, topics: list[TopicSuggestion]) -> list[TopicSuggestion]:
    """Save topic suggestions. Returns saved topics with IDs."""
    for topic in topics:
        session.add(topic)
    session.commit()
    for topic in topics:
        session.refresh(topic)
    return topics


def get_cached_profile(
    session: Session, github_url: str, date_str: str
) -> Optional[ProjectProfile]:
    """Check if a project was already analyzed today.

    Args:
        session: Database session
        github_url: Project GitHub URL
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Cached profile if found for today, None otherwise
    """
    from sqlalchemy import func

    # Find raw_project by URL
    raw = session.exec(select(RawProject).where(RawProject.github_url == github_url)).first()
    if not raw:
        return None

    # Check if profile exists and was analyzed today
    profile = session.exec(
        select(ProjectProfile).where(
            (ProjectProfile.raw_project_id == raw.id)
            & (func.date(ProjectProfile.analyzed_at) == date_str)
        )
    ).first()
    return profile


def create_pipeline_run(session: Session) -> PipelineRun:
    """Create a new pipeline run record."""
    run = PipelineRun(status="running")
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def finish_pipeline_run(
    session: Session,
    run_id: int,
    status: str,
    projects_collected: int = 0,
    projects_analyzed: int = 0,
    topics_generated: int = 0,
    error_log: Optional[str] = None,
) -> None:
    """Mark a pipeline run as finished."""
    run = session.get(PipelineRun, run_id)
    if run:
        run.status = status
        run.projects_collected = projects_collected
        run.projects_analyzed = projects_analyzed
        run.topics_generated = topics_generated
        run.error_log = error_log
        run.finished_at = datetime.utcnow()
        session.add(run)
        session.commit()


def get_topics_with_status(
    session: Session,
    date_str: Optional[str] = None,
    status: Optional[str] = None,
) -> list[tuple[TopicSuggestion, UserAction]]:
    """Get topics with their user action status, optionally filtered by date and status.

    Returns list of (TopicSuggestion, UserAction) tuples.
    """
    from sqlalchemy import func

    query = select(TopicSuggestion, UserAction).outerjoin(
        UserAction, TopicSuggestion.id == UserAction.topic_id
    )
    if date_str:
        query = query.where(func.date(TopicSuggestion.created_at) == date_str)
    if status:
        # Filter by action status; topics without actions default to pending
        query = query.where(
            (UserAction.action == status) | (UserAction.id == None) if status == "pending" else UserAction.action == status
        )
    results = session.exec(query.order_by(TopicSuggestion.priority_score.desc())).all()
    return list(results)


def get_pipeline_stages(session: Session, run_id: int) -> list[PipelineRunStage]:
    """Get all stage records for a pipeline run, ordered by start time."""
    stages = session.exec(
        select(PipelineRunStage)
        .where(PipelineRunStage.run_id == run_id)
        .order_by(PipelineRunStage.started_at)
    ).all()
    return list(stages)


def get_or_create_weights(session: Session) -> ScoringWeight:
    """Get scoring weights, creating defaults if none exist."""
    result = session.exec(select(ScoringWeight)).first()
    if result is None:
        result = ScoringWeight()
        session.add(result)
        session.commit()
        session.refresh(result)
    return result


def create_pipeline_run_stage(
    session: Session,
    run_id: int,
    stage_name: str,
    status: str = "running",
    message: Optional[str] = None,
) -> PipelineRunStage:
    """Create a new pipeline run stage record."""
    stage = PipelineRunStage(
        run_id=run_id,
        stage_name=stage_name,
        status=status,
        message=message,
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    return stage


def finish_pipeline_run_stage(
    session: Session,
    stage_id: int,
    status: str = "complete",
    progress: int = 100,
    message: Optional[str] = None,
) -> None:
    """Mark a pipeline run stage as finished."""
    stage = session.get(PipelineRunStage, stage_id)
    if stage:
        stage.status = status
        stage.progress = progress
        if message:
            stage.message = message
        stage.finished_at = datetime.utcnow()
        session.add(stage)
        session.commit()
