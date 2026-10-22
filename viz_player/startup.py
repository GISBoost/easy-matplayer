"""Start aplikacji uruchamianej dwuklikiem (D27): log do pliku zamiast konsoli i okna z komunikatami błędów."""
import ctypes
import os
import sys
import time
import traceback

from viz_player import APP_NAME, __version__
from viz_player.paths import DATA, FROZEN

LOG = DATA / f"{APP_NAME}.log"
LOG_MAX = 2_000_000
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
NO_DIALOG = "EASY_MATANIMATION_NO_DIALOG"  # testy: bez okien


def setup_logging():
    """Bez konsoli (exe okienkowe, pythonw) stdout i stderr to None i pierwszy print wywaliłby program.
    Wtedy, a także w paczce, wszystko idzie do pliku z dziennikiem. W repo z konsolą nic się nie zmienia."""
    if not FROZEN and sys.stdout is not None and sys.stderr is not None:
        return None
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > LOG_MAX:
        os.replace(LOG, LOG.with_name(LOG.name + ".1"))
    fh = open(LOG, "a", encoding="utf-8", buffering=1)
    fh.write(f"\n--- {time.strftime('%Y-%m-%dT%H:%M:%S')} {APP_NAME} {__version__} ---\n")
    sys.stdout = sys.stderr = fh
    return fh


def show_error(title, text):
    """Komunikat w oknie systemowym; zawsze też do dziennika. Nic nie robi poza Windows i przy NO_DIALOG."""
    print(f"BŁĄD {title}: {text}", flush=True)
    if os.name != "nt" or os.environ.get(NO_DIALOG):
        return
    ctypes.windll.user32.MessageBoxW(None, text, f"{APP_NAME}: {title}", 0x10 | 0x1000)


def crash(exc=None):
    """Nieobsłużony wyjątek: pełny ślad do dziennika, krótki komunikat w oknie. Brak WebView2 dostaje link do instalatora."""
    trace = traceback.format_exc() if exc is None else "".join(traceback.format_exception(exc))
    print(trace, flush=True)
    low = trace.lower()
    if "webview2" in low or "edgechromium" in low or "edge chromium" in low:
        show_error(
            "brak WebView2",
            "Aplikacja potrzebuje składnika Microsoft Edge WebView2 Runtime.\nPobierz go z:\n" + WEBVIEW2_URL
            + "\n\nPotem uruchom aplikację ponownie.",
        )
        return
    last = trace.strip().splitlines()[-1] if trace.strip() else "nieznany błąd"
    show_error("błąd", f"{last}\n\nSzczegóły są w pliku:\n{LOG}")
