"""Okno odtwarzacza (D24). WebView2 + Leaflet. Panel id ma oś czynności.

Nie parsuje XML. Czyta indeks przez pipeline/viz_engine.py i rysuje klatkę.
Bez klucza CARTO zostają cięciwy na #121418 i zdanie „Podkład wyłączony.”

  uv run python -m viz_player output/g5r6_25pct_s4711
  uv run python -m viz_player --self-test
"""
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import numpy as np
from pyproj import Transformer

import viz_engine

ORIGIN = viz_engine.viz_index.ORIGIN
HERE = Path(__file__).resolve().parent
STATE = ROOT / "output" / "viz_player_state.json"
VMAX = 14.0
START = 6 * 3600
CARTO = "https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}.png?key="
ATTR = "© OpenStreetMap contributors © CARTO"


def clock(t):
    t = max(0, int(math.floor(float(t))))
    hour, rem = divmod(t, 3600)
    minute, sec = divmod(rem, 60)
    return f"{hour:02d}:{minute:02d}:{sec:02d}"


def sample_label(value):
    if value is None:
        return "brak"
    return f"{float(value):.2f}".rstrip("0").rstrip(".").replace(".", ",")


def kmh(mps):
    value = float(mps) * 3.6
    text = f"{value:.0f}" if abs(value - round(value)) < 0.05 else f"{value:.1f}".replace(".", ",")
    return text + " km/h"


def meters(length):
    return f"{float(length):.0f} m"


def auta(n):
    n = int(n)
    if n == 1:
        return "1 auto"
    digit, hundred = n % 10, n % 100
    if 2 <= digit <= 4 and not 12 <= hundred <= 14:
        return f"{n} auta"
    return f"{n} aut"


def ramp_rgb(speed):
    """Te same progi co rampa w shell.html i w blender/g6_load.py (vmax 14 m/s)."""
    u = max(0.0, min(1.0, float(speed) / VMAX))
    red, yellow, cyan = (255, 31, 13), (255, 179, 26), (26, 230, 255)
    if u <= 0.4:
        span, left, right = u / 0.4, red, yellow
    else:
        span, left, right = (u - 0.4) / 0.6, yellow, cyan
    return tuple(int(round(left[i] + (right[i] - left[i]) * span)) for i in range(3))


def covering(rows, t):
    """Czynność obejmująca t. Początkowa, bez actstart, trwa do pierwszego actend."""
    opened = None
    for row in rows:
        if row["t"] > t:
            if opened is not None:
                return opened
            if row is rows[0] and row["kind"] == "actend":
                return row
            return None
        opened = row if row["kind"] == "actstart" else None
    return opened


def _cut(start, end, cuts):
    pieces = [(start, end)]
    for c0, c1 in cuts:
        nxt = []
        for a, b in pieces:
            if c1 <= a or c0 >= b:
                nxt.append((a, b))
                continue
            if a < c0:
                nxt.append((a, c0))
            if c1 < b:
                nxt.append((c1, b))
        pieces = nxt
    return [(a, b) for a, b in pieces if b > a]


def _on_axis(a, b, t, t_max):
    if a <= t < b:
        return True
    return t >= t_max and abs(b - t_max) <= 1e-3 and a < b and a <= t


def schedule(rows, t_min, t_max, trips, t):
    """Odcinki na osi [t_min, t_max]. Jazda bierze się z przejazdów i wycina czynność."""
    t_min, t_max, t = float(t_min), float(t_max), float(t)
    spans = []
    if rows and rows[0]["kind"] == "actend" and t_min < float(rows[0]["t"]):
        spans.append((t_min, float(rows[0]["t"]), rows[0]["type"]))
    for i, row in enumerate(rows):
        if row["kind"] != "actstart":
            continue
        start = float(row["t"])
        end = t_max
        for nxt in rows[i + 1:]:
            if nxt["kind"] == "actend" or float(nxt["t"]) > start:
                end = float(nxt["t"])
                break
        if start < end:
            spans.append((start, end, row["type"]))
    clipped = []
    for a, b in trips:
        a, b = max(float(a), t_min), min(float(b), t_max)
        if b > a:
            clipped.append((a, b))
    out = []
    for a, b, label in spans:
        for c0, c1 in _cut(a, b, clipped):
            out.append({
                "t0": c0, "t1": c1, "label": label, "trip": False,
                "on": _on_axis(c0, c1, t, t_max),
            })
    for a, b in clipped:
        out.append({
            "t0": a, "t1": b, "label": "jazda", "trip": True,
            "on": _on_axis(a, b, t, t_max),
        })
    out.sort(key=lambda seg: seg["t0"])
    return out


def carto_basemap():
    path = ROOT / "config" / "viz_basemap.local.toml"
    if not path.exists():
        return None
    import tomllib
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    key = str(data.get("key") or "").strip()
    if not key or any(ch in key for ch in " \t\r\n/?#&="):
        return None
    return {"url": CARTO + key, "attr": ATTR}


def save_state(run_dir, dest=STATE):
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        stored = Path(run_dir).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        stored = str(Path(run_dir))
    dest.write_text(json.dumps({"run": stored}, ensure_ascii=False) + "\n", encoding="utf-8")


