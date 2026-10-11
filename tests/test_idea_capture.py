"""Tests for idea capture ingestion handler, dual write, receipts, and privacy guarantees."""

from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest
from click.testing import CliRunner

from sbo_ingestion.handlers import idea_capture
from sbo_ingestion.ingest import cli, ingest

ACTUAL_FIXTURE_BYTES = (
    b'{"version":1,"rawText":"  Synthetic caf\xc3\xa9 \xe2\x8f\x80 \xf0\x9f\xa7\xa0\\r\\n  ",'
    b'"tags":"  first\\r\\nsecond, duplicate, duplicate  ",'
    b'"source":"PRIVATE_SOURCE_SENTINEL","sourceRef":"PRIVATE_LOCATOR_SENTINEL"}'
)


@pytest.fixture
def idea_fixture_file(tmp_path: Path) -> Path:
    f = tmp_path / "actual_idea_capture.json"
    f.write_bytes(ACTUAL_FIXTURE_BYTES)
    return f


def test_actual_packet_api_and_cli(tmp_path: Path, idea_fixture_file: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    # API test
    results = ingest(
        idea_fixture_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )

    assert len(results) == 1
    res = results[0]
    assert res.private_path.exists()
    assert res.brain_path.exists()
    assert not res.brain_preserved

    raw_bytes = res.private_path.read_bytes()
    assert raw_bytes == ACTUAL_FIXTURE_BYTES

    brain_text = res.brain_path.read_text(encoding="utf-8")
    assert "status: needs-summary" in brain_text
    assert "Captured Idea" in brain_text

    index_file = brain_root / "_inbox" / "idea-capture" / "_INDEX.md"
    assert index_file.exists()
    index_text = index_file.read_text(encoding="utf-8")

    # Assert no private sentinels leak to brain or index
    for sentinel in [
        "PRIVATE_SOURCE_SENTINEL",
        "PRIVATE_LOCATOR_SENTINEL",
        "Synthetic café",
        "first\r\nsecond",
    ]:
        assert sentinel not in brain_text
        assert sentinel not in index_text

    # CLI test with new roots
    brain_root2 = tmp_path / "brain2"
    private_root2 = tmp_path / "private2"
    brain_root2.mkdir()
    private_root2.mkdir()

    runner = CliRunner()
    cli_res = runner.invoke(
        cli,
        [
            str(idea_fixture_file),
            "--brain-root",
            str(brain_root2),
            "--private-root",
            str(private_root2),
            "--format",
            "idea-capture",
            "--mode",
            "agent",
        ],
    )
    assert cli_res.exit_code == 0
    assert "wrote 1 conversation pairs" in cli_res.output
    assert "PRIVATE_SOURCE_SENTINEL" not in cli_res.output


def test_string_tags_bom_crlf_fidelity(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    bom_bytes = b"\xef\xbb\xbf" + ACTUAL_FIXTURE_BYTES
    bom_file = tmp_path / "bom_capture.json"
    bom_file.write_bytes(bom_bytes)

    results = ingest(
        bom_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )
    assert len(results) == 1
    assert results[0].private_path.read_bytes() == bom_bytes

    # LIST tags rejected before writes
    list_tags_file = tmp_path / "list_tags.json"
    list_tags_data = {
        "version": 1,
        "rawText": "valid text",
        "tags": ["tag1", "tag2"],
        "source": "valid_source",
        "sourceRef": None,
    }
    list_tags_file.write_text(json.dumps(list_tags_data), encoding="utf-8")

    brain_before = list(brain_root.rglob("*"))
    private_before = list(private_root.rglob("*"))

    with pytest.raises(ValueError, match="Invalid tags"):
        ingest(
            list_tags_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )

    assert list(brain_root.rglob("*")) == brain_before
    assert list(private_root.rglob("*")) == private_before


def test_semantic_identity_and_byte_variants(tmp_path: Path, idea_fixture_file: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    # Initial ingest
    res1 = ingest(
        idea_fixture_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )[0]

    # Re-ingest reordered JSON keys / variant
    reordered_bytes = (
        b'{"tags":"  first\\r\\nsecond, duplicate, duplicate  ",'
        b'"source":"PRIVATE_SOURCE_SENTINEL",'
        b'"sourceRef":"PRIVATE_LOCATOR_SENTINEL",'
        b'"version":1,'
        b'"rawText":"  Synthetic caf\xc3\xa9 \xe2\x8f\x80 \xf0\x9f\xa7\xa0\\r\\n  "}'
    )
    var_file = tmp_path / "variant_capture.json"
    var_file.write_bytes(reordered_bytes)

    res2 = ingest(
        var_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )[0]

    assert res2.brain_preserved
    assert res2.brain_path == res1.brain_path

    # Verify variant stored in private/_distill/idea-capture/variants/
    variants_dir = private_root / "_distill" / "idea-capture" / "variants"
    assert variants_dir.exists()
    var_files = list(variants_dir.rglob("*.json"))
    assert len(var_files) == 1
    assert var_files[0].read_bytes() == reordered_bytes


def test_reviewed_brain_note_preservation(tmp_path: Path, idea_fixture_file: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    res1 = ingest(
        idea_fixture_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )[0]

    # Modify brain note (human review)
    res1.brain_path.write_text("--- \nstatus: reviewed\n---\nReviewed content", encoding="utf-8")

    res2 = ingest(
        idea_fixture_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )[0]

    assert res2.brain_preserved
    assert "Reviewed content" in res2.brain_path.read_text(encoding="utf-8")


def test_corrupt_receipt_fails_safely(tmp_path: Path, idea_fixture_file: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    ingest(
        idea_fixture_file,
        brain_root=brain_root,
        private_root=private_root,
        format="idea-capture",
        mode="agent",
    )

    receipt_dir = private_root / "_distill" / "idea-capture"
    receipt_files = list(receipt_dir.glob("*.json"))
    assert len(receipt_files) == 1
    receipt_files[0].write_text("{corrupt json", encoding="utf-8")

    with pytest.raises(ValueError, match="Corrupt idea capture receipt"):
        ingest(
            idea_fixture_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )


def test_path_and_symlink_denial(tmp_path: Path, idea_fixture_file: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    symlink_file = tmp_path / "symlink_capture.json"
    try:
        symlink_file.symlink_to(idea_fixture_file)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable; denial behavior not verified here")
        raise

    with pytest.raises(ValueError, match="symlink"):
        ingest(
            symlink_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )


def test_malformed_oversize_surrogate_rejection(tmp_path: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    # Oversize (> 8MiB)
    big_file = tmp_path / "oversize.json"
    big_file.write_bytes(b"x" * (8 * 1024 * 1024 + 10))

    with pytest.raises(ValueError, match="8MiB"):
        ingest(
            big_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )

    # Duplicate keys in JSON
    dup_file = tmp_path / "dup_keys.json"
    dup_file.write_bytes(
        b'{"version":1,"version":1,"rawText":"a","tags":"t","source":"s","sourceRef":null}'
    )

    with pytest.raises(ValueError, match="Duplicate keys"):
        ingest(
            dup_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )

    # Surrogates in UTF-8
    surrogate_file = tmp_path / "surrogate.json"
    surrogate_file.write_bytes(
        b'{"version":1,"rawText":"\xed\xa0\x80","tags":"t","source":"s","sourceRef":null}'
    )

    with pytest.raises(ValueError):
        ingest(
            surrogate_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )

    # Invalid version (boolean True)
    bool_ver_file = tmp_path / "bool_ver.json"
    bool_ver_file.write_bytes(
        b'{"version":true,"rawText":"a","tags":"t","source":"s","sourceRef":null}'
    )

    with pytest.raises(ValueError, match="Invalid version"):
        ingest(
            bool_ver_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="agent",
        )


def test_agent_mode_enforced(tmp_path: Path, idea_fixture_file: Path) -> None:
    brain_root = tmp_path / "brain"
    private_root = tmp_path / "private"
    brain_root.mkdir()
    private_root.mkdir()

    with pytest.raises(ValueError, match="requires agent mode"):
        ingest(
            idea_fixture_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="api",
            api_key="test-key",
        )

    with pytest.raises(ValueError, match="requires agent mode"):
        ingest(
            idea_fixture_file,
            brain_root=brain_root,
            private_root=private_root,
            format="idea-capture",
            mode="dry-run",
        )


def test_corpus_index_keeps_each_selected_capture(tmp_path: Path) -> None:
    brain = tmp_path / "brain"
    private = tmp_path / "private"
    for number in range(3):
        packet = json.loads(ACTUAL_FIXTURE_BYTES)
        packet["rawText"] += f" distinct-{number}"
        export = tmp_path / f"capture-{number}.json"
        export.write_text(json.dumps(packet), encoding="utf-8")
        ingest(export, brain_root=brain, private_root=private, format="idea-capture", mode="agent")
        index = frontmatter.load(brain / "_inbox" / "idea-capture" / "_INDEX.md")
        assert index["conversation_count"] == number + 1
        assert "PRIVATE_SOURCE_SENTINEL" not in index.content


def test_interrupted_retry_preserves_conflicting_private_bytes(
    tmp_path: Path, idea_fixture_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sbo_ingestion.ingest as implementation

    brain, private = tmp_path / "brain", tmp_path / "private"
    writer = implementation._atomic_write_text

    def interrupted(path: Path, *args: object, **kwargs: object) -> None:
        if path.is_relative_to(brain):
            raise OSError("Synthetic interrupted brain write")
        writer(path, *args, **kwargs)

    with monkeypatch.context() as failure:
        failure.setattr(implementation, "_atomic_write_text", interrupted)
        with pytest.raises(OSError, match="interrupted"):
            ingest(
                idea_fixture_file,
                brain_root=brain,
                private_root=private,
                format="idea-capture",
                mode="agent",
            )
    raw = next((private / "chat-history").rglob("*.json"))
    conflicting = b"OTHER_WRITER_SENTINEL"
    raw.write_bytes(conflicting)
    with pytest.raises(FileExistsError, match="Conflicting"):
        ingest(
            idea_fixture_file,
            brain_root=brain,
            private_root=private,
            format="idea-capture",
            mode="agent",
        )
    assert raw.read_bytes() == conflicting


@pytest.mark.parametrize("variants", [[], None, {"not-a-digest": "elsewhere"}, {"a" * 64: None}])
def test_malformed_receipt_variants_refuse_cleanly(
    tmp_path: Path, idea_fixture_file: Path, variants: object
) -> None:
    brain, private = tmp_path / "brain", tmp_path / "private"
    ingest(
        idea_fixture_file,
        brain_root=brain,
        private_root=private,
        format="idea-capture",
        mode="agent",
    )
    receipt = next((private / "_distill" / "idea-capture").glob("*.json"))
    record = json.loads(receipt.read_text())
    record["variants"] = variants
    receipt.write_text(json.dumps(record))
    unchanged = receipt.read_bytes()
    with pytest.raises(ValueError, match="Corrupt idea capture receipt fields"):
        ingest(
            idea_fixture_file,
            brain_root=brain,
            private_root=private,
            format="idea-capture",
            mode="agent",
        )
    assert receipt.read_bytes() == unchanged


@pytest.mark.parametrize("field", ["rawText", "tags", "source", "sourceRef"])
def test_escaped_surrogate_fields_refuse_before_writes(tmp_path: Path, field: str) -> None:
    packet = json.loads(ACTUAL_FIXTURE_BYTES)
    packet[field] = "\ud800"
    export = tmp_path / "invalid.json"
    export.write_text(json.dumps(packet, ensure_ascii=True), encoding="utf-8")
    with pytest.raises(ValueError, match="Surrogate"):
        idea_capture.read_and_validate_packet(export)
    brain, private = tmp_path / "brain", tmp_path / "private"
    with pytest.raises(ValueError, match="Surrogate"):
        ingest(export, brain_root=brain, private_root=private, format="idea-capture", mode="agent")
    assert not brain.exists() and not private.exists()


def test_capture_actor_is_unverified(idea_fixture_file: Path) -> None:
    packet, _ = idea_capture.read_and_validate_packet(idea_fixture_file)
    conversation = idea_capture.create_idea_conversation(
        packet, idea_capture.compute_semantic_identity(packet)
    )
    assert conversation.messages[0].sender == "captured-unverified"


@pytest.mark.parametrize("target", ["raw", "receipt", "variant"])
def test_oversized_persisted_capture_refuses_before_read(
    tmp_path: Path, idea_fixture_file: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    brain, private = tmp_path / "brain", tmp_path / "private"
    ingest(idea_fixture_file, brain_root=brain, private_root=private, format="idea-capture")
    receipt = next((private / "_distill" / "idea-capture").glob("*.json"))
    record = json.loads(receipt.read_text())
    if target == "receipt":
        oversized = receipt
    elif target == "raw":
        oversized = private / record["original_raw_path"]
    else:
        variant = tmp_path / "variant.json"
        packet = json.loads(ACTUAL_FIXTURE_BYTES)
        variant.write_text(json.dumps(packet, indent=4), encoding="utf-8")
        ingest(variant, brain_root=brain, private_root=private, format="idea-capture")
        record = json.loads(receipt.read_text())
        oversized = private / next(iter(record["variants"].values()))
    with oversized.open("r+b") as handle:
        handle.truncate(idea_capture.MAX_IDEA_CAPTURE_SIZE + 1)
    prior_size = oversized.stat().st_size
    opener = Path.open

    def forbid_oversized_read(path: Path, mode: str = "r", *args: object, **kwargs: object):
        if path == oversized and "r" in mode:
            raise AssertionError("Oversized persisted capture was opened for reading")
        return opener(path, mode, *args, **kwargs)

    with monkeypatch.context() as gate:
        gate.setattr(Path, "open", forbid_oversized_read)
        with pytest.raises(ValueError, match="size limit"):
            ingest(idea_fixture_file, brain_root=brain, private_root=private, format="idea-capture")
    assert oversized.stat().st_size == prior_size


def test_changed_import_date_cannot_leak_text_into_index(
    tmp_path: Path, idea_fixture_file: Path
) -> None:
    brain, private = tmp_path / "brain", tmp_path / "private"
    result = ingest(
        idea_fixture_file, brain_root=brain, private_root=private, format="idea-capture"
    )[0]
    post = frontmatter.load(result.brain_path)
    post["imported"] = "2026-10-11T12:00:00 PRIVATE_DATE_SENTINEL"
    result.brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    prior = result.brain_path.read_bytes()
    ingest(idea_fixture_file, brain_root=brain, private_root=private, format="idea-capture")
    index = brain / "_inbox" / "idea-capture" / "_INDEX.md"
    assert "PRIVATE_DATE_SENTINEL" not in index.read_text(encoding="utf-8")
    assert result.brain_path.read_bytes() == prior


@pytest.mark.parametrize("surface", ["brain-note", "receipt-lock"])
def test_capture_refuses_link_before_read_or_lock(
    tmp_path: Path, idea_fixture_file: Path, monkeypatch: pytest.MonkeyPatch, surface: str
) -> None:
    brain, private = tmp_path / "brain", tmp_path / "private"
    brain.mkdir()
    private.mkdir()
    target = private / "retained-source.md"
    target.write_bytes(b"PRIVATE_LINK_SENTINEL")
    if surface == "brain-note":
        link = brain / "linked.md"
    else:
        packet, _ = idea_capture.read_and_validate_packet(idea_fixture_file)
        identity = idea_capture.compute_semantic_identity(packet)[:16]
        link = private / "_distill" / "idea-capture" / f"idea-{identity}.lock"
        link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable")
        raise
    opener = Path.open

    def forbidden(path: Path, *args: object, **kwargs: object):
        if path == link:
            raise AssertionError("Capture opened a symbolic link")
        return opener(path, *args, **kwargs)

    with monkeypatch.context() as gate:
        gate.setattr(Path, "open", forbidden)
        with pytest.raises(ValueError, match="symlink"):
            ingest(idea_fixture_file, brain_root=brain, private_root=private, format="idea-capture")
    assert target.read_bytes() == b"PRIVATE_LINK_SENTINEL"
