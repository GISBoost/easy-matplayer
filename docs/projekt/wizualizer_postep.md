# Wizualizer easy-matanimation: postęp przebudowy (D26)

Plan i uzasadnienie: `docs/research/wizualizer_architektura_research.md` (sekcja „Aktualizacja 2026-10-22” jest nadrzędna). Gałąź `claude/viz-fundamenty-e093b2`, commity `wizualizer: <co>`, po jednym na krok, bez merge i pushu. Krok jest odhaczony dopiero po uruchomionym teście i dowodzie (liczby, testy, zrzut).

## Liczby bazowe (Kutno 100%, pomiar z badania, 2026-10-22)

| | wartość |
|---|---|
| silnik klatek w Pythonie, szczyt 6–9 (2807 pojazdów) | mediana 13,8 ms, p95 19,3 ms |
| most pywebview, 48 KB JSON | 3,3 ms |
| indeks w RAM | 316 MB |
| klatka w JSON | 108 KB |
| deck.gl 9.4, 200 tys. punktów + 164 tys. budynków 3D, RTX 4070 | limit monitora (~170 FPS) |

Cel: 30 FPS na Kutnie 100%. Łódź tylko 10%. Test tylko na GPU właściciela (RTX 4070). Run referencyjny dla regresji: `output/g5r7b_25pct_s4711` (szczyt klatki 798 o 57 539 s, okno 6–9: 728 o 28 704 s, 24 304 tras, 3 399 518 węzłów).

## Checklista

- [x] 1. Pomiar bazowy (raport badawczy).
- [x] 2. Strona okna po lokalnym HTTP, bez `_push_curves` i limitu strony (commit `3f3a684`).
- [x] 3. Eksport v2: porcje czasowe, `person_id`, tryb, `manifest.json`, origin z bbox sieci. Szczegóły niżej.
- [x] 4. Klient (JS) liczy klatkę, stan tylko po stronie klienta, Python poza pętlą klatek.
- [x] 5. Leaflet → MapLibre 6 + deck.gl, kamera pitch/bearing, komunikat przy braku WebGL2.
- [x] 6. Budynki z preprocessingu (wysokość: tag > levels × 3 m > H0 wg klasy, ±15% z hasha, `h_source`).
- [ ] 7. Nowe tryby, PT, atrybuty osób.
- [ ] 8. (decyzja o wygaszeniu `g6_bake.py` zapisana w D26 2026-10-22; reszta:) test na iGPU (odłożony), przeglądarka opcjonalnie.

Wcześniej zrobione (fundamenty, D24): origin z sieci, `person_id` i klasyfikator, bezstanowa klatka, podział kodu, testy pytest. Patrz PROGRESS 2026-10-22.

## Dziennik kroków

(uzupełniany przy każdym kroku: co, liczby, dowód)

### Krok 3: eksport v2 (2026-10-22)

- `pipeline/viz_export.py`: porcje 15 min, `person_id` i klasa w `tracks.bin`, tryb (dziś tylko `car`), `manifest.json` z wersją, origin z bbox sieci (z `meta.json` indeksu). Cache z kluczem źródła. `Player.write_site` buduje `data/` obok strony, `boot.json` ma pole `data`.
- Liczby: R7b 25% 3 399 518 → 3 460 575 węzłów w porcjach (+1,8%), 130 porcji, 69,7 MB, 1,4 s; Kutno 100% (kopia w katalogu tymczasowym, `output/` oryginalny nietknięty) 13 733 294 → 13 974 338 węzłów, 131 porcji, 281 MB, 4,0 s (indeks 80 s jak wcześniej). Pierwsza wersja (pełne przejazdy w porcji) dawała 2,5× nadmiar (171 MB), dlatego porcja trzyma tylko węzły przedziału i graniczne.
- Dowód: `uv run --group viz pytest viz_player/tests` 45 passed, w tym `test_export.py` (pozycja z porcji = pozycja z `viz_engine.frame` do 1e-7°, nadmiar ≤ 2 węzły na przejazd w porcji, tabele, unieważnianie cache). Klient jeszcze nie czyta porcji (krok 4), więc zachowanie okna bez zmian.

### Krok 4: klient liczy klatkę (2026-10-22)

- `viz_player/engine.js` (bez DOM, działa też pod node): ładowanie porcji, `frame`, łamane OSM, `trail`, `lookup`, `linkNow`. `shell.html` trzyma cały stan, rysuje z `engine.frame`, klika po stronie klienta. Python zostaje tylko jako `describe` (panel, oś czynności, kotwica śledzenia), wołany rzadko (zmiana zaznaczenia, co 250 ms). `Api` ma jedną metodę.
- Liczby (Kutno 100%, szczyt 6–9, 2834 aut): klatka w JS pod node mediana **0,21 ms**, p95 0,39 ms (baza: Python 13,8 ms + most 3,3 ms = ok. 17 ms). Kutno 25%: 717 aut, 0,035 ms. Pętla klatek nie woła Pythona wcale.
- Zgodność: R7b w prawdziwym oknie: 728 aut w oknie 6–9, 452 bez klasy `tlo` (jak przed zmianą), klatka klienta = klatka Pythona (te same przejazdy; pozycja mediana 5 mm, p90 16 cm, max 0,87 m na linku 6 km, nieliniowość lon/lat vs EPSG:2180).
- Dowód: `pytest` 47 passed (w tym `test_client.py` pod node: z łamaną i bez, ślad, `lookup`), `--smoke` na R7b OK (klik w auto, chip, oś, Esc), `accept_r7b` R7b OK.
- Otwarte: RAM Pythona (indeks 316 MB dla 100%) zostaje, bo `describe` czyta czynności z indeksu; wyniesienie tego do eksportu jest kandydatem na krok 7.

