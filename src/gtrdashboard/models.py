"""SQLModel definitions for GTR Dashboard.

Data relationships:
    RawProject (1) ──> ProjectProfile (1) ──> TopicSuggestion (1) ──> UserAction (N)
    UserPreference (1) ──> influences all Agent analysis
    PipelineRun (1) ──> tracks each execution
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RawProject(SQLModel, table=True):
    """Raw project data scraped from GitHub Trending."""

    __tablename__ = "raw_projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    github_url: str = Field(index=True, unique=True)
    name: str
    owner: str
    language: Optional[str] = None
    stars: Optional[int] = None
    description: Optional[str] = None
    readme_text: Optional[str] = None
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectProfile(SQLModel, table=True):
    """LLM-generated analysis of a project."""

    __tablename__ = "project_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    raw_project_id: Optional[int] = Field(default=None, foreign_key="raw_projects.id")
    novelty_score: int = Field(ge=1, le=10)
    utility_score: int = Field(ge=1, le=10)
    doc_quality_score: int = Field(ge=1, le=10)
    local_ai_relevance: int = Field(ge=1, le=10)
    tags: Optional[str] = None  # JSON array stored as string
    summary: Optional[str] = None
    analysis_status: str = Field(default="complete")  # complete | degraded | failed
    analysis_reason: Optional[str] = None  # why degraded/failed
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class TopicSuggestion(SQLModel, table=True):
    """Content strategy output for a project."""

    __tablename__ = "topic_suggestions"

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: Optional[int] = Field(default=None, foreign_key="project_profiles.id")
    candidate_id: Optional[int] = Field(default=None, foreign_key="topic_candidates.id")
    why_post: Optional[str] = None
    differentiation_angle: Optional[str] = None
    target_audience: Optional[str] = None
    engagement_estimate: str = Field(default="medium")  # high | medium | low
    draft_tweet: Optional[str] = None
    draft_script: Optional[str] = None
    draft_outline: Optional[str] = None
    user_edited_draft_tweet: Optional[str] = None
    user_edited_draft_script: Optional[str] = None
    user_edited_draft_outline: Optional[str] = None
    review_notes: Optional[str] = None
    priority_score: Optional[float] = None
    final_score: Optional[float] = None
    generation_status: str = Field(default="complete")  # complete | degraded | failed
    generation_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TopicCandidate(SQLModel, table=True):
    """Stable candidate pool entry keyed by GitHub project URL."""

    __tablename__ = "topic_candidates"

    id: Optional[int] = Field(default=None, primary_key=True)
    github_url: str = Field(index=True, unique=True)
    project_name: Optional[str] = None
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    seen_count: int = Field(default=1)
    latest_topic_id: Optional[int] = Field(default=None, foreign_key="topic_suggestions.id")
    status: str = Field(default="pending")  # pending | approved | published | skipped
    final_score: Optional[float] = None


class UserAction(SQLModel, table=True):
    """User feedback on topic suggestions."""

    __tablename__ = "user_actions"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: Optional[int] = Field(default=None, foreign_key="topic_suggestions.id")
    candidate_id: Optional[int] = Field(default=None, foreign_key="topic_candidates.id")
    action: str = Field(default="pending")  # pending | approved | published | skipped
    notes: Optional[str] = None
    acted_at: datetime = Field(default_factory=datetime.utcnow)


class TopicReviewMessage(SQLModel, table=True):
    """Persisted chat message for reviewing a topic."""

    __tablename__ = "topic_review_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic_suggestions.id", index=True)
    candidate_id: Optional[int] = Field(default=None, foreign_key="topic_candidates.id", index=True)
    role: str  # user | assistant
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TopicReviewSignal(SQLModel, table=True):
    """Structured preference signal extracted from a review conversation."""

    __tablename__ = "topic_review_signals"

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic_suggestions.id", index=True)
    candidate_id: Optional[int] = Field(default=None, foreign_key="topic_candidates.id", index=True)
    message_id: Optional[int] = Field(default=None, foreign_key="topic_review_messages.id")
    signal_type: str  # preference | concern | requirement | adoption_reason | rejection_reason
    label: str
    polarity: str = Field(default="neutral")  # positive | negative | neutral
    strength: int = Field(default=3, ge=1, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewSignalInput(SQLModel):
    """Input shape for creating a review signal."""

    signal_type: str
    label: str
    polarity: str = "neutral"
    strength: int = Field(default=3, ge=1, le=5)


class PipelineRun(SQLModel, table=True):
    """Tracks each pipeline execution."""

    __tablename__ = "pipeline_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="running")  # running | success | partial_failure | failed
    projects_collected: int = Field(default=0)
    projects_analyzed: int = Field(default=0)
    topics_generated: int = Field(default=0)
    error_log: Optional[str] = None
    triggered_by: str = Field(default="manual")  # manual | scheduled | api
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class PipelineRunStage(SQLModel, table=True):
    """Tracks progress of each pipeline stage."""

    __tablename__ = "pipeline_run_stages"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="pipeline_runs.id", index=True)
    stage_name: str  # collect | profile | strategize | curate | report
    status: str = Field(default="running")  # running | complete | failed
    progress: int = Field(default=0, ge=0, le=100)
    message: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None


class UserPreference(SQLModel, table=True):
    """User taste and positioning configuration."""

    __tablename__ = "user_preferences"

    id: Optional[int] = Field(default=None, primary_key=True)
    positioning: Optional[str] = Field(default="本地AI实战派")
    preferred_languages: Optional[str] = Field(default='["python", "typescript", "go"]')
    blacklist_keywords: Optional[str] = Field(default="[]")
    whitelist_keywords: Optional[str] = Field(default="[]")
    min_stars_threshold: int = Field(default=100)
    local_ai_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    daily_run_time: str = Field(default="09:00")
    auto_publish: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScoringWeight(SQLModel, table=True):
    """Configurable scoring weights for curation."""

    __tablename__ = "scoring_weights"

    id: Optional[int] = Field(default=None, primary_key=True)
    novelty_weight: float = Field(default=0.15, ge=0.0, le=1.0)
    utility_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    local_ai_weight: float = Field(default=0.30, ge=0.0, le=1.0)
    doc_quality_weight: float = Field(default=0.10, ge=0.0, le=1.0)
    engagement_weight: float = Field(default=0.25, ge=0.0, le=1.0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
