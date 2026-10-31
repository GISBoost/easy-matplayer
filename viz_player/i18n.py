"""Język interfejsu: angielski (domyślnie) albo polski.

Klucz tłumaczenia to polski tekst z kodu, więc przy wywołaniu widać, co jest napisane. Tekst bez wpisu w EN zostaje po polsku.
Wybór zapisuje się w DATA/viz_player_lang.json. Strona okna dostaje słownik w boot.json (tabela), więc JS nie ma osobnej kopii.
Testy i tryby --check / --smoke działają po polsku, bo ich asercje czytają napisy z DOM i komunikaty z Pythona.
"""
import json

from viz_player.paths import DATA

FILE = DATA / "viz_player_lang.json"
LANGS = ("en", "pl")
DEFAULT = "en"
_lang = DEFAULT


def lang():
    return _lang


def set_lang(code):
    global _lang
    if code not in LANGS:
        raise ValueError(f"nieznany język {code!r}")
    _lang = code


def load():
    """Przy starcie: zapamiętany wybór albo DEFAULT. Błędny plik nie blokuje startu."""
    try:
        code = json.loads(FILE.read_text(encoding="utf-8")).get("lang")
    except (OSError, ValueError, AttributeError):
        code = None
    set_lang(code if code in LANGS else DEFAULT)


def save(code):
    set_lang(code)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps({"lang": code}) + "\n", encoding="utf-8")


def t(text):
    """Tłumaczenie szablonu (może mieć {nazwy} do .format). Po polsku zwraca tekst bez zmian."""
    return EN.get(text, text) if _lang == "en" else text


def table():
    """Słownik dla strony okna (boot.json): po angielsku pełny, po polsku pusty."""
    return EN if _lang == "en" else {}


