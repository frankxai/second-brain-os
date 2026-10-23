from pathlib import Path
import pytest
from sbo_ingestion.safe_path import safe_component, ensure_within

def test_safe_component_normal():
    assert safe_component("normal-file.txt", fallback="default") == "normal-file.txt"

def test_safe_component_illegal_characters():
    assert safe_component("file<name>.txt", fallback="default") == "file-name-.txt"
    assert safe_component('file"name".txt', fallback="default") == "file-name-.txt"
    assert safe_component("file:name.txt", fallback="default") == "file-name.txt"
    assert safe_component("file/name.txt", fallback="default") == "file-name.txt"
    assert safe_component("file\\name.txt", fallback="default") == "file-name.txt"
    assert safe_component("file|name.txt", fallback="default") == "file-name.txt"
    assert safe_component("file?name.txt", fallback="default") == "file-name.txt"
    assert safe_component("file*name.txt", fallback="default") == "file-name.txt"
    assert safe_component("file\x00name.txt", fallback="default") == "file-name.txt"

def test_safe_component_parent_directory():
    assert safe_component("foo/../bar", fallback="default") == "foo---bar"
    assert safe_component("..", fallback="default") == "-"

def test_safe_component_max_length():
    assert len(safe_component("a" * 100, fallback="default", max_len=10)) == 10
    assert safe_component("a" * 100, fallback="default", max_len=10) == "a" * 10

def test_safe_component_windows_reserved():
    assert safe_component("CON", fallback="default") == "default"
    assert safe_component("PRN", fallback="default") == "default"
    assert safe_component("AUX", fallback="default") == "default"
    assert safe_component("NUL", fallback="default") == "default"
    assert safe_component("COM1", fallback="default") == "default"
    assert safe_component("COM9", fallback="default") == "default"
    assert safe_component("LPT1", fallback="default") == "default"
    assert safe_component("LPT9", fallback="default") == "default"

    assert safe_component("con.txt", fallback="default") == "default"
    assert safe_component("CoN", fallback="default") == "default"

def test_safe_component_empty_fallback():
    assert safe_component("", fallback="default") == "default"
    assert safe_component("...", fallback="default") == "-"
    assert safe_component(" ", fallback="default") == "default"

def test_ensure_within_valid(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = root / "file.txt"
    # Using relative_to to bypass resolve() requiring existence in some cases
    assert ensure_within(root, target) == target

def test_ensure_within_invalid(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "outside.txt"
    with pytest.raises(ValueError, match="refusing to write outside"):
        ensure_within(root, target)
