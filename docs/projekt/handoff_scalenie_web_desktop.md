# Handoff: scalenie wersji web i desktop, własne WMS/WMTS w web, ekran ładowania

Data: 2026-10-31. Autor: poprzednia sesja (Claude). Odbiorca: agent, który będzie to kodował.
Stan repo w chwili pisania: `main` = `origin/main` = `f295540` (wypchnięte). Ten plik jest lokalnym commitem, bez pusha.

## 1. Co zostało ustalone z właścicielem

- Wersja web (GitHub Pages, `https://gisboost.github.io/easy-matplayer/`) i aplikacja desktop (pywebview/WebView2) mają jeden klient: `viz_player/shell.html` + `viz_player/engine.js`. Tryb web włącza `?run=<id>`. Chcemy **dalej scalić development**, żeby nowa funkcja trafiała do obu wersji bez kopiowania.
- Właściciel chce w web **własne usługi WMS/WMTS** (jak „dodaj warstwę” w QGIS). Jego stanowisko: serwer, który nie wysyła `Access-Control-Allow-Origin`, to problem serwera, nie nasz. Dołożenie biblioteki do przeliczania układów (proj4js) uważa za małą rzecz. **To zastępuje wcześniejszą decyzję z 2026-10-26 „własnych WMS w web nie ma”**; wpis w `wizualizer_postep.md` trzeba zaktualizować.
- Właściciel chce **ekranu ładowania z paskiem postępu** po kliknięciu kafelka na stronie gisboost (hub `mapy-analizy`): odtwarzacz z animacją ładuje się dziś kilka sekund, bez żadnej informacji. Ma być, jeśli technicznie się da i koszt jest niski.
- Poprzednio zrobione i wypchnięte: ortofoto GUGiK przez kafelkowy WMTS (`298d8c8`), dokumentacja (`f295540`). **Strona na Pages nadal ma stary kod** (WMS), bo workflow `web_pages.yml` nie był uruchomiony po tej zmianie; deploy robi właściciel.

## 2. Co wiemy o kodzie (sprawdzone w tej sesji)

**Podział web / desktop dziś**
- `shell.html` ma kilka rozgałęzień `if (WEB)` (np. linie ~536, 541, 976, 1009, 1413, 1534, 1985, 1992) i siedem odwołań do `window.pywebview`.
- Desktop: most Pythona (`viz_player/window.py`, klasa `Api`): otwieranie runu, plik OSM, usługi OGC (`ogc.py`), rastry (`rasters.py`), postęp (`Api.progress()`).
- Web: statyczne pliki zbudowane przez `scripts/web_build.py` (z runów w `web/scenarios.json`), `boot.<lang>.json`, dane w `../s/<id>/`. CSS: `body.web` ukrywa `#openrun`, `#osm`, `#svc` (panel usług) i pokazuje `#weblinks`, `#webbase` (dwa podkłady: OSM i ortofoto GUGiK z suwakiem krycia, tablica `WEB_BASE`).
- Python **nie liczy klatek**; klient liczy je z porcji binarnych. Indeks i eksport powstają w Pythonie/CI i na stronie lądują gotowe. Tego nie przenosić do JS.

**Własne usługi OGC (desktop)**
- `ogc.py`: `GetCapabilities` (WMS i WMTS), wybór warstwy, URL kafelka, układy: EPSG:3857 wprost, EPSG:4326 jako bbox w stopniach, inne (np. 2180) przez `pyproj` + `Pillow` (przepróbowanie na siatkę kafelka). Retry 3x, bo publiczne serwery dają losowe 404.
- Klient woła `ogc://<id>/{z}/{x}/{y}` (protokół MapLibre, `shell.html` ~1549–1575) i dostaje kafelek z mostu.
- Sam MapLibre bierze zwykły szablon `tiles: ["https://…/{z}/{x}/{y}"]`, więc w web **usługi w EPSG:3857 nie potrzebują Pythona**.

