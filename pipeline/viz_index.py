"""Rzadki indeks odtwarzacza (D24, krok 1).

Czyta gotowy run i zapisuje output/<run>/viz/index.npz oraz meta.json.
Nic nie zapisuje do MATSim, sieci ani planów. Java i g6_bake.py zostają bez zmian.

Semantyka pozycji jest kopią pipeline/g6_bake.py: cztery typy eventów ruchu,
punkt wjazdu wg relativePosition (brak atrybutu = 1), entered link na węźle from,
left link i leaves traffic na węźle to, długość linku tylko na końcu odcinka.
Dodatkowo na węźle zostaje indeks linku. actstart i actend poza
„car interaction” idą do osobnej tabeli; brak x albo y przerywa budowę.
Prędkość (sufit 30 m/s, jak bake)
liczy silnik klatki w kroku 2 z knot_len i dt. Tu jej nie zapisujemy.

Uruchomienie z katalogu projektu:
  uv run python pipeline/viz_index.py output/g5r6_25pct_s4711
  uv run python pipeline/viz_index.py --self-test

Drugi start przy tym samym sha256 eventów, sieci i tego pliku nie parsuje XML
(log: reuse). Zmiana tego skryptu unieważnia indeks.
Test geometrii: seed 1, trzy przejazdy o więcej niż 8 węzłach, osobny odczyt
eventów, 20 chwil, odległość pozycji od cięciwy linku < 0,5 m.
Kod wyjścia 1, gdy test albo akceptacja runu referencyjnego nie przejdzie.
"""
import argparse
import array
import hashlib
import io
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import zstandard
from lxml import etree

from g6_bake import ORIGIN

EVENTS_NAME = "output_events.xml.zst"
NETWORK_NAME = "output_network.xml.zst"
CONFIG_NAME = "output_config.xml"
BUCKET_SEC = 60
WIN0, WIN1 = 6 * 3600.0, 9 * 3600.0
CLASS_LETTERS = ("r", "c", "o", "t", "h")
CLASS_NAMES = ("mieszkaniec", "przyjeżdżający", "wyjeżdżający", "tło lekkie", "ciężkie")
OTHER_CLASS = 5
MOVEMENT = ("vehicle enters traffic", "entered link", "left link", "vehicle leaves traffic")
FORMAT = 1
# Akceptacja runu zmierzonego 2026-10-20. Inny katalog przechodzi geometrię, nie te liczby.
R6_NAME = "g5r6_25pct_s4711"
R6_TRACKS = 29660
R6_ENTERS_WIN = 6641
R6_PEAK = 961
R6_PEAK_WIN = 849
R6_LINKS = 10383
R6_NODES = 4534
FILE_BUDGET = 200 * 1024 * 1024
PARSE_BUDGET_SEC = 300


class CheckFailed(Exception):
    pass


def log_to(path, message):
    print(message)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def field(line, name):
    key = f'{name}="'
    i = line.find(key)
    if i < 0:
        return None
    j = line.find('"', i + len(key))
    return line[i + len(key):j]


def read_sample_size(run):
    """Pierwsze name=\"sampleSize\", jak convergence.sample_size. Brak: None.

    convergence.py wykonuje się przy imporcie, więc odczyt jest skopiowany.
    """
    path = run / CONFIG_NAME
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    key = 'name="sampleSize" value="'
    i = text.find(key)
    if i < 0:
        return None
    j = text.find('"', i + len(key))
    return float(text[i + len(key):j])


def class_code(vehicle_id):
    if not vehicle_id:
        return OTHER_CLASS
    i = "rcoth".find(vehicle_id[0])
    return i if i >= 0 else OTHER_CLASS


def class_legend():
    legend = {str(i): CLASS_NAMES[i] for i in range(len(CLASS_NAMES))}
    legend[str(OTHER_CLASS)] = "inne"
    return legend


