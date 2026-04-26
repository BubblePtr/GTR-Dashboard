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
    ReviewSignalInput,
    TopicCandidate,
    TopicReviewMessage,
    TopicReviewSignal,
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
    _ensure_additive_schema()


def _ensure_additive_schema() -> None:
    """Apply small additive schema fixes for local SQLite databases."""
    required_columns = {
        "topic_suggestions": {
            "candidate_id": "INTEGER",
            "user_edited_draft_tweet": "VARCHAR",
            "user_edited_draft_script": "VARCHAR",
            "user_edited_draft_outline": "VARCHAR",
            "review_notes": "VARCHAR",
        },
        "user_actions": {
            "candidate_id": "INTEGER",
        },
        "topic_review_messages": {
            "candidate_id": "INTEGER",
        },
        "topic_review_signals": {
            "candidate_id": "INTEGER",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in required_columns.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
            }
            if not existing:
                continue
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )


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


def save_review_message(session: Session, message: TopicReviewMessage) -> TopicReviewMessage:
    """Save one topic review chat message."""
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


def save_review_signals(
    session: Session,
    topic_id: int,
    message_id: Optional[int],
    signals: list[ReviewSignalInput],
    candidate_id: Optional[int] = None,
) -> list[TopicReviewSignal]:
    """Save structured signals extracted from a review conversation."""
    saved: list[TopicReviewSignal] = []
    for signal in signals:
        row = TopicReviewSignal(
            topic_id=topic_id,
            candidate_id=candidate_id,
            message_id=message_id,
            signal_type=signal.signal_type,
            label=signal.label,
            polarity=signal.polarity,
            strength=signal.strength,
        )
        session.add(row)
        saved.append(row)
    session.commit()
    for row in saved:
        session.refresh(row)
    return saved


def get_review_messages(session: Session, topic_id: int) -> list[TopicReviewMessage]:
    """Return persisted review messages for a topic in chronological order."""
    messages = session.exec(
        select(TopicReviewMessage)
        .where(TopicReviewMessage.topic_id == topic_id)
        .order_by(TopicReviewMessage.created_at)
    ).all()
    return list(messages)


def get_review_signals(session: Session, topic_id: int) -> list[TopicReviewSignal]:
    """Return structured learning signals for a topic."""
    signals = session.exec(
        select(TopicReviewSignal)
        .where(TopicReviewSignal.topic_id == topic_id)
        .order_by(TopicReviewSignal.created_at)
    ).all()
    return list(signals)


def get_review_messages_for_topic(
    session: Session, topic: TopicSuggestion
) -> list[TopicReviewMessage]:
    """Return messages for a topic, including stable candidate messages when available."""
    candidate = _candidate_for_topic(session, topic)
    return _messages_for_topic_or_candidate(session, topic.id, candidate.id if candidate else None)


def get_review_signals_for_topic(
    session: Session, topic: TopicSuggestion
) -> list[TopicReviewSignal]:
    """Return signals for a topic, including stable candidate signals when available."""
    candidate = _candidate_for_topic(session, topic)
    return _signals_for_topic_or_candidate(session, topic.id, candidate.id if candidate else None)


def _project_for_topic(
    session: Session, topic: TopicSuggestion
) -> tuple[Optional[ProjectProfile], Optional[RawProject]]:
    profile = session.get(ProjectProfile, topic.profile_id) if topic.profile_id else None
    project = session.get(RawProject, profile.raw_project_id) if profile and profile.raw_project_id else None
    return profile, project


def _candidate_for_topic(
    session: Session, topic: TopicSuggestion
) -> Optional[TopicCandidate]:
    if topic.candidate_id:
        candidate = session.get(TopicCandidate, topic.candidate_id)
        if candidate:
            return candidate

    _, project = _project_for_topic(session, topic)
    if not project:
        return None

    candidate = session.exec(
        select(TopicCandidate).where(TopicCandidate.github_url == project.github_url)
    ).first()
    if candidate and topic.candidate_id != candidate.id:
        topic.candidate_id = candidate.id
        session.add(topic)
        session.commit()
    return candidate


