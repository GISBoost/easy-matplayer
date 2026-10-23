import math

import numpy as np

from viz_player import curves

BEND = ([1, 2, 3], np.array([0.0, 100.0, 100.0]), np.array([0.0, 0.0, 100.0]))
CHORD = np.array([0.0, 0.0, 100.0, 100.0])


def _forward():
    return curves.best_chain(BEND, "1", "3", CHORD, 200.0)


def test_between():
    assert curves.between(7, 0) == [7, 6, 5, 4, 3, 2, 1, 0]
    assert curves.between(1, 3) == [1, 2, 3] and curves.between(3, 1) == [3, 2, 1]
    assert curves.between(2, 2) is None


def test_chain_selection():
    straight = ([1, 2, 3], np.array([0.0, 50.0, 100.0]), np.array([0.0, 0.0, 0.0]))
    assert curves.best_chain(straight, "1", "3", np.array([0.0, 0.0, 100.0, 0.0]), 100.0) is None
    forward = _forward()
    back = curves.best_chain(BEND, "3", "1", np.array([100.0, 100.0, 0.0, 0.0]), 200.0)
    assert forward is not None and back is not None and abs(curves.arc_length(forward) - 200) < 1e-6
    assert abs(back[0, 0] - 100) < 1e-6 and abs(back[-1, 0]) < 1e-6 and abs(back[1, 1]) < 1e-6
    assert curves.best_chain(BEND, "1", "3", CHORD, 100.0) is None, "łuk niezgodny z length"


def test_point_at():
    forward = _forward()
    x, y, heading = curves.point_at(forward, 0.5)
    assert abs(x - 100) < 1e-6 and abs(y) < 1e-6 and abs(heading - math.pi / 2) < 1e-6
    assert abs(curves.point_at(forward, 0.25)[2]) < 1e-6


def test_place_follow_nearest():
    c = curves.Curves(np.array([0, 3, 3], dtype=np.int32), _forward())
    chords = np.array([[0.0, 0.0, 100.0, 100.0], [200.0, 0.0, 300.0, 0.0]])
    px, py, _hd, mask = c.place(chords, [0], [50.0], [50.0])
    assert mask[0] and abs(px[0] - 100) < 1e-3 and abs(py[0]) < 1e-3
    path = c.follow(chords, [0.0, 100.0], [0.0, 100.0], [0, 0])
    assert any(abs(p[0] - 100) < 1e-3 and abs(p[1]) < 1e-3 for p in path), "ślad omija róg"
    assert c.nearest(chords, 100.0, 1.0, 5) == 0
    assert c.nearest(chords, 50.0, 50.0, 5) is None, "cięciwa łuku nie jest drogą"
    assert c.nearest(chords, 250.0, 1.0, 5) == 1


def test_cache_needs_same_origin(tmp_path):
    net = tmp_path / "net"
    net.write_bytes(b"x")
    c = curves.Curves(np.array([0, 3], dtype=np.int32), _forward())
    cache = tmp_path / "curves.npz"
    curves.write_cache(cache, c, (525000.0, 485000.0))
    assert curves.read_cache(cache, 1, net, None, (525000.0, 485000.0)) is not None
    assert curves.read_cache(cache, 1, net, None, (526000.0, 485000.0)) is None


def _fake_run(tmp_path, monkeypatch, ways):
    """Run z jednym linkiem o origid 5 (węzły 1 -> 3) i atrapą skanu OSM; zwraca (run, wywołania skanu)."""
    run = tmp_path / "run"
    (run / "viz").mkdir(parents=True)
    (run / "output_network.xml.zst").write_bytes(b"x")
    calls = []
    monkeypatch.setattr(curves, "read_ends", lambda path: (["a"], ["1"], ["3"], ["5"]))
    monkeypatch.setattr(curves, "grab_ways", lambda pbf, wanted: (calls.append(pbf.name), ways)[1])
    return run, calls


def _load(run, pbf):
    import viz_buildings

    original = curves.find_pbf
    curves.find_pbf = lambda: pbf
    try:
        return curves.load(run, np.array(["a"]), np.array([[0.0, 0.0, 100.0, 100.0]]), np.array([200.0]), (0.0, 0.0))
    finally:
        curves.find_pbf = original


def test_load_reports_osm_coverage_and_keys_cache_to_the_file(tmp_path, monkeypatch):
    run, calls = _fake_run(tmp_path, monkeypatch, {})
    pbf = tmp_path / "a.osm.pbf"
    pbf.write_bytes(b"1")
    built, note = _load(run, pbf)
    assert built.n_bent == 0 and "nie pokrywa tej sieci (0 z 1 dróg)" in note, "plik bez dróg sieci: komunikat zamiast pustego rysunku"
    _load(run, pbf)
    assert calls == ["a.osm.pbf"], "ten sam plik: cache, bez ponownego skanu"
    other = tmp_path / "b.osm.pbf"
    other.write_bytes(b"22")
    _load(run, other)
    assert calls == ["a.osm.pbf", "b.osm.pbf"], "inny plik OSM unieważnia cache"
    again, note = _load(run, None)
    assert calls == ["a.osm.pbf", "b.osm.pbf"] and again.found == 0 and again.wanted == 1, "bez pliku (demo) cache jest używany i pamięta pokrycie"


def test_load_counts_found_ways(tmp_path, monkeypatch):
    run, _calls = _fake_run(tmp_path, monkeypatch, {5: BEND})
    pbf = tmp_path / "a.osm.pbf"
    pbf.write_bytes(b"1")
    monkeypatch.setattr(curves, "project", lambda ways, origin, crs: ways)
    built, note = _load(run, pbf)
    assert built.n_bent == 1 and "w pliku OSM 1 z 1 dróg sieci" in note


def test_cache_older_than_network_is_kept_without_pbf_only(tmp_path):
    import os

    net = tmp_path / "net"
    net.write_bytes(b"x")
    c = curves.Curves(np.array([0, 3], dtype=np.int32), _forward())
    cache = tmp_path / "curves.npz"
    curves.write_cache(cache, c, (525000.0, 485000.0))
    os.utime(cache, (1_000_000_000, 1_000_000_000))  # rozpakowanie dema potrafi zostawić cache starszy od sieci
    assert curves.read_cache(cache, 1, net, None, (525000.0, 485000.0)) is not None, "bez pliku OSM nie ma czym przeliczyć"
    assert curves.read_cache(cache, 1, net, tmp_path / "nie-ma.pbf", (525000.0, 485000.0)) is not None
