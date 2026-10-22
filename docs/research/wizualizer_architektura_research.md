# Wizualizer: czy fundamenty techniczne są dobre? Badanie architektury

Data: 2026-10-22 (wszystkie „dostęp” w źródłach = ta data). Autor: agent badawczy, tylko odczyt kodu. Nie zmieniałem kodu ani istniejących plików. Raport jest jedynym plikiem utworzonym w repo; skrypty pomiarowe (sonda WebGL, zliczanie budynków) leżały w katalogu tymczasowym sesji poza repo.

Oznaczenia: **[F]** fakt ze źródła (URL w nawiasie lub w sekcji Źródła), **[P]** pomiar własny na tym komputerze, **[W]** wniosek, **[S]** szacunek z liczb, **[?]** nie dało się sprawdzić albo to wiedza własna bez weryfikacji.

---

> **Stan po odpowiedziach właściciela (2026-10-22):** aplikacja zostaje desktopowa (pywebview, Windows), nazwa robocza **easy-matanimation**, licencja GPL-3.0-or-later, cel 30 FPS na Kutnie 100% (Łódź 10%). Decyzje, licencje, pomiary Pythona/mostu/deck.gl i zmieniony plan kroków są w sekcji „Aktualizacja 2026-10-22” (przed „Ograniczeniami”). Tam, gdzie reszta raportu mówi inaczej (np. „przeglądarka jako główny cel”), obowiązuje ta sekcja.

## Streszczenie (1 strona)

**Werdykt: zostać przy webowym stosie (strona w oknie jest normalną, powszechną praktyką), ale zmienić jego środek. Zmiana częściowa, nie przepisanie od zera.**

Co jest dobre i zostaje:
- „Lokalna strona w oknie” to standard. Tak działają Electron, Tauri, pywebview i lokalny serwer + przeglądarka. Wszystkie dojrzałe narzędzia tej klasy do MATSim (SimWrapper) i do SUMO (sumo-web3d) są webowe lub z webowym frontem. [F]
- Rzadki indeks eventów (`index.npz`) jest mały: 9,5 MB dla Kutna 25%, 37 MB dla Kutna 100% (97 tys. tras, 13,7 mln węzłów). [P: `meta.json` w `output/`]
- WebView2 w pywebview daje na tym komputerze WebGL2 z akceleracją sprzętową (RTX 4070 przez ANGLE/D3D11, Chromium 155). [P]

Co jest złe i trzeba zmienić:
1. **Python w pętli klatek.** Dla Kutna to jeszcze działa (szczyt to ok. 800 pojazdów przy 25% i ok. 3000 przy 100%, [P] z `meta.json`), ale to architektura, która nie skaluje się na Łódź (rząd 50 tys. jednoczesnych, [S]). Sprawdzony wzorzec (deck.gl, Kepler.gl, SimWrapper, lonboard) to **precompute raz → tablice binarne → interpolacja po stronie klienta**. Python jest wtedy eksporterem, nie silnikiem klatek.
2. **Leaflet + canvas 2D nie ma kamery 3D.** Pitch/bearing i budynki 3D wymagają silnika WebGL. Rekomendacja: **MapLibre GL JS (v6.0.0 z 2026-07-22) + deck.gl 9.4 jako nakładka** (ta sama para, którą używa SimWrapper). [F]
3. **Ładowanie strony przez `html=`** to przyczyna limitu ~1,5 MB i całej „łatki” `_push_curves` (patrz wcześniejszy audyt). pywebview umie serwować lokalny katalog po HTTP (`http_server`), więc to znika. [F: źródło pywebview]

Cena zmiany: **średnia, rozłożona na kroki** (sekcja Rekomendacja). Krok 0 (godzina pomiaru) powinien poprzedzić każdą decyzję o dużej przeróbce. Tauri, Electron, Qt, Unity/Unreal/Godot i notebook **nie** są warte zmiany dla tego projektu (uzasadnienie w sekcji 1).

Nieoczekiwane ustalenie: liczby w opisie zadania („kilka tysięcy pojazdów jednocześnie dla 25%”) są ok. 4× za duże. Szczyt dla Kutna 25% to 798, dla 100% to 2991 [P]. Problemem skali nie jest Kutno, tylko Łódź i **pamięć na całodobowe trajektorie** (sekcja 3).

---

## 1. Czy „lokalna strona w oknie” to dobry wybór?

**Tak, to powszechna praktyka.** Różne warianty tej samej idei:

| Wariant | Co to jest | Uwagi |
|---|---|---|
| Przeglądarka + lokalny serwer | `python -m viz serve`, otwiera domyślną przeglądarkę | Najprostsza dystrybucja, niezależna od systemu. SUMO-web3d tak działa: `pip install sumo-web3d`, serwer na localhost:5000 [F] |
| pywebview | okno natywne z systemowym silnikiem | Obecny wybór. Wersja 6.2.1, 2026-04-15 [F]. Na Windows to WebView2 (Chromium), na macOS WKWebView, na Linuksie WebKitGTK/Qt [F/W] |
| Tauri | Rust + system webview | Aktualna linia 2.x (tauri-cli 2.12.4, 2026-10-21) [F]. Ten sam silnik WebView2/WebKitGTK, co pywebview, więc nie daje lepszego WebGL, a dokłada Rust i sidecar Pythona |
| Electron | wbudowany Chromium | [?] wiedza własna: ten sam Chromium na każdym systemie (WebGL przewidywalny), cena to ~150 MB paczki. Nie weryfikowałem |
| Czysto statyczna aplikacja | strona hostowana, dane z pliku lokalnego | Tak działa SimWrapper: „single page application”, przegląda lokalne foldery w przeglądarce [F: Charlton i Sana 2022] |

**Znana pułapka webowych okien: WebGL na Linuksie.** Dokumentacja Tauri ostrzega, że WebKitGTK potrafi po cichu spaść na wolną ścieżkę dla WebGL/canvas (zwłaszcza z NVIDIA), kontekst WebGL2 się tworzy, a renderer jest zamaskowany, więc front nie wykryje problemu; zaleca fallback bez WebGL na Linuksie. [F: v2.tauri.app/develop/debug/linux-graphics, dostęp 2026-10-22] Wniosek [W]: wersja „nie tylko Windows” jest bezpieczna, jeśli ostatecznym frontendem jest **zwykła przeglądarka (Chrome/Edge/Firefox)**, a pywebview jest opcjonalną otoczką tylko na Windows.

**Alternatywy.** (Dla wszystkich poniżej: ocena z wiedzy własnej [?], poza wskazanymi faktami; nie testowałem ich.)

