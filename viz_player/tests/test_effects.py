"""Błysk aktywności i obciążenie linków: eksport v2, wzorce z Pythona liczone z surowych eventów, klient (engine.js) pod node."""
import json
import shutil
import subprocess

import numpy as np
import pytest
from pyproj import Transformer

import viz_engine
import viz_export
import viz_index
from viz_player import player as pl

from . import fixture as fx

NODE = shutil.which("node")
FLOW_FACTOR = 0.25   # fixtura wpisuje flowCapacityFactor = sampleSize
CAPACITY = 600.0     # fixtura: capacity="600", permlanes="1", freespeed="10", length="100"
FREESPEED = 10.0
LENGTH = 100.0

# trzy zwykłe przejazdy (czas wjazdu 1000, 1030, 5000), wolny (30 s na l0 zamiast 10 s) i wjazd w połowie linku l2
SLOW = [
    fx.enter("s1", 2000, person="s1"),
    '<event time="2030" type="left link" vehicle="s1" link="l0"/>',
    '<event time="2030" type="entered link" vehicle="s1" link="l1"/>',
    fx.leave("s1", 2040, link="l1", person="s1"),
    fx.act("actstart", "s1", 2041, "l1", 200, "shop"),
]
PARTIAL = [
    fx.enter("p1", 3000, link="l2", rel="0.5", person="p1"),
    fx.leave("p1", 3005, link="l2", person="p1"),
    fx.act("actstart", "p1", 3006, "l2", 250, "work"),
]
ROWS = [*fx.trip("r1", 1000), *fx.trip("t1", 1030), *fx.trip("c1", 5000), *SLOW, *PARTIAL]


def ev_time(line):
    return float(viz_index.field(line, "time"))


def ref_exits(rows):
    """Wyjazdy z linków prosto z eventów: (czas, link, pełny przejazd, czas na linku). Niezależne od indeksu i porcji."""
    cur, out = {}, []
    for row in sorted(rows, key=ev_time):
        typ, veh, t = viz_index.field(row, "type"), viz_index.field(row, "vehicle"), ev_time(row)
        link = viz_index.field(row, "link")
        if typ == "vehicle enters traffic":
            cur[veh] = (link, t, float(viz_index.field(row, "relativePosition") or 1) == 0)
        elif typ == "entered link":
            cur[veh] = (link, t, True)
        elif typ in ("left link", "vehicle leaves traffic"):
            if veh not in cur:   # fixtura dubluje „left link” i „leaves traffic” na ostatnim linku, MATSim nie
                continue
            _, t0, full = cur.pop(veh)
            out.append((t, int(link[1:]), full, t - t0))
    return out


def ref_stats(rows, t, window):
    n = np.zeros(fx.N_LINKS, int)
    nf, ln, tt = np.zeros(fx.N_LINKS, int), np.zeros(fx.N_LINKS), np.zeros(fx.N_LINKS)
    for te, link, full, dt in ref_exits(rows):
        if t - window < te <= t:
            n[link] += 1
            if full:
                nf[link] += 1
                ln[link] += LENGTH
                tt[link] += max(dt, 0.1)
    return n, nf, ln, tt


def ref_values(n, nf, ln, tt, window):
    speed = [float(ln[i] / tt[i] / FREESPEED) if nf[i] else None for i in range(fx.N_LINKS)]
    flow = [float(n[i] * 3600 / window / (CAPACITY * FLOW_FACTOR)) if n[i] else None for i in range(fx.N_LINKS)]
    return speed, flow


def ref_starts(rows, t, life):
    """Starty aktywności z (t - life, t] prosto z eventów (bez „car interaction”): (czas, typ)."""
    return sorted(
        (ev_time(r), viz_index.field(r, "actType")) for r in rows
        if viz_index.field(r, "type") == "actstart" and viz_index.field(r, "actType") != "car interaction" and t - life < ev_time(r) <= t
    )


