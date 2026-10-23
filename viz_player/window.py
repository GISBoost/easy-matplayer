"""Okno odtwarzacza (D24): pywebview (WebView2) serwuje katalog strony po lokalnym HTTP.

  uv run --group viz python -m viz_player output/g5r7b_25pct_s4711   okno
  uv run --group viz python -m viz_player --check output/<run>       akceptacja bez okna
  uv run --group viz python -m viz_player --smoke output/<run>       automat okna (zrzut do output/<run>/viz/)
Testy: uv run --group viz pytest viz_player/tests
"""
import base64
import json
import mimetypes
import shutil
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

import numpy as np

from viz_player import check, grab, ogc, rasters
from viz_player import APP_NAME, __version__, i18n, startup
from viz_player.i18n import t
from viz_player.paths import DATA, RES as ROOT, RUNS
from viz_player.player import Player, clock, note, pick_ident, save_pbf, save_state, saved_pbf, saved_run, scaled

SERVICES = DATA / "viz_player_services.json"
RASTERS = DATA / "viz_player_rasters"

# MapLibre 6 to moduły ES; przeglądarka odrzuca je bez typu JavaScript, a rejestr Windows bywa pusty
mimetypes.add_type("text/javascript", ".mjs")


def _busy():
    """Funkcja, nie stała: tekst zależy od języka wybranego po imporcie."""
    return {"status": "error", "message": t("Poprzednia operacja jeszcze trwa.")}


