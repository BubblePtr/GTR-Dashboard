"""Tests for configurable scoring and feedback adjustments."""

from __future__ import annotations

from gtrdashboard.models import ScoringWeight, TopicReviewSignal
from gtrdashboard.scoring import ScoreInput, ScoringService


def test_scoring_service_uses_configured_weights() -> None:
    service = ScoringService(
        ScoringWeight(
            novelty_weight=0.0,
            utility_weight=0.0,
            local_ai_weight=1.0,
            doc_quality_weight=0.0,
            engagement_weight=0.0,
        )
    )

    score = service.score(
        ScoreInput(
            novelty=1,
            utility=1,
            local_ai=9,
            doc_quality=1,
            engagement_estimate="low",
        )
    )

    assert score.base_score == 9.0
    assert score.final_score == 9.0


def test_scoring_service_boosts_positive_video_demo_signals() -> None:
    service = ScoringService(ScoringWeight())

    without_signal = service.score(
        ScoreInput(
            novelty=5,
            utility=5,
            local_ai=5,
            doc_quality=5,
            engagement_estimate="medium",
        )
    )
    with_signal = service.score(
        ScoreInput(
            novelty=5,
            utility=5,
            local_ai=5,
            doc_quality=5,
            engagement_estimate="medium",
            signals=[
                TopicReviewSignal(
                    topic_id=1,
                    signal_type="requirement",
                    label="偏好可演示项目",
                    polarity="positive",
                    strength=5,
                )
            ],
        )
    )

    assert with_signal.preference_adjustment > 0
    assert with_signal.final_score > without_signal.final_score
