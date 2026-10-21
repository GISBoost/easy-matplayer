"""Silnik klatki bez okna (D24, krok 2).

Czyta output/<run>/viz/ albo buduje go przez pipeline/viz_index.py.
Nie rysuje, nie czyta XML sam i nic nie zapisuje do MATSim, sieci ani planów.

  uv run python pipeline/viz_engine.py --self-test
  uv run python pipeline/viz_engine.py output/g5r6_25pct_s4711

Pozycja jest liniowa między węzłami. Auto widać w [track_t0, track_t1].
Prędkość: długość końca odcinka / dt, a gdy długość jest 0, to odcinek euklidesowy / dt.
Sufit 30 m/s. Odcinek o zerowym przesunięciu dziedziczy poprzedni kierunek.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

import viz_index

SPEED_CAP = 30.0
DT_FLOOR = 1e-3
RAM_BUDGET = 1 << 30
LETTERS = {ch: i for i, ch in enumerate("rcoth")}
LETTERS["?"] = viz_index.OTHER_CLASS


class EngineFailed(Exception):
    pass


class Frame:
    __slots__ = ("xy", "heading", "speed", "link", "cls", "track")

    def __init__(self, xy, heading, speed, link, cls, track):
        self.xy = xy
        self.heading = heading
        self.speed = speed
        self.link = link
        self.cls = cls
        self.track = track

    def __len__(self):
        return int(len(self.track))


class Index:
    __slots__ = (
        "run_dir", "meta", "nbytes",
        "ids", "id_text", "id_of",
        "track_id", "track_class", "track_t0", "track_t1", "knot_off",
        "knot_t", "knot_x", "knot_y", "knot_len", "knot_link",
        "link_xy",
        "bucket_sec", "bucket_t0", "bucket_off", "bucket_track",
        "act_id", "act_t", "act_kind", "act_type", "act_link", "act_x", "act_y",
        "track_order", "track_off", "act_order", "act_off",
    )

    def __init__(self, run_dir, meta, arrays):
        self.run_dir = Path(run_dir)
        self.meta = meta
        self.nbytes = int(sum(a.nbytes for a in arrays.values()))
        ids = arrays["ids"]
        self.ids = ids
        self.id_text = [str(s) for s in ids]
        self.id_of = {name: i for i, name in enumerate(self.id_text)}
        self.track_id = arrays["track_id"]
        self.track_class = arrays["track_class"]
        self.track_t0 = arrays["track_t0"]
        self.track_t1 = arrays["track_t1"]
        self.knot_off = arrays["knot_off"]
        self.knot_t = arrays["knot_t"]
        self.knot_x = arrays["knot_x"]
        self.knot_y = arrays["knot_y"]
        self.knot_len = arrays["knot_len"]
        self.knot_link = arrays["knot_link"]
        self.link_xy = arrays["link_xy"]
        self.bucket_sec = int(arrays["bucket_sec"])
        self.bucket_t0 = float(arrays["bucket_t0"])
        self.bucket_off = arrays["bucket_off"]
        self.bucket_track = arrays["bucket_track"]
        self.act_id = arrays["act_id"]
        self.act_t = arrays["act_t"]
        self.act_kind = arrays["act_kind"]
        self.act_type = arrays["act_type"]
        self.act_link = arrays["act_link"]
        self.act_x = arrays["act_x"]
        self.act_y = arrays["act_y"]
        n_ids = len(self.id_text)
        self.track_order, self.track_off = _group(arrays["track_id_i"], n_ids, stable=True)
        act_order = np.lexsort((np.arange(len(self.act_t)), self.act_t, arrays["act_id"]))
        self.act_order = act_order.astype(np.int32, copy=False)
        self.act_off = _offsets(arrays["act_id"], n_ids)


def _offsets(keys, n_ids):
    counts = np.bincount(keys.astype(np.int64, copy=False), minlength=n_ids)
    off = np.zeros(n_ids + 1, dtype=np.int64)
    np.cumsum(counts, out=off[1:])
    return off


def _group(keys, n_ids, stable):
    order = np.argsort(keys, kind="stable" if stable else "quicksort").astype(np.int32, copy=False)
    return order, _offsets(keys, n_ids)


def _copy_npz(path):
    with np.load(path, allow_pickle=False) as z:
        return {name: np.array(z[name]) for name in z.files}


def load(run_dir):
    """Buduje albo czyta viz/. Zwraca tablice w RAM, plik npz jest zamknięty."""
    run_dir = Path(run_dir)
    if viz_index.run(run_dir) != 0:
        raise EngineFailed(f"indeks nie powstał: {run_dir}")
    viz = run_dir / "viz"
    arrays = _copy_npz(viz / "index.npz")
    meta = json.loads((viz / "meta.json").read_text(encoding="utf-8"))
    index = Index(run_dir, meta, arrays)
    if index.nbytes >= RAM_BUDGET:
        raise EngineFailed(f"indeks w RAM ma {index.nbytes} B, budżet to < {RAM_BUDGET} B")
    return index


def _allow(classes_on):
    if classes_on is None:
        return None
    allow = np.zeros(viz_index.OTHER_CLASS + 1, dtype=bool)
    for ch in classes_on:
        if ch not in LETTERS:
            raise EngineFailed(f"nieznana klasa {ch!r}")
        allow[LETTERS[ch]] = True
    return allow


def _bucket_tracks(index, t):
    b = int(math.floor((float(t) - index.bucket_t0) / index.bucket_sec))
    n = len(index.bucket_off) - 1
    if b < 0 or b >= n:
        return np.empty(0, dtype=np.int32)
    lo, hi = int(index.bucket_off[b]), int(index.bucket_off[b + 1])
    return index.bucket_track[lo:hi]


def pose_at(kt, kx, ky, kl, ki, t):
    """Pozycja, kierunek, prędkość i link w czasie t. t należy do [pierwszy, ostatni] węzeł."""
    n = len(kt)
    if n == 1:
        return float(kx[0]), float(ky[0]), 0.0, 0.0, int(ki[0])
    j = int(np.searchsorted(kt, np.float32(t), side="right") - 1)
    j = min(max(j, 0), n - 2)
    t0, t1 = float(kt[j]), float(kt[j + 1])
    dt = t1 - t0
    if dt <= 0:
        x, y = float(kx[j + 1]), float(ky[j + 1])
        link = int(ki[j + 1])
    else:
        u = (float(t) - t0) / dt
        x = float(kx[j]) + u * (float(kx[j + 1]) - float(kx[j]))
        y = float(ky[j]) + u * (float(ky[j + 1]) - float(ky[j]))
        link = int(ki[j + 1] if float(t) >= t1 else ki[j])
    heading = 0.0
    k = j
    while k >= 0:
        dx = float(kx[k + 1]) - float(kx[k])
        dy = float(ky[k + 1]) - float(ky[k])
        if dx != 0.0 or dy != 0.0:
            heading = math.atan2(dy, dx)
            break
        k -= 1
    leng = float(kl[j + 1])
    dist = leng if leng > 0.0 else math.hypot(float(kx[j + 1]) - float(kx[j]), float(ky[j + 1]) - float(ky[j]))
    speed = min(dist / max(dt, DT_FLOOR), SPEED_CAP)
    return x, y, heading, speed, link


def frame(index, t, classes_on=None):
    t = float(t)
    cand = _bucket_tracks(index, t)
    if len(cand):
        t0 = index.track_t0[cand]
        t1 = index.track_t1[cand]
        mask = (t0 <= t) & (t <= t1)
        allow = _allow(classes_on)
        if allow is not None:
            mask &= allow[index.track_class[cand]]
        sel = cand[mask]
    else:
        sel = cand
    a = len(sel)
    xy = np.empty((a, 2), dtype=np.float32)
    heading = np.empty(a, dtype=np.float32)
    speed = np.empty(a, dtype=np.float32)
    link = np.empty(a, dtype=np.int32)
    off = index.knot_off
    for n, i in enumerate(sel):
        i = int(i)
        c0, c1 = int(off[i]), int(off[i + 1])
        x, y, h, s, li = pose_at(
            index.knot_t[c0:c1], index.knot_x[c0:c1], index.knot_y[c0:c1],
            index.knot_len[c0:c1], index.knot_link[c0:c1], t,
        )
        xy[n, 0] = x
        xy[n, 1] = y
        heading[n] = h
        speed[n] = s
        link[n] = li
    return Frame(
        xy, heading, speed, link,
        np.array(index.track_class[sel], dtype=np.uint8, copy=True),
        np.array(sel, dtype=np.int32, copy=True),
    )


def _nearest(xy, point, tolerance_m):
    if len(xy) == 0:
        return None
    px, py = float(point[0]), float(point[1])
    d2 = (xy[:, 0].astype(np.float64) - px) ** 2 + (xy[:, 1].astype(np.float64) - py) ** 2
    i = int(np.argmin(d2))
    if d2[i] <= float(tolerance_m) ** 2:
        return i
    return None


def pick_vehicle(frame, xy_screen_to_world, px_tolerance_m):
    """Najbliższy przejazd w metrach. Przy remisie wygrywa wcześniejszy w klatce."""
    i = _nearest(frame.xy, xy_screen_to_world, px_tolerance_m)
    if i is None:
        return None
    return int(frame.track[i])


def pick_link(index, world_xy, px_tolerance_m):
    """Najbliższa cięciwa. Liczone przy kliknięciu, nie w klatce."""
    xy = index.link_xy
    if len(xy) == 0:
        return None
    xy = xy.astype(np.float64, copy=False)
    x0, y0, x1, y1 = xy[:, 0], xy[:, 1], xy[:, 2], xy[:, 3]
    px, py = float(world_xy[0]), float(world_xy[1])
    bx, by = x1 - x0, y1 - y0
    den = bx * bx + by * by
    u = np.zeros(len(xy), dtype=np.float64)
    np.divide((px - x0) * bx + (py - y0) * by, den, out=u, where=den >= 1e-12)
    np.clip(u, 0.0, 1.0, out=u)
    d2 = (px - (x0 + u * bx)) ** 2 + (py - (y0 + u * by)) ** 2
    i = int(np.argmin(d2))
    if d2[i] > float(px_tolerance_m) ** 2:
        return None
    return i


def link_now(frame, link):
    sel = frame.speed[frame.link == int(link)]
    n = int(len(sel))
    if n == 0:
        return {"n": 0, "speed_mean": None, "speed_median": None}
    return {"n": n, "speed_mean": float(np.mean(sel)), "speed_median": float(np.median(sel))}


def lookup(index, query):
    """Dokładne id pierwsze, potem prefiks. Najwyżej 20 id, każde ze swoimi przejazdami."""
    query = str(query)
    if not query:
        return []
    ids = index.ids
    j = int(np.searchsorted(ids, query))
    hits = []
    n = len(index.id_text)
    while j < n and index.id_text[j].startswith(query) and len(hits) < 20:
        a, b = int(index.track_off[j]), int(index.track_off[j + 1])
        hits.append({
            "id": index.id_text[j],
            "tracks": [int(k) for k in index.track_order[a:b]],
        })
        j += 1
    return hits


def activities(index, ident):
    """Czynności id po czasie. car interaction nie wchodzi do indeksu."""
    id_i = index.id_of.get(str(ident))
    if id_i is None:
        return []
    legend = index.meta["act_type_legend"]
    a, b = int(index.act_off[id_i]), int(index.act_off[id_i + 1])
    out = []
    for src in index.act_order[a:b]:
        src = int(src)
        kind = int(index.act_kind[src])
        out.append({
            "t": float(index.act_t[src]),
            "kind": "actstart" if kind == 1 else "actend",
            "type": legend[str(int(index.act_type[src]))],
            "link": int(index.act_link[src]),
            "x": float(index.act_x[src]),
            "y": float(index.act_y[src]),
        })
    return out


def _log(path, message):
    print(message)
    if path is not None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(message + "\n")


def _knot_span(index, track):
    a, b = int(index.knot_off[track]), int(index.knot_off[track + 1])
    return a, b


def _assert_knots(index, track, tol=0.001):
    a, b = _knot_span(index, track)
    worst = 0.0
    for j in range(a, b):
        t = float(index.knot_t[j])
        fr = frame(index, t, None)
        hit = np.where(fr.track == track)[0]
        if len(hit) != 1:
            raise EngineFailed(f"przejazd {track} niewidoczny w swoim węźle t={t}")
        dx = float(fr.xy[hit[0], 0]) - float(index.knot_x[j])
        dy = float(fr.xy[hit[0], 1]) - float(index.knot_y[j])
        worst = max(worst, math.hypot(dx, dy))
        if worst > tol:
            raise EngineFailed(f"węzeł {track} t={t} odchylenie {worst:.4f} m")
    t0 = float(index.track_t0[track])
    t1 = float(index.track_t1[track])
    if track in set(int(k) for k in frame(index, t0 - 1e-3, None).track):
        raise EngineFailed(f"przejazd {track} widoczny przed t0")
    if track in set(int(k) for k in frame(index, t1 + 1e-3, None).track):
        raise EngineFailed(f"przejazd {track} widoczny po t1")
    return worst


def check(run_dir):
    """Akceptacja kroku 2 na gotowym indeksie. Wynik dopisuje viz/engine.log."""
    run_dir = Path(run_dir)
    log_path = run_dir / "viz" / "engine.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    _log(log_path, f"--- {time.strftime('%Y-%m-%dT%H:%M:%S')} {run_dir.name} ---")
    try:
        index = load(run_dir)
        meta = index.meta
        peak_t = float(meta["max_concurrent_time"])
        tick = time.perf_counter()
        full = frame(index, peak_t, ("r", "c", "o", "t", "h", "?"))
        no_t = frame(index, peak_t, ("r", "c", "o", "h", "?"))
        elapsed = time.perf_counter() - tick
        if len(full) != int(meta["max_concurrent"]):
            raise EngineFailed(
                f"filtr pełny {len(full)} != przebieg enter/leave {meta['max_concurrent']} o {peak_t}"
            )
        if len(no_t) >= len(full) or np.any(no_t.cls == LETTERS["t"]):
            raise EngineFailed(f"filtr bez t: {len(no_t)} z {len(full)}")
        if run_dir.name == viz_index.R6_NAME and len(full) != viz_index.R6_PEAK:
            raise EngineFailed(f"R6 szczyt klatki {len(full)}")
        first_r = next(str(s) for s in index.track_id if str(s).startswith("r"))
        hits = lookup(index, first_r)
        if not hits or hits[0]["id"] != first_r or not hits[0]["tracks"]:
            raise EngineFailed(f"lookup {first_r!r} nie zwraca przejazdów")
        want = {int(i) for i in np.where(index.track_id == first_r)[0]}
        if set(hits[0]["tracks"]) != want:
            raise EngineFailed(f"lookup {first_r} ma {hits[0]['tracks']}, indeks {sorted(want)}")
        track = hits[0]["tracks"][0]
        worst = _assert_knots(index, track)
        picked = None
        a, b = _knot_span(index, track)
        for j in range(a, b):
            point = (float(index.knot_x[j]), float(index.knot_y[j]))
            fr = frame(index, float(index.knot_t[j]), None)
            picked = pick_vehicle(fr, point, 0.5)
            if picked == track:
                break
        if picked != track:
            raise EngineFailed(f"pick_vehicle nie zwraca przejazdu {track} ({first_r})")
        home_code = next(int(k) for k, name in meta["act_type_legend"].items() if name == "home")
        src = int(np.flatnonzero(index.act_type == home_code)[0])
        who = index.id_text[int(index.act_id[src])]
        acts = activities(index, who)
        mid = index.link_xy[0]
        link_hit = pick_link(index, ((float(mid[0]) + float(mid[2])) / 2, (float(mid[1]) + float(mid[3])) / 2), 1.0)
        on_link = link_now(full, int(full.link[0]))
        if link_hit is None or on_link["n"] < 1 or on_link["speed_mean"] is None or on_link["speed_mean"] > SPEED_CAP:
            raise EngineFailed(f"pick_link={link_hit} link_now={on_link}")
        types = {row["type"] for row in acts}
        times = [row["t"] for row in acts]
        if "home" not in types or "car interaction" in types or times != sorted(times):
            raise EngineFailed(f"czynności {who}: {types}")
        _log(
            log_path,
            f"check OK full={len(full)} bez_t={len(no_t)} t={peak_t:.1f} "
            f"lookup={first_r} tracks={len(hits[0]['tracks'])} knots_worst={worst:.6f} m "
            f"home={who} frame_sec={elapsed:.3f} bytes={index.nbytes} "
            f"sec={time.perf_counter() - t0:.1f}",
        )
    except EngineFailed as exc:
        _log(log_path, f"FAIL {exc}")
        return 1
    return 0


def self_test():
    import tempfile

    ox, oy = viz_index.ORIGIN
    with tempfile.TemporaryDirectory(prefix="viz_engine_") as tmp:
        run_dir = Path(tmp) / "mini"
        run_dir.mkdir()
        nodes = "".join(
            f'<node id="n{i}" x="{ox + 100 * i}" y="{oy}"/>' for i in range(7)
        )
        links = "".join(
            f'<link id="l{i}" from="n{i}" to="n{i + 1}" length="100" freespeed="10" '
            f'permlanes="1" capacity="600" oneway="1" modes="car">'
            f'<attributes><attribute name="type" class="java.lang.String">residential</attribute></attributes>'
            f'</link>'
            for i in range(6)
        )
        viz_index.write_zst(
            run_dir / viz_index.NETWORK_NAME,
            f'<?xml version="1.0"?><network>{nodes}{links}</network>',
        )
        (run_dir / viz_index.CONFIG_NAME).write_text(
            '<config><module name="qsim"><param name="sampleSize" value="0.25"/></module></config>',
            encoding="utf-8",
        )

        def trip(vid, t_enter):
            rows = [
                f'<event time="{t_enter - 1}" type="actend" person="{vid}" link="l0" '
                f'x="{ox}" y="{oy}" actType="home"/>',
                f'<event time="{t_enter}" type="actstart" person="{vid}" link="l0" '
                f'x="{ox}" y="{oy}" actType="car interaction"/>',
                f'<event time="{t_enter}" type="vehicle enters traffic" person="{vid}" vehicle="{vid}" '
                f'link="l0" relativePosition="0"/>',
            ]
            t = t_enter
            for i in range(6):
                t += 10
                rows.append(f'<event time="{t}" type="left link" vehicle="{vid}" link="l{i}"/>')
                if i < 5:
                    rows.append(f'<event time="{t}" type="entered link" vehicle="{vid}" link="l{i + 1}"/>')
            rows.append(
                f'<event time="{t}" type="vehicle leaves traffic" person="{vid}" vehicle="{vid}" link="l5"/>'
            )
            rows.append(
                f'<event time="{t + 1}" type="actstart" person="{vid}" link="l5" '
                f'x="{ox + 600}" y="{oy}" actType="work"/>'
            )
            return rows

        rows = []
        rows.extend(trip("r1", 1000))
        rows.extend(trip("t1", 1030))
        rows.extend(trip("c1", 5000))
        rows.append(
            f'<event time="50" type="vehicle enters traffic" vehicle="h1" link="l0" relativePosition="0"/>'
        )
        rows.append('<event time="51" type="vehicle leaves traffic" vehicle="h1" link="l0"/>')
        rows.append(
            f'<event time="8000" type="vehicle enters traffic" vehicle="r1" link="l0" relativePosition="0"/>'
        )
        rows.append('<event time="8010" type="vehicle leaves traffic" vehicle="r1" link="l0"/>')
        rows.append(
            f'<event time="9000" type="vehicle enters traffic" vehicle="r1b" link="l0" relativePosition="0"/>'
        )
        rows.append('<event time="9010" type="vehicle leaves traffic" vehicle="r1b" link="l0"/>')
        rows.sort(key=lambda line: float(viz_index.field(line, "time")))
        viz_index.write_zst(
            run_dir / viz_index.EVENTS_NAME,
            '<?xml version="1.0"?>\n<events>\n' + "\n".join(rows) + "\n</events>\n",
        )
        try:
            index = load(run_dir)
        except EngineFailed:
            log_file = run_dir / "viz" / "index.log"
            if log_file.exists():
                print(log_file.read_text(encoding="utf-8"))
            raise
        npz = run_dir / "viz" / "index.npz"
        moved = npz.with_name("index.moved.npz")
        npz.replace(moved)
        moved.replace(npz)

        x, y, heading, speed, _link = pose_at(
            np.array([0, 10, 10], np.float32),
            np.array([0, 100, 100], np.float32),
            np.array([0, 0, 0], np.float32),
            np.array([0, 100, 0], np.float32),
            np.array([0, 0, 0], np.int32),
            10,
        )
        if abs(x - 100) > 1e-6 or abs(y) > 1e-6 or heading != 0.0 or speed != 0.0:
            raise SystemExit(f"self-test: dziedziczenie kierunku {x, y, heading, speed}")

        r_hits = lookup(index, "r1")
        if [hit["id"] for hit in r_hits] != ["r1", "r1b"]:
            raise SystemExit(f"self-test: lookup r1 {r_hits}")
        if len(r_hits[0]["tracks"]) != 2:
            raise SystemExit("self-test: r1 ma dwa przejazdy")
        if lookup(index, "") or lookup(index, "brak"):
            raise SystemExit("self-test: puste lookup")
        track = r_hits[0]["tracks"][0]
        worst = _assert_knots(index, track)
        if worst > 0.001:
            raise SystemExit(f"self-test: węzeł {worst}")
        fr = frame(index, 1005, None)
        if len(fr) != 1 or int(fr.track[0]) != track:
            raise SystemExit(f"self-test: klatka 1005 {list(fr.track)}")
        if abs(float(fr.xy[0, 0]) - 50) > 0.001 or abs(float(fr.xy[0, 1])) > 0.001:
            raise SystemExit(f"self-test: pozycja {fr.xy[0]}")
        if abs(float(fr.speed[0]) - 10) > 1e-3 or abs(float(fr.heading[0])) > 1e-6:
            raise SystemExit(f"self-test: prędkość/kierunek {float(fr.speed[0])} {float(fr.heading[0])}")
        if pick_vehicle(fr, (50.0, 0.0), 0.5) != track or pick_vehicle(fr, (50.0, 20.0), 0.5) is not None:
            raise SystemExit("self-test: pick_vehicle")
        both = frame(index, 1030, ("r", "c", "o", "t", "h", "?"))
        quiet = frame(index, 1030, ("r", "c", "o", "h"))
        if len(both) != 2 or len(quiet) != 1 or np.any(quiet.cls == LETTERS["t"]):
            raise SystemExit(f"self-test: filtr {len(both)} {len(quiet)}")
        try:
            frame(index, 1030, ("zz",))
            raise SystemExit("self-test: zła klasa przeszła")
        except EngineFailed:
            pass
        cap = frame(index, 50.5, None)
        if len(cap) != 1 or abs(float(cap.speed[0]) - 30) > 1e-3 or abs(float(cap.xy[0, 0]) - 50) > 0.001:
            raise SystemExit(f"self-test: sufit prędkości {float(cap.speed[0]) if len(cap) else 'brak'}")
        if pick_link(index, (50.0, 0.2), 1.0) != 0 or pick_link(index, (50.0, 30.0), 1.0) is not None:
            raise SystemExit("self-test: pick_link")
        now = link_now(fr, 0)
        if now != {"n": 1, "speed_mean": 10.0, "speed_median": 10.0}:
            raise SystemExit(f"self-test: link_now {now}")
        if link_now(fr, 5)["n"] != 0 or link_now(fr, 5)["speed_mean"] is not None:
            raise SystemExit("self-test: pusty link")
        acts = activities(index, "r1")
        if [row["type"] for row in acts] != ["home", "work"]:
            raise SystemExit(f"self-test: czynności {[row['type'] for row in acts]}")
        if acts[0]["kind"] != "actend" or acts[1]["kind"] != "actstart":
            raise SystemExit("self-test: rodzaj czynności")
        if "car interaction" in {row["type"] for row in acts}:
            raise SystemExit("self-test: car interaction")
        load(run_dir)
    print("self-test OK")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description="Silnik klatki odtwarzacza runu MATSim, bez okna (D24, krok 2).")
    ap.add_argument("run", nargs="?", help="katalog runu, np. output/g5r6_25pct_s4711")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.self_test:
        return self_test()
    if not args.run:
        ap.print_help()
        return 2
    return check(args.run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
