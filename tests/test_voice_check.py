"""Tests for voice_check — AI-slop phrase detection in summaries."""

from __future__ import annotations

from sbo_ingestion.voice_check import find_slop_phrases, score_voice


def test_finds_banned_phrases() -> None:
    text = "Let's delve into the architecture and dive into the details."
    hits = find_slop_phrases(text)
    assert "delve into" in hits
    assert "dive into" in hits


def test_returns_empty_for_clean_text() -> None:
    text = "The architecture has two vaults with hard separation."
    hits = find_slop_phrases(text)
    assert hits == ()


def test_case_insensitive() -> None:
    text = "It's Worth Noting that DELVE into patterns is wrong."
    hits = find_slop_phrases(text)
    assert "it's worth noting" in hits
    assert "delve into" in hits


def test_score_clean() -> None:
    score = score_voice("Direct, technical, warm. Pattern recognition as poetry.")
    assert score == 1.0


def test_score_degraded_for_slop() -> None:
    score = score_voice("Let's delve into the topic. Dive into the details. Certainly worth noting.")
    assert 0.0 <= score < 1.0
