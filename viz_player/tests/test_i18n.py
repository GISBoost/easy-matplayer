import re

from viz_player import i18n, player


def fields(text):
    return set(re.findall(r"\{(\w+)\}", text))


def test_every_english_entry_keeps_the_placeholders_of_its_key():
    # brak zgodności nawiasów rozwaliłby .format() dopiero w czasie działania, więc sprawdzamy od razu
    for key, value in i18n.EN.items():
        assert fields(key) == fields(value), key


def test_translate_follows_the_language_and_keeps_unknown_text():
    i18n.set_lang("en")
    assert i18n.t("Eksport danych dla okna") == "Exporting window data"
    assert i18n.t("tekst bez wpisu") == "tekst bez wpisu"
    i18n.set_lang("pl")
    assert i18n.t("Eksport danych dla okna") == "Eksport danych dla okna"


def test_table_for_the_page_is_empty_in_polish():
    i18n.set_lang("en")
    assert i18n.table() is i18n.EN
    i18n.set_lang("pl")
    assert i18n.table() == {}


def test_counted_nouns_in_english(monkeypatch):
    i18n.set_lang("en")
    assert player.auta(1) == "1 car"
    assert player.auta(3) == "3 cars"
    assert player.auta(12) == "12 cars"
    assert player.auta(22) == "22 cars"


def test_saved_choice_is_read_back_and_bad_file_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "FILE", tmp_path / "lang.json")
    i18n.save("pl")
    i18n.set_lang(i18n.DEFAULT)
    i18n.load()
    assert i18n.lang() == "pl"
    (tmp_path / "lang.json").write_text("nie json", encoding="utf-8")
    i18n.load()
    assert i18n.lang() == i18n.DEFAULT
    i18n.set_lang(i18n.DEFAULT)


def test_english_run_shows_no_polish_text(tmp_path):
    from viz_player import player as pl

    from . import fixture as fx

    rows = [
        fx.act("actend", "r2", 23000, "l0", 0, "home"),
        *fx.leg("r2", 23000, 23100),
        fx.act("actstart", "r2", 23100, "l0", 100, "work"),
        *fx.leg("t2", 21600, 21620),
        *fx.leg("h2", 23040, 23060),
        *fx.leg("r2b", 30000, 30010),
        *fx.trip("c1", 1000, acts=False),
        *fx.trip("o1", 2000, acts=False),
        *fx.trip("t9", 3000, acts=False),
    ]
    run = fx.write_run(tmp_path / "mini", rows)
    i18n.set_lang("en")
    p = pl.Player()
    p.open(run, remember=False)
    boot = p.boot()
    texts = [boot["curveNote"], boot["crsNote"], boot["buildingsNote"], boot["sample"]]
    texts += [line for sel in ({"id": "r2"}, {"id": "t2"}, {"link": 0}) for line in p.frame(23050, selected=sel)["panel"]["lines"]]
    texts += [c["name"] for c in boot["classes"]]
    polish = re.compile("[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
    assert not [s for s in texts if polish.search(str(s))], texts
