"""Lightweight extraction of review signals from user messages."""

from __future__ import annotations

from gtrdashboard.models import ReviewSignalInput


def infer_signals_from_message(message: str) -> list[ReviewSignalInput]:
    """Infer transparent preference signals from a review chat message."""
    text = message.strip()
    signals: list[ReviewSignalInput] = []

    if "太工程化" in text or "太底层" in text:
        signals.append(
            ReviewSignalInput(
                signal_type="concern",
                label="担心太工程化",
                polarity="negative",
                strength=4,
            )
        )

    if "普通观众" in text or "看不懂" in text:
        signals.append(
            ReviewSignalInput(
                signal_type="requirement",
                label="重视普通观众理解",
                polarity="positive",
                strength=4,
            )
        )

    if "演示" in text or "实战" in text:
        signals.append(
            ReviewSignalInput(
                signal_type="preference",
                label="偏好可演示项目",
                polarity="positive",
                strength=5,
            )
        )

    if "60 秒" in text or "60秒" in text or "钩子" in text:
        signals.append(
            ReviewSignalInput(
                signal_type="requirement",
                label="需要 60 秒视频钩子",
                polarity="positive",
                strength=5,
            )
        )

    return signals
