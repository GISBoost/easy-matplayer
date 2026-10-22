"""Generuje viz_player/selftest/kutno_tiny.osm.pbf: jeden budynek w centrum Kutna (do smoke zbudowanego exe, krok „plik OSM”).
Uruchomienie: uv run --group viz python scripts/viz_make_selftest_pbf.py. Plik trafia do paczki jako dane (viz_player/easy-matanimation.spec)."""
from pathlib import Path

import osmium

OUT = Path(__file__).resolve().parents[1] / "viz_player" / "selftest" / "kutno_tiny.osm.pbf"
RING = [(19.3530, 52.2330), (19.3532, 52.2330), (19.3532, 52.2332), (19.3530, 52.2332)]

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.unlink(missing_ok=True)
    with osmium.SimpleWriter(str(OUT)) as w:
        ids = []
        for i, (lon, lat) in enumerate(RING, start=1):
            w.add_node(osmium.osm.mutable.Node(id=i, location=(lon, lat)))
            ids.append(i)
        w.add_way(osmium.osm.mutable.Way(id=1, nodes=ids + [ids[0]], tags={"building": "yes", "height": "12"}))
    print(OUT, OUT.stat().st_size, "B")
