# Audyt kodu wizualizera (okno odtwarzacza, D24)

Data: 2026-10-22. Zakres: gałąź `wizualizer` (teraz w `main`): `pipeline/viz_index.py`, `pipeline/viz_engine.py`, `viz_player/player.py`, `viz_player/curves.py`, `viz_player/shell.html`, zależności. Kod przeczytany w całości, nie uruchamiany. Cel audytu: dobre fundamenty przed dokładaniem funkcji w etapie 3 (PT, rower, pieszo, ride, atrybuty osób, Łódź).

## Werdykt

Silnik jest sensowny: rzadki indeks z cache po sha256, klatka liczona po kubełkach czasu, łamane OSM z bezpiecznym fallbackiem na cięciwę, sporo testów. Nie przepisywać od zera. Fundamenty nie udźwigną jednak etapu 3: trzy miejsca blokują nowe tryby, kilka stałych jest na sztywno pod Kutno i run R6, a jedna „łatka” (wysyłanie łamanych przez `evaluate_js`) wynika z błędnej metody ładowania strony.

## Blokery pod etap 3

1. **Tylko samochód, klasa z pierwszej litery id.**
   - `viz_index.py` indeksuje cztery eventy ruchu po sieci (`vehicle enters traffic`, `entered link`, `left link`, `vehicle leaves traffic`). Odcinki `walk` i `bike` teleportowane (jak w Kelheim) nie mają eventów ruchu po linkach, więc ich nie będzie w indeksie. Linie PT to inne eventy (`TransitDriverStarts`, `PersonEntersVehicle`).
   - Klasa pojazdu to `"rcoth".find(vehicle_id[0])`, a polskie nazwy klas siedzą w kodzie (`CLASS_NAMES`). To konwencja nazewnictwa agentów, a nie atrybut osoby.
   - Potrzebny klasyfikator czytający `subpopulation` i atrybuty z planów oraz tryb. Litery `r c o t h` stają się jednym z jego wyników.
2. **Id pojazdu zlewa się z id osoby.** `pack()` robi `id_of` z sumy id pojazdów i osób, a wyszukiwanie i zaznaczanie opiera się na równości tekstów. Przy jednym trybie sieciowym `car` pojazd ma id osoby i to działa. Przy kilku trybach sieciowych (`ride`, `bike` na sieci, jak w Berlinie i Kelheim) id pojazdu prawdopodobnie dostaje suffix trybu (do sprawdzenia na pierwszym runie z `ride`). Tracki powinny mieć jawne `person_id` (event `vehicle enters traffic` ma atrybut `person`).
3. **Stan w dwóch miejscach i wyścigi.** `t`, klasy, zaznaczenie i śledzenie żyją w `Player` (Python), czas jest też w JS, razem z flagami `dirty`, `busy`, `hold`, `scrub`. pywebview woła `Api` z wielu wątków, a `frame_np` cache'uje `_fr` pod kluczem `(t, classes)`; `pick`, `classes`, `lookup` mutują ten sam stan bez blokady. Cel: czysty `frame(t, classes, selected, follow) -> payload`, cały stan po stronie klienta.

## Stałe na sztywno

- `ORIGIN = (524805.0, 485023.0)` pochodzi z `pipeline/g6_bake.py` (Blender) i jest punktem Kutna. `viz_index` importuje go z kodu Blendera. `script_sha256` w cache liczy tylko `viz_index.py`, więc zmiana `ORIGIN` w `g6_bake.py` nie unieważni indeksu, a pozycje się przesuną. Origin ma wynikać z bbox sieci, trafiać do `meta.json` i do klucza cache.
- `"1807611370009f"` w produkcyjnym `boot()` (`viz_player/player.py`, `bendI`/`bendN` w payloadzie, JS tego nie używa). Pozostałość debugowania. Ten sam link w `check()`.
- Akceptacja R6 w kodzie biblioteki: `R6_NAME`, `R6_TRACKS`, `R6_PEAK` itd. w `viz_index.py`, osoba `r6510903_5` i współrzędne Kutna (52,2307 N) w `check()`/`smoke()`. Baza to już R7b (D23/D25), a po G1 i atrybutach osób liczby się zmienią. Przenieść do fixtury albo raportu.
- Limity jako twarde błędy: 300 s parsowania (`PARSE_BUDGET_SEC`) i 1 GiB RAM (`RAM_BUDGET`). Run 100% albo Łódź się nie otworzy. Ostrzeżenie i tryb ograniczony zamiast `raise`.
- `START = 6*3600` i okno 6–9 wpisane w indeks (`max_concurrent_6_9`).

