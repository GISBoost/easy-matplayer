# Wizualizer — recenzja niezależna

Data: 2026-10-20. Recenzja `wizualizer_koncepcja.md`. Żaden punkt nie jest wybrany. Ta notatka nie zmienia zakresu i nie jest wpisem do `DECISIONS.md`.

Źródła, które sprawdziłem w repozytorium i na dysku, a nie w poprzedniej rozmowie: `pipeline/g6_bake.py`, `pipeline/plans.py`, `pipeline/convergence.py`, `matsim/src/main/java/org/matsim/kutno/CreateKutnoNetwork.java`, `docs/research/G6_blender.md`, `README.md`, `reports/etap2/g5_kalibracja/g5_r6_ref.md`, pliki `output/g5r6_25pct_s4711/`, `output/g6_blender*/`, `output/f6_100pct/output_events.xml.zst`, dokumentacja SimWrapper (events viewer, stan strony na 2026-10-20), strona funkcji Via (Simunto, 2026).

## Co w notatce jest trafne

Cel się broni. Program ma czytać gotowy run i nic nie zapisywać do MATSim. Cztery wymagania (lekkość odtwarzania, inspekcja, współczesny wygląd, obsługa bez instrukcji) są wymogiem użytkownika, nie hipotezą agenta.

`g6_bake.py` naprawdę robi to, co opisuje notatka: cztery typy eventów, interpolacja wzdłuż cięciwy, `relativePosition` przy wjeździe, prędkość z długości linku (nie z cięciwy), sufit 30 m/s, origin `(524805, 485023)`, test trzech tras i próg 0,5 m. Gęsta tablica `pos` o kształcie klatka × przejazd × xy jest w `vehicles.npz`. Sieć w tym pliku to cięciwy.

SimWrapper zostaje przy dashboardach. Podgląd eventów jest na stronie docs opisany jako eksperyment: wolne ładowanie `output_events.xml.gz`, brak YAML, brak osadzenia w dashboardzie. Nasze eventy są w `.zst`, więc ten podgląd i tak nie bierze pliku wprost.

Via ładuje sieć i eventy i animuje warstwę pojazdów. Publiczny opis (stan strony features, 2026) obejmuje też atrybuty sieci, aktywności agentów, select-link, porównania i zrzuty. Tego player v1 nie musi powtarzać. Dekompilacja nic tu nie wnosi.

WebView2 na tej maszynie jest: runtime `155.0.4283.62`. To fakt o instalacji, nie argument za stosem.

Sieć nie ma łamanych OSM. `CreateKutnoNetwork` zapisuje węzły i linki. Atrybut `type` (klasa drogi OSM) i `origid` (id way) w pliku runu są. Atrybutu nazwy ulicy nie ma: 0 linków z nazwą.

## Fakty, które notatka miesza

Liczby 4 822 przejazdy, około 755 aut naraz, bake około 12 s i plik około 33 MB pochodzą z bake'u D16 (`docs/research/G6_blender.md`, run `output/d16_25pct_s4711`). Tego runu już nie ma na dysku (`output_events.xml.zst` brak). Przypisanie tych liczb do R6 25% jest błędne. Test trzech tras z tamtego bake'u nie jest dziś powtarzalny.

Zmierzony run referencyjny `output/g5r6_25pct_s4711`:

| wielkość | pomiar 2026-10-20 |
|---|---|
| `output_events.xml.zst` | 46 813 676 B (44,6 MB) |
| `output_network.xml.zst` | 363 931 B |
| eventy razem | 4 261 936 |
| czas eventów | 14 s … 116 589 s (około 32,4 h) |
| `vehicle enters traffic` | 29 660 (tyle samo, co nogi car w `g5_r6_ref.md`) |
| wjazdy w 06:00–09:00 | 6 641 |
| eventy ruchu (4 typy) | 3 787 376 |
| `actstart` / `actend` | po 88 980 |
| max aut naraz, cała doba | 961 o czasie 58 170 s (16:09) |
| max aut naraz w 06:00–09:00 | 849 o czasie 28 591 s (07:56) |
| węzły / linki w sieci runu | 4 534 / 10 383 |

Udział linii eventów ruchu według pierwszej litery id pojazdu: `t` 2 220 570, `h` 769 806, `r` 367 902, `c` 310 004, `o` 119 094. Nogi z tabeli referencji: tło lekkie 16 439, ciężkie 5 743, reszta (dwie nogi na osobę) 7 478. Lekkie tło jest większością ruchu. Filtr „trzech klas” z notatki (mieszkaniec, przyjeżdżający, `h…`) pomija `t` i `o`.

