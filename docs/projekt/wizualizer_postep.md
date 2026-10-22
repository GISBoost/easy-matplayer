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
- [x] P1. Poprawki okna (plan `wizualizer_plan.md`, zlecenie 2026-10-22): mnożnik ze strzałkami co 1.
- [x] P2. Kolor dróg wg `type` (checkbox, legenda).
- [x] P3. Kolor auta: prędkość / klasa (przełącznik, legenda).
- [x] P4. Znacznik grot + półkole (`IconLayer`), skalowany z zoomem w granicach 0,25–3.
- [x] P5. Własny raster, WMS, otwieranie runu przez wybór folderu (P5a, P5b, P5c niżej).
- [x] P5a. Przycisk „otwórz run…” (wybór folderu, błąd zostawia bieżący run, sukces przeładowuje stronę).
- [x] P5b. Podkłady WMS / WMTS jak w QGIS: „dodaj WMS / WMTS…”, nazwa + adres, lista warstw z GetCapabilities, układ dopasowany automatycznie.
- [x] P5c. Własny raster: kafelki XYZ, obraz z georeferencją (GeoTIFF, plik świata) i obraz bez niej (układanie ręczne albo wpisany zakres).

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

### P1: mnożnik ze strzałkami (2026-10-22)

- `shell.html`: ◀ / bieżący mnożnik / ▶ między pauzą a presetami, skok 1, zakres 1–300, strzałka na granicy nic nie zmienia. Preset świeci tylko, gdy jest równy mnożnikowi (po `10×` → `9×` nie świeci żaden). Klawisze ←/→ dalej ±60 s.
- Dowód: smoke w prawdziwym oknie sprawdza sekwencję `1×, ◀ → 1×, ▶ → 2×, 10× i ◀ → 9×`, zero podświetlonych presetów; 52 testy; smoke OK n=728, budynki 83 617.

### P2: kolor dróg wg `type` (2026-10-22)

- Checkbox „kolor dróg OSM” w panelu (domyślnie wyłączony = dawna szara paleta). Tabela kolorów z planu, `*_link` bierze kolor klasy głównej, grubości bez zmian. Legenda (lewy dolny róg, pod rampą prędkości) pokazuje tylko typy z `types` otwartego runu, „inna” gdy jest typ spoza tabeli. Kolor to akcesor `PathLayer` z `updateTriggers`, dane się nie przebudowują.
- Dowód: smoke przełącza checkbox: legenda widoczna, ≥3 wiersze, brak błędu rysowania, po wyłączeniu legenda znika; 52 testy; smoke OK 728 aut. Wygląd ocenia człowiek.

### P3: kolor auta, prędkość / klasa (2026-10-22)

- Przycisk „kolor auta” w panelu przełącza rampę prędkości na kolor klasy (`CLASS_COLOR`: r `#5aa2ff`, c `#3dbe7a`, o `#e0c15a`, t `#a89880`, h `#e15a4a`, inne `#e7e9ee`). W trybie klasy rampa chowa się, a legenda klas (klasy z chipami) staje w tym samym miejscu. Liczba km/h w panelu bez zmian.
- Dowód: smoke przełącza tryb, sprawdza legendę (liczba wierszy = liczba chipów), a bufor kolorów pierwszego auta równy kolorowi jego klasy, i wraca do prędkości; 52 testy; smoke OK 728 aut.

### P4: znacznik grot + półkole (2026-10-22)

- Auto to `IconLayer` z atlasem trzech ikon (wypełnienie, obrys 1 px `#121418`, kontur zaznaczenia `#7eb6ff` 1,5 px). Podstawa 16 px, półkole z tyłu o promieniu 8, grot 32 px przed środkiem podstawy; ciężkie ×22/16. Punkt pojazdu w środku podstawy. Kółko i kreska kierunku usunięte, tolerancja kliku 8 px bez zmian.
- Skalowanie z zoomem: mnożnik `2^(0,5·(zoom−15))`, granice 0,25–3 (`MARKER` w `shell.html`, jedno miejsce do strojenia). Przy zoomie 15 znacznik ma rozmiar z planu; bardzo duże przybliżenie daje 3×, widok całej gminy 0,25×.
- Dowód: smoke (skala 1 przy zoomie 15, granice, rośnie z zoomem, brak błędu rysowania), 52 testy, zrzut `smoke.png` pokazuje znaczniki w widoku całej gminy. Czeka na ocenę wzrokową na kilku zoomach i sprawdzenie kierunku grota względem jazdy (obrót jak dotychczasowa kreska).

