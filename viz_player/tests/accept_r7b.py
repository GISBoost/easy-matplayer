"""Akceptacja wizualizera na runie referencyjnym R7b (dane niewersjonowane, nie pytest).

  uv run --group viz python -m viz_player.tests.accept_r7b [output/g5r7b_25pct_s4711]

Liczby to punkt odniesienia sprzed refaktoru fundamentów (2026-10-22, indeks FORMAT 1):
przejazdy, linki, szczyt i okno 6–9 muszą zostać takie same. Wynik: 0 albo 1.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "pipeline"), str(ROOT)]

import numpy as np  # noqa: E402

from viz_player import curves, player as pl  # noqa: E402

RUN = "output/g5r7b_25pct_s4711"
EXPECT = {
    "n_tracks": 24304, "n_links": 10383, "n_nodes": 4534, "n_knots": 3399518, "n_activities": 48608,
    "max_concurrent": 798, "max_concurrent_time": 57539.0,
    "max_concurrent_6_9": 728, "max_concurrent_6_9_time": 28704.0,
    "enters_6_9": 5726, "t_min": 14.0, "t_max": 116633.0, "sample_size": 0.25,
    "class_counts": {"resident": 4336, "commuter": 2410, "outbound": 732, "tlo": 11984, "ciezkie": 4842},
}
PERSON = "r6510903_5"
BENT_LINK = "1807611370009f"
KUTNO = (52.2307, 19.3633)


def main(run=RUN):
    run = Path(run)
    player = pl.Player()
    player.open(run, remember=False)
    problems = [player.error] if player.error else []
    if not problems:
        meta = player.index.meta
        problems += [f"{k}: {meta.get(k)} != {v}" for k, v in EXPECT.items() if meta.get(k) != v]
        lon, lat = player.fwd.transform(*player.origin)
        if abs(lat - KUTNO[0]) > 0.1 or abs(lon - KUTNO[1]) > 0.1:
            problems.append(f"origin {lat:.4f},{lon:.4f} daleko od Kutna")
        if abs(player.t - pl.START) > 1e-6:
            problems.append(f"start {player.t}")
        player.t = float(meta["max_concurrent_time"])
        if player.payload()["n"] != EXPECT["max_concurrent"]:
            problems.append("szczyt klatki okna")
        if player.lookup(PERSON).get("followed") != PERSON:
            problems.append(f"lookup {PERSON}")
        hit = np.where(player.link_id == BENT_LINK)[0]
        if len(hit) != 1:
            problems.append(f"brak linku {BENT_LINK}")
        else:
            i = int(hit[0])
            leng = float(player.link_length[i])
            row = player.index.link_xy[i]
            chord = math.hypot(float(row[2] - row[0]), float(row[3] - row[1]))
            chain = player.curve.chain(i) if player.curve is not None else None
            if not (leng > 1900 and chord < 900) or chain is None or len(chain) < 3:
                problems.append(f"łamana {BENT_LINK}: długość {leng:.0f}, cięciwa {chord:.0f}")
            elif abs(curves.arc_length(chain) - leng) > 1.0:
                problems.append(f"łuk {curves.arc_length(chain):.2f} przy length {leng:.2f}")
    print("FAIL " + "; ".join(problems) if problems else "R7b OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
