"""Budynki 3D dla okna odtwarzacza (D26, krok 6): wysokości z OSM liczone raz, offline.

Czyta data/raw/osm/lodzkie-*.osm.pbf, bierze zamknięte linie z tagiem `building` w obwiedni sieci runu
i zapisuje je do <out>/ jako pliki binarne dla klienta (nic nie liczy się na klatkę).
Wysokość: `height` > `building:levels` × floor_height_m > H0 klasy `building=*` (config/viz_buildings.toml).
Dla wysokości wyprowadzonej (nie z tagu `height`) dochodzi ±spread z hasha id budynku, więc wynik jest
za każdym razem ten sam. Flaga źródła: 0 tag, 1 piętra, 2 założenie. Wartości H0 i spread to ZAŁOŻENIA.
Nie obsługuje relacji multipolygon (budynki z dziedzińcami): tylko zamknięte linie, obrys zewnętrzny.

  uv run python pipeline/viz_buildings.py output/g5r7b_25pct_s4711
"""
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "viz_buildings.toml"
FORMAT = 1
MARGIN_DEG = 0.003  # ok. 300 m wokół obwiedni sieci
SKIP = {"no", "disused", "construction", "proposed"}
SOURCES = ["tag", "levels", "default"]
NUMBER = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(?:m|meters?)?\s*$", re.I)


def load_config(path=CONFIG):
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


def number(text):
    """Liczba z tagu OSM (`12`, `12,5`, `12 m`) albo None."""
    hit = NUMBER.match(str(text or ""))
    return float(hit.group(1).replace(",", ".")) if hit else None


def spread_factor(osm_id, spread):
    """Mnożnik 1 ± spread, deterministyczny z id budynku."""
    u = int.from_bytes(hashlib.sha1(str(osm_id).encode()).digest()[:4], "big") / 2**32
    return 1.0 + float(spread) * (2.0 * u - 1.0)


def height_of(tags, osm_id, cfg):
    """(wysokość w metrach, indeks w SOURCES)."""
    h = number(tags.get("height"))
    if h is not None and h > 0:
        return h, 0
    levels = number(tags.get("building:levels"))
    if levels is not None and levels > 0:
        return levels * float(cfg["floor_height_m"]) * spread_factor(osm_id, cfg["spread"]), 1
    if cfg["variant"] == "single":
        base = float(cfg["single_m"])
    else:
        base = float(cfg["h0_m"].get(tags.get("building"), cfg["default_m"]))
    return base * spread_factor(osm_id, cfg["spread"]), 2


def find_pbf():
    """Najnowszy lodzkie-*.osm.pbf; w worktree gita szuka też w głównym repo (data/ jest poza gitem)."""
    for base in [ROOT, *ROOT.parents]:
        hits = sorted((base / "data" / "raw" / "osm").glob("lodzkie-*.osm.pbf"))
        if hits:
            return hits[-1]
    return None


