# Licencje: program, biblioteki, modele, dane demo i podkłady mapowe

Dotyczy repozytorium easy-matanimation i paczek z wydania (`easy-matanimation-windows.zip`, `easy-matanimation-demo-kutno.zip`). Ten plik jest dołączany do zipa demo. Wersja angielska: [LICENSE-DATA.en.md](LICENSE-DATA.en.md) (tłumaczenie pomocnicze, wiążący jest tekst polski).

## 1. Program (GPL-3.0-or-later)

Kod odtwarzacza (`viz_player/`, `pipeline/`, `scripts/`, testy, `config/viz_buildings.toml`, dokumentacja) jest na licencji **GNU GPL 3.0 lub nowszej**. Pełny tekst: [LICENSE](LICENSE).

## 2. Biblioteki w repozytorium i w paczce

| składnik | licencja | gdzie |
|---|---|---|
| MapLibre GL JS 6.0.0 | BSD-3-Clause | `viz_player/vendor/maplibre/` (tekst w `LICENSE`) |
| deck.gl 9.4.0 | MIT, © vis.gl contributors | `viz_player/vendor/deck.min.js`, tekst w `viz_player/vendor/deck.LICENSE` |
| LowPoly Car pack (model samochodu), Quaternius | CC0 (domena publiczna) | `viz_player/vendor/quaternius/`, opis w `CREDITS.md` |
| biblioteki Pythona w paczce (numpy, pyproj, pywebview, lxml, Pillow, osmium, zstandard i ich zależności) oraz środowisko Python | własne licencje każdej biblioteki | teksty w folderze `THIRD_PARTY/` obok programu (tworzy je `scripts/viz_third_party.py` przy budowie) |

Licencje BSD i MIT wymagają zachowania noty i tekstu licencji przy redystrybucji. Dlatego pliki z `vendor/` zostają w paczce razem z licencjami, a `THIRD_PARTY/` jest dołączany do każdej paczki.

## 3. Dane w zipie demo

Demo (`easy-matanimation-demo-kutno.zip`) zawiera jeden run symulacji MATSim dla Kutna (25% mieszkańców) z gotowym indeksem, drogami łamanymi i budynkami:

- **Wyniki symulacji** (eventy, plany wynikowe): **CC BY 4.0**, jak pliki wejściowe i wyjściowe przykładowego projektu MATSim (`matsim-example-project`, sekcja Licenses jego README).
- **Populacja i plany podróży**: dane syntetyczne pochodne publikacji Głównego Urzędu Statystycznego (GUS: NSP 2021, BDL, macierz dojazdów do pracy). Licencja **CC BY 4.0**, wymagane jest podanie źródła: „Główny Urząd Statystyczny” i nazwa publikacji.
- **Sieć drogowa, budynki i drogi łamane** (w runie i w folderze `viz/`): © współtwórcy OpenStreetMap (https://www.openstreetmap.org/copyright), **Open Database License 1.0 (ODbL)**. Baza wyprowadzona z OSM, którą udostępniamy publicznie, zostaje na ODbL z atrybucją.
- W demo nie ma danych komercyjnych ani danych na licencjach niekomercyjnych (CC BY-NC).

Podziały licencji w demo (CC BY dla wyników i planów, ODbL dla danych z OSM) opisują stan wiedzy autora projektu. Przed publicznym wydaniem właściciel potwierdza je w `docs/projekt/wizualizer_postep.md` (zapis A5).

## 4. Runy innych autorów

Program otwiera dowolny run MATSim zapisany w `.xml.zst`. Runy i scenariusze innych autorów mają własne licencje (np. Kelheim i Wiedeń 2023.2: CC BY-NC 4.0, użytek niekomercyjny; Berlin: CC BY 4.0). **Nie dołączamy ich do wydań ani do tego repozytorium.** Wolno je otwierać na własnym komputerze zgodnie z ich licencją. Lista i odnośniki: [docs/viz/README_pl.md](docs/viz/README_pl.md).

## 5. Podkłady mapowe

Program nie zawiera kafelków mapy. Domyślnie tło jest jednolite. Użytkownik może sam dodać usługę WMS, WMTS lub XYZ albo własny obraz (panel mapy). Warunki użycia, atrybucja i ewentualny koszt każdej usługi należą do jej dostawcy i do użytkownika. Program wyświetla atrybucję usługi tam, gdzie ją udostępnia. Żądania kafelków ujawniają dostawcy usługi oglądany obszar mapy.

Opcjonalny podkład CARTO (ciemna mapa bez etykiet, dane © OpenStreetMap contributors © CARTO) działa tylko z kluczem wpisanym lokalnie w `config/viz_basemap.local.toml`. Klucza nie ma w repozytorium ani w paczkach.

## 6. Czego nie ma w repozytorium

Nie ma w nim danych źródłowych GUS ani OSM, dużych plików OSM (`*.pbf`, poza małym plikiem testowym `viz_player/selftest/kutno_tiny.osm.pbf`, który jest wycinkiem OSM: © współtwórcy OpenStreetMap, ODbL 1.0), runów MATSim ani kluczy dostępowych. Program otwiera pliki OSM wskazane przez użytkownika i nie wysyła żadnych danych o runie.