**Ładowanie na stronie (do ekranu postępu)**
- `loadBoot()` w `shell.html` (~1002–1040) robi **sekwencję `await get(...)`**: `boot.<lang>.json`, `link_ll.bin`, `link_type.bin`, `link_attr.bin`, (krzywe: 3 pliki), (budynki: `buildings.json` + 4 pliki `.bin`), potem `Engine.load` (`manifest.json`, `persons.json`, `tracks.bin`) i `engine.want(boot.t)` (pierwsza porcja). Nie ma dziś żadnego wskaźnika; `#runbar` (`<progress>`) istnieje, ale służy do otwierania runu w aplikacji.
- Ciężkie zasoby statyczne: `viz_player/vendor/deck.min.js` ~2,0 MB, `maplibre-gl-shared.mjs` ~0,48 MB, mesh auta `vendor/quaternius/car_mesh.json`.
- Nie zmierzono: rozmiaru i czasu każdego pliku na Pages, kompresji `.bin` (zapisane w postępie jako „nie sprawdzone”). **Hipoteza**: sekwencyjne pobieranie wielu plików (zamiast równoległego) wydłuża start; trzeba to zmierzyć, zanim się to naprawi.

## 3. Czego nie wiemy / ryzyka (do zbadania i pytań do właściciela)

1. **Definicje układów w proj4js.** `pyproj` ma całą bazę EPSG, proj4js potrzebuje definicji. Dla Polski (2180), Wiednia (3416), Berlina/Kelheim (25832) i 4326 można je wbudować; dla dowolnego kodu trzeba pobierać definicję (np. z epsg.io, **CORS i dostępność niesprawdzone**). Zdecyduj z właścicielem: lista wbudowana, czy pobieranie.
2. **Rozmiar proj4js** ok. 100 KB po minifikacji (z pamięci, **zweryfikuj**). Zgodnie z `CLAUDE.md`: nowa biblioteka w `viz_player/vendor/` przychodzi z plikiem licencji i wpisem w `LICENSE-DATA.md` lub `scripts/viz_third_party.py`.
3. **Przeliczanie kafelków w przeglądarce** (usługi w innym układzie niż 3857): canvas/`OffscreenCanvas` zamiast Pillow. Trzeba sprawdzić jakość i koszt (CPU w głównym wątku vs worker). Wersja 1 może obsłużyć tylko 3857 + 4326 i jasno napisać „ten układ jest tylko w aplikacji”, dopóki przeliczanie nie jest gotowe.
4. **Mieszana zawartość:** strona na https nie pobierze usługi na http. Komunikat dla użytkownika.
5. **CORS:** zgodnie ze stanowiskiem właściciela nie obchodzimy go proxy. Wymagane tylko **czytelny komunikat** przy błędzie („serwer nie pozwala przeglądarce pobrać kafelków (CORS); dostępne w aplikacji”), bez udawania, że usługa działa (zasada „nie udawaj obserwacji” z `CLAUDE.md`).
6. **Własne obrazy z plikiem świata** (`rasters.py`) to osobny kawałek (wybór pliku, przeliczenie układu); **poza pierwszym etapem**, chyba że właściciel zdecyduje inaczej.
7. **Stan usług w web:** w aplikacji lista usług jest globalna dla użytkownika (plik w `DATA`); w web naturalnym miejscem jest `localStorage` (z try/catch). Do ustalenia, czy zapisywać.
8. **Bezpieczeństwo adresu wpisanego przez użytkownika:** schemat tylko http/https (tak jest w `ogc._fetch`), bez wstrzykiwania HTML do panelu (nazwy warstw z XML wstawiaj jako tekst).

## 4. Proponowany kształt rozwiązania (propozycja, nie decyzja)

- **Warstwa hosta:** jeden obiekt `host` z metodami i flagami możliwości (`canOpenRun`, `canOsmFile`, `canOgc`, `canRaster`, …). Aplikacja wypełnia go przez pywebview, web przez implementację w JS. Rozproszone `if (WEB)` i `window.pywebview` znikają z logiki funkcji.
- **Wspólne podkłady:** `WEB_BASE` i OGC w EPSG:3857 działają w obu wersjach przez ten sam kod; Python zostaje tam, gdzie jest naprawdę potrzebny (przeliczanie układów w aplikacji, o ile JS tego nie przejmie, otwieranie runów, OSM).
- **Ekran ładowania:** nakładka na całą stronę (nazwa scenariusza + etap + pasek) pokazywana od startu do pierwszej narysowanej klatki. Postęp z liczby pobranych bajtów (`Content-Length` + `ReadableStream`) albo, prościej, z liczby ukończonych plików ze znanej listy. Przy okazji zmierzyć i, jeśli hipoteza się potwierdzi, pobierać pliki równolegle (`Promise.all`). Teksty przez istniejący mechanizm i18n (klucz = polski tekst, EN w `viz_player/i18n.py` i `boot.*.json`).
- **Wspólne wydanie:** rozważyć deploy Pages przy tagu `viz-v*` razem z wydaniem aplikacji (dziś `web_pages.yml` jest ręczny i bierze zip demo z wydania). To zmiana workflow; **pytaj właściciela przed zmianą**.
- **Nie przenosić do JS:** budowy indeksu i eksportu, OSM, `output_config.xml`. Zostają w Pythonie/CI.

