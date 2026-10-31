# Błyski aktywności

Krótki znak na mapie w miejscu i chwili, gdy osoba zaczyna albo kończy aktywność (dom, praca, szkoła, zakupy…). Pokazuje, **gdzie i kiedy ludzie przychodzą i wychodzą**, także wtedy, gdy auto już nie jedzie (po dojściu pieszo) albo jeszcze nie jedzie.

Opis dla użytkownika w skrócie jest w `README_pl.md`. Ten plik opisuje szczegóły: co znaczą błyski, jak je czytać, skąd biorą się dane i jakie są granice.

## Jak to wygląda

| Zdarzenie | Event MATSim | Wygląd |
|---|---|---|
| początek aktywności | `actstart` | **sam rdzeń**: kropka w kolorze typu, która gaśnie |
| koniec aktywności | `actend` | **sam pierścień**: obręcz w kolorze typu, która rozchodzi się od środka i gaśnie |

Start i koniec tego samego typu mają ten sam kolor, więc rozróżnia je kształt. Np. poranny „dom, koniec” to pierścienie w kolorze domu (wyjazdy z osiedli), „praca, start” to rdzenie w kolorze pracy (przyjazdy do zakładów).

### Kolory typów

Kolor wynika z nazwy typu aktywności w danym runie (nazwy zależą od scenariusza):

| Typ zaczyna się od | Kolor |
|---|---|
| `home` | pomarańczowy |
| `work` | niebieski |
| `edu`, `school` | fioletowy |
| `shop` | zielony |
| `leis` | różowy |
| `other` | jasnoszary |
| inne nazwy | z palety ośmiu kolorów, wybór po haszu nazwy (ta sama nazwa zawsze dostaje ten sam kolor) |

Aktywność techniczna `car interaction` (przesiadka na auto) jest pomijana: nie jest miejscem, w którym ktoś coś robi.

## Panel

- **błyski aktywności**: włącza i wyłącza wszystkie błyski.
- **start: sam rdzeń** i **koniec: sam pierścień rozchodzi się**: osobne przełączniki dla obu rodzajów. Można oglądać same przyjazdy albo same wyjazdy.
- **Lista typów** z kolorową kropką i checkboxem: pokazuje typy, które w tym runie mają jakikolwiek start lub koniec. Wyłączenie typu chowa jego błyski.

Błyski nie zależą od przycisków klas aut (mieszkaniec, przyjeżdżający…): dotyczą osób, nie pojazdów, a część osób jedzie innym trybem niż auto i nie ma pojazdu na mapie.

### Ruch tła (`tlo_start`, `tlo_end`)

W scenariuszach z ruchem tła (np. demo Kutno) pojazdy tła zaczynają i kończą trasę na granicy sieci. W demo to 16 826 startów i tyle samo końców, czyli ok. 69% wszystkich zdarzeń. Są poprawne, ale zasłaniają błyski miejskie, więc:

- **aplikacja** pokazuje wszystkie typy, a Ty wyłączasz je na liście typów;
- **strona demo** ma `tlo_start` i `tlo_end` domyślnie wyłączone (`"flash_off"` w `web/scenarios.json`), nadal można je włączyć checkboxem.

## Czas życia i prędkość odtwarzania

Błysk trwa **ok. 1,5 s czasu ekranu** bez względu na mnożnik. Program przelicza to na czas symulacji: `życie = 1,5 s × mnożnik`, nie mniej niż 3 s i nie więcej niż 450 s symulacji. Np. przy 60× błysk trwa 90 s symulacji, przy 1× trzy sekundy.

Wygląd błysku jest funkcją samego czasu `t` i mnożnika, więc:

- przeciągnięcie suwaka do dowolnej chwili pokazuje właściwe błyski od razu;
- w pauzie błyski stoją w swojej fazie.

W jednej klatce rysowanych jest najwyżej **5 000** najnowszych błysków. Gdy jest ich więcej (np. 300× na szczycie w dużym runie bez wyłączonego tła), starsze są pomijane, a klient ustawia znacznik `truncated`.

Rysowanie: dwie warstwy deck.gl (`ScatterplotLayer`: pierścienie i rdzenie), mieszanie addytywne (nakładające się błyski rozjaśniają się), nad drogami i pod autami.

## Skąd dane

Pozycja i czas błysku to `x`, `y` i `time` z eventu `actstart` lub `actend`, przeliczone na układ mapy tak samo jak reszta danych. Nic nie jest wymyślane ani rozmywane.

- Eksport (`pipeline/viz_export.py`, **FORMAT 2**) dokłada do porcji 15 min zdarzenia aktywności z czasem w `[t0, t1)`, posortowane po czasie: kolumny `act_t`, `act_dlon`, `act_dlat`, `act_type`, `act_kind` (1 = start, 0 = koniec), `act_person_i`. Manifest ma `act_types`, `act_start_counts`, `act_end_counts`, `n_acts`.
- Klient (`engine.js`, `Engine.flashes`) wybiera zdarzenia z okna `(t − życie, t]` z porcji bieżącej i poprzedniej (binarne wyszukiwanie, bez alokacji w każdej klatce).
- Stary eksport (FORMAT 1) nie ma zdarzeń aktywności: panel błysków jest wtedy ukryty, a program działa jak wcześniej. Cache eksportu przebudowuje się sam.

## Jak czytać błyski (i czego nie wolno z nich wyczytać)

- Błysk to **zdarzenie z symulacji**, nie obserwacja. Skupisko błysków „praca, start” między 6 a 7 w strefie ekonomicznej oznacza, że model wysyła tam poranną zmianę. To wynik modelu i próbki (np. 25% populacji), nie pomiar.
- Pierścień „koniec” stoi w miejscu, gdzie aktywność się kończy, czyli zwykle przy domu, a auto pojawia się na drodze chwilę później albo w ogóle (inny tryb).
- Auto znika z drogi wcześniej niż błysk startu: MATSim dolicza dojście pieszo jako teleportowaną nogę `walk`, której program nie rysuje (w wyniku nie ma jej trasy i nie jest rekonstruowana, to decyzja właściciela). Ten odstęp jest prawdziwy.
- Błysk pokazuje liczbę zdarzeń w próbce. Przy próbce 25% jeden błysk to jedna osoba z próbki, nie cztery.
- Nie ma tu rozróżnienia „ta sama osoba wraca”: każde zdarzenie błyska osobno.

## Testy

- `viz_player/tests/test_effects.py`: eksport v2 zgodny z indeksem; `flash_window` zgodne z surowymi eventami (starty, końce i oba naraz, 10 chwil); klient w node (`effects_check.js`) zgodny z Pythonem co do liczby, wieku, typu i rodzaju każdego błysku; liczniki w manifeście.
- `--smoke` na prawdziwym runie w WebView2: liczba błysków klienta równa liczbie z indeksu (`blyski=<w oknie>/<narysowane>`).

## Co nie jest zrobione

- Wygląd i gęstość na dużych runach (Wiedeń, Berlin) przy 300× nie były oglądane; stałe wyglądu są w `FLASH` w `shell.html` (`wall`, `min`, `max`, `r0`, `r1`, `cap`) i są do strojenia.
- Kliknięcie błysku nie zaznacza osoby (id osoby jest w eksporcie jako `act_person_i`, wykorzystanie to osobny krok).
