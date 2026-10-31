# easy-matviz — dokumentacja odtwarzacza

Data: 2026-10-21. Branch: `wizualizer`. Opis programu, który już stoi. Ostatnia zmiana kodu odtwarzacza: `d62c8ee` (`viz_player/`, bez zmian w `pipeline/viz_index.py` i `pipeline/viz_engine.py` po tym commicie).

To nie jest decyzja i nie jest plan. Decyzja jest w `docs/projekt/DECISIONS.md` (D24 i punkt otwarty pod tabelą). Plan, kolejność i pomiar spike'u: `docs/research/wizualizer_plan.md`. Koncepcja sprzed wyboru: `docs/research/wizualizer_koncepcja.md`. Recenzja tej koncepcji: `docs/research/wizualizer_recenzja.md`. Przebieg prac: `docs/projekt/PROGRESS.md`. Pułapki z budowy: lekcje 24–29 w `docs/projekt/ERRORS.md`.

Nazwa robocza okna to **easy-matviz**. Pakiet Pythona nazywa się `viz_player`. Tytuł okna systemowego to `easy-matviz`.

## Po co jest

Odtwarzacz czyta gotowy run MATSim i pokazuje go na tym komputerze: mapa, czas, auta, droga, jeden pojazd, jedna droga. Nic nie liczy w MATSim. Nic nie zapisuje do sieci, eventów, planów ani do `scenarios/`. Java i `pipeline/g6_bake.py` zostają bez zmian.

Run, na którym liczby poniżej są zmierzone: `output/g5r6_25pct_s4711` (pomiary R6 są historyczne; od 2026-10-22 runem referencyjnym jest R7b, `output/g5r7b_25pct_s4711`, liczby w sekcji „Zmiany architektury” i w PROGRESS). To próbka 25% bazy R6. Inny katalog z `output_events.xml.zst` i `output_network.xml.zst` też się otwiera. Testy `--check` i `--smoke` są napisane pod ten jeden run.

Maszyna, na której okno powstało: Windows, 16 GB RAM, Python 3.12 przez `uv`. Do odtwarzania Java nie jest potrzebna. Do samego MATSim dalej jest Temurin 25.

## Czego program nie robi

- Nie przebudowuje sieci i nie woła `setStoreOriginalGeometry`. Łamana OSM jest tylko rysunkiem w oknie.
- Nie skaluje liczby aut do 100%. Rysuje tyle pojazdów, ile jest w eventach. Ułamek z `sampleSize` jest podpisem.
- Nie rysuje budynków, pasów, nazw ulic ani wykresu natężenia doby.
- Nie stawia dwóch runów obok siebie.
- Nie spina się z `g6_bake.py`. Film G6 dalej czyta swój `vehicles.npz`.
- Nie dotyczy Łodzi. Sieć i PBF są łódzkie tylko dlatego, że Kutno leży w tym wycinku OSM.
- Nie używa `tile.openstreetmap.org`.
- Nie zapisuje klucza CARTO. Bez pliku lokalnego podkład jest wyłączony.
- Akceptacja automatyczna (self-test, check, smoke) przeszła. Obejście obrazu przez człowieka zostaje otwarte. Zrzut smoke nie jest tą akceptacją.

## Zmiany architektury (fundamenty, 2026-10-22)

Refaktor po audycie kodu (`docs/research/wizualizer_audyt_kodu.md`), bez zmiany zachowania dla runu samochodowego. Liczby referencyjne R7b (przejazdy, linki, szczyt, okno 6–9) są przed i po takie same (PROGRESS 2026-10-22).

- **Origin z sieci.** Środek bbox węzłów `output_network.xml.zst` zaokrąglony do 1000 m, w `meta.json` (`origin`) i w kluczu cache indeksu oraz łamanych. Inny origin przebudowuje indeks. `viz_index` nie importuje już nic z `g6_bake.py` (Blender ma własny origin).
- **Biblioteka nie zna runu.** Stałe R6, osoba `r6510903_5`, link `1807611370009f` i współrzędne Kutna są tylko w `viz_player/tests/accept_r7b.py`.
- **Strona po lokalnym HTTP.** `site.py` zapisuje katalog `output/<run>/viz/site/`, pywebview serwuje go (`http_server=True`), JS pobiera `boot.json` i tablice `.bin`. Nie ma `html=`, limitu rozmiaru strony ani dosyłania łamanych przez `evaluate_js`.
- **`person_id` i klasyfikator.** Track niesie osobę z eventu `vehicle enters traffic` (`track_person_i`). `ids` to osoby, `track_id` zostaje id pojazdu. Klasę daje `pipeline/viz_classes.py`: atrybut `kind`, potem `subpopulation` z `output_plans.xml.zst`; bez planów albo dla osoby spoza planów pierwsza litera id, potem `?`. Nazwy znanych kluczy są w `viz_classes.KNOWN`, nieznany klucz dostaje własną nazwę. `FORMAT` indeksu to 4 (dodane `link_capacity`, `link_lanes`, `flow_capacity_factor` w `meta.json`; capacity znormalizowane do pojazdów na godzinę z `capperiod` sieci), plany wchodzą do klucza cache (`plans_sha256`).
- **Bezstanowa klatka.** `Player.frame(t, classes, selected, follow)`, `pick(t, classes, ...)`, `lookup(query)` nic nie zapamiętują po `open()`. Czas, klasy, zaznaczenie i śledzenie trzyma JS. Od kroku 4 D26 okno nie woła już tych metod: klatkę liczy klient (sekcja „Klient liczy klatkę”).
- **Podział kodu.** `player.py` (model), `window.py` (okno, `Api`, smoke, `main`), `check.py` (akceptacja dowolnego runu), `grab.py` (zrzut okna), `site.py` (katalog strony), `tests/` (pytest, jedna fixtura mini-runu).
- **Zależności.** `pywebview` i `pytest` w grupie `viz` (`uv run --group viz ...`). `osmium` zostaje w głównych zależnościach, bo używają go skrypty pipeline'u (`border_zones.py`, `osm_features.py`, `dk60_corridor.py`, `turn_violations.py`).
- **Limity jako ostrzeżenia.** 300 s parsowania, 200 MB pliku i 1 GiB RAM nie przerywają budowy (linia `UWAGA`).
- **Okno.** Etykieta linku to „średnia na odcinku”, pasek pokazuje „łamane: X z Y”.

Otwarte: wskaźnik postępu budowy indeksu w oknie (okno otwiera się po indeksie), `START`/okno 6–9 wpisane w indeks, spięcie `g6_bake.py` z indeksem, tryby PT/rower/pieszo (indeks zna tylko cztery eventy ruchu po sieci).

## Eksport v2 (D26, krok 3)

