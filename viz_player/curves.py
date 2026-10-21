"""Łamane OSM tylko do rysunku w oknie. Nie zapisuje sieci, eventów ani planów.

Cache: output/<run>/viz/curves.npz. Brak PBF, albo łuk różny od length o więcej niż 1 m:
zostaje cięciwa. Kropka auta jedzie po tej samej łamanej, ułamkiem cięciwy.
"""
import math
import time
from pathlib import Path

import numpy as np

LEN_M = 1.0
END_M = 1.0
# ponytail: odchylenie <= 2 m zostaje cięciwą. Na ekranie i tak prosta.
DEV_M = 2.0
VERSION = 1


class Curves:
    def __init__(self, off, xy):
        self.off = np.asarray(off, dtype=np.int32)
        self.xy = np.asarray(xy, dtype=np.float32).reshape(-1, 2)
        self._seg = None

    @property
    def n_bent(self):
        if len(self.off) < 2:
            return 0
        return int(np.count_nonzero(np.diff(self.off) >= 3))

    def chain(self, i):
        a, b = int(self.off[i]), int(self.off[i + 1])
        if b - a < 3:
            return None
        return self.xy[a:b]

    def place(self, chords, links, xs, ys):
        """xy i kierunek na łamanej. mask=False: punkt zostaje na cięciwie."""
        xs = np.asarray(xs, dtype=np.float64)
        ys = np.asarray(ys, dtype=np.float64)
        out_x = xs.copy()
        out_y = ys.copy()
        heading = np.zeros(len(xs), dtype=np.float64)
        mask = np.zeros(len(xs), dtype=bool)
        for i, li in enumerate(links):
            chain = self.chain(int(li))
            if chain is None:
                continue
            c = chords[int(li)]
            u = chord_u(c[0], c[1], c[2], c[3], xs[i], ys[i])
            out_x[i], out_y[i], heading[i] = point_at(chain, u)
            mask[i] = True
        return out_x, out_y, heading, mask

    def follow(self, chords, xs, ys, links):
        """Ślad przejazdu. Między węzłami jednego linku dokleja punkty łamanej."""
        out = []
        for i, li in enumerate(links):
            li = int(li)
            chain = self.chain(li)
            x, y = float(xs[i]), float(ys[i])
            if i and int(links[i - 1]) == li and chain is not None:
                c = chords[li]
                u0 = chord_u(c[0], c[1], c[2], c[3], float(xs[i - 1]), float(ys[i - 1]))
                u1 = chord_u(c[0], c[1], c[2], c[3], x, y)
                pts = span(chain, u0, u1)
                if out and pts:
                    pts = pts[1:]
                out.extend(pts)
            elif chain is not None:
                c = chords[li]
                u = chord_u(c[0], c[1], c[2], c[3], x, y)
                out.append(point_at(chain, u)[:2])
            else:
                out.append((x, y))
        return out

    def nearest(self, chords, x, y, tol):
        if self._seg is None:
            self._seg = segments(self, chords)
        x0, y0, x1, y1, owner = self._seg
        if len(owner) == 0:
            return None
        bx, by = x1 - x0, y1 - y0
        den = bx * bx + by * by
        u = np.zeros(len(owner), dtype=np.float64)
        np.divide((x - x0) * bx + (y - y0) * by, den, out=u, where=den >= 1e-12)
        np.clip(u, 0.0, 1.0, out=u)
        d2 = (x - (x0 + u * bx)) ** 2 + (y - (y0 + u * by)) ** 2
        i = int(np.argmin(d2))
        if d2[i] > float(tol) ** 2:
            return None
        return int(owner[i])


def empty(n):
    return Curves(np.zeros(n + 1, dtype=np.int32), np.zeros((0, 2), dtype=np.float32))


def chord_u(x0, y0, x1, y1, x, y):
    dx, dy = float(x1) - float(x0), float(y1) - float(y0)
    den = dx * dx + dy * dy
    if den < 1e-12:
        return 0.0
    u = ((float(x) - float(x0)) * dx + (float(y) - float(y0)) * dy) / den
    return min(1.0, max(0.0, u))


