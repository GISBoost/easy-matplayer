# Błysk aktywności i obciążenie linków: plan (2026-10-31)

Dwie funkcje odtwarzacza, obie w kliencie wspólnym dla aplikacji i wersji web (`viz_player/shell.html`, `engine.js`):

- **A. Błysk aktywności.** Gdy osoba zaczyna aktywność (event `actstart`), w tym miejscu na mapie pojawia się krótki błysk, jak w Via.
- **B. Obciążenie linków.** Kolor drogi zależy od prędkości względem swobodnej albo od natężenia względem przepustowości, zamiast od samej klasy drogi.

Kolejność: A, potem B. Obie są niezależne i każda to osobne kroki z własnymi commitami.

## Co już jest w danych (zmierzone 2026-10-31 na demo Kutno 25%)

| Fakt | Wartość |
|---|---|
| Zdarzenia aktywności w `index.npz` (`act_t`, `act_kind`, `act_type`, `act_id`, `act_x`, `act_y`) | 48 608 (24 304 starty, 24 304 końce), 20 565 osób |
| Typy (`act_type_legend`) | `home` 3 739, `work` 3 739, `tlo_start`/`tlo_end` 16 826 (ruch tła, techniczne) |
| Szczyt startów | 57 na minutę, 641 na 15 minut (o 16:00) |
| W eksporcie dla klienta (`viz_export.py`, format 1) | **nie ma**: tylko trasy i węzły aut |
| Klient liczy dziś | pozycję, prędkość i link auta w klatce (`Engine.frame`), liczbę aut i średnią prędkość jednego linku (`linkNow`) |
| W indeksie na link | `link_length`, `link_freespeed`, `link_type`; **brak** `capacity`, liczby pasów i `capperiod` |
| `output_config.xml` runu | `flowCapacityFactor` 0,25 i `sampleSize` 0,25 (sieć ma pełne przepustowości, skalowane w symulacji) |
| Prędkości odtwarzania | 1×, 10×, 60×, 300× |

Wniosek: A potrzebuje tylko nowych kolumn w eksporcie (dane już są w indeksie). B potrzebuje atrybutów linków z sieci, a statystyki liczy klient z węzłów, które i tak ma w pamięci.

## Ograniczenia, których plan pilnuje (CLAUDE.md)

- Błysk to **zdarzenie z pliku**: czas i współrzędne `x`, `y` z `actstart`. Nie rekonstruujemy dojścia pieszo. Auto znika przy `vehicle leaves traffic`, a błysk pojawia się później, bo MATSim dokleja teleportowane `walk` po nodze `car`. Ten odstęp jest prawdziwy i zostaje.
- Błysk pokazuje aktywności **wszystkich** osób z eventów, także tych, które jadą innym trybem niż auto i nie mają pojazdu na mapie. W demo są tylko nogi `car`, więc tam to się nie rzuca w oczy, ale dla runu z PT i pieszymi zdarzają się błyski bez auta. Opisać w README.
- Nazwy typów aktywności zależą od scenariusza (`home`, `work`, `home_600`, `tlo_start`). Kolory i filtr budujemy z legendy runu, nic z Kutna nie wchodzi do kodu biblioteki.
- B: wskaźnik to przybliżenie z eventów, nie „stan sieci”. Linki bez ruchu w oknie są szare, nie zielone („brak ruchu” to nie „swobodnie”). Wszystkie pojazdy liczone jako 1 PCE (pojazdy PT mają w MATSim większe PCE); do opisania.
- Zmiana formatu eksportu i indeksu przebudowuje cache sama (`FORMAT`, skrót skryptu w kluczu).

## A. Błysk aktywności

### Wygląd i zachowanie