def saved_run():
    if not STATE.exists():
        return None
    try:
        return json.loads(STATE.read_text(encoding="utf-8")).get("run")
    except Exception:
        return None


def _note(run_dir, message):
    print(message)
    if run_dir is None:
        return
    viz = Path(run_dir) / "viz"
    if not viz.is_dir():
        return
    with (viz / "player.log").open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


class Player:
    def __init__(self):
        self.run_dir = None
        self.run_name = ""
        self.error = None
        self.index = None
        self.basemap = None
        self.t = 0.0
        self.classes = ()
        self.chip_letters = []
        self.selected_id = None
        self.selected_link = None
        self.follow = False
        self._key = None
        self._fr = None

    def open(self, run, remember=True):
        self.run_dir = Path(run).resolve()
        self.run_name = self.run_dir.name
        self.error = None
        self.index = None
        self.basemap = carto_basemap()
        self.fwd = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        self.inv = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
        if not self.run_dir.is_dir():
            self.error = f"Brak katalogu runu {self.run_name}."
            return
        missing = []
        if not (self.run_dir / "output_events.xml.zst").exists():
            missing.append("eventów")
        if not (self.run_dir / "output_network.xml.zst").exists():
            missing.append("sieci")
        if missing:
            self.error = "Brak " + " i ".join(missing) + f" w {self.run_name}."
            return
        try:
            self.index = viz_engine.load(self.run_dir)
            self._read_links()
        except viz_engine.EngineFailed as exc:
            self.index = None
            self.error = f"Indeks się nie zbudował: {exc}"
            return
        self._setup()
        if remember:
            save_state(self.run_dir)

    def _read_links(self):
        with np.load(self.run_dir / "viz" / "index.npz", allow_pickle=False) as blob:
            self.link_id = np.array(blob["link_id"])
            self.link_length = np.array(blob["link_length"])
            self.link_freespeed = np.array(blob["link_freespeed"])
            self.link_type = np.array(blob["link_type"])
        if len(self.link_id) != len(self.index.link_xy):
            raise viz_engine.EngineFailed("link_id i link_xy mają różną długość")

    def _setup(self):
        meta = self.index.meta
        t0, t1 = float(meta["t_min"]), float(meta["t_max"])
        self.t = float(START if t0 <= START <= t1 else t0)
        legend = meta["class_legend"]
        self.class_name = {
            "r": legend["0"], "c": legend["1"], "o": legend["2"],
            "t": legend["3"], "h": legend["4"], "?": legend["5"],
        }
        self.letter_of = list(meta["class_letter"])
        types = meta["type_legend"]
        count = max((int(key) for key in types), default=-1) + 1
        self.type_names = [types[str(i)] for i in range(count)]
        other = viz_engine.viz_index.OTHER_CLASS
        self.chip_letters = ["r", "c", "o", "t", "h"]
        if bool(np.any(self.index.track_class == other)):
            self.chip_letters.append("?")
        self.classes = tuple(self.chip_letters)
        self.selected_id = None
        self.selected_link = None
        self.follow = False
        self._key = None
        self.sample = sample_label(meta.get("sample_size"))

    def set_time(self, t):
        t = float(t)
        if self.index is not None:
            t = min(max(t, float(self.index.meta["t_min"])), float(self.index.meta["t_max"]))
        self.t = t

    def set_classes(self, letters):
        letters = str(letters or "")
        for ch in letters:
            if ch not in viz_engine.LETTERS:
                raise viz_engine.EngineFailed(f"nieznana klasa {ch!r}")
        self.classes = tuple(dict.fromkeys(letters))
        self._key = None

    def clear(self):
        self.selected_id = None
        self.selected_link = None
        self.follow = False

    def frame_np(self):
        key = (round(float(self.t), 3), self.classes)
        if key != self._key:
            self._key = key
            self._fr = viz_engine.frame(self.index, float(self.t), self.classes)
        return self._fr

    def local(self, lon, lat):
        east, north = self.inv.transform(float(lon), float(lat))
        return float(east) - ORIGIN[0], float(north) - ORIGIN[1]

    def active_track(self, ident):
        id_i = self.index.id_of.get(str(ident))
        if id_i is None:
            return None
        t = float(self.t)
        a, b = int(self.index.track_off[id_i]), int(self.index.track_off[id_i + 1])
        for raw in self.index.track_order[a:b]:
            k = int(raw)
            if float(self.index.track_t0[k]) <= t <= float(self.index.track_t1[k]):
                return k
        return None

    def link_bits(self, link_i):
        link_i = int(link_i)
        if link_i < 0 or link_i >= len(self.link_id):
            return "?", "?", "?", "?"
        type_i = int(self.link_type[link_i])
        name = self.type_names[type_i] if 0 <= type_i < len(self.type_names) else "?"
        return (
            str(self.link_id[link_i]),
            name,
            meters(self.link_length[link_i]),
            kmh(self.link_freespeed[link_i]),
        )

    def activity_view(self, ident):
        rows = viz_engine.activities(self.index, ident)
        return rows, covering(rows, float(self.t))

    def trips_of(self, ident):
        id_i = self.index.id_of.get(str(ident))
        if id_i is None:
            return []
        a, b = int(self.index.track_off[id_i]), int(self.index.track_off[id_i + 1])
        return [
            (float(self.index.track_t0[int(k)]), float(self.index.track_t1[int(k)]))
            for k in self.index.track_order[a:b]
        ]

    def panel(self):
        if self.index is None:
            return {"kind": "empty", "lines": [self.error or "Brak runu."], "axis": []}
        if self.selected_id is None and self.selected_link is not None:
            return self._link_panel(self.selected_link)
        if self.selected_id is None:
            return {"kind": "empty", "lines": [], "axis": []}
        return self._id_panel(self.selected_id)

    def _id_panel(self, ident):
        rows, cover = self.activity_view(ident)
        axis = schedule(
            rows, self.index.meta["t_min"], self.index.meta["t_max"],
            self.trips_of(ident), self.t,
        )
        track = self.active_track(ident)
        fr = self.frame_np()
        if track is not None:
            hit = np.where(fr.track == track)[0]
            if len(hit):
                i = int(hit[0])
                lid, typ, _leng, free = self.link_bits(int(fr.link[i]))
                letter = self.letter(int(fr.cls[i]))
                return {
                    "kind": "vehicle",
                    "lines": [
                        ident, self.class_name.get(letter, letter), kmh(fr.speed[i]),
                        "link " + lid, typ, "freespeed " + free,
                    ],
                    "axis": axis,
                }
        if cover is not None:
            lid, _typ, _leng, _free = self.link_bits(int(cover["link"]))
            return {
                "kind": "activity",
                "lines": [ident, cover["type"], "link " + lid, "nie jedzie"],
                "axis": axis,
            }
        return {"kind": "idle", "lines": [ident, "nie jedzie"], "axis": axis}

    def _link_panel(self, link_i):
        lid, typ, leng, free = self.link_bits(link_i)
        now = viz_engine.link_now(self.frame_np(), link_i)
        line = "teraz " + auta(now["n"])
        if now["n"]:
            line += ", średnia " + kmh(now["speed_mean"])
        return {
            "kind": "link",
            "lines": [lid, typ, leng, "freespeed " + free, line],
            "axis": [],
        }

    def letter(self, code):
        if 0 <= int(code) < len(self.letter_of):
            return self.letter_of[int(code)]
        return "?"

    def path_latlon(self, track):
        index = self.index
        t = float(self.t)
        a, b = int(index.knot_off[track]), int(index.knot_off[track + 1])
        j = int(np.searchsorted(index.knot_t[a:b], np.float32(t), side="right"))
        j = min(max(j, 1), b - a)
        xs = [float(v) for v in index.knot_x[a:a + j]]
        ys = [float(v) for v in index.knot_y[a:a + j]]
        x, y, _h, _s, _link = viz_engine.pose_at(
            index.knot_t[a:b], index.knot_x[a:b], index.knot_y[a:b],
            index.knot_len[a:b], index.knot_link[a:b], t,
        )
        if abs(xs[-1] - x) > 1e-3 or abs(ys[-1] - y) > 1e-3:
            xs.append(float(x))
            ys.append(float(y))
        lon, lat = self.fwd.transform(np.asarray(xs) + ORIGIN[0], np.asarray(ys) + ORIGIN[1])
        return [[round(float(lat[i]), 6), round(float(lon[i]), 6)] for i in range(len(xs))]

    def payload(self):
        empty = {
            "t": self.t, "clock": clock(self.t), "n": 0,
            "lon": [], "lat": [], "v": [], "hd": [], "heavy": [],
            "sel": None, "path": [], "link": None, "pan": None, "panel": self.panel(),
        }
        if self.index is None:
            return empty
        fr = self.frame_np()
        if len(fr) == 0:
            lon_l, lat_l, speed, heading, heavy = [], [], [], [], []
        else:
            lon, lat = self.fwd.transform(
                fr.xy[:, 0].astype(np.float64) + ORIGIN[0],
                fr.xy[:, 1].astype(np.float64) + ORIGIN[1],
            )
            lon_l = np.round(lon, 6).tolist()
            lat_l = np.round(lat, 6).tolist()
            speed = np.round(fr.speed.astype(np.float64), 3).tolist()
            heading = np.round(fr.heading.astype(np.float64), 4).tolist()
            heavy = (fr.cls == viz_engine.LETTERS["h"]).astype(np.uint8).tolist()
        sel = None
        path = []
        pan = None
        if self.selected_id:
            track = self.active_track(self.selected_id)
            if track is not None and len(fr):
                hit = np.where(fr.track == track)[0]
                if len(hit):
                    sel = int(hit[0])
                    if self.follow:
                        pan = [lat_l[sel], lon_l[sel]]
                path = self.path_latlon(track)
            elif self.follow:
                _rows, cover = self.activity_view(self.selected_id)
                if cover is not None:
                    plon, plat = self.fwd.transform(ORIGIN[0] + float(cover["x"]), ORIGIN[1] + float(cover["y"]))
                    pan = [round(float(plat), 6), round(float(plon), 6)]
        return {
            "t": self.t, "clock": clock(self.t), "n": int(len(fr)),
            "lon": lon_l, "lat": lat_l, "v": speed, "hd": heading, "heavy": heavy,
            "sel": sel, "path": path,
            "link": None if self.selected_id is not None else self.selected_link,
            "pan": pan, "panel": self.panel(),
        }

    def pick(self, lat, lon, lat2, lon2):
        if self.index is None:
            return {"kind": "miss"}
        x, y = self.local(lon, lat)
        x2, y2 = self.local(lon2, lat2)
        tol = max(math.hypot(x2 - x, y2 - y), 0.5)
        track = viz_engine.pick_vehicle(self.frame_np(), (x, y), tol)
        if track is not None:
            self.selected_link = None
            self.follow = False
            self.selected_id = str(self.index.track_id[int(track)])
            return self.panel()
        link = viz_engine.pick_link(self.index, (x, y), tol)
        if link is not None:
            self.selected_id = None
            self.follow = False
            self.selected_link = int(link)
            return self.panel()
        return {"kind": "miss"}

    def lookup(self, query):
        query = str(query).strip()
        if self.index is None or not query:
            return {"hits": []}
        hits = viz_engine.lookup(self.index, query)
        exact = [hit for hit in hits if hit["id"] == query]
        chosen = exact[0] if len(exact) == 1 else (hits[0] if len(hits) == 1 else None)
        if chosen is not None:
            self.selected_id = chosen["id"]
            self.selected_link = None
            self.follow = True
            return {"followed": chosen["id"]}
        return {"hits": [{"id": hit["id"]} for hit in hits]}

    def select(self, ident):
        ident = str(ident)
        if self.index is None or ident not in self.index.id_of:
            return
        self.selected_id = ident
        self.selected_link = None
        self.follow = True

    def boot(self):
        base = {
            "error": self.error, "run": self.run_name, "t": self.t,
            "tMin": 0, "tMax": 1, "sample": "brak", "basemap": self.basemap,
            "bounds": None, "types": [], "classes": [], "links": [],
        }
        if self.index is None:
            return base
        xy = self.index.link_xy
        lon1, lat1 = self.fwd.transform(xy[:, 0].astype(np.float64) + ORIGIN[0], xy[:, 1].astype(np.float64) + ORIGIN[1])
        lon2, lat2 = self.fwd.transform(xy[:, 2].astype(np.float64) + ORIGIN[0], xy[:, 3].astype(np.float64) + ORIGIN[1])
        stack = np.column_stack((
            np.round(lon1, 6), np.round(lat1, 6), np.round(lon2, 6), np.round(lat2, 6),
            self.link_type.astype(np.int16),
        ))
        south = float(min(lat1.min(), lat2.min()))
        north = float(max(lat1.max(), lat2.max()))
        west = float(min(lon1.min(), lon2.min()))
        east = float(max(lon1.max(), lon2.max()))
        base.update({
            "error": None,
            "tMin": float(self.index.meta["t_min"]),
            "tMax": float(self.index.meta["t_max"]),
            "sample": self.sample,
            "bounds": [[south, west], [north, east]],
            "types": self.type_names,
            "classes": [
                {"letter": letter, "name": self.class_name[letter], "on": letter in self.classes}
                for letter in self.chip_letters
            ],
            "links": stack.tolist(),
        })
        return base