class Api:
    """Mostek JS: klatkę liczy klient (engine.js), Python opisuje zaznaczenie. Bez własnego stanu."""

    def __init__(self, player, site=None, services=None, rasters_dir=None):
        # pola z _ : pywebview wystawia do JS tylko publiczne atrybuty
        self._player = player
        self._services_file = Path(services) if services else SERVICES
        self._lock = threading.Lock()
        self._caps = {}
        self._rasters_dir = Path(rasters_dir) if rasters_dir else RASTERS
        self._staged = {}  # obrazy z plikiem świata czekające na kod EPSG
        self._progress = {"busy": False, "label": "", "frac": 0.0}  # postęp otwierania runu dla paska w panelu
        self._services = self._load_services()
        self._site = site or player.run_dir / "viz" / "site"  # katalog, z którego okno ładuje stronę
        self._window = None

    def attach(self, window):
        self._window = window

    # ---- podkłady WMS / WMTS (jak „dodaj warstwę” w QGIS): lista usług jest globalna dla użytkownika, nie dla runu ----
    def _load_services(self):
        try:
            return json.loads(self._services_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_services(self):
        self._services_file.parent.mkdir(parents=True, exist_ok=True)
        self._services_file.write_text(json.dumps(self._services, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def ogc_connect(self, url):
        """GetCapabilities: lista warstw z adnotacją, czy da się je narysować w tej mapie."""
        try:
            cap = ogc.capabilities(url)
        except ogc.OgcError as exc:
            return {"status": "error", "message": str(exc)}
        self._caps[url.strip()] = cap
        layers = []
        for layer in cap["layers"]:
            row = {"name": layer["name"], "title": layer["title"], "path": layer["path"]}
            try:
                spec = ogc.make_spec(cap, layer["name"])
                how = {"3857": "", "4326": " " + t("(przeliczany ze stopni)"), "proj": " " + t("(przeliczany)")}.get(spec.get("mode", "3857"), "")
                row.update(ok=True, note=(spec.get("crs") or "EPSG:3857") + how)
            except ogc.OgcError as exc:
                row.update(ok=False, note=str(exc))
            layers.append(row)
        return {"status": "ok", "kind": cap["kind"], "title": cap["title"], "layers": layers}

    def ogc_add(self, name, url, layer):
        cap = self._caps.get(url.strip())
        try:
            if cap is None:
                cap = ogc.capabilities(url)
            spec = ogc.make_spec(cap, layer)
        except ogc.OgcError as exc:
            return {"status": "error", "message": str(exc)}
        entry = {"id": uuid.uuid4().hex[:8], "name": (name or "").strip() or layer, "url": url.strip(), "spec": spec, "on": True, "opacity": 1.0}
        with self._lock:
            self._services.append(entry)
            self._save_services()
        return {"status": "ok", "service": entry}

    def ogc_list(self):
        return list(self._services)

    def ogc_remove(self, ident):
        with self._lock:
            gone = [s for s in self._services if s["id"] == ident]
            gone += [self._staged.pop(ident)["entry"]] if ident in self._staged else []
            self._services = [s for s in self._services if s["id"] != ident]
            self._save_services()
        for entry in gone:
            if entry.get("type") == "image":
                (self._rasters_dir / entry["file"]).unlink(missing_ok=True)
        return True

    # ---- własny obraz jako podkład (P5c): z georeferencją z pliku albo ułożony ręcznie ----
    def raster_pick(self):
        import webview
        sel = self._window.create_file_dialog(
            webview.FileDialog.OPEN, directory=str(RUNS),
            file_types=(t("Obrazy (*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.webp)"), t("Wszystkie pliki (*.*)")),
        )
        if not sel:
            return {"status": "cancel"}
        return {"status": "path", "path": str(sel[0] if isinstance(sel, (list, tuple)) else sel)}

    def raster_import(self, path, view):
        """Zapisuje obraz i ustala narożniki. Statusy: ok (georeferencja z pliku), manual (do ułożenia ręcznie), needs_crs, error."""
        ident = uuid.uuid4().hex[:8]
        try:
            georef = rasters.read_georef(path)
            name, size, src = rasters.store_image(path, self._rasters_dir, ident)
            base = {"id": ident, "type": "image", "name": Path(path).stem, "file": name, "size": list(size), "on": True, "opacity": 1.0}
            if georef is None:
                entry = dict(base, corners=rasters.manual_corners(view, size), georef=t("ręczne"))
                return self._add_image(entry, "manual")
            if georef["crs"] is None:
                self._staged[ident] = {"entry": base, "affine": georef["affine"], "src": src, "source": georef["source"]}
                return {"status": "needs_crs", "id": ident, "name": base["name"], "source": georef["source"],
                        "guess": rasters.guess_crs(georef["affine"], src)}
            entry = dict(base, corners=rasters.corners_from_affine(georef["affine"], src, georef["crs"]),
                         georef=f"{georef['source']}, EPSG:{georef['crs']}")
            return self._add_image(entry, "ok")
        except rasters.RasterError as exc:
            return {"status": "error", "message": str(exc)}

    def _add_image(self, entry, status):
        with self._lock:
            self._services.append(entry)
            self._save_services()
        return {"status": status, "service": entry}

    @staticmethod
    def _epsg(value):
        code = ogc.epsg(str(value)) or (str(value).strip() if str(value).strip().isdigit() else None)
        if not code:
            raise rasters.RasterError(t("Podaj kod układu, np. 2180 albo EPSG:4326."))
        return int(code)

    def raster_set_crs(self, ident, crs):
        stage = self._staged.get(ident)
        if stage is None:
            return {"status": "error", "message": t("Ten obraz już nie czeka na układ.")}
        try:
            entry = dict(stage["entry"], corners=rasters.corners_from_affine(stage["affine"], stage["src"], self._epsg(crs)),
                         georef=f"{stage['source']}, EPSG:{self._epsg(crs)}")
        except rasters.RasterError as exc:
            return {"status": "error", "message": str(exc)}
        self._staged.pop(ident)
        return self._add_image(entry, "ok")

    def _update_image(self, ident, corners, how):
        with self._lock:
            for s in self._services:
                if s["id"] == ident and s.get("type") == "image":
                    s["corners"], s["georef"] = corners, how
                    self._save_services()
                    return {"status": "ok", "service": s}
        return {"status": "error", "message": t("Nie ma takiego obrazu.")}

    def raster_set_corners(self, ident, corners):
        return self._update_image(ident, [[float(a), float(b)] for a, b in corners], t("ręczne"))

    def raster_set_bbox(self, ident, west, south, east, north, crs):
        try:
            code = self._epsg(crs)
            corners = rasters.corners_from_bbox(float(west), float(south), float(east), float(north), code)
        except (rasters.RasterError, ValueError) as exc:
            return {"status": "error", "message": str(exc) if isinstance(exc, rasters.RasterError) else t("Zakres musi składać się z czterech liczb.")}
        return self._update_image(ident, corners, t("zakres EPSG:{code}").format(code=code))

    def raster_data(self, ident):
        entry = next((s for s in self._services if s["id"] == ident and s.get("type") == "image"), None)
        if entry is None:
            return {"error": "nieznany obraz"}
        mime, body = rasters.read_stored(self._rasters_dir, entry["file"])
        return {"mime": mime, "b64": base64.b64encode(body).decode("ascii")}

    def ogc_set(self, ident, on, opacity):
        with self._lock:
            for s in self._services:
                if s["id"] == ident:
                    s["on"] = bool(on)
                    s["opacity"] = min(1.0, max(0.0, float(opacity)))
            self._save_services()
        return True

    def ogc_tile(self, ident, z, x, y):
        """Kafelek z/x/y usługi jako base64; błąd jako {"error": zdanie}."""
        spec = next((s["spec"] for s in self._services if s["id"] == ident), None)
        if spec is None:
            return {"error": "nieznana usługa"}
        try:
            mime, body = ogc.tile(spec, int(z), int(x), int(y))
        except ogc.OgcError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}
        return {"mime": mime, "b64": base64.b64encode(body).decode("ascii")}

    def describe(self, t, selected, veh, now):
        return self._player.describe(t, selected, veh, now)

    def pick_run(self):
        """Okno wyboru katalogu runu. Anulowanie zwraca {"status": "cancel"}, bieżący run zostaje."""
        import webview
        sel = self._window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=str(RUNS if RUNS.is_dir() else Path.home()),
        )
        if not sel:
            return {"status": "cancel"}
        return {"status": "path", "path": str(sel[0] if isinstance(sel, (list, tuple)) else sel)}

    def osm_pick(self):
        """Okno wyboru pliku OSM (.osm.pbf). Anulowanie zwraca {"status": "cancel"}."""
        import webview
        sel = self._window.create_file_dialog(
            webview.FileDialog.OPEN, directory=str(RUNS if RUNS.is_dir() else Path.home()),
            file_types=(t("Plik OSM (*.osm.pbf;*.pbf)"), t("Wszystkie pliki (*.*)")),
        )
        if not sel:
            return {"status": "cancel"}
        return {"status": "path", "path": str(sel[0] if isinstance(sel, (list, tuple)) else sel)}

    def osm_use(self, path):
        """Ustawia plik OSM (path pusty: usuwa wybór) i otwiera bieżący run od nowa, żeby powstały budynki i łamane drogi.
        Błąd przywraca poprzedni wybór."""
        if self._progress["busy"]:
            return _busy()
        before = saved_pbf()
        if path:
            problem = _pbf_problem(Path(path))
            if problem:
                return {"status": "error", "message": problem}
        save_pbf(path or None)
        self._report("Start", 0.0)
        try:
            out = self._open_path(str(self._player.run_dir))
        finally:
            self._progress = {"busy": False, "label": "", "frac": 1.0}
        if out["status"] != "ok":
            save_pbf(before)
        print(f"plik OSM {path or '(zapomniany)'}: {out}", flush=True)
        return out

    def progress(self):
        """Postęp trwającego otwierania runu: {busy, label, frac} (frac None: czas nieokreślony)."""
        return dict(self._progress)

    def _report(self, label, frac):
        self._progress = {"busy": True, "label": label, "frac": frac}

    def open_path(self, path):
        """Otwiera run w nowym Playerze. Błąd zostawia bieżący run; sukces zapisuje stan i strona ma się przeładować."""
        if self._progress["busy"]:
            return _busy()
        self._report("Start", 0.0)
        try:
            return self._open_path(path)
        finally:
            self._progress = {"busy": False, "label": "", "frac": 1.0}

    def set_language(self, code):
        """Zapisuje język i otwiera bieżący run od nowa: nazwy klas i komunikaty z Pythona powstają przy otwarciu. Strona się przeładowuje."""
        if self._progress["busy"]:
            return _busy()
        i18n.save(code)
        self._report("Start", 0.0)
        try:
            return self._open_path(str(self._player.run_dir))
        finally:
            self._progress = {"busy": False, "label": "", "frac": 1.0}

    def _open_path(self, path):
        fresh = Player()
        try:
            fresh.open(path, remember=False, progress=scaled(self._report, 0.0, 0.85))
        except Exception as exc:
            return {"status": "error", "message": t("Nie udało się otworzyć: {exc}").format(exc=exc)}
        if fresh.error:
            return {"status": "error", "message": fresh.error}
        try:
            fresh.write_site(self._site, progress=scaled(self._report, 0.85, 1.0))
        except Exception as exc:
            return {"status": "error", "message": t("Nie udało się przygotować strony: {exc}").format(exc=exc)}
        save_state(fresh.run_dir)
        self._player = fresh
        return {"status": "ok", "run": fresh.run_name}


def _pbf_problem(path):
    """Opis kłopotu z plikiem OSM albo None. Sprawdza rozszerzenie i nagłówek (szybko, bez skanowania)."""
    if not path.is_file():
        return t("Nie ma pliku {name}.").format(name=path.name)
    if path.suffix.lower() != ".pbf":
        return t("To nie jest plik .osm.pbf.")
    try:
        import osmium
        with osmium.io.Reader(str(path), osmium.osm.osm_entity_bits.NOTHING) as reader:
            reader.header()
    except Exception as exc:
        return t("Nie da się odczytać pliku OSM: {exc}").format(exc=exc)
    return None


def _dumps(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _wait_js(window, expr, seconds=8):
    deadline = time.perf_counter() + seconds
    value = None
    while time.perf_counter() < deadline:
        value = window.evaluate_js(expr)
        if value:
            return value
        time.sleep(0.1)
    return value


def _fake_wms():
    """Lokalna usługa WMS do smoke: opis z jedną warstwą w EPSG:3857, kafelki to jednolity PNG. Zwraca (adres, lista GetMap, zamknięcie)."""
    import http.server
    import io
    import threading
    import urllib.parse

    from PIL import Image

    png = io.BytesIO()
    Image.new("RGBA", (256, 256), (255, 0, 160, 255)).save(png, "PNG")
    requests = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = {k.upper(): v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
            if q.get("REQUEST") == "GetCapabilities":
                body = (
                    '<?xml version="1.0"?><WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms" xmlns:xlink="http://www.w3.org/1999/xlink">'
                    "<Service><Title>Lokalny test</Title></Service><Capability><Request><GetMap><Format>image/png</Format>"
                    f'<DCPType><HTTP><Get><OnlineResource xlink:href="http://127.0.0.1:{self.server.server_port}/wms?"/></Get></HTTP></DCPType></GetMap></Request>'
                    "<Layer><Title>Korzeń</Title><Layer><Name>rozowa</Name><Title>Różowa warstwa</Title><CRS>EPSG:3857</CRS></Layer></Layer>"
                    "</Capability></WMS_Capabilities>"
                ).encode("utf-8")
                ctype = "text/xml"
            else:
                requests.append(q)
                body, ctype = png.getvalue(), "image/png"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_port}/wms", requests, server.shutdown


def _smoke_osm(window, js):
    """Plik OSM (A2c): panel pokazuje źródło; malutki plik (jeden budynek w centrum Kutna, viz_player/selftest) daje budynek z prawdziwego
    skanu PBF i komunikat o braku dróg tej sieci w pliku; „zapomnij plik” wraca do stanu bez wyboru. Zwraca zdanie błędu albo None."""
    from viz_player.player import save_pbf

    pbf = ROOT / "viz_player" / "selftest" / "kutno_tiny.osm.pbf"
    if not pbf.is_file():
        return f"osm: brak pliku testowego {pbf}"
    ready = "window.mapReady === true && window.apiReady === true"
    try:
        if not str(js("document.getElementById('osmname').textContent")).startswith("OSM: "):
            return "osm: brak linii źródła w panelu"
        js(f"window.useOsm({json.dumps(str(pbf).replace(chr(92), '/'))});")
        if not _wait_js(window, f"boot.osm && boot.osm.user === true && boot.osm.file === 'kutno_tiny.osm.pbf' && {ready} && window.drawnN > 0", 180):
            return f"osm: po wskazaniu pliku {js('JSON.stringify(boot.osm)')} msg={js('document.getElementById(\'runmsg\').textContent')}"
        curves_text = str(js("document.getElementById('curves').textContent"))
        if "nie pokrywa" not in curves_text and "brak origid" not in curves_text:
            return f"osm: brak komunikatu o pokryciu: {curves_text!r}"
        buildings_note = str(js("boot.buildingsNote"))
        if not buildings_note.startswith("budynki 1:"):
            return f"osm: budynek z malutkiego pliku: {buildings_note!r}"
        if js("document.getElementById('osm-clear').hidden"):
            return "osm: brak przycisku „zapomnij plik”"
        js("document.getElementById('osm-clear').click();")
        if not _wait_js(window, f"boot.osm && boot.osm.user === false && {ready} && window.drawnN > 0", 180):
            return f"osm: po zapomnieniu pliku {js('JSON.stringify(boot.osm)')} msg={js('document.getElementById(' + chr(34) + 'runmsg' + chr(34) + ').textContent')}"
        return None
    finally:
        save_pbf(None)


def _smoke_images(window, js, work, services_file):
    """Własny obraz (P5c): bez georeferencji (ręczne ułożenie, przeciąganie, zakres) i z plikiem świata bez układu. Zwraca zdanie błędu albo None."""
    from PIL import Image

    work.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 100), (240, 200, 40)).save(work / "plan.png")
    Image.new("RGB", (60, 40), (40, 120, 240)).save(work / "ortho.png")
    (work / "ortho.wld").write_text("10\n0\n0\n-10\n500005\n599995\n")
    plan = json.dumps(str(work / "plan.png").replace("\\", "/"))
    ortho = json.dumps(str(work / "ortho.png").replace("\\", "/"))

    def call(expr):
        js("window._r = undefined; (" + expr + ").then(function(r){window._r = r;}, function(e){window._r = {status: 'exc', message: String(e && e.stack || e)};});")
        if not _wait_js(window, "window._r !== undefined", 20):
            return None
        return js("window._r")

    # bez georeferencji: wstaje jako „manual”, od razu w trybie ręcznego układania z pięcioma uchwytami
    r = call(f"window.addImagePath({plan})")
    if not r or r.get("status") != "manual":
        return f"obraz bez georeferencji: {r} {js('window.drawError')}"
    ident = r["service"]["id"]
    if js("document.querySelectorAll('#hnd i').length") != 5 or js("document.getElementById('edit-hint').hidden"):
        return "obraz bez georeferencji: brak uchwytów edycji"
    if not _wait_js(window, f"map.getSource('svc-{ident}') && map.isSourceLoaded('svc-{ident}')", 20):
        return "obraz bez georeferencji: źródło nie załadowane " + str(js("window.drawError"))
    geom = (
        "(function(){var c=services.find(function(s){return s.id==='" + ident + "';}).corners.map(function(p){var q=map.project(p);return [q.x,q.y];});"
        "return {c:c};})()"
    )
    before = js(geom)["c"]

    def drag(handle, dx, dy):
        js(
            "(function(){var h=document.querySelector('#hnd i[data-k=\"" + handle + "\"]').getBoundingClientRect();"
            "var x=h.left+h.width/2,y=h.top+h.height/2;"
            "document.querySelector('#hnd i[data-k=\"" + handle + "\"]').dispatchEvent(new PointerEvent('pointerdown',{clientX:x,clientY:y,pointerId:7,bubbles:true,cancelable:true}));"
            f"window.dispatchEvent(new PointerEvent('pointermove',{{clientX:x+({dx}),clientY:y+({dy}),pointerId:7}}));"
            "window.dispatchEvent(new PointerEvent('pointerup',{pointerId:7}));})()"
        )
        time.sleep(0.5)

    drag("mid", 120, 40)
    after = js(geom)["c"]
    mid_b = [(before[0][i] + before[2][i]) / 2 for i in (0, 1)]
    mid_a = [(after[0][i] + after[2][i]) / 2 for i in (0, 1)]
    if abs(mid_a[0] - mid_b[0] - 120) > 3 or abs(mid_a[1] - mid_b[1] - 40) > 3:
        return f"przesunięcie środkiem: {mid_b} -> {mid_a}"
    import math

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    w0, h0 = dist(after[0], after[1]), dist(after[0], after[3])
    drag("2", 80, 60)
    scaled = js(geom)["c"]
    w1, h1 = dist(scaled[0], scaled[1]), dist(scaled[0], scaled[3])
    if not (w1 > w0 * 1.05 and abs(w1 / h1 - w0 / h0) < 0.02 * (w0 / h0)) or dist(scaled[0], after[0]) > 3:
        return f"skalowanie rogiem: szer {w0:.1f}->{w1:.1f}, wys {h0:.1f}->{h1:.1f}, kotwica {dist(scaled[0], after[0]):.1f}"
    saved = call("svcApi().ogc_list()")
    mine = next((x for x in saved if x["id"] == ident), None)
    if not mine or abs(mine["corners"][0][0] - js("services.find(function(s){return s.id==='" + ident + "';}).corners[0][0]")) > 1e-9:
        return "obraz bez georeferencji: ułożenie nie zapisane"
    js("document.getElementById('edit-done').click()")
    if js("document.querySelectorAll('#hnd').length") != 0:
        return "obraz: gotowe nie chowa uchwytów"

    # zakres wpisany ręcznie
    js(f"window.editImage('{ident}'); document.getElementById('edit-bbox').click();")
    js("document.getElementById('img-epsg').value='4326'; document.getElementById('img-w').value='19,30'; document.getElementById('img-e').value='19.40';"
       "document.getElementById('img-s').value='52.20'; document.getElementById('img-n').value='52.26'; document.getElementById('img-form').requestSubmit();")
    if not _wait_js(window, "document.getElementById('img-dlg').hidden && document.querySelectorAll('#hnd').length === 0", 10):
        return "zakres: " + str(js("document.getElementById('img-msg').textContent"))
    c = js("services.find(function(s){return s.id==='" + ident + "';}).corners")
    if abs(c[0][0] - 19.30) > 1e-6 or abs(c[0][1] - 52.26) > 1e-6 or abs(c[2][0] - 19.40) > 1e-6 or abs(c[2][1] - 52.20) > 1e-6:
        return f"zakres: narożniki {c}"

    # plik świata bez układu: pyta o EPSG z podpowiedzią 2180
    r = call(f"window.addImagePath({ortho})")
    if not r or r.get("status") != "needs_crs" or r.get("guess") != 2180:
        return f"plik świata: {r}"
    if js("document.getElementById('img-dlg').hidden") or js("document.getElementById('img-epsg').value") != "2180":
        return "plik świata: brak okna z podpowiedzią układu"
    js("document.getElementById('img-form').requestSubmit();")
    if not _wait_js(window, "document.getElementById('img-dlg').hidden && window.svcLayerIds.length === 3", 10):
        return "plik świata: po podaniu układu brak warstwy " + str(js("document.getElementById('img-msg').textContent"))
    placed = js("services[services.length-1].corners")
    if not (18 < placed[0][0] < 21 and 51 < placed[0][1] < 54 and placed[0][1] > placed[3][1]):
        return f"plik świata: narożniki {placed}"
    return None


