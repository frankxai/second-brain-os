"""Artifact index over synthetic exports: no account data, no provider calls."""

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest
from click.testing import CliRunner

from sbo_ingestion import chatgpt_artifacts
from sbo_ingestion.handlers.chatgpt import parse_export
from sbo_ingestion.ingest import ingest

PNG = b"\x89PNG\r\n\x1a\n" + b"synthetic sketch pixels"
WEBP = b"RIFF\x10\x00\x00\x00WEBP" + b"synthetic generated pixels"
PLOT = b"\x89PNG\r\n\x1a\n" + b"synthetic plot pixels"
PDF = b"%PDF-1.7 synthetic document"
PLACEHOLDER = "<<synthetic-secret-prompt>>"


def node(key, parent, children, role, content, metadata=None):
    return {
        "id": key,
        "parent": parent,
        "children": children,
        "message": {
            "id": "message-" + key,
            "author": {"role": role},
            "create_time": 1,
            "content": content,
            "metadata": metadata or {},
        },
    }


def image_part(pointer, **extra):
    return {"content_type": "image_asset_pointer", "asset_pointer": pointer, **extra}


def conversation():
    mapping = {
        "root": {"id": "root", "parent": None, "children": ["u1", "u2"], "message": None},
        # Abandoned branch: its upload must be indexed and marked as not selected.
        "u1": node(
            "u1",
            "root",
            [],
            "user",
            {"content_type": "multimodal_text", "parts": [image_part("sediment://file_0abandoned")]},
        ),
        "u2": node(
            "u2",
            "root",
            ["a1"],
            "user",
            {
                "content_type": "multimodal_text",
                "parts": [
                    image_part("sediment://file_00aa11", size_bytes=len(PNG), width=4, height=3),
                    "restyle this sketch",
                ],
            },
            {
                "attachments": [
                    {"id": "file_00aa11", "name": "sketch.png", "mime_type": "image/png"},
                    {"id": "file-Doc55", "name": "brief.pdf", "size": len(PDF)},
                ]
            },
        ),
        "a1": node(
            "a1",
            "u2",
            ["t1"],
            "assistant",
            {
                "content_type": "multimodal_text",
                "parts": [
                    image_part(
                        "file-service://file-Bb22",
                        metadata={"dalle": {"prompt": PLACEHOLDER, "seed": 7}},
                    ),
                    image_part("file-service://file-Missing33"),
                ],
            },
        ),
        "t1": node(
            "t1",
            "a1",
            [],
            "tool",
            {"content_type": "execution_output", "text": "<<ImageDisplayed>>"},
            {
                "aggregate_result": {
                    "messages": [
                        {"message_type": "image", "image_url": "file-service://file-Plot44"}
                    ]
                }
            },
        ),
    }
    return {
        "id": "synthetic-visual",
        "title": "Synthetic visuals",
        "create_time": 1,
        "current_node": "t1",
        "mapping": mapping,
    }


def text_only():
    mapping = {
        "root": {"id": "root", "parent": None, "children": ["u"], "message": None},
        "u": node("u", "root", [], "user", {"content_type": "text", "parts": ["plain question"]}),
    }
    return {"id": "synthetic-text", "title": "Text", "current_node": "u", "mapping": mapping}


def write_zip(path, conversations, members):
    with ZipFile(path, "w", ZIP_STORED) as archive:
        archive.writestr("conversations.json", json.dumps(conversations))
        for name, data in members.items():
            archive.writestr(name, data)
    return path


MEMBERS = {
    "file_00aa11.dat": PNG,
    "dalle-generations/file-Bb22-0000.webp": WEBP,
    "file-Plot44-plot.png": PLOT,
    "file-Doc55-brief.pdf": PDF,
    "file-Orphan66-unused.png": PNG,
    "conversation_asset_file_names.json": json.dumps({"file_00aa11.dat": "uploads/sketch.png"}),
}


@pytest.fixture
def visual_zip(tmp_path):
    return write_zip(tmp_path / "export.zip", [conversation(), text_only()], MEMBERS)


def run(source, tmp_path):
    return ingest(
        source,
        brain_root=tmp_path / "brain",
        private_root=tmp_path / "private",
        account_scope="synthetic",
    )