### Poprawki po teście właściciela, runda 2 (2026-10-22)

- **Kolor auta „klasa” nie działał:** klucze klas w manifeście to `resident`, `commuter`, `outbound`, `tlo`, `ciezkie`, a tabela `CLASS_COLOR` miała litery `r c o t h`, więc wszystko wpadało w kolor „inne” (biały). Smoke tego nie łapał, bo porównywał bufor z tym samym białym zapasowym kolorem. Tabela ma teraz klucze z manifestu, a smoke wymaga, żeby każda klasa z chipem miała własny kolor i żeby kolor pierwszego auta był kolorem jego klasy, nie zapasowym.
- **Grot krótszy o 15%:** `MARKER.tip` = 1,7 podstawy (było 2), czyli 27 px przy podstawie 16.
- **Grubość dróg w trybie „kolor dróg OSM”:** autostrada 4 px, główna 3, drugorzędna 2,5, trzeciorzędna 2, osiedlowa i bez klasy 1,5, strefa zamieszkania 1,25, zawrotka 0,75, inna 1 (wyłączony checkbox zostawia dawne grubości). Wybrana droga ma o 2 px grubszą nakładkę.
- **Modele 3D pojazdów (checkbox):** bryły z kodu w metrach (osobówka 4,5 × 1,8 m z kabiną, ciężarówka 10 × 2,5 m z kabiną), `SimpleMeshLayer`, kolor jak ikony (prędkość albo klasa). Ikony chowają się od zoomu 16, modele są zawsze. Przy widoku całej gminy modele są mniejsze niż piksel, więc to widać po przybliżeniu (najlepiej z przyciskiem „3D”). Lekcja: binarne atrybuty `getOrientation` i `getTransformMatrix` w `SimpleMeshLayer` deck.gl 9.4 są ignorowane, działają akcesory obiektowe; orientacja `[0, kurs, 0]` (kurs w stopniach, przeciwnie do ruchu wskazówek od wschodu).
- Dowód: smoke w prawdziwym oknie z dwoma zrzutami przy zoomie 18,5 tego samego auta (`smoke_zoom.png` z modelem, `smoke_icon.png` z ikoną): model leży wzdłuż drogi, grot wskazuje kierunek jazdy; 52 testy.
- **Modele za małe (runda 3):** bryła w prawdziwych metrach miała kilka pikseli. Teraz długość modelu na ekranie = długość znacznika (`MODEL_PX` 35 px × mnożnik zoomu znacznika, ciężarówka ×22/16), nigdy mniejsza niż prawdziwy rozmiar; ikony chowają się od zoomu 17 (`MODEL_ICON_ZOOM`), więc model jest przesadzony 2–8×, żeby był czytelny. Smoke sprawdza skalę ≈3 przy zoomie 18,5. Uwaga: zrzut smoke łapie okno po tytule, więc przy otwartej aplikacji właściciela łapie jego okno. Wygląd ocenia właściciel po restarcie aplikacji.
- **Model samochodu Quaternius (runda 4):** za zgodą właściciela pobrany „LowPoly Car pack” (OpenGameArt, 911 KB, CC0). Do repo trafiły `BasicCar.obj`, `CarTexture.png`, `CREDITS.md` i wynik `car_mesh.json` (188 KB, 5604 wierzchołków) w `viz_player/vendor/quaternius/`; `pipeline/viz_models.py` robi konwersję (oś przodu `FRONT_SIGN`, długość 4,5 m, role kolorów z tekstury-palety). Okno ładuje go zamiast bryły osobówki, nadwozie dostaje kolor pojazdu (mnożenie z kolorem modelu działa), reszta ciemna; panel podpisuje „Modele aut: Quaternius (CC0)”. Paczka nie ma ciężarówki, zostaje bryła z kodu. Dowód: zrzut `smoke_zoom.png` z własnego okna smoke (tytuł „easy-matviz smoke”, żeby zrzut nie łapał okna właściciela): auto leży wzdłuż drogi, pół z kabiną z tyłu; test `test_models.py`; 53 testy.
- **Grot pod modelem (runda 5):** przy włączonych modelach ikony (grot) nie są rysowane wcale (wcześniej do zoomu 17 grot jechał pod modelem); `MODEL_ICON_ZOOM` usunięty. Zaznaczenie przy modelach to okrąg wokół modelu zamiast konturu grota. Smoke sprawdza listę warstw: z modelami są `car-models` i brak `cars`/`car-outline`, po wyłączeniu odwrotnie.
- **Auta jechały tyłem (runda 6):** `FRONT_SIGN` w `viz_models.py` ma być `+1` (przód modelu w +z OBJ; moje pierwsze założenie z reflektorów było odwrotne). Zmiana samej stałej nic nie daje, trzeba uruchomić `uv run python pipeline/viz_models.py`, bo okno czyta gotowy `car_mesh.json`. Ciężarówki (bryła z kodu) jechały dobrze.

