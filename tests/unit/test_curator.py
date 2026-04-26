"""Tests for CuratorAgent — pure computation, no external deps."""

import pytest

from gtrdashboard.agents.curator import CuratorAgent, DailyReport
from gtrdashboard.models import TopicSuggestion, UserPreference


@pytest.fixture
def curator() -> CuratorAgent:
    return CuratorAgent(top_n=3)


@pytest.fixture
def default_prefs() -> UserPreference:
    return UserPreference(local_ai_weight=0.30)


class TestCuratorEmptyInput:
    def test_empty_topics(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        report = curator.rank_with_scores([], default_prefs)
        assert report.total_analyzed == 0
        assert report.total_selected == 0
        assert report.topics == []
        assert "今日无选题" in report.report_summary


class TestCuratorScoring:
    def test_basic_ranking(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        topics = [
            TopicSuggestion(
                profile_id=1,
                differentiation_angle="Project A",
                engagement_estimate="high",
            ),
            TopicSuggestion(
                profile_id=2,
                differentiation_angle="Project B",
                engagement_estimate="medium",
            ),
            TopicSuggestion(
                profile_id=3,
                differentiation_angle="Project C",
                engagement_estimate="low",
            ),
        ]
        scores = [
            (topics[0], {"novelty": 8, "utility": 8, "local_ai": 9, "doc_quality": 7}),
            (topics[1], {"novelty": 6, "utility": 6, "local_ai": 5, "doc_quality": 5}),
            (topics[2], {"novelty": 4, "utility": 4, "local_ai": 4, "doc_quality": 4}),
        ]

        report = curator.rank_with_scores(scores, default_prefs)

        assert report.total_analyzed == 3
        assert report.total_selected == 3
        assert report.topics[0].rank == 1
        assert report.topics[0].topic.differentiation_angle == "Project A"
        assert report.topics[0].final_score > report.topics[1].final_score

    def test_top_n_limit(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        topics = [
            TopicSuggestion(profile_id=i, differentiation_angle=f"Project {i}")
            for i in range(5)
        ]
        scores = [
            (t, {"novelty": 5, "utility": 5, "local_ai": 5, "doc_quality": 5})
            for t in topics
        ]

        report = curator.rank_with_scores(scores, default_prefs)
        assert report.total_selected == 3  # curator.top_n = 3

    def test_local_ai_weight_impact(self) -> None:
        topic = TopicSuggestion(profile_id=1, differentiation_angle="Test")
        scores = {"novelty": 5, "utility": 5, "local_ai": 10, "doc_quality": 5}

        low_weight = UserPreference(local_ai_weight=0.0)
        high_weight = UserPreference(local_ai_weight=1.0)

        curator = CuratorAgent(top_n=1)
        report_low = curator.rank_with_scores([(topic, scores)], low_weight)
        report_high = curator.rank_with_scores([(topic, scores)], high_weight)

        assert report_high.topics[0].final_score > report_low.topics[0].final_score


class TestCuratorSelectionReason:
    def test_local_ai_reason(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        topic = TopicSuggestion(profile_id=1, differentiation_angle="Test")
        scores = {"novelty": 5, "utility": 5, "local_ai": 9, "doc_quality": 5}

        report = curator.rank_with_scores([(topic, scores)], default_prefs)
        assert "本地AI" in report.topics[0].selection_reason

    def test_novelty_reason(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        topic = TopicSuggestion(profile_id=1, differentiation_angle="Test")
        scores = {"novelty": 9, "utility": 5, "local_ai": 5, "doc_quality": 5}

        report = curator.rank_with_scores([(topic, scores)], default_prefs)
        assert "新颖度" in report.topics[0].selection_reason

    def test_balanced_fallback(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        topic = TopicSuggestion(profile_id=1, differentiation_angle="Test")
        scores = {"novelty": 5, "utility": 5, "local_ai": 5, "doc_quality": 5}

        report = curator.rank_with_scores([(topic, scores)], default_prefs)
        assert "综合评分平衡" in report.topics[0].selection_reason


class TestCuratorSummary:
    def test_summary_counts(self, curator: CuratorAgent, default_prefs: UserPreference) -> None:
        topics = [
            TopicSuggestion(profile_id=1, differentiation_angle="High"),
            TopicSuggestion(profile_id=2, differentiation_angle="Med"),
            TopicSuggestion(profile_id=3, differentiation_angle="Low"),
        ]
        scores = [
            (topics[0], {"novelty": 9, "utility": 9, "local_ai": 9, "doc_quality": 9}),
            (topics[1], {"novelty": 6, "utility": 6, "local_ai": 6, "doc_quality": 6}),
            (topics[2], {"novelty": 3, "utility": 3, "local_ai": 3, "doc_quality": 3}),
        ]

        report = curator.rank_with_scores(scores, default_prefs)
        assert "3 个选题" in report.report_summary
        assert "高潜力选题" in report.report_summary
        assert "中等潜力选题" in report.report_summary