def smoke(run):
    """Automat okna: prawdziwy WebView2, strona z lokalnego HTTP, klik w chip, szukanie id, Esc."""
    player = Player()
    player.open(run)
    if player.error:
        note(player.run_dir, f"FAIL {player.error}")
        return 1
    import webview
    services_file = player.run_dir / "viz" / "smoke_services.json"
    services_file.unlink(missing_ok=True)
    shutil.rmtree(player.run_dir / "viz" / "smoke_rasters", ignore_errors=True)
    shutil.rmtree(player.run_dir / "viz" / "smoke_img", ignore_errors=True)
    api = Api(player, services=services_file, rasters_dir=player.run_dir / "viz" / "smoke_rasters")
    wms_url, wms_requests, wms_stop = _fake_wms()
    window = webview.create_window(
        f"{APP_NAME} smoke", url=str(player.write_site()), js_api=api,
        width=1440, height=900, background_color="#121418", text_select=True,
    )
    api.attach(window)
    shot = player.run_dir / "viz" / "smoke.png"
    result = {"ok": False}

    def js(expr):
        return window.evaluate_js(expr)

    def body():
        try:
            if not _wait_js(window, "window.mapReady === true && window.apiReady === true", 30):
                result["error"] = "mapa nie wstała"
                return
            n_curve = int(js("boot.curveLon ? boot.curveLon.length : 0") or 0)
            if n_curve != player.boot()["nCurve"]:
                result["error"] = f"łamane w oknie {n_curve}, w indeksie {player.boot()['nCurve']}"
                return
            if not _wait_js(window, f"document.getElementById('clock').textContent === '{clock(player.t_start)}'", 15):
                result["error"] = "brak klatki " + str(js("window.drawError"))
                return
            js("window.hold = true")
            title, ver = js("document.title"), js("document.getElementById('ver').textContent")
            if title != APP_NAME or ver != "v" + __version__:
                result["error"] = f"tytuł albo wersja okna: {title!r} {ver!r}"
                return
            time.sleep(0.4)
            t_win = float(player.index.meta["max_concurrent_6_9_time"])
            ref = player._frame_np(t_win, None)
            thin_key = player.chip_keys[int(np.bincount(ref.cls).argmax())]
            thin_n = len(player._frame_np(t_win, [k for k in player.chip_keys if k != thin_key]))
            size = js("window.mapSize")
            sample = js("document.getElementById('sample').textContent")
            base = js("document.getElementById('base').textContent")
            if js("window.drawError"):
                result["error"] = js("window.drawError")
                return
            if len(ref) < 100:
                result["error"] = f"za mało aut w szczycie: {len(ref)}"
                return
            if not size or int(str(size).split("x")[0]) < 200:
                result["error"] = f"mapa {size}"
                return
            if player.sample not in str(sample):
                result["error"] = f"próbka {sample}"
                return
            if player.basemap is None and str(base) != "Podkład wyłączony.":
                result["error"] = f"podkład {base}"
                return
            # Klatka klienta (engine.js w oknie) = klatka silnika Pythona
            js("window._cf = undefined; window.clientFrame(" + str(t_win) + ", " + json.dumps(player.chip_keys) + ").then(function(r){window._cf = r;});")
            if not _wait_js(window, "window._cf !== undefined", 15):
                result["error"] = "klatka klienta nie wróciła " + str(js("window.drawError"))
                return
            got = js("window._cf")
            order = np.argsort(ref.track)
            if got["n"] != len(ref) or list(got["track"]) != [int(v) for v in ref.track[order]]:
                result["error"] = f"klient {got['n']} aut, Python {len(ref)}"
                return
            lon, lat = player.fwd.transform(
                ref.xy[order, 0].astype(np.float64) + player.origin[0], ref.xy[order, 1].astype(np.float64) + player.origin[1],
            )
            cl = np.cos(np.radians(lat))
            miss = np.hypot((np.asarray(got["lon"]) - lon) * cl, np.asarray(got["lat"]) - lat) * 111194.93
            # Klient interpoluje liniowo w lon/lat, Python w układzie runu: na linkach dłuższych niż kilka km (np. łączniki spoza miasta
            # w modelu Wiednia, do 300 km) różnią się nieliniowością odwzorowania, nie błędem. Porównuję auta na zwykłych linkach.
            miss = miss[np.asarray(player.link_length)[ref.link[order]] < 3000.0]
            if len(miss) < 100:
                result["error"] = f"za mało aut na zwykłych linkach do porównania: {len(miss)}"
                return
            if float(miss.max()) > 2.0:
                result["error"] = f"pozycje klienta różnią się od Pythona o {float(miss.max()):.3f} m"
                return
            result["worst_m"] = float(miss.max())
            js("document.getElementById('hide').click()")
            time.sleep(0.3)
            back = js(
                "(function(){var b=document.getElementById('hide');var r=b.getBoundingClientRect();"
                "return r.width>20 && r.left>=0 && r.right<=window.innerWidth+1 && b.textContent==='panel';})()"
            )
            js("document.getElementById('hide').click()")
            if back is not True:
                result["error"] = "przycisk panelu " + str(back)
                return
            # Rysunek: czas ustawiony na szczyt, pętla rysuje klatkę klienta
            js("window.hold = false; t = " + str(t_win) + "; change();")
            if not _wait_js(window, f"window.drawnN === {len(ref)}", 15):
                result["error"] = f"rysunek {js('window.drawnN')} aut, Python {len(ref)} {js('window.drawError')}"
                return
            # Kliknięcie w auto na mapie: zaznaczona jest osoba tego auta
            ident_vehicle = js("(function(){var o=engine.out;var tr=o.track[0];var q=map.project([o.lon[0],o.lat[0]]);"
                               "map.fire('click', {point: q});return engine.personId(tr);})()")
            if js("selected && selected.id") != ident_vehicle or not ident_vehicle:
                result["error"] = f"klik w auto: zaznaczono {js('selected')}, auto {ident_vehicle}"
                return
            js("selected = null; follow = false; change();")
            chip = "document.querySelector('.chip[data-key=\"" + thin_key + "\"]').click()"
            js(chip)
            if thin_key in js("classesOn"):
                result["error"] = f"chip {thin_key} został włączony"
                return
            if not _wait_js(window, f"window.drawnN === {thin_n}", 15) or not thin_n < len(ref):
                result["error"] = f"filtr {js('window.drawnN')} aut, Python {thin_n} z {len(ref)}"
                return
            js(chip)
            if thin_key not in js("classesOn"):
                result["error"] = f"chip {thin_key} nie wrócił"
                return
            if not _wait_js(window, f"window.drawnN === {len(ref)}", 15):
                result["error"] = f"po chipie {js('window.drawnN')} aut, Python {len(ref)}"
                return
            mult_seq = js(
                "(function(){var g=function(){return document.getElementById('mval').textContent;};var o=[g()];"
                "document.getElementById('mdn').click();o.push(g());document.getElementById('mup').click();o.push(g());"
                "document.querySelector('#bar button[data-m=\"10\"]').click();document.getElementById('mdn').click();o.push(g());"
                "o.push(document.querySelectorAll('#bar button[data-m].on').length);"
                "document.querySelector('#bar button[data-m=\"1\"]').click();return o;})()"
            )
            if mult_seq != ["1×", "1×", "2×", "9×", 0]:
                result["error"] = f"mnożnik {mult_seq}"
                return
            js("document.getElementById('osmroads').click()")
            road_ok = js(
                "osmRoads === true && !document.getElementById('lg-road').hidden"
                " && document.querySelectorAll('#lg-road div').length >= " + str(min(3, len(set(player.type_names)))) + " && !window.drawError"  # sieć bez typów dróg (Wiedeń) ma jedną pozycję legendy
            )
            js("document.getElementById('osmroads').click()")
            if road_ok is not True or js("osmRoads === false && document.getElementById('lg-road').hidden") is not True:
                result["error"] = f"kolor dróg {road_ok} {js('window.drawError')}"
                return
            js("document.getElementById('carcolor').click()")
            car_ok = js(
                "carByClass === true && document.getElementById('lg-speed').hidden && !document.getElementById('lg-class').hidden"
                " && document.querySelectorAll('#lg-class div').length === boot.classes.length && !window.drawError"
            )
            if car_ok is True:
                js("t = t + 1; change();")
                car_ok = _wait_js(
                    window,
                    "(function(){var c=buf.col, k=engine.classKeys[engine.out.cls[0]], h=CLASS_COLOR[k]||CLASS_COLOR['?'];"
                    "var r=hexRgb(h);return c[0]===r[0]&&c[1]===r[1]&&c[2]===r[2];})()", 15,
                )
            js("document.getElementById('carcolor').click()")
            if car_ok is not True or js("carByClass === false && !document.getElementById('lg-speed').hidden") is not True:
                result["error"] = f"kolor auta {car_ok} {js('window.drawError')}"
                return
            scale_ok = js("markerScale(15) === 1 && markerScale(5) === MARKER.min && markerScale(30) === MARKER.max && markerScale(17) > markerScale(13)")
            if scale_ok is not True or js("window.drawError"):
                result["error"] = f"znacznik {scale_ok} {js('window.drawError')}"
                return
            js("document.getElementById('play').click()")
            label = js("document.getElementById('play').textContent")
            js("document.getElementById('play').click()")
            if label != "pauza":
                result["error"] = f"start {label}"
                return
            if player.buildings is not None:
                js("document.getElementById('three').click()")
                if not _wait_js(window, "threeD === true && map.getPitch() > 50 && buildingData !== null", 15):
                    result["error"] = f"3D: pitch {js('map.getPitch()')} budynki {js('buildingData && buildingData.length')} {js('window.drawError')}"
                    return
                if js("buildingData.length") != player.buildings["n"] or js("window.drawError"):
                    result["error"] = f"budynki w oknie {js('buildingData.length')}, w eksporcie {player.buildings['n']} {js('window.drawError')}"
                    return
                result["buildings"] = player.buildings["n"]
                js("document.getElementById('three').click()")
                if not _wait_js(window, "threeD === false && map.getPitch() < 5", 15):
                    result["error"] = "3D nie wyłącza się " + str(js("map.getPitch()"))
                    return
            out, _code = grab.window_png(shot, f"{APP_NAME} smoke")
            result["grab"] = out.strip()
            js(
                "window.hold = false; window._r0 = window.renders; document.getElementById('models').click();"
                "(function(){var fr = engine.out, i = -1; for (var k = 0; k < fr.n; k++) { if (!engine.classHeavy[fr.cls[k]] && Math.abs(Math.sin(fr.heading[k])) > 0.7) { i = k; break; } }"
                "if (i >= 0) map.jumpTo({center: [fr.lon[i], fr.lat[i]], zoom: 18.5}); window._zi = i; })()"
            )
            if js("window._zi") < 0 or not _wait_js(window, "window.renders > window._r0 && !window.drawError", 15):
                result["error"] = f"modele 3D zi={js('window._zi')} r={js('window.renders')} r0={js('window._r0')} hold={js('window.hold')} err={js('window.drawError')}"
                return
            if js("window.layerIds.indexOf('cars') < 0 && window.layerIds.indexOf('car-outline') < 0 && window.layerIds.indexOf('car-models') >= 0") is not True:
                result["error"] = f"przy modelach grot nadal rysowany: {js('window.layerIds')}"
                return
            scale = js("modelScale(false)")
            if not (2.5 < scale < 3.5) or not js("modelScale(true) > 1"):
                result["error"] = f"skala modelu {scale} (oczekiwane ok. 3 przy zoomie 18,5)"
                return
            time.sleep(0.6)
            grab.window_png(shot.with_name("smoke_zoom.png"), f"{APP_NAME} smoke")
            js("window._r0 = window.renders; document.getElementById('models').click(); dirty = true;")
            _wait_js(window, "window.renders > window._r0", 15)
            time.sleep(0.6)
            if js("window.layerIds.indexOf('cars') >= 0 && window.layerIds.indexOf('car-models') < 0") is not True:
                result["error"] = f"po wyłączeniu modeli brak grota: {js('window.layerIds')}"
                return
            grab.window_png(shot.with_name("smoke_icon.png"), f"{APP_NAME} smoke")
            js("window.hold = true;")
            ident = pick_ident(player.index)
            js("window.hold = false; t = " + str(t_win) + "; change();")
            js(f"document.getElementById('q').value = {json.dumps(ident)}; document.getElementById('find').requestSubmit();")
            if not _wait_js(window, f"document.getElementById('detail').innerText.indexOf({json.dumps(ident)}) >= 0", 15):
                result["error"] = f"panel {js('document.getElementById(\"detail\").innerText')}"
                return
            axis_ok = js(
                "(function(){var box=document.getElementById('axis');"
                "var bar=document.getElementById('axis-bar');"
                "var n=bar?bar.querySelectorAll('.seg').length:0;"
                "var trip=bar?bar.querySelector('.seg.trip'):null;"
                "var tw=trip?trip.getBoundingClientRect().width:0;"
                "var bw=bar?bar.getBoundingClientRect().width:0;"
                "return !!box && !box.hidden && n>0 && bw>40 && tw>2;})()"
            )
            if axis_ok is not True:
                result["error"] = "oś " + str(axis_ok)
                return
            js("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
            if js("selected === null && follow === false") is not True:
                result["error"] = "escape nie czyści zaznaczenia"
                return
            # przycisk „cały obszar sieci”: z odległego, mocno przybliżonego widoku wraca do obwiedni sieci
            js("map.jumpTo({center: [boot.bounds[0][1], boot.bounds[0][0]], zoom: 17.5, bearing: 0, pitch: 0}); 0")
            time.sleep(0.5)
            js("document.getElementById('fit').click()")
            fit_ok = _wait_js(
                window,
                "(function(){var v=map.getBounds(),b=boot.bounds;return !map.isMoving() && map.getZoom()<14 && (map.getZoom()<=map.getMinZoom()+1e-6"
                " || (v.getWest()<=b[0][1]+1e-6 && v.getSouth()<=b[0][0]+1e-6 && v.getEast()>=b[1][1]-1e-6 && v.getNorth()>=b[1][0]-1e-6));})()", 10,  # sieć szersza niż minZoom (Wiedeń, 1000 km): widok stoi na minZoom
            )
            if not fit_ok:
                result["error"] = f"cały obszar: widok {js('JSON.stringify([map.getBounds().toArray(), boot.bounds, map.getZoom()])')}"
                return
            # skala mapy zmienia się z zoomem, a oddalenie sięga zoomu 3 (cały kraj)
            scale = []
            for zoom in (16, 12):
                js(f"map.jumpTo({{zoom: {zoom}}}); 0")
                time.sleep(0.4)
                scale.append(js("(document.querySelector('.maplibregl-ctrl-scale')||{}).textContent||''"))
            overlap = js("(function(){var a=document.querySelector('.maplibregl-ctrl-scale').getBoundingClientRect(),b=document.getElementById('legend').getBoundingClientRect();"
                         "return !(a.right<=b.left||a.left>=b.right||a.bottom<=b.top||a.top>=b.bottom);})()")
            if overlap is not False:
                result["error"] = "skala zasłonięta przez legendę"
                return
            js("map.jumpTo({zoom: 0}); 0")
            if not all(scale) or scale[0] == scale[1] or js("map.getMinZoom() <= 3 && map.getZoom() <= 3.01") is not True:
                result["error"] = f"skala lub minZoom: {scale}, zoom {js('map.getZoom()')}"
                return
            # podkład WMS jak w QGIS: dialog, połączenie, wybór warstwy, kafelki z usługi (lokalna atrapa)
            js("document.getElementById('svc-add').click()")
            js(f"document.getElementById('svc-url').value = {json.dumps(wms_url)}; document.getElementById('svc-form').requestSubmit();")
            if not _wait_js(window, "document.querySelectorAll('#svc-layers input:not(:disabled)').length === 1", 20):
                result["error"] = f"wms: lista warstw {js('document.getElementById(\"svc-msg\").textContent')}"
                return
            js("document.querySelector('#svc-layers input').click(); document.getElementById('svc-ok').click();")
            if not _wait_js(window, "window.svcLayerIds && window.svcLayerIds.length === 1 && document.getElementById('svc-dlg').hidden", 20):
                result["error"] = f"wms: warstwa nie dodana {js('window.drawError')}"
                return
            js("map.jumpTo({zoom: 12}); 0")
            if not _wait_js(window, "map.isSourceLoaded(window.svcLayerIds[0])", 30) or not wms_requests:
                result["error"] = f"wms: brak kafelków, zapytań {len(wms_requests)}"
                return
            q = wms_requests[0]
            if q.get("CRS") != "EPSG:3857" or q.get("LAYERS") != "rozowa" or len(q.get("BBOX", "").split(",")) != 4:
                result["error"] = f"wms: zapytanie {q}"
                return
            js("document.querySelector('#svc-list .svc input[type=checkbox]').click()")
            if js("map.getLayoutProperty(window.svcLayerIds[0], 'visibility')") != "none":
                result["error"] = "wms: wyłączenie nie chowa warstwy"
                return
            js("document.querySelector('#svc-list .svc input[type=checkbox]').click()")
            result["wms_tiles"] = len(wms_requests)
            err = _smoke_images(window, js, player.run_dir / "viz" / "smoke_img", services_file)
            if err:
                result["error"] = err
                return
            # „otwórz run”: zły katalog zostawia bieżący run i pisze zdanie, drugi run podmienia stronę, powrót przywraca
            home = player.run_name
            js("window._or = undefined; window.openRunPath('C:/nie/ma/takiego/runu').then(function(r){window._or = r;});")
            if not _wait_js(window, "window._or !== undefined", 20) or js("window._or.status") != "error"                     or js("document.getElementById('runmsg').hidden") or js("boot.run") != home:
                result["error"] = f"otwórz run, zły katalog: {js('window._or')} / {js('boot.run')}"
                return
            other = player.run_dir.parent / "g5r6_25pct_s4711"
            if (other / "output_events.xml.zst").exists():
                for want in (other.name, home):
                    path = str((other if want == other.name else player.run_dir)).replace("\\", "/")
                    js(f"window.openRunPath({json.dumps(path)});")
                    if not _wait_js(window, f"boot.run === {json.dumps(want)} && window.mapReady === true && window.apiReady === true && window.drawnN > 0", 180):
                        result["error"] = f"otwórz run {want}: {js('boot.run')} {js('window.drawError')} msg={js('document.getElementById(\"runmsg\").textContent')}"
                        return
                result["switched"] = other.name
            err = _smoke_osm(window, js)
            if err:
                result["error"] = err
                return
            if js("window.svcLayerIds && window.svcLayerIds.length") != 3:
                result["error"] = f"wms: po przeładowaniu strony usługa zniknęła {js('window.svcLayerIds')}"
                return
            for _ in range(3):
                js("document.querySelector('#svc-list .svc button[title=\"usuń\"]').click()")
                time.sleep(0.4)
            if not _wait_js(window, "window.svcLayerIds.length === 0", 10) \
                    or json.loads(services_file.read_text(encoding="utf-8")) != [] \
                    or any((player.run_dir / "viz" / "smoke_rasters").glob("*")):
                result["error"] = "wms: usunięcie nie czyści listy albo plików obrazów"
                return
            result.update(ok=True, n=len(ref), thin=thin_n, clock=clock(t_win), size=size, key=thin_key)
        except Exception:
            import traceback
            result["error"] = traceback.format_exc()
        finally:
            wms_stop()
            window.destroy()

    storage = DATA / "viz_player_webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(
        body, gui="edgechromium", private_mode=False, http_server=True,
        storage_path=str(storage), user_agent=APP_NAME,
    )
    if not result.get("ok"):
        note(player.run_dir, "FAIL smoke " + str(result.get("error") or result))
        return 1
    png = "zrzut=" + str(shot) if shot.exists() and shot.stat().st_size >= 10000 else "zrzut=nieudany " + str(result.get("grab"))
    note(
        player.run_dir,
        f"smoke OK n={result['n']} bez_{result['key']}={result['thin']} zegar={result['clock']} "
        f"mapa={result['size']} klient_vs_python_max={result['worst_m']:.2f} m budynki3D={result.get('buildings', 'brak')} otwarcie_runu={result.get('switched', 'brak')} wms_kafelki={result.get('wms_tiles', 'brak')} {png}",
    )
    return 0