### Pomiar wydajności (2026-10-22)

- `viz_player/bench.py` (`uv run --group viz python -m viz_player.bench output/<run>`): prawdziwe okno WebView2, RTX 4070, odtwarzanie 1× w szczycie 6–9, po 6 s na wariant (po 2 s rozgrzewki). Mierzy odstępy `requestAnimationFrame` i czas `render()` po stronie CPU. Okno pomiarowe musi być widoczne i niezasłonięte.
- Kutno 100% (`gha_100pct_10it/kutno-r7b-100pct-10it`, 2833 auta, łamane włączone), widok gminy i zbliżenie z zoomem 16,5, ikony / modele 3D, bez i z budynkami 3D (83 617, pochylenie 55°): **wszystkie osiem wariantów 169,5–169,8 FPS** (limit monitora), odstęp klatek p95 6,0 ms, `render()` mediana 0,8–1,0 ms, p95 1,1–2,0 ms. Cel 30 FPS spełniony z zapasem, także dla modeli jako obiektów z akcesorami.
- Ograniczenie: FPS jest przycięty do odświeżania monitora, więc to, ile zapasu jest ponad 170, mówi tylko czas CPU (≈1 ms). GPU zintegrowane (krok 8) nadal nie sprawdzone.
- Po drodze: pomiar wieszał się, bo `evaluate_js` zwracał obiekt mapy (`map.jumpTo(...)`), którego most nie umie zserializować; wyrażenia sterujące kończyć `; 0`. Pierwsze podejście zmarnowało też przebudowa indeksu 100% (80 s) przy pierwszym otwarciu.

### Pomiar bez GPU, render programowy (2026-10-22)

- Komputer właściciela: Ryzen 5 5600X, brak zintegrowanej grafiki, jedyny GPU to RTX 4070. Render na CPU wymusza `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--disable-gpu --enable-unsafe-swiftshader"`; okno raportuje renderer „SwiftShader (Vulkan, CPU)”. To nie jest to samo co prawdziwe iGPU: SwiftShader jest zwykle o rząd wielkości wolniejszy, więc wynik to dolna granica.
- Kutno 100%, 2843 auta, 8 wariantów jak wyżej (6 s na wariant, ~1 klatka na rozgrzewkę): ikony płasko **2,1 FPS** (gmina) i **2,5 FPS** (zoom 16,5); budynki 3D **0,26–0,31 FPS**; modele 3D płasko 0,29 (gmina) i 0,64 (zoom); modele + 3D 0,2 FPS. Czas `render()` po stronie CPU bez zmian (≈1,5–2,3 ms), czyli cały koszt to rasteryzacja w SwiftShader.
- Wniosek: bez GPU 100% jest nieużywalne (cel 30 FPS niespełniony ponad 10×), a 3D i modele dodatkowo go zabijają. Prawdziwe iGPU (krok 8) trzeba sprawdzić na innym komputerze. Opcje na później: tryb „lekki” (bez budynków i modeli, rzadsze klatki, mniej aut), jeśli ktoś ma otwierać to bez GPU.

