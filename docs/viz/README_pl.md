# easy-matanimation

Odtwarzacz wyników symulacji [MATSim](https://matsim.org/): ruch samochodów na mapie, w 2D i 3D, z budynkami. Działa lokalnie na Windowsie, bez instalacji i bez Pythona.

## Pobranie i uruchomienie

1. Z [Releases](../../../../releases) pobierz `easy-matanimation-windows.zip` (ok. 46 MB) i rozpakuj w dowolne miejsce (ścieżka może mieć spacje i polskie znaki).
2. Uruchom `easy-matanimation.exe`. Jeśli Windows pokaże „Chroniony komputer” (SmartScreen), kliknij „Więcej informacji”, potem „Uruchom mimo to”. Plik nie jest podpisany certyfikatem.
3. Wskaż folder runu MATSim. Przy pierwszym otwarciu program buduje indeks (od kilkunastu sekund do minuty, widać pasek postępu). Potem ten sam run otwiera się od razu, a program pamięta ostatni run.

Wymagania: Windows 10 22H2 albo 11 (64-bit) i Microsoft Edge WebView2 Runtime (jest w Windows 11 i w większości Windows 10; jeśli go brakuje, program pokaże komunikat z linkiem do instalatora). Karta graficzna z obsługą WebGL; zintegrowana wystarcza.

## Demo

`easy-matanimation-demo-kutno.zip` (ok. 59 MB, osobny plik w tym samym wydaniu) to run Kutna (25% mieszkańców, 100 iteracji, sieć z zakazami skrętu z OSM) z gotowym indeksem. Rozpakuj i wskaż folder `demo-kutno`. Otwiera się w kilka sekund, z budynkami 3D, bez żadnych dodatkowych plików.

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

`%LOCALAPPDATA%\easy-matanimation\`: dziennik `easy-matanimation.log` (przy problemach wklej jego koniec w zgłoszeniu), pamięć ostatniego runu i pliku OSM. Odinstalowanie to usunięcie folderu programu i tego folderu. Program nie zapisuje nic w rejestrze.

## Sieć

Do działania mapa podkładowa pobiera kafelki z publicznych usług WMS/WMTS (adresy w panelu mapy). Bez internetu ruch i sterowanie działają, brakuje tylko podkładu. Program nie wysyła żadnych danych o runie.

## Licencje

- Program: GPL-3.0-or-later (plik `LICENSE`). Biblioteki w paczce: teksty licencji w `THIRD_PARTY/` w folderze programu.
- Demo: wyniki symulacji CC BY 4.0, plany pochodne danych GUS (CC BY 4.0), sieć i budynki © współtwórcy OpenStreetMap (ODbL 1.0). Szczegóły: `LICENSE-DATA.md` w zipie demo. W demo nie ma danych komercyjnych.
- Modele samochodów: Quaternius, CC0.

## Znane ograniczenia

- Tylko Windows, bez podpisu kodu i instalatora.
- Mapa tła wymaga internetu.
- Wysokości budynków bez tagów to założenia, nie pomiar.

## Budowa ze źródeł

```
scripts\viz_build.bat
```

Wymaga [uv](https://docs.astral.sh/uv/). Skrypt tworzy venv w `build_viz\`, buduje paczkę PyInstaller, sprawdza, że exe się uruchamia, dokłada licencje bibliotek i pakuje zip. To ten sam skrypt, którego używa workflow wydania (`viz-v*`).
