"""Własny obraz jako podkład (P5c): georeferencja z pliku albo ręcznie.

Kolejność, gdy użytkownik poda obraz:
  1. GeoTIFF (tagi w pliku) albo plik świata obok (.wld, .pgw, .jgw, .tfw...), układ z GeoKeys albo z pliku .prj;
  2. plik świata bez układu: okno pyta o kod EPSG (podpowiedź z liczb);
  3. brak odniesienia: obraz trafia na środek widoku i użytkownik układa go ręcznie (przesuwanie, skala i obrót
     jednym rogiem) albo wpisuje zakres (W, S, E, N w wybranym układzie).
Wszystko sprowadza się do czterech narożników w lon/lat [lewy-górny, prawy-górny, prawy-dolny, lewy-dolny],
które MapLibre przyjmuje w źródle `image` (dowolny czworokąt, więc obrót i skos są za darmo).
Obraz jest kopiowany do `output/viz_player_rasters/` (poza gitem), zmniejszany do MAX_PX po dłuższym boku.
"""
import io
import math
import re
from pathlib import Path

from PIL import Image

from viz_player.i18n import t

MAX_PX = 4096
ORIGIN = 20037508.342789244
WORLD_EXT = {
    ".png": (".pgw", ".pngw", ".wld"),
    ".jpg": (".jgw", ".jpgw", ".jpegw", ".wld"),
    ".jpeg": (".jgw", ".jpgw", ".jpegw", ".wld"),
    ".tif": (".tfw", ".tifw", ".tiffw", ".wld"),
    ".tiff": (".tfw", ".tifw", ".tiffw", ".wld"),
    ".webp": (".wld",),
}
Image.MAX_IMAGE_PIXELS = 300_000_000


class RasterError(Exception):
    """Zdanie dla użytkownika."""


def lonlat_to_merc(lon, lat):
    x = lon * ORIGIN / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) * ORIGIN / math.pi
    return x, y


def merc_to_lonlat(x, y):
    return x / ORIGIN * 180.0, math.degrees(2 * math.atan(math.exp(y / ORIGIN * math.pi)) - math.pi / 2)


# ---- georeferencja z pliku -----------------------------------------------------------------------------------------

def _world_file(path):
    """Sześć liczb pliku świata -> afiniczna (a, b, c, d, e, f): x = a*kol + b*wiersz + c, y = d*kol + e*wiersz + f, po rogu piksela."""
    for ext in WORLD_EXT.get(path.suffix.lower(), (".wld",)):
        cand = path.with_suffix(ext)
        if not cand.exists():
            continue
        try:
            a, d, b, e, c, f = (float(line.split()[0]) for line in cand.read_text(encoding="utf-8", errors="ignore").splitlines()[:6])
        except (ValueError, IndexError):
            raise RasterError(t("Plik świata {name} ma zły format (oczekiwano sześciu liczb).").format(name=cand.name))
        return (a, b, c - a / 2 - b / 2, d, e, f - d / 2 - e / 2)
    return None


def _prj_epsg(path):
    cand = path.with_suffix(".prj")
    if not cand.exists():
        return None
    try:
        from pyproj import CRS
        return CRS.from_wkt(cand.read_text(encoding="utf-8", errors="ignore")).to_epsg(min_confidence=20)
    except Exception:
        return None


def _geotiff(img):
    """Tagi GeoTIFF czytane przez Pillow: (afiniczna, EPSG albo None) albo None, gdy plik nie jest GeoTIFF-em."""
    tags = getattr(img, "tag_v2", None)
    if tags is None:
        return None
    scale, tie, trans, keys = tags.get(33550), tags.get(33922), tags.get(34264), tags.get(34735)
    if trans and len(trans) == 16:
        aff = (trans[0], trans[1], trans[3], trans[4], trans[5], trans[7])
    elif scale and tie and len(tie) >= 6:
        sx, sy = scale[0], scale[1]
        i, j, _, X, Y, _ = tie[:6]
        aff = (sx, 0.0, X - i * sx, 0.0, -sy, Y + j * sy)
    else:
        return None
    code = None
    if keys:
        table = {keys[4 + 4 * n]: keys[7 + 4 * n] for n in range(keys[3]) if len(keys) >= 8 + 4 * n}
        for key in (3072, 2048):  # ProjectedCSType, GeographicType
            if table.get(key) not in (None, 0, 32767):
                code = int(table[key])
                break
    return aff, code