FLASHES = [(1062, 5), (1092, 100), (5062, 3), (2045, 10), (3007, 5), (4000, 50), (1092, 1)]
STATS = [(1060, 60), (1045, 20), (2031, 30), (2040, 15), (3005, 10), (5030, 15), (1000, 5), (2040, 900)]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return fx.write_run(tmp_path_factory.mktemp("effects") / "mini", ROWS)


@pytest.fixture(scope="module")
def index(run):
    return viz_engine.load(run)


def test_export_v2_carries_activities(run, index):
    manifest = viz_export.build(run, chunk_sec=7)
    assert manifest["format"] == 2 and manifest["n_acts"] == len(index.act_t)
    assert manifest["act_types"] == [index.meta["act_type_legend"][str(i)] for i in range(len(manifest["act_types"]))]
    starts = np.bincount(index.act_type[index.act_kind == 1], minlength=len(manifest["act_types"]))
    assert manifest["act_start_counts"] == [int(v) for v in starts]
    out = run / "viz" / "export"
    cols = [tuple(c) for c in manifest["chunk_columns"]]
    rows = []
    to_ll = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    ox, oy = manifest["origin_local"]
    for ch in manifest["chunks"]:
        c = viz_export.read_columns(out / ch["file"], cols, viz_export.column_counts(ch))
        assert len(c["act_t"]) == ch["n_acts"]
        assert np.all(np.diff(c["act_t"]) >= 0) and np.all((c["act_t"] >= ch["t0"]) & (c["act_t"] < ch["t1"]))
        for k in range(len(c["act_t"])):
            rows.append((float(c["act_t"][k]), int(c["act_kind"][k]), int(c["act_type"][k]), int(c["act_person_i"][k]),
                         manifest["origin_lonlat"][0] + float(c["act_dlon"][k]), manifest["origin_lonlat"][1] + float(c["act_dlat"][k])))
    assert len(rows) == len(index.act_t) > 0
    order = np.lexsort((index.act_type, index.act_kind, index.act_t))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    for r, i in zip(rows, order):
        lon, lat = to_ll.transform(float(index.act_x[i]) + ox, float(index.act_y[i]) + oy)
        assert (r[0], r[1], r[2], r[3]) == (float(index.act_t[i]), int(index.act_kind[i]), int(index.act_type[i]), int(index.act_id[i]))
        assert abs(r[4] - lon) < 1e-7 and abs(r[5] - lat) < 1e-7


def test_flash_window_matches_raw_events(index):
    names = [index.meta["act_type_legend"][str(i)] for i in range(len(index.meta["act_type_legend"]))]
    for t, life in FLASHES:
        got = sorted((float(index.act_t[i]), names[int(index.act_type[i])]) for i in viz_engine.flash_window(index, t, life))
        assert got == ref_starts(ROWS, t, life), (t, life)
    assert len(ref_starts(ROWS, 1092, 100)) == 2 and len(ref_starts(ROWS, 4000, 50)) == 0


def test_link_window_stats_match_raw_events(index):
    for t, window in STATS:
        got = viz_engine.link_window_stats(index, t, window)
        n, nf, ln, tt = ref_stats(ROWS, t, window)
        assert list(got["n"]) == list(n) and list(got["nf"]) == list(nf), (t, window)
        assert np.allclose(got["len"], ln) and np.allclose(got["tt"], tt), (t, window)
    # wolny przejazd: 30 s na linku 100 m przy swobodnej 10 m/s to jedna trzecia
    n, nf, ln, tt = ref_stats(ROWS, 2031, 30)
    assert nf[0] == 1 and abs(ln[0] / tt[0] / FREESPEED - 1 / 3) < 1e-9
    # wjazd w połowie linku liczy się do natężenia, nie do prędkości
    n, nf, *_ = ref_stats(ROWS, 3005, 10)
    assert n[2] == 1 and nf[2] == 0


def test_class_filter_in_window_stats(index):
    tlo = viz_engine.link_window_stats(index, 1060, 60, [k for k in index.class_keys if k != "tlo"])
    all_ = viz_engine.link_window_stats(index, 1060, 60)
    assert int(all_["n"].sum()) > int(tlo["n"].sum()) > 0


