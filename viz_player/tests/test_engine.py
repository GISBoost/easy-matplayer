import numpy as np
import pytest

import viz_engine
import viz_index

from . import fixture as fx

ALL = ("r", "c", "o", "t", "h", "?")


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    rows = []
    rows += fx.trip("r1", 1000)
    rows += fx.trip("t1", 1030)
    rows += fx.trip("c1", 5000)
    rows += fx.leg("h1", 50, 51)
    rows += fx.leg("r1", 8000, 8010)
    rows += fx.leg("r1b", 9000, 9010)
    run = fx.write_run(tmp_path_factory.mktemp("engine") / "mini", rows)
    return viz_engine.load(run)


def test_pose_inherits_heading_on_zero_move():
    x, y, heading, speed, _link = viz_engine.pose_at(
        np.array([0, 10, 10], np.float32), np.array([0, 100, 100], np.float32),
        np.array([0, 0, 0], np.float32), np.array([0, 100, 0], np.float32),
        np.array([0, 0, 0], np.int32), 10,
    )
    assert (x, y, heading, speed) == (100.0, 0.0, 0.0, 0.0)


def test_lookup(index):
    hits = viz_engine.lookup(index, "r1")
    assert [h["id"] for h in hits] == ["r1", "r1b"]
    assert len(hits[0]["tracks"]) == 2
    assert viz_engine.lookup(index, "") == [] and viz_engine.lookup(index, "brak") == []


def test_knots_exact(index):
    track = viz_engine.lookup(index, "r1")[0]["tracks"][0]
    assert viz_engine.assert_knots(index, track) <= 0.001


def test_frame_position_speed_pick(index):
    track = viz_engine.lookup(index, "r1")[0]["tracks"][0]
    fr = viz_engine.frame(index, 1005, None)
    assert len(fr) == 1 and int(fr.track[0]) == track
    ex, ey = fx.local(50)
    assert abs(float(fr.xy[0, 0]) - ex) < 1e-3 and abs(float(fr.xy[0, 1]) - ey) < 1e-3
    assert abs(float(fr.speed[0]) - 10) < 1e-3 and abs(float(fr.heading[0])) < 1e-6
    assert viz_engine.pick_vehicle(fr, (ex, ey), 0.5) == track
    assert viz_engine.pick_vehicle(fr, (ex, ey + 20), 0.5) is None


def test_class_filter(index):
    both = viz_engine.frame(index, 1030, ALL)
    quiet = viz_engine.frame(index, 1030, ("r", "c", "o", "h"))
    assert len(both) == 2 and len(quiet) == 1
    assert not np.any(quiet.cls == viz_engine.LETTERS["t"])
    with pytest.raises(viz_engine.EngineFailed):
        viz_engine.frame(index, 1030, ("zz",))


def test_speed_cap(index):
    cap = viz_engine.frame(index, 50.5, None)
    ex, _ = fx.local(50)
    assert len(cap) == 1 and abs(float(cap.speed[0]) - 30) < 1e-3 and abs(float(cap.xy[0, 0]) - ex) < 1e-3


def test_links(index):
    ex, ey = fx.local(50)
    assert viz_engine.pick_link(index, (ex, ey + 0.2), 1.0) == 0
    assert viz_engine.pick_link(index, (ex, ey + 30), 1.0) is None
    fr = viz_engine.frame(index, 1005, None)
    assert viz_engine.link_now(fr, 0) == {"n": 1, "speed_mean": 10.0, "speed_median": 10.0}
    assert viz_engine.link_now(fr, 5) == {"n": 0, "speed_mean": None, "speed_median": None}


def test_activities(index):
    acts = viz_engine.activities(index, "r1")
    assert [a["type"] for a in acts] == ["home", "work"]
    assert [a["kind"] for a in acts] == ["actend", "actstart"]