## 5. Zasady (z `CLAUDE.md`, przypomnienie)

- Jeden krok = jeden commit `wizualizer: <co>` z trailerem `Co-Authored-By`. **Bez pusha, merge, tagów i wydania**; to robi właściciel.
- Przed commitem: `uv run --group viz pytest viz_player/tests -q` (dziś 132 passed, ~4 min) i smoke na prawdziwym runie. Dowody (liczby, zrzuty) do `docs/projekt/wizualizer_postep.md`; blocker zostaje otwartym punktem.
- Dokumentacja z każdym krokiem: `wizualizer_postep.md`, `docs/viz/README_pl.md` (zachowanie), `docs/projekt/wizualizer_web.md` (różnice web/desktop).
- Krok dotykający paczki kończy się uruchomieniem **zbudowanego exe** z okrojonym PATH (z `WindowsPowerShell\v1.0`, bo `grab.py` woła `powershell`) i `EASY_MATPLAYER_DATA` w pustym katalogu.
- Klucze, dane CC BY-NC i `.xml.zst` nie wchodzą do repo.

## 6. Linia bazowa (to, czego scalenie nie może pogorszyć)

- `pytest viz_player/tests -q`: 132 passed.
- Smoke z kodu na `../matsim-kutno/output/g1r8_25pct_s4711`: `smoke OK n=729 … mapa=1426x863 klient_vs_python_max=0.46 m budynki3D=83617 blyski=215/4 linki_z_ruchem=2911`.
- Smoke exe (zamrożony) po `scripts\viz_build.bat`: OK, exit 0.
- Układ desktopu (wyspy ze szkła, kapsuła, panel pod pastylką) i telefonu: bez zmian.
- Strona: `?run=demo-kutno` pokazuje auta, budynki 3D, dwa podkłady z suwakami krycia, przełącznik języka.

---

# PROMPT dla następnego agenta

Skopiuj poniższy blok do nowej sesji w katalogu repo `easy-matanimation`.

