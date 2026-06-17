from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_fixture(name: str) -> dict:
    return json.loads((ROOT / "tests" / "fixtures" / "nara" / name).read_text())
