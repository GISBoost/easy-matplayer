import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "pipeline", ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import pytest


@pytest.fixture(autouse=True)
def no_real_pbf(monkeypatch):
    """Testy nie skanują prawdziwego PBF (36 s); budynki mają własny test na małym pliku."""
    import viz_buildings

    monkeypatch.setattr(viz_buildings, "find_pbf", lambda: None)
