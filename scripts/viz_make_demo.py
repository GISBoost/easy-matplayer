"""Buduje zip z runami demo dla easy-matplayer: pliki runów, gotowe indeksy, łamane drogi i budynki (bez pliku OSM u odbiorcy).

Użycie: uv run --group viz python scripts/viz_make_demo.py <zip> <nazwa>=<katalog runu> [<nazwa>=<katalog runu> ...]
Wymaga pliku OSM (data/raw/osm/lodzkie-*.osm.pbf), z którego liczy łamane drogi i budynki. Indeks zależy od skrótu skryptów pipeline,
więc demo trzeba zbudować od nowa przy każdej zmianie viz_index/viz_classes (robi to krok release).
"""
import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEEDED = ("output_events.xml.zst", "output_network.xml.zst", "output_plans.xml.zst", "output_config.xml")  # config: układ współrzędnych i próbka
TOP = "easy-matplayer-demo"
README = """easy-matplayer: runy demo

Ruch samochodów w Kutnie (symulacja MATSim, próbka 25% mieszkańców), z gotowymi indeksami, więc otwierają się od razu.
Runy w tym folderze:
{runs}

Jak otworzyć: uruchom easy-matplayer.exe, w oknie wyboru folderu wskaż jeden z folderów runu (np. {first}).
Pliki .zst to dane wejściowe MATSim, folder viz/ to indeks i dane pomocnicze (można go usunąć, program zbuduje go od nowa).

Dane i licencje:
- Populacja i plany podróży: dane syntetyczne pochodne publikacji Głównego Urzędu Statystycznego (GUS), CC BY 4.0.
- Sieć drogowa, budynki, łamane drogi: © współtwórcy OpenStreetMap, ODbL 1.0 (https://www.openstreetmap.org/copyright).
  Wysokości budynków to założenia (z tagów OSM albo z klasy budynku), nie pomiar.
- Wyniki symulacji (eventy): CC BY 4.0, jak pliki wynikowe w matsim-example-project.
- Szczegóły: LICENSE-DATA.md w tym folderze. Kod programu: GPL-3.0-or-later.
- W demo nie ma danych komercyjnych (TomTom, HERE) ani kluczy dostępu.
"""


def build(player_cls, run, stage, work, i):
    for name in NEEDED:
        if not (run / name).is_file():
            sys.exit(f"brak {name} w {run}")
        shutil.copy2(run / name, stage / name)  # copy2: czas modyfikacji sieci wchodzi do świeżości cache łamanych
    player = player_cls()
    player.open(stage, remember=False)  # indeks i łamane drogi powstają w kopii, runu źródłowego nie ruszam
    if player.error:
        sys.exit(player.error)
    player.write_site(work / f"site{i}")
    if player.buildings is None or player.curve.n_bent == 0:
        sys.exit("brak pliku OSM: demo bez budynków i łamanych dróg nie ma sensu (data/raw/osm/lodzkie-*.osm.pbf)")
    viz = stage / "viz"
    for junk in ("export", "site", "player.log", "engine.log", "smoke.png"):
        path = viz / junk
        shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zip")
    ap.add_argument("runy", nargs="+", metavar="nazwa=katalog")
    args = ap.parse_args()
    out_zip = Path(args.zip).resolve()
    pairs = [a.split("=", 1) for a in args.runy]
    if any(len(p) != 2 for p in pairs):
        sys.exit("runy podaj jako nazwa=katalog")
    work = Path(tempfile.mkdtemp(prefix="viz_demo_"))
    os.environ["EASY_MATPLAYER_DATA"] = str(work / "data")  # żadnych śladów w profilu użytkownika
    sys.path[:0] = [str(ROOT), str(ROOT / "pipeline")]
    from viz_player.player import Player

    top = work / TOP
    top.mkdir()
    for i, (name, run) in enumerate(pairs):
        (top / name).mkdir()
        build(Player, Path(run).resolve(), top / name, work, i)
    runs = "\n".join(f"- {name}" for name, _ in pairs)
    (top / "README-DEMO.txt").write_text(README.format(runs=runs, first=pairs[0][0]), encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE-DATA.md", top / "LICENSE-DATA.md")
    files = sorted(p for p in top.rglob("*") if p.is_file())
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    out_zip.unlink(missing_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, Path(TOP) / p.relative_to(top))
    print(f"{out_zip} {out_zip.stat().st_size / 1e6:.1f} MB, plików {len(files)}")
    for p in files:
        print(f"  {p.relative_to(top)} {p.stat().st_size / 1e6:.2f} MB")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
