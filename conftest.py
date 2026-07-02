# Put src/ on sys.path so `pytest` works in a fresh clone with zero setup (no `pip install -e .`).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