`pipeline/viz_export.py` robi z `viz/index.npz` katalog `viz/site/data/` (dla okna) albo `viz/export/` (uruchomienie samodzielne): `manifest.json`, `persons.json`, `tracks.bin` i `chunk_NNN.bin` co 15 min (`CHUNK_SEC = 900`). Eksport v2 ma `FORMAT` 2: oprócz węzłów porcja niesie zdarzenia aktywności z czasem w `[t0, t1)` (kolumny `act_t`, `act_dlon`, `act_dlat`, `act_type`, `act_kind`, `act_person_i`, posortowane po czasie, liczność `"a"`), a manifest `act_types` (legenda) i `act_start_counts` (starty na typ). To wewnętrzny cache z numerem wersji (`FORMAT`), nie publiczny kontrakt. Klucz źródła (`source_key` w manifeście) to sha256 eventów, sieci, skryptu indeksu, planów, `FORMAT` indeksu, origin, `FORMAT` eksportu, długości porcji i samego `viz_export.py`; niezgodny klucz przebudowuje eksport.

- **Porcja jest samowystarczalna.** Dla każdego przejazdu dotykającego przedziału zawiera węzły z przedziału plus po jednym węźle po obu stronach, więc klient interpoluje w obrębie jednej porcji. Powtórzone są tylko węzły graniczne: Kutno 25% 3 399 518 → 3 460 575 węzłów (+1,8%), 100% 13 733 294 → 13 974 338.
- **Pozycje** to przesunięcia lon/lat względem `origin_lonlat` w float32 (ok. 2 mm); klient dodaje origin w float64. Kolumny porcji: `track` (i32, globalny numer przejazdu), `knot_off` (i32, n+1), `knot_t`, `knot_dlon`, `knot_dlat`, `knot_len` (f32), `knot_link` (i32), każda dopełniona do 8 bajtów; liczby elementów są w manifeście (`n_tracks`, `n_knots`).
- **Adresy z kluczem.** `boot.json` wskazuje `data/manifest.json?v=<12 znaków source_key>`, a silnik dopisuje to samo `?v=` do `persons.json`, `tracks.bin` i porcji. Serwer pywebview nie ustawia `Cache-Control`, a profil WebView2 jest trwały, więc bez tego po ponownym eksporcie przeglądarka oddawała stary plik pod tym samym adresem (naprawdę się zdarzyło: `RangeError: Invalid typed array length`).
- **`tracks.bin`**: `person_i` (i32, indeks do `persons.json`), `cls` (u8, indeks do `classes` w manifeście), `mode` (u8, indeks do `modes`), `t0`, `t1` (f32). Dziś `modes = ["car"]`: indeks zna tylko ruch aut po sieci.
- **Rozmiary:** Kutno 25% 130 porcji, 69,7 MB, budowa 1,4 s; Kutno 100% 131 porcji, 281 MB (ok. 2,1 MB na porcję), budowa 4 s. Pierwszy test: `viz_player/tests/test_export.py` (pozycja z porcji = pozycja z silnika klatek, rozmiar nadmiaru, tabele, cache).

## Budynki 3D (D26, krok 6)

`pipeline/viz_buildings.py` czyta `data/raw/osm/lodzkie-*.osm.pbf` (osmium, jak `curves.py`), bierze zamknięte linie z tagiem `building` (bez `no`, `disused`, `construction`, `proposed`) z obwiedni sieci runu plus 300 m i zapisuje `buildings.json` oraz `buildings_{off,xy,h,src}.bin` obok eksportu v2 (`site/data/`). Skan prawdziwego PBF trwa ok. 36 s, wynik jest w cache (klucz: PBF, config, obwiednia, origin, kod).

- **Wysokość** (`height_of`): tag `height` (dokładnie) > `building:levels` × `floor_height_m` > H0 klasy `building=*`; dla wysokości wyprowadzonej (piętra, klasa) dochodzi ±`spread` z hasha sha1 id budynku (deterministycznie). Flaga źródła `src`: 0 tag, 1 piętra, 2 założenie.
- **Config** `config/viz_buildings.toml`: wszystko to ZAŁOŻENIA robocze do potwierdzenia przez właściciela: `variant` (`per_class` albo `single`), `floor_height_m = 3,0`, `spread = 0,15`, tabela `h0_m`, `default_m`. Zmiana configu przebudowuje budynki.
- **Okno:** przycisk „3D” przechyla mapę (55°) i włącza budynki jako jedną statyczną warstwę `SolidPolygonLayer` (wyciągnięcie z `h`). Kolor zależy od źródła (jaśniej z tagu, ciemniej założenie). Pod paskiem legendy stoi opis z liczbami i adnotacją, że wysokości z pięter i klasy to założenia, oraz „© OpenStreetMap contributors”. Bez PBF przycisk tylko przechyla mapę. Budynki i auta są w tej samej kanwie deck.gl, więc głębokość się zgadza.
- **Ograniczenia:** tylko zamknięte linie (bez relacji multipolygon, więc budynki z dziedzińcami i część dużych obiektów brakuje), tylko obrys zewnętrzny, bez dachów.
- **Liczby R7b** (obwiednia sieci = powiat z buforem, nie samo miasto): 83 617 budynków, z tagu `height` 326, z pięter 52 480, założenie wg klasy 30 811, mediana 3,3 m, pliki 4,5 MB.

## Uruchomienie

Z katalogu projektu. `python` nie jest na PATH, polecenie to `uv run`. Okno, testy i akceptacja potrzebują grupy zależności `viz` (pywebview, pytest). Sam pipeline jej nie potrzebuje.

```
uv run --group viz python -m viz_player output/g5r7b_25pct_s4711
```

Okno wstaje wstrzymane. Zegar pokazuje `06:00:00`, gdy ta godzina leży między początkiem i końcem runu. Powtórne wywołanie bez ścieżki otwiera ostatni run z `output/viz_player_state.json`.

W konsoli, zanim pojawi się okno, mogą minąć dwie rzeczy, jedna po drugiej:

1. Budowa indeksu, jeśli `output/<run>/viz/index.npz` jest nieświeży. Na R7b przebieg XML trwa ok. 20 s (`build_sec` w `meta.json`). Drugi start przy tych samych eventach, sieci, planach, originie i tym samym kodzie (`viz_index.py`, `viz_classes.py`) loguje `reuse` i XML pomija.
2. Łamane OSM. Pierwszy raz: linia `łamane: czytam OSM…`, skan ok. 7 s, potem `łamane: 4705 z 10383, skan …`. Kolejny start: `łamane: 4705 z 10383, cache`.

Potem Python zapisuje katalog strony `output/<run>/viz/site/` (`index.html`, `vendor/`, `boot.json`, tablice `.bin`), a pywebview serwuje go po lokalnym HTTP. Strona sama pobiera dane. Dowód klatki to liczba aut na pasku i kropki na mapie. Log okna dopisuje się do `output/<run>/viz/player.log`.

### Gdy okno jest puste

