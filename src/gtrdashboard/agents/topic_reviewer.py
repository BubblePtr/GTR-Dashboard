"""TopicReviewerAgent — conversational review and content refinement for a single topic.

Data flow:
    Topic + Profile + Project + UserPreference + message history
        → format as context string
        → OpenAI chat.completions.create with JSON prompt
        → ReviewerOutput

Failure modes:
    - LLM API error → return generic fallback response
    - Invalid response format → retry once, then fallback
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from gtrdashboard.models import ProjectProfile, RawProject, TopicSuggestion, UserPreference
from gtrdashboard.prompts import load_reviewer_prompt


class ReviewerOutput(BaseModel):
    """Structured output from TopicReviewerAgent."""

    response: str = Field(default="")
    action: Optional[str] = Field(default=None)
    refined_content: Optional[str] = Field(default=None)


@dataclass
class ReviewerConfig:
    """Configuration for TopicReviewer."""

    positioning: str = "本地AI实战派"
    model: str = "qwen3.6-max-preview"


class TopicReviewerAgent:
    """Conversational agent for reviewing and refining individual topics."""

    def __init__(self, config: Optional[ReviewerConfig] = None) -> None:
        self.config = config or ReviewerConfig()
        self._client: Optional[object] = None

    def _get_client(self) -> object:
        """Return an OpenAI client configured from env."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
        return self._client

    async def chat(
        self,
        topic: TopicSuggestion,
        profile: ProjectProfile,
        project: RawProject,
        preferences: UserPreference,
        user_message: str,
        history: Optional[list[dict[str, str]]] = None,
    ) -> ReviewerOutput:
        """Process a user message and return a review response.

        Args:
            topic: The topic suggestion being reviewed
            profile: The project profile with scores
            project: The raw project data
            preferences: User preferences for positioning
            user_message: The user's current message
            history: Optional list of previous messages [{"role": "user|assistant", "content": "..."}]

        Returns:
            ReviewerOutput with response text, action type, and optional refined content
        """
        system_prompt = self._build_system_prompt(topic, profile, project, preferences)
        messages = self._build_messages(system_prompt, history, user_message)

        client = self._get_client()

        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.config.model,
                messages=messages,
                temperature=0.7,
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.strip("`").strip()
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            data = json.loads(text)
            return ReviewerOutput(**data)

        except Exception as e:
            print(f"[TopicReviewer] Chat failed: {e}")
            return self._fallback_response(user_message)

    def _build_system_prompt(
        self,
        topic: TopicSuggestion,
        profile: ProjectProfile,
        project: RawProject,
        preferences: UserPreference,
    ) -> str:
        """Build the system prompt with full context."""
        prompt = load_reviewer_prompt()
        prompt = prompt.replace("{{ positioning }}", preferences.positioning or "本地AI实战派")

        # Parse tags
        tags = []
        if profile.tags:
            try:
                tags = json.loads(profile.tags)
            except json.JSONDecodeError:
                tags = []

        # Build context block
        context_lines = [
            "\n\n## CURRENT TOPIC CONTEXT\n",
            f"Project: {project.owner}/{project.name}",
            f"GitHub: {project.github_url}",
            f"Stars: {project.stars or 'N/A'}",
            f"Language: {project.language or 'N/A'}",
            f"Description: {project.description or 'N/A'}",
            "",
            "Profile Scores:",
            f"  - Novelty: {profile.novelty_score}/10",
            f"  - Utility: {profile.utility_score}/10",
            f"  - Local AI Relevance: {profile.local_ai_relevance}/10",
            f"  - Doc Quality: {profile.doc_quality_score}/10",
            f"  - Tags: {', '.join(tags) if tags else 'N/A'}",
            f"  - Summary: {profile.summary or 'N/A'}",
            "",
            "Current Drafts (Original):",
            f"  - Tweet: {topic.draft_tweet or '(none)'}",
            f"  - Script: {topic.draft_script or '(none)'}",
            f"  - Outline: {topic.draft_outline or '(none)'}",
            "",
            "Current Drafts (User Edited):",
            f"  - Tweet: {topic.user_edited_draft_tweet or '(none)'}",
            f"  - Script: {topic.user_edited_draft_script or '(none)'}",
            f"  - Outline: {topic.user_edited_draft_outline or '(none)'}",
            "",
            "Topic Strategy:",
            f"  - Why Post: {topic.why_post or 'N/A'}",
            f"  - Differentiation: {topic.differentiation_angle or 'N/A'}",
            f"  - Target Audience: {topic.target_audience or 'N/A'}",
            f"  - Engagement Estimate: {topic.engagement_estimate}",
            f"  - Final Score: {topic.final_score or 'N/A'}",
        ]

        schema_hint = (
            "\n\nYou MUST return ONLY a single valid JSON object matching this schema:\n"
            + json.dumps(ReviewerOutput.model_json_schema(), indent=2)
            + "\nDo not wrap in markdown code blocks."
        )

        return prompt + "\n".join(context_lines) + schema_hint

    def _build_messages(
        self,
        system_prompt: str,
        history: Optional[list[dict[str, str]]],
        user_message: str,
    ) -> list[dict[str, str]]:
        """Build the message list for the LLM call."""
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if history:
            for msg in history:
                # Only include user and assistant roles (skip any system messages in history)
                if msg.get("role") in ("user", "assistant"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _fallback_response(self, user_message: str) -> ReviewerOutput:
        """Return a safe fallback when the LLM call fails."""
        return ReviewerOutput(
            response="抱歉，处理你的请求时出错了。请重试或换个方式提问。",
            action="general",
            refined_content=None,
        )
