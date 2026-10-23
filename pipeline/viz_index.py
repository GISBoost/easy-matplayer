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
  uv run --group viz pytest viz_player/tests   (testy indeksu, silnika i okna)

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
import re
import sys
import time
from pathlib import Path

import numpy as np
import zstandard
from lxml import etree

import viz_classes

EVENTS_NAME = "output_events.xml.zst"
NETWORK_NAME = "output_network.xml.zst"
CONFIG_NAME = "output_config.xml"
BUCKET_SEC = 60
WIN0, WIN1 = 6 * 3600.0, 9 * 3600.0
MOVEMENT = ("vehicle enters traffic", "entered link", "left link", "vehicle leaves traffic")
FORMAT = 3
# Początek lokalnego układu (m): środek bbox węzłów sieci, zaokrąglony do ORIGIN_SNAP_M.
ORIGIN_SNAP_M = 1000.0
FILE_BUDGET = 200 * 1024 * 1024
# Limity są ostrzeżeniami: duży run (100%, Łódź) ma się otworzyć, tylko wolniej.
PARSE_BUDGET_SEC = 300


class CheckFailed(Exception):
    pass


class Progress:
    """Postęp dla okna aplikacji: cb(etykieta, ułamek 0..1). Etap ma swój przedział całości, ułamek w etapie z pozycji w pliku."""

    def __init__(self):
        self.cb, self.label, self.lo, self.hi = None, "", 0.0, 0.0

    def start(self, cb):
        self.cb, self.label, self.lo, self.hi = cb, "", 0.0, 0.0

    def phase(self, label, lo, hi):
        self.label, self.lo, self.hi = label, lo, hi
        self._emit(lo)

    def at(self, frac):
        self._emit(self.lo + (self.hi - self.lo) * min(max(frac, 0.0), 1.0))

    def stop(self):
        self._emit(1.0)
        self.cb = None

    def _emit(self, value):
        if self.cb is not None:
            self.cb(self.label, value)


PROG = Progress()


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


DEFAULT_CRS = "EPSG:2180"  # scenariusze Kutna; run bez output_config.xml albo bez coordinateSystem


def read_crs(run):
    """Układ współrzędnych sieci z param coordinateSystem w output_config.xml (np. epsg:3416 -> EPSG:3416). Brak: DEFAULT_CRS."""
    path = run / CONFIG_NAME
    if not path.exists():
        return DEFAULT_CRS
    m = re.search(r'name="coordinateSystem"\s+value="([^"]*)"', path.read_text(encoding="utf-8"))
    if not m or not m.group(1).strip():
        return DEFAULT_CRS
    code = m.group(1).strip()
    if re.fullmatch(r"(?i)epsg:\d+", code):
        return "EPSG:" + code.split(":")[1]
    raise CheckFailed(f"nieobsługiwany coordinateSystem {code!r} w {CONFIG_NAME} (oczekuję kodu EPSG, np. EPSG:2180)")


def network_origin(path):
    """Origin z bbox węzłów sieci (we współrzędnych sieci runu, E, N). Węzły są w pliku przed linkami."""
    xs, ys = [], []
    stream = zstandard.ZstdDecompressor().stream_reader(path.open("rb"))
    for _, el in etree.iterparse(stream, tag=("node", "link"), load_dtd=False, no_network=True):
        if el.tag == "link":
            break
        xs.append(float(el.get("x")))
        ys.append(float(el.get("y")))
        el.clear()
    if not xs:
        raise CheckFailed("sieć bez węzłów, brak origin")
    snap = ORIGIN_SNAP_M
    return (round((min(xs) + max(xs)) / 2 / snap) * snap, round((min(ys) + max(ys)) / 2 / snap) * snap)


def read_network(path, origin):
    """Węzły i linki. xy to metry względem origin, jeszcze w float64."""
    nodes = {}
    ids, xy, length, freespeed, types = [], [], [], [], []
    stream = zstandard.ZstdDecompressor().stream_reader(path.open("rb"))
    for _, el in etree.iterparse(stream, tag=("node", "link"), load_dtd=False, no_network=True):
        a = el.attrib
        if el.tag == "node":
            nodes[a["id"]] = (float(a["x"]) - origin[0], float(a["y"]) - origin[1])
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
    raw = path.open("rb")
    size = max(path.stat().st_size, 1)
    stream = zstandard.ZstdDecompressor().stream_reader(raw)
    lines = io.TextIOWrapper(stream, encoding="utf-8", newline="")
    n = 0
    warned = False
    for line in lines:
        i = line.find('type="')
        if i < 0:
            continue
        j = line.find('"', i + 6)
        typ = line[i + 6:j]
        if typ not in MOVEMENT and typ != "actstart" and typ != "actend":
            continue
        n += 1
        if n % 100_000 == 0:
            PROG.at(raw.tell() / size)
        if n % 500_000 == 0:
            elapsed = time.perf_counter() - started
            log_to(log_path, f"parse lines={n} sec={elapsed:.1f}")
            if elapsed > PARSE_BUDGET_SEC and not warned:
                warned = True
                log_to(log_path, f"UWAGA odczyt eventów trwa już ponad {PARSE_BUDGET_SEC} s (duży run), czekam")
        yield typ, line