```text
Pracujesz w repo easy-matplayer (pywebview/WebView2 + strona na GitHub Pages, jeden klient: viz_player/shell.html + engine.js). Zanim cokolwiek zrobisz, przeczytaj CLAUDE.md oraz docs/projekt/handoff_scalenie_web_desktop.md (tam jest pełny kontekst, ustalenia z właścicielem, hipotezy i ryzyka) i docs/projekt/wizualizer_postep.md. Pracuj po polsku. Jeśli czegoś nie wiesz albo masz wątpliwość co do decyzji, zadaj pytanie właścicielowi (Michał), zamiast zgadywać.

CEL (trzy rzeczy, w tej kolejności):
1. Scalenie developmentu web i desktop: nowa funkcja ma trafiać do obu wersji bez kopiowania. Ma to być warstwa hosta (obiekt z metodami i flagami możliwości) zamiast rozsianych `if (WEB)` i `window.pywebview` w logice funkcji. Nie przenoś do JS budowy indeksu, eksportu, OSM ani czytania output_config.xml.
2. Własne WMS/WMTS/XYZ w wersji web (dziś ukryte). Decyzja właściciela: serwer bez Access-Control-Allow-Origin to jego problem, nie obchodzimy CORS proxy; ma być tylko czytelny komunikat. Dołożenie proj4js (do przeliczania układów) jest akceptowane. Zacznij od usług w EPSG:3857/4326 (MapLibre bierze szablon URL wprost), potem przeliczanie innych układów w przeglądarce. Własne obrazy z plikiem świata są poza zakresem, chyba że właściciel zdecyduje inaczej.
3. Ekran ładowania z paskiem postępu na stronie (po kliknięciu kafelka w hubie ładowanie trwa kilka sekund bez żadnej informacji): nakładka z nazwą scenariusza, etapem i paskiem, do pierwszej narysowanej klatki. Najpierw zmierz, co trwa (loadBoot pobiera pliki sekwencyjnie), potem ewentualnie zrównoleglij pobieranie. Teksty przez istniejące i18n (pl/en).

KOLEJNOŚĆ PRACY (przestrzegaj restrykcyjnie):
A. ANALIZA KODU NAJPIERW. Przeczytaj shell.html (zwłaszcza rozgałęzienia WEB, loadBoot, bootMap, sekcje usług OGC ~1549–1810, WEB_BASE ~1938), engine.js, window.py (klasa Api), ogc.py, rasters.py, scripts/web_build.py, web/index.html, .github/workflows/web_pages.yml i testy. Nie koduj, dopóki nie napiszesz właścicielowi krótkiego podsumowania: co jest wspólne, co jest rozdzielone, jak widzisz docelową architekturę, jakie ryzyka i jakie masz pytania. Poczekaj na jego odpowiedź.
B. TESTY LINII BAZOWEJ PRZED REFAKTOREM. Zapisz stan obecny, żeby wersja po scaleniu nie była gorsza: pytest (dziś 132 passed), smoke z kodu na prawdziwym runie (liczby z handoffu, sekcja 6), smoke zamrożonego exe. Dopisz testy, które chronią to, co scalenie może zepsuć: tryb web (?run=), ukryte/pokazane kontrolki w obu trybach, flagi możliwości hosta, podkłady web, adres kafelka WMTS GUGiK, parsowanie GetCapabilities po stronie klienta (na fixturach z viz_player/tests/test_ogc.py), komunikat przy błędzie CORS/https/http, ekran ładowania (etapy i znikanie). Testy kończą się asercją i nie piszą do śledzonych katalogów repo.
C. KODUJ W MAŁYCH KROKACH, jeden commit na krok (`wizualizer: <co>`, trailer Co-Authored-By). Po każdym kroku: pytest + smoke, wynik i dowód w wizualizer_postep.md, aktualizacja README_pl.md i wizualizer_web.md. Zmianę, która dotyka paczki, zakończ uruchomieniem zbudowanego exe (okrojony PATH z WindowsPowerShell\v1.0, EASY_MATPLAYER_DATA w pustym katalogu).
D. Sprawdź wynik w przeglądarce wbudowanej (strona z ?run=demo-kutno z lokalnego serwera statycznego, zbudowanego scripts/web_build.py) i w oknie aplikacji; zapisz, czego NIE zmierzyłeś.

GRANICE:
- Nie rób pusha, merge, tagów, wydania ani deployu Pages; to robi właściciel (CLAUDE.md). Nie zmieniaj workflow web_pages.yml bez zapytania.
- Nie wymyślaj danych i nie udawaj obserwacji: gdy usługa nie działa (CORS, http na stronie https, układ nieobsługiwany), pokaż to użytkownikowi.
- Nowa biblioteka w viz_player/vendor/ (proj4js) przychodzi z plikiem licencji i wpisem w LICENSE-DATA.md lub scripts/viz_third_party.py. Sprawdź jej rozmiar i wersję (min. 2 tygodnie), nie zgaduj.
- Adres wpisany przez użytkownika: tylko http/https, nazwy warstw z XML jako tekst (bez wstrzykiwania HTML).
- Nie ruszaj układu graficznego desktopu i telefonu, chyba że wymaga tego zadanie.

PYTANIA, które musisz zadać właścicielowi przed kodowaniem: (1) definicje układów w proj4js: lista wbudowana (2180, 3416, 25832, 4326) czy pobieranie z sieci; (2) czy zapisywać dodane usługi w web (localStorage); (3) czy dopuścić od razu przeliczanie układów innych niż 3857/4326, czy w pierwszym etapie komunikat „tylko w aplikacji”; (4) czy ekran ładowania ma pokazywać bajty, czy etapy; (5) czy zmienić workflow Pages na deploy przy tagu viz-v*.
```
