import json
from unittest.mock import patch

import frontmatter
import pytest

from sbo_ingestion.ingest import ingest, CaptureBatchError
from tests.test_kura import capture


def test_kura_dual_write_is_incremental_and_retains_curated_note(tmp_path, tmp_vault_pair):
    brain, private = tmp_vault_pair
    source = capture(tmp_path / "Kura" / "chatgpt" / "2026-10-04_test" / "conversation.md")
    with patch("sbo_ingestion.ingest.summarize") as model:
        first = ingest(source.parent.parent.parent, brain_root=brain, private_root=private)
        assert len(first) == 1
        assert frontmatter.load(first[0].brain_path)["status"] == "needs-summary"
        assert "A source-backed answer" in first[0].private_path.read_text(encoding="utf-8")
        assert "A source-backed answer" not in first[0].brain_path.read_text(encoding="utf-8")
        assert ingest(source, brain_root=brain, private_root=private) == []
        post = frontmatter.load(first[0].brain_path)
        post.content = "Human-curated decision"
        post["status"] = "reviewed"
        first[0].brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
        curated = first[0].brain_path.read_bytes()
        capture(source, answer="Updated source-backed answer")
        second = ingest(source, brain_root=brain, private_root=private)
        assert second[0].brain_preserved
        assert first[0].brain_path.read_bytes() == curated
        assert second[0].private_path == first[0].private_path
        history = list((private / "_distill" / "kura" / "history").glob("*/*.md"))
        assert len(history) == 1
        assert "A source-backed answer" in history[0].read_text(encoding="utf-8")
        receipt = json.loads(next((private / "_distill" / "kura").glob("*.json")).read_text())
        assert receipt["refresh_pending"] is True
        model.assert_not_called()


def test_changed_capture_reuses_existing_official_export_private_reference(tmp_path, tmp_vault_pair):
    brain, private = tmp_vault_pair
    source = capture(tmp_path / "conversation.md")
    first = ingest(source, brain_root=brain, private_root=private)[0]
    original = first.private_path
    dated = original.with_name("2026-01-01-native-a.md")
    original.rename(dated)
    post = frontmatter.load(first.brain_path)
    post["private_file"] = str(dated.relative_to(private))
    first.brain_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    capture(source, answer="Another answer")
    second = ingest(source, brain_root=brain, private_root=private)[0]
    assert second.private_path == dated
    assert not original.exists()


def test_overlapping_roots_fail_before_writes(tmp_path):
    source = capture(tmp_path / "conversation.md")
    with pytest.raises(ValueError, match="non-overlapping"):
        ingest(source, brain_root=tmp_path / "vault", private_root=tmp_path / "vault" / "private")


def test_browser_view_cannot_replace_official_raw_history(tmp_path, tmp_vault_pair):
    brain, private = tmp_vault_pair
    source = capture(tmp_path / "conversation.md")
    first = ingest(source, brain_root=brain, private_root=private)[0]
    post = frontmatter.load(first.private_path)
    del post["capture_scope"]
    post.content = "Full official account export including branches"
    first.private_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    official = first.private_path.read_bytes()
    capture(source, answer="Partial browser view")
    second = ingest(source, brain_root=brain, private_root=private)[0]
    assert second.private_path != first.private_path
    assert "kura-views" in second.private_path.parts
    assert first.private_path.read_bytes() == official
    assert frontmatter.load(second.brain_path)["private_file"] == str(first.private_path.relative_to(private)).replace("\\", "/")


def test_changed_capture_does_not_spend_api_money_for_a_preserved_note(tmp_path, tmp_vault_pair):
    brain, private = tmp_vault_pair
    source = capture(tmp_path / "conversation.md")
    ingest(source, brain_root=brain, private_root=private)
    capture(source, answer="Changed answer")
    with patch("sbo_ingestion.ingest.summarize") as model:
        result = ingest(source, brain_root=brain, private_root=private, mode="api", api_key="test")
        assert result[0].brain_preserved
        model.assert_not_called()


def test_damaged_capture_does_not_block_later_healthy_inputs(tmp_path, tmp_vault_pair):
    brain, private = tmp_vault_pair
    root = tmp_path / 'Kura'
    broken = capture(root / 'chatgpt' / '2026-10-04_a' / 'conversation.md')
    broken.with_name('capture.json').write_text('{"kind": "unfinished"}', encoding='utf-8')
    capture(root / 'chatgpt' / '2026-10-04_b' / 'conversation.md')
    with pytest.raises(CaptureBatchError) as error:
        ingest(root, brain_root=brain, private_root=private)
    assert len(error.value.results) == 1
    assert 'A source-backed answer' in error.value.results[0].private_path.read_text(encoding='utf-8')
    assert str(broken) in str(error.value)


def test_reset_receipt_cannot_erase_previous_private_source(tmp_path, tmp_vault_pair):
    brain, private = tmp_vault_pair
    source = capture(tmp_path / 'conversation.md')
    first = ingest(source, brain_root=brain, private_root=private)[0]
    original = first.private_path.read_text(encoding='utf-8')
    next((private / '_distill' / 'kura').glob('*.json')).unlink()
    capture(source, answer='Revised after a receipt reset')
    ingest(source, brain_root=brain, private_root=private)
    history = list((private / '_distill' / 'kura' / 'history').glob('*/*.md'))
    assert len(history) == 1
    assert history[0].read_text(encoding='utf-8') == original


def test_malformed_yaml_and_multiple_cli_inputs_continue_healthy_work(tmp_path, tmp_vault_pair):
    from click.testing import CliRunner
    from sbo_ingestion.ingest import cli
    brain, private = tmp_vault_pair
    bad = capture(tmp_path / 'bad' / 'conversation.md')
    bad.write_text('---\nid: [unterminated\n---\ntext', encoding='utf-8')
    good = capture(tmp_path / 'good' / 'conversation.md')
    result = CliRunner().invoke(cli, [str(bad), str(good), '--brain-root', str(brain), '--private-root', str(private)])
    assert result.exit_code == 1
    assert 'Invalid Kura frontmatter' in result.output
    assert 'wrote 1 conversation pairs' in result.output
    assert len(list((private / 'chat-history').glob('*/*.md'))) == 1
