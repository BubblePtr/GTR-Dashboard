"""CuratorAgent — ranks and selects top topics using a weighted formula.

Data flow:
    List[TopicSuggestion] + UserPreference
        → apply weighted formula
        → sort by final_score
        → DailyReport (top 10)

No LLM calls — pure computation.

Failure modes:
    - Empty input → return empty report
    - Invalid engagement_estimate → map to default
    - Division by zero → clamp score to 0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from gtrdashboard.models import TopicSuggestion, UserPreference


@dataclass
class CuratedTopic:
    """A topic with its computed rank and score."""

    topic: TopicSuggestion
    rank: int
    final_score: float
    selection_reason: str
    project_name: Optional[str] = None
    github_url: Optional[str] = None


@dataclass
class DailyReport:
    """The final curated daily report."""

    topics: list[CuratedTopic]
    report_summary: str
    total_analyzed: int
    total_selected: int


class CuratorAgent:
    """Ranks topics using weighted scoring and selects the best."""

    def __init__(self, top_n: int = 10) -> None:
        self.top_n = top_n

    def rank(
        self,
        topics: list[TopicSuggestion],
        preferences: UserPreference,
        project_names: dict[int, str] = {},
        project_urls: dict[int, str] = {},
    ) -> DailyReport:
        """Rank topics and produce a daily report.

        Args:
            topics: List of topic suggestions (must have linked profiles)
            preferences: User preferences including weight settings

        Returns:
            DailyReport with top N curated topics
        """
        if not topics:
            return DailyReport(
                topics=[],
                report_summary="今日无选题。",
                total_analyzed=0,
                total_selected=0,
            )

        # Score each topic
        scored: list[tuple[TopicSuggestion, float, str]] = []
        for topic in topics:
            score, reason = self._compute_score(topic, preferences)
            scored.append((topic, score, reason))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select top N
        selected: list[CuratedTopic] = []
        for i, (topic, score, reason) in enumerate(scored[: self.top_n], start=1):
            selected.append(
                CuratedTopic(
                    topic=topic,
                    rank=i,
                    final_score=round(score, 2),
                    selection_reason=reason,
                    project_name=project_names.get(topic.profile_id),
                    github_url=project_urls.get(topic.profile_id),
                )
            )

        # Generate summary
        summary = self._generate_summary(selected, scored)

        return DailyReport(
            topics=selected,
            report_summary=summary,
            total_analyzed=len(topics),
            total_selected=len(selected),
        )

    def _compute_score(
        self,
        topic: TopicSuggestion,
        preferences: UserPreference,
    ) -> tuple[float, str]:
        """Compute weighted score for a single topic.

        Returns:
            (final_score, selection_reason)
        """
        # Get linked profile scores
        # Profile data needs to be fetched — for now, we'll store profile
        # scores on the TopicSuggestion via a join, but since we don't have
        # the profile object here, we need to pass it differently.
        #
        # SOLUTION: We'll fetch profile data in the pipeline orchestrator
        # and attach scores to the TopicSuggestion as a temporary attribute,
        # or we change the interface to pass (TopicSuggestion, ProjectProfile) pairs.
        #
        # For now, we'll use a simpler approach: the pipeline passes profile
        # scores along with topics.

        # This is a placeholder — the actual scores come from profile data
        # We'll modify the pipeline to pass profile scores
        return 0.0, "Score computed in pipeline"

    def rank_with_scores(
        self,
        topics_with_scores: list[tuple[TopicSuggestion, dict[str, int]]],
        preferences: UserPreference,
        project_names: dict[int, str] = {},
        project_urls: dict[int, str] = {},
    ) -> DailyReport:
        """Rank topics with explicit profile scores.

        Args:
            topics_with_scores: List of (topic, profile_scores) tuples
                where profile_scores = {
                    "novelty": int,
                    "utility": int,
                    "doc_quality": int,
                    "local_ai": int,
                }
            preferences: User preferences

        Returns:
            DailyReport with top N curated topics
        """
        if not topics_with_scores:
            return DailyReport(
                topics=[],
                report_summary="今日无选题。",
                total_analyzed=0,
                total_selected=0,
            )

        # Clamp user weight to [0, 1]
        user_weight = max(0.0, min(1.0, preferences.local_ai_weight))

        # Map engagement estimate to boost score
        engagement_map = {"high": 10, "medium": 6, "low": 3}

        scored: list[tuple[TopicSuggestion, float, str]] = []
        for topic, scores in topics_with_scores:
            engagement_boost = engagement_map.get(topic.engagement_estimate, 3)

            final_score = (
                scores.get("novelty", 5) * 0.15
                + scores.get("utility", 5) * 0.20
                + scores.get("local_ai", 5) * user_weight
                + scores.get("doc_quality", 5) * 0.10
                + engagement_boost * 0.25
            )

            # Generate selection reason
            reasons = []
            if scores.get("local_ai", 5) >= 8:
                reasons.append("完美契合本地AI定位")
            elif scores.get("local_ai", 5) >= 6:
                reasons.append("本地部署能力强")
            if scores.get("novelty", 5) >= 8:
                reasons.append("高新颖度")
            if engagement_boost >= 8:
                reasons.append("高互动潜力")

            reason = reasons[0] if reasons else "综合评分平衡"
            scored.append((topic, final_score, reason))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select top N
        selected: list[CuratedTopic] = []
        for i, (topic, score, reason) in enumerate(scored[: self.top_n], start=1):
            selected.append(
                CuratedTopic(
                    topic=topic,
                    rank=i,
                    final_score=round(score, 2),
                    selection_reason=reason,
                    project_name=project_names.get(topic.profile_id),
                    github_url=project_urls.get(topic.profile_id),
                )
            )

        summary = self._generate_summary(selected, scored)

        return DailyReport(
            topics=selected,
            report_summary=summary,
            total_analyzed=len(topics_with_scores),
            total_selected=len(selected),
        )

    def _generate_summary(
        self,
        selected: list[CuratedTopic],
        all_scored: list[tuple[TopicSuggestion, float, str]],
    ) -> str:
        """Generate a summary of today's curation."""
        if not selected:
            return "今日无选题。"

        # Identify themes from tags
        high_scores = [t for t in all_scored if t[1] >= 7.0]
        medium_scores = [t for t in all_scored if 5.0 <= t[1] < 7.0]

        lines = [
            f"从 {len(all_scored)} 个分析项目中选出 {len(selected)} 个选题。",
            f"高潜力选题（分数≥7）：{len(high_scores)} 个",
            f"中等潜力选题（分数 5-7）：{len(medium_scores)} 个",
        ]

        # Top theme
        if selected:
            top = selected[0]
            project_label = top.project_name or top.topic.differentiation_angle or "N/A"
            lines.append(
                f"今日最佳：{project_label[:80]}..."
            )

        return " ".join(lines)