def read_network(path):
    """Węzły i linki. xy to metry względem ORIGIN, jeszcze w float64."""
    nodes = {}
    ids, xy, length, freespeed, types = [], [], [], [], []
    stream = zstandard.ZstdDecompressor().stream_reader(path.open("rb"))
    for _, el in etree.iterparse(stream, tag=("node", "link"), load_dtd=False, no_network=True):
        a = el.attrib
        if el.tag == "node":
            nodes[a["id"]] = (float(a["x"]) - ORIGIN[0], float(a["y"]) - ORIGIN[1])
        else:
            ids.append(a["id"])
            x0, y0 = nodes[a["from"]]
            x1, y1 = nodes[a["to"]]
            xy.append((x0, y0, x1, y1))
            length.append(float(a["length"]))
            freespeed.append(float(a["freespeed"]))
            types.append(next((x.text or "" for x in el.iter("attribute") if x.get("name") == "type"), ""))
        el.clear()
    names = sorted(set(types))
    if len(names) > 255:
        raise CheckFailed(f"za dużo klas dróg: {len(names)}")
    code = {name: i for i, name in enumerate(names)}
    return {
        "id": ids,
        "xy": np.asarray(xy, dtype=np.float64).reshape(-1, 4),
        "length": np.asarray(length, dtype=np.float64),
        "freespeed": np.asarray(freespeed, dtype=np.float64),
        "type": np.asarray([code[name] for name in types], dtype=np.uint8),
        "type_legend": {str(i): name for i, name in enumerate(names)},
        "index": {link_id: i for i, link_id in enumerate(ids)},
        "n_nodes": len(nodes),
    }


def event_lines(path, started, log_path):
    stream = zstandard.ZstdDecompressor().stream_reader(path.open("rb"))
    lines = io.TextIOWrapper(stream, encoding="utf-8", newline="")
    n = 0
    for line in lines:
        i = line.find('type="')
        if i < 0:
            continue
        j = line.find('"', i + 6)
        typ = line[i + 6:j]
        if typ not in MOVEMENT and typ != "actstart" and typ != "actend":
            continue
        n += 1
        if n % 500_000 == 0:
            elapsed = time.perf_counter() - started
            log_to(log_path, f"parse lines={n} sec={elapsed:.1f}")
            if elapsed > PARSE_BUDGET_SEC:
                raise CheckFailed("odczyt eventów przekroczył 5 min, przerywam zanim dojdzie okno")
        yield typ, line


def as_f32(buf):
    if array.array("f").itemsize != 4 or array.array("i").itemsize != 4:
        raise CheckFailed("array 'f'/'i' nie ma 4 bajtów")
    return np.frombuffer(buf, dtype=np.float32).copy()


def as_i32(buf):
    return np.frombuffer(buf, dtype=np.int32).copy()