def as_f32(buf):
    if array.array("f").itemsize != 4 or array.array("i").itemsize != 4:
        raise CheckFailed("array 'f'/'i' nie ma 4 bajtów")
    return np.frombuffer(buf, dtype=np.float32).copy()


def as_i32(buf):
    return np.frombuffer(buf, dtype=np.int32).copy()


def build(run, log_path, origin):
    """Jeden przebieg XML. Węzły przejazdu trzymamy do jego końca, potem doklejamy zwartym blokiem.

    Eventy pojazdów są przeplatane, a specyfikacja chce zwarty wycinek knot_off.
    """
    started = time.perf_counter()
    net = read_network(run / NETWORK_NAME, origin)
    link_index = net["index"]
    xy, leng = net["xy"], net["length"]
    knot_t, knot_x, knot_y = array.array("f"), array.array("f"), array.array("f")
    knot_len, knot_link = array.array("f"), array.array("i")
    cur = {}
    track_vid, track_person, track_start, track_end = [], [], [], []
    cur_person = {}
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
        track_person.append(cur_person.pop(vehicle))
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
            x, y = float(raw_x) - origin[0], float(raw_y) - origin[1]
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
            cur_person[vehicle] = field(line, "person") or vehicle
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
        "track_person": track_person,
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


def pack(built, run_name, by_person):
    net = built["net"]
    vids = list(built["track_vid"])
    persons = list(built["track_person"])
    act_vids = list(built["act_vid"])
    id_list = sorted(set(persons) | set(act_vids))
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
    keys = [viz_classes.class_key(p, v, by_person) for p, v in zip(persons, vids)]
    table = viz_classes.class_table(keys)
    code = {row["key"]: i for i, row in enumerate(table)}
    arrays = {
        "link_id": np.asarray(net["id"], dtype=str),
        "link_xy": net["xy"].astype(np.float32),
        "link_length": net["length"].astype(np.float32),
        "link_freespeed": net["freespeed"].astype(np.float32),
        "link_type": net["type"],
        "ids": np.asarray(id_list, dtype=str),
        "track_id": np.asarray(vids, dtype=str),
        "track_person_i": np.asarray([id_of[p] for p in persons], dtype=np.int32),
        "track_class": np.asarray([code[k] for k in keys], dtype=np.uint8),
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
        "classes": table,
        "class_source": "plans" if by_person is not None else "id",
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


def scan_check(path, wanted, log_path, by_person):
    """Osobny odczyt: licznik wjazdów i szczytu oraz sekwencje linków wybranych pojazdów."""
    started = time.perf_counter()
    enters = enters_win = 0
    active = peak = peak_win = 0
    peak_t = peak_win_t = None
    classes = {}
    person_of = {}
    seq = {vid: [] for vid in wanted}
    for typ, line in event_lines(path, started, log_path):
        if typ not in MOVEMENT:
            continue
        t = float(field(line, "time"))
        vid = field(line, "vehicle") or ""
        if typ == "vehicle enters traffic":
            enters += 1
            active += 1
            key = viz_classes.class_key(field(line, "person") or vid, vid, by_person)
            classes[key] = classes.get(key, 0) + 1
            if vid in seq:
                person_of[vid] = field(line, "person") or vid
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
        "persons": person_of,
        "sequences": seq,
    }


def geometry_check(idx, net, sequences, persons, pick, log_path):
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
        if str(ids[int(idx["track_person_i"][j])]) != persons[vid]:
            raise CheckFailed(f"track_person_i {vid}: {ids[int(idx['track_person_i'][j])]} != {persons[vid]}")
        log_to(log_path, f"check OK {vid}: 20 chwil, najgorzej {worst:.4f} m, linków {len(intervals)}")


def validate(run, index_path, log_path, origin, table, by_person):
    idx = np.load(index_path, allow_pickle=False)
    try:
        return _validate(run, index_path, log_path, idx, origin, table, by_person)
    finally:
        idx.close()