| Alternatywa | Ocena dla tego projektu |
|---|---|
| QGIS Temporal Controller + 3D | Dobre do jednorazowych klipów, nie do odtwarzacza 10^4 agentów na żywo; QGIS 3D nie jest zbudowany pod animowane punkty w skali. Zostaje jako narzędzie kontrolne (projekt ma już MCP QGIS). |
| Qt/PySide (QtQuick3D, QOpenGLWidget) | Pełna kontrola i sensowna wydajność, ale własny silnik mapy (kafelki, projekcje, kamera, budynki) trzeba napisać. Koszt dla jednego programisty zbyt duży. |
| Godot/Unity/Unreal | Świetne 3D i kamera, słaba integracja z GIS (EPSG:2180, kafelki OSM, budynki). Ciężka dystrybucja, własny pipeline danych. Sensowne dopiero przy produkcie „digital twin dla miasta”. |
| Rust + wgpu/egui, Dear ImGui | Najwyższa wydajność, najwyższy koszt. Nie dla jednego analityka w Pythonie. |
| vispy, pyglet, arcade | Szybkie punkty w GPU z Pythona, ale bez map, kafelków i budynków; dużo ręcznej roboty. |
| Notebook (Jupyter + lonboard/kepler.gl) | Dobre do eksploracji. lonboard: 3 mln punktów w 2,5 s, bo trzyma dane binarne od Pythona do GPU (GeoArrow + GeoParquet + deck.gl) [F: Development Seed]. Nie ma w źródłach nic o TripsLayer w lonboard. Brak „odtwarzacza dla ludzi spoza projektu”. |
| Aplikacja czysto statyczna (bez Pythona w pętli) | **To jest docelowy kształt, patrz sekcja 3 i rekomendacja.** |

**Ocena kryteriów** (skala: dobrze / średnio / słabo):

| Kryterium | Webowa (MapLibre+deck.gl) | Qt/PySide | Silnik gier | Rust+wgpu |
|---|---|---|---|---|
| 10^4–10^5 punktów | dobrze | dobrze | dobrze | dobrze |
| 10^6 punktów | średnio (zależy od GPU) | średnio | dobrze | dobrze |
| 3D, kamera | dobrze | średnio (praca własna) | dobrze | średnio |
| Koszt dla 1 osoby | **mały** | duży | duży | bardzo duży |
| Dystrybucja | **bardzo dobra** (URL/przeglądarka) | średnio | słabo | średnio |
| Nie tylko Windows | **tak** | tak | tak | tak |

(Wartości to moje wnioski [W].)

---

## 2. Jak robią to inni?

| Projekt | Stack (źródło) | Skąd pozycje | Skala / agenci | Licencja |
|---|---|---|---|---|
| **Via (Simunto)** | Aplikacja desktopowa na Windows, macOS, Linux; wtyczki PT, emisje, licznikowe; zapis filmów [F: simunto.com/via] | Z `events.xml` wczytywanych do wersji z warstwą „Vehicles”: „Load Data” wyciąga pozycje z eventów [F: matsim.org/install] | „Optimized for large scenarios” [F]. Darmowa wersja ogranicza liczbę agentów, jedno źródło trzecie podaje 500 pojazdów [F, niepewne] | Zamknięte, komercyjne. Cennik: nie znalazłem [?] |
| **OTFVis** | Java, OpenGL2 (Swing bez OpenGL, uboższy) [F: changelog MATSim 0.6.0, 2014], dołączony do MATSim | Na żywo z symulacji albo z pliku | Oficjalne narzędzie MATSim, wymaga instalacji i wiedzy technicznej [F: Charlton i Laudan 2020] | GPL (część MATSim) [?] |
| **SimWrapper** | Vue SPA, TypeScript, deck.gl 9.2.9, maplibre-gl 5.x, three 0.127, @flowmap.gl, duckdb-wasm, pmtiles [F: package.json] | Statyczna strona czyta pliki z lokalnego folderu lub z chmury; w 2025 dodano „event viewer animations” [F: MUM25 paper 22] | Szczegółów skali animacji nie znalazłem [?] | GPL-3.0 [F] |
| **SUMO: sumo-gui** | C++, 3D przez OpenSceneGraph jako opcja, „experimental”, problemy z wydajnością przy wielu pojazdach [F: sumo.dlr.de/docs/sumo-gui] | Z symulacji lub FCD | Lokalna aplikacja Linux/Windows [F] | EPL-2.0 (SUMO) [F przez sumo-web3d] |
| **sumo-web3d (Sidewalk Labs)** | Python + TypeScript, przeglądarka, 3D drogi, pojazdy, ludzie, budynki; TraCI na żywo [F] | TraCI (strumień ze SUMO) | Ostatni push 2023-01-25 (mirror) [F, możliwe nieaktualne] | EPL-2.0 [F] |
| **sumo3Dviz (ETH)** | Pipeline renderujący wideo z wyników SUMO [F] | Z wyjścia SUMO | Offline, nie interaktywny | [?] |
| **Kepler.gl** | deck.gl; Trip layer wymaga GeoJSON LineString z czasem jako 4. współrzędną; limit uploadu ~250 MB w Chrome, więcej po URL [F: docs.kepler.gl] | Dane w całości wczytane do przeglądarki | Demo ~1000 / 3700 / 9000 tras; autor ostrzega przed małymi GPU [F: community demo] | MIT [?] |
| **deck.gl TripsLayer** | WebGL (od 9.4 oficjalny port wszystkich warstw na WebGPU, v9.4.0 2026-09-05) [F: GitHub releases] | `getPath` + `getTimestamps`, znaczniki czasu float32 (trzeba odjąć epokę); to ślady, nie punkty bieżącej pozycji [F: deck.gl docs] | ScatterplotLayer płynnie do ok. 1 mln elementów na MacBooku Pro z 2015, 10–20 FPS przy 10 mln [F: deck.gl performance, uwaga: stary sprzęt] | MIT [?] |
| **lonboard** | deck.gl + GeoArrow + GeoParquet + anywidget [F] | Arrow binarnie z Pythona do GPU | 3 mln punktów w 2,5 s [F] | MIT [?] |
| **CesiumJS** | WebGL, 3D globus; aktualna wersja 1.146 (2026-10-01) [F: GitHub] | Entities/Primitives | Dokumentacja: lepiej mało dużych kolekcji; brak publicznego benchmarku 100 tys. punktów [F: brak] | Apache-2.0 [?] |
| **A/B Street** | Rust; „as of 2025 turned into several other projects” [F: ecosyste.ms] | Własna symulacja | Nie weryfikowałem wgpu/egui/WASM [?] | Apache-2.0 [F] |
| **MovingPandas** | Python, analiza trajektorii (Matplotlib, Folium, GeoViews) [F] | Z GPS/CSV | Analiza, nie odtwarzacz | [?] |
| **Flowmap.gl** | Warstwa deck.gl dla przepływów O-D [F] | Agregaty O-D | Nie agentowa | [?] |
| TraVis (DLR) | Webowa aplikacja do analizy modelu TAPAS, „internal use only” [F: GitHub] | — | — | — |
| UrbanSim, Eqasim, CityFlow, Unreal/Unity digital twins | **nie zbadane** | — | — | — |