def build(run, log_path):
    """Jeden przebieg XML. Węzły przejazdu trzymamy do jego końca, potem doklejamy zwartym blokiem.

    Eventy pojazdów są przeplatane, a specyfikacja chce zwarty wycinek knot_off.
    """
    started = time.perf_counter()
    net = read_network(run / NETWORK_NAME)
    link_index = net["index"]
    xy, leng = net["xy"], net["length"]
    knot_t, knot_x, knot_y = array.array("f"), array.array("f"), array.array("f")
    knot_len, knot_link = array.array("f"), array.array("i")
    cur = {}
    track_vid, track_start, track_end = [], [], []
    act_vid, act_type_name = [], []
    act_t, act_kind = array.array("f"), array.array("B")
    act_link, act_x, act_y = array.array("i"), array.array("f"), array.array("f")

    def flush(vehicle):
        knots = cur.pop(vehicle)
        start = len(knot_t)
        for t, x, y, length, li in knots:
            knot_t.append(t)
            knot_x.append(x)
            knot_y.append(y)
            knot_len.append(length)
            knot_link.append(li)
        track_vid.append(vehicle)
        track_start.append(start)
        track_end.append(len(knot_t))

    for typ, line in event_lines(run / EVENTS_NAME, started, log_path):
        t = float(field(line, "time"))
        if typ == "actstart" or typ == "actend":
            act_type = field(line, "actType")
            if act_type == "car interaction":
                continue
            person, link_id = field(line, "person"), field(line, "link")
            if person is None or link_id is None or act_type is None:
                raise CheckFailed(f"czynność bez person/link/actType: {line.strip()[:180]}")
            li = link_index.get(link_id)
            if li is None:
                raise CheckFailed(f"czynność na nieznanym linku {link_id}")
            raw_x, raw_y = field(line, "x"), field(line, "y")
            if raw_x is None or raw_y is None:
                raise CheckFailed(f"czynność bez x/y: {line.strip()[:180]}")
            x, y = float(raw_x) - ORIGIN[0], float(raw_y) - ORIGIN[1]
            act_vid.append(person)
            act_t.append(t)
            act_kind.append(1 if typ == "actstart" else 0)
            act_type_name.append(act_type)
            act_link.append(li)
            act_x.append(x)
            act_y.append(y)
            continue
        vehicle, link_id = field(line, "vehicle"), field(line, "link")
        if vehicle is None or link_id is None:
            raise CheckFailed(f"ruch bez vehicle/link: {line.strip()[:180]}")
        li = link_index.get(link_id)
        if li is None:
            raise CheckFailed(f"ruch na nieznanym linku {link_id}")
        if typ == "vehicle enters traffic":
            if vehicle in cur:
                flush(vehicle)
            rel = field(line, "relativePosition")
            p = 1.0 if rel is None else float(rel)
            x0, y0, x1, y1 = (float(v) for v in xy[li])
            cur[vehicle] = [(t, x0 + p * (x1 - x0), y0 + p * (y1 - y0), 0.0, li)]
        elif vehicle not in cur:
            continue
        elif typ == "entered link":
            cur[vehicle].append((t, float(xy[li, 0]), float(xy[li, 1]), 0.0, li))
        else:
            cur[vehicle].append((t, float(xy[li, 2]), float(xy[li, 3]), float(leng[li]), li))
            if typ == "vehicle leaves traffic":
                flush(vehicle)
    for vehicle in list(cur):
        flush(vehicle)
    knot_t_np = as_f32(knot_t)
    for vid, a, b in zip(track_vid, track_start, track_end):
        if b <= a:
            raise CheckFailed(f"pusty przejazd {vid}")
        if np.any(np.diff(knot_t_np[a:b]) < 0):
            raise CheckFailed(f"czas węzłów maleje, przejazd {vid}")
    return {
        "net": net,
        "knot_t": knot_t_np,
        "knot_x": as_f32(knot_x),
        "knot_y": as_f32(knot_y),
        "knot_len": as_f32(knot_len),
        "knot_link": as_i32(knot_link),
        "track_vid": track_vid,
        "track_start": np.asarray(track_start, dtype=np.int64),
        "track_end": np.asarray(track_end, dtype=np.int64),
        "act_vid": act_vid,
        "act_t": as_f32(act_t),
        "act_kind": np.frombuffer(act_kind, dtype=np.uint8).copy(),
        "act_type_name": act_type_name,
        "act_link": as_i32(act_link),
        "act_x": as_f32(act_x),
        "act_y": as_f32(act_y),
    }