def _messages_for_topic_or_candidate(
    session: Session, topic_id: int, candidate_id: Optional[int]
) -> list[TopicReviewMessage]:
    if candidate_id:
        messages = session.exec(
            select(TopicReviewMessage)
            .where(
                (TopicReviewMessage.candidate_id == candidate_id)
                | (TopicReviewMessage.topic_id == topic_id)
            )
            .order_by(TopicReviewMessage.created_at)
        ).all()
        return list(messages)
    return get_review_messages(session, topic_id)


def _signals_for_topic_or_candidate(
    session: Session, topic_id: int, candidate_id: Optional[int]
) -> list[TopicReviewSignal]:
    if candidate_id:
        signals = session.exec(
            select(TopicReviewSignal)
            .where(
                (TopicReviewSignal.candidate_id == candidate_id)
                | (TopicReviewSignal.topic_id == topic_id)
            )
            .order_by(TopicReviewSignal.created_at)
        ).all()
        return list(signals)
    return get_review_signals(session, topic_id)


def _latest_action_for_topic_or_candidate(
    session: Session, topic_id: int, candidate_id: Optional[int]
) -> Optional[UserAction]:
    stmt = select(UserAction).where(UserAction.topic_id == topic_id)
    if candidate_id:
        stmt = select(UserAction).where(
            (UserAction.candidate_id == candidate_id) | (UserAction.topic_id == topic_id)
        )
    return session.exec(stmt.order_by(UserAction.acted_at.desc())).first()


def _review_state(action_value: str, message_count: int) -> str:
    if action_value == "approved":
        return "已采纳"
    if action_value == "skipped":
        return "已跳过"
    if message_count > 0:
        return "对话中"
    return "未聊"


def _matches_topic_status(topic: dict, status: Optional[str]) -> bool:
    if not status:
        return True
    if status == "chatting":
        return topic["review_state"] == "对话中"
    if status == "pending":
        return topic["action"] == "pending" and topic["review_state"] == "未聊"
    return topic["action"] == status


def _topic_output(
    session: Session,
    topic: TopicSuggestion,
    candidate: Optional[TopicCandidate] = None,
) -> dict:
    candidate = candidate or _candidate_for_topic(session, topic)
    _, project = _project_for_topic(session, topic)

    project_name = candidate.project_name if candidate else None
    github_url = candidate.github_url if candidate else None
    if project:
        project_name = project_name or f"{project.owner}/{project.name}"
        github_url = github_url or project.github_url

    candidate_id = candidate.id if candidate else None
    action = _latest_action_for_topic_or_candidate(session, topic.id, candidate_id)
    messages = _messages_for_topic_or_candidate(session, topic.id, candidate_id)
    action_value = (
        candidate.status if candidate and candidate.status != "pending"
        else action.action if action
        else "pending"
    )

    return {
        "id": topic.id,
        "candidate_id": candidate_id,
        "profile_id": topic.profile_id,
        "project_name": project_name,
        "github_url": github_url,
        "why_post": topic.why_post,
        "differentiation_angle": topic.differentiation_angle,
        "target_audience": topic.target_audience,
        "engagement_estimate": topic.engagement_estimate,
        "draft_tweet": topic.draft_tweet,
        "draft_script": topic.draft_script,
        "draft_outline": topic.draft_outline,
        "user_edited_draft_tweet": topic.user_edited_draft_tweet,
        "user_edited_draft_script": topic.user_edited_draft_script,
        "user_edited_draft_outline": topic.user_edited_draft_outline,
        "review_notes": topic.review_notes,
        "priority_score": topic.priority_score,
        "final_score": candidate.final_score if candidate and candidate.final_score is not None else topic.final_score,
        "generation_status": topic.generation_status,
        "created_at": topic.created_at,
        "action": action_value,
        "review_state": _review_state(action_value, len(messages)),
        "message_count": len(messages),
        "first_seen_at": candidate.first_seen_at if candidate else topic.created_at,
        "last_seen_at": candidate.last_seen_at if candidate else topic.created_at,
        "seen_count": candidate.seen_count if candidate else 1,
        "latest_topic_id": candidate.latest_topic_id if candidate else topic.id,
    }