Identyfikatory z `pipeline/plans.py`: `r` mieszkaniec, `c` przyjeżdżający, `o` wyjeżdżający, `t` tło lekkie, `h` ciężkie. Id pojazdu = id osoby. `subpopulation` osób z planu to `person` / `tlo` / `ciezkie` i nie rozdziela r/c/o. Litera id rozdziela.

Sieć F2 w `README.md` to 4 453 węzły i 10 296 linków. Sieć w outputcie R6 jest większa (pomiar wyżej). Do playera bierze się sieć z runu, nie liczbę z F2.

Rozmiary gęstych npz (to bake D16, opis w `G6_blender.md`):

| plik | bajty |
|---|---|
| `output/g6_blender/vehicles.npz` (06–09, krok 5 s) | 33 741 907 |
| `output/g6_blender_day/vehicles.npz` | 58 638 417 |
| `output/g6_blender_day20/vehicles.npz` (do 20:00, krok 10 s) | 251 324 769 |
| `output/g6_blender/network.npz` | 65 692 |

Notatka pisze 32 MB i 240 MB. Dokument G6 pisze 33 MB i 250 MB. Pliki są po stronie dokumentu G6. Pole `hw` w `network.npz` to tekst atrybutu `type`, nie szerokość jezdni (`g6_bake.py` wkłada tam piąte pole krotki linku).

Eventy F6 100% ważą 61 776 940 B. To starszy MVP, bez tła R6. Nie wolno z tego pliku wyliczać „R6 × 4”.

`sampleSize` w `output_config.xml` tego runu wynosi 0,25. Ten sam odczyt co `pipeline/convergence.py` (`name="sampleSize"`). W pliku jest też wcześniejsze `flowCapacityFactor` 1,0 z innego modułu. Pasek stanu ma brać `sampleSize`, nie pierwszą lepszą przepustowość.

Aktywności są w tym samym pliku eventów. Próbka: `actend` z `actType="home"`, `actstart` z `actType="car interaction"`. Cztery typy ruchu aktywności nie niosą. Osobny odczyt planów do prostego harmonogramu nie jest potrzebny. `car interaction` to dojście teleportem, nie czynność do pokazania jako praca.

Zegar nie mieści się w 0–24. Ostatni event jest po 32 h. W configu widać więcej niż jedno `endTime` (w tym 30:00:00 i 48:00:00). UI bierze zakres z indeksu.

Sufit „dziesiątki MB” dla rzadkiego indeksu doby R6 25% jest za niski. Same węzły: 3 787 376 zdarzeń ruchu × około 20 B (czas, x, y, długość, indeks linku) ≈ 76 MB, plus identyfikatory i kubełki. Uczciwy budżet tego runu to rząd 100–150 MB. Nadal jest lekki przy gęstej tablicy: sama pozycja doby R6 co 5 s to rząd 5 GB nieskompresowanych (23 tys. klatek × 29 660 × 8 B). Ściana skali jest prawdziwa. Liczba przy niej była zbyt optymistyczna.

Rysowanie Kutna nie jest ścianą. Szczyt to 961 aut. Kilkadziesiąt tysięcy aut naraz to hipoteza o Łodzi, nie pomiar z tego projektu. Argument „1–2 MB na klatkę przy 50 tysiącach” jest rachunkiem binarnym (50 000 × kilkanaście bajtów), nie pomiarem mostu do okna. JSON albo wywołanie metody na każde auto ten rachunek psuje.

## Punkt po punkcie

### 1. Czy w ogóle ruszamy

Propozycja (nie pisać kodu, aż będzie wpis w `DECISIONS.md` i zamknięte punkty 2–6) broni się jako reguła repozytorium. MVP w `CLAUDE.md` wizualizer wyklucza. Konsekwencja startu kodu w `pipeline/` albo `matsim/` bez wpisu: zakres puchnie w miejscu, które jest źródłem prawdy, a lokalny eksperyment zaczyna wyglądać jak faza.

Konsekwencja czekania: nic nie stoi na dysku poza notatkami. Run R6 jest, więc po wpisie indeks można policzyć od razu.

Zostawiłbym próg. Plan w `wizualizer_plan.md` jest właśnie po to, żeby po wyborze nie projektować od zera. Kodu playera tu nie ma.

### 2. Co jest produktem

(a) lokalny player z inspekcją, (b) kolejne filmy, (c) tylko SimWrapper.

