"""Buduje zip z runem demo dla easy-matanimation: pliki runu, gotowy indeks, łamane drogi i budynki (bez pliku OSM u odbiorcy).

Użycie: uv run --group viz python scripts/viz_make_demo.py <katalog runu> <zip> [--nazwa demo-kutno]
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
NEEDED = ("output_events.xml.zst", "output_network.xml.zst", "output_plans.xml.zst")
README = """easy-matanimation: run demo ({name})

Ruch samochodów w Kutnie (symulacja MATSim, próbka 25% mieszkańców), z gotowym indeksem, więc otwiera się od razu.

Jak otworzyć: uruchom easy-matanimation.exe, w oknie wyboru folderu wskaż ten folder ({name}).
Pliki .zst to dane wejściowe MATSim, folder viz/ to indeks i dane pomocnicze (można go usunąć, program zbuduje go od nowa).

Dane i licencje:
- Populacja i plany podróży: dane syntetyczne pochodne publikacji Głównego Urzędu Statystycznego (GUS), CC BY 4.0.
- Sieć drogowa, budynki, łamane drogi: © współtwórcy OpenStreetMap, ODbL 1.0 (https://www.openstreetmap.org/copyright).
  Wysokości budynków to założenia (z tagów OSM albo z klasy budynku), nie pomiar.
- Szczegóły: LICENSE-DATA.md w tym folderze. Kod programu: GPL-3.0-or-later.
- W demo nie ma danych komercyjnych (TomTom, HERE) ani kluczy dostępu.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("zip")
    ap.add_argument("--nazwa", default="demo-kutno")
    args = ap.parse_args()
    run, out_zip = Path(args.run).resolve(), Path(args.zip).resolve()
    work = Path(tempfile.mkdtemp(prefix="viz_demo_"))
    os.environ["EASY_MATANIMATION_DATA"] = str(work / "data")  # żadnych śladów w profilu użytkownika
    sys.path[:0] = [str(ROOT), str(ROOT / "pipeline")]
    from viz_player.player import Player

    stage = work / args.nazwa
    stage.mkdir()
    for name in NEEDED:
        if not (run / name).is_file():
            sys.exit(f"brak {name} w {run}")
        shutil.copy2(run / name, stage / name)  # copy2: czas modyfikacji sieci wchodzi do świeżości cache łamanych
    player = Player()
    player.open(stage, remember=False)  # indeks i łamane drogi powstają w kopii, runu źródłowego nie ruszam
    if player.error:
        sys.exit(player.error)
    player.write_site(work / "site")
    if player.buildings is None or player.curve.n_bent == 0:
        sys.exit("brak pliku OSM: demo bez budynków i łamanych dróg nie ma sensu (data/raw/osm/lodzkie-*.osm.pbf)")
    viz = stage / "viz"
    for junk in ("export", "site", "player.log", "engine.log", "smoke.png"):
        path = viz / junk
        shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
    (stage / "README-DEMO.txt").write_text(README.format(name=args.nazwa), encoding="utf-8")
    shutil.copy2(ROOT / "LICENSE-DATA.md", stage / "LICENSE-DATA.md")
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    out_zip.unlink(missing_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, Path(args.nazwa) / p.relative_to(stage))
    print(f"{out_zip} {out_zip.stat().st_size / 1e6:.1f} MB, plików {len(files)}")
    for p in files:
        print(f"  {p.relative_to(stage)} {p.stat().st_size / 1e6:.2f} MB")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
