"""Scoring service for topic ranking and feedback adjustments."""

from __future__ import annotations

from dataclasses import dataclass, field

from gtrdashboard.models import ScoringWeight, TopicReviewSignal


@dataclass
class ScoreInput:
    """Inputs required to score a topic candidate."""

    novelty: int
    utility: int
    local_ai: int
    doc_quality: int
    engagement_estimate: str
    signals: list[TopicReviewSignal] = field(default_factory=list)


@dataclass
class ScoreResult:
    """Computed score with explainable components."""

    base_score: float
    preference_adjustment: float
    final_score: float


class ScoringService:
    """Compute topic scores using configured weights and review feedback."""

    def __init__(self, weights: ScoringWeight) -> None:
        self.weights = weights

    def score(self, score_input: ScoreInput) -> ScoreResult:
        """Return an explainable score for one topic."""
        engagement_map = {"high": 10, "medium": 6, "low": 3}
        engagement = engagement_map.get(score_input.engagement_estimate, 3)

        base_score = (
            score_input.novelty * self.weights.novelty_weight
            + score_input.utility * self.weights.utility_weight
            + score_input.local_ai * self.weights.local_ai_weight
            + score_input.doc_quality * self.weights.doc_quality_weight
            + engagement * self.weights.engagement_weight
        )
        preference_adjustment = self._preference_adjustment(score_input.signals)
        final_score = max(0.0, min(10.0, base_score + preference_adjustment))

        return ScoreResult(
            base_score=round(base_score, 2),
            preference_adjustment=round(preference_adjustment, 2),
            final_score=round(final_score, 2),
        )

    def _preference_adjustment(self, signals: list[TopicReviewSignal]) -> float:
        """Translate accumulated review signals into a small transparent adjustment."""
        adjustment = 0.0
        positive_keywords = ("可演示", "演示", "视频", "钩子", "普通观众")
        negative_keywords = ("太工程化", "太底层", "看不懂", "难视频化")

        for signal in signals:
            label = signal.label or ""
            strength = max(1, min(5, signal.strength))
            if signal.polarity == "positive" and any(k in label for k in positive_keywords):
                adjustment += strength * 0.08
            elif signal.polarity == "negative" and any(k in label for k in negative_keywords):
                adjustment -= strength * 0.08

        return adjustment
