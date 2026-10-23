"""Usługi mapowe OGC (WMS, WMTS) jak w QGIS: GetCapabilities, wybór warstwy, kafelki w układzie Web Mercator.

Kafelki pobiera Python, nie przeglądarka (CORS), a okno dostaje je przez most pywebview.
Obsługa układów: EPSG:3857 (i aliasy) wprost, EPSG:4326 jako zapytanie o bbox kafelka w stopniach
(rozjazd Mercatora na kafelku to ułamek piksela od zoomu ~10), a każdy inny układ rzutowany (np. EPSG:2180)
przez pyproj + Pillow: obraz w tym układzie jest przepróbowany na siatkę kafelka.
"""
import io
import math
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from viz_player.i18n import t

UA ="easy-matanimation"
ORIGIN = 20037508.342789244  # połowa obwodu Ziemi w EPSG:3857, m
SCALE0 = 559082264.0287178  # mianownik skali kafelka 256 px przy z=0 (piksel 0,28 mm)
WEBMERC = {"3857", "900913", "102100", "102113", "3785"}
TIMEOUT = 25
RETRIES = 3


class OgcError(Exception):
    """Błąd do pokazania użytkownikowi jednym zdaniem."""


def _fetch(url, timeout=TIMEOUT):
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise OgcError(t("Adres usługi musi zaczynać się od http:// albo https://"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(), resp.headers.get("Content-Type", "")
        except Exception as exc:  # urllib daje kilka różnych wyjątków, użytkownik chce jedno zdanie
            # publiczne usługi bywają chwilowo niedostępne (zrywane połączenie, losowe 404), więc kilka prób
            if attempt == RETRIES - 1:
                raise OgcError(t("Usługa nie odpowiada: {exc}").format(exc=exc)) from exc
            time.sleep(0.8)


def with_query(base, **params):
    """Dokłada parametry do adresu; klucze z adresu użytkownika (np. map=...) zostają, nasze nadpisują bez względu na wielkość liter."""
    parts = urllib.parse.urlsplit(base)
    mine = {k.lower() for k in params}
    keep = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in mine]
    query = urllib.parse.urlencode(keep + [(k, str(v)) for k, v in params.items()], safe=":,/")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _tag(el):
    return el.tag.rsplit("}", 1)[-1]


def _kids(el, name):
    return [c for c in el if _tag(c) == name]


def _kid(el, name):
    found = _kids(el, name)
    return found[0] if found else None


def _text(el, name, default=""):
    kid = _kid(el, name)
    return (kid.text or "").strip() if kid is not None else default


def _find_all(el, name):
    return [c for c in el.iter() if _tag(c) == name]


def epsg(code):
    """'urn:ogc:def:crs:EPSG::3857', 'urn:ogc:def:crs:EPSG:6.18.3:3857' (wersja bazy w URN, basemap.at), 'EPSG:3857', 'epsg:900913' -> kod; inne (CRS:84) -> None."""
    m = re.search(r"EPSG:(?:[\d.]*:)?(\d+)", str(code), re.I)
    return m.group(1) if m else None


def _href(el):
    for key, value in el.attrib.items():
        if key.endswith("href"):
            return value
    return None


# ---- GetCapabilities -------------------------------------------------------------------------------------------

def capabilities(url):
    """Pobiera i parsuje opis usługi. Zwraca słownik z kind 'wms' albo 'wmts'."""
    url = url.strip()
    if not url:
        raise OgcError(t("Wpisz adres usługi."))
    if "{z}" in url and "{x}" in url:
        return {"kind": "xyz", "url": url, "title": "", "template": url,
                "layers": [{"name": "xyz", "title": "Kafelki XYZ", "path": "Kafelki XYZ", "crs": ["EPSG:3857"]}]}
    order = ["WMTS", "WMS"] if "wmts" in url.lower() else ["WMS", "WMTS"]
    last = None
    for service in order:
        extra = {"VERSION": "1.0.0"} if service == "WMTS" else {}
        body, _ = _fetch(with_query(url, SERVICE=service, REQUEST="GetCapabilities", **extra))
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            last = OgcError(t("Odpowiedź usługi nie jest XML-em ({exc}).").format(exc=exc))
            continue
        name = _tag(root)
        if name in ("WMS_Capabilities", "WMT_MS_Capabilities"):
            return _parse_wms(root, url)
        if name == "Capabilities":
            return _parse_wmts(root, url)
        text = " ".join("".join(root.itertext()).split())[:200]
        last = OgcError(t("Usługa zwróciła błąd: {text}").format(text=text or name))
    raise last or OgcError(t("Nie rozpoznano usługi."))


def _parse_wms(root, url):
    version = root.get("version", "1.3.0")
    cap = _kid(root, "Capability")
    if cap is None:
        raise OgcError("Brak sekcji Capability w opisie WMS.")
    getmap = None
    formats = []
    req = _kid(cap, "Request")
    gm = _kid(req, "GetMap") if req is not None else None
    if gm is not None:
        formats = [(f.text or "").strip() for f in _kids(gm, "Format")]
        for el in _find_all(gm, "OnlineResource"):
            getmap = _href(el)
            break
    layers = []

    def walk(el, crs, trail):
        mine = set(crs)
        for tag in ("CRS", "SRS"):
            for c in _kids(el, tag):
                mine.update((c.text or "").split())
        title = _text(el, "Title")
        here = trail + ([title] if title else [])
        name = _text(el, "Name")
        if name:
            layers.append({"name": name, "title": title or name, "path": " / ".join(here), "crs": sorted(mine)})
        for child in _kids(el, "Layer"):
            walk(child, mine, here)

    top = _kid(cap, "Layer")
    if top is not None:
        walk(top, set(), [])
    return {
        "kind": "wms", "url": url, "title": _text(_kid(root, "Service"), "Title") if _kid(root, "Service") is not None else "",
        "version": version, "getmap": getmap or url, "formats": formats, "layers": layers,
    }


def _parse_wmts(root, url):
    contents = _kid(root, "Contents")
    if contents is None:
        raise OgcError("Brak sekcji Contents w opisie WMTS.")
    kvp = None
    for op in _find_all(root, "Operation"):
        if op.get("name") == "GetTile":
            for el in _find_all(op, "Get"):
                kvp = _href(el)
                break
    sets = {}
    for ms in _kids(contents, "TileMatrixSet"):
        ident = _text(ms, "Identifier")
        crs = epsg(_text(ms, "SupportedCRS"))
        matrices = []
        for tm in _kids(ms, "TileMatrix"):
            top = _text(tm, "TopLeftCorner").split()
            matrices.append({
                "id": _text(tm, "Identifier"), "scale": float(_text(tm, "ScaleDenominator", "0") or 0),
                "tw": int(_text(tm, "TileWidth", "256") or 256), "th": int(_text(tm, "TileHeight", "256") or 256),
                "mw": int(_text(tm, "MatrixWidth", "0") or 0), "mh": int(_text(tm, "MatrixHeight", "0") or 0),
                "top": [float(v) for v in top] if len(top) == 2 else None,
            })
        sets[ident] = {"crs": crs, "matrices": matrices}
    layers = []
    for ly in _kids(contents, "Layer"):
        ident = _text(ly, "Identifier")
        styles = [_text(s, "Identifier") for s in _kids(ly, "Style")]
        default = next((_text(s, "Identifier") for s in _kids(ly, "Style") if s.get("isDefault") == "true"), styles[0] if styles else "default")
        rest = {}
        for ru in _kids(ly, "ResourceURL"):
            if ru.get("resourceType", "tile") == "tile":
                rest[ru.get("format", "")] = ru.get("template", "")
        layers.append({
            "name": ident, "title": _text(ly, "Title") or ident, "path": _text(ly, "Title") or ident,
            "formats": [(f.text or "").strip() for f in _kids(ly, "Format")], "style": default, "rest": rest,
            "sets": [_text(l, "TileMatrixSet") for l in _kids(ly, "TileMatrixSetLink")],
            "crs": sorted({"EPSG:" + c for c in (sets.get(s, {}).get("crs") for s in [_text(l, "TileMatrixSet") for l in _kids(ly, "TileMatrixSetLink")]) if c}),
        })
    return {
        "kind": "wmts", "url": url, "title": _text(_kid(root, "ServiceIdentification"), "Title") if _kid(root, "ServiceIdentification") is not None else "",
        "kvp": kvp or url, "sets": sets, "layers": layers,
    }


# ---- wybór układu i opis warstwy do rysowania ------------------------------------------------------------------

def _pick_format(formats, prefer=("image/png", "image/jpeg")):
    for want in prefer:
        if want in formats:
            return want
    images = [f for f in formats if f.startswith("image/")]
    return images[0] if images else (formats[0] if formats else "image/png")


def make_spec(cap, layer_name):
    """Z opisu usługi i nazwy warstwy robi samodzielny opis do pobierania kafelków albo rzuca OgcError."""
    layer = next((l for l in cap["layers"] if l["name"] == layer_name), None)
    if layer is None:
        raise OgcError(t("Usługa nie ma warstwy {layer_name}.").format(layer_name=layer_name))
    if cap["kind"] == "xyz":
        return {"kind": "xyz", "template": cap["template"]}
    if cap["kind"] == "wms":
        codes = {epsg(c) for c in layer["crs"]}
        if "CRS:84" in layer["crs"]:
            codes.add("84")
        web = next((c for c in layer["crs"] if epsg(c) in WEBMERC), None)
        spec = {"kind": "wms", "getmap": cap["getmap"], "version": cap["version"], "layer": layer_name,
                "format": _pick_format(cap["formats"])}
        if web:
            spec.update(crs=web, mode="3857")
        elif "84" in codes or "4326" in codes:
            lonlat = "CRS:84" if "CRS:84" in layer["crs"] and cap["version"] >= "1.3" else "EPSG:4326"
            spec.update(crs=lonlat, mode="4326")
        else:
            other = next((c for c in layer["crs"] if epsg(c)), None)
            if other is None:
                raise OgcError(t("Warstwa nie podaje żadnego układu współrzędnych."))
            spec.update(crs=other, mode="proj")
        return spec
    # WMTS
    best = None
    for set_id in layer["sets"]:
        tms = cap["sets"].get(set_id)
        if tms and tms["crs"] in WEBMERC and tms["matrices"] and all(m["tw"] == 256 and m["th"] == 256 for m in tms["matrices"]):
            best = (set_id, tms)
            break
    if best is None:
        have = ", ".join(sorted({"EPSG:" + str(cap["sets"][s]["crs"]) for s in layer["sets"] if s in cap["sets"]})) or "brak"
        raise OgcError(t("Warstwa WMTS nie ma zestawu kafelków w EPSG:3857 (256 px); ma: {have}.").format(have=have))
    set_id, tms = best
    matrices = {}
    for m in tms["matrices"]:
        if m["scale"] > 0:
            z = round(math.log2(SCALE0 / m["scale"]))
            if abs(SCALE0 / 2 ** z - m["scale"]) / m["scale"] < 1e-3:
                matrices[z] = m["id"]
    if not matrices:
        raise OgcError(t("Zestaw kafelków WMTS nie ma skal zgodnych z siatką Web Mercator."))
    fmt = _pick_format(layer["formats"])
    spec = {"kind": "wmts", "layer": layer_name, "style": layer["style"], "set": set_id, "format": fmt,
            "matrices": {str(z): i for z, i in matrices.items()}, "kvp": cap["kvp"]}
    if fmt in layer["rest"]:
        spec["rest"] = layer["rest"][fmt]
    return spec


# ---- kafelki -----------------------------------------------------------------------------------------------------

def tile_bbox_3857(z, x, y):
    size = 2 * ORIGIN / 2 ** z
    return (-ORIGIN + x * size, ORIGIN - (y + 1) * size, -ORIGIN + (x + 1) * size, ORIGIN - y * size)


def _to_lonlat(mx, my):
    lon = mx / ORIGIN * 180.0
    lat = math.degrees(2 * math.atan(math.exp(my / ORIGIN * math.pi)) - math.pi / 2)
    return lon, lat


def wms_tile_url(spec, z, x, y):
    minx, miny, maxx, maxy = tile_bbox_3857(z, x, y)
    v13 = spec["version"] >= "1.3"
    mode = spec["mode"]
    if mode == "3857":
        bbox = (minx, miny, maxx, maxy)
        size = 256
    elif mode == "4326":
        lon0, lat0 = _to_lonlat(minx, miny)
        lon1, lat1 = _to_lonlat(maxx, maxy)
        bbox = (lat0, lon0, lat1, lon1) if (v13 and spec["crs"] == "EPSG:4326") else (lon0, lat0, lon1, lat1)
        size = 256
    else:
        raise OgcError("Układ rzutowany obsługuje wms_tile_proj.")
    return with_query(
        spec["getmap"], SERVICE="WMS", VERSION=spec["version"], REQUEST="GetMap", LAYERS=spec["layer"], STYLES="",
        FORMAT=spec["format"], TRANSPARENT="TRUE", WIDTH=size, HEIGHT=size,
        **{("CRS" if v13 else "SRS"): spec["crs"], "BBOX": ",".join(repr(float(v)) for v in bbox)},
    )


def wmts_tile_url(spec, z, x, y):
    ident = spec["matrices"].get(str(z))
    if ident is None:
        raise OgcError(t("Brak poziomu {z} w zestawie kafelków.").format(z=z))
    if spec.get("rest"):
        url = spec["rest"]
        for key, val in (("TileMatrixSet", spec["set"]), ("TileMatrix", ident), ("TileRow", y), ("TileCol", x), ("Style", spec["style"])):
            url = re.sub(r"\{" + key + r"\}", str(val), url, flags=re.I)
        return url
    return with_query(
        spec["kvp"], SERVICE="WMTS", REQUEST="GetTile", VERSION="1.0.0", LAYER=spec["layer"], STYLE=spec["style"],
        TILEMATRIXSET=spec["set"], TILEMATRIX=ident, TILEROW=y, TILECOL=x, FORMAT=spec["format"],
    )


def _check_image(body, ctype):
    if not ctype.lower().startswith("image/"):
        text = " ".join(body[:400].decode("utf-8", "replace").split())
        raise OgcError(t("Usługa zwróciła nie obraz: {text}").format(text=text[:160]))
    return ctype.split(";")[0].strip(), body


def _tile_proj(spec, z, x, y):
    """Układ rzutowany (np. EPSG:2180): prosty bbox w tym układzie obejmujący kafelek, potem przepróbowanie na siatkę kafelka."""
    import numpy as np
    from PIL import Image
    from pyproj import CRS, Transformer
    minx, miny, maxx, maxy = tile_bbox_3857(z, x, y)
    n = 256
    xs = minx + (np.arange(n) + 0.5) / n * (maxx - minx)
    ys = maxy - (np.arange(n) + 0.5) / n * (maxy - miny)
    gx, gy = np.meshgrid(xs, ys)
    code = int(epsg(spec["crs"]))
    fwd = Transformer.from_crs(3857, code, always_xy=True)
    px, py = fwd.transform(gx, gy)
    if not np.isfinite(px).all():
        raise OgcError(t("Kafelek poza zakresem układu usługi."))
    x0, x1, y0, y1 = float(px.min()), float(px.max()), float(py.min()), float(py.max())
    pad = max(x1 - x0, y1 - y0) / n * 2
    x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad
    w = h = 512
    v13 = spec["version"] >= "1.3"
    # WMS 1.3.0 podaje bbox w kolejności osi układu; EPSG:2180 i stopnie mają północ jako pierwszą oś
    north_first = CRS.from_epsg(code).axis_info[0].direction.lower().startswith("north")
    bbox = (y0, x0, y1, x1) if (v13 and north_first) else (x0, y0, x1, y1)
    url = with_query(
        spec["getmap"], SERVICE="WMS", VERSION=spec["version"], REQUEST="GetMap", LAYERS=spec["layer"], STYLES="",
        FORMAT=spec["format"], TRANSPARENT="TRUE", WIDTH=w, HEIGHT=h,
        **{("CRS" if v13 else "SRS"): spec["crs"], "BBOX": ",".join(repr(float(v)) for v in bbox)},
    )
    body, ctype = _fetch(url)
    _check_image(body, ctype)
    src = Image.open(io.BytesIO(body)).convert("RGBA")
    arr = np.asarray(src)
    ix = np.clip(((px - x0) / (x1 - x0) * w).astype(int), 0, w - 1)
    iy = np.clip(((y1 - py) / (y1 - y0) * h).astype(int), 0, h - 1)
    out = Image.fromarray(arr[iy, ix], "RGBA")
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return "image/png", buf.getvalue()


def xyz_tile_url(template, z, x, y):
    """Szablon {z}/{x}/{y}; {-y} to schemat TMS (y od dołu), {s} to pierwszy z serwerów a, b, c."""
    url = template.replace("{s}", "a").replace("{-y}", str(2 ** z - 1 - y))
    return url.replace("{z}", str(z)).replace("{x}", str(x)).replace("{y}", str(y))


def tile(spec, z, x, y):
    """(mime, bajty) kafelka z/x/y w siatce Web Mercator (schemat XYZ)."""
    if spec["kind"] == "xyz":
        body, ctype = _fetch(xyz_tile_url(spec["template"], z, x, y))
        return _check_image(body, ctype)
    if spec["kind"] == "wms":
        if spec["mode"] == "proj":
            return _tile_proj(spec, z, x, y)
        body, ctype = _fetch(wms_tile_url(spec, z, x, y))
        return _check_image(body, ctype)
    body, ctype = _fetch(wmts_tile_url(spec, z, x, y))
    return _check_image(body, ctype)