def source_key(pbf, cfg_path, box, origin_lonlat):
    st = pbf.stat()
    parts = [
        str(FORMAT), f"{pbf.name}:{st.st_size}:{st.st_mtime_ns}",
        hashlib.sha256(Path(cfg_path).read_bytes()).hexdigest(), json.dumps(box), json.dumps(origin_lonlat),
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def scan(pbf, box, cfg):
    """[(osm_id, lon[], lat[], h, src)] dla budynków, których pierwszy punkt leży w box=(w, s, e, n)."""
    import osmium

    w0, s0, e0, n0 = box
    rows = []

    class Grab(osmium.SimpleHandler):
        def way(self, way):
            tag = way.tags.get("building")
            if tag is None or tag in SKIP or not way.is_closed() or len(way.nodes) < 4:
                return
            try:
                lon = [n.lon for n in way.nodes]
                lat = [n.lat for n in way.nodes]
            except osmium.InvalidLocationError:
                return
            if not (w0 <= lon[0] <= e0 and s0 <= lat[0] <= n0):
                return
            tags = {t.k: t.v for t in way.tags}
            h, src = height_of(tags, way.id, cfg)
            rows.append((int(way.id), lon[:-1], lat[:-1], h, src))

    Grab().apply_file(str(pbf), locations=True)
    return rows


def build(out, box, origin_lonlat, pbf=None, cfg_path=CONFIG):
    """Zapisuje <out>/buildings.json i buildings_*.bin. Zwraca opis albo None, gdy brak PBF."""
    pbf = Path(pbf) if pbf else find_pbf()
    if pbf is None or not pbf.is_file():
        return None
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    key = source_key(pbf, cfg_path, box, origin_lonlat)
    meta_path = out / "buildings.json"
    if meta_path.exists():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if old.get("source_key") == key and all((out / f"buildings_{n}.bin").exists() for n in ("off", "xy", "h", "src")):
            return old
    cfg = load_config(cfg_path)
    rows = scan(pbf, box, cfg)
    lon0, lat0 = origin_lonlat
    off = np.zeros(len(rows) + 1, dtype=np.int32)
    off[1:] = np.cumsum([len(r[1]) for r in rows])
    xy = np.empty((int(off[-1]), 2), dtype=np.float32)
    for i, r in enumerate(rows):
        xy[off[i]:off[i + 1], 0] = np.asarray(r[1], dtype=np.float64) - lon0
        xy[off[i]:off[i + 1], 1] = np.asarray(r[2], dtype=np.float64) - lat0
    h = np.asarray([r[3] for r in rows], dtype=np.float32)
    src = np.asarray([r[4] for r in rows], dtype=np.uint8)
    off.tofile(out / "buildings_off.bin")
    xy.tofile(out / "buildings_xy.bin")
    h.tofile(out / "buildings_h.bin")
    src.tofile(out / "buildings_src.bin")
    meta = {
        "format": FORMAT, "source_key": key, "n": len(rows), "n_vertices": int(off[-1]),
        "origin_lonlat": list(origin_lonlat), "box": list(box), "pbf": pbf.name,
        "sources": SOURCES, "counts": {name: int(np.count_nonzero(src == i)) for i, name in enumerate(SOURCES)},
        "variant": cfg["variant"], "spread": cfg["spread"], "floor_height_m": cfg["floor_height_m"],
        "assumption": "wysokości z flagi „założenie” i „piętra” to ZAŁOŻENIA (config/viz_buildings.toml), nie pomiar",
        "h_median": float(np.median(h)) if len(h) else 0.0,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return meta


def network_box(run_dir):
    """(w, s, e, n) obwiedni sieci runu z marginesem, w stopniach, i origin_lonlat indeksu."""
    from pyproj import Transformer

    viz = Path(run_dir) / "viz"
    meta = json.loads((viz / "meta.json").read_text(encoding="utf-8"))
    with np.load(viz / "index.npz", allow_pickle=False) as z:
        xy = np.asarray(z["link_xy"], dtype=np.float64)
    ox, oy = meta["origin"]
    to_ll = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
    lon, lat = to_ll.transform(np.concatenate([xy[:, 0], xy[:, 2]]) + ox, np.concatenate([xy[:, 1], xy[:, 3]]) + oy)
    lon0, lat0 = (float(v) for v in to_ll.transform(float(ox), float(oy)))
    box = (float(np.min(lon)) - MARGIN_DEG, float(np.min(lat)) - MARGIN_DEG,
           float(np.max(lon)) + MARGIN_DEG, float(np.max(lat)) + MARGIN_DEG)
    return box, (lon0, lat0)


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    run = Path(argv[0])
    box, origin = network_box(run)
    meta = build(run / "viz" / "site" / "data", box, origin)
    if meta is None:
        print("brak PBF w data/raw/osm")
        return 1
    print(f"budynki OK: {meta['n']} (tag {meta['counts']['tag']}, piętra {meta['counts']['levels']}, "
          f"założenie {meta['counts']['default']}), mediana {meta['h_median']:.1f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