@pytest.mark.skipif(NODE is None, reason="brak node")
def test_client_matches_python(run, tmp_path):
    p = pl.Player()
    p.open(run, remember=False)
    assert not p.error and p.boot()["flowFactor"] == FLOW_FACTOR
    site_dir = p.write_site(tmp_path / "site").parent
    names = [p.index.meta["act_type_legend"][str(i)] for i in range(len(p.index.meta["act_type_legend"]))]
    expected = {"flowFactor": FLOW_FACTOR, "flashes": [], "stats": []}
    for t, life in FLASHES:
        starts = ref_starts(ROWS, t, life)
        ranked = sorted(((t - te, name) for te, name in starts), key=lambda r: (-r[0], names.index(r[1])))
        expected["flashes"].append({"t": t, "life": life, "types": names, "ages": [r[0] for r in ranked], "names": [r[1] for r in ranked]})
    for t, window in STATS:
        n, nf, ln, tt = ref_stats(ROWS, t, window)
        speed, flow = ref_values(n, nf, ln, tt, window)
        expected["stats"].append({"t": t, "W": window, "n": n.tolist(), "nf": nf.tolist(), "len": ln.tolist(), "tt": tt.tolist(), "speed": speed, "flow": flow})
    exp = tmp_path / "expected.json"
    exp.write_text(json.dumps(expected), encoding="utf-8")
    res = subprocess.run([NODE, str(pl.ROOT / "viz_player" / "tests" / "effects_check.js"), str(site_dir), str(exp)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout)
    assert got["meta"]["hasActs"] and got["meta"]["back"] == 1
    assert sum(r["n_py"] for r in got["flashes"]) >= 5, "test błysków porównuje za mało"
    for r in got["flashes"]:
        assert r["n_js"] == r["n_py"] and r["ok"], r
    for r in got["stats"]:
        assert all(r[k] for k in ("n", "nf", "len", "tt", "speed", "flow")), r


def test_link_attributes_reach_the_site(run, tmp_path):
    p = pl.Player()
    p.open(run, remember=False)
    p.write_site(tmp_path / "site")
    attr = np.fromfile(tmp_path / "site" / "link_attr.bin", "<f4").reshape(-1, 4)
    assert attr.shape == (fx.N_LINKS, 4)
    assert np.allclose(attr, [LENGTH, FREESPEED, CAPACITY, 1.0])
    assert json.loads((tmp_path / "site" / "boot.json").read_text(encoding="utf-8"))["flowFactor"] == FLOW_FACTOR


def test_capacity_is_normalised_to_one_hour(tmp_path):
    assert viz_index.parse_capperiod("00:30:00") == 1800.0 and viz_index.parse_capperiod(None) == 3600.0
    assert viz_index.parse_capperiod("00:00:00") == 3600.0 and viz_index.parse_capperiod("zle") == 3600.0
    # prawdziwa sieć MATSim ma <nodes> i <links capperiod=...>; capacity z capperiod 30 min to dwa razy więcej na godzinę
    xml = fx.network_xml()
    i = xml.index("<link ")
    real = xml[:i].replace("<network>", "<network><nodes>") + '</nodes><links capperiod="00:30:00">' + xml[i:].replace("</network>", "</links></network>")
    run = fx.write_run(tmp_path / "half", [*fx.trip("r1", 1000), *fx.trip("t1", 1030), *fx.trip("c1", 5000)], network=real)
    index = viz_engine.load(run)
    with np.load(run / "viz" / "index.npz") as z:
        assert np.allclose(z["link_capacity"], 2 * CAPACITY) and np.allclose(z["link_lanes"], 1.0)
    assert index.meta["flow_capacity_factor"] == FLOW_FACTOR
    assert viz_index.read_qsim_param(run, "flowCapacityFactor") == FLOW_FACTOR
    assert viz_index.read_qsim_param(run, "storageCapacityFactor") is None