def upsert_topic_candidates(
    session: Session, topics: list[TopicSuggestion]
) -> list[TopicCandidate]:
    """Upsert stable candidate pool rows for topic suggestions."""
    saved: list[TopicCandidate] = []
    for topic in topics:
        _, project = _project_for_topic(session, topic)
        if not project:
            continue

        project_name = f"{project.owner}/{project.name}"
        candidate = session.exec(
            select(TopicCandidate).where(TopicCandidate.github_url == project.github_url)
        ).first()
        if candidate:
            candidate.project_name = project_name
            candidate.last_seen_at = topic.created_at or datetime.utcnow()
            candidate.seen_count += 1
            candidate.latest_topic_id = topic.id
            candidate.final_score = topic.final_score
        else:
            candidate = TopicCandidate(
                github_url=project.github_url,
                project_name=project_name,
                first_seen_at=topic.created_at or datetime.utcnow(),
                last_seen_at=topic.created_at or datetime.utcnow(),
                seen_count=1,
                latest_topic_id=topic.id,
                final_score=topic.final_score,
            )
            session.add(candidate)
            session.flush()

        topic.candidate_id = candidate.id
        session.add(candidate)
        session.add(topic)
        saved.append(candidate)

    session.commit()
    for candidate in saved:
        session.refresh(candidate)
    return saved


def list_topics_with_review_state(
    session: Session,
    status: Optional[str] = None,
    date_str: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return topic suggestions with project info and persisted review state."""
    from sqlalchemy import func

    stmt = select(TopicSuggestion).order_by(TopicSuggestion.created_at.desc())
    if date_str:
        stmt = stmt.where(func.date(TopicSuggestion.created_at) == date_str)

    topics = session.exec(stmt.offset(offset).limit(limit)).all()
    output = [_topic_output(session, topic) for topic in topics]
    if status:
        output = [topic for topic in output if _matches_topic_status(topic, status)]
    return output


def get_topic_with_review_state(session: Session, topic: TopicSuggestion) -> dict:
    """Return one topic suggestion with project info and persisted review state."""
    return _topic_output(session, topic)


def list_topic_candidates(
    session: Session,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Return the stable candidate pool ordered by latest appearance."""
    missing_topics = session.exec(
        select(TopicSuggestion)
        .where(TopicSuggestion.candidate_id == None)
        .order_by(TopicSuggestion.created_at)
    ).all()
    if missing_topics:
        upsert_topic_candidates(session, list(missing_topics))

    stmt = select(TopicCandidate).order_by(TopicCandidate.last_seen_at.desc())
    if status and status != "chatting":
        stmt = stmt.where(TopicCandidate.status == status)

    candidates = session.exec(stmt.offset(offset).limit(limit)).all()
    output: list[dict] = []
    for candidate in candidates:
        if not candidate.latest_topic_id:
            continue
        topic = session.get(TopicSuggestion, candidate.latest_topic_id)
        if not topic:
            continue
        topic_output = _topic_output(session, topic, candidate)
        if _matches_topic_status(topic_output, status):
            output.append(topic_output)
    return output


def list_today_candidates(session: Session, limit: int = 8) -> list[dict]:
    """Return today's ranked topic candidates for the review workspace."""
    from sqlalchemy import func

    today = datetime.utcnow().strftime("%Y-%m-%d")
    topics = session.exec(
        select(TopicSuggestion)
        .where(func.date(TopicSuggestion.created_at) == today)
        .order_by(TopicSuggestion.final_score.desc(), TopicSuggestion.created_at.desc())
        .limit(limit)
    ).all()

    return [_topic_output(session, topic) for topic in topics]


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