def manifests(tmp_path):
    return [
        json.loads(p.read_bytes())
        for p in sorted((tmp_path / "private/_distill/chatgpt/artifacts").rglob("*.json"))
    ]


def assets_by_id(manifest):
    return {asset["asset_id"]: asset for asset in manifest["assets"]}


def tree_bytes(root):
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


def test_manifest_hashes_shipped_files_and_names_missing_ones(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    (manifest,) = manifests(tmp_path)
    assert manifest["schema_version"] == "sbo.chatgpt-artifacts.v1"
    assert manifest["export_sha256"] == sha256(visual_zip.read_bytes()).hexdigest()
    assert manifest["export_snapshot"] == (
        f"_distill/chatgpt/exports/{manifest['export_sha256']}/original.zip"
    )
    assets = assets_by_id(manifest)
    upload = assets["file_00aa11"]["original"]
    assert upload == {
        "status": "in-export",
        "member": "file_00aa11.dat",
        "sha256": sha256(PNG).hexdigest(),
        "size_bytes": len(PNG),
        "sniffed_media_type": "image/png",
        "original_name": "sketch.png",
    }
    generated = assets["file-Bb22"]["original"]
    assert generated["member"] == "dalle-generations/file-Bb22-0000.webp"
    assert generated["sha256"] == sha256(WEBP).hexdigest()
    assert generated["sniffed_media_type"] == "image/webp"
    assert assets["file-Plot44"]["kinds"] == ["tool-output"]
    assert assets["file-Doc55"]["original"]["sniffed_media_type"] == "application/pdf"
    assert assets["file-Missing33"]["original"] == {"status": "missing-from-export"}
    assert manifest["counts"]["in-export"] == 4
    assert manifest["counts"]["missing-from-export"] == 2
    assert manifest["counts"]["assets"] == 6


def test_one_file_keeps_every_reference_and_branch_state(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    assets = assets_by_id(manifests(tmp_path)[0])
    upload = assets["file_00aa11"]
    assert upload["kinds"] == ["attachment", "image"]
    assert [r["reference"] for r in upload["references"]] == [
        "#/original/mapping/u2/message/content/parts/0/asset_pointer",
        "#/original/mapping/u2/message/metadata/attachments/0",
    ]
    assert upload["references"][0]["declared"] == {
        "size_bytes": len(PNG),
        "width": 4,
        "height": 3,
    }
    assert all(r["on_selected_branch"] for r in upload["references"])
    abandoned = assets["file_0abandoned"]["references"][0]
    assert abandoned["on_selected_branch"] is False
    assert abandoned["node_id"] == "u1"


def test_references_resolve_inside_the_preserved_source_envelope(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    manifest = manifests(tmp_path)[0]
    envelopes = [
        json.loads(p.read_bytes())
        for p in (tmp_path / "private/_distill/chatgpt/sources").rglob("*.json")
    ]
    (envelope,) = [e for e in envelopes if e["stable_id"] == manifest["stable_id"]]
    assert envelope["content_sha256"] == manifest["source_content_sha256"]
    for asset in manifest["assets"]:
        for reference in asset["references"]:
            value = envelope
            for token in reference["reference"][2:].split("/"):
                token = token.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, list) else value[token]
            located = value if isinstance(value, str) else value["id"]
            assert located in asset["pointers"]


def test_generation_prompt_stays_in_the_source_and_capture_is_not_approval(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    path = next((tmp_path / "private/_distill/chatgpt/artifacts").rglob("*.json"))
    text = path.read_text(encoding="utf-8")
    assert PLACEHOLDER not in text
    assert sha256(path.read_bytes()).hexdigest() == path.stem
    manifest = json.loads(text)
    generated = assets_by_id(manifest)["file-Bb22"]
    assert generated["references"][0]["declared"] == {"has_generation_metadata": True}
    assert all(
        asset["governance"] == {"status": "captured", "approved_for_reuse": False}
        for asset in manifest["assets"]
    )
    assert "rendered screenshots" in manifest["not_captured"]


def test_nothing_is_extracted_and_nothing_reaches_the_brain_vault(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    private = tree_bytes(tmp_path / "private")
    for name, data in private.items():
        if not name.endswith("original.zip"):
            assert PNG not in data and WEBP not in data and PDF not in data
    brain = b"".join(tree_bytes(tmp_path / "brain").values())
    for marker in (b"file_00aa11", b"file-Bb22", b"sbo.chatgpt-artifacts", b"asset_pointer"):
        assert marker not in brain
    assert not list((tmp_path / "brain").rglob("*artifact*"))


def test_receipt_reports_coverage_without_claiming_completeness(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    (receipt,) = chatgpt_artifacts.load_receipts(tmp_path / "private")
    assert receipt["schema_version"] == "sbo.chatgpt-artifact-receipt.v1"
    assert receipt["conversations_scanned"] == 2
    assert receipt["conversations_with_artifacts"] == 1
    assert receipt["counts"]["assets"] == 6
    assert receipt["counts"]["in-export"] == 4
    assert receipt["counts"]["missing-from-export"] == 2
    assert receipt["asset_ids_in_export"] == 5
    assert receipt["asset_ids_never_referenced"] == 1
    assert receipt["unknown"]
    record = receipt["records"][0]
    manifest = tmp_path / "private" / record["manifest"]
    assert sha256(manifest.read_bytes()).hexdigest() == record["manifest_sha256"]
    imported = json.loads(
        next((tmp_path / "private/_distill/chatgpt/imports").rglob("*.json")).read_bytes()
    )
    assert imported["schema_version"] == "sbo.chatgpt-import.v1"
    assert all("manifest" not in row and "counts" not in row for row in imported["records"])


def test_identical_replay_writes_no_new_bytes(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    before = tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain")
    assert run(visual_zip, tmp_path)[0].source_unchanged
    assert before == (tree_bytes(tmp_path / "private"), tree_bytes(tmp_path / "brain"))


def test_later_export_that_ships_a_missing_file_adds_a_manifest(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    fuller = write_zip(
        tmp_path / "later.zip",
        [conversation(), text_only()],
        {**MEMBERS, "file-Missing33-recovered.png": PLOT},
    )
    assert run(fuller, tmp_path)[0].source_unchanged
    first, second = sorted(manifests(tmp_path), key=lambda m: m["counts"]["in-export"])
    assert first["source_content_sha256"] == second["source_content_sha256"]
    assert first["export_sha256"] != second["export_sha256"]
    assert assets_by_id(first)["file-Missing33"]["original"]["status"] == "missing-from-export"
    assert assets_by_id(second)["file-Missing33"]["original"]["sha256"] == sha256(PLOT).hexdigest()
    assert len(chatgpt_artifacts.load_receipts(tmp_path / "private")) == 2


def test_conflicting_members_for_one_id_are_never_selected(tmp_path):
    source = write_zip(
        tmp_path / "export.zip",
        [conversation()],
        {**MEMBERS, "user-synthetic/file_00aa11-copy.png": PLOT},
    )
    original = assets_by_id(next(parse_and_build(source, tmp_path)))["file_00aa11"]["original"]
    assert original["status"] == "ambiguous"
    assert "sha256" not in original and "member" not in original
    assert {c["sha256"] for c in original["candidates"]} == {
        sha256(PNG).hexdigest(),
        sha256(PLOT).hexdigest(),
    }


def test_identical_duplicate_members_resolve_to_one_file(tmp_path):
    source = write_zip(
        tmp_path / "export.zip",
        [conversation()],
        {**MEMBERS, "user-synthetic/file_00aa11-copy.png": PNG},
    )
    original = assets_by_id(next(parse_and_build(source, tmp_path)))["file_00aa11"]["original"]
    assert original["status"] == "in-export"
    assert original["member"] == "file_00aa11.dat"
    assert original["duplicate_members"] == ["user-synthetic/file_00aa11-copy.png"]


def test_corrupt_member_is_reported_without_blocking_the_import(visual_zip, tmp_path):
    data = bytearray(visual_zip.read_bytes())
    data[data.index(b"synthetic plot pixels")] ^= 0xFF
    visual_zip.write_bytes(bytes(data))
    results = run(visual_zip, tmp_path)
    assert len(results) == 2
    assets = assets_by_id(manifests(tmp_path)[0])
    assert assets["file-Plot44"]["original"] == {
        "status": "unreadable",
        "members": ["file-Plot44-plot.png"],
    }
    assert assets["file_00aa11"]["original"]["status"] == "in-export"


def test_oversize_member_is_listed_without_being_read(visual_zip, tmp_path, monkeypatch):
    monkeypatch.setattr(chatgpt_artifacts, "MAX_HASH_BYTES", len(PDF) - 1)
    original = assets_by_id(next(parse_and_build(visual_zip, tmp_path)))["file-Doc55"]["original"]
    assert original == {"status": "not-hashed-oversize", "members": ["file-Doc55-brief.pdf"]}


def test_json_export_states_that_it_carries_no_binaries(tmp_path):
    source = tmp_path / "conversations.json"
    source.write_text(json.dumps([conversation()]), encoding="utf-8")
    run(source, tmp_path)
    (manifest,) = manifests(tmp_path)
    assert manifest["counts"]["export-has-no-binaries"] == manifest["counts"]["assets"] == 6
    assert manifest["counts"]["in-export"] == 0
    (receipt,) = chatgpt_artifacts.load_receipts(tmp_path / "private")
    assert receipt["export_kind"] == "json"


def test_unknown_pointer_shape_is_recorded_not_dropped(tmp_path):
    source = conversation()
    source["mapping"]["a1"]["message"]["content"]["parts"].append(
        image_part("sediment://opaque-handle")
    )
    path = write_zip(tmp_path / "export.zip", [source], MEMBERS)
    manifest = next(parse_and_build(path, tmp_path))
    unknown = [a for a in manifest["assets"] if a["asset_id"] is None]
    assert unknown[0]["pointers"] == ["sediment://opaque-handle"]
    assert unknown[0]["original"] == {"status": "unrecognized-pointer"}


def test_prose_that_mentions_a_pointer_is_not_a_reference(tmp_path):
    source = text_only()
    source["mapping"]["u"]["message"]["content"]["parts"] = [
        "sediment://file_00aa11 is what the export calls my upload"
    ]
    path = write_zip(tmp_path / "export.zip", [source], MEMBERS)
    assert list(parse_and_build(path, tmp_path)) == [None]


def test_unknown_branch_selection_is_not_reported_as_unselected(tmp_path):
    source = conversation()
    del source["current_node"]
    path = write_zip(tmp_path / "export.zip", [source], MEMBERS)
    manifest = next(parse_and_build(path, tmp_path))
    states = {r["on_selected_branch"] for a in manifest["assets"] for r in a["references"]}
    assert states == {None}


def test_tampered_receipt_fails_closed(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    receipt = next((tmp_path / "private/_distill/chatgpt/artifact-receipts").rglob("*.json"))
    receipt.write_text(receipt.read_text(encoding="utf-8").replace("in-export", "in-Export"))
    with pytest.raises(ValueError, match="hash mismatch"):
        chatgpt_artifacts.load_receipts(tmp_path / "private")


def test_report_command_prints_counts_only(visual_zip, tmp_path):
    run(visual_zip, tmp_path)
    result = CliRunner().invoke(
        chatgpt_artifacts.cli, ["--private-root", str(tmp_path / "private")]
    )
    assert result.exit_code == 0
    assert "2 conversations scanned, 1 with file references" in result.output
    assert "files referenced: 6; in export with hash: 4" in result.output
    assert "missing-from-export: 2" in result.output
    assert "files in export never referenced: 1" in result.output
    assert "2 without a verified file: chatgpt-" in result.output
    assert "Synthetic visuals" not in result.output and "sketch.png" not in result.output


def test_report_command_on_a_vault_without_imports(tmp_path):
    result = CliRunner().invoke(chatgpt_artifacts.cli, ["--private-root", str(tmp_path)])
    assert result.exit_code == 0
    assert "no ChatGPT artifact receipts" in result.output


def parse_and_build(source: Path, tmp_path: Path):
    export = chatgpt_artifacts.ExportAssets(source)
    for convo in parse_export(source, account_scope="synthetic"):
        yield chatgpt_artifacts.build_manifest(convo.source_graph, export, tmp_path / "private")
