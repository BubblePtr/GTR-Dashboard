"""Topics router."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import (
    TopicActionUpdate,
    TopicChatRequest,
    TopicChatResponse,
    TopicContentUpdate,
    TopicOut,
    TopicStats,
)
from gtrdashboard.models import TopicSuggestion, UserAction

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicOut])
def list_topics(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List topics with optional status and date filtering."""
    # Build base query joining topics with their actions
    stmt = (
        select(TopicSuggestion, UserAction)
        .outerjoin(UserAction, TopicSuggestion.id == UserAction.topic_id)
        .order_by(TopicSuggestion.created_at.desc())
    )

    if date:
        stmt = stmt.where(func.date(TopicSuggestion.created_at) == date)

    results = db.exec(stmt.offset(offset).limit(limit)).all()

    # Filter by status in Python (simpler than complex SQL for pending default)
    output: list[dict] = []
    for topic, action in results:
        topic_status = action.action if action else "pending"
        if status and topic_status != status:
            continue

        # Get project info via profile -> raw_project join
        project_name = None
        github_url = None
        if topic.profile_id:
            from gtrdashboard.models import ProjectProfile, RawProject

            profile = db.get(ProjectProfile, topic.profile_id)
            if profile and profile.raw_project_id:
                project = db.get(RawProject, profile.raw_project_id)
                if project:
                    project_name = f"{project.owner}/{project.name}"
                    github_url = project.github_url

        output.append(
            {
                "id": topic.id,
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
                "final_score": topic.final_score,
                "generation_status": topic.generation_status,
                "created_at": topic.created_at,
                "action": topic_status,
            }
        )
    return output


@router.patch("/{topic_id}/action")
def update_topic_action(
    topic_id: int,
    update: TopicActionUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Update the user action for a topic."""
    topic = db.get(TopicSuggestion, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    action = db.exec(
        select(UserAction).where(UserAction.topic_id == topic_id)
    ).first()

    if action:
        action.action = update.action
        action.notes = update.notes or action.notes
        action.acted_at = datetime.utcnow()
    else:
        action = UserAction(
            topic_id=topic_id,
            action=update.action,
            notes=update.notes,
            acted_at=datetime.utcnow(),
        )
        db.add(action)

    db.commit()
    return {"topic_id": topic_id, "action": update.action}


@router.post("/{topic_id}/chat", response_model=TopicChatResponse)
async def chat_with_topic(
    topic_id: int,
    request: TopicChatRequest,
    db: Session = Depends(get_db),
) -> TopicChatResponse:
    """Chat with the TopicReviewerAgent about a specific topic."""
    from gtrdashboard.agents.topic_reviewer import ReviewerConfig, TopicReviewerAgent
    from gtrdashboard.database import get_or_create_preferences
    from gtrdashboard.models import ProjectProfile, RawProject

    topic = db.get(TopicSuggestion, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Load related data
    profile = None
    project = None
    if topic.profile_id:
        profile = db.get(ProjectProfile, topic.profile_id)
        if profile and profile.raw_project_id:
            project = db.get(RawProject, profile.raw_project_id)

    if not profile or not project:
        raise HTTPException(status_code=404, detail="Topic profile or project not found")

    preferences = get_or_create_preferences(db)

    agent = TopicReviewerAgent(
        ReviewerConfig(
            positioning=preferences.positioning or "本地AI实战派",
        )
    )

    result = await agent.chat(
        topic=topic,
        profile=profile,
        project=project,
        preferences=preferences,
        user_message=request.message,
        history=request.history or [],
    )

    return TopicChatResponse(
        response=result.response,
        action=result.action,
        refined_content=result.refined_content,
    )


@router.patch("/{topic_id}/content")
def update_topic_content(
    topic_id: int,
    update: TopicContentUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Update user-edited content for a topic."""
    topic = db.get(TopicSuggestion, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    if update.user_edited_draft_tweet is not None:
        topic.user_edited_draft_tweet = update.user_edited_draft_tweet
    if update.user_edited_draft_script is not None:
        topic.user_edited_draft_script = update.user_edited_draft_script
    if update.user_edited_draft_outline is not None:
        topic.user_edited_draft_outline = update.user_edited_draft_outline
    if update.review_notes is not None:
        topic.review_notes = update.review_notes

    db.add(topic)
    db.commit()
    return {"topic_id": topic_id, "updated": True}


@router.get("/stats", response_model=TopicStats)
def get_topic_stats(db: Session = Depends(get_db)) -> TopicStats:
    """Get counts of topics by action status."""
    # Count all topics
    total = db.exec(select(func.count(TopicSuggestion.id))).one()

    # Count by action status
    pending = db.exec(
        select(func.count(TopicSuggestion.id))
        .outerjoin(UserAction, TopicSuggestion.id == UserAction.topic_id)
        .where((UserAction.id == None) | (UserAction.action == "pending"))
    ).one()

    approved = db.exec(
        select(func.count(UserAction.id)).where(UserAction.action == "approved")
    ).one()

    published = db.exec(
        select(func.count(UserAction.id)).where(UserAction.action == "published")
    ).one()

    skipped = db.exec(
        select(func.count(UserAction.id)).where(UserAction.action == "skipped")
    ).one()

    return TopicStats(
        pending=pending or 0,
        approved=approved or 0,
        published=published or 0,
        skipped=skipped or 0,
        total=total or 0,
    )
