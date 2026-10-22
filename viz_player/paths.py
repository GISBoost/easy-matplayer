"""Ścieżki aplikacji (D27): zasoby tylko do odczytu osobno od danych użytkownika.

W repo (uruchomienie z kodu): RES = katalog repo, DATA = RES/output, jak dotąd.
W paczce PyInstaller (sys.frozen): RES = katalog rozpakowanej paczki, DATA = katalog easy-matanimation w %LOCALAPPDATA%.
EASY_MATANIMATION_DATA nadpisuje DATA w obu trybach (testy, przenośne kopie).
"""
import os
import sys
from pathlib import Path

APP = "easy-matanimation"
ENV_DATA = "EASY_MATANIMATION_DATA"


def locate(frozen, env, meipass=None, here=None):
    """(RES, DATA, RUNS): zasoby, zapisy, katalog, od którego zaczyna się wybór runu."""
    if frozen:
        res = Path(meipass)
        local = env.get("LOCALAPPDATA")
        data = (Path(local) if local else Path.home() / "AppData" / "Local") / APP
        runs = Path.home()
    else:
        res = Path(here).resolve().parents[1]
        data = res / "output"
        runs = data
    if env.get(ENV_DATA):
        data = Path(env[ENV_DATA])
    return res, data, runs


FROZEN = bool(getattr(sys, "frozen", False))
RES, DATA, RUNS = locate(FROZEN, os.environ, getattr(sys, "_MEIPASS", None), __file__)
