import json
from pathlib import Path

import pytest

from viz_player import check as chk
from viz_player import player as pl

from . import fixture as fx


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    rows = [
        fx.act("actend", "r2", 23000, "l0", 0, "home"),
        *fx.leg("r2", 23000, 23100),
        fx.act("actstart", "r2", 23100, "l0", 100, "work"),
        *fx.leg("t2", 21600, 21620),
        *fx.leg("h2", 23040, 23060),
        *fx.leg("r2b", 30000, 30010),
        *fx.trip("c1", 1000, acts=False),
        *fx.trip("o1", 2000, acts=False),
        *fx.trip("t9", 3000, acts=False),
    ]
    return fx.write_run(tmp_path_factory.mktemp("player") / "mini", rows)


@pytest.fixture
def player(run_dir):
    p = pl.Player()
    p.open(run_dir, remember=False)
    assert not p.error
    return p


def wgs(p, x, y=0.0):
    lon, lat = p.fwd.transform(*fx.world(x, y))
    return float(lat), float(lon)


def test_clock_and_labels():
    assert pl.clock(pl.START) == "06:00:00" and pl.clock(28591) == "07:56:31"
    assert pl.clock(30 * 3600 + 12 * 60) == "30:12:00" and pl.clock(-5) == "00:00:00"
    assert pl.sample_label(0.25) == "0,25" and pl.sample_label(None) == "brak"


DAY = [
    {"t": 100.0, "kind": "actend", "type": "home"},
    {"t": 200.0, "kind": "actstart", "type": "work"},
    {"t": 500.0, "kind": "actend", "type": "work"},
    {"t": 600.0, "kind": "actstart", "type": "home"},
]


def test_schedule_axis():
    got = [(s["label"], s["t0"], s["t1"], s["on"]) for s in pl.schedule(DAY, 0, 800, [(100, 200), (500, 600)], 550)]
    assert got == [
        ("home", 0.0, 100.0, False), ("jazda", 100.0, 200.0, False), ("work", 200.0, 500.0, False),
        ("jazda", 500.0, 600.0, True), ("home", 600.0, 800.0, False),
    ]


def test_schedule_squeezes_stays():
    squeezed = pl.schedule(
        [
            {"t": 300.0, "kind": "actend", "type": "home"},
            {"t": 900.0, "kind": "actstart", "type": "work"},
            {"t": 8 * 3600 + 900.0, "kind": "actend", "type": "work"},
            {"t": 8 * 3600 + 1500.0, "kind": "actstart", "type": "home"},
        ],
        0, 30 * 3600, [(300.0, 900.0), (8 * 3600 + 900.0, 8 * 3600 + 1500.0)], 400.0,
    )
    stays = [s["u1"] - s["u0"] for s in squeezed if not s["trip"]]
    trips = [s["u1"] - s["u0"] for s in squeezed if s["trip"]]
    assert len(stays) == 3 and len(trips) == 2 and min(trips) >= 0.15 and max(stays) <= 0.25
    assert max(stays) - min(stays) < 1e-4


def test_schedule_edges():
    end = pl.schedule(DAY, 0, 800, [(100, 200), (500, 600)], 800)
    assert end[-1]["on"] and not any(s["on"] for s in end[:-1])
    cut = pl.schedule([{"t": 200.0, "kind": "actstart", "type": "work"}], 0, 400, [(180, 220)], 200)
    assert [(s["label"], s["on"]) for s in cut] == [("jazda", True), ("work", False)]


def test_covering():
    home = {"t": 100.0, "kind": "actend", "type": "home"}
    work = {"t": 200.0, "kind": "actstart", "type": "work"}
    rows = [home, work]
    assert pl.covering(rows, 50) is home and pl.covering(rows, 100) is None and pl.covering(rows, 150) is None
    assert pl.covering(rows, 200) is work and pl.covering(rows, 250) is work
    assert pl.covering([{"t": 10.0, "kind": "actstart", "type": "work"}], 5) is None


def test_open_sets_origin_start_sample(player):
    assert player.origin == fx.ORIGIN
    assert abs(player.t_start - pl.START) < 1e-6 and player.sample == "0,25"
    lat, lon = wgs(player, 0)
    east, north = player.inv.transform(lon, lat)
    assert abs(east - fx.world(0)[0]) < 0.01 and abs(north - fx.world(0)[1]) < 0.01


def test_missing_run_dir(tmp_path):
    p = pl.Player()
    p.open(tmp_path / "nie-ma", remember=False)
    assert p.error and "Brak katalogu" in p.error
    assert p.frame(0)["panel"]["lines"] == [p.error]


def test_morning_frame(player):
    morning = player.frame(player.t_start)
    assert morning["n"] == 1 and morning["clock"] == "06:00:00" and morning["heavy"] == [0]


def test_activity_panel_and_axis(player):
    pay = player.frame(player.t_start, None, {"id": "r2"})
    panel = pay["panel"]
    assert panel["kind"] == "activity" and "home" in panel["lines"] and "nie jedzie" in panel["lines"]
    axis = panel["axis"]
    assert [s["label"] for s in axis] == ["home", "jazda", "work"]
    assert axis[0]["on"] and not axis[1]["on"] and not axis[2]["on"]
    assert (axis[1]["t0"], axis[1]["t1"], axis[1]["trip"]) == (23000.0, 23100.0, True)
    assert axis[1]["u1"] - axis[1]["u0"] >= 0.2
    assert pay["sel"] is None and not pay["path"], "stojący nie ma ducha na drodze"
    later = player.frame(24000, None, {"id": "r2"})["panel"]
    assert later["kind"] == "activity" and "work" in later["lines"]
    assert any(s["label"] == "work" and s["on"] for s in later["axis"])


