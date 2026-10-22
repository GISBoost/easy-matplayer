"""Klasyfikator klas pojazdów wizualizera (D24).

Klasa osoby = pierwszy obecny atrybut z CLASS_ATTRIBUTES w output_plans.xml.zst
(w Kutnie `kind`, w innych runach np. `subpopulation`). Bez planów albo dla osoby
spoza planów zostaje konwencja id (pierwsza litera r c o t h), potem klasa "?".
Nazwy znanych kluczy są w KNOWN; nieznany klucz pokazuje się pod własną nazwą,
więc nowy run (inne miasto, nowe tryby) nie wymaga zmiany kodu.
Tu ma być miejsce na tryb i atrybuty osób etapu 3; na razie tylko klasa.
"""
import io
import re

import zstandard

PLANS_NAME = "output_plans.xml.zst"
CLASS_ATTRIBUTES = ("kind", "subpopulation")
OTHER = "?"
OTHER_NAME = "inne"
# klucz: (nazwa w oknie, czy rysować większą kropką); kolejność = kolejność chipów
KNOWN = {
    "resident": ("mieszkaniec", False),
    "commuter": ("przyjeżdżający", False),
    "outbound": ("wyjeżdżający", False),
    "tlo": ("tło lekkie", False),
    "ciezkie": ("ciężkie", True),
}
LETTER_KEY = {"r": "resident", "c": "commuter", "o": "outbound", "t": "tlo", "h": "ciezkie"}
_ATTR = re.compile(r'<attribute name="([^"]+)"[^>]*>([^<]*)</attribute>')
_ID = re.compile(r'<person id="([^"]+)"')


def read_person_classes(run_dir):
    """{person: klucz klasy} z atrybutów osób w planach. Brak pliku albo atrybutów: None."""
    path = run_dir / PLANS_NAME
    if not path.exists():
        return None
    out = {}
    stream = zstandard.ZstdDecompressor().stream_reader(path.open("rb"))
    person, attrs = None, {}
    for line in io.TextIOWrapper(stream, encoding="utf-8", newline=""):
        if "<person " in line:
            m = _ID.search(line)
            person, attrs = (m.group(1) if m else None), {}
        elif person is None:
            continue
        elif "<plan " in line:
            for name in CLASS_ATTRIBUTES:
                if attrs.get(name):
                    out[person] = attrs[name]
                    break
            person = None
        elif "<attribute " in line:
            m = _ATTR.search(line)
            if m and m.group(1) in CLASS_ATTRIBUTES:
                attrs[m.group(1)] = m.group(2).strip()
    return out or None


def class_key(person, vehicle, by_person):
    if by_person is not None and person in by_person:
        return by_person[person]
    for ident in (person, vehicle):
        key = LETTER_KEY.get(ident[:1]) if ident else None
        if key:
            return key
    return OTHER


def class_table(keys):
    """Posortowana lista klas [{key, name, heavy}]: najpierw KNOWN w swojej kolejności, potem reszta, "?" na końcu."""
    order = list(KNOWN)
    ranked = sorted(set(keys), key=lambda k: (k == OTHER, order.index(k) if k in KNOWN else len(order), k))
    return [
        {"key": k, "name": OTHER_NAME if k == OTHER else KNOWN.get(k, (k, False))[0], "heavy": KNOWN.get(k, ("", False))[1]}
        for k in ranked
    ]
