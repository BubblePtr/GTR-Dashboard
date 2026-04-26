"""Tests for database operations — uses in-memory SQLite."""

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from gtrdashboard.database import (
    init_db,
    get_or_create_preferences,
    save_profiles,
    save_raw_projects,
    save_topics,
)
from gtrdashboard.models import (
    PipelineRun,
    ProjectProfile,
    RawProject,
    TopicSuggestion,
    UserPreference,
)


@pytest.fixture
def session():
    """Create an in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestUserPreferences:
    def test_create_default(self, session: Session) -> None:
        prefs = get_or_create_preferences(session)
        assert prefs.positioning == "本地AI实战派"
        assert prefs.local_ai_weight == 0.30

    def test_get_existing(self, session: Session) -> None:
        prefs1 = get_or_create_preferences(session)
        prefs1.positioning = "Custom"
        session.add(prefs1)
        session.commit()

        prefs2 = get_or_create_preferences(session)
        assert prefs2.positioning == "Custom"


class TestSaveRawProjects:
    def test_insert_new(self, session: Session) -> None:
        projects = [
            RawProject(
                github_url="https://github.com/a/b",
                name="b",
                owner="a",
                stars=100,
            )
        ]
        saved = save_raw_projects(session, projects)
        assert len(saved) == 1
        assert saved[0].id is not None

    def test_upsert_existing(self, session: Session) -> None:
        project = RawProject(
            github_url="https://github.com/a/b",
            name="b",
            owner="a",
            stars=100,
        )
        save_raw_projects(session, [project])

        updated = RawProject(
            github_url="https://github.com/a/b",
            name="b",
            owner="a",
            stars=200,
        )
        saved = save_raw_projects(session, [updated])
        assert saved[0].stars == 200

    def test_dedup_by_url(self, session: Session) -> None:
        projects = [
            RawProject(github_url="https://github.com/a/b", name="b", owner="a"),
            RawProject(github_url="https://github.com/a/b", name="b", owner="a"),
        ]
        saved = save_raw_projects(session, projects)
        # Both get saved but second updates first in same session
        # In practice, collect() dedups before calling save
        assert len(saved) == 2


class TestSaveProfiles:
    def test_save_and_get_id(self, session: Session) -> None:
        profiles = [
            ProjectProfile(
                raw_project_id=1,
                novelty_score=7,
                utility_score=8,
                doc_quality_score=6,
                local_ai_relevance=9,
            )
        ]
        saved = save_profiles(session, profiles)
        assert saved[0].id is not None
        assert saved[0].novelty_score == 7


class TestSaveTopics:
    def test_save_topic(self, session: Session) -> None:
        topics = [
            TopicSuggestion(
                profile_id=1,
                why_post="Because it's great",
                engagement_estimate="high",
                generation_status="complete",
            )
        ]
        saved = save_topics(session, topics)
        assert saved[0].id is not None
        assert saved[0].generation_status == "complete"


class TestSchemaMigration:
    def test_init_db_adds_missing_topic_review_columns(self, tmp_path, monkeypatch) -> None:
        db_path = tmp_path / "legacy.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE topic_suggestions (
                    id INTEGER PRIMARY KEY,
                    profile_id INTEGER,
                    why_post VARCHAR,
                    differentiation_angle VARCHAR,
                    target_audience VARCHAR,
                    engagement_estimate VARCHAR NOT NULL,
                    draft_tweet VARCHAR,
                    draft_script VARCHAR,
                    draft_outline VARCHAR,
                    priority_score FLOAT,
                    final_score FLOAT,
                    generation_status VARCHAR NOT NULL,
                    generation_reason VARCHAR,
                    created_at DATETIME NOT NULL
                )
                """
            )

        monkeypatch.setattr("gtrdashboard.database.engine", engine)
        init_db()

        with engine.connect() as conn:
            columns = {
                row[1] for row in conn.exec_driver_sql("PRAGMA table_info(topic_suggestions)")
            }

        assert "user_edited_draft_tweet" in columns
        assert "user_edited_draft_script" in columns
        assert "user_edited_draft_outline" in columns
        assert "review_notes" in columns
