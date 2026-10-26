# Przekazanie sesji: stan easy-matplayer (2026-10-23)

Dokument dla następnej sesji pracy w tym repo. Zasady pracy są w `CLAUDE.md` (lokalnym, poza gitem) i w `docs/projekt/wizualizer_postep.md`; tu jest stan i co robić dalej.

## Gdzie co jest

- Repo: `C:\Users\Michal\Desktop\MATSim\easy-matplayer`, gałąź `main`, lokalne, **bez `origin`** (remote, push, merge, tagi robi właściciel).
- Historia: wycięta z gałęzi `claude/viz-fundamenty-e093b2` repo `matsim-kutno` (`git filter-branch`, 75 commitów, ten sam autor i daty). Stara gałąź (ostatni commit `0437efa`) to **archiwum**: nie dostaje już zmian. W `matsim-kutno` nic nie usuwano.
- Ostatnie commity: `c029d72` (ostrzeżenie o braku układu współrzędnych, `crs` w kluczu cache indeksu i łamanych, skala nad legendą), `4622cdc` (pliki repo: `pyproject.toml`, `uv.lock`, `.gitignore`, `.gitattributes`, `README.md`).
- Dane lokalne (poza gitem): `data/raw/osm/lodzkie-261015.osm.pbf` (kopia z matsim-kutno, bez niej demo i smoke nie mają budynków), `build_viz/` (paczki: `easy-matplayer-windows.zip` ok. 46 MB, `easy-matplayer-demo-kutno.zip` 59 MB, `run_do_testu/` z `output_config.xml`). Runy do testów leżą w `matsim-kutno\output\` (np. `g1r8_25pct_s4711` = Kutno 25%, `vienna_1pct_test` = Wiedeń). Plik OSM Wiednia: `matsim-kutno\data\raw\osm\wien-bbbike-261017.osm.pbf`.

## Jak pracować

- Python: `uv run --group viz ...`. Testy: `uv run --group viz pytest viz_player/tests -q` (109 przechodzi).
- Smoke okna na prawdziwym runie (osobny katalog danych, żeby nie ruszać profilu): `EASY_MATPLAYER_DATA=<pusty katalog> uv run --group viz python -m viz_player --smoke "C:/Users/Michal/Desktop/MATSim/matsim-kutno/output/g1r8_25pct_s4711"`. Wiedeń: ten sam polecenie z `vienna_1pct_test`; kończy się znanym, kutnowskim testem „budynek z malutkiego pliku” (nie błąd zmian).
- Paczka: `scripts\viz_build.bat` (zip w `build_viz\`); nie uruchamiaj, gdy aplikacja z `build_viz\dist` jest otwarta (blokuje pliki). Demo: `uv run --group viz python scripts/viz_make_demo.py build_viz/easy-matplayer-demo-kutno.zip "demo-kutno=C:/Users/Michal/Desktop/MATSim/matsim-kutno/output/g1r8_25pct_s4711"`. Demo trzeba przebudować po każdej zmianie `pipeline/viz_*.py`.
- Jeden krok = jeden commit `wizualizer: <co>` z trailerem `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`. Dowód (test, smoke, liczby) i dokumentacja w tym samym kroku; punkt checklisty odhaczasz dopiero po uruchomionym teście z dowodem.
- Zrzuty okna: tylko przez PrintWindow na uchwycie okna aplikacji. `viz_player/grab.py` używa CopyFromScreen i może złapać inne okna pulpitu: nie używaj go do zrzutów, a istniejące `smoke.png` z runów nie otwieraj.
- Zgłoszenia z testów na innych komputerach: najpierw zweryfikuj na własnym kodzie, hipotezy zapisuj jako hipotezy. Pytaj właściciela, zamiast zgadywać.

## Zrobione (skrót)

Aplikacja okienkowa (pywebview + MapLibre + deck.gl), indeks i klatki z eventów, łamane drogi i budynki z OSM, podkłady WMS/WMTS (basemap.at działa), układ współrzędnych z `output_config.xml` z fallbackiem EPSG:3857 i ostrzeżeniem, skala mapy, `minZoom` 3, widok „cały obszar sieci” odporny na szerokie sieci (Wiedeń), paczka PyInstaller, demo (jeden run Kutna), workflow wydania `.github/workflows/viz_release.yml` (nigdy nie uruchomiony na GitHubie), licencje bibliotek w `THIRD_PARTY/`.

## Otwarte (kolejność wg ważności)

1. **A4, test na drugim komputerze:** lista kroków w `docs/projekt/wizualizer_test_drugi_komputer.md` (15 kroków, w tym WMS i skala). Część wyników przyszła z komputera nr 2 (naprawione: mapa przy (0,0), skala pod legendą). Czekają wyniki całości; A4 nieodhaczone.
2. **Pętla startowa na komputerze nr 1:** niepotwierdzona. Hipoteza: stan (`viz_player_state.json`) zapisuje się po zbudowaniu indeksu, a przed pokazaniem okna (`Player.open`, `save_state`), więc mógł utrwalić run z pustym oknem. Potrzebny opis objawu i końcówka `%LOCALAPPDATA%\easy-matplayer\easy-matplayer.log` z komputera nr 1. **Decyzja właściciela:** czy zapis stanu przesunąć na moment po udanym otwarciu okna; opcja `--reset` dopiero po tej decyzji.
3. **Potwierdzenie w oknie przez właściciela:** wygląd skali na ciemnym podkładzie, kafelki WMS/WMTS przy zoomie 3–6, dodanie warstwy WMTS kliknięciem, Wiedeń z plikiem BBBike (łamane 39 456 z 374 991, budynki).
4. **Berlin i Kelheim (EPSG:25832) nigdy nie otwarte.** Berlin v6.4 1%: eventy ok. 274 MB gz + sieć 17 MB, trzeba przepakować na `.zst`. Pobranie wymaga zgody właściciela (limit z `CLAUDE.md`: pytać przy > 500 MB, tu jest mniej, ale decyzja o zakresie jest jego).
5. **Wydanie 0.1.0** (push, merge, tag `viz-v0.1.0`, `gh release upload` zipa dema): robi właściciel. Pierwsze uruchomienie workflow to jego pierwszy prawdziwy test.
6. Drobiazgi: pasek postępu miga na 100% po błędzie indeksu; uszkodzony zapamiętany plik OSM blokuje otwieranie, dopóki nie zedytuje się `viz_player_osm.json`; `grab.py` (CopyFromScreen) do zamiany na PrintWindow; zip z `Compress-Archive` ma separatory `\` (Windows rozpakowuje poprawnie); Geoportal (ortofoto PL) losowo zwraca 404.
7. Wspólne `DECISIONS.md`, `ROADMAP.md`, `PROGRESS.md` zostały w `matsim-kutno` i nie mają wpisu o przeniesieniu; dopisanie (i ewentualne usunięcie wizualizera ze starego repo) robi właściciel.

## Adresy usług mapowych do testów

- OSM (WMS): `https://ows.terrestris.de/osm/service`, warstwa `OSM-WMS`.
- Ortofoto Polska (WMS): `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution`.
- Ortofoto Wiedeń (WMTS): `https://mapsneu.wien.gv.at/basemapneu/1.0.0/WMTSCapabilities.xml`, warstwa `bmaporthofoto30cm`.
