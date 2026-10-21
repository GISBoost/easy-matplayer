# easy-matviz — dokumentacja odtwarzacza

Data: 2026-10-21. Branch: `wizualizer`. Opis programu, który już stoi. Ostatnia zmiana kodu odtwarzacza: `d62c8ee` (`viz_player/`, bez zmian w `pipeline/viz_index.py` i `pipeline/viz_engine.py` po tym commicie).

To nie jest decyzja i nie jest plan. Decyzja jest w `docs/projekt/DECISIONS.md` (D24 i punkt otwarty pod tabelą). Plan, kolejność i pomiar spike'u: `docs/research/wizualizer_plan.md`. Koncepcja sprzed wyboru: `docs/research/wizualizer_koncepcja.md`. Recenzja tej koncepcji: `docs/research/wizualizer_recenzja.md`. Przebieg prac: `docs/projekt/PROGRESS.md`. Pułapki z budowy: lekcje 24–29 w `docs/projekt/ERRORS.md`.

Nazwa robocza okna to **easy-matviz**. Pakiet Pythona nazywa się `viz_player`. Tytuł okna systemowego to `easy-matviz`.

## Po co jest

Odtwarzacz czyta gotowy run MATSim i pokazuje go na tym komputerze: mapa, czas, auta, droga, jeden pojazd, jedna droga. Nic nie liczy w MATSim. Nic nie zapisuje do sieci, eventów, planów ani do `scenarios/`. Java i `pipeline/g6_bake.py` zostają bez zmian.

Run, na którym liczby poniżej są zmierzone: `output/g5r6_25pct_s4711`. To próbka 25% bazy R6. Inny katalog z `output_events.xml.zst` i `output_network.xml.zst` też się otwiera. Testy `--check` i `--smoke` są napisane pod ten jeden run.

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

## Uruchomienie

Z katalogu projektu (`C:\Users\Michal\Desktop\MATSim`). `python` nie jest na PATH. Polecenie to `uv run python`.

```
uv run python -m viz_player output/g5r6_25pct_s4711
```

Okno wstaje wstrzymane. Na R6 zegar pokazuje `06:00:00`, bo 6:00 leży między początkiem i końcem runu. Powtórne wywołanie bez ścieżki otwiera ostatni run z `output/viz_player_state.json`.

W konsoli, zanim pojawi się okno, mogą minąć dwie rzeczy, jedna po drugiej:

1. Budowa indeksu, jeśli `output/<run>/viz/index.npz` jest nieświeży. Na R6 pierwszy przebieg XML trwał 22,4 s (`build_sec` w `meta.json`). Drugi start przy tych samych eventach, sieci i tym samym `viz_index.py` loguje `reuse` i XML pomija.
2. Łamane OSM. Pierwszy raz na R6: linia `łamane: czytam OSM…`, skan 7,2 s, potem `łamane: 4705 z 10383, skan 7.2 s`. Kolejny start: `łamane: 4705 z 10383, cache`.

Po starcie okna Python dosyła punkty łamanych kawałkami. Dopóki to trwa, mapa może być sama, bez aut. Na R6 to krótka chwila (50 196 punktów, kawałki po 2000). Potem pojawiają się drogi i auta. Zegar `06:00:00` bywa widoczny już w szablonie, zanim przyjdzie pierwsza klatka. Dowód klatki to liczba aut na pasku i kropki na mapie.

Log okna dopisuje się do `output/<run>/viz/player.log`.

### Gdy okno jest puste

- W logu jest `FAIL okno nie wstało`: strona nie zgłosiła `mapReady` i `apiReady` w 20 s. Punkty łamanych nie poszły, a pętla klatek czeka na nie, więc auta nie przyjdą.
- W logu jest `łamane: …; cięciwy`: okno działa, drogi są prostymi między węzłami. Powód jest w tym samym zdaniu (`brak PBF`, `brak origid`, `sieć nieczytelna`, `inna kolejność linków`, albo treść wyjątku).
- Po krzyżyku kolejne okno bywało puste, bo mostek pywebview dostawał `api` wcześniej niż funkcję `frame`, a flaga `busy` zostawała na zawsze. Od lekcji 28 `pull` woła `frame` dopiero, gdy funkcja jest, i zdejmuje `busy` po wyjątku. Profil WebView2 zostaje w `output/viz_player_webview` (`private_mode=False`).

## Okno