- Rozszerzający się pierścień i jasny rdzeń, przezroczystość maleje do zera, promień rośnie od ok. 4 do ok. 24 px (px, nie metry: błysk ma być widoczny przy każdym zoomie).
- Kolor wg typu aktywności (stała paleta, nieparzyste typy z haszu nazwy; znane prefiksy `home`/`work`/`edu`/`shop`/`leis` dostają stałe kolory, reszta rotuje po palecie). Dodatkowo legenda typów w panelu z checkboxem na typ, żeby wyłączyć np. techniczne `tlo_*`.
- Domyślnie tylko **starty**. Końce aktywności (`actend`) są w eksporcie (potrzebuje ich też W3, oś harmonogramu osoby), a rysowanie ich to ewentualny przełącznik później.
- Czas życia błysku liczony w czasie ściennym, przeliczony na czas symulacji mnożnikiem odtwarzania: `życie_sym = clamp(1,5 s × mnożnik, 3 s, 450 s)`. Czyli 1,5 s na ekranie przy 10×, 60×, 300×, a przy 1× dolna granica 3 s symulacji. Animacja jest czystą funkcją `t` i mnożnika, więc przewijanie suwakiem działa, a przy pauzie błyski stoją zamrożone w swojej fazie.
- Szczyt w demo: 641 startów na 15 minut, przy 300× (450 s życia) to ok. 320 błysków naraz. Dla dużych runów (100%, Łódź) limit liczby narysowanych błysków (np. 5 000 najnowszych) i komunikat w panelu przy przycinaniu.
- Mieszanie addytywne (jasność dodaje się, gdy błyski nachodzą na siebie). Wymaga sprawdzenia w deck.gl 9.4 przy `MapboxOverlay` nieprzeplatanym (patrz ryzyka).

### Zmiany w danych

1. `pipeline/viz_export.py`, **FORMAT 1 → 2**. Do każdej porcji (15 min) dochodzą zdarzenia aktywności z czasem w `[t0, t1)`, posortowane po czasie:

   | kolumna | typ | opis |
   |---|---|---|
   | `act_t` | `<f4` | czas zdarzenia |
   | `act_dlon`, `act_dlat` | `<f4` | przesunięcie od `origin_lonlat`, ten sam przeliczony układ co węzły |
   | `act_type` | `<u2` | kod z legendy |
   | `act_kind` | `u1` | 1 = start, 0 = koniec |
   | `act_person_i` | `<i4` | indeks do `persons.json` |

   Nowa liczność kolumn `"a"` (liczba zdarzeń w porcji) w `CHUNK_COUNTS`. Manifest dostaje `act_types` (legenda: lista nazw w kolejności kodów). Rozmiar dla demo: 48,6 tys. × 19 B = ok. 0,9 MB razem, więc ok. +1% strony web.
2. `viz_player/engine.js`: `counts()` zna `"a"`; `Engine.load` przyjmuje format 1 i 2 (przy 1 funkcja błysku jest wyłączona, bo brak kolumn).

### Silnik

`Engine.flashes(t, life, startsOnly, typeMask)` zwraca bufory (bez alokacji co klatkę) ze zdarzeniami z `(t − life, t]`: dla porcji `ci−1` i `ci` wyszukiwanie binarne po `act_t`, przefiltrowanie `act_kind` i maski typów. `Engine.want` zamawia dodatkowo porcję `ci−1`, gdy błyski są włączone (życie ≤ 450 s < 900 s, więc jedna wstecz wystarcza).

### Klient

- Przełącznik „Błyski aktywności” (domyślnie włączony) i lista typów z kolorami w panelu (obok „Klasy”). Napisy w `i18n.py` (EN) i `T()`.
- Warstwa `ScatterplotLayer` z buforami binarnymi (`getRadius`, `getFillColor`, `getLineColor` jako atrybuty wyliczane z wieku), dwa przebiegi: pierścień (`stroked`) i rdzeń. Rysowana pod autami, nad drogami i budynkami.
- Działa tak samo w aplikacji i na stronie. Web: opcjonalna lista wyłączonych typów w `web/scenarios.json` (`flash_off`), bo w demo 69% startów to `tlo_end` na granicy sieci.

### Kroki i dowody

