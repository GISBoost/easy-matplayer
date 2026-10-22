"""Akceptacja okna bez okna: klatka z Playera zgadza się z liczbami w meta.json dowolnego runu.

  uv run --group viz python -m viz_player --check output/<run>
Konkretny run referencyjny: viz_player/tests/accept_r7b.py.
"""
import numpy as np

from viz_player.player import CARTO, START, Player, clock, note, pick_ident, sample_label


def run(run):
    """Akceptacja okna na dowolnym runie: klatka musi zgadzać się z liczbami w meta.json."""
    player = Player()
    player.open(run)
    if player.error:
        note(player.run_dir if player.run_dir and player.run_dir.exists() else None, f"FAIL {player.error}")
        return 1
    meta = player.index.meta
    problems = []

    def need(cond, message):
        if not cond:
            problems.append(message)

    lon, lat = player.fwd.transform(player.origin[0], player.origin[1])
    boot = player.boot()
    t0, t1 = float(meta["t_min"]), float(meta["t_max"])
    t_win = float(meta["max_concurrent_6_9_time"])
    need(player.sample == sample_label(meta.get("sample_size")), f"próbka {player.sample}")
    need(abs(player.t_start - (START if t0 <= START <= t1 else t0)) < 1e-6, f"start {player.t_start}")
    need(boot["nLinks"] == int(meta["n_links"]), f"linki {boot['nLinks']} {meta['n_links']}")
    south, west = boot["bounds"][0]
    north, east = boot["bounds"][1]
    need(abs(lat - (south + north) / 2) < 0.02 and abs(lon - (west + east) / 2) < 0.02,
         f"origin {lat:.4f},{lon:.4f} daleko od środka sieci {boot['bounds']}")
    url = "" if boot["basemap"] is None else str(boot["basemap"].get("url", ""))
    need(boot["basemap"] is None or url.startswith(CARTO), "host kafelków")
    need("openstreetmap.org" not in url, "kafelki OSM")
    peak = player.frame(float(meta["max_concurrent_time"]))
    need(peak["n"] == int(meta["max_concurrent"]), f"szczyt {peak['n']} != {meta['max_concurrent']}")
    window = player.frame(t_win)
    need(window["n"] == int(meta["max_concurrent_6_9"]), f"okno 6–9 {window['n']} != {meta['max_concurrent_6_9']}")
    need(window["clock"] == clock(t_win), f"zegar {window['clock']}")
    biggest = max(player.chip_keys, key=lambda key: int(meta["class_counts"].get(key, 0)))
    thin = player.frame(t_win, [key for key in player.chip_keys if key != biggest])
    need(thin["n"] < window["n"], f"filtr {biggest} {thin['n']} przy {window['n']}")
    frame = player._frame_np(t_win, None)
    if len(frame) == 0:
        problems.append("pusta klatka 6–9")
    else:
        panel = player.frame(t_win, None, {"link": int(np.bincount(frame.link).argmax())})["panel"]
        need(panel["kind"] == "link" and not panel["lines"][-1].startswith("teraz 0"), f"link {panel['lines']}")
    ident = pick_ident(player.index)
    need(ident is not None, "brak id z przejazdem i czynnościami")
    axis = []
    if ident is not None:
        followed = player.lookup(ident)
        need(followed.get("followed") == ident, f"lookup {followed}")
        axis = player.frame(t_win, None, {"id": ident}, True)["panel"].get("axis") or []
        need(len(axis) >= 2 and any(seg["trip"] for seg in axis), f"oś {len(axis)}")
        need(sum(bool(seg["on"]) for seg in axis) <= 1, "oś: dwie naraz")
        need([seg["t0"] for seg in axis] == sorted(seg["t0"] for seg in axis), "oś nie po czasie")
    if problems:
        note(player.run_dir, "FAIL " + "; ".join(problems))
        return 1
    base = "wyłączony" if boot["basemap"] is None else "włączony"
    note(
        player.run_dir,
        f"check OK run={player.run_name} start={clock(player.t_start)} probka={player.sample} podklad={base} "
        f"okno6_9={window['n']} szczyt={peak['n']} bez_{biggest}={thin['n']} os={len(axis)} linki={boot['nLinks']} "
        f"lamane={0 if player.curve is None else player.curve.n_bent} id={ident}",
    )
    return 0
