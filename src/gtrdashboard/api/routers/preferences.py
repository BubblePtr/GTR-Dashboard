"""Preferences router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import PreferenceOut, PreferenceUpdate
from gtrdashboard.database import get_or_create_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=PreferenceOut)
def get_preferences(db: Session = Depends(get_db)) -> PreferenceOut:
    """Get current user preferences."""
    prefs = get_or_create_preferences(db)
    return PreferenceOut(
        id=prefs.id,
        positioning=prefs.positioning,
        preferred_languages=prefs.preferred_languages,
        min_stars_threshold=prefs.min_stars_threshold,
        local_ai_weight=prefs.local_ai_weight,
        daily_run_time=prefs.daily_run_time,
        auto_publish=prefs.auto_publish,
        updated_at=prefs.updated_at,
    )


@router.put("", response_model=PreferenceOut)
def update_preferences(
    update: PreferenceUpdate,
    db: Session = Depends(get_db),
) -> PreferenceOut:
    """Update user preferences."""
    prefs = get_or_create_preferences(db)

    if update.positioning is not None:
        prefs.positioning = update.positioning
    if update.preferred_languages is not None:
        prefs.preferred_languages = update.preferred_languages
    if update.min_stars_threshold is not None:
        prefs.min_stars_threshold = update.min_stars_threshold
    if update.local_ai_weight is not None:
        prefs.local_ai_weight = update.local_ai_weight
    if update.daily_run_time is not None:
        prefs.daily_run_time = update.daily_run_time
    if update.auto_publish is not None:
        prefs.auto_publish = update.auto_publish

    db.add(prefs)
    db.commit()
    db.refresh(prefs)

    return PreferenceOut(
        id=prefs.id,
        positioning=prefs.positioning,
        preferred_languages=prefs.preferred_languages,
        min_stars_threshold=prefs.min_stars_threshold,
        local_ai_weight=prefs.local_ai_weight,
        daily_run_time=prefs.daily_run_time,
        auto_publish=prefs.auto_publish,
        updated_at=prefs.updated_at,
    )
