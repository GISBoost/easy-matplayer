# Licencje danych i wyników

Repozytorium MATSim Kutno ma dwie licencje. Kod jest na GPL-3.0-or-later (plik `LICENSE`). Dane, wyniki i raporty mają licencje opisane poniżej.

## Kod (GPL-3.0-or-later)

Dotyczy kodu w `pipeline/`, `matsim/src/`, `blender/`, `docs/research/G4_beeline/` oraz skryptów w `reports/`. Pełny tekst: [LICENSE](LICENSE).

Przykładowy projekt MATSim w `matsim/` ma własną licencję GPL-2.0-or-later (`matsim/LICENSE`). GPL-3.0-or-later jest z nią zgodna.

## Dane wyjściowe z GUS (CC BY 4.0)

Dotyczy danych wyprowadzonych z publikacji GUS: tablic NSP 2021, BDL (P4507, P4508, TABL. 5), macierzy dojazdów do pracy, geometrii BREC 2021 i tabel obwodów. Autorem danych źródłowych jest Główny Urząd Statystyczny.

Wyniki z tych danych (plany, populacja, macierze, tabele, wykresy) są na licencji **Creative Commons Uznanie autorstwa 4.0 (CC BY 4.0)**. Wymagane jest podanie źródła: „Główny Urząd Statystyczny” i nazwa publikacji.

## Dane z OpenStreetMap (ODbL 1.0)

Dotyczy sieci drogowej, budynków i użytkowania terenu wyprowadzonych z OSM. Źródło: © OpenStreetMap contributors. Dane z OSM są na licencji **Open Database License 1.0 (ODbL)**.

Zgodnie z ODbL każda publiczna, wyprowadzona baza danych zawierająca dane z OSM musi być udostępniona na tej samej licencji (ODbL) z podaniem autorstwa. Dotyczy to m.in. `scenarios/kutno/network*.xml.gz` i plików OSM w `scenarios/kutno/osm/`, jeśli zostaną opublikowane.

## Dane, których nie wolno publikować

Dane z TomTom (wariant A, D22) i z innych API komercyjnych nie są w repozytorium. Wyjątek to zagregowane metryki i raporty. Nie są na licencji CC BY ani ODbL.

Dane z Senozon AG (licencja własna) nie są używane w tym projekcie.

## Źródła

Każde źródło ma opis, status i licencję w [docs/ZRODLA.md](docs/ZRODLA.md).
