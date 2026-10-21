# Wizualizer MATSim — wstępna koncepcja

Data notatki: 2026-10-20. To nie jest decyzja projektowa sama z siebie. Wybór jest w D24. Ta notatka jest na branchu `wizualizer`, nie na `main`.

Recenzja: `docs/research/wizualizer_recenzja.md`. Plan i wybór z 2026-10-20: `docs/research/wizualizer_plan.md` (sekcja „Wybór użytkownika”). Propozycje poniżej są hipotezą sprzed wyboru. Obowiązuje plan. Wybór jest wpisany jako D24 w `docs/projekt/DECISIONS.md`.

Źródła tej notatki: rozmowa o wizualizerze (archiwum, G6, lokalny odtwarzacz, REA) oraz stan kodu na 2026-10-20. Liczby poniżej są z tamtej rozmowy i z plików runów, nie z nowego pomiaru.

## Instrukcja dla następnego agenta

Przeczytaj ten plik jako wsad do własnej analizy, nie jako stan ustaleń. Żadna „propozycja” poniżej nie jest wybrana. Użytkownik (Michał) ma wybrać sam, na końcu Twojej pracy.

Zrób po kolei:

1. Sprawdź każdy fakt w repozytorium i w dokumentacji, zanim go powtórzysz. Liczby (rozmiary eventów, liczba przejazdów, zachowanie SimWrapper, składniki Via, stos WebView2, to, co naprawdę zapisuje `pipeline/g6_bake.py`) mogły się zdezaktualizować albo być uproszczone. Jak plik i kod się różnią, wygrywa kod i plik.
2. Przejdź wszystkie 11 punktów. Przy każdym napisz, czy propozycja się broni, co sprawdziłeś i co byś zmienił. Wolno odrzucić propozycję. Nie wolno przyjąć jej dlatego, że tu stoi.
3. Nie pisz kodu wizualizera, nie zmieniaj `DECISIONS.md`, `TASKS.md` ani zakresu. Ta notatka zostaje lokalna.
4. Na samym końcu odpowiedzi zatrzymaj się i zapytaj użytkownika, którą opcję wybiera w każdym punkcie. Podaj przy każdym punkcie krótką rekomendację po Twojej własnej analizie i realne opcje. Decyzję zostaw jemu. Nie zapisuj wyboru, dopóki go nie podejmie.

## Po co

W `archiwum/kutno_2026-10/matsim_lodz_kutno_podsumowanie.md` własny wizualizer jest ostatnim punktem po działającym Kutnie. Powód: Via (Simunto) jest płatne. Pada tam nazwa Kepler.gl albo własny dashboard. Dłuższy research (`docs/research/MATSim_Lodz_research_v2.md`, część 4.3) rozdziela role: SimWrapper i QGIS do analizy, Kepler/deck.gl do przepływów, Via pomijamy. Zakres MVP wizualizer wyklucza (`CLAUDE.md`).

Cel, który wynika z rozmowy: oglądać ruch z gotowego runu na tym komputerze, także przy większej próbce niż film z Blendera. Program nic nie liczy w MATSim i nic do niego nie zapisuje.

Cztery wymagania dopisane 2026-10-20, po obejrzeniu Via:

- **Lekkość.** Ma dać się odpalać dużo i dużych symulacji na maszynie 16 GB. Lekki jest silnik danych (rzadki indeks, w klatce tylko auta będące w sieci, przełączenie runu bez ponownego czytania XML). Ciężki instalator interfejsu jest do przyjęcia, ciężka klatka odtwarzania nie.
- **Inspekcja.** Duża interaktywność jest wymogiem pierwszej wersji, nie dodatkiem. Klik i szukanie mają powiedzieć, co to za auto albo link, a nie tylko pokazać kolorową kropkę.
- **Nowoczesny wygląd.** Via wygląda jak program zaprojektowany około 2001 roku i od tamtej pory nieruszany. Ten ma wyglądać jak współczesne narzędzie: ciemny motyw (taki sam kierunek jak wykresy w projekcie), mapa na prawie całym oknie, jeden cichy panel, czytelna typografia, mało przycisków na wierzchu.
- **Łatwość użycia.** Otworzenie runu, play, suwak, szukanie agenta i filtr klasy bez instrukcji. Skróty: spacja, strzałki, śledzenie wybranego auta, czyszczenie wyboru.

