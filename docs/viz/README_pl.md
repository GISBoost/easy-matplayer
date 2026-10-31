# easy-matplayer

Odtwarzacz wyników symulacji [MATSim](https://matsim.org/): ruch samochodów na mapie, w 2D i 3D, z budynkami. Działa lokalnie na Windowsie, bez instalacji i bez Pythona.

## Pobranie i uruchomienie

1. Z [Releases](../../../../releases) pobierz `easy-matplayer-windows.zip` (ok. 46 MB) i rozpakuj w dowolne miejsce (ścieżka może mieć spacje i polskie znaki).
2. Uruchom `easy-matplayer.exe`. Jeśli Windows pokaże „Chroniony komputer” (SmartScreen), kliknij „Więcej informacji”, potem „Uruchom mimo to”. Plik nie jest podpisany certyfikatem.
3. Wskaż folder runu MATSim. Przy pierwszym otwarciu program buduje indeks (od kilkunastu sekund do minuty, widać pasek postępu). Potem ten sam run otwiera się od razu, a program pamięta ostatni run.

Wymagania: Windows 10 22H2 albo 11 (64-bit) i Microsoft Edge WebView2 Runtime (jest w Windows 11 i w większości Windows 10; jeśli go brakuje, program pokaże komunikat z linkiem do instalatora). Karta graficzna z obsługą WebGL; zintegrowana wystarcza.

## Język

Interfejs startuje po angielsku (wersja angielska tej instrukcji: [README.md](README.md)). Przycisk obok „otwórz run…” w panelu przełącza na polski (wtedy opisuje się jako „English”). Wybór zapisuje się w `%LOCALAPPDATA%\easy-matplayer\viz_player_lang.json`. Zmiana języka przeładowuje otwarty run. Nazwy przycisków w tej instrukcji są po polsku i zgadzają się z interfejsem po przełączeniu na polski.

## Demo

`easy-matplayer-demo-kutno.zip` (ok. 59 MB, osobny plik w tym samym wydaniu) to run Kutna (25% mieszkańców, 100 iteracji, sieć z zakazami skrętu z OSM) z gotowym indeksem. Rozpakuj i wskaż folder `demo-kutno`. Otwiera się w kilka sekund, z budynkami 3D, bez żadnych dodatkowych plików.

## Inne publiczne scenariusze MATSim

Nie dołączamy ich do wydania (każdy ma własną licencję). Pobierz sam i wskaż folder z wynikami; program wymaga plików `.xml.zst`, więc wyniki w `.xml.gz` trzeba przepakować (patrz niżej). Układ współrzędnych sieci program czyta z `output_config.xml` runu (`coordinateSystem`, kod EPSG); bez wpisu albo z wartością inną niż kod EPSG (MATSim domyślnie wpisuje `Atlantis`) przyjmuje EPSG:3857 (współrzędne jako metry Web Mercator), więc run się otwiera, ale ruch może leżeć w złym miejscu na mapie. Przetestowany jest Wiedeń (EPSG:3416); Berlin i Kelheim (EPSG:25832) nie były otwierane. Budynki i łamane drogi z OSM są liczone dla obszaru sieci, więc przy bardzo dużych sieciach potrzebny jest plik OSM obejmujący ten obszar.

| scenariusz | gdzie | licencja danych |
|---|---|---|
| Berlin v6.4 (1%, 10%, 25%) | [matsim-berlin](https://github.com/matsim-scenarios/matsim-berlin), wyniki na [serwerze TU Berlin](https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/berlin/berlin-v6.4/output/) (eventy 1%: ok. 274 MB) | CC BY 4.0 |
| Kelheim | [matsim-kelheim](https://github.com/matsim-scenarios/matsim-kelheim), wyniki na [serwerze TU Berlin](https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/kelheim/) | CC BY-NC 4.0 (tylko użytek niekomercyjny) |
| Wiedeń 2023.2 | [ait-energy/matsim-model-vienna](https://github.com/ait-energy/matsim-model-vienna) (tylko wejścia, wyniki trzeba policzyć samemu) | CC BY-NC 4.0 (tylko użytek niekomercyjny) |

Pliki NC wolno otwierać na własnym komputerze; nie wolno ich dołączać do publicznych paczek z tym programem.

## Własny run

Folder runu MATSim musi zawierać `output_events.xml.zst`, `output_network.xml.zst` i `output_plans.xml.zst`. MATSim zapisuje takie pliki, gdy w konfiguracji ustawisz `controller` → `compressionType` = `zst`. Run zapisany jako `.xml.gz` trzeba przepakować (`gzip -dc output_events.xml.gz | zstd -o output_events.xml.zst`). Program nie zmienia niczego w folderze runu poza podfolderem `viz/` (indeks, cache).

## Budynki i łamane drogi z OpenStreetMap (opcjonalnie)

Domyślnie drogi są prostymi odcinkami z sieci runu, a budynków nie ma. Żeby je dodać, w panelu po prawej kliknij „plik OSM…” i wskaż plik `.osm.pbf` z obszarem runu (np. z [Geofabrik](https://download.geofabrik.de/europe/poland.html)). Program wytnie budynki (z wysokościami z tagów OSM albo założonymi z klasy budynku) i dopasuje kształt dróg. Wynik zapisuje przy runie (`viz/`), więc ten run można potem skopiować na inny komputer bez pliku OSM. „zapomnij plik” wraca do prostych odcinków.

## Gdzie są dane programu

Dziennik `easy-matplayer.log` leży obok `easy-matplayer.exe` (przy problemach wyślij go; gdy folder programu jest chroniony przed zapisem, trafia do `%LOCALAPPDATA%\easy-matplayer\`). W `%LOCALAPPDATA%\easy-matplayer\` są: pamięć ostatniego runu, pliku OSM i wybranego języka. Odinstalowanie to usunięcie folderu programu i tego folderu. Program nie zapisuje nic w rejestrze.

## Sieć

Do działania mapa podkładowa pobiera kafelki z publicznych usług WMS/WMTS (adresy w panelu mapy). Bez internetu ruch i sterowanie działają, brakuje tylko podkładu. Program nie wysyła żadnych danych o runie.

## Licencje

- Program: GPL-3.0-or-later (plik `LICENSE`). Biblioteki w paczce: teksty licencji w `THIRD_PARTY/` w folderze programu.
- Demo: wyniki symulacji CC BY 4.0, plany pochodne danych GUS (CC BY 4.0), sieć i budynki © współtwórcy OpenStreetMap (ODbL 1.0). Szczegóły: `LICENSE-DATA.md` w zipie demo. W demo nie ma danych komercyjnych.
- Modele samochodów: Quaternius, CC0.

## Błyski aktywności

Gdy osoba zaczyna aktywność (event `actstart`) albo ją kończy (`actend`, czyli np. wyjeżdża z domu), w tym miejscu mapy pojawia się krótki błysk. Przełącznik „błyski aktywności” w panelu, pod nim osobne checkboxy dla startu i końca oraz lista typów (np. żeby wyłączyć techniczne `tlo_start` i `tlo_end` ruchu tła).

- **Start:** sam rdzeń (kropka, która gaśnie), bez pierścienia.
- **Koniec:** sam pierścień, który rozchodzi się od środka i gaśnie, bez rdzenia.

Oba w kolorze typu aktywności, więc start i koniec rozróżnia kształt. Szczegóły: `blyski_aktywnosci.md`.

Kolory typów: `home` pomarańczowy, `work` niebieski, `edu`/`school` fioletowy, `shop` zielony, `leis…` różowy, inne typy z palety.

- Miejsce i czas błysku to współrzędne `x`, `y` i czas z eventu `actstart`. Auto znika wcześniej (koniec jazdy), a MATSim dolicza dojście pieszo jako teleportowaną nogę `walk`, której program nie rysuje (nie ma trasy w wyniku). Ten odstęp jest prawdziwy.
- Błyski pokazują starty aktywności wszystkich osób z eventów, także tych, które jadą innym trybem niż auto i nie mają pojazdu na mapie. Filtr klas ich nie dotyczy.
- Błysk trwa ok. 1,5 s na ekranie bez względu na mnożnik odtwarzania (przy 1× co najmniej 3 s symulacji). Przewijanie suwakiem działa, w pauzie błyski stoją w swojej fazie. W jednej klatce rysowanych jest najwyżej 5 000 najnowszych błysków.

## Kolor dróg: obciążenie

Panel „Widok” ma trzy ustawienia: `auta` (domyślnie, drogi w zwykłych kolorach), `tylko drogi` (auta ukryte, drogi w kolorze obciążenia) i `auta + drogi`. W dwóch ostatnich wybierasz wskaźnik, `prędkości` albo `natężenia`, oraz okno 1, 5 (domyślnie) lub 15 minut symulacji. Wartości liczone są z eventów ruchu w oknie `(t − okno, t]`, odświeżane 4 razy na sekundę. Szczegóły: `predkosc_i_natezenie.md`.

| Wskaźnik | Co pokazuje | Skala |
|---|---|---|
| prędkość | średnia prędkość na linku (suma długości / suma czasów przejazdu) podzielona przez prędkość swobodną linku | czerwony ≤ 30%, żółty 60%, zielony ≥ 90% |
| natężenie | liczba wyjazdów z linku na godzinę podzielona przez `capacity × flowCapacityFactor` | niebieski 0, pomarańczowy 50%, czerwony ≥ 100% |

- Link bez wyjazdu w oknie jest szary: brak ruchu to nie „swobodnie”.
- Natężenie jest w skali próbki. Przepustowość sieci jest pełna, symulacja skaluje ją przez `flowCapacityFactor` z `output_config.xml` (moduł `qsim`), więc dzielimy przez ten iloczyn i nie przeliczamy do pełnej populacji. Bez `flowCapacityFactor` w configu tryb „natężenie” jest wyłączony z komunikatem.
- Prędkość liczą tylko pełne przejazdy linku (początek w początku linku). Wjazd w środek linku (początek i koniec trasy) liczy się do natężenia, nie do prędkości. Wszystkie pojazdy liczone jako jeden pojazd (pojazdy PT mają w MATSim większy współczynnik PCE).
- Statystyki z próbki 25% są szumne na pojedynczych linkach (kilka aut w oknie): dłuższe okno wygładza. W widoku `auta + drogi` auta są kolorowane klasą (po powrocie do `auta` wraca poprzedni wybór), żeby nie zlewały się z drogą. Kolor dróg liczy cały ruch: przyciski klas aut ukrywają auta, ale nie zmieniają koloru dróg.
- Panel zaznaczonego linku ma dodatkowy wiersz z wartościami z okna, np. „ostatnie 5 min: 13 km/h (swobodna 42 km/h), 156 poj/h (104% przepustowości, w skali próbki)”.

## Komputer: pływające wyspy (aplikacja okienkowa i strona, od 701 px)

Ten sam wygląd co na telefonie (ciemny, szkło, zaokrąglenia), w układzie na szeroki ekran. Aplikacja i strona w przeglądarce są jednym plikiem, więc wyglądają tak samo; różnią się tylko funkcje (własne usługi WMS/WMTS/XYZ, obrazy, otwieranie runów i plik OSM są tylko w aplikacji; strona ma dwa gotowe podkłady: OpenStreetMap i ortofotomapę GUGiK, obie z suwakiem krycia). Własnych usług nie ma na stronie, bo nie każdy serwer map pozwala przeglądarce pobierać z nich kafelków (brak nagłówka CORS), a aplikacja pobiera je przez Pythona.

- Mapa jest na cały ekran. Po prawej u góry szklana pastylka z trzema przyciskami: 3D, pokaż cały obszar i ustawienia. Ustawienia otwierają panel, który wysuwa się pod pastylką do dołu okna; sekcje panelu zwija się nagłówkami. Legenda i skala są w jednym polu w lewym górnym rogu. Kółko myszy i przeciąganie jak dotąd; prawy przycisk myszy: obrót i pochylenie.
- Na dole pośrodku kapsuła odtwarzacza (do 720 px): zegar bez sekund i liczba aut, start/pauza, suwak, mnożnik. Kliknięcie mnożnika rozwija rząd ◀ 1× 10× 60× 300× ▶. Pod spodem próbka, uwagi o runie, „© OpenStreetMap” i skróty klawiszowe: spacja (start), strzałki (±1 min), F (śledź), Esc (wyczyść).
- Ustawienia to szklany panel pod pastylką, do dołu i prawej krawędzi okna; kapsuła odtwarzacza przesuwa się wtedy do wolnej części okna (także w oknie prawie kwadratowym). Przycisk ustawień ją wysuwa i zwija; kliknięcie auta lub drogi też ją otwiera. W oknie do 1024 px kliknięcie pustej mapy ją zamyka. Na górze szczegóły zaznaczenia i ostrzeżenia o runie, niżej sekcje rozwijane nagłówkiem: Widok, Klasy, Warstwy, Szukaj, Podkłady (strona), Zaawansowane (aplikacja: WMS/WMTS/XYZ, obrazy, otwórz run, plik OSM; domyślnie zwinięte).
- Szerokość wyspy i kapsuły zależy od okna: do 1024 px 300 i 560, do 1439 px 340 i 640, od 1440 px 360 i 720.
- Bez rozmycia tła (stara przeglądarka), przy wyłączonych w Windows efektach przezroczystości i przy wysokim kontraście tło szkła ma być jednolite (reguły CSS są dodane; działanie w WebView2 nie było jeszcze sprawdzone).

## Telefon (strona w przeglądarce)

Przy szerokości okna do 700 px (telefon w pionie) strona przełącza się na układ dotykowy. Od 701 px w górę (komputer, aplikacja okienkowa, poziomy tablet) działa układ pływających wysp, opisany niżej.

- Mapa jest na cały ekran. Dwa palce: obrót i pochylenie.
- U góry po lewej pigułka z czasem i liczbą aut, po prawej szklany stos przycisków: 3D, pokaż cały obszar, ustawienia.
- Na dole pływająca karta odtwarzacza: start/pauza, suwak czasu i mnożnik. Dotknięcie „60×” rozwija rząd ◀ 1× 10× 60× 300× ▶ (◀ ▶ zmieniają mnożnik o 1, jak na komputerze). Pod spodem próbka, uwagi o runie (np. pokrycie OSM) i skrót „© OpenStreetMap” (pełny tekst na dole arkusza). Zegar w pigułce pokazuje godziny i minuty.
- Panel boczny to arkusz nad odtwarzaczem o trzech wysokościach: zamknięty, środek, wysoko. Przeciągasz go za uchwyt u góry (albo dotykasz uchwytu: środek ↔ wysoko), przycisk ustawień otwiera i zamyka. Dotknięcie auta lub drogi otwiera arkusz ze szczegółami. Dotknięcie pustej mapy zamyka arkusz, a przy zamkniętym kasuje zaznaczenie. Mapa zostaje widoczna nad arkuszem.
- W arkuszu: szczegóły, widok (auta, tylko drogi, auta + drogi), klasy aut, przełączniki (kolor dróg OSM, modele 3D, błyski), wyszukiwarka, podkłady.
- Granice: tylko układ pionowy (poziomo telefon dostaje układ komputerowy), arkusz przeciąga się tylko za uchwyt, skróty klawiszowe nie dotyczą telefonu, a własne WMS/WMTS/XYZ, obrazy i otwieranie runów są tylko w aplikacji.

## Znane ograniczenia

- Tylko Windows, bez podpisu kodu i instalatora.
- Mapa tła wymaga internetu.
- Wysokości budynków bez tagów to założenia, nie pomiar.

## Budowa ze źródeł

```
scripts\viz_build.bat
```

Wymaga [uv](https://docs.astral.sh/uv/). Skrypt tworzy venv w `build_viz\`, buduje paczkę PyInstaller, sprawdza, że exe się uruchamia, dokłada licencje bibliotek i pakuje zip. To ten sam skrypt, którego używa workflow wydania (`viz-v*`).
