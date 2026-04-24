"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gtrdashboard.api.routers import (
    history,
    pipeline,
    preferences,
    projects,
    reports,
    topics,
    weights,
)
from gtrdashboard.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan: init DB on startup."""
    init_db()
    yield


app = FastAPI(
    title="GTR Dashboard API",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/v1")
app.include_router(topics.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(preferences.router, prefix="/api/v1")
app.include_router(weights.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


def main() -> None:
    import uvicorn

    uvicorn.run("gtrdashboard.api.main:app", host="0.0.0.0", port=9000, reload=True)