EN = {
    # --- player.py: stan runu, panel, budynki, etapy eksportu
    "Brak katalogu runu {run}.": "No run folder {run}.",
    "eventów": "events",
    "sieci": "network",
    " i ": " and ",
    "Brak {what} w {run}.": "Missing {what} in {run}.",
    "Indeks się nie zbudował: {exc}": "The index could not be built: {exc}",
    "Łamane drogi (OSM)": "Polyline roads (OSM)",
    "Brak układu współrzędnych w output_config.xml: założono {crs}. Jeśli mapa jest w złym miejscu, dodaj ten plik do runu.":
        "No coordinate system in output_config.xml: {crs} assumed. If the map is in the wrong place, add this file to the run.",
    "łamane: {exc}; cięciwy": "polylines: {exc}; chords",
    "łamane: {n} z {total}{coverage}": "polylines: {n} of {total}{coverage}",
    "brak": "none",
    "1 auto": "1 car",
    "{n} auta": "{n} cars",
    "{n} aut": "{n} cars",
    "teraz {cars}": "now {cars}",
    ", średnia na odcinku {speed}": ", average on the link {speed}",
    "nie jedzie": "not driving",
    "Brak runu.": "No run.",
    "0 aut": "0 cars",
    "budynki: brak pliku OSM (wskaż plik .osm.pbf w panelu)": "buildings: no OSM file (pick a .osm.pbf file in the panel)",
    "budynki: w pliku OSM nie ma budynków w obszarze sieci (czy plik pokrywa tę sieć?)":
        "buildings: the OSM file has no buildings in the network area (does the file cover this network?)",
    "budynki {n}: wysokość z tagu {tag}, z pięter {levels}, założenie wg klasy {default} (piętra i klasa to założenia)":
        "buildings {n}: height from tag {tag}, from floors {levels}, assumed by class {default} (floors and class are assumptions)",
    "Eksport danych dla okna": "Exporting window data",
    "Budynki 3D (OSM)": "3D buildings (OSM)",
    "Zapisuję stronę okna": "Writing the window page",
    "Gotowe": "Done",
    # --- player.py: nazwy klas pojazdów i etykiety osi (klucze z pipeline/viz_classes.py)
    "mieszkaniec": "resident",
    "przyjeżdżający": "commuter",
    "wyjeżdżający": "outbound",
    "tło lekkie": "light background",
    "ciężkie": "heavy",
    "inne": "other",
    "jazda": "trip",
    "dom": "home",
    "praca": "work",
    "tło": "background",
    "próbka {s}": "sample {s}",
    # --- curves.py: łamane drogi z pliku OSM
    "; w pliku OSM {found} z {wanted} dróg sieci": "; OSM file has {found} of {wanted} network roads",
    "łamane: {n_bent} z {n}, cache{coverage}": "polylines: {n_bent} of {n}, cache{coverage}",
    "łamane: sieć nieczytelna ({exc}); cięciwy": "polylines: network unreadable ({exc}); chords",
    "łamane: inna kolejność linków; cięciwy": "polylines: different link order; chords",
    "łamane: {why}; cięciwy": "polylines: {why}; chords",
    "brak origid ani osm:way:id": "no origid or osm:way:id",
    "brak PBF": "no PBF file",
    "łamane: czytam OSM…": "polylines: reading OSM…",
    "łamane: plik OSM nie pokrywa tej sieci (0 z {n} dróg); cięciwy":
        "polylines: the OSM file does not cover this network (0 of {n} roads); chords",
    "łamane: {n_bent} z {n}, skan {s} s{coverage}": "polylines: {n_bent} of {n}, scan {s} s{coverage}",
    # --- ogc.py: usługi WMS / WMTS / XYZ
    "Adres usługi musi zaczynać się od http:// albo https://": "The service address must start with http:// or https://",
    "Usługa nie odpowiada: {exc}": "The service does not respond: {exc}",
    "Wpisz adres usługi.": "Enter the service address.",
    "Odpowiedź usługi nie jest XML-em ({exc}).": "The service response is not XML ({exc}).",
    "Usługa zwróciła błąd: {text}": "The service returned an error: {text}",
    "Nie rozpoznano usługi.": "The service was not recognised.",
    "Usługa nie ma warstwy {layer_name}.": "The service has no layer {layer_name}.",
    "Warstwa nie podaje żadnego układu współrzędnych.": "The layer gives no coordinate system.",
    "Warstwa WMTS nie ma zestawu kafelków w EPSG:3857 (256 px); ma: {have}.":
        "The WMTS layer has no tile set in EPSG:3857 (256 px); it has: {have}.",
    "Zestaw kafelków WMTS nie ma skal zgodnych z siatką Web Mercator.":
        "The WMTS tile set has no scales matching the Web Mercator grid.",
    "Brak poziomu {z} w zestawie kafelków.": "There is no level {z} in the tile set.",
    "Usługa zwróciła nie obraz: {text}": "The service returned something other than an image: {text}",
    "Kafelek poza zakresem układu usługi.": "The tile is outside the service's coordinate system.",
    "(przeliczany ze stopni)": "(converted from degrees)",
    "(przeliczany)": "(converted)",
    # --- rasters.py: własne obrazy (pliki świata)
    "Plik świata {name} ma zły format (oczekiwano sześciu liczb).": "World file {name} has the wrong format (six numbers expected).",
    "plik świata": "world file",
    "Nieznany układ EPSG:{crs}.": "Unknown coordinate system EPSG:{crs}.",
    "Zakres musi mieć W < E oraz S < N.": "The extent must have W < E and S < N.",
    "Nie da się wczytać obrazu {name}: {exc}": "The image {name} cannot be loaded: {exc}",
    # --- window.py: API dla strony
    "Poprzednia operacja jeszcze trwa.": "The previous operation is still running.",
    "Ten obraz już nie czeka na układ.": "This image is no longer waiting for a coordinate system.",
    "Podaj kod układu, np. 2180 albo EPSG:4326.": "Enter a coordinate system code, e.g. 2180 or EPSG:4326.",
    "Zakres musi składać się z czterech liczb.": "The extent must consist of four numbers.",
    "Nie ma takiego obrazu.": "There is no such image.",
    "ręczne": "manual",
    "zakres EPSG:{code}": "extent EPSG:{code}",
    "Nie udało się otworzyć: {exc}": "Could not open: {exc}",
    "Nie udało się przygotować strony: {exc}": "Could not prepare the page: {exc}",
    "Nie ma pliku {name}.": "There is no file {name}.",
    "To nie jest plik .osm.pbf.": "This is not an .osm.pbf file.",
    "Nie da się odczytać pliku OSM: {exc}": "The OSM file cannot be read: {exc}",
    "Obrazy (*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.webp)": "Images (*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.webp)",
    "Wszystkie pliki (*.*)": "All files (*.*)",
    "Plik OSM (*.osm.pbf;*.pbf)": "OSM file (*.osm.pbf;*.pbf)",
    "Nie da się otworzyć runu": "The run cannot be opened",
    "Otwieram run {name}": "Opening run {name}",
    # --- startup.py: okna systemowe
    "błąd": "error",
    "brak WebView2": "no WebView2",
    "Aplikacja potrzebuje składnika Microsoft Edge WebView2 Runtime.\nPobierz go z:\n":
        "The app needs the Microsoft Edge WebView2 Runtime.\nDownload it from:\n",
    "\n\nPotem uruchom aplikację ponownie.": "\n\nThen start the app again.",
    "Szczegóły są w pliku:\n{log}": "Details are in the file:\n{log}",
    "{app}: wskaż folder runu MATSim (z plikami output_events.xml.zst i output_network.xml.zst)":
        "{app}: select a MATSim run folder (with output_events.xml.zst and output_network.xml.zst)",
    # --- strona okna (shell.html, engine.js): tekst statyczny i z JS
    "otwórz run…": "open run…",
    "plik OSM…": "OSM file…",
    "zapomnij plik": "forget file",
    "id pojazdu": "vehicle id",
    "kolor dróg OSM": "OSM road colors",
    "modele 3D pojazdów": "3D vehicle models",
    "kolor auta: prędkość": "car color: speed",
    "kolor auta: ": "car color: ",
    "prędkość": "speed",
    "klasa": "class",
    "Podkłady: WMS, WMTS, XYZ, obrazy": "Basemaps: WMS, WMTS, XYZ, images",
    "dodaj WMS / WMTS / XYZ…": "add WMS / WMTS / XYZ…",
    "dodaj obraz…": "add image…",
    "Kliknij auto albo drogę.": "Click a car or a road.",
    "← scenariusze": "← scenarios",
    "Podkłady": "Basemaps",
    "Ortofotomapa (GUGiK)": "Orthophoto (GUGiK)",
    "krycie": "opacity",
    "błyski aktywności": "activity flashes",
    "start: pierścień rozchodzi się": "start: the ring expands",
    "koniec: jaśniejszy pierścień zbiega się": "end: a lighter ring contracts",
    "Kolor dróg": "Road color",
    "typ drogi": "road type",
    "natężenie": "flow",
    "okno:": "window:",
    "prędkość / swobodna: 30% … 90%": "speed / free speed: 30% … 90%",
    "natężenie / przepustowość: 0 … 100%": "flow / capacity: 0 … 100%",
    "szary: brak ruchu": "grey: no traffic",
    "Brak flowCapacityFactor w configu runu: natężenie niedostępne.": "No flowCapacityFactor in the run config: flow is unavailable.",
    "ostatnie {w} min: brak ruchu": "last {w} min: no traffic",
    "{v} (swobodna {f})": "{v} (free {f})",
    "{q} poj/h": "{q} veh/h",
    " ({p}% przepustowości, w skali próbki)": " ({p}% of capacity, sample scale)",
    "ostatnie {w} min: {x}": "last {w} min: {x}",
    "GISBoost · analizy mapowe": "GISBoost · map analyses",
    "postoje ściśnięte": "stops compressed",
    "Modele aut: Quaternius (CC0).": "Car models: Quaternius (CC0).",
    "Spacja: start. Strzałki: ±1 min. F: śledź. Esc: wyczyść. Prawy przycisk myszy: obrót i pochylenie mapy.":
        "Space: start. Arrows: ±1 min. F: follow. Esc: clear. Right mouse button: rotate and tilt the map.",
    "pauza": "pause",
    "mnożnik −1": "speed −1",
    "mnożnik +1": "speed +1",
    "Podkład wyłączony.": "Basemap off.",
    "ukryj": "hide",
    "Układ współrzędnych (kod EPSG)": "Coordinate system (EPSG code)",
    "zastosuj": "apply",
    "zamknij": "close",
    "Obraz bez georeferencji: przeciągnij środek, żeby przesunąć, róg, żeby skalować i obracać. Suwak przezroczystości w panelu pomaga trafić w drogi.":
        "Image without georeference: drag the centre to move it, a corner to scale and rotate it. The opacity slider in the panel helps you hit the roads.",
    "wpisz zakres…": "enter extent…",
    "gotowe": "done",
    "Dodaj usługę WMS / WMTS": "Add a WMS / WMTS service",
    "Nazwa": "Name",
    "Adres usługi": "Service address",
    "https://…/wms albo …/wmts": "https://…/wms or …/wmts",
    "połącz": "connect",
    "dodaj warstwę": "add layer",
    "Łączę…": "Connecting…",
    ", warstw: {n}": ", layers: {n}",
    "Wpisz zakres obrazu": "Enter the image extent",
    "Współrzędne krawędzi obrazu w wybranym układzie (dla stopni: długość jako W i E, szerokość jako S i N).":
        "Coordinates of the image edges in the chosen system (for degrees: longitude as W and E, latitude as S and N).",
    "Plik świata bez układu": "World file without a coordinate system",
    "Obraz ma georeferencję ({source}), ale nie wiadomo, w jakim układzie jest zapisana. Podpowiedź z liczb: EPSG:{guess}.":
        "The image has a georeference ({source}), but the coordinate system it is stored in is unknown. Hint from the numbers: EPSG:{guess}.",
    "Run się otwiera…": "Opening the run…",
    "Czytam plik OSM…": "Reading the OSM file…",
    "Otwieram run bez pliku OSM…": "Opening the run without an OSM file…",
    "Brak takiego id.": "No such id.",
    "usuń": "remove",
    "ustaw": "set",
    "Pokaż cały obszar sieci": "Show the whole network area",
    "Ta aplikacja rysuje mapę w WebGL2, a to okno go nie ma": "This app draws the map with WebGL2, and this window does not have it",
    ". Zaktualizuj sterownik karty graficznej albo uruchom program na komputerze z kartą obsługującą WebGL2.":
        ". Update the graphics driver or run the program on a computer with a WebGL2 graphics card.",
    "OSM: {file}": "OSM: {file}",
    "OSM: dane zapisane przy runie": "OSM: data saved with the run",
    "OSM: brak (proste odcinki, bez budynków)": "OSM: none (straight segments, no buildings)",
    "autostrada": "motorway",
    "droga główna": "primary road",
    "droga drugorzędna": "secondary road",
    "droga trzeciorzędna": "tertiary road",
    "ulica osiedlowa": "residential street",
    "droga bez klasy": "unclassified road",
    "strefa zamieszkania": "living street",
    "zawrotka graniczna": "boundary turnaround",
    "inna": "other",
}