## Co już jest

- **SimWrapper** (D15): dashboardy zagregowane (natężenia, podróże, stuck). Podgląd samych eventów w SimWrapper jest eksperymentalny: wolno ładuje plik, bez konfiguracji, nie wchodzi do dashboardu. Zostaje do statystyki, nie do odtwarzania aut.
- **G6** (`pipeline/g6_bake.py`, `blender/g6_*.py`, opis w `docs/research/G6_blender.md`): eventy → pozycje → film. To warstwa prezentacji. Szczyt 06:00–09:00, próbka 25%, krok 5 s: 4822 przejazdy, najwyżej około 755 aut naraz, bake około 12 s, `vehicles.npz` 32 MB. Cały dzień do 20:00, krok 10 s: `vehicles.npz` 240 MB. Eventy R6 25% (`output/g5r6_25pct_s4711/output_events.xml.zst`) ważą 45 MB, sieć 0,3 MB. Eventy F6 100% ważą 59 MB, ale to wcześniejszy MVP, bez tła z R6.
- Bake czyta cztery typy: `vehicle enters traffic`, `entered link`, `left link`, `vehicle leaves traffic`. Pozycja między końcami linku jest interpolowana, więc korek widać jako zwolnienie. Origin sceny: (524805, 485023) EPSG:2180. Test: trzy losowe trasy, pozycja bliżej niż 0,5 m od odcinka linku.
- Sieć Kutna (powiat + 3 km): 4 453 węzły, 10 296 linków. Link to cięciwa między węzłami, bez łamanej z OSM.
- Select-link jest w `pipeline/select_link.py`, bez mapy.

## Czego nie robimy

- Nie dekompilujemy Via i nie podłączamy w tym celu REA. REA (`morluto/rea`, MIT) da się zarejestrować w Grok Build (`npx rea-agents setup`, Node 22.19+ / 24.11+ / 26+), ale Via nie chowa formatu. Publiczny opis Simunto to sieć, eventy i warstwa pojazdów. Ten sam mechanizm jest już w bake.
- Nie budujemy OTFVis (podgląd na żywo w trakcie QSim).
- Player nie parsuje XML przy każdym otwarciu. Indeks powstaje raz.
- Gęsta tablica „klatka × auto × xy” zostaje przy Blenderze. Dla Kutna 100% przez całą dobę urasta do kilku GB. To ona ogranicza skalę, nie sam fakt rysowania.
- Kepler.gl nie jest odtwarzaczem aut. Nadaje się do macierzy O–D i statycznych linków.
- Trajektorie nie wędrują do strony internetowej ani do karty przeglądarki. Indeks zostaje w procesie Pythona. Powłoka okna może być nowoczesnym widokiem (także na lokalnym WebView2), bo do rysowania dostaje tylko pozycje aut z bieżącej klatki.

## Koncepcja: lokalny odtwarzacz

Dwa programy, oba na tym komputerze, oba w Pythonie, bez zmian w Javie MATSim.

1. **Indeks, raz na run.** Strumieniowo czyta sieć i eventy. Zapisuje plik binarny z węzłami czasowymi `(czas, x, y)` na końcach linków oraz kubełki czasu (co 30–60 s) z listą przejazdów aktywnych w oknie. Dla R6 25% na dobę rząd wielkości to dziesiątki MB, nie setki. Player tego pliku już nie zamienia z powrotem na XML.
2. **Silnik odtwarzania.** Jeden zegar symulacji, niezależny od klatek obrazu. Każdy aktywny przejazd ma kursor na odcinku. Odtwarzanie do przodu kosztuje tyle, ile aut jest w sieci. Suwak wstecz skacze do kubełka i ustawia kursory od nowa. Widok z góry, metry EPSG:2180, ten sam origin co G6, float32. Sieć: statyczny bufor linii. Auta: jedna tablica instancji (pozycja, kierunek, prędkość, klasa) liczona co klatkę. Kolor prędkości w shaderze. Picking: identyfikator pod kursorem liczy silnik, nie warstwa obrazu.
3. **Powłoka.** Mapa, pasek czasu, pole szukania, panel inspekcji. Ma być lekka w obsłudze i współczesna. Nie trzyma trajektorii. Szczegóły stosu są decyzją 4.

