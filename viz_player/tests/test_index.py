import json
import math

import numpy as np

import viz_index

from . import fixture as fx


def _events():
    rows = []
    for k, vid in enumerate(("r1", "c1", "o1", "t1", "h1")):
        rows += fx.trip(vid, 1000 + 10 * k)
    # pojazd spoza konwencji liter i wjazd w środku linku
    rows += [fx.enter("q1", 50, rel="0.25"), fx.leave("q1", 60)]
    return rows


def _load(run_dir):
    meta = json.loads((run_dir / "viz" / "meta.json").read_text(encoding="utf-8"))
    return meta, np.load(run_dir / "viz" / "index.npz", allow_pickle=False)


def _log(run_dir):
    return (run_dir / "viz" / "index.log").read_text(encoding="utf-8")


def test_sample_size(tmp_path):
    run = fx.write_run(tmp_path / "a", [])
    assert viz_index.read_sample_size(run) == 0.25
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / viz_index.CONFIG_NAME).write_text("<config/>", encoding="utf-8")
    assert viz_index.read_sample_size(bare) is None


def test_origin_from_bbox(tmp_path):
    run = fx.write_run(tmp_path / "a", [])
    assert viz_index.network_origin(run / viz_index.NETWORK_NAME) == fx.ORIGIN


def test_build_positions_and_reuse(tmp_path):
    run = fx.write_run(tmp_path / "mini", _events())
    assert viz_index.run(run) == 0
    meta, idx = _load(run)
    try:
        assert meta["sample_size"] == 0.25 and meta["source_run"] == "mini" and meta["crs"] == "EPSG:2180"
        assert meta["format"] == viz_index.FORMAT
        assert meta["origin"] == list(fx.ORIGIN)
        assert set(meta["act_type_legend"].values()) == {"home", "work"}
        assert meta["class_counts"] == {"r": 1, "c": 1, "o": 1, "t": 1, "h": 1, "q": 1}
        home = next(int(k) for k, v in meta["act_type_legend"].items() if v == "home")
        work = next(int(k) for k, v in meta["act_type_legend"].items() if v == "work")
        assert np.all(idx["act_kind"][idx["act_type"] == home] == 0), "home to actend"
        assert np.all(idx["act_kind"][idx["act_type"] == work] == 1), "work to actstart"
        j = int(np.where(idx["track_id"] == "r1")[0][0])
        a, b = int(idx["knot_off"][j]), int(idx["knot_off"][j + 1])
        px, py = viz_index.position_at(idx["knot_t"][a:b], idx["knot_x"][a:b], idx["knot_y"][a:b], 1005.0)
        ex, ey = fx.local(50)
        assert abs(px - ex) < 1e-3 and abs(py - ey) < 1e-3
        k = int(np.where(idx["track_id"] == "q1")[0][0])
        c0 = int(idx["knot_off"][k])
        ex, ey = fx.local(25)
        assert abs(float(idx["knot_x"][c0]) - ex) < 1e-3 and abs(float(idx["knot_y"][c0]) - ey) < 1e-3
        first = int(math.floor((1000 - float(idx["bucket_t0"])) / viz_index.BUCKET_SEC))
        last = int(math.floor((1060 - float(idx["bucket_t0"])) / viz_index.BUCKET_SEC))
        got = set()
        for bkt in range(first, last + 1):
            lo, hi = int(idx["bucket_off"][bkt]), int(idx["bucket_off"][bkt + 1])
            got.update(int(x) for x in idx["bucket_track"][lo:hi])
        assert j in got, "kubełek zawiera r1"
    finally:
        idx.close()
    assert viz_index.run(run) == 0
    log = _log(run)
    assert "reuse" in log and "check OK" in log


def test_origin_change_invalidates(tmp_path, monkeypatch):
    run = fx.write_run(tmp_path / "mini", _events())
    assert viz_index.run(run) == 0
    before = json.loads((run / "viz" / "meta.json").read_text(encoding="utf-8"))["origin"]
    monkeypatch.setattr(viz_index, "ORIGIN_SNAP_M", 100.0)
    assert viz_index.run(run) == 0
    after = json.loads((run / "viz" / "meta.json").read_text(encoding="utf-8"))["origin"]
    assert after != before, "inny origin musi przebudować indeks"
    assert _log(run).count("wrote index.npz") == 2


def test_old_format_is_rebuilt(tmp_path):
    run = fx.write_run(tmp_path / "mini", _events())
    assert viz_index.run(run) == 0
    meta_path = run / "viz" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["format"] = viz_index.FORMAT - 1
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert viz_index.run(run) == 0
    assert json.loads(meta_path.read_text(encoding="utf-8"))["format"] == viz_index.FORMAT
    assert _log(run).count("wrote index.npz") == 2