def test_class_filter(player):
    assert player.frame(player.t_start, ["resident", "commuter", "outbound", "ciezkie"])["n"] == 0
    both = player.frame(23050, player.chip_keys)
    assert both["n"] == 2 and sum(both["heavy"]) == 1
    with pytest.raises(Exception):
        player.frame(23050, ["nie-ma-takiej"])


def test_pick_vehicle_then_link(player):
    hit = player.pick(23010, None, *wgs(player, 10), *wgs(player, 18))
    assert hit == {"kind": "vehicle", "id": "r2"}
    pay = player.frame(23010, None, hit and {"id": hit["id"]})
    assert pay["panel"]["kind"] == "vehicle" and pay["panel"]["lines"][0] == "r2"
    assert "3,6 km/h" in pay["panel"]["lines"] and len(pay["path"]) >= 2 and pay["sel"] == 0
    road = player.pick(23010, None, *wgs(player, 80, 3), *wgs(player, 88, 3))
    assert road["kind"] == "link"
    panel = player.frame(23010, None, {"link": road["link"]})["panel"]
    assert panel["kind"] == "link" and "residential" in panel["lines"] and "freespeed 36 km/h" in panel["lines"]
    assert "teraz 1 auto" in panel["lines"][-1] and "średnia na odcinku" in panel["lines"][-1]
    assert player.pick(23010, None, *wgs(player, 10, 300), *wgs(player, 18, 300)) == {"kind": "miss"}


def test_follow_pans_to_vehicle_and_activity(player):
    moving = player.frame(23010, None, {"id": "r2"}, True)
    assert moving["pan"] == [moving["lat"][moving["sel"]], moving["lon"][moving["sel"]]]
    parked = player.frame(24000, None, {"id": "r2"}, True)
    assert parked["pan"] is not None and parked["sel"] is None
    assert player.frame(24000, None, {"id": "r2"}, False)["pan"] is None


def test_stale_selection_is_ignored(player):
    pay = player.frame(player.t_start, None, {"id": "nie-ma", "link": 999})
    assert pay["panel"]["kind"] == "empty" and pay["sel"] is None and pay["link"] is None


def test_lookup(player):
    assert player.lookup("r2") == {"followed": "r2"}
    many = player.lookup("r")
    assert {h["id"] for h in many.get("hits", [])} == {"r2", "r2b"}
    assert player.lookup("") == {"hits": []}


def test_frame_is_stateless_across_threads(player):
    """pywebview woła Api z wielu wątków: wynik zależy tylko od argumentów."""
    from concurrent.futures import ThreadPoolExecutor

    calls = [
        (t, classes, sel, follow)
        for t in (21600, 23010, 23050, 24000)
        for classes in (None, ["tlo"], ["ciezkie", "resident"])
        for sel, follow in (({"id": "r2"}, True), ({"link": 0}, False), (None, False))
    ]
    expected = [player.frame(*c) for c in calls]
    with ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda c: player.frame(*c), calls * 8))
    assert got == expected * 8


def test_state_file(tmp_path):
    inside = pl.ROOT / "viz_player" / "no-such-run"
    dest = tmp_path / "state.json"
    pl.save_state(inside, dest)
    assert json.loads(dest.read_text(encoding="utf-8"))["run"] == "viz_player/no-such-run"
    pl.save_state(tmp_path / "x", dest)
    assert Path(json.loads(dest.read_text(encoding="utf-8"))["run"]) == tmp_path / "x"


def test_site_files(player, tmp_path):
    index = player.write_site(tmp_path / "site")
    site_dir = index.parent
    boot = json.loads((site_dir / "boot.json").read_text(encoding="utf-8"))
    assert boot["nLinks"] == 6 and boot["run"] == "mini" and boot["error"] is None
    assert boot["basemap"] is None or str(boot["basemap"]["url"]).startswith(pl.CARTO)
    assert (site_dir / "link_ll.bin").stat().st_size == 6 * 4 * 8
    assert (site_dir / "link_type.bin").stat().st_size == 6
    assert (site_dir / "vendor" / "leaflet.js").is_file()
    assert not (site_dir / "curve_off.bin").exists(), "mini-run nie ma łamanych"
    manifest = json.loads((site_dir / boot["data"]).read_text(encoding="utf-8"))
    assert manifest["format"] == 1 and (site_dir / "data" / manifest["chunks"][0]["file"]).is_file()
    assert "tile.openstreetmap.org" not in index.read_text(encoding="utf-8")


def test_site_curves(player, tmp_path):
    import numpy as np

    from viz_player import curves

    player.curve = curves.Curves(
        np.array([0, 3, 3, 3, 3, 3, 3], dtype=np.int32),
        np.array([[0, 0], [50, 0], [100, 0]], dtype=np.float32),
    )
    site_dir = player.write_site(tmp_path / "site").parent
    assert player.boot()["nCurve"] == 3
    assert (site_dir / "curve_off.bin").stat().st_size == 7 * 4
    assert (site_dir / "curve_lon.bin").stat().st_size == 3 * 8
    assert (site_dir / "curve_lat.bin").stat().st_size == 3 * 8


def test_generic_check_passes(run_dir):
    assert chk.run(run_dir) == 0


def test_curve_note_reaches_boot(player):
    assert player.boot()["curveNote"] == player.curve_note and player.curve_note.startswith("łamane")
