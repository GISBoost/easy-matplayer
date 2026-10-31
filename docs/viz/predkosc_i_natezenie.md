# Prędkość i natężenie na drogach

Kolor dróg według tego, co się na nich dzieje w ostatnich minutach symulacji: jak szybko jadą pojazdy (prędkość) albo ile ich przejeżdża w stosunku do przepustowości (natężenie). Pokazuje korki i obciążone ciągi.

Opis dla użytkownika w skrócie jest w `README_pl.md`. Ten plik opisuje szczegóły: widoki, definicje wskaźników, skąd biorą się liczby i jakie są granice.

## Widok: auta, tylko drogi, auta + drogi

Panel „Widok” ma trzy ustawienia:

| Widok | Auta | Kolor dróg |
|---|---|---|
| **auta** (domyślny) | tak, kolor wg prędkości albo klasy (przycisk „kolor auta”) | zwykły: typ drogi albo kolory OSM |
| **tylko drogi** | ukryte | wg wybranego wskaźnika |
| **auta + drogi** | tak, kolorem klasy | wg wybranego wskaźnika |

Po wybraniu „tylko drogi” albo „auta + drogi” pojawia się wybór wskaźnika (**prędkości** albo **natężenia**) i okna czasu.

- W widoku „tylko drogi” znikają też legenda aut, przycisk „kolor auta”, modele 3D i zaznaczanie aut kliknięciem (klik wybiera wtedy drogę).
- W widoku „auta + drogi” auta są kolorowane klasą, bo kolor prędkości auta i kolor prędkości drogi leżą na tej samej skali i zlewałyby się. Po powrocie do widoku „auta” wraca poprzedni wybór koloru aut.
- Kolor dróg liczy **cały ruch**, bez względu na przyciski klas aut (mieszkaniec, przyjeżdżający, tło…). Przyciski klas ukrywają auta, nie zmieniają kolorów dróg. Dzięki temu kolor drogi nie zależy od tego, które auta akurat są włączone.

## Definicje wskaźników

Wartości liczone są z eventów ruchu w oknie `(t − okno, t]`, gdzie okno to **1, 5 (domyślnie) albo 15 minut** czasu symulacji. Odświeżanie: najwyżej 4 razy na sekundę przy odtwarzaniu, od razu przy przesunięciu suwaka.

| Wskaźnik | Definicja | Skala koloru |
|---|---|---|
| **prędkość** | średnia prędkość na linku w oknie (suma długości przejazdów / suma czasów przejazdu) podzielona przez prędkość swobodną linku | czerwony ≤ 30%, żółty 60%, zielony ≥ 90% |
| **natężenie** | liczba wyjazdów z linku na godzinę (`n · 3600 / okno`) podzielona przez `capacity × flowCapacityFactor` | niebieski 0, pomarańczowy 50%, czerwony ≥ 100% |

**Link bez ruchu w oknie jest szary.** Brak pojazdów to nie „swobodnie” i nie „zero natężenia w kolorze skali”.

### Szczegóły liczenia

- **Wyjazd z linku** to pojazd, który wjechał na link i go opuścił, liczony w oknie wg czasu wyjazdu. Pojazd, który jeszcze jedzie po linku, nie jest liczony.
- **Prędkość** liczą tylko pełne przejazdy linku, czyli takie, w których poprzedni węzeł trasy leży na początku linku (tolerancja 1,5 m). Wjazd w środek linku (początek trasy) i zjazd przed końcem (koniec trasy) liczą się do natężenia, ale nie do prędkości, bo skróciłyby średnią.
- **Przepustowość** (`capacity`) jest w sieci MATSim podana na `capperiod` (zwykle godzina, ale nie zawsze). Indeks przelicza ją na pojazdy na godzinę (`link_capacity`), a prędkość swobodna (`freespeed`) i długość pochodzą z tej samej sieci.
- Wszystkie pojazdy liczą się jak jeden pojazd. Pojazdy transportu publicznego mają w MATSim współczynnik PCE większy niż 1, którego tu nie uwzględniamy.

### Natężenie jest w skali próbki

