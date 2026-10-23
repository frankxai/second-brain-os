import pytest
from pathlib import Path
from sbo_ingestion.dual_write import _render_brain_body
from sbo_ingestion.summarize import Summary
from sbo_ingestion.ingest import _mark_needs_summary
import frontmatter

def test_non_list_tags_behavior(tmp_path: Path):
    brain_root = tmp_path / "brain"
    brain_root.mkdir()
    brain_path = brain_root / "test.md"

    # Create frontmatter with string tags
    post = frontmatter.Post(
        content="body",
        status="triage",
        tags="str",
    )
    brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    _mark_needs_summary(brain_path, brain_root=brain_root)

    updated_post = frontmatter.load(brain_path)
    assert updated_post["status"] == "needs-summary"
    # list("str") returns ['s', 't', 'r'] and then we append "needs-summary"
    assert "s" in updated_post["tags"]
    assert "t" in updated_post["tags"]
    assert "r" in updated_post["tags"]
    assert "needs-summary" in updated_post["tags"]
