"""FastAPI dependencies."""

from typing import Generator

from sqlmodel import Session

from gtrdashboard.database import engine


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependency injection."""
    with Session(engine, expire_on_commit=False) as session:
        yield session
