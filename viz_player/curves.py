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
VERSION = 2


class Curves:
    def __init__(self, off, xy):
        self.off = np.asarray(off, dtype=np.int32)
        self.xy = np.asarray(xy, dtype=np.float32).reshape(-1, 2)
        self._seg = None
        self.found = self.wanted = None  # ile potrzebnych dróg było w pliku OSM (None: nie wiadomo)

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

    def prepare(self, chords):
        """Odcinki do nearest() liczone raz przy otwarciu, nie leniwie z wielu wątków."""
        if self._seg is None:
            self._seg = segments(self, chords)

    def nearest(self, chords, x, y, tol):
        self.prepare(chords)
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
    import viz_buildings

    return viz_buildings.find_pbf()


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
            if attr.get("name") in ("origid", "osm:way:id") and attr.text:  # origid: Supersonic (Kutno), osm:way:id: matsim-osm (Wiedeń)
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


def project(ways, origin, crs="EPSG:2180"):
    from pyproj import Transformer

    if not ways:
        return {}
    tr = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    ox, oy = origin
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


def pbf_stamp(pbf):
    """Tożsamość pliku OSM do klucza cache: nazwa, rozmiar i czas zapisu."""
    st = Path(pbf).stat()
    return f"{Path(pbf).name}:{st.st_size}:{st.st_mtime_ns}"


def _fresh(cache, network, check_age=True):
    """check_age: cache starszy od sieci jest nieświeży. Bez pliku OSM (demo) nie ma jak go przeliczyć, a kopiowanie i rozpakowanie
    potrafią przestawić czasy plików, więc wtedy bierzemy cache (liczba linków i origin są sprawdzane dalej)."""
    if not cache.is_file() or not network.is_file():
        return False
    return not check_age or cache.stat().st_mtime >= network.stat().st_mtime


def coverage(curves):
    """„, w pliku OSM X z Y dróg sieci” albo pusty napis, gdy nie wiadomo."""
    if curves.wanted is None or curves.found is None:
        return ""
    return f"; w pliku OSM {curves.found} z {curves.wanted} dróg sieci"


def read_cache(cache, n, network, pbf, origin, crs="EPSG:2180"):
    if not _fresh(cache, network, pbf is not None and pbf.is_file()):
        return None
    with np.load(cache, allow_pickle=False) as blob:
        if "version" not in blob.files or int(blob["version"]) != VERSION:
            return None
        if pbf is not None and pbf.is_file():  # bez pliku OSM (demo) cache bierzemy taki, jaki jest; z plikiem tylko zbudowany z tego pliku
            if "pbf" not in blob.files or str(blob["pbf"]) != pbf_stamp(pbf):
                return None
        if "crs" not in blob.files or str(blob["crs"]) != crs:  # inny układ sieci (config dopisany po zbudowaniu) daje inne współrzędne
            return None
        found = int(blob["found"]) if "found" in blob.files and int(blob["found"]) >= 0 else None
        wanted = int(blob["wanted"]) if "wanted" in blob.files and int(blob["wanted"]) >= 0 else None
        if "origin" not in blob.files or [float(v) for v in blob["origin"]] != [float(origin[0]), float(origin[1])]:
            return None
        off = np.array(blob["off"])
        xy = np.array(blob["xy"])
    if off.shape != (n + 1,) or int(off[0]) != 0 or int(off[-1]) != len(xy):
        return None
    if len(off) > 1 and np.any(np.diff(off.astype(np.int64)) < 0):
        return None
    out = Curves(off, xy)
    out.found, out.wanted = found, wanted
    return out


def write_cache(cache, curves, origin, pbf=None, crs="EPSG:2180"):
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name("curves-partial.npz")
    with tmp.open("wb") as handle:
        np.savez(
            handle,
            version=np.int32(VERSION),
            origin=np.asarray(origin, dtype=np.float64),
            off=curves.off,
            xy=curves.xy,
            pbf=np.str_(pbf_stamp(pbf) if pbf is not None else ""),
            crs=np.str_(crs),
            found=np.int32(-1 if curves.found is None else curves.found),
            wanted=np.int32(-1 if curves.wanted is None else curves.wanted),
        )
    tmp.replace(cache)


def load(run_dir, link_id, link_xy, link_length, origin, crs="EPSG:2180"):
    run_dir = Path(run_dir)
    n = len(link_id)
    network = run_dir / "output_network.xml.zst"
    cache = run_dir / "viz" / "curves.npz"
    pbf = find_pbf()
    cached = read_cache(cache, n, network, pbf, origin, crs)
    if cached is not None:
        return cached, f"łamane: {cached.n_bent} z {n}, cache{coverage(cached)}"
    try:
        ends = read_ends(network)
    except Exception as exc:
        return empty(n), f"łamane: sieć nieczytelna ({exc}); cięciwy"
    if list(ends[0]) != [str(x) for x in link_id]:
        return empty(n), "łamane: inna kolejność linków; cięciwy"
    wanted = {int(oid) for oid in ends[3] if oid and str(oid).lstrip("-").isdigit()}
    if not wanted or pbf is None:
        why = "brak origid ani osm:way:id" if not wanted else "brak PBF"
        return empty(n), f"łamane: {why}; cięciwy"
    print("łamane: czytam OSM…", flush=True)
    started = time.perf_counter()
    ways = grab_ways(pbf, wanted)
    built = assemble(link_xy, link_length, ends, project(ways, origin, crs))
    built.found, built.wanted = len(ways), len(wanted)
    write_cache(cache, built, origin, pbf, crs)
    if not ways:
        return built, f"łamane: plik OSM nie pokrywa tej sieci (0 z {len(wanted)} dróg); cięciwy"
    return built, f"łamane: {built.n_bent} z {n}, skan {time.perf_counter() - started:.1f} s{coverage(built)}"

