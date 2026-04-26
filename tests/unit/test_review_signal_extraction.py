"""Tests for lightweight review-signal extraction."""

from __future__ import annotations

from gtrdashboard.review_signals import infer_signals_from_message


def test_infer_signals_from_user_requirements_and_concerns() -> None:
    signals = infer_signals_from_message(
        "这个项目太工程化，普通观众可能看不懂。我更想要可以演示的 60 秒视频钩子。"
    )

    assert [signal.label for signal in signals] == [
        "担心太工程化",
        "重视普通观众理解",
        "偏好可演示项目",
        "需要 60 秒视频钩子",
    ]
    assert signals[0].polarity == "negative"
    assert signals[2].polarity == "positive"
