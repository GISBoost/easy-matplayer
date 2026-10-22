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
