"""Okno odtwarzacza (D24): pywebview (WebView2) serwuje katalog strony po lokalnym HTTP.

  uv run --group viz python -m viz_player output/g5r7b_25pct_s4711   okno
  uv run --group viz python -m viz_player --check output/<run>       akceptacja bez okna
  uv run --group viz python -m viz_player --smoke output/<run>       automat okna (zrzut do output/<run>/viz/)
Testy: uv run --group viz pytest viz_player/tests
"""
import json
import mimetypes
import sys
import time

import numpy as np

from viz_player import check, grab
from viz_player.player import ROOT, Player, clock, note, pick_ident, save_state, saved_run

# MapLibre 6 to moduły ES; przeglądarka odrzuca je bez typu JavaScript, a rejestr Windows bywa pusty
mimetypes.add_type("text/javascript", ".mjs")


class Api:
    """Mostek JS: klatkę liczy klient (engine.js), Python opisuje zaznaczenie. Bez własnego stanu."""

    def __init__(self, player, site=None):
        # pola z _ : pywebview wystawia do JS tylko publiczne atrybuty
        self._player = player
        self._site = site or player.run_dir / "viz" / "site"  # katalog, z którego okno ładuje stronę
        self._window = None

    def attach(self, window):
        self._window = window

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


def smoke(run):
    """Automat okna: prawdziwy WebView2, strona z lokalnego HTTP, klik w chip, szukanie id, Esc."""
    player = Player()
    player.open(run)
    if player.error:
        note(player.run_dir, f"FAIL {player.error}")
        return 1
    import webview
    api = Api(player)
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
            result.update(ok=True, n=len(ref), thin=thin_n, clock=clock(t_win), size=size, key=thin_key)
        except Exception:
            import traceback
            result["error"] = traceback.format_exc()
        finally:
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
        f"mapa={result['size']} klient_vs_python_max={result['worst_m']:.2f} m budynki3D={result.get('buildings', 'brak')} otwarcie_runu={result.get('switched', 'brak')} {png}",
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