Przy wymogu inspekcji (b) i (c) produktu nie dają. Blender jest niemy: klatka jest obrazem, klik nic nie zwraca. SimWrapper liczy agregaty, które już są w `output/g5r6_25pct_s4711/analysis/` i w dashboardach. Eksperymentalny podgląd eventów nie jest odtwarzaczem tego repozytorium.

Konsekwencja (a): drugi program obok filmów. Żeby się nie rozjechały, semantyka czterech typów ma być jedna. Unifikacja kodu z `g6_bake.py` w pierwszym kroku jest ryzykowna dla działających filmów. Bezpieczniej: player ma własny indeks o tej samej geometrii, bake zostaje, a wspólna funkcja jest osobnym krokiem, gdy test 0,5 m przechodzi po obu stronach.

Rekomendacja recenzenta: (a). Blender i SimWrapper zostają przy swoich rolach.

### 3. Co potrafi pierwsza wersja

Sam suwak jest sprzeczny z wymogiem inspekcji. Pełne Via (select-link historyczny, dwa runy, wykres doby, podkład, edycja) jest osobnym produktem.

Propozycja notatki (mapa, czas, szukanie, klik auta, klik linku, trzy klasy, bez harmonogramu) jest prawie dobra i ma dwie dziury.

Dziura pierwsza: trzy klasy. Na R6 większość linii ruchu to `t`. Bez przełącznika tła nie da się obejrzeć mieszkańców. Wyjeżdżający `o` też znikają z filtra albo wpadają w złą szufladę. Konsekwencja zostawienia trzech klas: inspekcja G5 jest ślepa na warstwę, którą G5 właśnie dodało.

Dziura druga: brak aktywności w v1. Między nogami auto znika z sieci (praca, koniec tła). Bez `actstart`/`actend` wygląda to jak błąd odtwarzacza. Te eventy są w tym samym pliku i w tym samym przebiegu indeksu. Harmonogram w panelu wybranego id (lista czynności, bez `car interaction`, bez wykresu doby) jest tani. Wykres całego dnia i porównanie dwóch runów zostają poza v1.

Klik linku „ile aut i jaka prędkość teraz” wymaga, żeby indeks trzymał id linku na węźle. Bake tego nie zapisuje. To jest rozszerzenie danych, nie nowy ekran.

Rekomendacja: v1 = mapa, czas, szukanie id, klik auta (id, klasa, prędkość, link, śledzenie), klik linku (liczba i prędkość teraz, typ drogi, freespeed), pięć klas domyślnie włączonych, lista czynności wybranego id. Bez drugiego runu i bez wykresu doby.

### 4. Stos okna

Goły pyglet/moderngl i Dear ImGui spełniają lekkość i nie spełniają wyglądu, o który chodzi po obejrzeniu Via. Domyślny Qt wygląda jak szary krewniak Via, dopóki ktoś nie narysuje motywu. To trafne.

WebView2 jako „najtaniej współczesny” jest hipotezą o koszcie CSS, nie o koszcie klatki. Na tej maszynie runtime jest. Wiązanie, które jest pod ręką (`pywebview` i podobne), woła skrypt mostem COM. Dokumentacja WebView2 mówi wprost, że częste wołania obiektów hosta są wolniejsze niż jedna wiadomość, a duże bufory idą przez `PostSharedBufferToScript`. Tego API typowe `pywebview` nie owija. Konsekwencja przyjęcia WebView2 bez próby: ładny panel i kopiowanie klatki jako JSON. Przy 961 autach Kutno to jeszcze wytrzyma. Przy Łodzi albo przy 30 Hz z identyfikatorami do pickingu most staje się drugą ścianą, obok tej, której chcieliśmy uniknąć.

Druga konsekwencja: użytkownik wcześniej odrzucił przeglądarkę. WebView2 jest oknem systemowym z silnikiem Edge, nie kartą Chrome. Trajektorie mogą zostać w Pythonie. To nadal silnik przeglądarki. Jeśli „nie przeglądarka” znaczy „nie Chromium”, ta propozycja odpada niezależnie od wydajności.

Qt (PySide6) w tym samym procesie, rysowanie mapy w OpenGL, panel jako zwykłe kontrolki z ciemnym arkuszem: klatka nie przekracza granicy procesu, picking zostaje w NumPy, instalator jest ciężki (to użytkownik dopuszcza), wygląd jest pracą, nie prezentem od CSS. Konsekwencja: bez świadomego arkusza wyjdzie Via. Arkusz jest częścią v1, nie kitem później.

