"""Okno odtwarzacza (D24): pywebview (WebView2) serwuje katalog strony po lokalnym HTTP.

  uv run --group viz python -m viz_player output/g5r7b_25pct_s4711   okno
  uv run --group viz python -m viz_player --check output/<run>       akceptacja bez okna
  uv run --group viz python -m viz_player --smoke output/<run>       automat okna (zrzut do output/<run>/viz/)
Testy: uv run --group viz pytest viz_player/tests
"""
import base64
import json
import mimetypes
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np

from viz_player import check, grab, ogc
from viz_player.player import ROOT, Player, clock, note, pick_ident, save_state, saved_run

SERVICES = ROOT / "output" / "viz_player_services.json"

# MapLibre 6 to moduły ES; przeglądarka odrzuca je bez typu JavaScript, a rejestr Windows bywa pusty
mimetypes.add_type("text/javascript", ".mjs")


class Api:
    """Mostek JS: klatkę liczy klient (engine.js), Python opisuje zaznaczenie. Bez własnego stanu."""

    def __init__(self, player, site=None, services=None):
        # pola z _ : pywebview wystawia do JS tylko publiczne atrybuty
        self._player = player
        self._services_file = Path(services) if services else SERVICES
        self._lock = threading.Lock()
        self._caps = {}
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
                how = {"3857": "", "4326": " (przeliczany ze stopni)", "proj": " (przeliczany)"}.get(spec.get("mode", "3857"), "")
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
            self._services = [s for s in self._services if s["id"] != ident]
            self._save_services()
        return True

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
        start = ROOT / "output"
        sel = self._window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=str(start if start.is_dir() else ROOT),
        )
        if not sel:
            return {"status": "cancel"}
        return {"status": "path", "path": str(sel[0] if isinstance(sel, (list, tuple)) else sel)}

    def open_path(self, path):
        """Otwiera run w nowym Playerze. Błąd zostawia bieżący run; sukces zapisuje stan i strona ma się przeładować."""
        fresh = Player()
        try:
            fresh.open(path, remember=False)
        except Exception as exc:
            return {"status": "error", "message": f"Nie udało się otworzyć: {exc}"}
        if fresh.error:
            return {"status": "error", "message": fresh.error}
        try:
            fresh.write_site(self._site)
        except Exception as exc:
            return {"status": "error", "message": f"Nie udało się przygotować strony: {exc}"}
        save_state(fresh.run_dir)
        self._player = fresh
        return {"status": "ok", "run": fresh.run_name}


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
    api = Api(player, services=services_file)
    wms_url, wms_requests, wms_stop = _fake_wms()
    window = webview.create_window(
        "easy-matviz smoke", url=str(player.write_site()), js_api=api,
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
            if float(miss.max()) > 2.0:  # długie linki (kilka km): nieliniowość odwzorowania lon/lat vs EPSG:2180
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
                " && document.querySelectorAll('#lg-road div').length >= 3 && !window.drawError"
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
                    "(function(){var c=buf.col, k=engine.classKeys[engine.out.cls[0]], h=CLASS_COLOR[k];"
                    "if(!h)return false;var r=hexRgb(h);return c[0]===r[0]&&c[1]===r[1]&&c[2]===r[2];})()", 15,
                )
            if car_ok is True:
                car_ok = js("boot.classes.every(function(c){return !!CLASS_COLOR[c.key];})")
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
            out, _code = grab.window_png(shot, "easy-matviz smoke")
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
            grab.window_png(shot.with_name("smoke_zoom.png"), "easy-matviz smoke")
            js("window._r0 = window.renders; document.getElementById('models').click(); dirty = true;")
            _wait_js(window, "window.renders > window._r0", 15)
            time.sleep(0.6)
            if js("window.layerIds.indexOf('cars') >= 0 && window.layerIds.indexOf('car-models') < 0") is not True:
                result["error"] = f"po wyłączeniu modeli brak grota: {js('window.layerIds')}"
                return
            grab.window_png(shot.with_name("smoke_icon.png"), "easy-matviz smoke")
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
                "return !!box && !box.hidden && n>0 && bw>40 && tw>bw*0.12;})()"
            )
            if axis_ok is not True:
                result["error"] = "oś " + str(axis_ok)
                return
            js("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))")
            if js("selected === null && follow === false") is not True:
                result["error"] = "escape nie czyści zaznaczenia"
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
            if js("window.svcLayerIds && window.svcLayerIds.length") != 1:
                result["error"] = f"wms: po przeładowaniu strony usługa zniknęła {js('window.svcLayerIds')}"
                return
            js("document.querySelector('#svc-list .svc button').click()")
            if not _wait_js(window, "window.svcLayerIds.length === 0", 10) \
                    or json.loads(services_file.read_text(encoding="utf-8")) != []:
                result["error"] = "wms: usunięcie nie czyści listy"
                return
            result.update(ok=True, n=len(ref), thin=thin_n, clock=clock(t_win), size=size, key=thin_key)
        except Exception:
            import traceback
            result["error"] = traceback.format_exc()
        finally:
            wms_stop()
            window.destroy()

    storage = ROOT / "output" / "viz_player_webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(
        body, gui="edgechromium", private_mode=False, http_server=True,
        storage_path=str(storage), user_agent="easy-matviz",
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


def serve(run):
    player = Player()
    player.open(run)
    import webview
    site = ROOT / "output" / "viz_player_site"  # stały katalog strony: „otwórz run” podmienia jego zawartość i przeładowuje stronę
    api = Api(player, site)
    window = webview.create_window(
        "easy-matviz", url=str(player.write_site(site)), js_api=api,
        width=1440, height=900, background_color="#121418", text_select=True,
    )
    api.attach(window)

    def kick():
        if not _wait_js(window, "window.mapReady === true && window.apiReady === true", seconds=20):
            note(player.run_dir, "FAIL okno nie wstało")

    where = "wyłączony" if player.basemap is None else "włączony"
    note(player.run_dir, f"okno run={player.run_name} podklad={where} blad={player.error or '-'}")
    storage = ROOT / "output" / "viz_player_webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(
        kick, gui="edgechromium", private_mode=False, http_server=True,
        storage_path=str(storage), user_agent="easy-matviz",
    )
    return 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if argv[:1] == ["--check"] and len(argv) >= 2:
        return check.run(argv[1])
    if argv[:1] == ["--smoke"] and len(argv) >= 2:
        return smoke(argv[1])
    run = argv[0] if argv else saved_run()
    if not run:
        print("podaj katalog runu, np. output/g5r7b_25pct_s4711")
        return 2
    return serve(run)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
