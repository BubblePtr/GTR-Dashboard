"""Tests for topic review conversations and learning signals."""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from gtrdashboard.database import (
    get_review_messages,
    get_review_signals,
    list_today_candidates,
    list_topic_candidates,
    list_topics_with_review_state,
    save_review_message,
    save_review_signals,
    upsert_topic_candidates,
)
from gtrdashboard.models import (
    ProjectProfile,
    RawProject,
    ReviewSignalInput,
    TopicReviewMessage,
    TopicReviewSignal,
    TopicSuggestion,
    UserAction,
)


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_review_messages_and_signals_round_trip() -> None:
    with make_session() as session:
        topic = TopicSuggestion(profile_id=1, why_post="值得做", final_score=8.4)
        session.add(topic)
        session.commit()
        session.refresh(topic)

        message = save_review_message(
            session,
            TopicReviewMessage(
                topic_id=topic.id,
                role="user",
                content="这个项目太工程化，我更想要可以演示的 60 秒视频。",
            ),
        )
        save_review_signals(
            session,
            topic.id,
            message.id,
            [
                ReviewSignalInput(
                    signal_type="concern",
                    label="担心太工程化",
                    polarity="negative",
                    strength=4,
                ),
                ReviewSignalInput(
                    signal_type="requirement",
                    label="需要 60 秒演示钩子",
                    polarity="positive",
                    strength=5,
                ),
            ],
        )

        messages = get_review_messages(session, topic.id)
        signals = get_review_signals(session, topic.id)

        assert [m.content for m in messages] == [
            "这个项目太工程化，我更想要可以演示的 60 秒视频。"
        ]
        assert [s.label for s in signals] == ["担心太工程化", "需要 60 秒演示钩子"]
        assert all(isinstance(signal, TopicReviewSignal) for signal in signals)


def test_today_candidates_are_ranked_and_include_review_state() -> None:
    with make_session() as session:
        project_a = RawProject(github_url="https://github.com/a/demo", owner="a", name="demo")
        project_b = RawProject(github_url="https://github.com/b/core", owner="b", name="core")
        session.add_all([project_a, project_b])
        session.commit()
        session.refresh(project_a)
        session.refresh(project_b)

        profile_a = ProjectProfile(
            raw_project_id=project_a.id,
            novelty_score=8,
            utility_score=8,
            doc_quality_score=7,
            local_ai_relevance=9,
        )
        profile_b = ProjectProfile(
            raw_project_id=project_b.id,
            novelty_score=6,
            utility_score=6,
            doc_quality_score=5,
            local_ai_relevance=5,
        )
        session.add_all([profile_a, profile_b])
        session.commit()
        session.refresh(profile_a)
        session.refresh(profile_b)

        topic_low = TopicSuggestion(profile_id=profile_b.id, why_post="偏底层", final_score=5.1)
        topic_high = TopicSuggestion(profile_id=profile_a.id, why_post="可演示", final_score=8.7)
        session.add_all([topic_low, topic_high])
        session.commit()
        session.refresh(topic_low)
        session.refresh(topic_high)

        save_review_message(
            session,
            TopicReviewMessage(topic_id=topic_high.id, role="user", content="先聊这个"),
        )
        session.add(UserAction(topic_id=topic_low.id, action="skipped", notes="太工程化"))
        session.commit()

        candidates = list_today_candidates(session, limit=8)

        assert [candidate["project_name"] for candidate in candidates] == ["a/demo", "b/core"]
        assert candidates[0]["review_state"] == "对话中"
        assert candidates[1]["action"] == "skipped"
        assert candidates[1]["review_state"] == "已跳过"


def test_topic_candidate_pool_upserts_repeated_github_url() -> None:
    with make_session() as session:
        project = RawProject(github_url="https://github.com/a/demo", owner="a", name="demo")
        session.add(project)
        session.commit()
        session.refresh(project)

        profile_a = ProjectProfile(
            raw_project_id=project.id,
            novelty_score=8,
            utility_score=8,
            doc_quality_score=7,
            local_ai_relevance=9,
        )
        profile_b = ProjectProfile(
            raw_project_id=project.id,
            novelty_score=9,
            utility_score=8,
            doc_quality_score=8,
            local_ai_relevance=9,
        )
        session.add_all([profile_a, profile_b])
        session.commit()
        session.refresh(profile_a)
        session.refresh(profile_b)

        first_topic = TopicSuggestion(profile_id=profile_a.id, why_post="第一次出现", final_score=7.1)
        second_topic = TopicSuggestion(profile_id=profile_b.id, why_post="再次出现", final_score=8.3)
        session.add_all([first_topic, second_topic])
        session.commit()
        session.refresh(first_topic)
        session.refresh(second_topic)

        upsert_topic_candidates(session, [first_topic])
        upsert_topic_candidates(session, [second_topic])

        pool = list_topic_candidates(session)

        assert len(pool) == 1
        assert pool[0]["github_url"] == "https://github.com/a/demo"
        assert pool[0]["project_name"] == "a/demo"
        assert pool[0]["seen_count"] == 2
        assert pool[0]["latest_topic_id"] == second_topic.id
        assert pool[0]["id"] == second_topic.id
        assert pool[0]["candidate_id"] is not None
        assert pool[0]["final_score"] == 8.3


def test_history_topics_include_real_review_state_and_message_count() -> None:
    with make_session() as session:
        project = RawProject(github_url="https://github.com/a/demo", owner="a", name="demo")
        session.add(project)
        session.commit()
        session.refresh(project)

        profile = ProjectProfile(
            raw_project_id=project.id,
            novelty_score=8,
            utility_score=8,
            doc_quality_score=7,
            local_ai_relevance=9,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        topic = TopicSuggestion(profile_id=profile.id, why_post="可演示", final_score=8.7)
        session.add(topic)
        session.commit()
        session.refresh(topic)
        upsert_topic_candidates(session, [topic])

        save_review_message(
            session,
            TopicReviewMessage(topic_id=topic.id, role="user", content="先聊这个"),
        )

        topics = list_topics_with_review_state(session)

        assert len(topics) == 1
        assert topics[0]["project_name"] == "a/demo"
        assert topics[0]["github_url"] == "https://github.com/a/demo"
        assert topics[0]["review_state"] == "对话中"
        assert topics[0]["message_count"] == 1


def test_topic_candidate_pool_backfills_existing_topic_snapshots() -> None:
    with make_session() as session:
        project = RawProject(github_url="https://github.com/a/demo", owner="a", name="demo")
        session.add(project)
        session.commit()
        session.refresh(project)

        profile = ProjectProfile(
            raw_project_id=project.id,
            novelty_score=8,
            utility_score=8,
            doc_quality_score=7,
            local_ai_relevance=9,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        topic = TopicSuggestion(profile_id=profile.id, why_post="历史候选", final_score=8.1)
        session.add(topic)
        session.commit()
        session.refresh(topic)

        pool = list_topic_candidates(session)

        assert len(pool) == 1
        assert pool[0]["github_url"] == "https://github.com/a/demo"
        assert pool[0]["project_name"] == "a/demo"
        assert pool[0]["seen_count"] == 1
