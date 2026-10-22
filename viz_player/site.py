"""Strona okna jako katalog: shell.html, Leaflet, boot.json i tablice binarne.

pywebview serwuje ten katalog po lokalnym HTTP (webview.start(http_server=True)),
więc strona nie jest jednym stringiem i nie ma limitu wielkości (NavigateToString).
JS pobiera boot.json oraz <nazwa>.bin (little-endian, typy w ARRAY_TYPES).
"""
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARRAY_TYPES = {
    "link_ll": "<f8", "link_type": "u1",
    "curve_off": "<i4", "curve_lon": "<f8", "curve_lat": "<f8",
}


def write_site(dest, boot, arrays):
    """Zapisuje index.html, vendor/, boot.json i <nazwa>.bin. Zwraca ścieżkę index.html."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "shell.html", dest / "index.html")
    shutil.copytree(HERE / "vendor", dest / "vendor", dirs_exist_ok=True)
    (dest / "boot.json").write_text(
        json.dumps(boot, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8",
    )
    for name, data in arrays.items():
        data.astype(ARRAY_TYPES[name], copy=False).tofile(dest / f"{name}.bin")
    return dest / "index.html"
