"""Paczka do testów na innym komputerze: zbudowana aplikacja + run demo (z zipa z viz_make_demo.py) w jednym zipie.

Użycie: python scripts/viz_pack_test.py <demo.zip> [<wyjście.zip>]
Wymaga wcześniej zbudowanego build_viz/dist/easy-matanimation (scripts\\viz_build.bat). Demo ląduje obok exe jako demo-kutno/ itd.
Zip ma separatory "/" (Compress-Archive pisze "\\").
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "build_viz" / "dist" / "easy-matanimation"
DEMO_TOP = "easy-matanimation-demo/"


def main():
    demo = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build_viz" / "easy-matanimation-test.zip"
    if not (APP / "easy-matanimation.exe").is_file():
        sys.exit(f"brak {APP}, najpierw scripts\\viz_build.bat")
    out.unlink(missing_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(APP.rglob("*")):
            if p.is_file():
                z.write(p, "easy-matanimation/" + p.relative_to(APP).as_posix())
        with zipfile.ZipFile(demo) as d:
            for info in d.infolist():
                name = info.filename
                if info.is_dir() or not name.startswith(DEMO_TOP) or name == DEMO_TOP + "README-DEMO.txt":
                    continue  # README-DEMO dubluje README.txt; LICENSE-DATA.md i foldery runów zostają
                z.writestr("easy-matanimation/" + name[len(DEMO_TOP):], d.read(info), zipfile.ZIP_DEFLATED, 6)
    print(f"{out} {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