def point_at(xy, u):
    """Punkt i kierunek na ułamku długości łamanej. u=0 początek, u=1 koniec."""
    xy = np.asarray(xy, dtype=np.float64)
    if len(xy) == 1:
        return float(xy[0, 0]), float(xy[0, 1]), 0.0
    step = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    total = float(step.sum())
    if total <= 1e-9:
        return float(xy[0, 0]), float(xy[0, 1]), 0.0
    target = min(1.0, max(0.0, float(u))) * total
    acc = 0.0
    last = len(step) - 1
    for i, seg in enumerate(step):
        if acc + seg >= target - 1e-9 or i == last:
            f = 0.0 if seg <= 1e-12 else (target - acc) / seg
            f = min(1.0, max(0.0, f))
            x = float(xy[i, 0] + f * (xy[i + 1, 0] - xy[i, 0]))
            y = float(xy[i, 1] + f * (xy[i + 1, 1] - xy[i, 1]))
            j = i + 1 if f >= 1.0 - 1e-9 and i < last else i
            heading = math.atan2(float(xy[j + 1, 1] - xy[j, 1]), float(xy[j + 1, 0] - xy[j, 0]))
            return x, y, heading
        acc += float(seg)
    return float(xy[-1, 0]), float(xy[-1, 1]), 0.0


def span(xy, u0, u1):
    rev = u1 < u0
    a, b = (u1, u0) if rev else (u0, u1)
    xy = np.asarray(xy, dtype=np.float64)
    step = np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1]))
    total = float(step.sum())
    pts = [point_at(xy, a)[:2]]
    if total > 1e-9 and b > a:
        acc = 0.0
        sa, sb = a * total, b * total
        for i in range(1, len(xy) - 1):
            acc += float(step[i - 1])
            if sa + 1e-4 < acc < sb - 1e-4:
                pts.append((float(xy[i, 0]), float(xy[i, 1])))
        end = point_at(xy, b)[:2]
        if math.hypot(end[0] - pts[-1][0], end[1] - pts[-1][1]) > 1e-3:
            pts.append(end)
    if rev:
        pts.reverse()
    return pts


def arc_length(xy):
    xy = np.asarray(xy, dtype=np.float64)
    if len(xy) < 2:
        return 0.0
    return float(np.hypot(np.diff(xy[:, 0]), np.diff(xy[:, 1])).sum())


def between(i0, i1):
    """Indeksy od i0 do i1 włącznie. Dojście wstecz do indeksu 0 nie gubi pierwszego węzła."""
    if i0 == i1:
        return None
    if i1 > i0:
        return list(range(i0, i1 + 1))
    if i1 == 0:
        return list(range(i0, -1, -1))
    return list(range(i0, i1 - 1, -1))


def deviation(east, north, chord):
    x0, y0, x1, y1 = (float(v) for v in chord)
    bx, by = x1 - x0, y1 - y0
    den = bx * bx + by * by
    if den < 1e-12:
        return float(np.max(np.hypot(east - x0, north - y0)))
    u = ((east - x0) * bx + (north - y0) * by) / den
    np.clip(u, 0.0, 1.0, out=u)
    return float(np.max(np.hypot(east - (x0 + u * bx), north - (y0 + u * by))))


def best_chain(way, frm, to, chord, length):
    refs, east, north = way
    try:
        start, end = int(frm), int(to)
    except (TypeError, ValueError):
        return None
    best, best_err = None, None
    starts = [i for i, ref in enumerate(refs) if ref == start]
    ends = [i for i, ref in enumerate(refs) if ref == end]
    for i0 in starts:
        for i1 in ends:
            idx = between(i0, i1)
            if idx is None or len(idx) < 3:
                continue
            e, n = east[idx], north[idx]
            if math.hypot(e[0] - chord[0], n[0] - chord[1]) > END_M:
                continue
            if math.hypot(e[-1] - chord[2], n[-1] - chord[3]) > END_M:
                continue
            arc = float(np.hypot(np.diff(e), np.diff(n)).sum())
            err = abs(arc - float(length))
            if err > LEN_M or deviation(e, n, chord) <= DEV_M:
                continue
            if best_err is None or err < best_err:
                best_err = err
                best = np.column_stack((e, n))
    return best


def segments(curves, chords):
    x0, y0, x1, y1, owner = [], [], [], [], []
    for i, chord in enumerate(chords):
        chain = curves.chain(i)
        if chain is None:
            x0.append(chord[0])
            y0.append(chord[1])
            x1.append(chord[2])
            y1.append(chord[3])
            owner.append(i)
            continue
        xy = np.asarray(chain, dtype=np.float64)
        x0.extend(xy[:-1, 0])
        y0.extend(xy[:-1, 1])
        x1.extend(xy[1:, 0])
        y1.extend(xy[1:, 1])
        owner.extend([i] * (len(xy) - 1))
    return (
        np.asarray(x0, dtype=np.float64),
        np.asarray(y0, dtype=np.float64),
        np.asarray(x1, dtype=np.float64),
        np.asarray(y1, dtype=np.float64),
        np.asarray(owner, dtype=np.int32),
    )