## Ładowanie strony przez `html=`

`NavigateToString` ucina stronę przy ok. 1,5 MB, a cała strona z Leafletem i siecią wchodzi jako jeden string. Z tego powodu istnieją: `_push_curves` (współrzędne w porcjach po 2000 przez `evaluate_js`), flagi `curveWait`, `curvesReady`, `paintedCurves` i test `page_bytes < 1_200_000`. Przyczyną jest metoda ładowania. pywebview potrafi serwować lokalny katalog po HTTP (`create_window(url=<ścieżka>)`, `webview.start(http_server=True)`), a JS pobierze `boot.json` i tablice binarne. To usuwa ok. 150 linii Pythona i część JS-a oraz limit wielkości. Najlepszy stosunek zysku do pracy w całym audycie.

## Struktura kodu

- `viz_player/player.py` ma 1250 linii: model okna, ~200 linii `self_test`, `check` (akceptacja na prawdziwym runie), `smoke` (automat UI) i `_grab` (60 linii PowerShella z user32). Testy używają `raise SystemExit` zamiast `assert`. `_forbid()` sprawdza obecność słów w kodzie źródłowym, a self-test sprawdza literalne tokeny w HTML (`"255, 31, 13"`, `"paintedCurves"`): zmiana nazwy zmiennej w JS wywali test bez błędu zachowania.
- Trzy kopie generatora mini-runu (sieć XML + eventy) w `viz_index.py`, `viz_engine.py` i `player.py`. Jedna wspólna fixtura wystarczy.
- `smoke` zapisuje `docs/research/wizualizer_okno.png`, a ten plik jest w gicie: test z efektem ubocznym w śledzonym katalogu.
- `VMAX`, rampa kolorów, `clock`, `auta` zdublowane w `player.py`, `shell.html` i `blender/g6_load.py`. Pilnuje ich tylko sprawdzanie tokenów.
- JS w jednym pliku z globalnymi zmiennymi; haki testowe w kodzie produkcyjnym (`window.drawnN`, `drawError`, `hold`).

## Decyzje projektowe

1. **Dwa źródła prawdy dla pozycji z eventów.** `viz_index.py` mówi wprost, że semantyka pozycji jest „kopią `g6_bake.py`”, a jednocześnie z niego importuje. Albo `g6_bake` czyta indeks, albo jest oznaczony jako przestarzały w ROADMAP. Teraz wyniki Blendera i okna mogą się rozjechać bez ostrzeżenia.
2. **Zależności.** `pywebview` i `osmium` są w głównych `dependencies` całego pipeline'u. Narzędzie desktopowe tylko pod Windows (`edgechromium`, PowerShell) nie powinno wpływać na instalację analizy: grupa `viz` (`uv add --group viz`).
3. **Łamane zależą od PBF.** `find_pbf()` bierze ostatni `lodzkie-*.osm.pbf`, świeżość cache liczona po mtime. Przy G1 sieć się zmieni. Fallback na cięciwy jest dobry, ale cichy (tylko `player.log`). Pokazać w UI „łamane: X z Y”.
4. **Podkład CARTO.** Klucz jest w gitignore i nie trafia do logów (dobrze). Sieć bez podkładu to rozsądne ustawienie domyślne. CARTO to zewnętrzna zależność z własnymi warunkami, a zrzut z kafelkami leży w publicznym repo (`docs/research/wizualizer_okno.png`). Sprawdzić warunki i atrybucję przed pushem.
5. **Prędkość w panelu to średnia na odcinku** (długość / dt), nie chwilowa. W kolejce zawyża. Zmienić etykietę.
6. **Okno otwiera się dopiero po zbudowaniu indeksu** (do 300 s, bez wskaźnika postępu). Dla 25% akceptowalne, dla 100% nie.

## Kolejność poprawek

1. Origin z bbox, zapis w `meta.json` i w kluczu cache, usunięcie importu z `g6_bake`.
2. Usunięcie `"1807611370009f"` i stałych R6 z kodu biblioteki.
3. Ładowanie strony po HTTP, bez `_push_curves`.
4. `person_id` i klasyfikator w indeksie (odblokowuje tryby i PT). Zmienia format indeksu (`FORMAT`).
5. Bezstanowe `frame(...)` ze stanem po stronie klienta.
6. Podział `player.py`, jedna fixtura testowa, grupa zależności `viz`.

Kroki 1–3 to małe, niezależne zmiany. Kroki 4–5 zmieniają format indeksu i API, więc robić je razem.
