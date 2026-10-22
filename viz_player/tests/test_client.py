"""Silnik klienta (viz_player/engine.js) pod node kontra wzorzec z Pythona (Player, viz_engine)."""
import json
import shutil
import subprocess

import numpy as np
import pytest

from viz_player import curves
from viz_player import player as pl

from . import fixture as fx

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="brak node")
TIMES = [999.0, 1003.0, 1016.5, 1030.0, 1035.2, 1061.0, 5000.0, 5020.25, 5059.9, 8005.0]


@pytest.fixture(scope="module")
def player(tmp_path_factory):
    rows = [*fx.trip("r1", 1000), *fx.trip("t1", 1030), *fx.trip("c1", 5000), *fx.leg("r1", 8000, 8010)]
    p = pl.Player()
    p.open(fx.write_run(tmp_path_factory.mktemp("client") / "mini", rows), remember=False)
    assert not p.error
    return p


def with_bend(player):
    """Łamana na linku 1 (l1): cięciwa 100 m, łuk wychylony o 30 m."""
    pts = [fx.local(100, 0), fx.local(150, 30), fx.local(200, 0)]
    player.curve = curves.Curves(np.array([0, 0, 3, 3, 3, 3, 3], dtype=np.int32), np.array(pts, dtype=np.float32))
    player.curve_note = "łamane: 1 z 6"


def run_node(player, tmp_path, with_curves):
    if with_curves:
        with_bend(player)
    site_dir = player.write_site(tmp_path / "site").parent
    expected = {"times": [], "trails": [], "lookups": []}
    for t in TIMES:
        fr = player._frame_np(t, None)
        lon, lat = player.fwd.transform(fr.xy[:, 0].astype(np.float64) + player.origin[0], fr.xy[:, 1].astype(np.float64) + player.origin[1])
        expected["times"].append({
            "t": t, "track": [int(v) for v in fr.track], "lon": list(map(float, lon)), "lat": list(map(float, lat)),
            "speed": list(map(float, fr.speed)), "heading": list(map(float, fr.heading)), "link": [int(v) for v in fr.link],
        })
    track = player.active_track("r1", 1035.2)
    expected["trails"].append({"track": int(track), "t": 1035.2, "path": player.path_latlon(track, 1035.2)})
    expected["lookups"] = [
        {"q": q, "want": player.lookup(q)} for q in ["r1", "r", "c1", "brak", ""]
    ]
    path = tmp_path / "expected.json"
    path.write_text(json.dumps(expected), encoding="utf-8")
    res = subprocess.run([NODE, str(pl.ROOT / "viz_player" / "tests" / "client_check.js"), str(site_dir), str(path)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


@pytest.mark.parametrize("bent", [False, True])
def test_client_matches_python(player, tmp_path, bent):
    got = run_node(player, tmp_path, bent)
    assert sum(r["n_py"] for r in got["frames"]) > 8, "test porównuje za mało aut"
    for r in got["frames"]:
        assert r["n_js"] == r["n_py"] and r["missing"] == 0, r
        assert r["pos_m"] < 0.02 and r["speed_rel"] < 0.01 and r["heading"] < 0.01 and r["link"] == 0, r
    for r in got["trails"]:
        assert r["n_js"] == r["n_py"] and r["pos_m"] < 0.1, r  # wzorzec zaokrągla do 1e-6° (11 cm)
    assert all(r["ok"] for r in got["lookups"]), got["lookups"]