**Powtarzające się wzorce** [W, oparte na powyższych faktach]:
1. Wszystkie nowoczesne narzędzia do eksploracji w skali są **webowe, na WebGL** (deck.gl / three / Cesium), nie na Canvas 2D.
2. **Dane trafiają do przeglądarki raz, w formie binarnej/kolumnowej** (GeoArrow, GeoParquet, GeoJSON z czasem, własny format), a ruch w czasie to funkcja czasu po stronie klienta (`currentTime`), nie wywołanie serwera na klatkę. Wyjątek to wizualizacje „na żywo” (sumo-web3d przez TraCI, OTFVis), bo symulacja jeszcze trwa.
3. **Rozdział „przygotuj dane” od „pokaż”.** SimWrapper czyta wyniki z folderu; Via ładuje pliki eventów; lonboard ładuje Arrow.
4. Skala powyżej kilkudziesięciu tysięcy agentów rozwiązywana jest **zakresem czasu i LOD**, nie siłą: użytkownik widzi próbkę lub okno.
5. Licencje otwarte (MIT/EPL/GPL), z wyjątkiem Via. Kod GPL-3.0 SimWrappera można czytać jako wzorzec, ale kopiowanie go ogranicza licencję projektu (decyzja dla właściciela).

---

## 3. Czy Python w pętli klatek to wąskie gardło?

**Dziś: jeszcze nie krytyczne, ale nie skaluje się.** Liczby z projektu [P]:

| | Kutno 25% | Kutno 100% |
|---|---|---|
| tras (`n_tracks`) | 24 304 | 97 210 |
| węzłów trajektorii (`n_knots`) | 3,40 mln | 13,73 mln |
| szczyt jednoczesnych pojazdów | 798 | 2991 |
| szczyt w oknie 6–9 | 728 | 2843 |
| plik `index.npz` | 9,5 MB | 37,3 MB |
| czas budowy indeksu | 19,5 s | 81,7 s |
| plik eventów | 40,7 MB | 172,3 MB |

(Plik 100%: `output/gha_100pct_10it/.../viz/meta.json`, `FORMAT` 1. Plik 25%: `output/g5r7b_25pct_s4711/viz/meta.json`, `FORMAT` 3. Formaty są różne, więc porównuję tylko rząd wielkości.)

**Co trzeba przesłać na klatkę przy dzisiejszym modelu** [S]: jeden punkt = x, y (float32), id (u32), klasa (u8) ≈ 13–16 B binarnie. Kutno 100%: 3000 × 16 B ≈ **48 KB/klatkę**, przy 30 klatkach/s ≈ 1,4 MB/s. Przez JSON (pywebview serializuje wynik funkcji `js_api` do JSON, [?] wiedza własna, dokumentacja nic nie mówi o wydajności) można liczyć 3–4× więcej tekstu. To jeszcze przechodzi. **Wąskie gardło to nie przepustowość, tylko opóźnienie wywołania, serializacja i blokada GIL w Pythonie przy wielu wątkach `js_api`** (potwierdza je audyt kodu: `_fr`, `busy`, `hold` w `player.py`). Nie mierzyłem tego, zalecam pomiar (krok 0).

**Łódź (szacunek liniowy z Kutna, rząd wielkości)** [S]: Kutno ma 42 255 mieszkańców (CLAUDE.md), Łódź ok. 650–670 tys. [?] (nie sprawdzałem), czyli ok. 15,5×. Stąd:
- tras ≈ 1,5 mln (100%), węzłów ≈ 210 mln, szczyt jednoczesnych ≈ 46 tys.
- Surowe trajektorie (czas f32 + x f32 + y f32 = 12 B/węzeł): **≈ 2,5 GB**. Gdyby trzymać tylko (czas, id segmentu) po 8 B: ≈ 1,7 GB.
- Jedna alokacja w Chrome jest ograniczona do 1 GB (deck.gl performance docs [F]), więc całodobowa tablica musi być **pocięta na porcje** (np. po 15 min = 96 plików po ok. 18–27 MB) ładowane „w okolicy bieżącego czasu”.
- Klatka: 46 tys. × 16 B ≈ 0,74 MB, przy 30 fps ≈ 22 MB/s. Binarnie to wykonalne, przez pywebview JSON nie. Tu Python w pętli klatek **przestaje wystarczać** (szacunkowo od ok. 10–20 tys. jednoczesnych punktów, do pomiaru).

**Sprawdzone wzorce** [F]:
- **Typed arrays bez obiektów JS**: deck.gl przyjmuje dane jako „non-iterable object with length” i atrybuty jako typed arrays albo bufory luma.gl; to omija generowanie atrybutów na CPU, które dokumentacja nazywa głównym wąskim gardłem. Atrybuty można generować w web workerach i przekazywać jako transferable. [deck.gl performance]
- **Stałe akcesory są dużo tańsze od funkcji.** [ten sam dokument]
- **Interpolacja na GPU**: Uber w ogłoszeniu deck.gl opisuje demo 2 mln punktów i 36 tys. przejazdów taksówek z interpolacją na GPU [F: Uber blog]. Gotowego przykładu „100 tys. pojazdów z interpolacją w shaderze” nie znalazłem; zwykła technika (węzły czasu w atrybutach lub teksturze, czas jako uniform) to wiedza własna [?].
- **Formaty**: GeoArrow/GeoParquet (lonboard), GeoJSON z 4. współrzędną czasu (Kepler), PMTiles (SimWrapper). Własny format binarny jest uzasadniony, jeśli jest prosty i opisany w manifeście (sekcja 5).

**Kluczowa obserwacja** [W]: obecny indeks jest *rzadki po linkach* (czasy wejścia/wyjścia z linku), czyli **geometria sieci + czasy**, nie gęste próbkowanie pozycji. Dzięki temu jest 37 MB dla Kutna 100%, a nie ~165 MB surowych pozycji (13,7 mln × 12 B). To jest dobra konstrukcja, którą warto **wysłać klientowi tak, jak jest** (plus sieć ~370 KB), i liczyć pozycję w JS lub shaderze. Python wtedy nie jest potrzebny w pętli.

**Kiedy rzadki indeks w Pythonie przestaje wystarczać** [S/W]:
- Klatka z Pythona: do ok. 5–10 tys. punktów komfortowo, powyżej wymagane przeniesienie interpolacji na klienta.
- Indeks w całości w pamięci procesu: Kutno 100% = 37 MB (OK); Łódź 100% ≈ 0,6–1 GB w indeksie zagęszczonym tak jak dziś (37 MB × 15,5 ≈ 580 MB, [S]) plus kopie w RAM — ostrożnie przy 16 GB, patrz limit `RAM_BUDGET = 1 GiB` w audycie kodu.