- W logu jest `FAIL okno nie wstało`: strona nie zgłosiła `mapReady` i `apiReady` w 20 s.
- W logu jest `łamane: …; cięciwy`: okno działa, drogi są prostymi między węzłami. Powód jest w tym samym zdaniu (`brak PBF`, `brak origid`, `sieć nieczytelna`, `inna kolejność linków`, albo treść wyjątku). Ten sam tekst pokazuje pasek okna.
- Po krzyżyku kolejne okno bywało puste, bo mostek pywebview dostawał `api` wcześniej niż funkcję `frame`, a flaga `busy` zostawała na zawsze. Od lekcji 28 `pull` woła `frame` dopiero, gdy funkcja jest, i zdejmuje `busy` po wyjątku. Profil WebView2 zostaje w `output/viz_player_webview` (`private_mode=False`).

## Okno

Rozmiar startowy 1440×900, tło `#121418`. Stos: pywebview 6.2.1 (`uv.lock`, wymaganie `pywebview>=6.2.1`), silnik `edgechromium` (WebView2), MapLibre GL JS 6.0.0 (BSD-3-Clause, tylko moduły ES, WebGL2 obowiązkowe) i deck.gl 9.4.0 (MIT, `deck.min.js`) w `viz_player/vendor/` razem z licencjami. Biblioteki leżą w katalogu strony (`vendor/`), strona nie ściąga ich z sieci. Wymaga WebGL2: bez niego zamiast mapy jest komunikat (`#nogl`) z prośbą o aktualizację sterownika, a nie biały ekran. `PySide6` nie jest zależnością.

Układ to siatka: mapa, panel 320 px po prawej, pasek 52 px na dole przez obie kolumny (`grid-column: 1 / -1`). Dzięki temu przycisk panelu zostaje na pasku, gdy panel znika.

Mapa MapLibre: zoom od 8 do 19, pochylenie do 70°, dopasowanie do obwiedni wszystkich końców linków z marginesem 20 px. Drogi (łamana OSM albo cięciwa), ślad zaznaczonego auta, podświetlenie linku, auta, kreski kierunku i obwódka zaznaczenia to warstwy deck.gl (`MapboxOverlay`): `PathLayer` dla dróg, śladu i linku, `ScatterplotLayer` dla aut (atrybuty binarne, promień w pikselach: 2,5, ciężkie 3,5), `IconLayer` dla kresek kierunku. Przesuwanie i zoom to gesty MapLibre; prawy przycisk myszy albo kontrolka w lewym górnym rogu obraca i pochyla mapę. Klik rozstrzyga kod w `shell.html` (`pickAt`: najbliższe auto w 8 px, inaczej najbliższy odcinek drogi), nie picking GPU.

Nakładka deck.gl działa w trybie `interleaved: false` (osobna kanwa nad mapą): tryb `interleaved: true` z MapLibre 6.0.0 i deck.gl 9.4.0 kończy się wyjątkiem w `deck.min.js` (odczyt `height` z undefined) i mapa nie dochodzi do `load`. Skutek: warstwy deck.gl nie są sortowane w głębi z warstwami MapLibre (np. budynki 3D w kroku 6 zasłonią się nie tak jak auta). Kropki aut liczy klient, dla bieżącego czasu. Serwer pywebview odpowiada `text/plain` dla `.mjs`, więc `window.py` rejestruje `mimetypes.add_type("text/javascript", ".mjs")`; bez tego przeglądarka odrzuca moduły. Serwer nie wysyła też `Cache-Control`, więc `site.py` kopiuje pliki bez zachowania daty (`shutil.copy`), żeby WebView2 po zmianie kodu sprawdzał je ponownie.

## Pasek

| element | działanie |
|---|---|
| `start` / `pauza` | Spacja albo przycisk. Na końcu zakresu odtwarzanie samo staje. |
| `1×` `10×` `60×` `300×` | Sekundy symulacji na sekundę rzeczywistą. Domyślnie 1×. Strzałki ◀ ▶ obok zmieniają mnożnik o 1 (zakres 1–300), preset świeci tylko, gdy jest równy mnożnikowi. Skok czasu w jednej klatce animacji jest obcięty do 0,1 s rzeczywistej, więc zawieszenie rysowania nie przewija doby naraz. |
| suwak | Jedna sekunda na krok. W trakcie ciągnięcia zegar nie leci do przodu sam. |
| zegar | `GG:MM:SS` od północy, bez zawijania po 24. R6 kończy się o `32:23:09` (116 589 s). |
| licznik | Auta w tej klatce, po filtrze klas. Forma `1 auto` / `2 auta` / `5 aut`. |
| `próbka 0,25` | `sampleSize` z `output_config.xml`. Brak parametru: `próbka brak`. |
| `Podkład wyłączony.` | Widać, gdy nie ma klucza CARTO. Z kluczem ten napis jest schowany, atrybucja zostaje na mapie. |
| `ukryj` / `panel` | Chowa albo przywraca prawy panel. |

Strzałki w lewo i w prawo przesuwają czas o 60 s, w granicach runu. Działają, gdy kursor nie jest w polu szukania.

## Panel

Nagłówek `easy-matviz` i nazwa katalogu runu. Pod spodem pole `id pojazdu`.

Szukanie idzie po posortowanej liście id, prefiksem, najwyżej 20 trafień (`viz_engine.lookup`). Jedno trafienie, albo dokładne id wśród tych 20, od razu wybiera pojazd i włącza śledzenie. Więcej trafień rysuje listę przycisków. Klik przycisku też wybiera i śledzi. Na R6 sam prefiks `r` nie wylistuje 4 336 mieszkańców: widać pierwszych 20 w kolejności napisu. Pełne id trafia.

Chipy klas są włączone wszystkie na starcie. Klik przełącza warstwę i prosi Python o nową klatkę. Chip `?` (inne) dochodzi tylko wtedy, gdy w indeksie jest pojazd o innej pierwszej literze.

Podpowiedź na dole panelu: „Spacja: start. Strzałki: ±1 min. F: śledź. Esc: wyczyść.”

Escape czyści wybór, listę trafień i śledzenie. W polu szukania najpierw zdejmuje fokus.

### Klik

Tolerancja to odcinek 8 pikseli w prawo od kliknięcia, przeliczony na metry, i nie mniej niż 0,5 m.

Najpierw najbliższe auto w bieżącej klatce. Przy remisie wygrywa wcześniejsze w tablicy klatki. Trafienie auta wyłącza śledzenie (klatka zostaje na miejscu) i czyści wybór drogi.

Gdy auta nie ma w tolerancji, szukana jest droga: odcinki łamanej, a przy linku bez łamanej cięciwa. Liczone w chwili kliknięcia, po wszystkich linkach.

### Auto

Gdy pojazd jest w ruchu, panel pokazuje:

1. id,
2. nazwę klasy,
3. prędkość w km/h,
4. `link` i jego id,
5. atrybut `type` drogi,
6. `freespeed` tej drogi w km/h.

`F` włącza śledzenie: mapa jedzie za kropką. Drugie `F` śledzenia nie wyłącza. Wyłącza je Escape, klik drogi albo klik auta.