Rekomendacja: nie zamykać stosu na papierze. Po wyborze produktu jeden krótki spike gitignored, dwa okna, ta sama klatka 5 000 punktów, 30 Hz, klik. Zostaje to, które trzyma pamięć i daje się ostylować. Mój typ przed spike'iem: PySide6 i rysowanie w procesie. WebView2 tylko jeśli spike pokaże binarny bufor i wygląd, a użytkownik uzna okno Edge za lokalne.

### 5. Format indeksu

Gęsty npz zostaje przy Blenderze. Dla playera jest ślepą uliczką (pomiar doby D16: 251 MB skompresowane do 20:00 przy 11 836 przejazdach; R6 ma 29 660 przejazdów i dłuższy zegar).

Rzadki indeks się broni. Konsekwencja złego formatu: drugi przebieg XML przy każdym otwarciu albo zmiana formatu przy pierwszym pełnym dniu. Jedno i drugie psuje wymóg „dużo symulacji”.

Kubełki 30–60 s są optymalizacją skoku. Przy 30 tysiącach przejazdów wektorowy `searchsorted` też jest szybki. Kubełki warto mieć, bo suwak ma reagować od razu. Nie są one powodem, żeby ciąć indeks do okna 06–09.

Indeks ma leżeć w katalogu runu (`output/.../viz/`), który i tak jest w `.gitignore`. Osobna kopia w repo nie ma po co powstawać.

Rekomendacja: rzadki indeks całego pliku eventów, semantyka pozycji jak w `g6_bake.py`, dodatkowo id linku na węźle i czynności poza `car interaction`. Gęsty npz bez zmian.

### 6. Pierwszy run i okno

R6 25%, seed 4711, jest właściwym pierwszym obrazem: to baza referencyjna, pliki są na dysku, tło i ciężkie widać. Okno 06:00–09:00 jest właściwym pierwszym kadrem, bo wtedy jest poranny szczyt (849 aut).

Konsekwencja zapisania w indeksie tylko tego okna: pełna doba, popołudnie (szczyt 961 jest o 16:09) i powrót z pracy wymagają drugiego formatu albo drugiego pliku. Notatka sama chce, żeby format przyjął dobę. Najprościej spełnić to od razu: indeks = cały plik, player otwiera się na 06:00.

Liczby 4 822 / 755 nie mogą być kryterium akceptacji. Kryterium z tego pomiaru: 29 660 przejazdów, 6 641 wjazdów w oknie 6–9, szczyt 961 i 849.

100% na start utrudnia pierwszy obraz i nie ma tu runu R6 100%. F6 100% jest innym modelem.

Rekomendacja: indeks całego `g5r6_25pct_s4711`, player startuje w 06:00–09:00, format bez osobnej wersji „porannej”.

### 7. Filtr klas

Sam kolor prędkości jest czytelny i nie rozdziela warstw G5. Trzy przełączniki z notatki są za ciasne (punkt 3).

Pięć przełączników jest tanich, bo klasa jest w pierwszym znaku id. Konsekwencja piątki: pasek ma pięć chipów. To nadal mało. Domyślnie wszystkie włączone, żeby obraz startowy był całym runem. Wyłączenie `t` jest gestem, dla którego ten filtr istnieje.

Klasa nieznana (gdyby kiedyś doszedł inny prefiks) idzie do szuflady „inne”, widocznej, a nie odrzucanej po cichu.

Rekomendacja: pięć klas, kolor prędkości zostaje (rampa jak w `blender/g6_load.py`: 0 m/s czerwień, 40% ze skali bursztyn, 14 m/s = 50 km/h cyjan; szybciej ten sam cyjan). Skala bezwzględna, z legendą. Stosunek do freespeed jest lepszy do korka i gorszy jako pierwszy obraz, bo wymaga legendy „udział prędkości swobodnej”. Zostawiłbym go na później.

### 8. Geometria dróg

Cięciwy wystarczą do inspekcji korka i są tym, co MATSim naprawdę jechał. Łamane OSM są zmianą `CreateKutnoNetwork` i osobną decyzją. Konsekwencja zrobienia ich w playerze „z boku”: obraz ładniejszy niż symulacja, klik w łuk trafia w geometrię, której QSim nie używał.

Czego notatka nie mówi: atrybut `type` jest na 10 383 linkach (residential 3 631, unclassified 2 864, tertiary 2 149, primary 882, secondary 367, living_street 308, motorway 95, łącznice, 2 zawrotki graniczne). Jednym kolorem cięciwa jest plątaniną. Kolor klasy drogi nic nie pobiera z OSM i nie udaje pasów. `permlanes` jest na elemencie linku. Szerokość z liczby pasów na v1 kłamie podobnie jak kostka ×8: zostawić stałą grubość na ekranie.