def pack(built, run_name):
    net = built["net"]
    vids = list(built["track_vid"])
    act_vids = list(built["act_vid"])
    id_list = sorted(set(vids) | set(act_vids))
    id_of = {name: i for i, name in enumerate(id_list)}
    n = len(vids)
    if n:
        if int(built["track_start"][0]) != 0 or int(built["track_end"][-1]) != len(built["knot_t"]):
            raise CheckFailed("węzły nie pokrywają tablicy")
        if np.any(built["track_start"][1:] != built["track_end"][:-1]):
            raise CheckFailed("przejazdy nie leżą jeden za drugim")
        knot_off = np.empty(n + 1, dtype=np.int64)
        knot_off[:-1] = built["track_start"]
        knot_off[-1] = built["track_end"][-1]
        track_t0 = built["knot_t"][built["track_start"]]
        track_t1 = built["knot_t"][built["track_end"] - 1]
    else:
        knot_off = np.zeros(1, dtype=np.int64)
        track_t0 = np.zeros(0, np.float32)
        track_t1 = np.zeros(0, np.float32)
    present = [a for a in (built["knot_t"], built["act_t"]) if len(a)]
    if not present:
        raise CheckFailed("brak węzłów i czynności")
    t_min = float(min(np.min(a) for a in present))
    t_max = float(max(np.max(a) for a in present))
    bucket_t0 = math.floor(t_min / BUCKET_SEC) * BUCKET_SEC
    if n:
        b0 = np.floor((track_t0.astype(np.float64) - bucket_t0) / BUCKET_SEC).astype(np.int64)
        b1 = np.floor((track_t1.astype(np.float64) - bucket_t0) / BUCKET_SEC).astype(np.int64)
        if np.any(b0 < 0) or np.any(b1 < b0):
            raise CheckFailed("kubełek czasu wychodzi przed początek indeksu")
        n_buckets = int(b1.max()) + 1
        counts = np.zeros(n_buckets, dtype=np.int64)
        for i in range(n):
            counts[int(b0[i]):int(b1[i]) + 1] += 1
        bucket_off = np.zeros(n_buckets + 1, dtype=np.int64)
        np.cumsum(counts, out=bucket_off[1:])
        bucket_track = np.empty(int(bucket_off[-1]), dtype=np.int32)
        cursor = bucket_off[:-1].copy()
        for i in range(n):
            for k in range(int(b0[i]), int(b1[i]) + 1):
                bucket_track[int(cursor[k])] = i
                cursor[k] += 1
    else:
        bucket_off = np.zeros(1, dtype=np.int64)
        bucket_track = np.zeros(0, dtype=np.int32)
    act_names = sorted(set(built["act_type_name"]))
    if len(act_names) > 65535:
        raise CheckFailed("za dużo typów czynności")
    act_code = {name: i for i, name in enumerate(act_names)}
    if "car interaction" in act_code:
        raise CheckFailed("car interaction w legendzie czynności")
    arrays = {
        "link_id": np.asarray(net["id"], dtype=str),
        "link_xy": net["xy"].astype(np.float32),
        "link_length": net["length"].astype(np.float32),
        "link_freespeed": net["freespeed"].astype(np.float32),
        "link_type": net["type"],
        "ids": np.asarray(id_list, dtype=str),
        "track_id": np.asarray(vids, dtype=str),
        "track_id_i": np.asarray([id_of[v] for v in vids], dtype=np.int32),
        "track_class": np.asarray([class_code(v) for v in vids], dtype=np.uint8),
        "track_t0": np.asarray(track_t0, dtype=np.float32),
        "track_t1": np.asarray(track_t1, dtype=np.float32),
        "knot_off": knot_off,
        "knot_t": built["knot_t"],
        "knot_x": built["knot_x"],
        "knot_y": built["knot_y"],
        "knot_len": built["knot_len"],
        "knot_link": built["knot_link"],
        "bucket_sec": np.int32(BUCKET_SEC),
        "bucket_t0": np.float32(bucket_t0),
        "bucket_off": bucket_off,
        "bucket_track": bucket_track,
        "act_id": np.asarray([id_of[v] for v in act_vids], dtype=np.int32),
        "act_t": built["act_t"],
        "act_kind": built["act_kind"],
        "act_type": np.asarray([act_code[name] for name in built["act_type_name"]], dtype=np.uint16),
        "act_link": built["act_link"],
        "act_x": built["act_x"],
        "act_y": built["act_y"],
    }
    info = {
        "t_min": t_min,
        "t_max": t_max,
        "type_legend": net["type_legend"],
        "act_type_legend": {str(i): name for i, name in enumerate(act_names)},
        "source_run": run_name,
        "n_nodes": net["n_nodes"],
    }
    return arrays, info