def prepare(run, site):
    """Otwiera run i zapisuje stronę okna. Pasek postępu pokazuje się, gdy to trwa dłużej niż chwilę (indeks 100%: ok. 80 s)."""
    def work(progress):
        player = Player()
        player.open(run, progress=scaled(progress, 0.0, 0.85))
        index_html = None if player.error else player.write_site(site, progress=scaled(progress, 0.85, 1.0))
        return player, index_html

    return startup.with_progress(t("Otwieram run {name}").format(name=Path(run).name), work)


def serve(run, explicit=False):
    """explicit: run podany w wierszu poleceń (błąd kończy program); inaczej brak runu albo błąd otwiera wybór folderu."""
    import webview
    if startup.webview2_missing():  # sprawdzenie przed budową indeksu: bez runtime okno byłoby puste, a program nie kończyłby pracy
        startup.show_webview2_missing()
        return 1
    site = DATA / "viz_player_site"  # stały katalog strony: „otwórz run” podmienia jego zawartość i przeładowuje stronę
    while True:
        if not run or not Path(run).is_dir():
            if explicit:
                startup.show_error(t("Nie da się otworzyć runu"), t("Brak katalogu {run}.").format(run=run))
                return 1
            run = startup.pick_run(RUNS if RUNS.is_dir() else Path.home())
            if not run:
                return 0
        try:
            player, index_html = prepare(run, site)
        except Exception as exc:  # uszkodzony plik runu albo OSM; zapamiętany run nie może zamykać drogi do wyboru innego
            if explicit:
                raise
            traceback.print_exc()
            error = f"{type(exc).__name__}: {exc}"
        else:
            error = player.error
        if not error:
            break
        startup.show_error(t("Nie da się otworzyć runu"), error)
        if explicit:
            return 1
        run = None
    api = Api(player, site)
    window = webview.create_window(
        APP_NAME, url=str(index_html), js_api=api,
        width=1440, height=900, background_color="#121418", text_select=True,
    )
    api.attach(window)

    def kick():
        if not _wait_js(window, "window.mapReady === true && window.apiReady === true", seconds=20):
            note(player.run_dir, "FAIL okno nie wstało")

    where = "wyłączony" if player.basemap is None else "włączony"
    note(player.run_dir, f"okno run={player.run_name} podklad={where} blad={player.error or '-'}")
    storage = DATA / "viz_player_webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(
        kick, gui="edgechromium", private_mode=False, http_server=True,
        storage_path=str(storage), user_agent=APP_NAME,
    )
    return 0


def main(argv):
    startup.setup_logging()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    i18n.load()
    if argv[:1] in (["--check"], ["--smoke"]):  # harness czyta polskie napisy z DOM i z komunikatów
        i18n.set_lang("pl")
    if argv[:1] == ["--check"] and len(argv) >= 2:
        return check.run(argv[1])
    if argv[:1] == ["--smoke"] and len(argv) >= 2:
        return smoke(argv[1])
    if argv[:1] == ["--version"]:
        print(f"{APP_NAME} {__version__}")
        return 0
    try:
        return serve(argv[0] if argv else saved_run(), explicit=bool(argv))
    except Exception:
        startup.crash()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
