"""Tests for the image ingestion handler.

These tests mock the Anthropic API client so no real API calls are made.
Image encoding is tested with a real (tiny) PNG constructed in-memory.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sbo_ingestion.handlers.image import (
    ImageCapture,
    _encode_image,
    _parse_response,
    analyze_image,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tiny_png(tmp_path: Path) -> Path:
    """Write a minimal 1x1 white PNG to tmp_path."""
    png_bytes = bytes(
        [
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
            0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
            0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
            0x44, 0xAE, 0x42, 0x60, 0x82,
        ]
    )
    p = tmp_path / "test.png"
    p.write_bytes(png_bytes)
    return p


@pytest.fixture()
def valid_response() -> str:
    return json.dumps(
        {
            "content_type": "handwritten_note",
            "title": "Meeting ideas",
            "body_md": "- Build image pipeline\n- Test with 10 notebooks",
            "tags": ["ideas", "planning"],
            "people": ["Frank"],
            "projects": ["second-brain"],
            "date_visible": "2026-05-14",
            "confidence": 0.92,
        }
    )


# ---------------------------------------------------------------------------
# _encode_image
# ---------------------------------------------------------------------------


def test_encode_image_returns_base64_and_media_type(tiny_png: Path) -> None:
    b64, media_type = _encode_image(tiny_png)
    assert media_type == "image/png"
    assert len(b64) > 0
    # base64-encoded data should be decodable
    import base64

    raw = base64.b64decode(b64)
    assert raw[:4] == b"\x89PNG"


def test_encode_image_jpeg_media_type(tmp_path: Path) -> None:
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)
    _, media_type = _encode_image(p)
    assert media_type == "image/jpeg"


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------


def test_parse_valid_json(valid_response: str, tiny_png: Path) -> None:
    capture = _parse_response(valid_response, tiny_png)
    assert capture.content_type == "handwritten_note"
    assert capture.title == "Meeting ideas"
    assert "ideas" in capture.tags
    assert "Frank" in capture.people
    assert capture.confidence == pytest.approx(0.92)


def test_parse_json_embedded_in_prose(tiny_png: Path) -> None:
    """Should extract JSON even if Claude wraps it in prose."""
    wrapped = 'Here is the analysis:\n{"content_type": "sketch", "title": "Diagram", "body_md": "A box", "tags": [], "people": [], "projects": [], "date_visible": "", "confidence": 0.7}\nDone.'
    capture = _parse_response(wrapped, tiny_png)
    assert capture.content_type == "sketch"
    assert capture.title == "Diagram"


def test_parse_invalid_json_falls_back_gracefully(tiny_png: Path) -> None:
    capture = _parse_response("not json at all", tiny_png)
    assert capture.content_type == "mixed"
    assert capture.source_path == tiny_png
    assert capture.confidence == 0.5


def test_parse_missing_fields_use_defaults(tiny_png: Path) -> None:
    capture = _parse_response('{"content_type": "table"}', tiny_png)
    assert capture.content_type == "table"
    assert capture.title == tiny_png.stem
    assert capture.tags == ()
    assert capture.people == ()


# ---------------------------------------------------------------------------
# analyze_image (mocked API)
# ---------------------------------------------------------------------------


def test_analyze_image_calls_api_and_returns_capture(
    tiny_png: Path, valid_response: str
) -> None:
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=valid_response)]

    with patch("sbo_ingestion.handlers.image.anthropic.Anthropic") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.messages.create.return_value = mock_message

        capture = analyze_image(tiny_png, api_key="test-key")

    assert isinstance(capture, ImageCapture)
    assert capture.content_type == "handwritten_note"
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-haiku-4-5-20251001"
    # Image block should be in the message
    content = call_kwargs["messages"][0]["content"]
    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["media_type"] == "image/png"


def test_analyze_image_uses_custom_model(tiny_png: Path) -> None:
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="{}")]

    with patch("sbo_ingestion.handlers.image.anthropic.Anthropic") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.messages.create.return_value = mock_message

        analyze_image(tiny_png, api_key="key", model="claude-opus-4-6")

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-6"
