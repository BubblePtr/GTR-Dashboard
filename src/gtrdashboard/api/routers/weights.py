"""Weights router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import WeightOut, WeightUpdate
from gtrdashboard.database import get_or_create_weights

router = APIRouter(prefix="/weights", tags=["weights"])


@router.get("", response_model=WeightOut)
def get_weights(db: Session = Depends(get_db)) -> WeightOut:
    """Get current scoring weights."""
    weights = get_or_create_weights(db)
    return WeightOut(
        id=weights.id,
        novelty_weight=weights.novelty_weight,
        utility_weight=weights.utility_weight,
        local_ai_weight=weights.local_ai_weight,
        doc_quality_weight=weights.doc_quality_weight,
        engagement_weight=weights.engagement_weight,
        updated_at=weights.updated_at,
    )


@router.put("", response_model=WeightOut)
def update_weights(
    update: WeightUpdate,
    db: Session = Depends(get_db),
) -> WeightOut:
    """Update scoring weights."""
    weights = get_or_create_weights(db)

    if update.novelty_weight is not None:
        weights.novelty_weight = update.novelty_weight
    if update.utility_weight is not None:
        weights.utility_weight = update.utility_weight
    if update.local_ai_weight is not None:
        weights.local_ai_weight = update.local_ai_weight
    if update.doc_quality_weight is not None:
        weights.doc_quality_weight = update.doc_quality_weight
    if update.engagement_weight is not None:
        weights.engagement_weight = update.engagement_weight

    db.add(weights)
    db.commit()
    db.refresh(weights)

    return WeightOut(
        id=weights.id,
        novelty_weight=weights.novelty_weight,
        utility_weight=weights.utility_weight,
        local_ai_weight=weights.local_ai_weight,
        doc_quality_weight=weights.doc_quality_weight,
        engagement_weight=weights.engagement_weight,
        updated_at=weights.updated_at,
    )