Rozmiar startowy 1440×900, tło `#121418`. Stos: pywebview 6.2.1 (`uv.lock`, wymaganie `pywebview>=6.2.1`), silnik `edgechromium` (WebView2), Leaflet 1.9.4 w `viz_player/vendor/` razem z `leaflet.LICENSE`. Leaflet jest wklejony w stronę. Strona nie ściąga go z sieci. `PySide6` nie jest zależnością.

Układ to siatka: mapa, panel 320 px po prawej, pasek 52 px na dole przez obie kolumny (`grid-column: 1 / -1`). Dzięki temu przycisk panelu zostaje na pasku, gdy panel znika.

Mapa Leaflet: zoom od 8 do 19, krok 0,25, dopasowanie do obwiedni wszystkich końców linków z marginesem 20 px. Auta, drogi, ślad i podświetlenie linku rysuje kanwa nad mapą (`#draw`, `pointer-events: none`). Klik przechodzi do mapy pod spodem. Przesuwanie i zoom są gestami Leaflet.

Warstwa dróg jest przerysowywana, gdy zmieni się rozmiar, zoom albo środek mapy (klucz z dokładnością środka do 5 miejsc po przecinku). Kropki aut przychodzą osobno, z Pythona, dla bieżącego czasu.

## Pasek

| element | działanie |
|---|---|
| `start` / `pauza` | Spacja albo przycisk. Na końcu zakresu odtwarzanie samo staje. |
| `1×` `10×` `60×` `300×` | Sekundy symulacji na sekundę rzeczywistą. Domyślnie 1×. Skok czasu w jednej klatce animacji jest obcięty do 0,1 s rzeczywistej, więc zawieszenie rysowania nie przewija doby naraz. |
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

## Kolor auta

Kolor to prędkość, ta sama rampa co w `blender/g6_load.py`. Skala kanwy kończy się na 14 m/s.

| prędkość | kolor |
|---|---|
| 0 | `rgb(255, 31, 13)` czerwień |
| 40% skali, około 20 km/h | `rgb(255, 179, 26)` żółć |
| 14 m/s, około 50 km/h, i wszystko powyżej | `rgb(26, 230, 255)` błękit |

Legenda w rogu mapy: `0 / 20 / 50 km/h`. Liczba w panelu jest osobno: prędkość silnika w km/h, z sufitem 30 m/s (108 km/h). Kolor powyżej 50 km/h już się nie zmienia. Prędkość nie jest przeliczana po przesunięciu kropki na łamaną. Zostaje `długość / dt` z indeksu.

## Klasy

Pierwsza litera id pojazdu. Legenda jest w `meta.json`, te same nazwy co w `pipeline/viz_index.py`.

| litera | kod | nazwa | przejazdów na R6 |
|---|---:|---|---:|
| `r` | 0 | mieszkaniec | 4 336 |
| `c` | 1 | przyjeżdżający | 2 410 |
| `o` | 2 | wyjeżdżający | 732 |
| `t` | 3 | tło lekkie | 16 439 |
| `h` | 4 | ciężkie | 5 743 |
| inna | 5 | inne | 0 |

Suma 29 660, tyle co `n_tracks`. Wyłączenie `t` na R6 zostawia 447 aut o 07:56:31 i 420 aut w szczycie 16:09:30. To dwa różne czasy. Oba wyniki są w logach.

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

`NavigateToString` odrzucił stronę o wielkości 1,7 MB (`Wartość jest spoza oczekiwanego zakresu`, lekcja 29). Sam szablon z cięciwami ma 659 KB. Check wymaga strony poniżej 1,2 MB.

`boot` niesie cięciwy (lon, lat, lon, lat, kod typu) i puste tablice łamanych. Flaga `curveWait` jest włączona, gdy jest choć jedna łamana. Po `mapReady` i `apiReady` Python dopisuje `curveOff`, `curveLon`, `curveLat` kawałkami po 2000 i sprawdza długość. Potem zeruje licznik namalowanych łamanych, czyści klucz warstwy dróg i puszcza rysunek. Pętla klatek stoi, dopóki `curvesReady` jest fałszem.

`bendI` / `bendN` w `boot` to haczyk testu dla `1807611370009f`. Nie ma ich na panelu.

## Współrzędne

Origin, wspólny z `g6_bake.py`: wschód 524 805 m, północ 485 023 m, EPSG:2180. W plikach odtwarzacza x i y są już po odjęciu originu. Na mapę wracają przez `pyproj`, oś zawsze x = wschód, y = północ, potem EPSG:4326.

Punkt originu wychodzi jako 52,2307° N, 19,3633° E. Check i self-test okna wymagają zgodności do 0,002°. Na R6 obwiednia linków obejmuje 52,23° N i 19,36° E.

