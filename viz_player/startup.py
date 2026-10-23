"""Start aplikacji uruchamianej dwuklikiem (D27): log do pliku zamiast konsoli i okna z komunikatami błędów."""
import ctypes
import os
import struct
import sys
import threading
import time
import traceback
from pathlib import Path

from viz_player import APP_NAME, __version__
from viz_player.paths import DATA, FROZEN

LOG = DATA / f"{APP_NAME}.log"
LOG_MAX = 2_000_000
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
NO_DIALOG = "EASY_MATANIMATION_NO_DIALOG"  # testy: bez okien
SKIP_WV2_CHECK = "EASY_MATANIMATION_SKIP_WEBVIEW2_CHECK"  # furtka przy fałszywym alarmie sprawdzenia WebView2


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


def webview2_missing():
    """True, gdy WebView2 Runtime nie da się znaleźć. Pyta ten sam WebView2Loader.dll, którego używa pywebview: wpis w rejestrze albo katalog
    Runtime nie wystarczają (w Windows Sandbox są, a okno i tak się nie uruchamia). Bez Runtime pywebview nie zgłasza błędu, tylko zostawia puste
    okno i działa dalej. Nie da się zapytać (inny system, brak biblioteki): False, niech zadecyduje pywebview."""
    if os.name != "nt" or struct.calcsize("P") != 8 or os.environ.get(SKIP_WV2_CHECK):
        return False
    try:
        import webview

        loader = ctypes.WinDLL(str(Path(webview.__file__).parent / "lib" / "runtimes" / "win-x64" / "native" / "WebView2Loader.dll"))
        version = ctypes.c_wchar_p()
        return loader.GetAvailableCoreWebView2BrowserVersionString(None, ctypes.byref(version)) != 0 or not version.value
    except Exception:  # noqa: BLE001
        return False


def show_webview2_missing():
    show_error(
        "brak WebView2",
        "Aplikacja potrzebuje składnika Microsoft Edge WebView2 Runtime.\nPobierz go z:\n" + WEBVIEW2_URL
        + "\n\nPotem uruchom aplikację ponownie.",
    )


def crash(exc=None):
    """Nieobsłużony wyjątek: pełny ślad do dziennika, krótki komunikat w oknie. Brak WebView2 dostaje link do instalatora."""
    trace = traceback.format_exc() if exc is None else "".join(traceback.format_exception(exc))
    print(trace, flush=True)
    low = trace.lower()
    if "webview2" in low or "edgechromium" in low or "edge chromium" in low:
        show_webview2_missing()
        return
    last = trace.strip().splitlines()[-1] if trace.strip() else "nieznany błąd"
    show_error("błąd", f"{last}\n\nSzczegóły są w pliku:\n{LOG}")


def pick_run(initial):
    """Okno wyboru folderu runu przed otwarciem głównego okna (start bez argumentu i bez zapamiętanego runu). Anulowanie: None."""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askdirectory(
            parent=root, initialdir=str(initial), mustexist=True,
            title=f"{APP_NAME}: wskaż folder runu MATSim (z plikami output_events.xml.zst i output_network.xml.zst)",
        )
    finally:
        root.destroy()
    return path or None


class _State:
    def __init__(self):
        self.lock = threading.Lock()
        self.label, self.frac = "Start…", 0.0

    def set(self, label, frac):
        with self.lock:
            self.label, self.frac = label, frac

    def get(self):
        with self.lock:
            return self.label, self.frac


def with_progress(title, work, delay=0.6):
    """Wykonuje work(postęp) w wątku i zwraca jego wynik (wyjątek jest podnoszony). Okno z paskiem pokazuje się dopiero,
    gdy praca trwa dłużej niż delay, więc szybkie otwarcie (indeks z cache) nie miga oknem."""
    state, out = _State(), {}

    def target():
        try:
            out["value"] = work(state.set)
        except BaseException as exc:  # noqa: BLE001: przekazane wywołującemu
            out["error"] = exc

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(delay)
    if thread.is_alive():
        try:
            _progress_window(title, state, thread)
        except Exception:  # pasek to dodatek (brak Tk, brak ekranu): praca ma się skończyć mimo to
            traceback.print_exc()
    thread.join()
    if "error" in out:
        raise out["error"]
    return out["value"]


def _progress_window(title, state, thread):
    import tkinter
    from tkinter import ttk

    bg, fg, accent = "#121418", "#e6e9ef", "#4f9cf9"
    root = tkinter.Tk()
    root.title(APP_NAME)
    root.configure(bg=bg)
    root.resizable(False, False)
    width, height = 460, 130
    root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 3}")
    root.attributes("-topmost", True)
    tkinter.Label(root, text=title, bg=bg, fg=fg, font=("Segoe UI", 11, "bold"), anchor="w").pack(fill="x", padx=18, pady=(16, 2))
    step = tkinter.Label(root, text="", bg=bg, fg="#9aa3b2", font=("Segoe UI", 9), anchor="w")
    step.pack(fill="x", padx=18)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("A.Horizontal.TProgressbar", troughcolor="#1d222b", background=accent, bordercolor=bg, lightcolor=accent, darkcolor=accent)
    bar = ttk.Progressbar(root, style="A.Horizontal.TProgressbar", maximum=100, length=width - 36)
    bar.pack(padx=18, pady=(10, 0))
    state_mode = {"indeterminate": False}

    def tick():
        label, frac = state.get()
        if frac is None:
            if not state_mode["indeterminate"]:
                bar.configure(mode="indeterminate")
                bar.start(12)
                state_mode["indeterminate"] = True
            step.configure(text=label)
        else:
            if state_mode["indeterminate"]:
                bar.stop()
                bar.configure(mode="determinate")
                state_mode["indeterminate"] = False
            bar["value"] = 100 * frac
            step.configure(text=f"{label}   {100 * frac:.0f}%")
        if thread.is_alive():
            root.after(100, tick)
        else:
            root.destroy()

    # zamknięcie okna w trakcie pracy kończy aplikację; niedokończony indeks nie ma meta.json, więc następnym razem powstaje od nowa
    root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))
    tick()
    root.mainloop()