---

## 4. Budynki 3D i kamera

**Leaflet + canvas 2D nie rozwinie się do pitch/bearing.** Leaflet nie ma obrotu ani nachylenia kamery w rdzeniu [?: wiedza własna]. Potrzebny silnik WebGL.

**Porównanie silników:**

| Silnik | Budynki 3D | Kamera | Animowane punkty | Waga / uwagi |
|---|---|---|---|---|
| **MapLibre GL JS 6.0.0** (2026-07-22) | `fill-extrusion` z wysokością i bazą w metrach [F: style spec]. Ujemne wysokości nieobsługiwane w JS [F] | pitch, bearing, `easeTo`, `jumpTo`, `followed` przez własny kod [?] | przez nakładkę deck.gl (interleaved, współdzielony kontekst WebGL2) [F: deck.gl docs] | **v6: WebGL2 obowiązkowe, tylko ESM (`maplibre-gl.mjs`, brak UMD)** [F: malagis.com]. Trzeba ładować jako `type="module"` i ewentualnie `setWorkerUrl()` |
| **deck.gl 9.4.0** (2026-09-05) | `GeoJsonLayer` z `extruded`, `ScenegraphLayer` dla modeli | Widoki: Map, Orbit, Globe z pitch/bearing (nowe w 9.4) [F: release notes] | Binarne atrybuty, TripsLayer, własne warstwy; do ~1 mln elementów płynnie na starym laptopie [F] | Oficjalnie rekomendowana integracja z MapLibre: `@deck.gl/maplibre` (MapLibre 4.5.1, 5, 6) [F] |
| **CesiumJS 1.146** | Natywne kafelki 3D, terenowe | Bardzo dobra (globus) | Brak publicznego benchmarku 100 tys. punktów [F: brak] | Cięższy; globus nie jest potrzebny dla miasta |
| **three.js** | Pełne 3D, ale wszystko własne | Własna | Najwyższa elastyczność | Brak kafelków i geografii: kosztowne dla jednego programisty |
| **Kepler.gl** | Poprzez deck.gl, GUI do eksploracji | Wbudowana | Trip layer: demo 1–9 tys. tras [F] | Aplikacja, nie biblioteka do osadzenia w kontrolowanym odtwarzaczu |

**Rekomendacja: MapLibre 6 + deck.gl jako `MapLibreOverlay` w trybie interleaved** (to samo, co SimWrapper, który jest na maplibre-gl 5.x + deck.gl 9.2.9 [F: package.json]). Powód: jeden kontekst WebGL2, budynki z `fill-extrusion`, ruchome punkty z deck.gl, kamera pitch/bearing „za darmo”, ekosystem i wzorzec sprawdzony w projekcie MATSim.

**Dane o wysokościach budynków** (pomiar własny [P] na `data/raw/osm/lodzkie-261015.osm.pbf`, zliczanie przez `osmium`; budynki z `building` ≠ `no/disused/construction/proposed`; **przybliżone bbox, nie granice administracyjne**; Kutno bbox 19,30–19,42 E / 52,19–52,26 N jest szerszy niż gmina miejska; Łódź bbox 19,30–19,65 / 51,68–51,86 obejmuje część sąsiednich gmin):

| | budynków | z tagiem `height` | z tagiem `building:levels` |
|---|---|---|---|
| Kutno (bbox) | 13 421 | 310 (2,3%) | 4 784 (35,6%) |
| Łódź (bbox) | 163 865 | 741 (0,5%) | 44 731 (27,3%) |

Wniosek [W]: **ok. 2/3 budynków nie ma żadnej wysokości w OSM**. Reguła zastępcza: `height` > `building:levels` × 3 m (OSM wiki: 3 m na kondygnację, [F: wiki.openstreetmap.org/wiki/OSM-3D]) > wartość domyślna wg typu `building=*` (np. `house` ≈ 7 m). Domyślne trzeba oznaczyć jako **ZAŁOŻENIE** w UI (zgodnie z regułą projektu „nie udawaj obserwacji”).
Inne źródła wysokości: społeczność OSM robi import pięter z BDOT10k (tylko dla budynków bez wartości), BDOT10k nie zawiera budynków < 40 m², a w Warszawie uzupełniano z EGiB [F: OSM wiki i forum]. Overture Maps (release 2026-06-17, schema 1.17.0) ma budynki z wysokością „as available”; pokrycie w Polsce nie sprawdzone [F/?]. LoD1/CityGML z GUGiK: **nie zweryfikowano** [?].

**WebView2 i WebGL: co sprawdziłem** [P] (skrypt w katalogu tymczasowym, `pywebview` z `.venv` projektu, okno ukryte, `gui="edgechromium"`):
- WebGL2: **dostępne**, renderer `ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 … Direct3D11)`, czyli sprzętowo (nie SwiftShader). `MAX_TEXTURE_SIZE` = 16384, `MAX_VERTEX_ATTRIBS` = 16.
- User-Agent: `Chrome/155.0.0.0 Edg/155.0.0.0` (Chromium 155).
- `navigator.gpu` (WebGPU) = **brak** w tym kontekście ładowania (`html=`); przyczyna nieznana (może niebezpieczny origin dla strony z `html=`, może konfiguracja) [?]. Dla deck.gl 9.4 WebGPU jest opcjonalne, WebGL2 wystarcza.
- **Nie testowałem** zintegrowanej grafiki (iGPU) ani drugiego komputera. Ten wynik dowodzi tylko, że na tej maszynie WebView2 używa GPU.

**Znane problemy i niewiadome** [F/?]:
- Zasada ogólna: gdy GPU jest na czarnej liście lub sterownik stary, Chromium schodzi na renderer programowy (SwiftShader), a `chrome://gpu` (u nas `edge://gpu`) pokazuje „Software only” [F: poradniki PlayCanvas/Cinevva]. Z tej ogólnej zasady wynika ryzyko dla MapLibre 6, bo **WebGL1 usunięto i nie ma wersji zapasowej** [F]. Aplikacja powinna wykrywać brak WebGL2 i pokazywać komunikat, a nie biały ekran.
- WebView2 na maszynach bez GPU/VM/RDP: brak źródła specyficznego dla WebView2, więc nie twierdzę nic ponad ogólną zasadę. Flagi (`--ignore-gpu-blocklist`, `--disable-gpu`) są ustawiane przez `AdditionalBrowserArguments` [? z wiedzy własnej, w wyszukiwaniu nie potwierdzone].
- **Nie znalazłem benchmarku 50–200 tys. animowanych punktów + budynki 3D na iGPU 30+ FPS** w żadnym źródle. Jedyne liczby to deck.gl ~1 mln punktów ScatterplotLayer na MacBooku Pro 2015 z dwiema kartami [F: stary sprzęt, warstwa statyczna]. **Cel 30+ FPS na iGPU trzeba zmierzyć na własnym prototypie** (to krok 0/2).