Kolejność w JSON Leaflet to szerokość, długość. W transformacji pyproj najpierw jest długość.

## Pliki

Kod, w gicie:

| plik | rola |
|---|---|
| `pipeline/viz_index.py` | jeden przebieg eventów i sieci, zapis indeksu |
| `pipeline/viz_engine.py` | klatka, klik, szukanie, czynności; bez rysowania i bez XML |
| `viz_player/player.py` | okno, panel, oś, przesunięcie kropki, testy |
| `viz_player/curves.py` | łamane OSM i ich cache |
| `viz_player/shell.html` | układ, rysunek, klawisze |
| `viz_player/vendor/` | Leaflet 1.9.4 |
| `viz_player/__main__.py` | `python -m viz_player` |

Wynik runu, poza gitem, pod `output/<run>/viz/`:

| plik | kto pisze |
|---|---|
| `index.npz`, `meta.json`, `index.log` | indekser; w trakcie zapisu bywa `index.writing.npz` |
| `engine.log` | `viz_engine.py` przy `--check` silnika |
| `curves.npz` | odtwarzacz; w trakcie `curves-partial.npz` |
| `player.log` | odtwarzacz, dopisywany |

Poza katalogiem runu, też poza gitem: `output/viz_player_state.json` (`{"run": "output/g5r6_25pct_s4711"}`) i katalog profilu `output/viz_player_webview`.

Ścieżka w stanie jest względna wobec katalogu projektu, gdy run w nim leży. Run spoza projektu zostaje ścieżką absolutną.

Klucz podkładu, gdy będzie: `config/viz_basemap.local.toml`, pole `key`. Plik jest w `.gitignore`. Klucz nie może zawierać spacji ani znaków `/?#&=`. URL to kafelki CARTO Dark Matter `dark_nolabels`. Atrybucja: `© OpenStreetMap contributors © CARTO`. Sam HTTP 200 bez klucza nie jest mapą: serwer oddaje kafelek z napisem o braku klucza. Dlatego brak poprawnego klucza zostawia zdanie „Podkład wyłączony.”

## Indeks

Format `1` w `meta.json`. Budżet pliku: poniżej 200 MB. Budżet tablic w RAM, sprawdzany przez silnik: poniżej 1 GB. R6 na dysku: plik `index.npz` 12 051 495 B, budowa 22,418 s. Tablice w RAM przy checku silnika: 89 497 631 B. Dwa pomiary klatki szczytu: 0,008 s i 0,007 s.

Indeks powstaje przy pierwszym otwarciu silnika albo okna. `viz_engine.load` woła `viz_index.run`. Plik jest świeży, gdy `checked` jest prawdziwe, format to 1, a sha256 eventów, sieci i skryptu `viz_index.py` zgadzają się z `meta.json`. Zmiana indeksera przebudowuje indeks. Zmiana odtwarzacza nie.

Wejście:

- `output_events.xml.zst`,
- `output_network.xml.zst`,
- `output_config.xml` tylko po `sampleSize` (pierwsze `name="sampleSize"`).

Eventy ruchu: `vehicle enters traffic`, `entered link`, `left link`, `vehicle leaves traffic`. Semantyka jest kopią `g6_bake.py`, z indeksem linku na węźle.

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

Te stałe (przejazdy, wjazdy 6–9, oba szczyty, linki, węzły, obecność pięciu liter) są wpisane w `viz_index.py` jako akceptacja katalogu o nazwie `g5r6_25pct_s4711`. Inny katalog przechodzi test geometrii bez tych liczb.

Test geometrii indeksera: seed 1, trzy przejazdy dłuższe niż 8 węzłów, osobny odczyt eventów, 20 chwil, pozycja nie dalej niż 0,5 m od cięciwy linku z eventów. To test pozycji na cięciwie. Łamana okna go nie dotyczy i nie powinna go ruszać.

## Silnik klatki

`pipeline/viz_engine.py` czyta `viz/` albo pozwala indekserowi go zbudować. Nie rysuje. Nie otwiera XML sam. Zwraca klatkę: `xy`, `heading`, `speed`, `link`, `cls`, `track`.

Pozycja: liniowo między węzłami, których czasy obejmują `t`. Przy `dt = 0` zostaje późniejszy węzeł. Link w trakcie odcinka to link wcześniejszego węzła, a w chwili węzła końcowego link tego węzła.

