import json

import numpy as np
import pytest
from pyproj import Transformer

import viz_engine
import viz_export

from . import fixture as fx


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    rows = []
    rows += fx.trip("r1", 1000)
    rows += fx.trip("t1", 1030)
    rows += fx.trip("c1", 5000)
    rows += fx.leg("r1", 8000, 8010)
    return fx.write_run(tmp_path_factory.mktemp("export") / "mini", rows)


@pytest.fixture(scope="module")
def made(run):
    index = viz_engine.load(run)
    manifest = viz_export.build(run, chunk_sec=7)  # krótkie porcje, żeby przejazdy przekraczały granice
    return index, manifest, run / "viz" / "export"


def read_chunk(out, manifest, i):
    ch = manifest["chunks"][i]
    cols = [tuple(c) for c in manifest["chunk_columns"]]
    return viz_export.read_columns(out / ch["file"], cols, viz_export.column_counts(ch))


def client_pose(manifest, chunk, k, t):
    """To samo liczy klient JS: liniowo między węzłami porcji, przesunięcia lon/lat + origin."""
    a, b = chunk["knot_off"][k], chunk["knot_off"][k + 1]
    kt = chunk["knot_t"][a:b]
    j = min(max(int(np.searchsorted(kt, np.float32(t), side="right")) - 1, 0), len(kt) - 2)
    u = (t - float(kt[j])) / max(float(kt[j + 1] - kt[j]), 1e-9)
    dlon = float(chunk["knot_dlon"][a + j]) + u * float(chunk["knot_dlon"][a + j + 1] - chunk["knot_dlon"][a + j])
    dlat = float(chunk["knot_dlat"][a + j]) + u * float(chunk["knot_dlat"][a + j + 1] - chunk["knot_dlat"][a + j])
    return manifest["origin_lonlat"][0] + dlon, manifest["origin_lonlat"][1] + dlat


def test_chunks_reproduce_engine_frame(made):
    index, manifest, out = made
    to_ll = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    ox, oy = manifest["origin_local"]
    checked = 0
    for i, ch in enumerate(manifest["chunks"]):
        chunk = read_chunk(out, manifest, i)
        for t in np.arange(ch["t0"], ch["t1"], 0.5):
            fr = viz_engine.frame(index, float(t), None)
            at = {int(tr): n for n, tr in enumerate(fr.track)}
            for k, tr in enumerate(chunk["track"]):
                tr = int(tr)
                if float(index.track_t0[tr]) <= t <= float(index.track_t1[tr]):
                    assert tr in at, (i, t, tr)
                    lon, lat = client_pose(manifest, chunk, k, float(t))
                    lon2, lat2 = to_ll.transform(float(fr.xy[at[tr], 0]) + ox, float(fr.xy[at[tr], 1]) + oy)
                    assert abs(lon - lon2) < 1e-7 and abs(lat - lat2) < 1e-7, (i, t, tr)
                    checked += 1
            for tr in at:
                assert tr in set(int(v) for v in chunk["track"]) or t >= ch["t1"], (i, t, tr)
    assert checked > 20


def test_knot_overhead_is_small(made):
    index, manifest, _out = made
    assert manifest["n_knots_unique"] == len(index.knot_t)
    assert manifest["n_knots_in_chunks"] >= manifest["n_knots_unique"]
    ntrack_chunks = sum(c["n_tracks"] for c in manifest["chunks"])
    assert manifest["n_knots_in_chunks"] <= manifest["n_knots_unique"] + 2 * ntrack_chunks


def test_tracks_and_persons(made):
    index, manifest, out = made
    cols = [tuple(c) for c in manifest["tracks"]["columns"]]
    tracks = viz_export.read_columns(out / "tracks.bin", cols, [manifest["n_tracks"]] * len(cols))
    assert list(tracks["person_i"]) == list(index.track_person_i)
    assert list(tracks["cls"]) == list(index.track_class)
    assert set(tracks["mode"]) == {0} and manifest["modes"] == ["car"]
    persons = json.loads((out / manifest["persons"]).read_text(encoding="utf-8"))
    assert persons == index.id_text


def test_cache_reused_and_invalidated(made):
    _index, manifest, out = made
    stamp = (out / "manifest.json").stat().st_mtime_ns
    again = viz_export.build(out.parent.parent, chunk_sec=7)
    assert again["source_key"] == manifest["source_key"]
    assert (out / "manifest.json").stat().st_mtime_ns == stamp
    meta = json.loads((out.parent / "meta.json").read_text(encoding="utf-8"))
    meta["origin"] = [meta["origin"][0] + 1000, meta["origin"][1]]
    assert viz_export.source_key(meta, 7) != manifest["source_key"]