### P5a: otwórz run (2026-10-22)

- Przycisk „otwórz run…” nad polem id. `Api.pick_run` woła `create_file_dialog(FOLDER)` (start w `output/`), anulowanie nic nie zmienia. `Api.open_path` otwiera run w świeżym `Player`: brak katalogu albo `output_events.xml.zst` / `output_network.xml.zst` daje zdanie pod przyciskiem i bieżący run zostaje; sukces buduje indeks, łamane, eksport i budynki, zapisuje `output/viz_player_state.json` i strona się przeładowuje. Na czas otwierania panel pisze „Run się otwiera…” (nowy indeks 100% to ok. 80 s).
- Okno uruchamiane z konsoli ładuje teraz stronę ze stałego katalogu `output/viz_player_site/`, bo przeładowanie wymaga tego samego adresu, a run się zmienia. Smoke i `--check` dalej piszą do `<run>/viz/site`.
- Dowód: smoke w prawdziwym oknie: zły katalog daje błąd i `boot.run` bez zmiany, potem przełączenie na `g5r6_25pct_s4711` (nowa strona, mapa i rysunek wstają), powrót do R7b; 53 testy. **Nie sprawdzone automatem:** sam systemowy dialog wyboru folderu (klika go człowiek).

### P5b: podkłady WMS / WMTS (2026-10-22)

- Użytkownik: panel „Podkłady WMS / WMTS” → „dodaj WMS / WMTS…” → nazwa i adres → „połącz” (GetCapabilities, typ rozpoznany sam) → lista warstw (z adnotacją o układzie, warstwy nie do narysowania szare z powodem) → „dodaj warstwę”. Każda dodana usługa ma checkbox, suwak przezroczystości i ×. Lista jest globalna (`output/viz_player_services.json`), przeżywa zmianę runu i restart; podkłady leżą pod autami i drogami.
- Kod: `viz_player/ogc.py` (stdlib + pyproj + Pillow, bez nowych zależności), `Api.ogc_*` w `window.py`, dialog i protokół MapLibre `ogc://<id>/{z}/{x}/{y}` w `shell.html`. **Kafelki pobiera Python**, nie przeglądarka (CORS), i oddaje je przez most; do usługi wysyłany jest tylko adres wpisany przez użytkownika, bez kluczy.
- Układ współrzędnych dopasowuje się sam, w kolejności: EPSG:3857 i aliasy (900913, 102100…) wprost z `BBOX` kafelka; stopnie (CRS:84 / EPSG:4326, z poprawną kolejnością osi dla 1.3.0); każdy inny układ rzutowany (np. EPSG:2180) przez pyproj: pobierany jest obraz w tym układzie i przepróbowany na siatkę kafelka. Kolejność osi bbox dla WMS 1.3.0 z definicji układu (EPSG:2180 ma północ pierwszą). WMTS: zestaw kafelków w EPSG:3857, 256 px, poziomy dopasowane po mianowniku skali (identyfikatory macierzy dowolne), tryb KVP i REST.
- Dowód: 9 testów `test_ogc.py` (opis WMS i WMTS, dziedziczenie CRS, wybór układu, bbox, oś, odrzucenie nie-obrazu, przepróbowanie 2180) i smoke w prawdziwym oknie z lokalną atrapą WMS: dialog, połączenie, wybór warstwy, 28 kafelków z poprawnym `CRS`/`LAYERS`/`BBOX`, ukrycie warstwy, przetrwanie przeładowania strony (zmiana runu), usunięcie. Prawdziwe publiczne usługi GUGiK (ortofotomapa WMS i WMTS, dane publiczne, bez klucza): kafelek 3857 vs ten sam kafelek przeliczony z 2180 korelacja 0,96 (średnia różnica 3,9/255), z 4326 korelacja 0,99; zrzut z okna: ortofoto leży zgodnie z siecią drogową (rondo w Kutnie na swoim miejscu).
- Uwagi: publiczne usługi bywają chwilowo niedostępne (zrywane połączenie, losowe 404), więc `_fetch` próbuje 3 razy. Kafelek, który mimo to zawiedzie, zostaje pusty (MapLibre nie ponawia). Pasek na dole nadal pisze „Podkład wyłączony.” (to dawny podkład CARTO, osobna sprawa). Własny raster (P5c) czeka.