Rekomendacja: v1 na cięciwach, kolor według `type`, szerokość umowna. Łamane dopiero, gdy obraz idzie poza projekt, i wtedy w konwerterze sieci.

### 9. Podkład mapy

Ciemne tło bez kafelków jest lżejsze, szybsze i nie ciągnie licencji ani zamiany EPSG:2180. To się broni.

Zdanie „nazwy dróg przy zbliżeniu, jeśli atrybut jest” odpada po pomiarze: atrybutu nie ma. `origid` pozwala kiedyś dociągnąć `name` z PBF. To osobny przebieg, osobna licencja (ODbL) i osobna decyzja. Obiecywanie nazw w v1 jest obietnicą bez danych.

Orientacja na v1: kolor klasy drogi, podziałka, zegar, przy zbliżeniu id linku po kliknięciu. A1 widać jako `motorway`, nie jako podpis.

Rekomendacja recenzenta była: v1 bez podkładu i bez nazw. Użytkownik 2026-10-20 wybrał inaczej: prosty ciemny podkład OSM, Leaflet albo kafelki, bez nazw ulic. Realizacja jest w planie (CARTO Dark Matter `dark_nolabels`, atrybucja, klucz lokalnie, nie serwer `tile.openstreetmap.org`). Ta rekomendacja już nie obowiązuje.

### 10. Jak pokazać próbkę

Dorysowanie aut do 100% kłamie i psuje inspekcję (klik w auto, którego nie ma w eventach). Podpis ułamka nic nie kosztuje, jeśli ułamek jest z `sampleSize`, nie z nazwy katalogu. Konsekwencja twardej „25%” w kodzie: run 10% i 100% dostaną zły pasek.

Rekomendacja: rysować tyle, ile jest w eventach. Pasek: wartość `sampleSize` tym samym odczytem co `convergence.py`. Brak parametru: pokazać „próbka nieznana”, nie zgadywać.

### 11. Gdzie mieszka kod

Drugi, cichy odczyt eventów rozjedzie film i player. Konsekwencja wspólnej edycji `g6_bake.py` w tym samym kroku co pierwsze okno: film, który już jest, zależy od ubocznego kształtu npz (`hw` jako tekst typu).

Rekomendacja: po wpisie D indekser jako `pipeline/viz_index.py` (albo paczka obok, ale jeden generator indeksu). Player jako osobny lokalny program, uruchamiany `uv run`, bez zmian w `matsim/`. Bake Blendera nietknięty, aż test geometrii przejdzie i ktoś świadomie spnie oba wejścia. Java bez zmian. Indeks tylko pod `output/`.

## Czego notatka nie pokrywa, a wdrożenie tak

- Jeden id ma kilka przejazdów (tam i z powrotem, albo jedna noga tła). Szukanie zwraca wszystkie. Śledzenie bierze ten, który o czasie `t` jest w sieci, a między nogami pokazuje czynność.
- Zdarzenia `walk` są teleportem. Player ich nie rysuje jako jazdy. Inaczej „auto” jedzie chodnikiem, którego w sieci car nie ma.
- Picking: auto wygrywa z linkiem w promieniu kilku pikseli. Liczy go silnik.
- Skok suwaka wstecz nie skanuje XML. Albo kubełek, albo `searchsorted` po indeksie.
- Otwarcie drugiego runu zwalnia poprzedni indeks. Dwa runy obok siebie są poza v1 i podwoiłyby budżet pamięci.
- Skróty z notatki (spacja, strzałki, śledzenie, czyszczenie) są częścią łatwości użycia. Bez nich zostaje sam suwak.
- Rozmiar auta na ekranie jest w pikselach i rośnie razem z odwrotnością zoomu tylko o tyle, żeby z widoku powiatu auto nie znikło. To konwencja, jak `--car-scale 8` w G6. Nie jest szerokością pojazdu z `vehicleType` (osobowy 7,5 m, ciężki 15 m w `plans.py`). Ciężki może być odrobinę większym glifem. To nadal umowa.
- Pierwszy ekran, który zobaczy człowiek, ma ciemny motyw od razu. Jasny domyślny Qt albo domyślna strona HTML mija się z wymaganiem wyglądu i z `plt.style.use("dark_background")`.
- Błąd indeksu (ucięty zst, brak sieci, sha niezgadza się z eventami) ma być zdaniem na ekranie, nie wyjątkiem w konsoli jako jedyną odpowiedzią.

Plan kroków, format pliku, testy i lista braków: `wizualizer_plan.md`.