Ślad to droga od startu przejazdu do teraz. Między węzłami jednego linku wchodzą punkty łamanej. Kolor śladu `#7eb6ff`, szerokość 2.

Kropka: promień 2,5 px, ciężkie (`h`) 3,5 px. Kreska z kropki to kierunek jazdy. Zaznaczone auto ma obręcz `#7eb6ff`.

### Postój

Gdy id jest wybrane, a w tej sekundzie nie ma przejazdu, panel pokazuje id, typ czynności z eventu (`home`, `work`, `tlo_start`, `tlo_end`, …), link czynności i zdanie `nie jedzie`. Współrzędna postoju zostaje taka, jak w evencie. Łamana jej nie rusza. Przy włączonym śledzeniu mapa jedzie na ten punkt.

`car interaction` nie wchodzi do indeksu. Dziura między czynnością a jazdą to dojście piesze i nie ma własnego bloku.

### Droga

Panel drogi: id linku, `type`, długość z atrybutu `length` (metry, zaokrąglone do pełnych), `freespeed`, potem `teraz N aut` i średnia prędkość aut, które w tej klatce mają ten link. Mediana jest liczona w `viz_engine.link_now` i na panel nie wchodzi. Oś czasu przy drodze się nie rysuje. Zaznaczona droga ma obrys `#7eb6ff` o szerokości 3, po łamanej albo po cięciwie.

### Oś czasu

Oś jest tylko przy wybranym id. To harmonogram tej osoby na zakresie całego runu (`t_min`…`t_max`), nie wykres natężenia.

Bloki biorą się z `actstart` / `actend`. Jazda bierze się z przejazdów i wycina nachodzący postój. Jeśli pierwsza czynność to `actend`, postój przed nią idzie od `t_min`. Czynność otwarta bez późniejszego końca trwa do `t_max`.

Szerokość nie jest proporcjonalna do czasu. Każdy postój ma wagę 1, choćby trwał kwadrans albo osiem godzin. Jazda krótsza niż 8 minut dostaje tę samą wagę co jeden postój. Dłuższa jazda waży `czas / 8 min`. Bloki leżą jeden przy drugim. Czas dojścia nie ma paska: na granicy bloków zegar przeskakuje. Ostatni blok jest dociągnięty do prawej krawędzi.

Pasek ma 36 px. Podpis (`dom`, `praca`, `tło`, `jazda`, albo surowa nazwa czynności) wchodzi do bloku, gdy blok ma co najmniej 16% szerokości. Pełny zakres jest w dymku: nazwa i `GG:MM:SS–GG:MM:SS`. Bieżący blok ma obrys. Biała kreska to teraz. Podpis pod paskiem: `postoje ściśnięte`, ukryty gdy same jazdy.

Klik w pasek ustawia zegar na czas wewnątrz klikniętego bloku. Jeśli odtwarzanie leci, leci dalej od tego miejsca.

Na R6, id `r6510903_5`, check z 2026-10-20 zapisał pięć bloków: dom `00:00:14–00:04:32`, jazda `00:05:09–00:12:40`, praca `00:17:33–08:17:33` (zaznaczona o 07:56), jazda `08:22:27–08:31:17`, dom do `32:23:09`.

## Znacznik auta

Grot z półkolem (`IconLayer`, atlas w `makeMarker` w `shell.html`): podstawa 16 px, promień półkola 8 px, grot 32 px przed środkiem podstawy, ciężkie ×22/16. Rozmiar skaluje się z zoomem (`MARKER`: `2^(0,5·(zoom−15))`, granice 0,25–3), żeby po przybliżeniu nie był malutki, a w widoku gminy nie zlewał aut w plamę.

## Modele 3D pojazdów

Checkbox „modele 3D pojazdów”: `SimpleMeshLayer` z bryłami z kodu (`MESH` w `shell.html`, osobówka i ciężarówka, metry, przód w +x). Rozmiar na ekranie dorównuje znacznikowi (`MODEL_PX`, mnożnik zoomu znacznika), nie jest prawdziwymi metrami, bo te byłyby kilkupikselowe. Przy włączonych modelach ikony (grot) nie są rysowane, a zaznaczenie to okrąg wokół modelu. Osobówka to model Quaternius (paczka „LowPoly Car pack”, CC0, `viz_player/vendor/quaternius/`, przeliczony przez `pipeline/viz_models.py`: osie, długość 4,5 m, kolory z tekstury; nadwozie dostaje kolor pojazdu, szyby, koła i światła zostają ciemne). Ciężarówka to nadal bryła z kodu, bo paczka nie ma ciężarówki. Przy włączonych modelach panel podpisuje autora. Dane idą jako obiekty z akcesorami, bo binarne `getOrientation` jest w tej wersji deck.gl ignorowane. Kolor modelu jak ikony (prędkość albo klasa).

## Kolor auta

Kolor to prędkość, ta sama rampa co w `blender/g6_load.py`. Skala kanwy kończy się na 14 m/s.

| prędkość | kolor |
|---|---|
| 0 | `rgb(255, 31, 13)` czerwień |
| 40% skali, około 20 km/h | `rgb(255, 179, 26)` żółć |
| 14 m/s, około 50 km/h, i wszystko powyżej | `rgb(26, 230, 255)` błękit |

Legenda w rogu mapy: `0 / 20 / 50 km/h`. Liczba w panelu jest osobno: prędkość silnika w km/h, z sufitem 30 m/s (108 km/h). Kolor powyżej 50 km/h już się nie zmienia. Prędkość nie jest przeliczana po przesunięciu kropki na łamaną. Zostaje `długość / dt` z indeksu.

## Kolor dróg OSM

Checkbox „kolor dróg OSM” w panelu przełącza kolor kresek z szarej palety na kolor klasy drogi (`ROAD_OSM` w `shell.html`, tabela z `wizualizer_plan.md`). Atrybut `type` jest ten sam co w indeksie, PBF nie jest czytany. Legenda w lewym dolnym rogu ma wiersz dla każdego typu obecnego w runie.

## Kolor auta

Przycisk „kolor auta” w panelu: `prędkość` (rampa, domyślnie) albo `klasa` (jeden kolor na literę id, tabela `CLASS_COLOR` w `shell.html`). Chipy dalej tylko chowają warstwy. Legenda klas zastępuje pasek prędkości.

## Błyski startu i końca aktywności