Pamięć playera: cel 2–4 GB na maszynie 16 GB. Węzły czasowe w jednej tablicy NumPy, nie jako lista obiektów Pythona. Co klatkę liczone są tylko auta aktualnie w sieci.

Sufit orientacyjny: Kutno 100% mieści się spokojnie. Łódź 100% też, dopóki trzymany jest indeks rzadki. Ściana to ponowne czytanie wielogigabajtowego XML, nie rysowanie instancji. Kilkadziesiąt tysięcy aut naraz jest dla karty drobiazgiem. W szczycie Kutna 25% widać ich około 750.

Blender zostaje do filmów (`g6_story*.py`). SimWrapper zostaje do dashboardów. Player ich nie zastępuje.

## Czego w pierwszej wersji koncepcji nie ma

Podkładu mapy, łamanych OSM, budynków, pasów ruchu, dźwięku, zapisu zwrotnego do MATSim, porównania dwóch runów obok siebie. Porównanie to drugi widok na dwa indeksy, nie osobna architektura. Szerokość drogi umowna, jak w G6. Próbka 25% wygląda jak ćwierć ruchu. Rozmiar auta na ekranie jest umowny (w G6 kostka jest powiększona ×8, bo z kilku kilometrów 4,5 m znika).

## Punkty do decyzji i propozycje z tej rozmowy

Żadna nie jest podjęta. „Propozycja” jest hipotezą poprzedniego agenta, nie rekomendacją do skopiowania i nie wpisem D*. Następny agent ma ją sprawdzić od nowa (instrukcja na górze pliku) i na końcu swojej odpowiedzi zapytać użytkownika o wybór.

Punkty 3, 4 i 7 są przestawione względem pierwszej wersji tej notatki: inspekcja i wygląd doszły jako wymóg użytkownika, więc sama mapa z suwakiem przestaje wystarczać jako pierwsza wersja. To też jest do weryfikacji, nie pewnik.

1. **Czy w ogóle ruszamy.** Wizualizer jest poza zamrożonym MVP. Start kodu wymaga wpisu w `DECISIONS.md`. Do tego czasu ta notatka zostaje lokalna. Propozycja: nie ruszać kodu, aż będzie wpis i zamknięte punkty 2–6.

2. **Co jest produktem.** (a) lokalny player z inspekcją, (b) kolejne filmy Blender, (c) tylko SimWrapper. Filmy są ładne i nieme. SimWrapper dobrze liczy agregaty i słabo pokazuje jadące auto. Propozycja: (a). Blender zostaje do filmów, SimWrapper do dashboardów.

3. **Co potrafi pierwsza wersja, którą da się używać.** Sam odtwarzacz (play, suwak, kolor prędkości) jest szybki w budowie i mało przydatny przy wymogu inspekcji. Pełne Via (select-link, dwa scenariusze, wykresy linku, plany, podkład) jest osobnym programem na miesiące. Propozycja v1: mapa, czas, szukanie po identyfikatorze, klik w auto (id, klasa, prędkość, link, śledzenie kamerą), klik w link (ile aut i jaka prędkość w tej chwili), filtr trzech klas. Bez dwóch runów obok siebie i bez wykresu całego dnia. Harmonogram dom–podróż–praca wymaga dociągnięcia aktywności albo planów. To drugi krok, bo samych czterech typów eventów ruchu do tego nie ma.

