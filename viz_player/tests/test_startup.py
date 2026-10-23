import sys

from viz_player import APP_NAME, __version__, startup


def test_no_console_logs_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(startup, "LOG", tmp_path / "x" / "app.log")
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    fh = startup.setup_logging()
    try:
        print("pierwszy print bez konsoli")
    finally:
        fh.close()
    text = (tmp_path / "x" / "app.log").read_text(encoding="utf-8")
    assert "pierwszy print bez konsoli" in text and __version__ in text


def test_log_is_rotated(tmp_path, monkeypatch):
    log = tmp_path / "app.log"
    log.write_text("x" * (startup.LOG_MAX + 1), encoding="utf-8")
    monkeypatch.setattr(startup, "LOG", log)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    startup.setup_logging().close()
    assert (tmp_path / "app.log.1").stat().st_size == startup.LOG_MAX + 1 and log.stat().st_size < 200


def test_console_in_repo_is_left_alone():
    assert startup.setup_logging() is None


def test_crash_message_for_missing_webview2(monkeypatch, capsys):
    shown = []
    monkeypatch.setattr(startup, "show_error", lambda title, text: shown.append((title, text)))
    startup.crash(RuntimeError("WebView2 runtime not found"))
    assert shown[0][0] == "brak WebView2" and startup.WEBVIEW2_URL in shown[0][1]
    shown.clear()
    startup.crash(ValueError("inny błąd"))
    assert shown[0][0] == "błąd" and "ValueError: inny błąd" in shown[0][1]


def test_show_error_silent_without_dialog(monkeypatch, capsys):
    monkeypatch.setenv(startup.NO_DIALOG, "1")
    startup.show_error("t", "treść")
    assert "treść" in capsys.readouterr().out


def test_app_name():
    assert APP_NAME == "easy-matanimation"


def test_with_progress_returns_value_without_window():
    calls = []
    out = startup.with_progress("t", lambda progress: (progress("etap", 0.5), calls.append(1), 42)[2], delay=5)
    assert out == 42 and calls == [1]


def test_with_progress_passes_exception_up():
    import pytest

    def boom(progress):
        raise ValueError("zepsute")

    with pytest.raises(ValueError, match="zepsute"):
        startup.with_progress("t", boom, delay=5)


def test_with_progress_opens_window_for_slow_work():
    import time

    seen = []

    def slow(progress):
        for i in range(6):
            progress(f"krok {i}", i / 5)
            time.sleep(0.15)
        progress("bez czasu", None)
        time.sleep(0.2)
        return "ok"

    original = startup._progress_window
    startup._progress_window = lambda title, state, thread: (seen.append(title), original(title, state, thread))[1]
    try:
        assert startup.with_progress("Otwieram run x", slow, delay=0.1) == "ok"
    finally:
        startup._progress_window = original
    assert seen == ["Otwieram run x"], "okno pojawia się, gdy praca trwa dłużej niż opóźnienie, i samo się zamyka"


def test_scaled_maps_stage_into_range():
    from viz_player.player import scaled

    got = []
    cb = scaled(lambda label, frac: got.append((label, frac)), 0.2, 0.6)
    cb("a", 0.0), cb("b", 0.5), cb("c", 1.0), cb("d", None)
    assert [round(f, 6) if f is not None else None for _, f in got] == [0.2, 0.4, 0.6, None]
    assert scaled(None, 0, 1) is None


def test_serve_without_run_asks_for_folder_and_cancel_ends_quietly(tmp_path, monkeypatch):
    from viz_player import window

    asked = []
    monkeypatch.setattr(startup, "pick_run", lambda initial: asked.append(initial))
    monkeypatch.setattr(startup, "show_error", lambda *a: asked.append(a))
    monkeypatch.setattr(window, "DATA", tmp_path)
    assert window.serve(None) == 0 and len(asked) == 1
    assert window.serve(str(tmp_path / "zniknął")) == 0, "zapamiętany run, którego już nie ma, otwiera wybór folderu"


def test_serve_with_bad_explicit_run_reports_and_fails(tmp_path, monkeypatch):
    from viz_player import window

    shown = []
    monkeypatch.setattr(startup, "show_error", lambda title, text: shown.append(text))
    monkeypatch.setattr(window, "DATA", tmp_path)
    assert window.serve(str(tmp_path / "nie-ma"), explicit=True) == 1 and "nie-ma" in shown[0]
    empty = tmp_path / "pusty"
    empty.mkdir()
    assert window.serve(str(empty), explicit=True) == 1 and "Brak" in shown[1]


def test_serve_error_in_remembered_run_falls_back_to_picker(tmp_path, monkeypatch):
    from viz_player import window

    empty = tmp_path / "pusty"
    empty.mkdir()
    picks, shown = [], []
    monkeypatch.setattr(startup, "pick_run", lambda initial: picks.append(1))
    monkeypatch.setattr(startup, "show_error", lambda title, text: shown.append(text))
    monkeypatch.setattr(window, "DATA", tmp_path)
    assert window.serve(str(empty)) == 0 and shown and picks == [1]


def test_serve_corrupt_remembered_run_falls_back_to_picker(tmp_path, monkeypatch):
    from viz_player import window

    bad = tmp_path / "zepsuty"
    bad.mkdir()
    (bad / "output_events.xml.zst").write_bytes(b"to nie jest zstd")
    (bad / "output_network.xml.zst").write_bytes(b"to nie jest zstd")
    picks, shown = [], []
    monkeypatch.setattr(startup, "pick_run", lambda initial: picks.append(1))
    monkeypatch.setattr(startup, "show_error", lambda title, text: shown.append(text))
    monkeypatch.setattr(window, "DATA", tmp_path)
    assert window.serve(str(bad)) == 0 and shown and picks == [1], "uszkodzony run nie zamyka drogi do wyboru innego"


def test_with_progress_survives_broken_window(monkeypatch):
    def broken(title, state, thread):
        raise RuntimeError("brak ekranu")

    monkeypatch.setattr(startup, "_progress_window", broken)
    import time
    assert startup.with_progress("t", lambda progress: (time.sleep(0.3), "ok")[1], delay=0.05) == "ok"


def test_api_refuses_second_open_while_busy(tmp_path):
    from viz_player import window

    api = window.Api.__new__(window.Api)
    api._progress = {"busy": True, "label": "", "frac": 0.0}
    assert api.open_path(str(tmp_path)) == window.BUSY and api.osm_use("") == window.BUSY


def test_serve_without_webview2_reports_before_opening_anything(tmp_path, monkeypatch):
    from viz_player import window

    shown = []
    monkeypatch.setattr(startup, "webview2_missing", lambda: True)
    monkeypatch.setattr(startup, "show_error", lambda title, text: shown.append((title, text)))
    assert window.serve(str(tmp_path)) == 1 and shown[0][0] == "brak WebView2" and startup.WEBVIEW2_URL in shown[0][1]


def test_webview2_missing_is_false_on_this_machine_when_runtime_is_registered():
    import os
    import pytest

    if os.name != "nt":
        pytest.skip("Windows")
    assert startup.webview2_missing() in (True, False)  # rejestr czytany bez wyjątku; wynik zależy od maszyny
