"""Model okna odtwarzacza (D24): indeks runu, łamane OSM i bezstanowe liczenie klatki.

Nie parsuje XML i nie zna okna. Czyta indeks przez pipeline/viz_engine.py.
Okno (pywebview) jest w viz_player/window.py, akceptacja runu w check.py.
Łamane OSM są tylko rysunkiem (viz_player/curves.py): sieć, eventy i run bez zmian.
Bez klucza CARTO zostaje sieć na #121418 i zdanie „Podkład wyłączony.”
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import numpy as np
from pyproj import Transformer

import viz_engine
import viz_export

from viz_player import curves, site

STATE = ROOT / "output" / "viz_player_state.json"
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


# ponytail: postój ma wagę 1, jazda co najmniej 8 min. Dłuższy postój nie dostaje pikseli.
TRIP_FLOOR_S = 8 * 60


def _fit_axis(segments):
    if not segments:
        return segments
    weights = []
    for seg in segments:
        dur = max(float(seg["t1"]) - float(seg["t0"]), 1.0)
        if seg["trip"]:
            weights.append(max(dur / TRIP_FLOOR_S, 1.0))
        else:
            weights.append(1.0)
    total = sum(weights)
    u = 0.0
    for seg, weight in zip(segments, weights):
        seg["u0"] = round(u, 5)
        u += weight / total
        seg["u1"] = round(u, 5)
    segments[-1]["u1"] = 1.0
    return segments


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
    return _fit_axis(out)


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


def note(run_dir, message):
    print(message)
    if run_dir is None:
        return
    viz = Path(run_dir) / "viz"
    if not viz.is_dir():
        return
    with (viz / "player.log").open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


class Player:
    """Model okna: indeks, łamane i liczenie klatki.

    Po open() tylko czyta. Stan widoku (czas, klasy, zaznaczenie, śledzenie) trzyma klient
    i przysyła go w każdym wywołaniu, więc wątki pywebview nie dzielą żadnego stanu.
    """

    def __init__(self):
        self.run_dir = None
        self.run_name = ""
        self.error = None
        self.index = None
        self.basemap = None
        self.chip_keys = []
        self.class_name = {}
        self.type_names = []
        self.t_start = 0.0
        self.sample = "brak"
        self.curve = None
        self.curve_note = ""
        self.origin = (0.0, 0.0)
        self.fwd = Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)
        self.inv = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)

    def open(self, run, remember=True):
        self.run_dir = Path(run).resolve()
        self.run_name = self.run_dir.name
        self.error = None
        self.index = None
        self.basemap = carto_basemap()
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
            self.origin = tuple(float(v) for v in self.index.meta["origin"])
        except viz_engine.EngineFailed as exc:
            self.index = None
            self.error = f"Indeks się nie zbudował: {exc}"
            return
        try:
            self.curve, msg = curves.load(
                self.run_dir, self.link_id, self.index.link_xy, self.link_length, self.origin,
            )
        except Exception as exc:
            self.curve = curves.empty(len(self.link_id))
            msg = f"łamane: {exc}; cięciwy"
        self.curve.prepare(self.index.link_xy)
        n_bent = self.curve.n_bent
        self.curve_note = f"łamane: {n_bent} z {len(self.link_id)}" if n_bent else msg
        note(self.run_dir, msg)
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
        self.t_start = float(START if t0 <= START <= t1 else t0)
        self.class_name = {row["key"]: row["name"] for row in meta["classes"]}
        types = meta["type_legend"]
        count = max((int(key) for key in types), default=-1) + 1
        self.type_names = [types[str(i)] for i in range(count)]
        self.chip_keys = list(self.index.class_keys)
        self.sample = sample_label(meta.get("sample_size"))

    def clamp(self, t):
        return min(max(float(t), float(self.index.meta["t_min"])), float(self.index.meta["t_max"]))

    def _frame_np(self, t, classes):
        keys = self.chip_keys if classes is None else [str(k) for k in classes]
        fr = viz_engine.frame(self.index, t, keys)
        if self.curve is not None and self.curve.n_bent and len(fr):
            xs, ys, hd, mask = self.curve.place(self.index.link_xy, fr.link, fr.xy[:, 0], fr.xy[:, 1])
            if mask.any():
                fr.xy[mask, 0] = xs[mask]
                fr.xy[mask, 1] = ys[mask]
                fr.heading[mask] = hd[mask]
        return fr

    def local(self, lon, lat):
        east, north = self.inv.transform(float(lon), float(lat))
        return float(east) - self.origin[0], float(north) - self.origin[1]

    def active_track(self, ident, t):
        id_i = self.index.id_of.get(str(ident))
        if id_i is None:
            return None
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

    def trips_of(self, ident):
        id_i = self.index.id_of.get(str(ident))
        if id_i is None:
            return []
        a, b = int(self.index.track_off[id_i]), int(self.index.track_off[id_i + 1])
        return [
            (float(self.index.track_t0[int(k)]), float(self.index.track_t1[int(k)]))
            for k in self.index.track_order[a:b]
        ]

    def panel(self, t, fr, ident, link):
        if self.index is None:
            return {"kind": "empty", "lines": [self.error or "Brak runu."], "axis": []}
        if ident is None and link is not None:
            return self._link_panel(fr, link)
        if ident is None:
            return {"kind": "empty", "lines": [], "axis": []}
        return self._id_panel(t, fr, ident)

    def _id_panel(self, t, fr, ident):
        rows = viz_engine.activities(self.index, ident)
        cover = covering(rows, t)
        axis = schedule(rows, self.index.meta["t_min"], self.index.meta["t_max"], self.trips_of(ident), t)
        track = self.active_track(ident, t)
        if track is not None:
            hit = np.where(fr.track == track)[0]
            if len(hit):
                i = int(hit[0])
                lid, typ, _leng, free = self.link_bits(int(fr.link[i]))
                key = self.index.class_keys[int(fr.cls[i])]
                return {
                    "kind": "vehicle",
                    "lines": [
                        ident, self.class_name.get(key, key), kmh(fr.speed[i]),
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

    def _link_panel(self, fr, link_i):
        lid, typ, leng, free = self.link_bits(link_i)
        now = viz_engine.link_now(fr, link_i)
        line = "teraz " + auta(now["n"])
        if now["n"]:
            line += ", średnia na odcinku " + kmh(now["speed_mean"])
        return {
            "kind": "link",
            "lines": [lid, typ, leng, "freespeed " + free, line],
            "axis": [],
        }

    def path_latlon(self, track, t):
        index = self.index
        a, b = int(index.knot_off[track]), int(index.knot_off[track + 1])
        j = int(np.searchsorted(index.knot_t[a:b], np.float32(t), side="right"))
        j = min(max(j, 1), b - a)
        xs = [float(v) for v in index.knot_x[a:a + j]]
        ys = [float(v) for v in index.knot_y[a:a + j]]
        x, y, _h, _s, link = viz_engine.pose_at(
            index.knot_t[a:b], index.knot_x[a:b], index.knot_y[a:b],
            index.knot_len[a:b], index.knot_link[a:b], t,
        )
        links = [int(v) for v in index.knot_link[a:a + j]]
        if abs(xs[-1] - x) > 1e-3 or abs(ys[-1] - y) > 1e-3:
            xs.append(float(x))
            ys.append(float(y))
            links.append(int(link))
        if self.curve is not None and self.curve.n_bent:
            pts = self.curve.follow(index.link_xy, xs, ys, links)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
        lon, lat = self.fwd.transform(np.asarray(xs) + self.origin[0], np.asarray(ys) + self.origin[1])
        return [[round(float(lat[i]), 6), round(float(lon[i]), 6)] for i in range(len(xs))]

    def frame(self, t, classes=None, selected=None, follow=False):
        """Klatka do narysowania. classes: klucze klas (None: wszystkie), selected: {"id"} albo {"link"}."""
        selected = selected or {}
        if self.index is None:
            return {
                "t": 0.0, "clock": clock(0), "n": 0, "lon": [], "lat": [], "v": [], "hd": [], "heavy": [],
                "sel": None, "path": [], "link": None, "pan": None, "panel": self.panel(0.0, None, None, None),
            }
        t = self.clamp(t)
        fr = self._frame_np(t, classes)
        ident = selected.get("id")
        if ident is not None and str(ident) not in self.index.id_of:
            ident = None
        link = selected.get("link")
        if link is not None and not 0 <= int(link) < len(self.link_id):
            link = None
        if len(fr) == 0:
            lon_l, lat_l, speed, heading, heavy = [], [], [], [], []
        else:
            lon, lat = self.fwd.transform(
                fr.xy[:, 0].astype(np.float64) + self.origin[0],
                fr.xy[:, 1].astype(np.float64) + self.origin[1],
            )
            lon_l = np.round(lon, 6).tolist()
            lat_l = np.round(lat, 6).tolist()
            speed = np.round(fr.speed.astype(np.float64), 3).tolist()
            heading = np.round(fr.heading.astype(np.float64), 4).tolist()
            heavy = self.index.class_heavy[fr.cls].astype(np.uint8).tolist()
        sel = None
        path = []
        pan = None
        if ident is not None:
            track = self.active_track(ident, t)
            if track is not None and len(fr):
                hit = np.where(fr.track == track)[0]
                if len(hit):
                    sel = int(hit[0])
                    if follow:
                        pan = [lat_l[sel], lon_l[sel]]
                path = self.path_latlon(track, t)
            elif follow:
                cover = covering(viz_engine.activities(self.index, ident), t)
                if cover is not None:
                    plon, plat = self.fwd.transform(self.origin[0] + float(cover["x"]), self.origin[1] + float(cover["y"]))
                    pan = [round(float(plat), 6), round(float(plon), 6)]
        return {
            "t": t, "clock": clock(t), "n": int(len(fr)),
            "lon": lon_l, "lat": lat_l, "v": speed, "hd": heading, "heavy": heavy,
            "sel": sel, "path": path,
            "link": None if ident is not None else (None if link is None else int(link)),
            "pan": pan, "panel": self.panel(t, fr, ident, None if link is None else int(link)),
        }

    def pick(self, t, classes, lat, lon, lat2, lon2):
        """Co jest pod kursorem: {"kind": "vehicle", "id"}, {"kind": "link", "link"} albo {"kind": "miss"}."""
        if self.index is None:
            return {"kind": "miss"}
        x, y = self.local(lon, lat)
        x2, y2 = self.local(lon2, lat2)
        tol = max(math.hypot(x2 - x, y2 - y), 0.5)
        track = viz_engine.pick_vehicle(self._frame_np(self.clamp(t), classes), (x, y), tol)
        if track is not None:
            return {"kind": "vehicle", "id": str(self.index.ids[int(self.index.track_person_i[int(track)])])}
        if self.curve is not None and self.curve.n_bent:
            link = self.curve.nearest(self.index.link_xy, x, y, tol)
        else:
            link = viz_engine.pick_link(self.index, (x, y), tol)
        if link is not None:
            return {"kind": "link", "link": int(link)}
        return {"kind": "miss"}

    def lookup(self, query):
        """{"followed": id} przy jednoznacznym trafieniu, inaczej {"hits": [{"id"}]}."""
        query = str(query).strip()
        if self.index is None or not query:
            return {"hits": []}
        hits = viz_engine.lookup(self.index, query)
        exact = [hit for hit in hits if hit["id"] == query]
        chosen = exact[0] if len(exact) == 1 else (hits[0] if len(hits) == 1 else None)
        if chosen is not None:
            return {"followed": chosen["id"]}
        return {"hits": [{"id": hit["id"]} for hit in hits]}

    def link_lonlat(self):
        xy = self.index.link_xy.astype(np.float64)
        ox, oy = self.origin
        lon1, lat1 = self.fwd.transform(xy[:, 0] + ox, xy[:, 1] + oy)
        lon2, lat2 = self.fwd.transform(xy[:, 2] + ox, xy[:, 3] + oy)
        return lon1, lat1, lon2, lat2

    def boot(self):
        """Małe metadane okna (boot.json). Tablice linków i łamanych: boot_arrays()."""
        base = {
            "error": self.error, "run": self.run_name, "t": self.t_start,
            "tMin": 0, "tMax": 1, "sample": "brak", "basemap": self.basemap,
            "bounds": None, "types": [], "classes": [], "nLinks": 0, "nCurve": 0, "curveNote": "", "data": None,
        }
        if self.index is None:
            return base
        lon1, lat1, lon2, lat2 = self.link_lonlat()
        base.update({
            "error": None,
            "tMin": float(self.index.meta["t_min"]),
            "tMax": float(self.index.meta["t_max"]),
            "sample": self.sample,
            "bounds": [
                [float(min(lat1.min(), lat2.min())), float(min(lon1.min(), lon2.min()))],
                [float(max(lat1.max(), lat2.max())), float(max(lon1.max(), lon2.max()))],
            ],
            "types": self.type_names,
            "classes": [{"key": key, "name": self.class_name[key], "on": True} for key in self.chip_keys],
            "nLinks": int(len(lon1)),
            "nCurve": int(len(self.curve.xy)) if self.curve is not None and self.curve.n_bent else 0,
            "curveNote": self.curve_note,
            "data": "data/manifest.json",
        })
        return base

    def boot_arrays(self):
        if self.index is None:
            return {}
        lon1, lat1, lon2, lat2 = self.link_lonlat()
        arrays = {
            "link_ll": np.column_stack((lon1, lat1, lon2, lat2)),
            "link_type": self.link_type.astype(np.uint8),
        }
        if self.curve is not None and self.curve.n_bent:
            lon, lat = self.fwd.transform(
                self.curve.xy[:, 0].astype(np.float64) + self.origin[0],
                self.curve.xy[:, 1].astype(np.float64) + self.origin[1],
            )
            arrays.update({"curve_off": self.curve.off, "curve_lon": np.asarray(lon), "curve_lat": np.asarray(lat)})
        return arrays

    def write_site(self, dest=None):
        dest = dest or self.run_dir / "viz" / "site"
        viz_export.build(self.run_dir, out=Path(dest) / "data")
        return site.write_site(dest, self.boot(), self.boot_arrays())


def pick_ident(index):
    """Pierwsze id, które jedzie i ma czynności (do sprawdzeń bez wiedzy o runie)."""
    both = np.flatnonzero((np.diff(index.act_off) > 0) & (np.diff(index.track_off) > 0))
    return index.id_text[int(both[0])] if len(both) else None