### Krok 5: MapLibre 6 + deck.gl (2026-10-22)

- Leaflet usunięty. `vendor/`: MapLibre GL JS 6.0.0 (BSD-3-Clause), deck.gl 9.4.0 (MIT), pobrane z rejestru npm (`npm pack`), licencje obok. Tło mapy to styl z samą warstwą `background` (opcjonalnie raster CARTO z kluczem), drogi/auta/ślad to warstwy deck.gl, kamera pitch/bearing z MapLibre (kontrolka w lewym górnym rogu, prawy przycisk). Brak WebGL2: komunikat zamiast białego ekranu (sprawdzone na stronie z wymuszonym brakiem `webgl2`).
- Liczby (prawdziwe okno WebView2, RTX 4070, pętla klatek przy 1× odtwarzaniu): Kutno 25% (674 aut) 169,8 FPS, Kutno 100% (2746 aut, bez łamanych) 169,8 FPS, czyli limit monitora; cel 30 FPS spełniony z zapasem. Wcześniej (Leaflet + Python) klatka ok. 17 ms bez rysowania.
- Dowód: `--smoke` w prawdziwym oknie na R7b OK (728 aut w oknie 6–9, 452 bez `tlo`, klatka klienta = klatka Pythona, klik w auto, chip, oś, Esc), pytest 47 passed, widok z pochyleniem 55° i obrotem 30° sprawdzony zrzutem w panelu przeglądarki (drogi i auta zgodne z kamerą).
- Odstępstwa i otwarte: (1) `interleaved: true` nie działa z tą parą wersji (wyjątek w deck.gl), nakładka jest osobną kanwą; dla budynków 3D (krok 6) oznacza to brak sortowania w głębi z autami, do sprawdzenia przy kroku 6 (inna wersja MapLibre 5 albo deck.gl, albo budynki jako deck `SolidPolygonLayer` w tej samej kanwie). (2) Serwer pywebview daje `.mjs` jako `text/plain`; obejście w `window.py`. (3) Biblioteki dodają do repo ok. 3,2 MB.
- Poprawka po drodze: adresy danych eksportu mają `?v=<klucz>` (stary cache WebView2 oddawał porcję sprzed zmiany układu).

### Krok 6: budynki 3D (2026-10-22)

- `pipeline/viz_buildings.py` + `config/viz_buildings.toml` (H0 wg klasy, piętra × 3 m, ±15% z hasha id, flaga źródła tag/piętra/założenie; wartości to ZAŁOŻENIA robocze do potwierdzenia). Statyczna warstwa `SolidPolygonLayer`, przycisk „3D” (pochylenie 55° + budynki), opis z liczbami i „© OpenStreetMap contributors”.
- Liczby R7b (obwiednia sieci, czyli powiat z buforem): 83 617 budynków, z tagu 326, z pięter 52 480, założenie 30 811, mediana 3,3 m, 4,5 MB, skan PBF 36 s jednorazowo (potem cache). Budowa danych warstwy w JS 53 ms, koszt `render()` po stronie CPU z 3D mediana 0,4 ms.
- Dowód: pytest 52 passed (w tym budynki z małego PBF utworzonego w teście: kolejność tag/piętra/klasa, hash, cache, obwiednia), `--smoke` w prawdziwym oknie: 83 617 budynków, pochylenie >50° po włączeniu i <5° po wyłączeniu, zrzut w panelu przeglądarki pokazuje bryły.
- **Nie zmierzone:** FPS z włączonym 3D w prawdziwym oknie (próby pomiaru zawiesił błąd skryptu pomiarowego, nie aplikacja). Do zrobienia osobno.
- Ograniczenia: tylko zamknięte linie (bez relacji multipolygon), obrys zewnętrzny, bez dachów.

### Poprawki po teście właściciela (2026-10-22)

- Stutter przy „3D”: warstwa budynków jest tworzona od pierwszej klatki jako ukryta (`visible: threeD`), więc triangulacja 83 tys. wielokątów nie blokuje kliknięcia. Zgłoszone przez właściciela po teście na R7b; nowych funkcji (kształt pojazdu itd.) jeszcze nie ruszamy.
- Budynki nie pojawiały się w worktree bez `data/raw`: PBF jest szukany też w głównym repo.