def read_georef(path):
    """{"affine", "crs" (EPSG albo None), "source"} albo None, gdy obraz nie ma odniesienia przestrzennego."""
    path = Path(path)
    with Image.open(path) as img:
        found = _geotiff(img)
    if found:
        aff, code = found
        return {"affine": aff, "crs": code or _prj_epsg(path), "source": "GeoTIFF"}
    aff = _world_file(path)
    if aff:
        return {"affine": aff, "crs": _prj_epsg(path), "source": t("plik świata")}
    return None


def guess_crs(affine, size):
    """Podpowiedź układu z samych liczb: stopnie, Polska CS92 (EPSG:2180), Web Mercator."""
    a, b, c, d, e, f = affine
    w, h = size
    xs = [c, c + a * w + b * h]
    ys = [f, f + d * w + e * h]
    if all(abs(v) <= 180 for v in xs) and all(abs(v) <= 90 for v in ys):
        return 4326
    if all(1e5 <= v <= 9.5e5 for v in xs) and all(-1e5 <= v <= 8e5 for v in ys):
        return 2180
    return 3857


def corners_from_affine(affine, size, crs):
    from pyproj import Transformer
    a, b, c, d, e, f = affine
    w, h = size
    pts = [(c, f), (c + a * w, f + d * w), (c + a * w + b * h, f + d * w + e * h), (c + b * h, f + e * h)]
    if int(crs) == 4326:
        return [[x, y] for x, y in pts]
    try:
        to = Transformer.from_crs(int(crs), 4326, always_xy=True)
    except Exception:
        raise RasterError(t("Nieznany układ EPSG:{crs}.").format(crs=crs))
    return [[float(v) for v in to.transform(x, y)] for x, y in pts]


def corners_from_bbox(west, south, east, north, crs=4326):
    """Zakres W, S, E, N jako x/y układu crs (dla stopni: długość, szerokość)."""
    if not (west < east and south < north):
        raise RasterError(t("Zakres musi mieć W < E oraz S < N."))
    return corners_from_affine((east - west, 0.0, west, 0.0, south - north, north), (1, 1), crs)


def manual_corners(view, size):
    """Obraz na środku widoku: 60% szerokości widoku, proporcje obrazu. view = {cx, cy, w} w metrach Web Mercator."""
    w_img, h_img = size
    half_w = 0.3 * float(view["w"])
    half_h = half_w * h_img / w_img
    cx, cy = float(view["cx"]), float(view["cy"])
    return [list(merc_to_lonlat(x, y)) for x, y in
            ((cx - half_w, cy + half_h), (cx + half_w, cy + half_h), (cx + half_w, cy - half_h), (cx - half_w, cy - half_h))]


# ---- plik obrazu -----------------------------------------------------------------------------------------------------

def store_image(path, dest_dir, ident, max_px=MAX_PX):
    """Kopiuje obraz do dest_dir jako PNG (z kanałem alfa) albo JPEG (zdjęcia), zmniejszony do max_px. Zwraca (plik, (w, h) zapisanego, (w, h) źródła)."""
    path = Path(path)
    if not path.is_file():
        raise RasterError(f"Brak pliku {path.name}.")
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:
        raise RasterError(t("Nie da się wczytać obrazu {name}: {exc}").format(name=path.name, exc=exc))
    src_size = img.size
    scale = min(1.0, max_px / max(img.size))
    if scale < 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    has_alpha = img.mode in ("RGBA", "LA", "P") and (img.mode != "P" or "transparency" in img.info)
    if has_alpha:
        name = f"{ident}.png"
        img.convert("RGBA").save(dest_dir / name, "PNG")
    else:
        name = f"{ident}.jpg"
        img.convert("RGB").save(dest_dir / name, "JPEG", quality=92)
    return name, img.size, src_size


def read_stored(dest_dir, name):
    data = (Path(dest_dir) / name).read_bytes()
    return ("image/png" if name.endswith(".png") else "image/jpeg"), data