def find_pbf():
    root = Path(__file__).resolve().parents[1]
    hits = sorted((root / "data" / "raw" / "osm").glob("lodzkie-*.osm.pbf"))
    return hits[-1] if hits else None


def read_ends(path):
    import zstandard
    from lxml import etree

    ids, frm, to, orig = [], [], [], []
    stream = zstandard.ZstdDecompressor().stream_reader(Path(path).open("rb"))
    for _, el in etree.iterparse(stream, tag="link", load_dtd=False, no_network=True):
        ids.append(el.get("id"))
        frm.append(el.get("from"))
        to.append(el.get("to"))
        oid = None
        for attr in el.iter("attribute"):
            if attr.get("name") == "origid" and attr.text:
                oid = attr.text.strip()
                break
        orig.append(oid)
        el.clear()
    return ids, frm, to, orig


def grab_ways(pbf, wanted):
    import osmium

    class Grab(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.ways = {}

        def way(self, w):
            if w.id not in wanted:
                return
            try:
                refs = [n.ref for n in w.nodes]
                lon = [n.lon for n in w.nodes]
                lat = [n.lat for n in w.nodes]
            except osmium.InvalidLocationError:
                return
            if len(refs) >= 2:
                self.ways[int(w.id)] = (refs, lon, lat)

    found = Grab()
    found.apply_file(str(pbf), locations=True)
    return found.ways


def project(ways):
    import viz_index
    from pyproj import Transformer

    if not ways:
        return {}
    tr = Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)
    ox, oy = viz_index.ORIGIN
    order, lons, lats = [], [], []
    for wid, (refs, lon, lat) in ways.items():
        order.append((wid, refs, len(lon)))
        lons.append(np.asarray(lon, dtype=np.float64))
        lats.append(np.asarray(lat, dtype=np.float64))
    east, north = tr.transform(np.concatenate(lons), np.concatenate(lats))
    east = np.asarray(east, dtype=np.float64) - ox
    north = np.asarray(north, dtype=np.float64) - oy
    out, i = {}, 0
    for wid, refs, k in order:
        out[wid] = (refs, east[i:i + k], north[i:i + k])
        i += k
    return out


def assemble(link_xy, link_length, ends, ways):
    _ids, frm, to, orig = ends
    parts, off = [], [0]
    for i, oid in enumerate(orig):
        chain = None
        if oid and str(oid).lstrip("-").isdigit():
            way = ways.get(int(oid))
            if way is not None:
                chain = best_chain(way, frm[i], to[i], link_xy[i], link_length[i])
        if chain is None:
            off.append(off[-1])
        else:
            parts.append(np.asarray(chain, dtype=np.float32))
            off.append(off[-1] + len(chain))
    stacked = np.vstack(parts) if parts else np.zeros((0, 2), dtype=np.float32)
    return Curves(np.asarray(off, dtype=np.int32), stacked)


def _fresh(cache, network, pbf):
    if not cache.is_file() or not network.is_file():
        return False
    stamp = cache.stat().st_mtime
    if stamp < network.stat().st_mtime:
        return False
    if pbf is not None and pbf.is_file() and stamp < pbf.stat().st_mtime:
        return False
    return True


def read_cache(cache, n, network, pbf):
    if not _fresh(cache, network, pbf):
        return None
    with np.load(cache, allow_pickle=False) as blob:
        if "version" not in blob.files or int(blob["version"]) != VERSION:
            return None
        off = np.array(blob["off"])
        xy = np.array(blob["xy"])
    if off.shape != (n + 1,) or int(off[0]) != 0 or int(off[-1]) != len(xy):
        return None
    if len(off) > 1 and np.any(np.diff(off.astype(np.int64)) < 0):
        return None
    return Curves(off, xy)


def write_cache(cache, curves):
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name("curves-partial.npz")
    with tmp.open("wb") as handle:
        np.savez(
            handle,
            version=np.int32(VERSION),
            off=curves.off,
            xy=curves.xy,
        )
    tmp.replace(cache)


