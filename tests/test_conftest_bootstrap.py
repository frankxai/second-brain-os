"""Guard: the root conftest.py must make sbo_ingestion importable in a fresh clone.

Baseline before v0.3.0: `pytest` failed collection with
`ModuleNotFoundError: No module named 'sbo_ingestion'` because nothing put src/
on sys.path and adopters had to know to run `pip install -e .` first. The root
conftest.py fixes that with zero setup — this test locks the contract in place.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_root_conftest_exists() -> None:
    assert (REPO_ROOT / "conftest.py").exists(), "root conftest.py must exist for zero-setup pytest"


def test_src_is_on_sys_path() -> None:
    """The root conftest.py inserted src/ so imports resolve without installation."""
    src = str(REPO_ROOT / "src")
    assert any(Path(p).resolve() == Path(src).resolve() for p in sys.path if p), (
        "src/ should be on sys.path (inserted by root conftest.py)"
    )


def test_sbo_ingestion_imports() -> None:
    """The whole reason the conftest exists: this import must succeed with no install."""
    import sbo_ingestion  # noqa: F401
    from sbo_ingestion.handlers import claude_ai, memories  # noqa: F401
