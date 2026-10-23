"""Kopiuje teksty licencji bibliotek wchodzących do paczki do <dist>/THIRD_PARTY/ (BSD/MIT wymagają noty i tekstu przy redystrybucji).

Użycie (z venv budowy): python scripts/viz_third_party.py <dist>
Zakres: zależności z viz_player/requirements.txt wraz z tranzytywnymi (bez narzędzi budowy) oraz licencja Pythona.
"""
import importlib.metadata as md
import re
import shutil
import sys
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def closure(names):
    seen, todo = {}, list(names)
    while todo:
        name = re.sub(r"[-_.]+", "-", todo.pop()).lower()
        if name in seen:
            continue
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            continue  # zależność warunkowa (inny system, wersja Pythona), nie jest zainstalowana
        seen[name] = dist
        for line in dist.requires or []:
            req = Requirement(line)
            if req.marker is None or req.marker.evaluate({"extra": ""}):
                todo.append(req.name)
    return seen


def main():
    out = Path(sys.argv[1]) / "THIRD_PARTY"
    shutil.rmtree(out, ignore_errors=True)
    names = [re.split(r"[=<>]", ln)[0] for ln in (ROOT / "viz_player" / "requirements.txt").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    rows = []
    for name, dist in sorted(closure(names).items()):
        meta = dist.metadata
        lic = (meta.get("License-Expression") or meta.get("License") or "zob. pliki licencji").splitlines()[0][:80]
        files = [f for f in dist.files or [] if re.search(r"(^|/)(licen[sc]e|copying|notice|authors)[^/]*$", f.as_posix(), re.I)]
        for f in files:
            dest = out / f"{name}-{dist.version}" / f.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dist.locate_file(f), dest)
        rows.append(f"| {meta['Name']} | {dist.version} | {lic} | {len(files)} |")
    py = next((p for p in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE") if p.is_file()), None)
    if py:
        (out / "python").mkdir(parents=True, exist_ok=True)
        shutil.copy2(py, out / "python" / "LICENSE.txt")
    (out / "README.md").write_text(
        "# Biblioteki w paczce\n\nTeksty licencji bibliotek spakowanych razem z easy-matanimation (Python, Tcl/Tk i WebView2Loader.dll "
        "w pywebview też). Skrypty JS i modele w `_internal/viz_player/vendor/` mają licencje obok plików. Program: GPL-3.0-or-later (`LICENSE`).\n\n"
        "| pakiet | wersja | licencja | plików licencji |\n|---|---|---|---|\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"THIRD_PARTY: {len(rows)} pakietów, python={'tak' if py else 'brak'}")


if __name__ == "__main__":
    main()
