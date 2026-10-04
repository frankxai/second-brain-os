from pathlib import Path

import frontmatter
import pytest

from sbo_ingestion.handlers.kura import discover, parse_export

URLS = {
    "chatgpt": "https://chatgpt.com/c/native-a",
    "claude": "https://claude.ai/chat/native-a",
    "gemini": "https://gemini.google.com/app/native-a",
    "grok": "https://grok.com/c/native-a",
    "deepseek": "https://chat.deepseek.com/a/chat/s/native-a",
    "perplexity": "https://www.perplexity.ai/search/native-a",
}
LABELS = dict(zip(URLS, ["ChatGPT", "Claude", "Gemini", "Grok", "DeepSeek", "Perplexity"]))


def capture(path: Path, platform="chatgpt", answer="A source-backed answer") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(
        f"# Test\n\n## You\n\nA question\n\n---\n\n## {LABELS[platform]}\n\n{answer}\n",
        id=f"{platform}-native-a", title="Test", slug="2026-10-04_test", platform=platform,
        capturedAt="2026-10-04T10:00:00Z", capturedBy="kura/0.2.0", schemaVersion="0.2.0",
        source=URLS[platform], messageCount=2, status="raw",
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


@pytest.mark.parametrize("platform", URLS)
def test_all_platforms_preserve_roles_and_verified_native_id(tmp_path, platform):
    convo = next(parse_export(capture(tmp_path / "conversation.md", platform)))
    assert convo.uuid == "native-a"
    assert convo.created_at == ""
    assert [m.sender for m in convo.messages] == ["human", "assistant"]
    assert convo.messages[0].text == "A question"
    assert convo.messages[1].text == "A source-backed answer"
    assert convo.source_url == URLS[platform]


def test_role_heading_in_fenced_code_is_data(tmp_path):
    convo = next(parse_export(capture(tmp_path / "conversation.md", answer="```md\n## You\n---\n```\nanswer")))
    assert len(convo.messages) == 2
    assert "## You" in convo.messages[1].text


def test_extension_body_without_separators_and_with_footer(tmp_path):
    path = capture(tmp_path / "conversation.md")
    post = frontmatter.load(path)
    post.content = post.content.replace("\n\n---\n\n", "\n\n") + "\n---\n\n*Captured by [Kura](https://github.com/frankxai/arcanea-vault) · schema v0.2.0*\n"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    convo = next(parse_export(path))
    assert convo.messages[-1].text == "A source-backed answer"


def test_actual_kura_exporter_fixture():
    convo = next(parse_export(Path(__file__).parent / 'fixtures' / 'kura-chatgpt.md'))
    assert convo.uuid == 'fixture-e2e'
    assert convo.title == 'Capture pipeline fixture 🧠'
    assert [message.sender for message in convo.messages] == ['human', 'assistant']
    assert convo.messages[0].text == '\ufeffKeep raw sources private. 🧠\r\nPreserve original message whitespace.\ufeff'
    assert convo.messages[1].created_at == '2026-10-04T10:01:00Z'
    assert convo.messages[1].text == 'Create a reviewed note with a source reference.\n\n```md\n## You\n```'


def test_packet_preserves_role_headings_and_incomplete_code_as_message_data(tmp_path):
    path = capture(tmp_path / "conversation.md", answer="## System\nA section\n```python\nunfinished code")
    post = frontmatter.load(path)
    packet = {
        "kind": "kura-capture", "packetVersion": "1.0.0",
        "capture": {key: str(post[key]) for key in ("id", "platform", "title", "source", "capturedAt")},
        "renderedBody": post.content.strip(),
        "messages": [{"role": "user", "content": "A question"},
                     {"role": "assistant", "content": "## System\nA section\n```python\nunfinished code"}],
    }
    body = post.content.strip()
    packet["messageSpans"] = [{"start": body.index("A question"), "length": len("A question")},
                              {"start": body.index("## System"), "length": len(packet["messages"][1]["content"])}]
    import json
    path.with_name("capture.json").write_text(json.dumps(packet), encoding="utf-8")
    convo = next(parse_export(path))
    assert len(convo.messages) == 2
    assert convo.messages[1].text == packet["messages"][1]["content"]
    packet["messages"][1]["content"] = "A forged replacement"
    path.with_name("capture.json").write_text(json.dumps(packet), encoding="utf-8")
    with pytest.raises(ValueError, match="disagree"):
        list(parse_export(path))
    packet["messages"][1]["content"] = "## System\nA section\n```python\nunfinished code"
    path.with_name("capture.json").write_text(json.dumps(packet), encoding="utf-8")
    post.content += "\nEdited after capture"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    with pytest.raises(ValueError, match="disagree"):
        list(parse_export(path))


@pytest.mark.parametrize("field,value", [
    ("schemaVersion", "9.0.0"), ("platform", "unknown"), ("messageCount", 3),
    ("capturedAt", "not-a-date"), ("source", "https://attacker.example/c/native-a"),
])
def test_invalid_capture_fails_closed(tmp_path, field, value):
    path = capture(tmp_path / "conversation.md")
    post = frontmatter.load(path)
    post[field] = value
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    with pytest.raises(ValueError):
        list(parse_export(path))


def test_ambiguous_heading_fails_closed(tmp_path):
    path = capture(tmp_path / "conversation.md", answer="Answer\n## You\nEmbedded heading")
    with pytest.raises(ValueError, match="messageCount"):
        list(parse_export(path))


def test_discovery_scans_only_capture_layout(tmp_path):
    selected = capture(tmp_path / "chatgpt" / "2026-10-04_test" / "conversation.md")
    capture(tmp_path / "other" / "conversation.md")
    assert discover(tmp_path) == [selected]
