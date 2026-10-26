"""Buduje statyczną stronę z odtwarzaczem (GitHub Pages) z folderów runów MATSim.

  uv run --group viz python scripts/web_build.py <katalog z runami> <katalog wyjściowy>

W <katalog z runami> szukane są podfoldery o id z web/scenarios.json (np. demo-kutno). Układ wyniku:
index.html (lista), scenarios.json, player/ (klient z aplikacji), s/<id>/ (boot.en|pl.json, *.bin, data/).
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))


def dir_mb(path):
    return round(sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file()) / 1e6)


def build_scenario(run, dest, work):
    """boot.<lang>.json dla obu języków (nazwy klas i komunikaty powstają przy otwarciu), dane raz."""
    from viz_player import i18n
    from viz_player.player import Player

    dest = Path(dest)
    for lang in ("en", "pl"):
        i18n.set_lang(lang)
        player = Player()
        player.open(run, remember=False)
        if player.error:
            raise SystemExit(f"{run}: {player.error}")
        tmp = Path(work) / lang
        player.write_site(tmp)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(tmp / "boot.json", dest / f"boot.{lang}.json")
        if lang == "en":
            for f in tmp.glob("*.bin"):
                shutil.move(f, dest / f.name)
            shutil.copytree(tmp / "data", dest / "data", dirs_exist_ok=True)


def main(runs, out):
    runs, out = Path(runs), Path(out)
    scenarios = json.loads((ROOT / "web" / "scenarios.json").read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    (out / "player").mkdir(parents=True)
    shutil.copy(ROOT / "viz_player" / "shell.html", out / "player" / "index.html")
    shutil.copy(ROOT / "viz_player" / "engine.js", out / "player" / "engine.js")
    shutil.copytree(ROOT / "viz_player" / "vendor", out / "player" / "vendor")
    shutil.copy(ROOT / "web" / "index.html", out / "index.html")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    built = []
    with tempfile.TemporaryDirectory() as work:
        for s in scenarios:
            run = runs / s["id"]
            if not run.is_dir():
                print(f"pomijam {s['id']}: brak folderu {run}")
                continue
            build_scenario(run, out / "s" / s["id"], work)
            s["size_mb"] = dir_mb(out / "s" / s["id"])
            built.append(s)
            print(f"{s['id']}: {s['size_mb']} MB")
    if not built:
        raise SystemExit("żaden scenariusz nie został zbudowany")
    (out / "scenarios.json").write_text(json.dumps(built, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    sys.exit(main(*sys.argv[1:]))