---

## 5. Dane i protokół

**Jak się to modeluje** [W + F, część wiedza własna]. Trzy reprezentacje:
1. **Trajektorie** (osoba/pojazd → ciąg (t, x, y) lub (t, link)). Dobre do odtwarzania; kompaktowe w wersji rzadkiej (czasy wejścia na link). Tak robi TripsLayer (`getPath` + `getTimestamps`) i Kepler [F].
2. **Zdarzenia** (event log). Wierne źródłu (MATSim), dobre do analizy, złe do wyświetlania wprost (trzeba złożyć klatkę).
3. **Stan w klatce** (snapshot na każdą sekundę). Najprostszy dla klienta, ale ogromny: rośnie z czasem × agentami. To dzisiejszy model „Python odsyła klatkę”.

Rekomendacja [W]: **wyeksportować trajektorie rzadkie + tabelę atrybutów** i obliczać klatkę po stronie klienta; eventy zostają w źródle MATSim.

**Modelowanie rzeczy, które właściciel chce dodać** [W]:
- **Atrybuty osób**: osobna tabela `persons` (kolumny: person_id, subpopulation, wiek, płeć, itd.) jako Parquet/Arrow lub JSON dla małych skal; trasy mają `person_id` jawnie (event `vehicle enters traffic` ma atrybut `person`, wg audytu kodu). Filtry działają jako bitmaska/indeks klasy po stronie klienta.
- **Tryby**: pole `mode` w trasie (car, ride, bike, walk, pt). **Pieszo i rower teleportowany nie mają eventów po linkach** (audyt kodu), więc dla nich trasa to interpolacja liniowa między aktywnościami (czas odjazdu/przyjazdu z eventów `departure`/`arrival`), co trzeba oznaczyć jako „uproszczone”.
- **PT**: dwie warstwy: (a) pojazdy PT jako zwykłe trasy (eventy `TransitDriverStarts` i ruch po linkach), (b) pasażerowie jako stan w pojeździe (`PersonEntersVehicle`), nie osobne trajektorie; linie i rozkłady jako osobny plik (GTFS lub schedule MATSim). Dla widoku wystarcza: linie jako geometrie, pojazdy jako trasy.
- **Wersjonowanie**: `manifest.json` z `format_version`, `crs`, `origin`, `time_range`, listą porcji, sha256 źródeł, listą kolumn atrybutów. Klient odmawia pliku o nieznanej wersji większej (główną) i toleruje nowsze pola w tej samej wersji. Dzisiejszy `FORMAT` w `meta.json` i klucz cache sha256 to dobra baza.

**Czy jeden otwarty format i rozdział „eksport” od „przeglądarki”?** **Tak, to rekomendacja** [W], uzasadniona wzorcem z sekcji 2 (SimWrapper, lonboard, Via czytają pliki; nie wywołują silnika). Konkret:
- **Własny prosty binarny + `manifest.json`** (typed arrays w porcjach czasu) dla trajektorii: zero zależności w kliencie, ładowanie przez `fetch(...).arrayBuffer()`, wprost do atrybutów deck.gl.
- **Parquet/GeoParquet** dla tabel atrybutów, sieci i budynków (czytelny w QGIS, DuckDB, pandas, lonboard). Klient wczyta je przez DuckDB-WASM (SimWrapper ma ją w zależnościach [F]) albo wystarczy JSON dla małych tabel.
- **PMTiles** (SimWrapper go używa [F]) dla budynków i podkładu: jeden plik, bez serwera kafelków.
- Nie wymieniam GeoArrow/Arrow IPC jako koniecznego: dodaje zależność w kliencie, a zysk jest mały przy tym rozmiarze. Jeśli kiedyś pojawi się lonboard/Jupyter, eksport Arrow dodaje się jako drugi format z tego samego eksportera.
- `g6_bake.py` (Blender) powinien czytać ten sam eksport albo zostać oznaczony jako przestarzały (zgodnie z audytem, dwa źródła prawdy).

---

## 6. Nazwa

Nazwa robocza: **easy-matanimation** (decyzja właściciela, 2026-10-22). Poprzednia lista polskich i angielskich propozycji została wycofana na prośbę właściciela.

Sprawdzone `curl` (2026-10-22) na PyPI i npm: `easy-matanimation`, `matanimation`, `easy_matanimation` zwracają 404, czyli takich pakietów nie ma. Kolizji na GitHubie i znaków towarowych nie sprawdzałem. Obecna nazwa „easy-matviz” kolidowała z biblioteką wykresów `matviz` i narzędziem MatViz (Kitware) [F: matviz.readthedocs.io, public.kitware.com/Wiki/MatViz]. Terminologia branżowa tej klasy narzędzi: „visualizer” (OTFVis, SimWrapper), „agent animation”, „event viewer animation” (SimWrapper) [F]; nazwa z „animation” jest zgodna z tym słownictwem.

---


## Tabela porównawcza opcji

Skala: ++ bardzo dobrze, + dobrze, 0 średnio, − słabo. Oceny to moje wnioski [W], oparte na faktach z sekcji 1–4; nie testowałem żadnej opcji poza obecną.

| Opcja | Wydajność 10^4–10^5 | 3D / kamera | Koszt rozwoju (1 osoba) | Przenośność | Licencja | Ryzyko |
|---|---|---|---|---|---|---|
| **A. Obecny stack** (pywebview + Leaflet + canvas 2D + Python w pętli) | + (Kutno), − (Łódź) | − (brak 3D) | ++ (już jest) | − (Windows) | BSD (Leaflet) [?] | Rośnie: kolejne tryby wiążą się z Pythonem w pętli |
| **B. pywebview/przeglądarka + MapLibre 6 + deck.gl, dane binarne, klient liczy** (rekomendowana) | ++ | ++ | 0 (jednorazowa przeróbka, potem tanio) | ++ (przeglądarka; pywebview opcjonalnie) | BSD/MIT [?] | Niskie. MapLibre 6 wymaga WebGL2; wyświetlić komunikat |
| **C. B, ale w Tauri** | ++ | ++ | − (Rust + sidecar) | + | MIT/Apache [?] | Średnie: dodatkowy język; ten sam silnik WebView2, bez zysku w WebGL |
| **D. B, ale w Electronie** | ++ | ++ | 0 | + (~150 MB paczki, [?]) | MIT [?] | Niskie; cięższa dystrybucja |
| **E. Czysto statyczna aplikacja (hostowana)** | ++ | ++ | 0 | ++ | j.w. | Niskie, ale dostęp do dużych plików lokalnych wymaga File System Access API (Chromium) [?] lub małego serwera |
| **F. Notebook (lonboard/kepler.gl)** | + | + | ++ (łatwe) | + | MIT [?] | Dla analityka tak, dla osób spoza projektu nie |
| **G. Qt/PySide z własnym silnikiem** | + | 0 | − | + | LGPL/GPL | Wysokie (silnik mapy własny) |
| **H. Godot/Unity/Unreal** | ++ | ++ | − | 0 | różne | Wysokie (GIS, dystrybucja) |
| **I. Rust + wgpu/egui** | ++ | 0 | − − | + | MIT/Apache | Bardzo wysokie |
| **J. Via (zakup)** | ? | + | ++ (zero) | ++ | Komercyjna | Zamknięte, ograniczenie agentów w darmowej wersji [F, niepewne]; cennik nie znaleziony |