Prędkość odcinka: jeśli `knot_len` końca > 0, to ta długość / `dt`, inaczej długość cięciwy / `dt`. `dt` poniżej 0,001 s liczy się jak 0,001 s. Sufit 30 m/s. Kierunek: `atan2` pierwszego niezerowego odcinka od bieżącego wstecz. Samotny węzeł ma kierunek 0 i prędkość 0.

Klik auta i klik cięciwy są w silniku. Klik po łamanej jest w `viz_player/curves.py` i używa tej samej geometrii „najbliższy odcinek”.

## Co okno wysyła do strony

Jedna klatka to JSON z `Api.frame`: czas, zegar, liczba aut, tablice `lon`, `lat`, `v` (m/s), `hd` (radiany), `heavy` (1 dla `h`), indeks zaznaczonej kropki, ślad (`path`: pary szerokość–długość), indeks zaznaczonego linku, punkt śledzenia `pan`, panel.

Długości i szerokości są obcięte do 6 miejsc, prędkość do 3, kąt do 4. `NaN` w tym JSON jest błędem (`allow_nan=False`).

Mostek pywebview, metody `Api`: `frame`, `pick`, `classes`, `lookup`, `select`, `follow`, `clear`.

## Podkład

Bez `config/viz_basemap.local.toml` mapa jest tłem `#121418`, drogi i auta na kanwie, na pasku zdanie „Podkład wyłączony.” Klucz dokłada Michał później. Do tego czasu kafelków nie ma, i tak ma być.

## Testy

Nie ma pytest. Każdy kawałek ma self-test na assertach. Syntetyczne eventy muszą mieć jeden event na linię. Na Windows `np.load` trzeba zamknąć, zanim kasuje się `index.npz`.

```
uv run python pipeline/viz_index.py --self-test
uv run python pipeline/viz_engine.py --self-test
uv run python -m viz_player --self-test
uv run python pipeline/viz_index.py output/g5r6_25pct_s4711
uv run python pipeline/viz_engine.py output/g5r6_25pct_s4711
uv run python -m viz_player --check output/g5r6_25pct_s4711
uv run python -m viz_player --smoke output/g5r6_25pct_s4711
```

Self-test okna buduje mini-run w katalogu tymczasowym (sieć bez `origid`, więc log `łamane: brak origid; cięciwy`), sprawdza zegar, próbkę `0,25`, rampę, oś, filtr `t`, klik auta i drogi, prefiks id oraz to, że szablon nie zawiera `tile.openstreetmap.org`, `iterparse`, `etree`, `zstandard`, `PySide` ani `g6_bake`. Te słowa wolno mieć w `curves.py`, bo self-test ogląda `player.py` tylko do funkcji `_forbid`, plus `shell.html` i `__main__.py`.

`--check` jest pod R6. Wymaga próbki `0,25`, strony poniżej 1,2 MB, szczytu zgodnego z `meta.json`, klatki 849 o `07:56:31`, mniejszej klatki bez `t`, osi `r6510903_5` i łamanej `1807611370009f`. Ostatni zielony wpis w `player.log`: `lamane=4705 bend=11`, osie `52.2307N 19.3633E`. Inny run na tym poleceniu padnie, choć okno da się nim otworzyć.

`--smoke` otwiera prawdziwe okno WebView2, czeka aż namalowane łamane przekroczą 100 (liczy linki z co najmniej trzema punktami, także poza kadrem), rysuje klatkę 07:56, klika ukrycie panelu, chip `t` i start, robi zrzut i sprawdza oś `r6510903_5`. Zrzut nadpisuje `docs/research/wizualizer_okno.png`. To pauza 07:56, nie stan tuż po otwarciu (otwarcie jest o 06:00). Ostatni zielony smoke: `n=849`, bez `t` 447, mapa `1106x811`. Smoke runu bez łamanych nie przejdzie progu 100.

Check silnika na tym samym runie, osobny log `engine.log`: pełna klatka szczytu 961, bez `t` 420, lookup `r6510903_5` (2 przejazdy), czynności `c1002062_103` zawierają `home` i nie zawierają `car interaction`.

Kod wyjścia 0: test przeszedł. 1: test albo brak plików runu. 2: uruchomienie bez ścieżki i bez zapisanego stanu.

## Odłożone

Zostaje, aż będzie osobne zlecenie: klucz CARTO, drugi run obok siebie, spięcie z `g6_bake.py`, Łódź, łamane w konwerterze Javy, przebudowa sieci. Dalszy kierunek zapisany przy D24 to poprawki GUI i podstawowe funkcje okna. Akceptacji obrazu przez człowieka ten dokument nie zalicza.
