"""Pomiar FPS w prawdziwym oknie (WebView2): ikony / modele 3D x bez / z budynkami 3D, widok gminy i zbliżenie.

  uv run --group viz python -m viz_player.bench output/<run>
Bez GPU: WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--disable-gpu --enable-unsafe-swiftshader" (renderer SwiftShader, osobny profil WebView2).
Wynik: tabela na stdout i linia w player.log. Odtwarzanie 1x w szczycie 6-9, każdy wariant 6 s.
"""
import json
import os
import sys
import time

from viz_player import APP_NAME
from viz_player.player import Player, note
from viz_player.window import Api, _wait_js

MEASURE = """
(function(){
  window._b = {frames: 0, gaps: [], cpu: [], r0: window.renders, last: 0};
  var orig = window.render || render;
  window._origRender = render;
  render = function(){ var a = performance.now(); var r = window._origRender(); window._b.cpu.push(performance.now() - a); return r; };
  function tick(now){ if (window._b.stop) return; if (window._b.last) window._b.gaps.push(now - window._b.last);
    window._b.last = now; window._b.frames++; requestAnimationFrame(tick); }
  requestAnimationFrame(tick);
})()
"""
STOP = """
(function(){
  var b = window._b; b.stop = true; render = window._origRender;
  var g = b.gaps.slice().sort(function(x, y){return x - y;}), c = b.cpu.slice().sort(function(x, y){return x - y;});
  var q = function(a, p){ return a.length ? a[Math.min(a.length - 1, Math.floor(p * a.length))] : 0; };
  var sum = g.reduce(function(s, v){return s + v;}, 0);
  return {fps: g.length / (sum / 1000), gap_p95: q(g, 0.95), gap_max: g[g.length - 1] || 0,
          cpu_med: q(c, 0.5), cpu_p95: q(c, 0.95), n: window.drawnN, renders: window.renders - b.r0};
})()
"""


def bench(run):
    player = Player()
    player.open(run)
    if player.error:
        print("FAIL", player.error)
        return 1
    import webview
    window = webview.create_window(
        f"{APP_NAME} bench", url=str(player.write_site()), js_api=Api(player),
        width=1440, height=900, background_color="#121418",
    )
    rows = []
    result = {"ok": False}

    def js(expr):
        return window.evaluate_js(expr)

    def set_flag(selector, want, var):
        if bool(js(var)) != want:
            js(f"document.querySelector('{selector}').click()")
            time.sleep(0.3)

    def body():
        try:
            print('body start', flush=True)
            if not _wait_js(window, "window.mapReady === true && window.apiReady === true", 60):
                result["error"] = "mapa nie wstała"
                return
            print('ready', flush=True)
            print('renderer', js("(function(){var g=document.createElement('canvas').getContext('webgl2');var e=g&&g.getExtension('WEBGL_debug_renderer_info');return e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):String(g)})()"), flush=True)
            t_win = float(player.index.meta["max_concurrent_6_9_time"])
            js("window.hold = false; t = " + str(t_win) + "; mult = 1; change();")
            if not _wait_js(window, "window.drawnN > 100", 30):
                result["error"] = "brak aut " + str(js("window.drawError"))
                return
            print('pre', flush=True)
            print('drawn', js('window.drawnN'), flush=True)
            # centrum chmury aut do zbliżenia
            center = js("(function(){var o=engine.out,sx=0,sy=0;for(var i=0;i<o.n;i++){sx+=o.lon[i];sy+=o.lat[i];}return [sx/o.n,sy/o.n];})()")
            print('center', center, flush=True)
            views = {"gmina": js("(function(){var c=map.getCenter();return [c.lng,c.lat,map.getZoom()];})()"),
                     "zoom 16.5": [center[0], center[1], 16.5]}
            print('views', views, flush=True)
            for vname, (lon, lat, zoom) in views.items():
                js(f"map.jumpTo({{center: [{lon}, {lat}], zoom: {zoom}, pitch: 0, bearing: 0}}); 0")
                for models in (False, True):
                    for three in (False, True):
                        print('wariant', vname, models, three, flush=True)
                        set_flag("#models", models, "modelsOn")
                        set_flag("#three", three, "threeD")
                        js(f"map.jumpTo({{center: [{lon}, {lat}], zoom: {zoom}, pitch: {55 if three else 0}}}); 0")
                        js("t = " + str(t_win) + "; window.hold = false; document.getElementById('play').textContent === 'start' && document.getElementById('play').click(); change();")
                        time.sleep(2.0)  # rozgrzewka: shadery, triangulacja budynków
                        js(MEASURE)
                        time.sleep(6.0)
                        m = js(STOP)
                        if js("window.drawError"):
                            m["err"] = js("window.drawError")[:120]
                        print('  ->', m, flush=True)
                        rows.append((vname, "modele" if models else "ikony", "3D" if three else "płasko", m))
                        js("document.getElementById('play').textContent === 'pauza' && document.getElementById('play').click()")
            result["ok"] = True
        except Exception:
            import traceback
            result["error"] = traceback.format_exc()
        finally:
            window.destroy()

    import webview as _w
    from viz_player.paths import DATA
    storage = DATA / ("viz_player_webview_sw" if os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS") else "viz_player_webview")
    storage.mkdir(parents=True, exist_ok=True)
    _w.start(body, gui="edgechromium", private_mode=False, http_server=True, storage_path=str(storage), user_agent=APP_NAME)
    if not result.get("ok"):
        print("FAIL", result.get("error"))
        return 1
    lines = [f"{'widok':10} {'znacznik':8} {'budynki':7} {'FPS':>6} {'gap p95':>8} {'gap max':>8} {'cpu med':>8} {'cpu p95':>8} {'aut':>5}"]
    for v, mk, th, m in rows:
        lines.append(f"{v:10} {mk:8} {th:7} {(m['fps'] or 0):6.1f} {m['gap_p95']:7.1f}ms {m['gap_max']:7.1f}ms {m['cpu_med']:7.2f}ms {m['cpu_p95']:7.2f}ms {m['n']:5d}"
                     + (" BŁĄD " + m["err"] if m.get("err") else ""))
    print("\n".join(lines))
    note(player.run_dir, "bench " + json.dumps([[v, mk, th, round(m["fps"], 1), round(m["cpu_med"], 2)] for v, mk, th, m in rows], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(bench(sys.argv[1]))