def save_index(path, arrays):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("index.writing.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(path)


def position_at(knot_t, knot_x, knot_y, t):
    """Pozycja liniowa między węzłami obejmującymi t. Przy dt = 0 zostaje późniejszy węzeł."""
    n = len(knot_t)
    if n == 1:
        return float(knot_x[0]), float(knot_y[0])
    i = int(np.searchsorted(knot_t, np.float32(t), side="right") - 1)
    i = min(max(i, 0), n - 2)
    t0, t1 = float(knot_t[i]), float(knot_t[i + 1])
    if t1 <= t0:
        return float(knot_x[i + 1]), float(knot_y[i + 1])
    u = (float(t) - t0) / (t1 - t0)
    return (
        float(knot_x[i]) + u * (float(knot_x[i + 1]) - float(knot_x[i])),
        float(knot_y[i]) + u * (float(knot_y[i + 1]) - float(knot_y[i])),
    )


def point_segment_distance(px, py, x0, y0, x1, y1):
    bx, by = x1 - x0, y1 - y0
    den = bx * bx + by * by
    if den < 1e-12:
        return math.hypot(px - x0, py - y0)
    u = max(0.0, min(1.0, ((px - x0) * bx + (py - y0) * by) / den))
    return math.hypot(px - (x0 + u * bx), py - (y0 + u * by))


def long_tracks(idx):
    off = idx["knot_off"]
    return [i for i in range(len(idx["track_id"])) if int(off[i + 1]) - int(off[i]) > 8]


def scan_check(path, wanted, log_path):
    """Osobny odczyt: licznik wjazdów i szczytu oraz sekwencje linków wybranych pojazdów."""
    started = time.perf_counter()
    enters = enters_win = 0
    active = peak = peak_win = 0
    peak_t = peak_win_t = None
    classes = {}
    seq = {vid: [] for vid in wanted}
    for typ, line in event_lines(path, started, log_path):
        if typ not in MOVEMENT:
            continue
        t = float(field(line, "time"))
        vid = field(line, "vehicle") or ""
        if typ == "vehicle enters traffic":
            enters += 1
            active += 1
            letter = vid[0] if vid else "?"
            classes[letter] = classes.get(letter, 0) + 1
            if active > peak:
                peak, peak_t = active, t
            if WIN0 <= t <= WIN1:
                enters_win += 1
                if active > peak_win:
                    peak_win, peak_win_t = active, t
        elif typ == "vehicle leaves traffic":
            active -= 1
        if vid in seq:
            link_id = field(line, "link")
            row = seq[vid]
            if typ in ("entered link", "vehicle enters traffic"):
                row.append([t, None, link_id])
            elif row and row[-1][1] is None:
                row[-1][1] = t
    return {
        "enters": enters,
        "enters_win": enters_win,
        "peak": peak,
        "peak_t": peak_t,
        "peak_win": peak_win,
        "peak_win_t": peak_win_t,
        "classes": classes,
        "sequences": seq,
    }


def geometry_check(idx, net, sequences, pick, log_path):
    ids = idx["ids"]
    for j in pick:
        vid = str(idx["track_id"][j])
        a, b = int(idx["knot_off"][j]), int(idx["knot_off"][j + 1])
        kt, kx, ky = idx["knot_t"][a:b], idx["knot_x"][a:b], idx["knot_y"][a:b]
        t0, t1 = float(kt[0]), float(kt[-1])
        intervals = [row for row in sequences.get(vid, []) if row[1] is not None and row[1] >= t0 and row[0] <= t1]
        if not intervals:
            raise CheckFailed(f"{vid}: osobny odczyt nie dał sekwencji linków")
        worst = 0.0
        for t in np.linspace(t0, t1, 20):
            px, py = position_at(kt, kx, ky, float(t))
            hits = [link for te, tl, link in intervals if te <= float(t) <= tl and link in net["index"]]
            if not hits:
                raise CheckFailed(f"{vid} t={float(t):.3f} poza odcinkami z eventów")
            dist = min(point_segment_distance(px, py, *net["xy"][net["index"][link]]) for link in hits)
            worst = max(worst, dist)
            if dist >= 0.5:
                raise CheckFailed(f"{vid} t={float(t):.3f} link={hits} dist={dist:.3f} m")
        if str(ids[int(idx["track_id_i"][j])]) != vid:
            raise CheckFailed(f"track_id_i nie wskazuje ids: {vid}")
        log_to(log_path, f"check OK {vid}: 20 chwil, najgorzej {worst:.4f} m, linków {len(intervals)}")


def validate(run, index_path, log_path):
    idx = np.load(index_path, allow_pickle=False)
    try:
        return _validate(run, index_path, log_path, idx)
    finally:
        idx.close()


def _validate(run, index_path, log_path, idx):
    net = read_network(run / NETWORK_NAME)
    n = int(len(idx["track_id"]))
    long = long_tracks(idx)
    if len(long) < 3:
        raise CheckFailed(f"za mało przejazdów dłuższych niż 8 węzłów: {len(long)}")
    pick = random.Random(1).sample(long, 3)
    wanted = {str(idx["track_id"][i]) for i in pick}
    log_to(log_path, "validate: osobny odczyt eventów")
    stats = scan_check(run / EVENTS_NAME, wanted, log_path)
    if n != stats["enters"]:
        raise CheckFailed(f"przejazdy {n} != wjazdy z eventów {stats['enters']}")
    enters_win = int(np.count_nonzero((idx["track_t0"] >= WIN0) & (idx["track_t0"] <= WIN1))) if n else 0
    if enters_win != stats["enters_win"]:
        raise CheckFailed(f"wjazdy 6–9 z indeksu {enters_win} != z eventów {stats['enters_win']}")
    letters = {}
    for vid in idx["track_id"]:
        text = str(vid)
        letter = text[0] if text else "?"
        letters[letter] = letters.get(letter, 0) + 1
    if letters != stats["classes"]:
        raise CheckFailed(f"klasy z indeksu {letters} != z eventów {stats['classes']}")
    geometry_check(idx, net, stats["sequences"], pick, log_path)
    size = index_path.stat().st_size
    if size >= FILE_BUDGET:
        raise CheckFailed(f"index.npz ma {size} B, budżet to < {FILE_BUDGET} B")
    if run.name == R6_NAME:
        if n != R6_TRACKS or enters_win != R6_ENTERS_WIN:
            raise CheckFailed(f"R6 przejazdy {n}, wjazdy 6–9 {enters_win}")
        if stats["peak"] != R6_PEAK or stats["peak_win"] != R6_PEAK_WIN:
            raise CheckFailed(
                f"R6 szczyt {stats['peak']} o {stats['peak_t']}, "
                f"w oknie {stats['peak_win']} o {stats['peak_win_t']}")
        if len(idx["link_id"]) != R6_LINKS or net["n_nodes"] != R6_NODES:
            raise CheckFailed(f"R6 sieć linki={len(idx['link_id'])} węzły={net['n_nodes']}")
        for letter in CLASS_LETTERS:
            if letters.get(letter, 0) < 1:
                raise CheckFailed(f"R6 brak klasy {letter}")
        log_to(
            log_path,
            f"R6 OK tracks={n} enters_6_9={enters_win} "
            f"peak={stats['peak']}@{stats['peak_t']} "
            f"peak_6_9={stats['peak_win']}@{stats['peak_win_t']} "
            f"bytes={size} classes={letters}",
        )
    else:
        log_to(
            log_path,
            f"OK tracks={n} enters_6_9={enters_win} peak={stats['peak']} "
            f"peak_6_9={stats['peak_win']} bytes={size} classes={letters}",
        )
    stats["enters_win"] = enters_win
    return stats, letters, size


def write_meta(path, run, ev_sha, net_sha, script_sha, arrays, info, stats, letters, size, build_sec):
    meta = {
        "format": FORMAT,
        "checked": True,
        "events_sha256": ev_sha,
        "network_sha256": net_sha,
        "script_sha256": script_sha,
        "events_bytes": (run / EVENTS_NAME).stat().st_size,
        "network_bytes": (run / NETWORK_NAME).stat().st_size,
        "origin": [ORIGIN[0], ORIGIN[1]],
        "crs": "EPSG:2180",
        "sample_size": read_sample_size(run),
        "t_min": info["t_min"],
        "t_max": info["t_max"],
        "n_tracks": int(len(arrays["track_id"])),
        "n_knots": int(len(arrays["knot_t"])),
        "n_links": int(len(arrays["link_id"])),
        "n_nodes": info["n_nodes"],
        "n_activities": int(len(arrays["act_t"])),
        "max_concurrent": stats["peak"],
        "max_concurrent_time": stats["peak_t"],
        "max_concurrent_6_9": stats["peak_win"],
        "max_concurrent_6_9_time": stats["peak_win_t"],
        "enters_6_9": stats["enters_win"],
        "class_counts": letters,
        "build_sec": round(build_sec, 3),
        "index_bytes": size,
        "class_legend": class_legend(),
        "class_letter": list(CLASS_LETTERS) + ["?"],
        "type_legend": info["type_legend"],
        "act_type_legend": info["act_type_legend"],
        "source_run": info["source_run"],
        "bucket_sec": BUCKET_SEC,
    }
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reuse_meta(viz, ev_sha, net_sha, script_sha):
    meta_path, index_path = viz / "meta.json", viz / "index.npz"
    if not meta_path.exists() or not index_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    same = (
        meta.get("checked") is True
        and meta.get("format") == FORMAT
        and meta.get("events_sha256") == ev_sha
        and meta.get("network_sha256") == net_sha
        and meta.get("script_sha256") == script_sha
    )
    return meta if same else None


def run(run_dir):
    run_dir = Path(run_dir)
    events, network = run_dir / EVENTS_NAME, run_dir / NETWORK_NAME
    if not events.exists() or not network.exists():
        print(f"brak eventów albo sieci w {run_dir}")
        return 1
    viz = run_dir / "viz"
    viz.mkdir(parents=True, exist_ok=True)
    log_path = viz / "index.log"
    t0 = time.perf_counter()
    log_to(log_path, f"--- {time.strftime('%Y-%m-%dT%H:%M:%S')} {run_dir.name} ---")
    hash_t = time.perf_counter()
    ev_sha, net_sha = sha256_file(events), sha256_file(network)
    script_sha = sha256_file(Path(__file__))
    log_to(log_path, f"sha256 sec={time.perf_counter() - hash_t:.1f}")
    cached = reuse_meta(viz, ev_sha, net_sha, script_sha)
    if cached is not None:
        log_to(log_path, f"reuse tracks={cached['n_tracks']} knots={cached['n_knots']} sec={time.perf_counter() - t0:.1f}")
        return 0
    index_path, meta_path = viz / "index.npz", viz / "meta.json"
    try:
        built = build(run_dir, log_path)
        arrays, info = pack(built, run_dir.name)
        save_index(index_path, arrays)
        stats, letters, size = validate(run_dir, index_path, log_path)
        write_meta(meta_path, run_dir, ev_sha, net_sha, script_sha, arrays, info, stats, letters, size,
                   time.perf_counter() - t0)
        log_to(
            log_path,
            f"wrote {index_path.name} bytes={size} knots={len(arrays['knot_t'])} "
            f"activities={len(arrays['act_t'])} sec={time.perf_counter() - t0:.1f}",
        )
    except CheckFailed as exc:
        log_to(log_path, f"FAIL {exc}")
        if index_path.exists():
            index_path.unlink()
        if meta_path.exists():
            meta_path.unlink()
        return 1
    return 0


def write_zst(path, text):
    path.write_bytes(zstandard.ZstdCompressor().compress(text.encode("utf-8")))


def self_test():
    """Mały run: geometria, relativePosition, klasy, brak car interaction, reuse."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="viz_index_") as tmp:
        run_dir = Path(tmp) / "mini"
        run_dir.mkdir()
        nodes = "".join(
            f'<node id="n{i}" x="{ORIGIN[0] + 100 * i}" y="{ORIGIN[1]}"/>' for i in range(7)
        )
        links = "".join(
            f'<link id="l{i}" from="n{i}" to="n{i + 1}" length="100" freespeed="10" '
            f'permlanes="1" capacity="600" oneway="1" modes="car">'
            f'<attributes><attribute name="type" class="java.lang.String">residential</attribute></attributes>'
            f'</link>'
            for i in range(6)
        )
        write_zst(run_dir / NETWORK_NAME, f'<?xml version="1.0"?><network>{nodes}{links}</network>')
        (run_dir / CONFIG_NAME).write_text(
            '<config><module name="qsim"><param name="sampleSize" value="0.25"/></module>'
            '<module name="controler"><param name="flowCapacityFactor" value="1.0"/></module></config>',
            encoding="utf-8",
        )
        if read_sample_size(run_dir) != 0.25:
            raise SystemExit("self-test: sampleSize")
        bare = Path(tmp) / "nosize"
        bare.mkdir()
        (bare / CONFIG_NAME).write_text("<config/>", encoding="utf-8")
        if read_sample_size(bare) is not None:
            raise SystemExit("self-test: brak sampleSize ma być null")

        def trip(vid, t_enter):
            rows = [
                f'<event time="{t_enter - 1}" type="actend" person="{vid}" link="l0" '
                f'x="{ORIGIN[0]}" y="{ORIGIN[1]}" actType="home"/>',
                f'<event time="{t_enter}" type="actstart" person="{vid}" link="l0" '
                f'x="{ORIGIN[0]}" y="{ORIGIN[1]}" actType="car interaction"/>',
                f'<event time="{t_enter}" type="vehicle enters traffic" person="{vid}" vehicle="{vid}" '
                f'link="l0" relativePosition="0"/>',
            ]
            t = t_enter
            for i in range(6):
                t += 10
                rows.append(f'<event time="{t}" type="left link" vehicle="{vid}" link="l{i}"/>')
                if i < 5:
                    rows.append(f'<event time="{t}" type="entered link" vehicle="{vid}" link="l{i + 1}"/>')
            rows.append(f'<event time="{t}" type="vehicle leaves traffic" person="{vid}" vehicle="{vid}" link="l5"/>')
            rows.append(
                f'<event time="{t + 1}" type="actstart" person="{vid}" link="l5" '
                f'x="{ORIGIN[0] + 600}" y="{ORIGIN[1]}" actType="work"/>'
            )
            return rows

        rows = []
        for k, vid in enumerate(("r1", "c1", "o1", "t1", "h1")):
            rows.extend(trip(vid, 1000 + 10 * k))
        rows.append(
            '<event relativePosition="0.25" link="l0" vehicle="q1" type="vehicle enters traffic" time="50"/>'
        )
        rows.append('<event time="60" type="vehicle leaves traffic" vehicle="q1" link="l0"/>')
        # Czas globalny, nie blokami pojazdu: węzły w pliku są przeplatane, jak w MATSim.
        rows.sort(key=lambda line: float(field(line, "time")))
        body = "\n".join(rows)
        write_zst(run_dir / EVENTS_NAME, f'<?xml version="1.0"?>\n<events>\n{body}\n</events>\n')

        def fail_with_log(message):
            log_file = run_dir / "viz" / "index.log"
            if log_file.exists():
                print(log_file.read_text(encoding="utf-8"))
            raise SystemExit(message)

        if run(run_dir) != 0:
            fail_with_log("self-test: pierwsza budowa nie przeszła")
        meta = json.loads((run_dir / "viz" / "meta.json").read_text(encoding="utf-8"))
        if meta["sample_size"] != 0.25 or meta["source_run"] != "mini" or meta["crs"] != "EPSG:2180":
            fail_with_log("self-test: meta")
        if meta["origin"] != [ORIGIN[0], ORIGIN[1]]:
            fail_with_log("self-test: origin")
        if set(meta["act_type_legend"].values()) != {"home", "work"}:
            fail_with_log(f"self-test: czynności {meta['act_type_legend']}")
        for letter in CLASS_LETTERS:
            if meta["class_counts"].get(letter, 0) < 1:
                fail_with_log(f"self-test: brak klasy {letter}")
        if meta["class_counts"].get("q", 0) != 1:
            fail_with_log(f"self-test: klasa q {meta['class_counts']}")
        idx = np.load(run_dir / "viz" / "index.npz", allow_pickle=False)
        try:
            home_code = next(int(k) for k, name in meta["act_type_legend"].items() if name == "home")
            work_code = next(int(k) for k, name in meta["act_type_legend"].items() if name == "work")
            if not np.all(idx["act_kind"][idx["act_type"] == home_code] == 0):
                fail_with_log("self-test: home ma być actend")
            if not np.all(idx["act_kind"][idx["act_type"] == work_code] == 1):
                fail_with_log("self-test: work ma być actstart")
            j = int(np.where(idx["track_id"] == "r1")[0][0])
            a, b = int(idx["knot_off"][j]), int(idx["knot_off"][j + 1])
            px, py = position_at(idx["knot_t"][a:b], idx["knot_x"][a:b], idx["knot_y"][a:b], 1005.0)
            if abs(px - 50.0) > 1e-3 or abs(py) > 1e-3:
                fail_with_log(f"self-test: pozycja r1 o 1005 to {px},{py}")
            k = int(np.where(idx["track_id"] == "q1")[0][0])
            c0 = int(idx["knot_off"][k])
            if abs(float(idx["knot_x"][c0]) - 25.0) > 1e-3 or abs(float(idx["knot_y"][c0])) > 1e-3:
                fail_with_log("self-test: relativePosition 0.25")
            if int(idx["track_class"][k]) != OTHER_CLASS:
                fail_with_log("self-test: klasa q")
            bt0 = float(idx["bucket_t0"])
            first = int(math.floor((1000 - bt0) / BUCKET_SEC))
            last = int(math.floor((1060 - bt0) / BUCKET_SEC))
            got = set()
            for bkt in range(first, last + 1):
                lo, hi = int(idx["bucket_off"][bkt]), int(idx["bucket_off"][bkt + 1])
                got.update(int(x) for x in idx["bucket_track"][lo:hi])
            if j not in got:
                fail_with_log("self-test: kubełek nie zawiera r1")
        finally:
            idx.close()
        if run(run_dir) != 0:
            fail_with_log("self-test: drugie otwarcie")
        log = (run_dir / "viz" / "index.log").read_text(encoding="utf-8")
        if "reuse" not in log or "check OK" not in log:
            fail_with_log("self-test: log bez reuse albo geometrii")
    print("self-test OK")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Rzadki indeks odtwarzacza runu MATSim (D24, krok 1).")
    ap.add_argument("run", nargs="?", help="katalog runu, np. output/g5r6_25pct_s4711")
    ap.add_argument("--self-test", action="store_true", help="syntetyczny run w katalogu tymczasowym")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.self_test:
        return self_test()
    if not args.run:
        ap.print_help()
        return 2
    return run(args.run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
