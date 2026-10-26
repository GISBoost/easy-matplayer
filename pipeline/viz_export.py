"""Eksport v2 indeksu runu dla klienta okna (D26, krok 3 planu easy-matplayer).

Z viz/index.npz robi katalog viz/export/: manifest.json, persons.json, tracks.bin
i porcje chunk_NNN.bin z trajektoriami rzadkimi (węzły na wejściach na linki).
Klient ładuje porcje wokół bieżącego czasu i sam interpoluje pozycję. Python nie liczy klatek.

Pozycje są przesunięciami lon/lat względem origin_lonlat (float32 daje wtedy ok. 2 mm),
klient dodaje origin_lonlat w float64. Porcja zawiera dla każdego przejazdu, który ją dotyka, węzły z jej przedziału plus po jednym
węźle po obu stronach, więc jest samowystarczalna, a powtórzone są tylko węzły graniczne.

  uv run python pipeline/viz_export.py output/g5r7b_25pct_s4711
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

FORMAT = 1
CHUNK_SEC = 900
ALIGN = 8
KEY_STEP = 1 << 20  # większe niż czas w s (t_max < 1 048 576), więc klucz track*KEY_STEP + t jest rosnący
MODES = ["car"]  # indeks zna tylko ruch aut po sieci (cztery eventy ruchu); PT, rower i pieszo dojdą z nowymi eventami

TRACK_COLUMNS = [("person_i", "<i4"), ("cls", "u1"), ("mode", "u1"), ("t0", "<f4"), ("t1", "<f4")]
CHUNK_COLUMNS = [
    ("track", "<i4"), ("g0", "<i4"), ("knot_off", "<i4"), ("knot_t", "<f4"), ("knot_dlon", "<f4"),
    ("knot_dlat", "<f4"), ("knot_len", "<f4"), ("knot_link", "<i4"),
]


# liczba elementów kolumn porcji: n = przejazdy porcji, k = jej węzły
CHUNK_COUNTS = ["n", "n", "n+1", "k", "k", "k", "k", "k"]


class ExportFailed(Exception):
    pass


def _pad(nbytes):
    return -nbytes % ALIGN


def write_columns(path, columns, data):
    """Kolumny jedna po drugiej, każda dopełniona do ALIGN bajtów. Zwraca długości w bajtach."""
    sizes = []
    with open(path, "wb") as fh:
        for name, dtype in columns:
            raw = np.ascontiguousarray(data[name], dtype=dtype).tobytes()
            fh.write(raw + b"\0" * _pad(len(raw)))
            sizes.append(len(raw))
    return sizes


def read_columns(path, columns, counts):
    """Odwrotność write_columns (do testów i kontroli). counts: liczba elementów każdej kolumny."""
    raw = Path(path).read_bytes()
    out, pos = {}, 0
    for (name, dtype), n in zip(columns, counts):
        size = n * np.dtype(dtype).itemsize
        out[name] = np.frombuffer(raw, dtype=dtype, count=n, offset=pos).copy()
        pos += size + _pad(size)
    if pos != len(raw):
        raise ExportFailed(f"{path}: {len(raw)} B, oczekiwane {pos} B")
    return out


def source_key(meta, chunk_sec=CHUNK_SEC):
    """Zmiana któregokolwiek z tych pól unieważnia eksport."""
    parts = [
        meta["events_sha256"], meta["network_sha256"], meta["script_sha256"],
        str(meta["plans_sha256"]), str(meta["format"]), json.dumps(meta["origin"]), str(FORMAT), str(chunk_sec),
        hashlib.sha256(Path(__file__).with_suffix(".py").read_bytes()).hexdigest(),  # w paczce PyInstaller __file__ wskazuje nieistniejący .pyc; źródła .py leżą obok jako dane (viz_player/easy-matplayer.spec)
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _gather(start, stop):
    """Indeksy węzłów z przedziałów [start, stop] (włącznie) i offsety wyniku."""
    lens = (stop - start + 1).astype(np.int64)
    new_off = np.zeros(len(start) + 1, dtype=np.int64)
    np.cumsum(lens, out=new_off[1:])
    total = int(new_off[-1])
    idx = np.repeat(start.astype(np.int64) - new_off[:-1], lens) + np.arange(total, dtype=np.int64)
    return idx, new_off


def build(run_dir, out=None, chunk_sec=CHUNK_SEC):
    """Zapisuje eksport. Zwraca manifest. Gdy klucz źródła się zgadza, nic nie przelicza."""
    run_dir = Path(run_dir)
    viz = run_dir / "viz"
    out = Path(out) if out else viz / "export"
    meta = json.loads((viz / "meta.json").read_text(encoding="utf-8"))
    key = source_key(meta, chunk_sec)
    manifest_path = out / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old.get("source_key") == key and all((out / c["file"]).exists() for c in old["chunks"]):
            return old
    with np.load(viz / "index.npz", allow_pickle=False) as z:
        a = {name: np.array(z[name]) for name in z.files}
    ox, oy = meta["origin"]
    to_ll = Transformer.from_crs(meta.get("crs", "EPSG:2180"), "EPSG:4326", always_xy=True)
    lon0, lat0 = (float(v) for v in to_ll.transform(float(ox), float(oy)))
    lon, lat = to_ll.transform(a["knot_x"].astype(np.float64) + ox, a["knot_y"].astype(np.float64) + oy)
    dlon = (np.asarray(lon) - lon0).astype(np.float32)
    dlat = (np.asarray(lat) - lat0).astype(np.float32)

    out.mkdir(parents=True, exist_ok=True)
    for old_file in out.glob("chunk_*.bin"):
        old_file.unlink()
    n_tracks = int(len(a["track_t0"]))
    t0, t1 = a["track_t0"], a["track_t1"]
    tracks = {
        "person_i": a["track_person_i"], "cls": a["track_class"],
        "mode": np.zeros(n_tracks, dtype=np.uint8), "t0": t0, "t1": t1,
    }
    write_columns(out / "tracks.bin", TRACK_COLUMNS, tracks)
    (out / "persons.json").write_text(
        json.dumps([str(s) for s in a["ids"]], ensure_ascii=False, separators=(",", ":")), encoding="utf-8",
    )

    t_min, t_max = float(meta["t_min"]), float(meta["t_max"])
    first = int(np.floor(t_min / chunk_sec))
    last = int(np.floor(t_max / chunk_sec))
    track_of_knot = np.repeat(np.arange(n_tracks, dtype=np.int64), np.diff(a["knot_off"]).astype(np.int64))
    knot_key = track_of_knot * KEY_STEP + a["knot_t"].astype(np.float64)
    chunks, total_knots = [], 0
    for c in range(first, last + 1):
        c0, c1 = c * chunk_sec, (c + 1) * chunk_sec
        sel = np.flatnonzero((t0 < c1) & (t1 >= c0)).astype(np.int64)
        lo, hi = a["knot_off"][sel].astype(np.int64), a["knot_off"][sel + 1].astype(np.int64) - 1
        first_k = np.maximum(np.searchsorted(knot_key, sel * KEY_STEP + c0, side="right") - 1, lo)
        last_k = np.minimum(np.searchsorted(knot_key, sel * KEY_STEP + c1, side="left"), hi)
        idx, off = _gather(first_k, np.maximum(last_k, first_k))
        data = {
            "track": sel, "g0": first_k, "knot_off": off, "knot_t": a["knot_t"][idx], "knot_dlon": dlon[idx],
            "knot_dlat": dlat[idx], "knot_len": a["knot_len"][idx], "knot_link": a["knot_link"][idx],
        }
        name = f"chunk_{c - first:03d}.bin"
        sizes = write_columns(out / name, CHUNK_COLUMNS, data)
        chunks.append({
            "file": name, "t0": c0, "t1": c1, "n_tracks": int(len(sel)), "n_knots": int(len(idx)),
            "bytes": int(sum(sizes) + sum(_pad(s) for s in sizes)),
        })
        total_knots += int(len(idx))
    manifest = {
        "format": FORMAT,
        "source_key": key,
        "source_format": meta["format"],
        "crs": "EPSG:4326",
        "origin_lonlat": [lon0, lat0],
        "origin_local": [ox, oy],
        "t_min": t_min,
        "t_max": t_max,
        "chunk_sec": chunk_sec,
        "modes": MODES,
        "classes": meta["classes"],
        "n_tracks": n_tracks,
        "n_persons": int(len(a["ids"])),
        "n_knots_unique": int(len(a["knot_t"])),
        "n_knots_in_chunks": total_knots,
        "tracks": {"file": "tracks.bin", "columns": TRACK_COLUMNS},
        "persons": "persons.json",
        "chunk_columns": CHUNK_COLUMNS,
        "chunk_counts": CHUNK_COUNTS,
        "align": ALIGN,
        "chunks": chunks,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return manifest


def column_counts(chunk):
    """Liczby elementów kolumn porcji w kolejności CHUNK_COLUMNS."""
    value = {"n": chunk["n_tracks"], "n+1": chunk["n_tracks"] + 1, "k": chunk["n_knots"]}
    return [value[spec] for spec in CHUNK_COUNTS]


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    m = build(argv[0])
    mb = sum(c["bytes"] for c in m["chunks"]) / 1e6
    print(f"export OK: {len(m['chunks'])} porcji, {m['n_tracks']} tras, węzły {m['n_knots_unique']} -> {m['n_knots_in_chunks']}, {mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