`Engine.flashes(t, life, typeOn, kindOn)` zwraca (bez alokacji co klatkę, bufory do 5 000 zdarzeń) starty i końce aktywności (`kindOn` indeksowane `act_kind`: [koniec, start]) z `(t − life, t]` z porcji bieżącej i poprzedniej (`Engine.back = 1`: `want` trzyma jedną porcję wstecz, a życie błysku i okno statystyk są krótsze niż porcja 900 s), najnowsze najpierw; `truncated`, gdy jest ich więcej. Wiek błysku to `t − act_t` w sekundach symulacji, rodzaj zdarzenia w `kind`. Start: sam rdzeń (`3 + 4e` px, alfa `e²`); koniec: sam pierścień rosnący `r0 → r1`, alfa `e²`; oba w kolorze typu (`e = 1 − wiek/życie`). W `shell.html` życie to `clamp(1,5 s × mnożnik, 3 s, 450 s)`, więc animacja jest czystą funkcją `t` i mnożnika. Manifest ma `act_start_counts` i `act_end_counts`, lista typów w oknie pokazuje typy z którymkolwiek. Dwie warstwy `ScatterplotLayer` z buforami binarnymi (pierścień `stroked`, rdzeń `filled`), mieszanie addytywne (`FLASH_BLEND`, w deck.gl 9.4 przy nieprzeplatanym `MapboxOverlay` przyjęte bez błędu), nad drogami, pod autami. Kolor z `actColor(nazwa typu)`: znane prefiksy, reszta z palety po haszu nazwy. `flash_off` w `web/scenarios.json` wchodzi do `boot.<lang>.json` jako `flashOff` (strona demo wyłącza `tlo_*`, aplikacja pokazuje wszystkie typy).

Wzorce w Pythonie: `viz_engine.flash_window` (z tablic indeksu) oraz test z surowych eventów (`test_effects.py`).

## Obciążenie linków

`Engine.linkStats(t, W, on)` liczy z węzłów porcji `ci−1` i `ci` wyjazdy z linków w oknie `(t − W, t]`: węzeł z `knot_len > 0` po węźle wjazdu (`knot_len = 0`) tego samego linku, liczony czasem wyjazdu i tylko w porcji, której `[t0, t1)` go zawiera (porcje powtarzają węzły graniczne). Warunek wjazdu przed wyjazdem odrzuca powtórzone zdarzenie wyjazdu (fixtura testowa emituje `left link` i `leaves traffic` na ostatnim linku; MATSim tylko drugie). `n` to wszystkie wyjazdy (natężenie), a `nf`, `len`, `tt` tylko pełne przejazdy: poprzedni węzeł leży w początku linku (tolerancja 1,5 m z `linkLL`), czyli wjazd z `relativePosition = 0` albo `entered link`. `Engine.loadValues` zamienia to na wskaźnik: prędkość `len / tt / freespeed` albo natężenie `n × 3600 / W / (capacity × flowFactor)`; `NaN`, gdy w oknie nie ma ruchu albo brak przepustowości. Atrybuty linków (`link_attr.bin`: długość, swobodna, przepustowość poj/h, pasy; `float32 × 4` na link) i `flowFactor` (z modułu `qsim` w `output_config.xml`) idą w `boot`. `shell.html` przelicza kolory co 250 ms (`refreshLoad`), a warstwa dróg bierze kolor z bufora (`getColor` z `updateTriggers` po `loadStamp`). Wzorzec w Pythonie: `viz_engine.link_window_stats`.

## Klasy

Klasa osoby (pipeline/viz_classes.py), w tej kolejności: atrybut `kind`, atrybut `subpopulation` z `output_plans.xml.zst`; bez planów albo dla osoby spoza planów pierwsza litera id (`r c o t h` → klucze poniżej); inaczej `?` („inne”). Legenda klas (`classes`: klucz, nazwa, czy większa kropka) jest w `meta.json`. Kolejność chipów: znane klucze, potem reszta alfabetycznie, `?` na końcu. Chip jest tylko dla klas, które mają przejazdy.

| klucz | litera (fallback) | nazwa | przejazdów na R7b |
|---|---|---|---:|
| `resident` | `r` | mieszkaniec | 4 336 |
| `commuter` | `c` | przyjeżdżający | 2 410 |
| `outbound` | `o` | wyjeżdżający | 732 |
| `tlo` | `t` | tło lekkie | 11 984 |
| `ciezkie` | `h` | ciężkie (większa kropka) | 4 842 |

Suma 24 304, tyle co `n_tracks`. Klucz spoza tabeli (np. inna wartość `kind` w innym mieście) pokazuje się pod własną nazwą bez zmiany kodu. Etap 3 (tryb, wiek, inne atrybuty osób) ma tu swoje miejsce, ale nie jest zaimplementowany.

## Drogi na mapie

Kolor i grubość biorą się z atrybutu `type`. Reszta typów (na R6: `residential`, `living_street`, `unclassified`) dostaje `#4e5663` i 1 px.

| `type` | kolor | grubość |
|---|---|---:|
| `motorway`, `motorway_link` | `#d5dde6` | 2 |
| `primary`, `primary_link` | `#aeb6c2` | 1,5 |
| `secondary`, `secondary_link`, `tertiary`, `tertiary_link` | `#7d8694` | 1,25 |
| `boundary_turnaround` | `#2a3038` | 0,75 |

Link poza kadrem (każdy punkt po jednej stronie, z marginesem 48 px) nie jest kreskowany. Licznik łamanych i tak go zalicza.

### Skąd się bierze łamana

W pliku sieci link MATSim to odcinek od węzła `from` do węzła `to` plus atrybut `length`. `length` bywa wyraźnie dłuższe niż cięciwa, bo reader OSM składa je z kawałków way. Konwerter `CreateKutnoNetwork` nie woła `setStoreOriginalGeometry`, więc w `output_network.xml.zst` geometrii way nie ma. Odtwarzacz składa ją sam, tylko do rysunku.

Źródła, oba tylko do odczytu:

- `output/<run>/output_network.xml.zst`: id linku, `from`, `to`, `length`, zagnieżdżony atrybut `origid`.
- ostatni plik `data/raw/osm/lodzkie-*.osm.pbf` po sortowaniu nazwy. Odczyt osmium z lokacjami. Współrzędne węzła bez lokacji odrzucają cały way.

`origid` jest id way OSM. Tak samo czyta go `pipeline/border_zones.py`. Matcher bierze podłańcuch way między węzłem `from` a węzłem `to`, nie cały way. Szuka każdej pary wystąpień tych id. Kierunek wsteczny, także do indeksu 0, zostawia pierwszy węzeł.

Łańcuch zostaje tylko wtedy, gdy naraz:

- ma co najmniej 3 punkty,
- oba końce są w odległości ≤ 1 m od końców cięciwy,
- długość łamanej różni się od `length` o co najwyżej 1 m,
- jakiś punkt odstaje od cięciwy o więcej niż 2 m (prostsza kreska i tak wygląda jak cięciwa).

Inaczej zostaje cięciwa. Zawrotki graniczne (`turnaround_<ujście>_<źródło>` w `CreateKutnoNetwork`) nie mają `origid`. Zostają cięciwami. Ich `length` to odległość euklidesowa, co najmniej 10 m, typ `boundary_turnaround`.

Na R6, cache odczytany 2026-10-21: 4 705 linków z łamaną z 10 383, 50 196 punktów, najdłuższy łańcuch 89 punktów. Link `1807611370009f`: 11 punktów, `length` 1 969 m, cięciwa 842 m, środek łamanej ponad 100 m od środka cięciwy. Te progi są w `viz_player --check`.