---

## Rekomendacja i kolejność kroków

Cel: dojść do **B** małymi krokami, z których każdy działa sam. Szacunek pracy: S = godziny do 1 dnia, M = kilka dni, L = ponad tydzień (przy jednym programiście; szacunki własne).

0. **Pomiar (S).** Zmierzyć dziś: (a) liczba klatek/s i opóźnienie wywołania `frame()` dla Kutna 100%; (b) ten sam test WebGL2/`edge://gpu` na laptopie z iGPU i na drugim komputerze; (c) mały prototyp deck.gl `ScatterplotLayer` z 50 tys. i 200 tys. punktów w `type="module"` stronie z MapLibre 6 i fill-extrusion na wszystkich ~13,4 tys. budynkach Kutna, FPS na iGPU. To jest jedyny sposób na uzyskanie liczb dla celu „30+ FPS na iGPU”, bo benchmarków nie znalazłem.
1. **Ładowanie strony po HTTP zamiast `html=` (S–M).** Już opisane w audycie; usuwa limit 1,5 MB i `_push_curves`. Niezależne od reszty.
2. **Nowy eksport „v2” (M).** `manifest.json` + porcje binarne trajektorii rzadkich (po 15 min) + `persons.parquet` (lub JSON) + sieć. Wprowadza `person_id` i klasyfikator trybu (odblokowuje tryby i PT), origin z bbox sieci w `meta`. Zmienia `FORMAT`; zrobić razem z krokiem 3.
3. **Klient liczy klatkę (M).** JS interpoluje pozycję z porcji (najpierw na CPU: 3 tys. punktów to nic), a stan (czas, klasy, zaznaczenie) jest tylko w kliencie. Python przestaje być w pętli. Interpolację na GPU (własna warstwa deck.gl z czasem jako uniform) dodać dopiero przy skali Łodzi (L).
4. **Wymiana silnika mapy na MapLibre 6 + deck.gl (M).** Najpierw to samo, co dziś (punkty + klasy + śledzenie), potem **pitch/bearing** (S) i **budynki** (S–M): wygenerować z PBF GeoJSON/PMTiles z `height` wg reguły z sekcji 4 i oznaczyć wartości domyślne jako założenie.
5. **Nowe tryby i atrybuty osób (M–L).** Pieszo/rower (interpolacja liniowa), ride, PT (pojazdy + linie), filtry po atrybutach.
6. **Dystrybucja (S–M).** Uruchomienie jedną komendą (`uv run`/`pipx`) otwierającą przeglądarkę na serwerze lokalnym; pywebview jako opcjonalne okno na Windows. Wykrywanie braku WebGL2 z czytelnym komunikatem.
7. **Skala Łodzi (L), dopiero gdy będzie potrzebna.** Porcje czasowe + LOD (próbkowanie agentów), interpolacja w shaderze.

**Dlaczego tak:** największa nierównowaga w obecnym stosie to *Python w pętli klatek* i *brak WebGL*. Obie naprawia ten sam ruch (dane binarne do klienta, silnik GL). Reszta (Tauri, Qt, silniki gier) kosztuje więcej, niż daje, bo nie rozwiązuje problemu danych, a dokłada utrzymanie.
**Cena zmiany:** kroki 1–4 to razem rząd **2–3 tygodni pracy** [S, bardzo grubo], z czego przepisanie rysowania z Leaflet na MapLibre+deck.gl jest najmniejsze, a eksport v2 + klient najtrudniejsze. Zysk: kamera 3D, budynki, tryby, Łódź i przeglądarka bez Windows.

---

## Otwarte decyzje dla właściciela (po odpowiedziach z 2026-10-22)

1. **Format wymiany (pytanie 4):** wewnętrzny cache z numerem wersji (propozycja na start) czy publicznie opisany format. Decyzja po kroku 3.
2. **Zakres użycia SimWrappera:** tylko wzorzec do czytania, czy kopiujemy fragmenty (wtedy sprawdzić nagłówki licencji „GPL-3.0 only” vs „or later”).
3. **Wartości `H0` wysokości budynków wg klasy** i amplituda losowości (propozycja ±15%): ZAŁOŻENIA do wpisania w config z wariantami; do wyboru, czy zaczynamy od jednej stałej dla wszystkich.
4. **Test na iGPU:** na jakim komputerze (laptop z samą zintegrowaną grafiką).
5. **Wygaszenie `g6_bake.py`:** zapis w `DECISIONS.md` i `ROADMAP.md` (nie zrobiłem; poza zakresem tej sesji).


---

## Aktualizacja 2026-10-22: decyzje właściciela i pomiary

**Decyzje właściciela (odpowiedzi na pytania z pierwszej wersji raportu):**

| # | Decyzja |
|---|---|
| 1 | Aplikacja **desktopowa w oknie Windows (pywebview)**; przeglądarka opcjonalnie później. |
| 2 | MapLibre 6 + deck.gl: zgoda, brak wymagania obsługi komputerów bez WebGL2. Licencje: niżej. |
| 3 | Licencja repo: **GPL-3.0-or-later**. SimWrapper (GPL-3.0) można więc wykorzystywać. |
| 4 | Wyjaśnienie niżej. |
| 5 | Wysokości budynków: tanio i **preprocessowane** (stała wysokość, gdy brak `levels`, losowość z ziarnem, mnożnik klasy budynku). Schemat niżej. |
| 6 | Cel 30 FPS: **Kutno 100%**. Łódź: **10%** (jak Berlin 1/3/10%), bez 100%. |
| 7 | Nazwa robocza: **easy-matanimation**. Polskie propozycje usunięte (sekcja 6). |
| 8 | `g6_bake.py` (Blender) można **wygasić**: Blender i ta aplikacja robią co innego. |
| 9 | Krótki pomiar zamiast 1 h: zrobiony, wyniki niżej. |

**Licencje składników docelowego stosu** (odczyt z GitHub API / pliku LICENSE, dostęp 2026-10-22):

