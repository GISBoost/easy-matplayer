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
