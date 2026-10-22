import json

import pytest

import viz_buildings as vb

from . import fixture as fx

CFG = {"variant": "per_class", "floor_height_m": 3.0, "spread": 0.15, "single_m": 7.0, "default_m": 7.0,
       "h0_m": {"house": 7.0, "apartments": 15.0}}


def test_number_parsing():
    assert vb.number("12") == 12 and vb.number("12,5") == 12.5 and vb.number(" 9 m ") == 9
    assert vb.number("kilka") is None and vb.number(None) is None and vb.number("") is None


def test_spread_is_deterministic_and_bounded():
    assert vb.spread_factor(123, 0.15) == vb.spread_factor(123, 0.15)
    values = [vb.spread_factor(i, 0.15) for i in range(2000)]
    assert 0.85 <= min(values) < 0.9 and 1.1 < max(values) <= 1.15
    assert vb.spread_factor(1, 0.0) == 1.0


def test_height_order_tag_levels_class():
    assert vb.height_of({"height": "20", "building:levels": "3"}, 1, CFG) == (20.0, 0)
    h, src = vb.height_of({"building:levels": "4", "building": "house"}, 1, CFG)
    assert src == 1 and 12 * 0.85 <= h <= 12 * 1.15
    h, src = vb.height_of({"building": "apartments"}, 1, CFG)
    assert src == 2 and 15 * 0.85 <= h <= 15 * 1.15
    assert vb.height_of({"building": "yes"}, 7, CFG)[1] == 2
    assert vb.height_of({"height": "0", "building": "yes"}, 7, CFG)[1] == 2, "zero w tagu to brak wysokości"
    single = dict(CFG, variant="single", single_m=10.0)
    h, src = vb.height_of({"building": "apartments"}, 1, single)
    assert src == 2 and 10 * 0.85 <= h <= 10 * 1.15


@pytest.fixture(scope="module")
def mini_pbf(tmp_path_factory):
    import osmium

    path = tmp_path_factory.mktemp("pbf") / "mini.osm.pbf"
    ring = [(19.40, 52.25), (19.4001, 52.25), (19.4001, 52.2501), (19.40, 52.2501)]
    with osmium.SimpleWriter(str(path)) as w:
        node_id = 1
        ways = [
            (101, {"building": "yes", "height": "20"}, 0.0),
            (102, {"building": "house", "building:levels": "2"}, 0.001),
            (103, {"building": "apartments"}, 0.002),
            (104, {"building": "no"}, 0.003),                 # pominięty
            (105, {"highway": "residential"}, 0.004),         # nie budynek
            (106, {"building": "yes"}, 5.0),                  # poza obwiednią
        ]
        for wid, tags, shift in ways:
            ids = []
            for lon, lat in ring:
                w.add_node(osmium.osm.mutable.Node(id=node_id, location=(lon + shift, lat)))
                ids.append(node_id)
                node_id += 1
            w.add_way(osmium.osm.mutable.Way(id=wid, nodes=ids + [ids[0]], tags=tags))
    return path


def test_build_from_small_pbf(mini_pbf, tmp_path):
    cfg = vb.CONFIG
    box, origin = (19.39, 52.24, 19.42, 52.26), (19.4, 52.25)
    meta = vb.build(tmp_path / "out", box, origin, pbf=mini_pbf, cfg_path=cfg)
    assert meta["n"] == 3 and meta["counts"] == {"tag": 1, "levels": 1, "default": 1}
    off = (tmp_path / "out" / "buildings_off.bin").read_bytes()
    assert len(off) == 4 * 4 and (tmp_path / "out" / "buildings_h.bin").stat().st_size == 3 * 4
    assert (tmp_path / "out" / "buildings_xy.bin").stat().st_size == 12 * 2 * 4, "3 budynki po 4 wierzchołki, bez powtórzonego pierwszego"
    first = json.loads((tmp_path / "out" / "buildings.json").read_text(encoding="utf-8"))
    stamp = (tmp_path / "out" / "buildings.json").stat().st_mtime_ns
    assert vb.build(tmp_path / "out", box, origin, pbf=mini_pbf, cfg_path=cfg)["source_key"] == first["source_key"]
    assert (tmp_path / "out" / "buildings.json").stat().st_mtime_ns == stamp, "cache nie przelicza"
    assert vb.build(tmp_path / "out", box, (19.5, 52.25), pbf=mini_pbf, cfg_path=cfg)["source_key"] != first["source_key"]


def test_no_pbf_means_no_buildings(tmp_path):
    assert vb.build(tmp_path / "out", (0, 0, 1, 1), (0.5, 0.5), pbf=tmp_path / "nie-ma.pbf") is None


def test_saved_buildings_are_used_without_pbf(mini_pbf, tmp_path):
    box, origin = (19.39, 52.24, 19.42, 52.26), (19.4, 52.25)
    built = vb.build(tmp_path / "out", box, origin, pbf=mini_pbf, cfg_path=vb.CONFIG)
    gone = tmp_path / "nie-ma.pbf"
    assert vb.build(tmp_path / "out", box, origin, pbf=gone) == built, "demo bez PBF pokazuje zapisane budynki"
    assert vb.build(tmp_path / "out", (19.0, 52.0, 19.1, 52.1), origin, pbf=gone) is None, "inna sieć: nie podstawiać cudzych budynków"
    assert vb.build(tmp_path / "out", box, (19.5, 52.25), pbf=gone) is None
    (tmp_path / "out" / "buildings_h.bin").unlink()
    assert vb.build(tmp_path / "out", box, origin, pbf=gone) is None, "niekompletne pliki to brak budynków"
