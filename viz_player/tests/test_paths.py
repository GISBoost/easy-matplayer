import json
from pathlib import Path

from viz_player import paths
from viz_player import player as pl


def test_repo_mode_keeps_output_dir():
    res, data, runs = paths.locate(False, {}, here=paths.__file__)
    assert (res / "viz_player" / "shell.html").is_file()
    assert data == res / "output" == runs


def test_frozen_mode_separates_resources_and_data(tmp_path):
    res, data, runs = paths.locate(True, {"LOCALAPPDATA": str(tmp_path / "local")}, meipass=str(tmp_path / "app"))
    assert res == tmp_path / "app"
    assert data == tmp_path / "local" / "easy-matplayer" and not str(data).startswith(str(res))
    assert runs == Path.home()


def test_env_overrides_data_in_both_modes(tmp_path):
    env = {paths.ENV_DATA: str(tmp_path / "d"), "LOCALAPPDATA": str(tmp_path / "local")}
    assert paths.locate(False, env, here=paths.__file__)[1] == tmp_path / "d"
    assert paths.locate(True, env, meipass=str(tmp_path))[1] == tmp_path / "d"


def test_saved_run_resolves_relative_to_resources(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    monkeypatch.setattr(pl, "STATE", state)
    state.write_text(json.dumps({"run": "output/x"}), encoding="utf-8")
    assert Path(pl.saved_run()) == pl.ROOT / "output" / "x"
    absolute = tmp_path / "abs"
    state.write_text(json.dumps({"run": str(absolute)}), encoding="utf-8")
    assert Path(pl.saved_run()) == absolute


def test_basemap_key_read_from_data_dir(tmp_path, monkeypatch):
    (tmp_path / "viz_basemap.local.toml").write_text('key = "abc"\n', encoding="utf-8")
    monkeypatch.setattr(pl, "DATA", tmp_path)
    assert pl.carto_basemap()["url"].endswith("?key=abc")
