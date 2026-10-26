"""Strona webowa (scripts/web_build.py): układ plików, oba języki, dane scenariusza wspólne z aplikacją."""
import importlib.util
import json
from pathlib import Path

import pytest

from . import fixture as fx

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def web_build():
    spec = importlib.util.spec_from_file_location("web_build", ROOT / "scripts" / "web_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def site(web_build, tmp_path_factory):
    base = tmp_path_factory.mktemp("web")
    fx.write_run(base / "runs" / "demo-kutno", [*fx.trip("r1", 1000), *fx.trip("t1", 1030), *fx.trip("c1", 5000)])
    out = base / "out"
    assert web_build.main(base / "runs", out) == 0
    return out


def test_layout(site):
    for name in ("index.html", "scenarios.json", ".nojekyll", "player/index.html", "player/engine.js",
                 "player/vendor/deck.min.js", "player/vendor/maplibre/maplibre-gl.mjs"):
        assert (site / name).is_file(), name
    s = site / "s" / "demo-kutno"
    for name in ("boot.en.json", "boot.pl.json", "link_ll.bin", "link_type.bin", "data/manifest.json", "data/persons.json"):
        assert (s / name).is_file(), name
    assert not (s / "boot.json").exists()
    assert list((s / "data").glob("chunk_*.bin"))


def test_scenarios_list(site):
    rows = json.loads((site / "scenarios.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in rows] == ["demo-kutno"]
    assert rows[0]["size_mb"] >= 0 and rows[0]["title"]["pl"] and rows[0]["title"]["en"]


def test_both_languages(site):
    en = json.loads((site / "s" / "demo-kutno" / "boot.en.json").read_text(encoding="utf-8"))
    pl = json.loads((site / "s" / "demo-kutno" / "boot.pl.json").read_text(encoding="utf-8"))
    assert en["lang"] == "en" and pl["lang"] == "pl"
    assert en["strings"] and not pl["strings"]
    assert en["data"] == pl["data"] and en["nLinks"] == pl["nLinks"]
    assert [c["key"] for c in en["classes"]] == [c["key"] for c in pl["classes"]]


def test_manifest_matches_boot(site):
    s = site / "s" / "demo-kutno"
    boot = json.loads((s / "boot.en.json").read_text(encoding="utf-8"))
    manifest = json.loads((s / boot["data"].split("?")[0]).read_text(encoding="utf-8"))
    assert boot["data"].endswith(manifest["source_key"][:12])


def test_missing_runs_fail(web_build, tmp_path):
    (tmp_path / "runs").mkdir()
    with pytest.raises(SystemExit):
        web_build.main(tmp_path / "runs", tmp_path / "out")