### P5c: własny raster (2026-10-22)

- **XYZ:** ten sam dialog „dodaj WMS / WMTS / XYZ…”; adres z `{z}` i `{x}` jest rozpoznany jako szablon kafelków (`{y}`, `{-y}` dla TMS, `{s}` = serwer a). Kafelki idą przez Pythona jak WMS.
- **Obraz z georeferencją:** „dodaj obraz…” (wybór pliku png/jpg/tif/webp). Georeferencja z GeoTIFF (tagi ModelPixelScale/Tiepoint/Transformation, układ z GeoKeys) albo z pliku świata obok (.wld, .pgw, .jgw, .tfw…), układ z `.prj`. Plik świata bez układu: okno pyta o kod EPSG z podpowiedzią policzoną z liczb (stopnie → 4326, zakres Polski → 2180, inaczej 3857).
- **Obraz bez georeferencji** (szkic, skan, zrzut): trafia na środek bieżącego widoku (60% szerokości, proporcje obrazu) w trybie ręcznego układania. Uchwyt środka przesuwa, uchwyt rogu skaluje i obraca wokół przeciwległego rogu (podobieństwo, proporcje zostają, czyli to samo co georeferencja po dwóch punktach). Suwak przezroczystości w panelu pozwala trafić w sieć dróg leżącą pod spodem; „gotowe” kończy układanie, „ustaw” przy obrazie wraca do niego. Alternatywa: „wpisz zakres…” (W, E, S, N w wybranym układzie, domyślnie 4326, przecinek dziesiętny przyjmowany).
- Obraz jest kopiowany do `output/viz_player_rasters/` (poza gitem), zmniejszany do 4096 px po dłuższym boku (limit tekstury słabszych GPU), PNG gdy ma przezroczystość, inaczej JPEG 92. Narożniki (lon/lat) trzymane w `output/viz_player_services.json` razem z podkładami WMS; MapLibre rysuje je źródłem `image` (dowolny czworokąt, więc obrót i skos działają). Usunięcie obrazu kasuje plik.
- Dowód: 12 nowych testów (`test_rasters.py`: plik świata z przesunięciem o pół piksela, .prj → EPSG, GeoTIFF zapisany Pillowem z tagami, brak georeferencji, zakres, ułożenie na środku, zmniejszanie i alfa; XYZ w `test_ogc.py`) i smoke w prawdziwym oknie: obraz bez georeferencji wstaje w trybie ręcznym z 5 uchwytami, przeciągnięcie środka o (120, 40) px przesuwa obraz o tyle, przeciągnięcie rogu skaluje z zachowaniem proporcji i stałym lewym-górnym rogiem, ułożenie zapisuje się w liście usług, wpisany zakres daje dokładne narożniki, plik świata bez układu pyta o EPSG (podpowiedź 2180) i ląduje w Polsce, po zmianie runu (przeładowanie strony) wszystkie trzy podkłady wracają, usunięcie czyści listę i pliki. Zrzut okna: szkic na tle sieci dróg z uchwytami i paskiem podpowiedzi.
- Ograniczenia: bez GeoTIFF-ów ze zwartym kodowaniem, którego Pillow nie czyta (wtedy komunikat „Nie da się wczytać”), bez PixelIsPoint (przesunięcie o pół piksela zaniedbane), obraz w układzie rzutowanym jest rysowany jako czworokąt z czterech narożników (przy dużych zasięgach krzywizny nie ma); edycja rogami działa najlepiej bez pochylenia widoku (pitch 0). Dwa punkty z podglądem obok siebie (pełna georeferencja punktami kontrolnymi jak w QGIS, z trzecim punktem dającym skos) to ewentualny następny krok.