| Składnik | Licencja | Zgodność z GPL-3.0-or-later |
|---|---|---|
| MapLibre GL JS | BSD-3-Clause (tekst w `LICENSE.txt`; GitHub API pokazuje „NOASSERTION”, bo plik nie jest standardowy) | tak |
| deck.gl | MIT | tak |
| pywebview | BSD-3-Clause | tak |
| Leaflet (obecny) | BSD-2-Clause | tak |
| DuckDB-WASM | MIT | tak |
| PMTiles (implementacja JS) | BSD-3-Clause; specyfikacja domena publiczna/CC0 | tak |
| SimWrapper | GPL-3.0 | tak, jeśli twój kod to GPL-3.0-or-later |

BSD i MIT są licencjami permisywnymi: można je włączyć do projektu GPL, zachowując ich noty autorskie. Odwrotnie nie (kod GPL nie wejdzie do projektu MIT). [W: ogólna wiedza o licencjach, nie porada prawna. Przy kopiowaniu fragmentów SimWrappera sprawdzić w nagłówkach plików, czy to „GPL-3.0 only” czy „or later”.] Praktycznie SimWrapper to Vue/TypeScript, więc bierze się z niego wzorce, nie wkleja 1:1.

**Pytanie 4 po ludzku: „format wymiany, publiczny kontrakt czy wewnętrzny”.** Aplikacja czyta pliki, które ktoś musi wyprodukować z wyniku MATSim (dziś robi to `viz_index.py`). Pytanie: czy te pliki mają być (a) **luźnym wewnętrznym cache**, który można zmieniać bez uprzedzenia i po zmianie kodu przebudować z eventów (tak jak dziś `FORMAT` w `meta.json`), czy (b) **udokumentowanym formatem** z numerem wersji, który inny skrypt, kolega albo Łódź w osobnym repo mogą generować własnym kodem, a aplikacja zawsze go przeczyta. Wariant (b) kosztuje trochę pracy (opis pliku, testy zgodności), ale oddziela „eksport” od „przeglądarki” i pozwala dodawać źródła (np. SUMO) bez zmian w aplikacji. **Propozycja:** start jako (a) z numerem wersji w pliku, opis dopisać, gdy format ustabilizuje się po krokach 3–4. Decyzja po kroku 3.

**Wysokości budynków: schemat taniego preprocessingu** [W, propozycja]. Liczone raz, offline, do pliku; aplikacja tylko czyta `h` i rysuje:
1. `h = height`, jeśli jest; inaczej `h = building:levels × 3 m` (OSM wiki: 3 m na kondygnację, [F]); inaczej `h = H0(klasa)`, gdzie klasa wynika z `building=*` (np. `house`/`detached` niskie, `apartments`/`residential` wyższe, `commercial`/`office`/`retail` wyższe, `industrial`/`warehouse` osobna wartość, `garage`/`shed` niskie). Wartości `H0` to **ZAŁOŻENIE** w configu z wariantami, nie „typowe” liczby wpisane w kod.
2. Losowość: `h *= 1 + u`, gdzie `u` pochodzi z deterministycznego hasha id budynku (np. ±15%), nie z `random()`, więc wynik jest za każdym razem ten sam.
3. Flaga `h_source` (`tag` / `levels` / `default`) w danych, żeby w UI odróżnić pomiar od założenia.
Koszt klatki: budynki to jedna statyczna warstwa; to dokładnie to, co mierzę w teście C niżej.

**Pomiary wykonane dziś** (skrypty w katalogu tymczasowym sesji; plik eventów 100% skopiowany do katalogu tymczasowego, `output/` nietknięte):

*A. Silnik klatek w Pythonie, Kutno 100%* (`pipeline/viz_engine.frame`; indeks z 97 210 tras i 13,73 mln węzłów zbudowany od nowa w katalogu tymczasowym, bo indeks z GitHub Actions ma starszy `FORMAT 1`; budowa 80,5 s):

| | wartość |
|---|---|
| indeks w RAM po wczytaniu | **316 MB** (na dysku 37 MB) |
| klatka w szczycie 6–9 (2807 pojazdów), 200 powtórzeń | mediana **13,8 ms**, p95 19,3 ms, max 35,0 ms |
| klatka w nocy (207 pojazdów) | mediana 1,0 ms, p95 1,8 ms |
| rozmiar klatki w JSON (`xy` + `cls`) | **108 KB**; binarnie (xy f32 + klasa) 25,6 KB |
| serializacja klatki do JSON | 2,7 ms |

Czas silnika rośnie mniej więcej liniowo z liczbą pojazdów (≈ 4,9 µs/pojazd). To sam silnik, bez mostu i rysowania. Szacunek [S]: Łódź 10% (≈ 4,6 tys. jednoczesnych w szczycie, skalowanie liniowe Kutno 100% × 15,5 × 0,1) → ≈ 23 ms na klatkę w samym silniku, czyli prawie cały budżet 33 ms przy 30 FPS; indeks w RAM ≈ 0,5 GB.

*B. Most pywebview → JS* (funkcja `js_api` zwraca gotową klatkę 2800 punktów, 48 KB JSON, 60 wywołań sekwencyjnych z JS): mediana **3,3 ms**, p95 3,7 ms. Most jest tani. Razem z silnikiem (13,8 ms) to ≈ 17 ms na klatkę dla Kutna 100% w szczycie, bez rysowania i przy wywołaniach jedno po drugim. **Dla Kutna Python w pętli mieści się w 30 FPS, ale zjada większość budżetu, a na Łódź 10% już nie wystarcza.**

*C. Render deck.gl 9.4.0 w WebView2 (pywebview, `http_server=True`)*: widok z pitch 55°, punkty ze stałego typed array aktualizowanego w JS co klatkę, budynki jako `SolidPolygonLayer` z `extruded` (losowe kwadraty), klatka mierzona przez `onAfterRender` po `gl.finish()`, 4 s na konfigurację:

| punkty | budynki | FPS | mediana klatki |
|---|---|---|---|
| 3 000 | 0 | 170 | 5,9 ms |
| 3 000 | 13 400 | 164 | 5,9 ms |
| 50 000 | 13 400 | 170 | 5,9 ms |
| 200 000 | 13 400 | 170 | 5,9 ms |
| 200 000 | 164 000 | 170 | 5,9 ms |

Wszystkie wyniki leżą na **limicie odświeżania monitora (~170 Hz)**. Dowodzi to tylko, że na RTX 4070 ten ładunek mieści się w budżecie klatki; **nie mówi, ile jest zapasu ani jak zachowa się zintegrowana grafika**. Ograniczenia: GPU dyskretne; nie potwierdziłem zrzutem ekranu, że wszystkie warstwy się narysowały; budynki to proste prostokąty; brak podkładu MapLibre; interpolacja zastąpiona dodawaniem (200 tys. punktów = 0,3 ms po stronie JS). Wniosek ostrożny [W]: 3D + 200 tys. punktów + 164 tys. budynków nie jest dla tego GPU trudne; test na iGPU zostaje do zrobienia przy prototypie.