### Jak jedzie kropka

Indeks trzyma pozycję na cięciwie: liniowo w czasie między węzłami przejazdu. Okno liczy ułamek tej cięciwy i stawia kropkę w tym samym ułamku długości łamanej. Kierunek to `atan2(dy, dx)` następnego odcinka łamanej, w EPSG:2180 (x na wschód, y na północ). Kanwa ma y w dół, więc rysunek bierze kąt ze znakiem minus.

Prędkość zostaje z silnika. Na łuku kropka jedzie wzdłuż drogi, a liczba km/h dalej jest `length / dt`, nie prędkością po cięciwie.

Przesunięcie jest kopią klatki po `viz_engine.frame`. Indeks na dysku i pamięć silnika się nie zmieniają. Drugie wywołanie klatki dla tego samego czasu i tych samych klas nie przesuwa punktu drugi raz: okno trzyma już przesuniętą klatkę.

### Cache łamanych

`output/<run>/viz/curves.npz` (katalog `output/` jest w `.gitignore`).

| pole | typ | treść |
|---|---|---|
| `version` | int32 | `1` |
| `off` | int32, długość = liczba linków + 1 | wycinki CSR w kolejności linków indeksu |
| `xy` | float32, kształt `(m, 2)` | metry względem originu, wschód i północ |

Link bez łamanej ma `off[i+1] == off[i]`. Zapis idzie przez `curves-partial.npz` i podmianę nazwy.

Cache jest świeży, gdy jego czas pliku jest nie wcześniejszy niż sieci i niż PBF, wersja to 1, `off` jest niemalejące, zaczyna się od 0 i kończy na liczbie punktów. Zmiana reguł w `viz_player/curves.py` sama cache nie unieważnia. Po zmianie reguł podnieś `VERSION` albo usuń `curves.npz`.

Brak PBF, nieczytelna sieć, inna kolejność linków niż w indeksie, albo wyjątek przy starcie: okno zostaje na cięciwach i dopisuje powód do `player.log`. Pusty wynik nie zapisuje cache.

### Dlaczego punkty nie siedzą w HTML

Strona nie jest stringiem. `NavigateToString` odrzucał duże HTML (lekcja 29), więc dawniej łamane szły po starcie przez `evaluate_js`. Teraz `site.write_site` zapisuje katalog, a pywebview serwuje go po lokalnym HTTP (`http_server=True`). `boot.json` to małe metadane (run, czas, klasy, podkład, zasięg, liczba linków, `curveNote`). Tablice są plikami little-endian: `link_ll.bin` (float64: lon1, lat1, lon2, lat2), `link_type.bin` (uint8), `curve_off.bin` (int32), `curve_lon.bin`, `curve_lat.bin` (float64). JS pobiera je przez `fetch`, a mapa rusza po ich wczytaniu. Nie ma limitu wielkości strony.

## Współrzędne

Origin to środek bbox węzłów sieci runu (EPSG:2180, wschód, północ), zaokrąglony do 1000 m, zapisany w `meta.json`. W plikach odtwarzacza x i y są już po odjęciu originu. Na mapę wracają przez `pyproj`, oś zawsze x = wschód, y = północ, potem EPSG:4326. Dla R7b origin to 528 000 / 488 000. Zmiana originu (inna sieć, inna reguła) przebudowuje indeks i cache łamanych.

Kolejność w JSON `boot.json` i w ścieżkach śladu jest szerokość–długość tam, gdzie to wynik Pythona (`panel`, `anchor`); MapLibre i deck.gl biorą długość pierwszą. W transformacji pyproj najpierw jest długość.

## Pliki

Kod, w gicie:

| plik | rola |
|---|---|
| `pipeline/viz_models.py` | konwersja modelu Quaternius (OBJ + tekstura) do `vendor/quaternius/car_mesh.json` |
| `pipeline/viz_index.py` | jeden przebieg eventów i sieci, zapis indeksu |
| `pipeline/viz_engine.py` | klatka, klik, szukanie, czynności; bez rysowania i bez XML |
| `pipeline/viz_classes.py` | klasa osoby z atrybutów planów, fallback na literę id |
| `viz_player/player.py` | model: indeks, panel, oś, przesunięcie kropki, bezstanowa klatka |
| `viz_player/window.py` | okno pywebview, `Api`, smoke, `main` |
| `viz_player/check.py` | akceptacja dowolnego runu bez okna |
| `viz_player/site.py`, `grab.py` | katalog strony; zrzut okna |
| `viz_player/tests/` | pytest, fixtura mini-runu, `accept_r7b.py` |
| `viz_player/curves.py` | łamane OSM i ich cache |
| `viz_player/shell.html`, `engine.js` | układ, rysunek, klawisze; klatka po stronie klienta |
| `viz_player/vendor/` | MapLibre GL JS 6.0.0 (`maplibre/`), deck.gl 9.4.0 (`deck.min.js`) |
| `viz_player/__main__.py` | `python -m viz_player` |

Wynik runu, poza gitem, pod `output/<run>/viz/`:

| plik | kto pisze |
|---|---|
| `index.npz`, `meta.json`, `index.log` | indekser; w trakcie zapisu bywa `index.writing.npz` |
| `engine.log` | `viz_engine.py` przy `--check` silnika |
| `curves.npz` | odtwarzacz; w trakcie `curves-partial.npz` |
| `site/` | odtwarzacz: strona serwowana oknu (generowana przy każdym otwarciu) |
| `smoke.png` | zrzut ze smoke |
| `player.log` | odtwarzacz, dopisywany |

Poza katalogiem runu, też poza gitem: `output/viz_player_state.json` (`{"run": "output/g5r7b_25pct_s4711"}`) i katalog profilu `output/viz_player_webview`.

Ścieżka w stanie jest względna wobec katalogu projektu, gdy run w nim leży. Run spoza projektu zostaje ścieżką absolutną.

Klucz podkładu, gdy będzie: `config/viz_basemap.local.toml`, pole `key`. Plik jest w `.gitignore`. Klucz nie może zawierać spacji ani znaków `/?#&=`. URL to kafelki CARTO Dark Matter `dark_nolabels`. Atrybucja: `© OpenStreetMap contributors © CARTO`. Sam HTTP 200 bez klucza nie jest mapą: serwer oddaje kafelek z napisem o braku klucza. Dlatego brak poprawnego klucza zostawia zdanie „Podkład wyłączony.”

## Indeks

Format `3` w `meta.json` (1: R6, 2: origin z bbox, 3: `person_id` i klasy z planów). Stary indeks jest przebudowywany, nie czytany po cichu. Orientacyjny budżet pliku 200 MB i tablic w RAM 1 GiB: przekroczenie to ostrzeżenie w logu, nie błąd. R7b: `index.npz` 9 486 977 B, budowa ok. 20 s, tablice w RAM 79 544 507 B, klatka szczytu 0,006 s.