class Api:
    def __init__(self, player):
        self._player = player

    def frame(self, t):
        self._player.set_time(t)
        return self._player.payload()

    def pick(self, lat, lon, lat2, lon2):
        return self._player.pick(lat, lon, lat2, lon2)

    def classes(self, letters):
        self._player.set_classes(letters)
        return {"ok": True}

    def lookup(self, query):
        return self._player.lookup(query)

    def select(self, ident):
        self._player.select(ident)
        return {"ok": True}

    def follow(self, on):
        self._player.follow = bool(on) and self._player.selected_id is not None
        return {"ok": True}

    def clear(self):
        self._player.clear()
        return {"ok": True}


def render(player):
    shell = (HERE / "shell.html").read_text(encoding="utf-8")
    css = (HERE / "vendor" / "leaflet.css").read_text(encoding="utf-8")
    js = (HERE / "vendor" / "leaflet.js").read_text(encoding="utf-8")
    boot = json.dumps(player.boot(), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return (
        shell.replace("/*__LEAFLET_CSS__*/", css)
        .replace("/*__LEAFLET_JS__*/", js)
        .replace("__BOOT__", boot)
    )


def _forbid():
    src = (HERE / "player.py").read_text(encoding="utf-8").split("def _forbid", 1)[0]
    blob = src + (HERE / "shell.html").read_text(encoding="utf-8") + (HERE / "__main__.py").read_text(encoding="utf-8")
    for word in ("iterparse", "etree", "zstandard", "tile.openstreetmap.org", "PySide", "g6_bake"):
        if word in blob:
            raise SystemExit(f"self-test: okno zawiera {word}")


def _wgs(player, x, y):
    lon, lat = player.fwd.transform(ORIGIN[0] + x, ORIGIN[1] + y)
    return float(lat), float(lon)


def self_test():
    import tempfile

    _forbid()
    if clock(START) != "06:00:00" or clock(28591) != "07:56:31":
        raise SystemExit(f"self-test: zegar {clock(START)} {clock(28591)}")
    if clock(30 * 3600 + 12 * 60) != "30:12:00" or clock(-5) != "00:00:00":
        raise SystemExit("self-test: zegar poza dobą")
    if sample_label(0.25) != "0,25" or sample_label(None) != "brak":
        raise SystemExit("self-test: próbka")
    if ramp_rgb(0) != (255, 31, 13) or ramp_rgb(VMAX) != (26, 230, 255):
        raise SystemExit(f"self-test: rampa {ramp_rgb(0)} {ramp_rgb(VMAX)}")
    shell = (HERE / "shell.html").read_text(encoding="utf-8")
    for token in ("255, 31, 13", "255, 179, 26", "26, 230, 255", "const VMAX = 14", "grid-column: 1 / -1", 'id="axis"'):
        if token not in shell:
            raise SystemExit(f"self-test: shell bez {token}")
    day = [
        {"t": 100.0, "kind": "actend", "type": "home"},
        {"t": 200.0, "kind": "actstart", "type": "work"},
        {"t": 500.0, "kind": "actend", "type": "work"},
        {"t": 600.0, "kind": "actstart", "type": "home"},
    ]
    full = schedule(day, 0, 800, [(100, 200), (500, 600)], 550)
    expect = [
        ("home", 0.0, 100.0, False),
        ("jazda", 100.0, 200.0, False),
        ("work", 200.0, 500.0, False),
        ("jazda", 500.0, 600.0, True),
        ("home", 600.0, 800.0, False),
    ]
    got = [(seg["label"], seg["t0"], seg["t1"], seg["on"]) for seg in full]
    if got != expect:
        raise SystemExit(f"self-test: oś {got}")
    end = schedule(day, 0, 800, [(100, 200), (500, 600)], 800)
    if not end[-1]["on"] or any(seg["on"] for seg in end[:-1]):
        raise SystemExit(f"self-test: koniec osi {end}")
    cut = schedule([{"t": 200.0, "kind": "actstart", "type": "work"}], 0, 400, [(180, 220)], 200)
    if [(seg["label"], seg["on"]) for seg in cut] != [("jazda", True), ("work", False)]:
        raise SystemExit(f"self-test: jazda wycina czynność {cut}")
    home = {"t": 100.0, "kind": "actend", "type": "home"}
    work = {"t": 200.0, "kind": "actstart", "type": "work"}
    rows = [home, work]
    if covering(rows, 50) is not home or covering(rows, 100) is not None or covering(rows, 150) is not None:
        raise SystemExit("self-test: czynność przed jazdą")
    if covering(rows, 200) is not work or covering(rows, 250) is not work:
        raise SystemExit("self-test: czynność po jeździe")
    if covering([{"t": 10.0, "kind": "actstart", "type": "work"}], 5) is not None:
        raise SystemExit("self-test: czynność z przyszłości")

    vx = viz_engine.viz_index
    ox, oy = ORIGIN
    with tempfile.TemporaryDirectory(prefix="viz_player_") as tmp:
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
        vx.write_zst(run_dir / vx.NETWORK_NAME, f'<?xml version="1.0"?><network>{nodes}{links}</network>')
        (run_dir / vx.CONFIG_NAME).write_text(
            '<config><module name="qsim"><param name="sampleSize" value="0.25"/></module></config>',
            encoding="utf-8",
        )

        def leg(vid, t0, t1):
            return [
                f'<event time="{t0}" type="vehicle enters traffic" person="{vid}" vehicle="{vid}" '
                f'link="l0" relativePosition="0"/>',
                f'<event time="{t1}" type="vehicle leaves traffic" person="{vid}" vehicle="{vid}" link="l0"/>',
            ]

        def long_trip(vid, t_enter):
            rows = [
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
            return rows

        events = [
            f'<event time="23000" type="actend" person="r1" link="l0" x="{ox}" y="{oy}" actType="home"/>',
            *leg("r1", 23000, 23100),
            f'<event time="23100" type="actstart" person="r1" link="l0" x="{ox + 100}" y="{oy}" actType="work"/>',
            *leg("t1", 21600, 21620),
            *leg("h1", 23040, 23060),
            *leg("r1b", 30000, 30010),
            *long_trip("c1", 1000),
            *long_trip("o1", 2000),
            *long_trip("t9", 3000),
        ]
        events.sort(key=lambda line: float(vx.field(line, "time")))
        vx.write_zst(
            run_dir / vx.EVENTS_NAME,
            '<?xml version="1.0"?>\n<events>\n' + "\n".join(events) + "\n</events>\n",
        )
        player = Player()
        player.open(run_dir, remember=False)
        if player.error:
            raise SystemExit(f"self-test: {player.error}")
        if abs(player.t - START) > 1e-6 or player.sample != "0,25":
            raise SystemExit(f"self-test: start {player.t} {player.sample}")
        lat, lon = _wgs(player, 0, 0)
        if abs(lat - 52.2307) > 0.002 or abs(lon - 19.3633) > 0.002:
            raise SystemExit(f"self-test: osie {lat:.4f} {lon:.4f}")
        morning = player.payload()
        if morning["n"] != 1 or morning["clock"] != "06:00:00" or morning["heavy"] != [0]:
            raise SystemExit(f"self-test: 06:00 {morning['n']} {morning['heavy']}")
        player.select("r1")
        home_panel = player.panel()
        if home_panel["kind"] != "activity" or "home" not in home_panel["lines"] or "nie jedzie" not in home_panel["lines"]:
            raise SystemExit(f"self-test: home {home_panel}")
        axis = home_panel["axis"]
        if [seg["label"] for seg in axis] != ["home", "jazda", "work"]:
            raise SystemExit(f"self-test: oś r1 {axis}")
        if not axis[0]["on"] or axis[1]["on"] or axis[2]["on"]:
            raise SystemExit(f"self-test: oś r1 teraz {axis}")
        if axis[1]["t0"] != 23000.0 or axis[1]["t1"] != 23100.0 or axis[1]["trip"] is not True:
            raise SystemExit(f"self-test: jazda r1 {axis[1]}")
        if player.payload()["sel"] is not None or player.payload()["path"]:
            raise SystemExit("self-test: duch na drodze")
        player.set_classes("rcoh")
        if player.payload()["n"] != 0:
            raise SystemExit("self-test: filtr t")
        player.set_classes("rcoth")
        player.t = 23050
        both = player.payload()
        if both["n"] != 2 or sum(both["heavy"]) != 1:
            raise SystemExit(f"self-test: ciężkie {both['n']} {both['heavy']}")
        player.clear()
        player.t = 23010
        lat, lon = _wgs(player, 10, 0)
        lat2, lon2 = _wgs(player, 18, 0)
        picked = player.pick(lat, lon, lat2, lon2)
        if picked["kind"] != "vehicle" or picked["lines"][0] != "r1" or "3,6 km/h" not in picked["lines"]:
            raise SystemExit(f"self-test: klik auta {picked}")
        if len(player.payload()["path"]) < 2:
            raise SystemExit("self-test: ślad")
        lat, lon = _wgs(player, 80, 3)
        lat2, lon2 = _wgs(player, 88, 3)
        road = player.pick(lat, lon, lat2, lon2)
        if road["kind"] != "link" or "residential" not in road["lines"] or "freespeed 36 km/h" not in road["lines"]:
            raise SystemExit(f"self-test: klik linku {road}")
        if "teraz 1 auto" not in road["lines"][-1]:
            raise SystemExit(f"self-test: liczba na linku {road['lines']}")
        player.t = 24000
        player.select("r1")
        later = player.panel()
        if later["kind"] != "activity" or "work" not in later["lines"]:
            raise SystemExit(f"self-test: praca {later}")
        if not any(seg["label"] == "work" and seg["on"] for seg in later["axis"]):
            raise SystemExit(f"self-test: oś pracy {later['axis']}")
        if player.lookup("r1").get("followed") != "r1":
            raise SystemExit("self-test: dokładne id")
        many = player.lookup("r")
        if {hit["id"] for hit in many.get("hits", [])} != {"r1", "r1b"}:
            raise SystemExit(f"self-test: prefiks {many}")
        missing = Player()
        missing.open(Path(tmp) / "nie-ma", remember=False)
        if not missing.error or "Brak katalogu" not in missing.error:
            raise SystemExit(f"self-test: brak katalogu {missing.error}")
        dest = Path(tmp) / "state.json"
        save_state(ROOT / "output" / "g5r6_25pct_s4711", dest)
        if json.loads(dest.read_text(encoding="utf-8"))["run"] != "output/g5r6_25pct_s4711":
            raise SystemExit("self-test: stan")
        page = render(player)
        if "tile.openstreetmap.org" in page or "__BOOT__" not in page and "mapReady" not in page:
            raise SystemExit("self-test: strona")
        if "__BOOT__" in page or "Podkład wyłączony." not in page:
            raise SystemExit("self-test: szablon")
        basemap = player.boot()["basemap"]
        if basemap is not None and not str(basemap.get("url", "")).startswith(CARTO):
            raise SystemExit("self-test: host kafelków")
    print("self-test OK")
    return 0


def check(run):
    player = Player()
    player.open(run)
    if player.error:
        _note(player.run_dir if player.run_dir and player.run_dir.exists() else None, f"FAIL {player.error}")
        return 1
    meta = player.index.meta
    problems = []

    def need(cond, message):
        if not cond:
            problems.append(message)

    lon, lat = player.fwd.transform(ORIGIN[0], ORIGIN[1])
    boot = player.boot()
    need(player.sample == "0,25", f"próbka {player.sample}")
    need(abs(player.t - START) < 1e-6, f"start {player.t}")
    need(abs(lat - 52.2307) < 0.002 and abs(lon - 19.3633) < 0.002, f"osie {lat:.4f} {lon:.4f}")
    need(len(boot["links"]) == int(meta["n_links"]), f"linki {len(boot['links'])} {meta['n_links']}")
    south, west = boot["bounds"][0]
    north, east = boot["bounds"][1]
    need(south < 52.23 < north and west < 19.36 < east, f"zasięg {boot['bounds']}")
    url = "" if boot["basemap"] is None else str(boot["basemap"].get("url", ""))
    need(boot["basemap"] is None or url.startswith(CARTO), "host kafelków")
    need("openstreetmap.org" not in url, "kafelki OSM")
    player.t = float(meta["max_concurrent_time"])
    peak = player.payload()
    need(peak["n"] == int(meta["max_concurrent"]), f"szczyt {peak['n']} != {meta['max_concurrent']}")
    player.t = float(meta["max_concurrent_6_9_time"])
    window = player.payload()
    need(window["n"] == int(meta["max_concurrent_6_9"]), f"okno 6–9 {window['n']} != {meta['max_concurrent_6_9']}")
    need(window["clock"] == clock(meta["max_concurrent_6_9_time"]), f"zegar {window['clock']}")
    player.set_classes("".join(ch for ch in player.chip_letters if ch != "t"))
    thin = player.payload()
    need(thin["n"] < window["n"], f"filtr t {thin['n']} przy {window['n']}")
    player.set_classes("".join(player.chip_letters))
    player.t = float(meta["max_concurrent_6_9_time"])
    frame = player.frame_np()
    if len(frame) == 0:
        problems.append("pusta klatka 6–9")
    else:
        link = int(np.bincount(frame.link).argmax())
        player.selected_id = None
        player.selected_link = link
        panel = player.panel()
        need(panel["kind"] == "link" and not panel["lines"][-1].startswith("teraz 0"), f"link {panel['lines']}")
    followed = player.lookup("r6510903_5")
    need(followed.get("followed") == "r6510903_5", f"lookup {followed}")
    axis = player.panel().get("axis") or []
    need(len(axis) >= 2 and any(seg["trip"] for seg in axis), f"oś {len(axis)}")
    need(sum(bool(seg["on"]) for seg in axis) <= 1, "oś: dwie naraz")
    need([seg["t0"] for seg in axis] == sorted(seg["t0"] for seg in axis), "oś nie po czasie")
    if problems:
        _note(player.run_dir, "FAIL " + "; ".join(problems))
        return 1
    base = "wyłączony" if boot["basemap"] is None else "włączony"
    _note(
        player.run_dir,
        f"check OK run={player.run_name} start=06:00:00 probka={player.sample} podklad={base} "
        f"okno6_9={window['n']} szczyt={peak['n']} bez_t={thin['n']} os={len(axis)} linki={len(boot['links'])} "
        f"osie={lat:.4f}N {lon:.4f}E",
    )
    return 0


def _dumps(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _grab(path):
    import subprocess
    import tempfile
    script = r"""
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Grab {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindowW(string c, string t);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[Grab]::SetProcessDPIAware() | Out-Null
$hwnd = [Grab]::FindWindowW([NullString]::Value, "easy-matviz")
if ($hwnd -eq [IntPtr]::Zero) { Write-Output "NOWINDOW"; exit 2 }
[Grab]::SetWindowPos($hwnd, [IntPtr](-1), 0, 0, 0, 0, 0x0001 -bor 0x0002) | Out-Null
Start-Sleep -Milliseconds 400
$rect = New-Object Grab+RECT
[Grab]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
if ($w -lt 100 -or $h -lt 100) { Write-Output "SMALL $w $h"; exit 3 }
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($rect.Left, $rect.Top, 0, 0, (New-Object System.Drawing.Size $w, $h))
$bmp.Save($env:VIZ_GRAB, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
[Grab]::SetWindowPos($hwnd, [IntPtr](-2), 0, 0, 0, 0, 0x0001 -bor 0x0002) | Out-Null
Write-Output "OK $w $h"
"""
    # ponytail: zrzut przez System.Drawing, bez dokładania Pillow do projektu
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        ps1 = handle.name
    try:
        env = dict(**{k: v for k, v in __import__("os").environ.items()})
        env["VIZ_GRAB"] = str(path)
        done = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=30,
        )
        return (done.stdout or "") + (done.stderr or ""), done.returncode
    finally:
        Path(ps1).unlink(missing_ok=True)


def _wait_js(window, expr, seconds=8):
    deadline = time.perf_counter() + seconds
    value = None
    while time.perf_counter() < deadline:
        value = window.evaluate_js(expr)
        if value:
            return value
        time.sleep(0.1)
    return value


def smoke(run):
    player = Player()
    player.open(run)
    if player.error:
        _note(player.run_dir, f"FAIL {player.error}")
        return 1
    import webview
    window = webview.create_window(
        "easy-matviz", html=render(player), js_api=Api(player),
        width=1440, height=900, background_color="#121418", text_select=True,
    )
    shot = ROOT / "docs" / "research" / "wizualizer_okno.png"
    result = {"ok": False}

    def body():
        try:
            ready = _wait_js(window, "window.mapReady === true && window.apiReady === true")
            if not ready:
                result["error"] = "mapa nie wstała"
                return
            opened = _wait_js(window, "document.getElementById('clock').textContent === '06:00:00'")
            if not opened:
                result["error"] = "brak klatki " + str(window.evaluate_js("window.drawError"))
                return
            window.evaluate_js("window.hold = true")
            time.sleep(0.4)
            meta = player.index.meta
            player.clear()
            player.set_classes("".join(player.chip_letters))
            player.t = float(meta["max_concurrent_6_9_time"])
            full = player.payload()
            window.evaluate_js("draw(" + _dumps(full) + ")")
            err = window.evaluate_js("window.drawError")
            drawn = window.evaluate_js("window.drawnN")
            size = window.evaluate_js("window.mapSize")
            sample = window.evaluate_js("document.getElementById('sample').textContent")
            base = window.evaluate_js("document.getElementById('base').textContent")
            if err:
                result["error"] = err
                return
            if drawn != full["n"] or full["n"] < 100:
                result["error"] = f"rysunek {drawn} dane {full['n']}"
                return
            if not size or int(str(size).split("x")[0]) < 200:
                result["error"] = f"mapa {size}"
                return
            if "0,25" not in str(sample):
                result["error"] = f"próbka {sample}"
                return
            if player.basemap is None and str(base) != "Podkład wyłączony.":
                result["error"] = f"podkład {base}"
                return
            window.evaluate_js("document.getElementById('hide').click()")
            time.sleep(0.3)
            back = window.evaluate_js(
                "(function(){var b=document.getElementById('hide');var r=b.getBoundingClientRect();"
                "return r.width>20 && r.left>=0 && r.right<=window.innerWidth+1 && b.textContent==='panel';})()"
            )
            window.evaluate_js("document.getElementById('hide').click()")
            if back is not True:
                result["error"] = "przycisk panelu " + str(back)
                return
            window.evaluate_js("document.querySelector('.chip[data-letter=\"t\"]').click()")
            time.sleep(0.8)
            if "t" in player.classes:
                result["error"] = "chip t został włączony"
                return
            thin = player.payload()
            window.evaluate_js("draw(" + _dumps(thin) + ")")
            drawn_thin = window.evaluate_js("window.drawnN")
            if drawn_thin != thin["n"] or not (thin["n"] < full["n"]):
                result["error"] = f"filtr {drawn_thin} {thin['n']} {full['n']}"
                return
            window.evaluate_js("document.querySelector('.chip[data-letter=\"t\"]').click()")
            time.sleep(0.8)
            if "t" not in player.classes:
                result["error"] = "chip t nie wrócił"
                return
            player.t = float(meta["max_concurrent_6_9_time"])
            window.evaluate_js("draw(" + _dumps(player.payload()) + ")")
            window.evaluate_js("document.getElementById('play').click()")
            label = window.evaluate_js("document.getElementById('play').textContent")
            window.evaluate_js("document.getElementById('play').click()")
            if label != "pauza":
                result["error"] = f"start {label}"
                return
            note, code = _grab(shot)
            result["grab"] = note.strip()
            result["grab_code"] = code
            player.lookup("r6510903_5")
            if player.selected_id != "r6510903_5":
                result["error"] = f"lookup {player.selected_id}"
                return
            window.evaluate_js("draw(" + _dumps(player.payload()) + ")")
            detail = window.evaluate_js("document.getElementById('detail').innerText")
            if "r6510903_5" not in str(detail):
                result["error"] = f"panel {detail}"
                return
            axis_ok = window.evaluate_js(
                "(function(){var box=document.getElementById('axis');"
                "var bar=document.getElementById('axis-bar');"
                "var n=bar?bar.querySelectorAll('.seg').length:0;"
                "return !!box && !box.hidden && n>0 && bar.getBoundingClientRect().width>40;})()"
            )
            if axis_ok is not True:
                result["error"] = "oś " + str(axis_ok)
                return
            window.evaluate_js("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
            time.sleep(0.5)
            if player.selected_id is not None:
                result["error"] = f"escape {player.selected_id}"
                return
            result["ok"] = True
            result["n"] = full["n"]
            result["thin"] = thin["n"]
            result["clock"] = full["clock"]
            result["size"] = size
        finally:
            window.destroy()

    storage = ROOT / "output" / "viz_player_webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(
        body, gui="edgechromium", private_mode=False,
        storage_path=str(storage), user_agent="easy-matviz",
    )
    if not result.get("ok"):
        _note(player.run_dir, "FAIL smoke " + str(result.get("error") or result))
        return 1
    png = "zrzut=" + str(shot.relative_to(ROOT)).replace("\\", "/")
    if not shot.exists() or shot.stat().st_size < 10000:
        png = "zrzut=nieudany " + str(result.get("grab"))
    _note(
        player.run_dir,
        f"smoke OK n={result['n']} bez_t={result['thin']} zegar={result['clock']} "
        f"mapa={result['size']} {png}",
    )
    return 0


def serve(run):
    player = Player()
    player.open(run)
    import webview
    webview.create_window(
        "easy-matviz", html=render(player), js_api=Api(player),
        width=1440, height=900, background_color="#121418", text_select=True,
    )
    where = "wyłączony" if player.basemap is None else "włączony"
    _note(player.run_dir, f"okno run={player.run_name} podklad={where} blad={player.error or '-'}")
    storage = ROOT / "output" / "viz_player_webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(
        gui="edgechromium", private_mode=False,
        storage_path=str(storage), user_agent="easy-matviz",
    )
    return 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if argv[:1] == ["--self-test"]:
        return self_test()
    if argv[:1] == ["--check"] and len(argv) >= 2:
        return check(argv[1])
    if argv[:1] == ["--smoke"] and len(argv) >= 2:
        return smoke(argv[1])
    run = argv[0] if argv else saved_run()
    if not run:
        print("podaj katalog runu, np. output/g5r6_25pct_s4711")
        return 2
    return serve(run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
