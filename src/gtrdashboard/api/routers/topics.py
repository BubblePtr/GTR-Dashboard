"""Topics router."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import (
    ReviewMessageOut,
    ReviewSignalIn,
    ReviewSignalOut,
    TopicActionUpdate,
    TopicChatRequest,
    TopicChatResponse,
    TopicContentUpdate,
    TopicOut,
    TopicReviewSessionOut,
    TopicStats,
)
from gtrdashboard.database import (
    get_review_messages_for_topic,
    get_review_signals_for_topic,
    get_topic_with_review_state,
    list_today_candidates,
    list_topic_candidates,
    list_topics_with_review_state,
    save_review_message,
    save_review_signals,
)
from gtrdashboard.models import (
    TopicCandidate,
    TopicReviewMessage,
    TopicSuggestion,
    UserAction,
)
from gtrdashboard.review_signals import infer_signals_from_message

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/today", response_model=list[TopicOut])
def list_today_topics(
    db: Session = Depends(get_db),
    limit: int = Query(8, ge=1, le=20),
) -> list[dict]:
    """List today's ranked candidates for the agent-driven review workspace."""
    return list_today_candidates(db, limit=limit)


@router.get("", response_model=list[TopicOut])
def list_topics(
    db: Session = Depends(get_db),
    scope: str = Query("history", pattern="^(history|today|pool)$"),
    status: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List topics with optional status and date filtering."""
    if scope == "today":
        return list_today_candidates(db, limit=limit)
    if scope == "pool":
        return list_topic_candidates(db, status=status, limit=limit, offset=offset)
    return list_topics_with_review_state(
        db,
        status=status,
        date_str=date,
        limit=limit,
        offset=offset,
    )


@router.get("/{topic_id}/review", response_model=TopicReviewSessionOut)
def get_topic_review_session(
    topic_id: int,
    db: Session = Depends(get_db),
) -> TopicReviewSessionOut:
    """Get one topic plus its persisted review conversation and learning signals."""
    candidates = [
        c for c in list_topics_with_review_state(db, limit=200, offset=0) if c["id"] == topic_id
    ]
    if not candidates:
        topic = db.get(TopicSuggestion, topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        candidates = [get_topic_with_review_state(db, topic)]

    topic = db.get(TopicSuggestion, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    messages = get_review_messages_for_topic(db, topic)
    signals = get_review_signals_for_topic(db, topic)
    return TopicReviewSessionOut(
        topic=TopicOut(**candidates[0]),
        messages=[
            ReviewMessageOut(
                id=m.id,
                topic_id=m.topic_id,
                candidate_id=m.candidate_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
        signals=[
            ReviewSignalOut(
                id=s.id,
                topic_id=s.topic_id,
                candidate_id=s.candidate_id,
                message_id=s.message_id,
                signal_type=s.signal_type,
                label=s.label,
                polarity=s.polarity,
                strength=s.strength,
                created_at=s.created_at,
            )
            for s in signals
        ],
    )


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
    topic_output = get_topic_with_review_state(db, topic)
    candidate_id = topic_output.get("candidate_id")
    candidate = db.get(TopicCandidate, candidate_id) if candidate_id else None

    if action:
        action.action = update.action
        action.candidate_id = candidate_id
        action.notes = update.notes or action.notes
        action.acted_at = datetime.utcnow()
    else:
        action = UserAction(
            topic_id=topic_id,
            candidate_id=candidate_id,
            action=update.action,
            notes=update.notes,
            acted_at=datetime.utcnow(),
        )
        db.add(action)
    if candidate:
        candidate.status = update.action
        candidate.final_score = topic.final_score
        db.add(candidate)

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
    topic_output = get_topic_with_review_state(db, topic)
    candidate_id = topic_output.get("candidate_id")
    user_message = save_review_message(
        db,
        TopicReviewMessage(
            topic_id=topic_id,
            candidate_id=candidate_id,
            role="user",
            content=request.message,
        ),
    )
    inferred_signals = infer_signals_from_message(request.message)
    if inferred_signals:
        save_review_signals(db, topic_id, user_message.id, inferred_signals, candidate_id)

    persisted_history = [
        {"role": m.role, "content": m.content}
        for m in get_review_messages_for_topic(db, topic)
        if m.id != user_message.id
    ]

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
        history=request.history or persisted_history,
    )
    assistant_message = save_review_message(
        db,
        TopicReviewMessage(
            topic_id=topic_id,
            candidate_id=candidate_id,
            role="assistant",
            content=result.response,
        ),
    )
    if result.signals:
        save_review_signals(db, topic_id, assistant_message.id, result.signals, candidate_id)

    all_signals = [
        ReviewSignalIn(
            signal_type=s.signal_type,
            label=s.label,
            polarity=s.polarity,
            strength=s.strength,
        )
        for s in [*inferred_signals, *result.signals]
    ]

    return TopicChatResponse(
        response=result.response,
        action=result.action,
        refined_content=result.refined_content,
        signals=all_signals,
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
