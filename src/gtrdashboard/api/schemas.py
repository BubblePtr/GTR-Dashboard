"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# --- Pipeline ---

class PipelineRunConfig(BaseModel):
    """Config to trigger a pipeline run from the API."""

    languages: list[str] = Field(default=[""])
    limit: int = Field(default=50, ge=1, le=200)
    fetch_readme: bool = True
    profile_concurrency: int = Field(default=3, ge=1, le=10)
    top_n: int = Field(default=10, ge=1, le=50)
    source: str = Field(default="legacy")
    model: str = Field(default="qwen3.6-max-preview")


class PipelineRunResponse(BaseModel):
    """Response after triggering a pipeline."""

    run_id: int
    status: str


class PipelineRunStageOut(BaseModel):
    """Pipeline run stage progress."""

    id: int
    stage_name: str
    status: str
    progress: int
    message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None


class PipelineRunStatus(BaseModel):
    """Full status of a pipeline run."""

    id: int
    status: str
    projects_collected: int
    projects_analyzed: int
    topics_generated: int
    triggered_by: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    stages: list[PipelineRunStageOut] = []
    error_log: Optional[str] = None


# --- Topics ---

class TopicOut(BaseModel):
    """Topic suggestion with project info for frontend."""

    id: int
    candidate_id: Optional[int] = None
    profile_id: Optional[int]
    project_name: Optional[str] = None
    github_url: Optional[str] = None
    why_post: Optional[str] = None
    differentiation_angle: Optional[str] = None
    target_audience: Optional[str] = None
    engagement_estimate: str
    draft_tweet: Optional[str] = None
    draft_script: Optional[str] = None
    draft_outline: Optional[str] = None
    user_edited_draft_tweet: Optional[str] = None
    user_edited_draft_script: Optional[str] = None
    user_edited_draft_outline: Optional[str] = None
    review_notes: Optional[str] = None
    priority_score: Optional[float] = None
    final_score: Optional[float] = None
    generation_status: str
    created_at: datetime
    action: str = "pending"
    review_state: str = "未聊"
    message_count: int = 0
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    seen_count: int = 1
    latest_topic_id: Optional[int] = None


class ReviewSignalOut(BaseModel):
    """Structured learning signal extracted during topic review."""

    id: int
    topic_id: int
    candidate_id: Optional[int] = None
    message_id: Optional[int] = None
    signal_type: str
    label: str
    polarity: str
    strength: int
    created_at: datetime


class ReviewSignalIn(BaseModel):
    """Structured learning signal emitted by the reviewer agent."""

    signal_type: str
    label: str
    polarity: str = "neutral"
    strength: int = Field(default=3, ge=1, le=5)


class ReviewMessageOut(BaseModel):
    """Persisted chat message in a topic review session."""

    id: int
    topic_id: int
    candidate_id: Optional[int] = None
    role: str
    content: str
    created_at: datetime


class TopicReviewSessionOut(BaseModel):
    """Full review state for one topic."""

    topic: TopicOut
    messages: list[ReviewMessageOut]
    signals: list[ReviewSignalOut]


class TopicActionUpdate(BaseModel):
    """Update a topic's user action."""

    action: str  # pending | approved | published | skipped
    notes: Optional[str] = None


class TopicStats(BaseModel):
    """Count of topics by status."""

    pending: int
    approved: int
    published: int
    skipped: int
    total: int


class TopicChatRequest(BaseModel):
    """Send a message to the TopicReviewerAgent."""

    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


class TopicChatResponse(BaseModel):
    """Response from the TopicReviewerAgent."""

    response: str
    action: Optional[str] = None
    refined_content: Optional[str] = None
    signals: list[ReviewSignalIn] = Field(default_factory=list)


class TopicContentUpdate(BaseModel):
    """Update user-edited draft content for a topic."""

    user_edited_draft_tweet: Optional[str] = None
    user_edited_draft_script: Optional[str] = None
    user_edited_draft_outline: Optional[str] = None
    review_notes: Optional[str] = None


# --- Projects ---

class ProjectOut(BaseModel):
    """Raw project data."""

    id: int
    github_url: str
    name: str
    owner: str
    language: Optional[str]
    stars: Optional[int]
    description: Optional[str]
    collected_at: datetime


# --- Preferences ---

class PreferenceOut(BaseModel):
    """User preferences."""

    id: int
    positioning: Optional[str]
    preferred_languages: Optional[str]
    min_stars_threshold: int
    local_ai_weight: float
    daily_run_time: str
    auto_publish: bool
    updated_at: datetime


class PreferenceUpdate(BaseModel):
    """Update user preferences."""

    positioning: Optional[str] = None
    preferred_languages: Optional[str] = None
    min_stars_threshold: Optional[int] = None
    local_ai_weight: Optional[float] = None
    daily_run_time: Optional[str] = None
    auto_publish: Optional[bool] = None


# --- Weights ---

class WeightOut(BaseModel):
    """Scoring weights."""

    id: int
    novelty_weight: float
    utility_weight: float
    local_ai_weight: float
    doc_quality_weight: float
    engagement_weight: float
    updated_at: datetime


class WeightUpdate(BaseModel):
    """Update scoring weights."""

    novelty_weight: Optional[float] = None
    utility_weight: Optional[float] = None
    local_ai_weight: Optional[float] = None
    doc_quality_weight: Optional[float] = None
    engagement_weight: Optional[float] = None


# --- History ---

class HistoryPoint(BaseModel):
    """Single day's pipeline summary."""

    date: str
    avg_score: float
    total_projects: int
    total_selected: int