def load(run_dir, link_id, link_xy, link_length):
    run_dir = Path(run_dir)
    n = len(link_id)
    network = run_dir / "output_network.xml.zst"
    cache = run_dir / "viz" / "curves.npz"
    pbf = find_pbf()
    cached = read_cache(cache, n, network, pbf)
    if cached is not None:
        return cached, f"łamane: {cached.n_bent} z {n}, cache"
    try:
        ends = read_ends(network)
    except Exception as exc:
        return empty(n), f"łamane: sieć nieczytelna ({exc}); cięciwy"
    if list(ends[0]) != [str(x) for x in link_id]:
        return empty(n), "łamane: inna kolejność linków; cięciwy"
    wanted = {int(oid) for oid in ends[3] if oid and str(oid).lstrip("-").isdigit()}
    if not wanted or pbf is None:
        why = "brak origid" if not wanted else "brak PBF"
        return empty(n), f"łamane: {why}; cięciwy"
    print("łamane: czytam OSM…", flush=True)
    started = time.perf_counter()
    built = assemble(link_xy, link_length, ends, project(grab_ways(pbf, wanted)))
    write_cache(cache, built)
    return built, f"łamane: {built.n_bent} z {n}, skan {time.perf_counter() - started:.1f} s"


def self_test():
    if between(7, 0) != [7, 6, 5, 4, 3, 2, 1, 0] or between(1, 3) != [1, 2, 3] or between(3, 1) != [3, 2, 1] or between(2, 2) is not None:
        raise SystemExit(f"self-test: cięcie {between(7, 0)} {between(3, 1)}")
    straight = ([1, 2, 3], np.array([0.0, 50.0, 100.0]), np.array([0.0, 0.0, 0.0]))
    chord = np.array([0.0, 0.0, 100.0, 0.0])
    if best_chain(straight, "1", "3", chord, 100.0) is not None:
        raise SystemExit("self-test: prosta dostała łamaną")
    bend = ([1, 2, 3], np.array([0.0, 100.0, 100.0]), np.array([0.0, 0.0, 100.0]))
    forward = best_chain(bend, "1", "3", np.array([0.0, 0.0, 100.0, 100.0]), 200.0)
    back = best_chain(bend, "3", "1", np.array([100.0, 100.0, 0.0, 0.0]), 200.0)
    if forward is None or back is None or abs(arc_length(forward) - 200) > 1e-6:
        raise SystemExit("self-test: łamana L")
    if abs(back[0, 0] - 100) > 1e-6 or abs(back[-1, 0]) > 1e-6 or abs(back[1, 1]) > 1e-6:
        raise SystemExit(f"self-test: cięcie wstecz {back}")
    if best_chain(bend, "1", "3", np.array([0.0, 0.0, 100.0, 100.0]), 100.0) is not None:
        raise SystemExit("self-test: łuk niezgodny z length")
    x, y, heading = point_at(forward, 0.5)
    if abs(x - 100) > 1e-6 or abs(y) > 1e-6 or abs(heading - math.pi / 2) > 1e-6:
        raise SystemExit(f"self-test: środek łamanej {x} {y} {heading}")
    _x, _y, east = point_at(forward, 0.25)
    if abs(east) > 1e-6:
        raise SystemExit("self-test: kierunek na pierwszym odcinku")
    curves = Curves(np.array([0, 3, 3], dtype=np.int32), forward)
    chords = np.array([[0.0, 0.0, 100.0, 100.0], [200.0, 0.0, 300.0, 0.0]])
    px, py, _hd, mask = curves.place(chords, [0], [50.0], [50.0])
    if not mask[0] or abs(px[0] - 100) > 1e-3 or abs(py[0]) > 1e-3:
        raise SystemExit(f"self-test: auto na łamanej {px} {py}")
    path = curves.follow(chords, [0.0, 100.0], [0.0, 100.0], [0, 0])
    if not any(abs(p[0] - 100) < 1e-3 and abs(p[1]) < 1e-3 for p in path):
        raise SystemExit(f"self-test: ślad omija róg {path}")
    if curves.nearest(chords, 100.0, 1.0, 5) != 0:
        raise SystemExit("self-test: klik w róg")
    if curves.nearest(chords, 50.0, 50.0, 5) is not None:
        raise SystemExit("self-test: klik w cięciwę łuku")
    if curves.nearest(chords, 250.0, 1.0, 5) != 1:
        raise SystemExit("self-test: klik w prosty link")