| Krok | Zakres | Dowód |
|---|---|---|
| F0 spike | addytywne mieszanie w deck.gl 9.4 nieprzeplatanym; koszt 500 i 5 000 błysków w klatce | czas klatki (ms), zrzut |
| F1 | eksport format 2, odczyt w kliencie | test w `test_export.py`: kolumny wracają bajt w bajt; liczba startów w porcjach = liczba w indeksie (24 304 w demo) |
| F2 | `Engine.flashes` | test węzłowy (`test_engine.py`): okno czasu, granica porcji, maska typów; porównanie z niezależnym skanem eventów (jak `scan_check`) dla 20 chwil |
| F3 | UI i rysowanie | `--smoke`: liczba narysowanych błysków w chwili T równa liczbie startów w oknie ze skanu; zrzut okna i strony web |
| F4 | dokumentacja | `README*`, `docs/viz/README_pl.md`, `wizualizer_postep.md`, opis eksportu w `docs/research/wizualizer_odtwarzacz.md` |

## B. Obciążenie linków

### Wskaźniki (okno ostatnich W minut symulacji, domyślnie 5)

Z węzłów trasy bierzemy **pełne przejazdy linku**: węzeł „wyjazd z linku” (`knot_len > 0`) poprzedzony węzłem „wjazd na link” tego samego przejazdu i tego samego linku. Pomijamy przejazdy zaczynające się od `vehicle enters traffic` (częściowy link). Czas przejazdu `tt` to różnica czasów węzłów, czyli z kolejką i czekaniem na skrzyżowaniu. Przejazd liczy się w oknie czasem wyjazdu.

| Tryb | Wzór | Skala koloru |
|---|---|---|
| **Prędkość** | `v = Σ długość / Σ tt` (średnia przestrzenna), `r = v / freespeed` | czerwony `r ≤ 0,3` → żółty `0,6` → zielony `r ≥ 0,9` |
| **Natężenie** | `q = n / W` (poj/h), `q / (capacity × flowCapacityFactor)` | jasny `0` → pomarańcz `0,5` → czerwony `≥ 1` (sufit 1,2) |
| Typ drogi | jak dziś | jak dziś |

- Link bez przejazdu w oknie: szary „brak ruchu”, w obu trybach.
- Natężenie jest **w skali próbki**: przepustowość sieci jest pełna, a symulacja ją skaluje przez `flowCapacityFactor`, więc dzielimy przez `capacity × flowCapacityFactor`. Nie ekstrapolujemy do pełnej populacji. Gdy `flowCapacityFactor` nie ma w configu, tryb natężenia jest wyłączony z komunikatem (nie zgadujemy 1).
- Prędkość swobodna z `freespeed` linku. Okno 1, 5 lub 15 minut (przełącznik).

### Zmiany w danych

1. `pipeline/viz_index.py` (`read_network`): do indeksu `link_capacity` (poj/h znormalizowane do godziny z `capperiod` sieci), `link_lanes`; `meta`: `flow_capacity_factor` z configu. **FORMAT 3 → 4**, stare indeksy przebudują się raz (kilkadziesiąt sekund).
2. `link_attr.bin` obok `link_type.bin`: `float32 × 4` na link (`length`, `freespeed`, `capacity`, `lanes`), 10 383 linków = 166 KB. Pole `flowCapacityFactor` w `boot.json`. Zapis w `Player.write_site` (web) i odczyt przez `get()` (aplikacja), tak jak `link_type.bin`.

### Silnik

`Engine.linkStats(t, W, mask)`: przechodzi po węzłach załadowanych porcji z oknem `(t − W, t]` (porcje `ci−1` i `ci`, dla W ≤ 15 min), zlicza `n` i `Σ tt` na link do buforów wielokrotnego użytku. Przejazd liczy się tylko w porcji, w której czas wyjazdu leży w `[t0, t1)` (granicznych węzłów porcje powtarzają, więc to chroni przed podwójnym liczeniem). Odświeżanie najwyżej 4 razy na sekundę, nie co klatkę. Maska klas jak dla aut: wyłączona klasa nie wlicza się do statystyk.

### Klient

- Przełącznik „Kolor dróg: typ / prędkość / natężenie”, okno W, legenda z gradientem i opisem („względem prędkości swobodnej”, „w skali próbki”).
- Kolor przez akcesor `getColor` z `updateTriggers` zwiększanym 4×/s. Dla Kutna (10 tys. linków) wystarczy. Dla Wiednia (375 tys.) trzeba zmierzyć; jeśli za wolno, dane binarne `PathLayer` (`startIndices`, kolor na wierzchołek).
- Panel zaznaczonego linku dostaje wiersz „w ostatnich 5 min: 23 km/h (swobodna 50), 130 poj/h”. W aplikacji tekst panelu składa Python (`describe`), w web klient (`webPanel`): dopisać obie ścieżki albo przenieść składanie wiersza do klienta w obu.
- Gdy auta są kolorowane prędkością (`RAMP`), a drogi też, kolory się mieszają. Przy włączeniu trybu prędkości/natężenia przełączyć auta na kolor klasy i zapamiętać poprzedni wybór (do ocenienia wzrokowo).

