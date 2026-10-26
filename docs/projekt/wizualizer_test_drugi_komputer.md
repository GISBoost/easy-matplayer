# Test easy-matplayer na drugim komputerze (A4)

Cel: sprawdzić na zwykłym Windowsie z działającym WebView2 to, czego nie da się sprawdzić w Windows Sandbox. Około 15 minut.
Wersja: 0.1.0 (zip z gałęzi `claude/viz-fundamenty-e093b2`). Wymagania: Windows 10 22H2 albo 11, 64-bit. Python i narzędzia deweloperskie **nie są** potrzebne (i najlepiej, żeby ich nie było).

## Co skopiować na drugi komputer

1. `build_viz\easy-matplayer-test.zip` (105 MB: aplikacja, `README.txt` i `demo-kutno`; składa go `scripts\viz_pack_test.py`, więc krok 13 nie wymaga osobnego zipa dema). Do kroku 14 przyda się też adres usługi mapowej (wklejasz go w panelu mapy, wybierasz warstwę):
   - OSM (WMS): `https://ows.terrestris.de/osm/service`, warstwa `OSM-WMS` (cały świat, EPSG:3857)
   - ortofoto Polska (WMS): `https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution` (Geoportal; serwer czasem zwraca chwilowe 404, wtedy ponów)
   - ortofoto Wiedeń (WMTS): `https://mapsneu.wien.gv.at/basemapneu/1.0.0/WMTSCapabilities.xml`, warstwa `bmaporthofoto30cm`
2. Folder `build_viz\run_do_testu` (ok. 45 MB; run Kutno 25%: eventy, sieć, plany; bez indeksu, więc pierwsze otwarcie zbuduje go od zera, ok. 25–60 s).
3. `build_viz\easy-matplayer-demo-kutno.zip` (59 MB, jeden run demo z gotowym indeksem i budynkami; do kroku 13).
4. Opcjonalnie plik `lodzkie-*.osm.pbf` (132 MB, z `data\raw\osm`), do kroku 9.

## Kroki (odhaczaj, przy problemie zapisz co zobaczyłeś i zrób zrzut)

1. [ ] Rozpakuj zip do folderu **ze spacją i polskimi znakami**, np. `C:\Users\<ty>\Desktop\Mój test żółć`. Powinien powstać folder `easy-matplayer` z `easy-matplayer.exe`.
2. [ ] Dwuklik na `easy-matplayer.exe`. Jeśli Windows pokaże „Chroniony komputer” (SmartScreen): „Więcej informacji” → „Uruchom mimo to”. **Zapisz, czy się pojawiło** (plik nie jest podpisany).
3. [ ] Pojawia się okno wyboru folderu „wskaż folder runu MATSim…”. Anuluj: program kończy się bez błędu. Uruchom ponownie.
4. [ ] Wskaż folder `run_do_testu`. Pokazuje się okno z paskiem postępu (procenty rosną), potem okno główne z mapą i ruchem. **Zanotuj czas do pojawienia się okna.**
5. [ ] W oknie: odtwarzanie (spacja albo przycisk), przesuwanie osi czasu, zmiana prędkości, kliknięcie auta, przycisk 3D (budynki są tylko z plikiem OSM, krok 9), przycisk pokazujący cały obszar. Czy cokolwiek jest puste, czarne albo się zacina?
6. [ ] Zamknij okno krzyżykiem. Sprawdź w Menedżerze zadań, czy nie został proces `easy-matplayer.exe` ani `msedgewebview2.exe` z tej aplikacji.
7. [ ] Uruchom ponownie dwuklikiem: powinien od razu otworzyć ten sam run (bez pytania o folder, szybko, bo indeks jest gotowy).
8. [ ] Wyłącz Wi-Fi/Ethernet (tryb samolotowy), uruchom aplikację. Podkład mapy może się nie wczytać (to oczekiwane), ale okno, ruch i sterowanie mają działać. Włącz sieć z powrotem.
9. [ ] (Opcjonalnie) Panel po prawej: „plik OSM…” → wskaż `lodzkie-*.osm.pbf`. Pasek postępu, potem budynki 3D i drogi łamane (wpis w panelu „łamane: ... z ...”, przycisk 3D działa). „zapomnij plik” wraca do prostych odcinków.
10. [ ] Plik dziennika `easy-matplayer.log` leży obok `easy-matplayer.exe`. Czy jest, czy kończy się wierszem `okno run=...`.
11. [ ] Błędny run: uruchom aplikację i wskaż folder bez plików `output_events.xml.zst`. Pojawia się komunikat po polsku, a nie awaria.
12. [ ] Odinstalowanie: usuń folder aplikacji i `%LOCALAPPDATA%\easy-matplayer`. Nic poza tym nie powinno zostać (nie ma instalatora ani wpisów w rejestrze poza WebView2).

## Co mi przekazać

Dla każdego kroku: przeszło / nie przeszło, a przy „nie” komunikat albo zrzut oraz `easy-matplayer.log`. Plus dane maszyny: wersja Windows, karta graficzna (jest dedykowana, czy tylko zintegrowana), czy WebView2 był zainstalowany wcześniej (Ustawienia → Aplikacje → „Microsoft Edge WebView2 Runtime”), czas z kroku 4.
13. [ ] Demo: rozpakuj `easy-matplayer-demo-kutno.zip` do innego folderu ze spacją, w aplikacji wskaż rozpakowany `demo-kutno`. Okno ma się pojawić w kilka sekund (bez paska postępu), z budynkami 3D (przycisk 3D) **bez** wskazywania pliku OSM; w panelu „OSM: dane zapisane przy runie”. Zapisz czas.
14. [ ] Podkłady WMS/WMTS (wymaga internetu): w panelu mapy wklej adres OSM z punktu 1 i wybierz `OSM-WMS`, potem ortofoto z drugiego adresu. Kafelki mają się pojawić pod ruchem. Po wpisaniu błędnego adresu ma być komunikat po polsku, a nie awaria.
15. [ ] Skala i oddalenie: w lewym dolnym rogu mapy jest skala (metry/kilometry), która zmienia się przy przybliżaniu; kółkiem myszy da się oddalić do widoku całego kraju (zoom 3).
