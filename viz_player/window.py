"""Okno odtwarzacza (D24): pywebview (WebView2) serwuje katalog strony po lokalnym HTTP.

  uv run --group viz python -m viz_player output/g5r7b_25pct_s4711   okno
  uv run --group viz python -m viz_player --check output/<run>       akceptacja bez okna
  uv run --group viz python -m viz_player --smoke output/<run>       automat okna (zrzut do output/<run>/viz/)
Testy: uv run --group viz pytest viz_player/tests
"""
import json
import sys
import time

import numpy as np

from viz_player import check, grab
from viz_player.player import ROOT, Player, clock, note, pick_ident, saved_run


class Api:
    """Mostek JS: cienka nakładka na Player, bez własnego stanu."""

    def __init__(self, player):
        self._player = player

    def frame(self, t, classes, selected, follow):
        return self._player.frame(t, classes, selected, bool(follow))

    def pick(self, t, classes, lat, lon, lat2, lon2):
        return self._player.pick(t, classes, lat, lon, lat2, lon2)

    def lookup(self, query):
        return self._player.lookup(query)


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
    window = webview.create_window(
        "easy-matviz", url=str(player.write_site()), js_api=Api(player),
        width=1440, height=900, background_color="#121418", text_select=True,
    )
    shot = player.run_dir / "viz" / "smoke.png"
    result = {"ok": False}

    def js(expr):
        return window.evaluate_js(expr)

    def body():
        try:
            if not _wait_js(window, "window.mapReady === true && window.apiReady === true"):
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
            full = player.frame(t_win, player.chip_keys)
            thin_key = player.chip_keys[int(np.bincount(player._frame_np(t_win, None).cls).argmax())]
            js("draw(" + _dumps(full) + ")")
            err, drawn, size = js("window.drawError"), js("window.drawnN"), js("window.mapSize")
            sample = js("document.getElementById('sample').textContent")
            base = js("document.getElementById('base').textContent")
            if err:
                result["error"] = err
                return
            if drawn != full["n"] or full["n"] < 100:
                result["error"] = f"rysunek {drawn} dane {full['n']}"
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
            chip = "document.querySelector('.chip[data-key=\"" + thin_key + "\"]').click()"
            js(chip)
            if thin_key in js("classesOn"):
                result["error"] = f"chip {thin_key} został włączony"
                return
            thin = player.frame(t_win, js("classesOn"))
            js("draw(" + _dumps(thin) + ")")
            if js("window.drawnN") != thin["n"] or not thin["n"] < full["n"]:
                result["error"] = f"filtr {js('window.drawnN')} {thin['n']} {full['n']}"
                return
            js(chip)
            if thin_key not in js("classesOn"):
                result["error"] = f"chip {thin_key} nie wrócił"
                return
            js("draw(" + _dumps(player.frame(t_win, player.chip_keys)) + ")")
            js("document.getElementById('play').click()")
            label = js("document.getElementById('play').textContent")
            js("document.getElementById('play').click()")
            if label != "pauza":
                result["error"] = f"start {label}"
                return
            out, _code = grab.window_png(shot)
            result["grab"] = out.strip()
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
            result.update(ok=True, n=full["n"], thin=thin["n"], clock=full["clock"], size=size, key=thin_key)
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
        f"mapa={result['size']} {png}",
    )
    return 0


def serve(run):
    player = Player()
    player.open(run)
    import webview
    window = webview.create_window(
        "easy-matviz", url=str(player.write_site()), js_api=Api(player),
        width=1440, height=900, background_color="#121418", text_select=True,
    )

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