### Kroki i dowody

| Krok | Zakres | Dowód |
|---|---|---|
| L0 spike | koszt `getColor` + `updateTriggers` dla 10 tys. i 375 tys. linków | czas aktualizacji (ms), czy klatka spada poniżej 30 FPS |
| L1 | atrybuty sieci w indeksie i `link_attr.bin` | test: wartości z fixtury sieci; `flow_capacity_factor` 0,25 z configu demo |
| L2 | `Engine.linkStats` | test węzłowy: dla 10 linków i 20 chwil wynik równy niezależnemu skanowi eventów (`entered link` → `left link`) |
| L3 | tryby kolorów, legenda, okno | `--smoke`: ten sam wynik w kliencie i w Pythonie dla kilku linków; zrzut o 16:00 (szczyt) i o 03:00; pomiar FPS |
| L4 | panel linku, dokumentacja | teksty PL/EN, `README*`, `wizualizer_postep.md` |

## Decyzje do potwierdzenia przez właściciela

Proponowane wartości domyślne, na których zacznę, jeśli nie powiesz inaczej.

| # | Pytanie | Propozycja |
|---|---|---|
| D1 | Błysk tylko przy starcie aktywności czy także przy końcu? | Tylko start, koniec jako przełącznik później. |
| D2 | `tlo_*` (ruch tła na granicy sieci) to 69% startów w demo. Błyskać? | Aplikacja: wszystkie typy włączone, lista typów z checkboxami. Strona demo: `tlo_*` domyślnie wyłączone (`flash_off` w `scenarios.json`). |
| D3 | Kolor błysku | Wg typu aktywności. |
| D4 | Domyślny tryb obciążenia | Prędkość względem swobodnej (nie wymaga skalowania próbki), natężenie jako drugi tryb, okno 5 min. |
| D5 | Kolejność | A (błysk), potem B. |

## Ryzyka

- Addytywne mieszanie przy `MapboxOverlay({interleaved: false})` w deck.gl 9.4 (luma.gl 9: nazwy parametrów inne niż w 8). Spike F0; zapas: zwykłe mieszanie alfa z jaśniejszym rdzeniem.
- Błyski dla runów z dużą liczbą aktywności (100%): limit i komunikat, wydajność mierzona na największym runie lokalnym.
- Gęstość błysków przy 300× może zlać się w „mgłę”: skala życia i promień są stałymi do strojenia po obejrzeniu na prawdziwym runie, nie do zgadywania.
- Statystyki z 25% próbki są szumne na pojedynczych linkach (kilka aut w oknie): legenda i README mówią to wprost; okno 15 min jako remedium.
- B wprowadza dwa kodowania koloru na mapie (auta i drogi): ocena wzrokowa przez właściciela.

## Wykonanie (2026-10-31)

Decyzje właściciela: D1 tylko start aktywności, D2 `tlo_*` z przełącznikiem (lista typów z checkboxami; strona demo wyłącza `tlo_*` przez `flash_off`), D3 kolor wg typu, D4 prędkość i natężenie, D5 najpierw A, potem B.