def _validate(run, index_path, log_path, idx, origin, table, by_person):
    net = read_network(run / NETWORK_NAME, origin)
    n = int(len(idx["track_id"]))
    long = long_tracks(idx)
    if len(long) < 3:
        raise CheckFailed(f"za mało przejazdów dłuższych niż 8 węzłów: {len(long)}")
    pick = random.Random(1).sample(long, 3)
    wanted = {str(idx["track_id"][i]) for i in pick}
    log_to(log_path, "validate: osobny odczyt eventów")
    stats = scan_check(run / EVENTS_NAME, wanted, log_path, by_person)
    if n != stats["enters"]:
        raise CheckFailed(f"przejazdy {n} != wjazdy z eventów {stats['enters']}")
    enters_win = int(np.count_nonzero((idx["track_t0"] >= WIN0) & (idx["track_t0"] <= WIN1))) if n else 0
    if enters_win != stats["enters_win"]:
        raise CheckFailed(f"wjazdy 6–9 z indeksu {enters_win} != z eventów {stats['enters_win']}")
    counts = np.bincount(idx["track_class"], minlength=len(table))
    class_counts = {row["key"]: int(counts[i]) for i, row in enumerate(table)}
    if class_counts != stats["classes"]:
        raise CheckFailed(f"klasy z indeksu {class_counts} != z eventów {stats['classes']}")

    geometry_check(idx, net, stats["sequences"], stats["persons"], pick, log_path)
    size = index_path.stat().st_size
    if size >= FILE_BUDGET:
        log_to(log_path, f"UWAGA index.npz ma {size} B, powyżej orientacyjnych {FILE_BUDGET} B")
    log_to(
        log_path,
        f"OK tracks={n} enters_6_9={enters_win} peak={stats['peak']} "
        f"peak_6_9={stats['peak_win']} bytes={size} classes={class_counts}",
    )
    stats["enters_win"] = enters_win
    return stats, class_counts, size


def write_meta(path, run, ev_sha, net_sha, script_sha, plans_sha, origin, arrays, info, stats, class_counts, size, build_sec):
    meta = {
        "format": FORMAT,
        "checked": True,
        "events_sha256": ev_sha,
        "network_sha256": net_sha,
        "script_sha256": script_sha,
        "events_bytes": (run / EVENTS_NAME).stat().st_size,
        "network_bytes": (run / NETWORK_NAME).stat().st_size,
        "origin": [origin[0], origin[1]],
        "crs": read_crs(run),
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
        "class_counts": class_counts,
        "build_sec": round(build_sec, 3),
        "index_bytes": size,
        "classes": info["classes"],
        "class_source": info["class_source"],
        "plans_sha256": plans_sha,
        "type_legend": info["type_legend"],
        "act_type_legend": info["act_type_legend"],
        "source_run": info["source_run"],
        "bucket_sec": BUCKET_SEC,
    }
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reuse_meta(viz, ev_sha, net_sha, script_sha, plans_sha, origin):
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
        and meta.get("plans_sha256") == plans_sha
        and meta.get("origin") == [origin[0], origin[1]]
    )
    return meta if same else None


def run(run_dir, progress=None):
    """Buduje albo czyta viz/. progress(etykieta, ułamek 0..1) dla okna aplikacji (indeks 100% to ok. 80 s)."""
    PROG.start(progress)
    try:
        return _run(run_dir)
    finally:
        PROG.stop()


def _run(run_dir):
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
    PROG.phase("Sprawdzam pliki runu", 0.0, 0.01)
    hash_t = time.perf_counter()
    ev_sha, net_sha = sha256_file(events), sha256_file(network)
    script_sha = sha256_file(Path(__file__).with_suffix(".py")) + sha256_file(Path(viz_classes.__file__).with_suffix(".py"))  # w paczce PyInstaller __file__ wskazuje nieistniejący .pyc; źródła .py leżą obok jako dane (viz_player/easy-matanimation.spec)
    plans = run_dir / viz_classes.PLANS_NAME
    plans_sha = sha256_file(plans) if plans.exists() else None
    log_to(log_path, f"sha256 sec={time.perf_counter() - hash_t:.1f}")
    try:
        origin = network_origin(network)
    except CheckFailed as exc:
        log_to(log_path, f"FAIL {exc}")
        return 1
    log_to(log_path, f"origin={origin[0]:.0f},{origin[1]:.0f}")
    cached = reuse_meta(viz, ev_sha, net_sha, script_sha, plans_sha, origin)
    if cached is not None:
        log_to(log_path, f"reuse tracks={cached['n_tracks']} knots={cached['n_knots']} sec={time.perf_counter() - t0:.1f}")
        return 0
    index_path, meta_path = viz / "index.npz", viz / "meta.json"
    try:
        PROG.phase("Czytam zdarzenia ruchu", 0.01, 0.64)
        built = build(run_dir, log_path, origin)
        PROG.phase("Zapisuję indeks", 0.64, 0.66)
        by_person = viz_classes.read_person_classes(run_dir)
        arrays, info = pack(built, run_dir.name, by_person)
        save_index(index_path, arrays)
        PROG.phase("Sprawdzam indeks", 0.66, 0.97)
        stats, class_counts, size = validate(run_dir, index_path, log_path, origin, info["classes"], by_person)
        PROG.phase("Zapisuję opis runu", 0.97, 1.0)
        write_meta(meta_path, run_dir, ev_sha, net_sha, script_sha, plans_sha, origin, arrays, info, stats, class_counts, size,
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


def main(argv):
    ap = argparse.ArgumentParser(description="Rzadki indeks odtwarzacza runu MATSim (D24, krok 1).")
    ap.add_argument("run", nargs="?", help="katalog runu, np. output/g5r6_25pct_s4711")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not args.run:
        ap.print_help()
        return 2
    return run(args.run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
