"""Synthetic source graphs: no account data or provider calls."""

import json

from sbo_ingestion.handlers.chatgpt import parse_export


def test_selected_branch_never_combines_competing_answers(branched_export):
    convo = next(parse_export(branched_export))
    assert [m.text for m in convo.messages] == [
        "edited prompt",
        "tool invocation",
        "selected answer",
    ]
    assert "alternate answer" not in convo.to_raw_markdown()
    assert "original prompt" not in convo.to_raw_markdown()


def test_source_graph_preserves_roles_edges_and_original_content(branched_export):
    convo = next(parse_export(branched_export))
    graph = convo.source_graph
    assert graph.schema_version == "sbo.chatgpt-source.v1"
    assert graph.current_node == "a2"
    assert graph.branch_heads == ("a1", "a2")
    assert graph.path_to("a1") == ("root", "system", "u1", "a1")
    raw = json.loads(graph.original_json)
    assert raw["mapping"]["tool"]["message"]["metadata"]["tool_call_id"] == "call-1"
    assert raw["mapping"]["call"]["message"]["recipient"] == "python"
    assert "**tool**" in graph.to_markdown()
    assert "**system**" in graph.to_markdown()
    assert "alternate answer" in graph.to_markdown("a1")
    assert "selected answer" not in graph.to_markdown("a1")


def test_ambiguous_missing_current_node_never_guesses(branched_export):
    obj = json.loads(branched_export.read_text(encoding="utf-8"))[0]
    del obj["current_node"]
    branched_export.write_text(json.dumps([obj]), encoding="utf-8")
    convo = next(parse_export(branched_export))
    assert convo.messages == ()
    assert convo.source_graph.selected_head is None
    assert "selection unknown" in convo.to_raw_markdown()


def test_cycle_fails_closed_without_losing_original(branched_export):
    obj = json.loads(branched_export.read_text(encoding="utf-8"))[0]
    obj["mapping"]["system"]["parent"] = "a2"
    branched_export.write_text(json.dumps([obj]), encoding="utf-8")
    convo = next(parse_export(branched_export))
    assert convo.messages == ()
    assert convo.source_graph.diagnostics
    assert json.loads(convo.source_graph.original_json) == obj


def test_provenance_is_scoped_and_byte_addressed(branched_export):
    from hashlib import sha256

    graph = next(parse_export(branched_export, account_scope="synthetic-account")).source_graph
    assert graph.account_scope == "synthetic-account"
    assert graph.source_sha256 == sha256(branched_export.read_bytes()).hexdigest()
    assert graph.member == "conversations.json"
    assert graph.coverage == "supplied-export-only"
    assert graph.provider == "chatgpt"


def test_content_reference_addresses_original_node(branched_export):
    graph = next(parse_export(branched_export)).source_graph
    assert graph.content_reference("tool") == "#/original/mapping/tool/message/content"
    assert graph.envelope()["content_references"]["tool"] == graph.content_reference("tool")


def test_missing_current_node_is_distinct_from_inferred_unique_head(chatgpt_export_path):
    from sbo_ingestion.handlers.chatgpt import _parse_conversation

    obj = json.loads(chatgpt_export_path.read_text(encoding="utf-8"))[0]
    del obj["current_node"]
    graph = _parse_conversation(obj).source_graph
    assert graph.current_node is None
    assert graph.selected_head == "msg-2"