4. **Stos okna.** Goły pyglet albo moderngl rysuje szybko i wygląda jak narzędzie inżynierskie. Dear ImGui dokłada panele i dalej wygląda jak debugger. Qt (PySide6) umie prawdziwe okno, search i HiDPI, a styl trzeba świadomie narysować, inaczej wyjdzie szary krewniak Via. Lokalna powłoka HTML w oknie systemowym (WebView2, jest w Windows) daje współczesny układ najtaniej. Żeby została lekka, trajektorie zostają w Pythonie, a widok dostaje tylko bieżącą klatkę (przy 50 tysiącach aut to około 1–2 MB na klatkę, nie cały dzień). Propozycja: silnik w Pythonie, powłoka lokalnego WebView2. Qt zostaje alternatywą, gdyby okno webowe odpadło.

5. **Format indeksu.** Gęsty `vehicles.npz` jest prosty i już jest, a puchnie z długością dnia razy liczbą aut (240 MB przy 25% do 20:00, kilka GB przy 100% i drobniejszym kroku). Rzadkie węzły plus kubełki czasu trzymają dobę R6 25% w dziesiątkach MB i pozwalają skakać do 08:15 bez skanu. To jest warunek „dużo symulacji”: przełączenie runu czyta indeks, nie XML. Propozycja: rzadki indeks w `output/` (katalog już ignorowany). Gęsty npz zostaje przy Blenderze. Ta sama interpretacja czterech typów eventów co w `g6_bake.py`.

6. **Pierwszy run i okno czasu.** Od razu 100% albo cała doba sprawdza skalę, a utrudnia pierwszy test obrazu. R6 25%, 06:00–09:00, jest już opisane (4822 przejazdy, około 755 aut naraz) i ma gotowy test trzech tras. Propozycja: ten run i to okno jako pierwszy obraz. Indeks od początku pisany tak, żeby to samo polecenie wzięło dobę i 100% bez zmiany formatu.

7. **Filtr klas.** Jeden kolor prędkości jest czytelniejszy na starcie. Filtr (mieszkaniec, przyjeżdżający, ciężarowy `h…`) jest tani, bo klasa siedzi w identyfikatorze, i bez niego inspekcja miasta z tłem G5 jest ślepa: osobowe i ciężarowe wyglądają tak samo. Propozycja: kolor prędkości oraz trzy przełączniki klas od pierwszej wersji. Domyślnie włączone wszystkie.

8. **Geometria dróg.** Cięciwy są w sieci dziś i wystarczą do inspekcji korka. Łamane z OSM wyglądają wierniej i są zmianą konwertera sieci, nie playera. Propozycja: v1 na cięciwach. Łamane osobno, kiedy obraz ma iść do kogoś spoza projektu.

9. **Podkład mapy.** Ciemna sieć na czarnym tle jest lżejsza, szybsza i zgodna z filmami G6. Kafelki OSM albo ortofoto pomagają rozpoznać ulicę i ciągną licencję oraz zamianę EPSG:2180 na długość i szerokość. Propozycja: v1 bez podkładu, z nazwami dróg przy zbliżeniu, jeśli atrybut nazwy jest w sieci. Podkład jako osobna decyzja później.

10. **Jak pokazać próbkę.** Dorysowanie aut „do 100%” wygląda gęściej i kłamie. Podpis „próbka 25%” jest uczciwy i nic nie kosztuje. Propozycja: rysować tyle aut, ile jest w runie, i trzymać ułamek próbki w pasku stanu.

11. **Gdzie mieszka kod, gdy decyzja zapadnie.** Drugi, niezależny odczyt eventów rozjedzie film i player. Propozycja: jeden indeks w `pipeline/`, player jako osobny lokalny program obok, bez zmian w `matsim/`. Blender dalej może piec gęste klatki z tego samego indeksu albo ze starego bake’a, aż ktoś je zepnie.

## Porządek prac po decyzjach

Szkic z tej rozmowy, też do sprawdzenia: najpierw rzadki indeks na R6 25%, 06:00–09:00, i test trzech tras. Potem okno: mapa, czas, szukanie, klik w auto, klik w link, filtr klas. Wygląd od pierwszej klatki, którą ogląda człowiek. Później harmonogram agenta, łamane OSM, podkład, drugi run obok siebie, Łódź.

Ten porządek startuje dopiero po tym, jak użytkownik sam wybierze opcje. Agent kończy analizę pytaniem o wybór i na tym się zatrzymuje.
