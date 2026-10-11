import json
from hashlib import sha256

import frontmatter
import pytest

from sbo_ingestion.archive_search import search
from sbo_ingestion.distill import complete_stub, find_stubs
from sbo_ingestion.distill_packet import acknowledge_packet, packet, plan_batch
from sbo_ingestion.ingest import ingest


def selected_capture(tmp_path):
    brain, private = tmp_path / "brain", tmp_path / "private"
    value = {
        "version": 1,
        "rawText": "Synthetic tidal habitat learning pavilion brief. " * 40,
        "tags": " habitat, learning, habitat ",
        "source": "unverified fixture",
        "sourceRef": "PRIVATE_LOCATION_SENTINEL",
    }
    export = tmp_path / "selected.json"
    original = b"\xef\xbb\xbf" + json.dumps(value, ensure_ascii=False).encode()
    export.write_bytes(original)
    result = ingest(export, brain_root=brain, private_root=private, format="idea-capture")[0]
    return brain, private, result, original


def test_capture_acknowledgment_distillation_and_cited_recall(tmp_path):
    brain, private, result, original = selected_capture(tmp_path)
    plan = plan_batch(find_stubs(brain), private, source_budget=32000)
    assert len(plan["notes"]) == 1 and not plan["invalid_sources"]
    digest = sha256(original).hexdigest()
    pieces, offset = [], 0
    while True:
        part = packet(
            result.brain_path,
            brain_root=brain,
            private_root=private,
            offset=offset,
            max_bytes=256,
            expected_sha256=digest if offset else "",
        )
        assert part["trust"] == "untrusted-data" and part["source_sha256"] == digest
        pieces.append(part["content"].encode("utf-8"))
        if offset == 0:
            with pytest.raises(ValueError, match="coverage"):
                complete_stub(result.brain_path, private, agent="test", source_sha256=digest)
        acknowledge_packet(
            result.brain_path,
            brain_root=brain,
            private_root=private,
            digest=digest,
            token=part["ack_token"],
        )
        if part["next_offset"] is None:
            break
        offset = part["next_offset"]
    assert b"".join(pieces) == original
    post = frontmatter.load(result.brain_path)
    post["title"] = "Tidal habitat learning pavilion"
    post.content = (
        "Draft synthesis: retain habitat protection and accessible field lessons. "
        "Source identity remains unverified."
    )
    result.brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    complete_stub(result.brain_path, private, agent="synthetic-test", source_sha256=digest)
    hits = search(brain, "tidal habitat learning")
    expected = result.brain_path.relative_to(brain).as_posix()
    assert hits["items"][0]["citation"] == expected
    assert hits["items"][0]["status"] == "triage"
    assert "PRIVATE_LOCATION_SENTINEL" not in json.dumps(hits)
    assert result.private_path.read_bytes() == original


@pytest.mark.parametrize(
    "mutation", ["wrong-source", "wrong-identity", "wrong-folder", "changed-body"]
)
def test_capture_json_reader_denies_forged_reference(tmp_path, mutation):
    brain, private, result, _ = selected_capture(tmp_path)
    post = frontmatter.load(result.brain_path)
    if mutation == "wrong-source":
        post["source"] = "chatgpt"
    elif mutation == "wrong-identity":
        post["conversation_id"] = "idea-" + "0" * 16
    elif mutation == "wrong-folder":
        post["private_file"] = post["private_file"].replace("/idea-capture/", "/chatgpt/")
    else:
        value = json.loads(result.private_path.read_bytes().decode("utf-8-sig"))
        value["rawText"] += " changed source"
        result.private_path.write_text(json.dumps(value), encoding="utf-8")
    result.brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    with pytest.raises(ValueError):
        packet(result.brain_path, brain_root=brain, private_root=private)