- [x] **F0** spike: addytywne mieszanie (`parameters` z `blendColorSrcFactor: "src-alpha"`, `blendColorDstFactor: "one"`) przyjęte przez deck.gl 9.4 w nieprzeplatanym `MapboxOverlay`, bez błędu; zrzut z pierścieniami nad drogami.
- [x] **F1** eksport format 2 (`viz_export.py`), `Uint16Array` dla `act_type` w `readColumns`. Demo: 48 608 zdarzeń, starty `home` 3 739, `tlo_end` 16 826, `work` 3 739, eksport porcji 70,8 MB (z 70 MB).
- [x] **F2** `Engine.flashes` + wzorzec `viz_engine.flash_window`.
- [x] **F3** UI i rysunek (przełącznik, lista typów, dwie warstwy), `--smoke`.
- [x] **F4** dokumentacja.
- [x] **L1** `viz_index` (FORMAT 4): `capacity` (poj/h z `capperiod`), `permlanes`, `flowCapacityFactor` z modułu `qsim`; `link_attr.bin`, `flowFactor` w `boot`.
- [x] **L2** `Engine.linkStats`, `Engine.loadValues` + wzorzec `viz_engine.link_window_stats`.
- [x] **L3** tryby koloru, okno, legenda, auta w kolorze klasy w trybie obciążenia.
- [x] **L4** wiersz w panelu zaznaczonego linku (aplikacja i web).
- [x] **L0** koszt: dla Kutna (10 383 linków) odświeżenie kolorów co 250 ms nie zmienia płynności (w pomiarze w przeglądarce 100 klatek/s w trybach typ, prędkość i natężenie; `linkStats` 0,4 ms). **Nie zmierzone na Wiedniu (375 tys. linków)**; jeśli akcesor `getColor` okaże się za wolny, zostają dane binarne `PathLayer`.

Zmiana decyzji D1 (właściciel, 2026-10-31, po obejrzeniu błysków o 6–7): błyski także przy **końcu** aktywności, żeby widać było wyjazd z domu, a kolor odróżniał start od końca. Wykonanie: dwa checkboxy (start, koniec), start = pierścień rozchodzący się z rdzeniem w kolorze typu, koniec = ten sam kolor rozjaśniony o 55%, pierścień zbiegający się do środka, bez rdzenia (kształt rozróżnia też bez koloru). Przeglądu, jak robi to Via, nie udało się potwierdzić: wyszukiwanie nie znalazło opisu błysków aktywności w Via ani OTFVis, więc projekt jest własny.

### Zmiana: widok „auta / tylko drogi / auta + drogi” (2026-10-31, uwaga właściciela)

Problem: kolor prędkości i natężenia zależał od filtra klas aut (statystyki liczone z maską klas), więc włączanie i wyłączanie klas zmieniało kolory dróg, a auta i drogi na jednej skali zlewały się. Decyzja: przełącznik „Widok” (auta, tylko drogi, auta + drogi) oraz osobny wybór wskaźnika (prędkość, natężenie) i okna.

- `view` = `cars | load | both`, `metric` = `speed | flow`; `roadMode` (`type | speed | flow`) wynika z nich, więc `setRoadMode` zostaje dla smoke i testów.
- Statystyki liczą **cały ruch** (maska ze wszystkimi klasami), filtr klas dotyczy tylko aut.
- Widok `load`: nie rysuje warstw aut ani modeli, chowa legendy aut i przycisk „kolor auta”, klik na mapie wybiera drogę (nie auto). Widok `both`: auta kolorem klasy (jak w poprzednim trybie obciążenia).
- Test: smoke sprawdza warstwy i legendy w trzech widokach oraz że wyłączenie klasy nie zmienia liczby kolorowanych linków.
- Nie robione: skala koloru bez suwaków, wskaźnik per klasa (można wrócić, jeśli będzie potrzebny).

Odstępstwa od planu:

- Wyjazd z linku liczy się tylko po węźle wjazdu (`knot_len = 0`), nie po dowolnym węźle tego samego linku. Powód: fixtura (i potencjalnie dziwny run) dubluje `left link` i `leaves traffic` na ostatnim linku, a podwójne wyjście zawyżałoby natężenie.
- `Engine.back = 1` jest domyślne (zawsze jedna porcja wstecz), bo trzeba jej i błyskom, i statystykom linków; koszt to jedna dodatkowa porcja na starcie.
- Wiersz okna w panelu linku dokleja klient (JS), nie `Player.describe` w Pythonie, więc ten sam tekst jest w aplikacji i w web.
- Wskaźnik okna nie jest zapisywany po odświeżeniu strony (wybór trybu i okna to stan sesji).
- Skala natężenia zaczyna się od niebieskiego (`rgb(86,150,235)`), nie od jasnego: jasny ginął na podkładzie OSM.