Przepustowość w sieci MATSim jest pełna, a symulacja skaluje ją przez `flowCapacityFactor` z `output_config.xml` (moduł `qsim`; moduł `hermes` ma własną wartość, nie bierzemy jej). Przy próbce 25% to zwykle 0,25. Dzielimy więc natężenie próbki przez `capacity × flowCapacityFactor` i **nie przeliczamy do pełnej populacji**. 100% na skali znaczy: droga jest obciążona do tego, co MATSim w tej symulacji uznaje za jej przepustowość.

Bez `flowCapacityFactor` w configu przycisk „natężenia” jest wyłączony z komunikatem „Brak flowCapacityFactor w configu runu”, a prędkość działa normalnie.

## Panel zaznaczonego linku

Po kliknięciu drogi panel ma dodatkowy wiersz z wartościami z tego samego okna, np.

> ostatnie 5 min: 13 km/h (swobodna 42 km/h), 156 poj/h (104% przepustowości, w skali próbki)

albo „ostatnie 5 min: brak ruchu”. Wiersz jest liczony w kliencie, więc jest taki sam w aplikacji i na stronie, także gdy widok jest „auta” (nie wymaga włączonego koloru dróg).

## Jak to jest liczone technicznie

- Indeks (`pipeline/viz_index.py`, **FORMAT 4**) zapisuje `link_capacity` (poj/h), `link_lanes` i `meta["flow_capacity_factor"]`. Aplikacja i strona dostają z tego plik `link_attr.bin` (cztery liczby `float32` na link: długość, prędkość swobodna, przepustowość, pasy) oraz `flowFactor` w `boot.json`.
- Klient (`engine.js`) liczy statystyki z węzłów porcji bieżącej i poprzedniej: `Engine.linkStats(t, okno)` (wyjazdy, pełne przejazdy, długość i czas), `Engine.loadValues(...)` (prędkość albo natężenie względne). Na demo Kutno (10 383 linków) jedno wyliczenie trwa ok. 0,4 ms.
- Wzorzec w Pythonie: `viz_engine.link_window_stats(index, t, okno)`.
- Warstwa dróg (deck.gl `PathLayer`) dostaje kolory z bufora `loadRgba`, a w widoku „auta” zwykłe kolory typu. Przy „tylko drogi” i „auta + drogi” linie są nieco grubsze, żeby kolor był czytelny.

## Jak czytać wyniki (i co z nich nie wynika)

- To są **wyniki symulacji**, nie pomiary ruchu. Czerwony odcinek znaczy, że w modelu pojazdy jechały tam wolno.
- Na próbce 25% pojedynczy link ma w oknie zaledwie kilka aut, więc wartości są szumne. Dłuższe okno (15 min) wygładza, krótsze (1 min) pokazuje zmiany, ale linki migają szaro-kolorowo, gdy ruch jest rzadki.
- Prędkość względem swobodnej < 100% bywa normalna na liniach z sygnalizacją i skrzyżowaniami, nie tylko w korku. Skala ma czerwony dopiero poniżej 30% swobodnej.
- Linki w całości poza obszarem ruchu (np. odcinki bez żadnego pojazdu przez cały dzień) są zawsze szare.

## Testy

- `viz_player/tests/test_effects.py`: `link_window_stats` zgodne z surowymi eventami; filtr klas w Pythonie; normalizacja `capperiod` do godziny; atrybuty linków w paczce strony; klient w node (`effects_check.js`) zgodny z Pythonem co do liczby wyjazdów, pełnych przejazdów, długości, czasów oraz wartości prędkości i natężenia na każdym linku.
- `--smoke` na prawdziwym runie w WebView2: statystyki klienta równe wzorcowi (wyjazdy co do sztuki, pełne przejazdy z tolerancją 1%), tryby prędkości i natężenia nie są w całości szare, trzy widoki (auta, tylko drogi, auta + drogi) mają właściwe warstwy i legendy, a **wyłączenie klasy aut nie zmienia liczby kolorowanych linków**.

## Co nie jest zrobione

- Wydajność dla bardzo dużych sieci (Wiedeń, ok. 375 tys. linków) nie była mierzona.
- Strona na GitHub Pages dostaje te funkcje dopiero po wdrożeniu (push robi właściciel).
- Skala koloru jest stała (0,3–0,9 dla prędkości, 0–1 dla natężenia); brak suwaków do jej zmiany.
