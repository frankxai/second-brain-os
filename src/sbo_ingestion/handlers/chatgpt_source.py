"""Lossless provider source envelope, not a memory-admission or execution schema."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_text(message: dict) -> str:
    content = message.get("content") or {}
    parts = content.get("parts") or []
    # Structured media/tool content remains in original_json; never invent its text.
    return "\n\n".join(p for p in parts if isinstance(p, str) and p).strip()


@dataclass(frozen=True)
class ChatGPTSource:
    original_json: str
    account_scope: str | None = None
    source_sha256: str = ""
    member: str = ""
    member_sha256: str = ""
    schema_version: str = "sbo.chatgpt-source.v1"
    provider: str = "chatgpt"
    coverage: str = "supplied-export-only"

    @property
    def content_sha256(self) -> str:
        return sha256(self.original_json.encode("utf-8")).hexdigest()

    @property
    def conversation_id(self) -> str:
        return json.loads(self.original_json)["id"]

    @property
    def stable_id(self) -> str:
        # Unknown scope is explicitly provisional; preserve established vault IDs.
        if self.account_scope is None:
            return self.conversation_id
        return (
            "chatgpt-"
            + sha256(
                canonical_json([self.provider, self.account_scope, self.conversation_id]).encode()
            ).hexdigest()
        )

    @property
    def current_node(self) -> str | None:
        return json.loads(self.original_json).get("current_node")

    @property
    def mapping(self) -> dict:
        return json.loads(self.original_json).get("mapping", {})

    @property
    def branch_heads(self) -> tuple[str, ...]:
        mapping = self.mapping
        parents = {n.get("parent") for n in mapping.values()}
        return tuple(sorted(key for key in mapping if key not in parents))

    @property
    def diagnostics(self) -> tuple[str, ...]:
        mapping = self.mapping
        errors = set()
        for key, node in mapping.items():
            parent = node.get("parent")
            if parent is not None and parent not in mapping:
                errors.add("missing-parent")
            children = node.get("children", [])
            if any(c not in mapping or mapping[c].get("parent") != key for c in children):
                errors.add("inconsistent-children")
            if parent in mapping and key not in mapping[parent].get("children", []):
                errors.add("inconsistent-parent")
        # Iterative walk handles deep exports without Python recursion limits.
        done = set()
        for key in mapping:
            seen = set()
            cursor = key
            while cursor in mapping and cursor not in done:
                if cursor in seen:
                    errors.add("cycle")
                    break
                seen.add(cursor)
                cursor = mapping[cursor].get("parent")
            done.update(seen)
        if self.current_node is not None and self.current_node not in mapping:
            errors.add("missing-current-node")
        return tuple(sorted(errors))

    @property
    def selected_head(self) -> str | None:
        if self.diagnostics:
            return None
        if self.current_node is not None:
            return self.current_node
        heads = self.branch_heads
        return heads[0] if len(heads) == 1 else None

    def path_to(self, head: str | None = None) -> tuple[str, ...]:
        if self.diagnostics:
            return ()
        cursor = head if head is not None else self.selected_head
        mapping = self.mapping
        if cursor is None:
            return ()
        if cursor not in mapping:
            raise ValueError("Unknown ChatGPT branch head")
        path = []
        while cursor is not None:
            path.append(cursor)
            cursor = mapping[cursor].get("parent")
        return tuple(reversed(path))

    def to_markdown(self, head: str | None = None) -> str:
        path = self.path_to(head)
        if not path:
            return "Branch selection unknown; inspect preserved source graph.\n"
        mapping = self.mapping
        lines = ["Derived branch: " + json.dumps(path[-1]), ""]
        for key in path:
            message = mapping[key].get("message")
            if not message:
                continue
            role = (message.get("author") or {}).get("role") or "unknown"
            role = "human" if role == "user" else role
            lines.extend(
                [
                    f"**{role}** · node {json.dumps(key)}",
                    "",
                    content_text(message) or "[non-text content: see source node]",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def content_reference(self, node_id: str) -> str:
        if node_id not in self.mapping:
            raise ValueError("Unknown ChatGPT node")
        escaped = node_id.replace("~", "~0").replace("/", "~1")
        return f"#/original/mapping/{escaped}/message/content"

    def envelope(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "account_scope": self.account_scope,
            "identity_status": (
                "account-scoped"
                if self.account_scope is not None
                else "provisional-unknown-account"
            ),
            "conversation_id": self.conversation_id,
            "stable_id": self.stable_id,
            "content_sha256": self.content_sha256,
            "source_sha256": self.source_sha256,
            "export_batch_id": self.source_sha256,
            "member": self.member,
            "member_sha256": self.member_sha256,
            "coverage": self.coverage,
            "current_node": self.current_node,
            "selected_head": self.selected_head,
            "branch_heads": self.branch_heads,
            "diagnostics": self.diagnostics,
            "content_references": {
                key: "#/original/mapping/"
                + key.replace("~", "~0").replace("/", "~1")
                + "/message/content"
                for key, node in self.mapping.items()
                if node.get("message") is not None
            },
            "original": json.loads(self.original_json),
        }