Indeks powstaje przy pierwszym otwarciu silnika albo okna. `viz_engine.load` woła `viz_index.run`. Plik jest świeży, gdy `checked` jest prawdziwe, format zgadza się z `FORMAT`, a sha256 eventów, sieci, planów (`plans_sha256`), skryptów (`viz_index.py` i `viz_classes.py`) oraz `origin` zgadzają się z `meta.json`. Zmiana indeksera, klasyfikatora, planów albo originu przebudowuje indeks. Zmiana odtwarzacza nie.

Wejście:

- `output_events.xml.zst`,
- `output_network.xml.zst`,
- `output_config.xml` tylko po `sampleSize` (pierwsze `name="sampleSize"`),
- `output_plans.xml.zst` (opcjonalnie) tylko po atrybutach osób `kind` i `subpopulation`.

Eventy ruchu: `vehicle enters traffic`, `entered link`, `left link`, `vehicle leaves traffic`. Semantyka jest kopią `g6_bake.py` (jest to druga, niezależna implementacja: spięcie z bake'em odłożone), z indeksem linku na węźle. `vehicle enters traffic` niesie też `person` (brak = id pojazdu).

- `vehicle enters traffic`: punkt na cięciwie wg `relativePosition`. Brak atrybutu = 1. Długość do prędkości = 0.
- `entered link`: węzeł `from`, długość 0.
- `left link` i `vehicle leaves traffic`: węzeł `to`, długość = atrybut `length`.

Czynności: `actstart` i `actend` poza `car interaction`. Brak `person`, `link`, `actType`, `x` albo `y` przerywa budowę. Brak współrzędnych nie jest uzupełniany węzłem.

Węzły jednego przejazdu leżą zwartym blokiem. Eventy pojazdów w pliku są przeplatane, więc otwarty przejazd siedzi w buforze i spływa przy `vehicle leaves traffic`, przy nowym wjeździe tego samego pojazdu albo na końcu pliku. Czas węzłów w przejeździe nie może maleć.

Przejazdy są też w kubełkach 60 s. Klatka o czasie `t` ogląda tylko przejazdy, których przedział zahacza o kubełek tej minuty, a potem zostawia te z `t` w `[t0, t1]` włącznie.

### Tablice `index.npz`

Współrzędne linków i węzłów są w metrach względem originu, float32.

| tablica | sens |
|---|---|
| `link_id`, `link_xy` `(n, 4)`, `link_length`, `link_freespeed`, `link_type` | sieć, w kolejności pliku |
| `ids` | posortowane id osób i pojazdów |
| `track_id`, `track_id_i`, `track_class`, `track_t0`, `track_t1` | jeden wiersz na przejazd |
| `knot_off` | CSR węzłów przejazdu |
| `knot_t`, `knot_x`, `knot_y`, `knot_len`, `knot_link` | węzły |
| `bucket_sec`, `bucket_t0`, `bucket_off`, `bucket_track` | kubełki minutowe |
| `act_id`, `act_t`, `act_kind`, `act_type`, `act_link`, `act_x`, `act_y` | czynności; `act_kind` 1 = start, 0 = koniec |

`meta.json` trzyma zakres czasu, legendy klas, typów dróg i czynności, sha256, `sample_size`, szczyty i rozmiar. Szczyt (`max_concurrent`) jest z osobnego przejścia po eventach: licznik wjazdów minus wyjazdy, nie z klatki rysowanej co sekundę. Potem silnik sprawdza, że klatka w tej sekundzie ma tę samą liczbę.

R6, z `meta.json` tego runu:

| pole | wartość |
|---|---|
| `t_min`, `t_max` | 14 s (`00:00:14`), 116 589 s (`32:23:09`) |
| przejazdy | 29 660 |
| węzły | 3 787 376 |
| linki, węzły sieci | 10 383, 4 534 |
| czynności | 59 320 |
| szczyt | 961 o 58 170 s (`16:09:30`) |
| szczyt 6:00–9:00 | 849 o 28 591 s (`07:56:31`) |
| wjazdy w 6:00–9:00 | 6 641 |
| czynności w legendzie | `home`, `work`, `tlo_start`, `tlo_end` |

Akceptacja konkretnego runu (liczby przejazdów, wjazdów 6–9, szczytów, linków i węzłów) nie jest w kodzie biblioteki. Jest w `viz_player/tests/accept_r7b.py`. Indeks przechodzi na dowolnym runie test geometrii i zgodność liczb z osobnym odczytem eventów (przejazdy, wjazdy 6–9, klasy).

Test geometrii indeksera: seed 1, trzy przejazdy dłuższe niż 8 węzłów, osobny odczyt eventów, 20 chwil, pozycja nie dalej niż 0,5 m od cięciwy linku z eventów. To test pozycji na cięciwie. Łamana okna go nie dotyczy i nie powinna go ruszać.

## Silnik klatki

`pipeline/viz_engine.py` czyta `viz/` albo pozwala indekserowi go zbudować. Nie rysuje. Nie otwiera XML sam. Zwraca klatkę: `xy`, `heading`, `speed`, `link`, `cls`, `track`.

Pozycja: liniowo między węzłami, których czasy obejmują `t`. Przy `dt = 0` zostaje późniejszy węzeł. Link w trakcie odcinka to link wcześniejszego węzła, a w chwili węzła końcowego link tego węzła.

Prędkość odcinka: jeśli `knot_len` końca > 0, to ta długość / `dt`, inaczej długość cięciwy / `dt`. `dt` poniżej 0,001 s liczy się jak 0,001 s. Sufit 30 m/s. Kierunek: `atan2` pierwszego niezerowego odcinka od bieżącego wstecz. Samotny węzeł ma kierunek 0 i prędkość 0.

Klik auta i klik cięciwy są w silniku. Klik po łamanej jest w `viz_player/curves.py` i używa tej samej geometrii „najbliższy odcinek”.

## Klient liczy klatkę (D26, krok 4)

Klatkę liczy `viz_player/engine.js` w oknie, z eksportu v2 (`data/`): `Engine.load` czyta `manifest.json`, `persons.json`, `tracks.bin`, a porcje `chunk_NNN.bin` ładuje wokół bieżącego czasu (`want`: bieżąca i następna, po 6 porcji w obie strony zostają w pamięci). `frame(t, on)` zwraca bufory: `lon`, `lat`, `speed`, `heading`, `cls`, `track`, `link`, `n`. Reguły są te same co w `pipeline/viz_engine.py` (liniowo między węzłami, link wcześniejszego węzła w trakcie odcinka, prędkość z `knot_len`/`dt`, sufit 30 m/s, kierunek z pierwszego niezerowego odcinka wstecz); łamane OSM przenoszą pozycję z cięciwy na łamaną tym samym ułamkiem (`pointAt`, `span` dla śladu).

Stan widoku (czas, klasy, zaznaczenie, śledzenie) jest tylko w `shell.html`. Przeglądarka sama robi: klatkę, ślad zaznaczonego auta (`trail`), szukanie id (`lookup`, prefiks, najwyżej 20), kliknięcie w auto (najbliższe w promieniu 8 px) albo drogę (najbliższy odcinek łamanej), prędkość średnią na linku (`linkNow`). Python pozostał tylko dla opisu zaznaczenia: `Api.describe(t, selected, veh, now)` zwraca panel (linie, oś czynności) i kotwicę śledzenia, gdy auto stoi. Wołane przy zmianie zaznaczenia i co 250 ms przy zaznaczeniu, odpowiedź spóźniona (`panelSeq`) odpada. `Player.frame`, `pick`, `lookup` zostały jako wzorzec dla testów i `--check`, okno ich nie woła.

Różnice względem wzorca z Pythona: pozycja z łamaną do ok. 1 m na długim linku (6 km; nieliniowość lon/lat względem EPSG:2180), mediana 5 mm, p90 16 cm na R7b; kierunek do 0,012 rad; prędkość i link bez różnic. Test: `viz_player/tests/test_client.py` (pod `node`, z i bez łamanej, ślad, `lookup`) i `--smoke` (prawdziwe okno: klatka klienta = klatka Pythona, klik w auto, chip, oś, Esc).

Wydajność silnika klienta pod node (Kutno 100%, szczyt 6–9, 2834 aut, bez łamanych): mediana 0,21 ms, p95 0,39 ms na klatkę (wcześniej Python 13,8 ms plus most 3,3 ms). Kutno 25%: 717 aut, 0,035 ms.

## Otwieranie runu z okna

Przycisk „otwórz run…” (`#openrun` w `shell.html`): `Api.pick_run` pokazuje systemowy wybór folderu, `Api.open_path(path)` otwiera run w nowym `Player` i dopiero po sukcesie (indeks, łamane, `write_site`) zapisuje stan i podmienia model w `Api`. Strona potem robi `location.reload()`. Błędy (brak katalogu, brak eventów/sieci, wyjątek budowy) wracają jako `{status: "error", message}` i bieżący run zostaje. `Api` trzyma katalog strony (`_site`); okno z konsoli używa stałego `output/viz_player_site/`.

## Podkłady WMS / WMTS

`viz_player/ogc.py`: `capabilities(url)` (WMS 1.1.1/1.3.0 i WMTS 1.0.0, typ po korzeniu XML), `make_spec(cap, warstwa)` (samodzielny opis do kafelków, wybór układu: 3857 → stopnie → rzutowany), `tile(spec, z, x, y)`. Kafelki idą przez `Api.ogc_tile` jako base64; w `shell.html` protokół MapLibre `ogc://<id>/{z}/{x}/{y}` (`maplibregl.addProtocol`) i źródła `raster` o id `svc-<id>`. Lista usług w `output/viz_player_services.json` (poza gitem). Układ rzutowany: obraz w układzie usługi jest przepróbowany (najbliższy sąsiad) na siatkę kafelka 256 px; oś bbox z `pyproj.CRS.axis_info`.

## Własny raster

`viz_player/rasters.py`: `read_georef` (GeoTIFF przez tagi Pillowa, plik świata z przesunięciem o pół piksela, `.prj`), `guess_crs`, `corners_from_affine` / `corners_from_bbox` (przez pyproj), `manual_corners` (obraz na środku widoku), `store_image` (kopia do `output/viz_player_rasters/`, max 4096 px). Wspólna postać to cztery narożniki lon/lat `[lewy-górny, prawy-górny, prawy-dolny, lewy-dolny]`, którą przyjmuje źródło `image` MapLibre. Edycja ręczna w `shell.html` (`editStart`, `dragMove`): uchwyty DOM nad mapą, przeciąganie liczone w metrach Web Mercator (konforemne, więc prostokąt zostaje prostokątem). `Api.raster_*` w `window.py`.

## Podkład

Bez `config/viz_basemap.local.toml` mapa jest tłem `#121418`, drogi i auta na kanwie, na pasku zdanie „Podkład wyłączony.” Klucz dokłada Michał później. Do tego czasu kafelków nie ma, i tak ma być.

## Testy

pytest w grupie `viz`. Syntetyczne eventy mają jeden event na linię. Na Windows `np.load` trzeba zamknąć, zanim kasuje się `index.npz`.

```
uv run --group viz pytest viz_player/tests
uv run python pipeline/viz_index.py output/g5r7b_25pct_s4711
uv run python pipeline/viz_engine.py output/g5r7b_25pct_s4711
uv run --group viz python -m viz_player --check output/g5r7b_25pct_s4711
uv run --group viz python -m viz_player.tests.accept_r7b
uv run --group viz python -m viz_player --smoke output/g5r7b_25pct_s4711
```

`viz_player/tests/` ma jedną fixturę mini-runu (`fixture.py`: sieć 6 linków, eventy, plany z atrybutami) i testy indeksu (origin, reuse, unieważnienie przez origin, format i plany, `person_id`, klasy z planów), silnika (pozycja, prędkość, filtr klas, klik, czynności), łamanych (w tym cache zależny od originu) i okna (oś, panel, klik, śledzenie, katalog strony, bezstanowość na 8 wątkach). Testy nie sprawdzają tekstu HTML ani JS.

`--check` działa na dowolnym runie: liczby klatki okna (szczyt, okno 6–9, filtr największej klasy, panel linku, oś pierwszego id z przejazdem i czynnościami) muszą zgadzać się z `meta.json`. `accept_r7b.py` to akceptacja runu referencyjnego R7b (liczby sprzed refaktoru, lookup `r6510903_5`, łamana `1807611370009f`). Ten run i ten link są tylko tam.

`--smoke` otwiera prawdziwe okno WebView2 (strona z lokalnego HTTP), sprawdza liczbę łamanych w oknie, rysuje klatkę z okna 6–9, klika ukrycie panelu, chip największej klasy i start, robi zrzut (`output/<run>/viz/smoke.png`, nie w gicie), szuka id przez pole wyszukiwania, sprawdza oś i czyści zaznaczenie klawiszem Esc. Pierwsze uruchomienie okna bywa odrzucone (`Main window failed to start`), drugie przechodzi.

Kod wyjścia 0: test przeszedł. 1: test albo brak plików runu. 2: uruchomienie bez ścieżki i bez zapisanego stanu.

## Odłożone

Zostaje, aż będzie osobne zlecenie: klucz CARTO, drugi run obok siebie, spięcie z `g6_bake.py`, Łódź, łamane w konwerterze Javy, przebudowa sieci. Plan poprawek okna zaakceptowany przez Michała, kod jeszcze nie: sekcja „Poprawki okna” w `docs/research/wizualizer_plan.md`. Michał 2026-10-21 potwierdził, że auta jadą po łuku. Reszta listy z kroku 3 zostaje do obejrzenia.
