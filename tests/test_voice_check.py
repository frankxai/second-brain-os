"""Tests for voice_check — AI-slop phrase detection in summaries."""

from __future__ import annotations

from sbo_ingestion.voice_check import _load_banned_phrases, find_slop_phrases, score_voice


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
    score = score_voice(
        "Let's delve into the topic. Dive into the details. Certainly worth noting."
    )
    assert 0.0 <= score < 1.0


def test_curly_apostrophe_detected() -> None:
    text = "It\u2019s worth noting that this works."
    hits = find_slop_phrases(text)
    assert hits == ("it's worth noting",)


def test_banned_phrases_file_with_curly_and_indented_comment(tmp_path, monkeypatch) -> None:
    phrases_file = tmp_path / "banned.txt"
    phrases_file.write_text("   # Indented comment\n  don\u2019t do this  \n", encoding="utf-8")
    monkeypatch.setenv("SBO_BANNED_PHRASES_FILE", str(phrases_file))

    hits = find_slop_phrases("Please don't do this here.")
    assert hits == ("don't do this",)


def test_left_single_quote_detected() -> None:
    text = "It\u2018s worth noting that this works."
    hits = find_slop_phrases(text)
    assert hits == ("it's worth noting",)


def test_indented_comment_is_not_loaded_as_a_phrase(tmp_path, monkeypatch) -> None:
    phrases_file = tmp_path / "banned.txt"
    phrases_file.write_text("   # banned comment phrase\nreal phrase\n", encoding="utf-8")
    monkeypatch.setenv("SBO_BANNED_PHRASES_FILE", str(phrases_file))

    assert _load_banned_phrases() == ("real phrase",)