**Wniosek z pomiarów** [W]: dla celu 30 FPS na Kutnie 100% obecna architektura technicznie się mieści, ale (1) Python zjada ~50% budżetu klatki i nie skaluje się do Łodzi 10%, (2) po stronie przeglądarki rysowanie nie jest wąskim gardłem (na tym GPU). Przeniesienie interpolacji do JS usuwa oba problemy.

**Zmieniony plan kroków** (jeden po drugim, nie wszystko naraz):
1. ✅ Pomiar bazowy (ten raport).
2. Ładowanie strony po HTTP (`http_server=True` działa, test C). [S–M]
3. Eksport v2: porcje czasowe trajektorii rzadkich + `person_id`/tryb. [M]
4. Klient liczy klatkę (JS, CPU); Python tylko eksport. [M]
5. Leaflet → MapLibre 6 + deck.gl, kamera pitch/bearing. [M]
6. Budynki z preprocessingu wg schematu wyżej. [S–M]
7. Nowe tryby, PT, atrybuty osób. [M–L]
8. Wygaszenie `g6_bake.py`; test na iGPU; przeglądarka opcjonalnie. [S]

---


## Ograniczenia tego badania

- Nie czytałem całego kodu aplikacji, tylko `meta.json` dwóch runów, fragmenty `player.py`/`shell.html` i wcześniejszy audyt.
- Nie mierzyłem wydajności bieżącej aplikacji ani żadnej alternatywy; nie ma publicznego benchmarku „50–200 tys. animowanych punktów + budynki na iGPU” w źródłach, które znalazłem.
- Nie zbadałem: UrbanSim, Eqasim, CityFlow, Unreal/Unity digital twins, GUGiK LoD1, kosztu Via. Wszystko oznaczone [?] to wiedza własna, nie weryfikowana.
- Liczba mieszkańców Łodzi (ok. 650–670 tys.) i skalowanie liniowe do Łodzi to szacunek.
- Zliczanie budynków jest przybliżone (bbox, nie granice gmin; wielokąty liczone po pierwszym punkcie obrysu).
- Wynik WebGL2 dotyczy jednego komputera z kartą dyskretną.

## Źródła (dostęp 2026-10-22)

- MapLibre GL JS v6.0.0 (2026-07-22, WebGL2 obowiązkowe, tylko ESM): https://geo.malagis.com/maplibre-gl-js-v6-mandatory-webgl-and-esm-only.html ; https://maplibre.org/news/2026-09-02-maplibre-newsletter-august-2026/
- MapLibre style spec (fill-extrusion): https://maplibre.org/maplibre-style-spec/layers/#fill-extrusion
- deck.gl release v9.4.0 (2026-09-05): https://api.github.com/repos/visgl/deck.gl/releases/latest
- deck.gl performance (1 mln, 10 mln, binarne atrybuty, limit 1 GB): https://deck.gl/docs/developer-guide/performance
- deck.gl TripsLayer: https://deck.gl/docs/api-reference/geo-layers/trips-layer
- deck.gl i MapLibre (interleaved, `@deck.gl/maplibre`): https://deck.gl/docs/developer-guide/base-maps/using-with-maplibre ; https://deck.gl/docs/api-reference/maplibre/overview
- deck.gl custom layers: https://deck.gl/docs/developer-guide/custom-layers/primitive-layers ; Uber (2M punktów, 36 tys. przejazdów): https://www.uber.com/en-JM/blog/visualizing-data-sets-deck-gl-framework
- pywebview release 6.2.1: https://api.github.com/repos/r0x0r/pywebview/releases/latest ; źródło `start()`/`http_server`: https://raw.githubusercontent.com/r0x0r/pywebview/master/webview/__init__.py ; architektura: https://pywebview.flowrl.com/guide/architecture.html
- Tauri (tauri-cli 2.12.4, 2026-10-21): https://api.github.com/repos/tauri-apps/tauri/releases/latest ; Linux WebGL: https://v2.tauri.app/develop/debug/linux-graphics/
- CesiumJS 1.146: https://api.github.com/repos/CesiumGS/cesium/releases/latest ; PointPrimitiveCollection: https://cesium.com/downloads/cesiumjs/releases/1.133/Build/Documentation/PointPrimitiveCollection.html
- SimWrapper package.json: https://raw.githubusercontent.com/simwrapper/simwrapper/master/package.json ; repo: https://github.com/simwrapper/simwrapper ; Charlton i Sana 2022: https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2022/22-21/CharltonSana2022SimWrapper.pdf ; Charlton i Laudan 2020: https://svn.vsp.tu-berlin.de/repos/public-svn/publications/vspwp/2020/20-08/CharltonLaudan2020WebBasedVisualization-accepted.pdf ; MUM25: https://matsim.org/conferences/mum2025/abstracts/MUM25_paper_22.pdf
- Via: https://www.simunto.com/via/ ; instalacja MATSim: https://matsim.org/install/
- OTFVis: https://matsim.org/apidocs/otfvis/12.0/ ; changelog: https://mac.softpedia.com/progChangelog/MATSim-Changelog-55750.html
- SUMO: https://sumo.dlr.de/docs/sumo-gui.html ; sumo-web3d: https://gittrend.io/repo/sidewalklabs/sumo-web3d
- Kepler.gl: https://docs.kepler.gl/docs/user-guides/c-types-of-layers/k-trip ; https://docs.kepler.gl/docs/user-guides/b-kepler-gl-workflow/a-add-data-to-the-map
- lonboard: https://developmentseed.org/lonboard/latest/performance/ ; https://developmentseed.org/lonboard/latest/how-it-works/internals/
- OSM budynki: https://wiki.openstreetmap.org/wiki/OSM-3D ; https://wiki.openstreetmap.org/wiki/BDOT10k_buildings_import ; https://community-cdn.openstreetmap.org/t/automatyczny-import-pieter-budynkow-z-bdot10k/119656
- Overture 2026-06-17: https://docs.overturemaps.org/blog/2026/06/17/release-notes/
- MovingPandas, Flowmap.gl, TraVis (DLR): https://anitagraser.com/movingpandas/ ; https://www.npmjs.com/package/flowmap.gl ; https://github.com/DLR-VF/TraVis
- Kolizje nazwy „matviz”: https://matviz.readthedocs.io ; https://public.kitware.com/Wiki/MatViz
- Dostępność nazw: bezpośrednie zapytania HTTP do `pypi.org/pypi/<nazwa>/json` i `registry.npmjs.org/<nazwa>` (2026-10-22).
- Pomiary własne: `output/g5r7b_25pct_s4711/viz/meta.json`, `output/gha_100pct_10it/kutno-r7b-100pct-10it/viz/meta.json`; sonda WebGL (pywebview z `.venv`, WebView2/Chromium 155); zliczanie budynków `data/raw/osm/lodzkie-261015.osm.pbf`.
