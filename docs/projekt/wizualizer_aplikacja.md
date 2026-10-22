# Wizualizer jako aplikacja z pulpitu i release na GitHubie: plan (D27)

Cel: ktoś pobiera z GitHuba Releases jeden zip, rozpakowuje, klika `easy-matviz.exe` i ma działającą aplikację, bez Pythona, `uv` i repozytorium. Do tego osobny zip z małym runem demo.

## Decyzje właściciela (2026-10-22)

| Pytanie | Decyzja |
|---|---|
| Gdzie release | Docelowo **nowe repo** (później). Teraz wszystko lokalnie w tym repo, tak żeby dało się to przenieść. |
| Format | **Tylko zip** (PyInstaller onedir, rozpakuj i uruchom), jak `chart_lab-windows.zip` w `GISBoost/easy-OTP`. Bez instalatora. |
| Dane demo | **Mały run demo osobnym plikiem** w release. Najpierw sprawdzić rozmiar i licencje danych. |
| Push | Wszystko przygotowuję lokalnie. **Push, merge do main i tag robi właściciel.** Ja niczego nie wypycham. |
| Zakres | PyInstaller **onedir**, Windows 10/11 x64. Bez podpisu kodu (SmartScreen: „Więcej informacji → Uruchom mimo to”). |

## Wzór: chart_lab (`easy-OTP/tools/chart_lab`)

Przejmujemy sprawdzone rozwiązania i nie wymyślamy ich od nowa:

- jeden skrypt budowania (`build_installer.bat`) używany tak samo lokalnie i w CI, workflow YAML tylko go woła;
- `chart_lab.spec` z `pathex` na rodzeństwo importowane przez `sys.path.insert` (PyInstaller nie wykonuje tego wywołania, więc bez `pathex` pakiet się buduje, a po uruchomieniu brakuje modułów);
- workflow `chart_lab_release.yml`: wyzwalacz tag z prefiksem (`chart_lab-v*`) i ręczny `workflow_dispatch`, `windows-latest`, `permissions: contents: write`, `concurrency` po tagu, sprawdzenie czy release już istnieje (idempotencja), zip przez `Compress-Archive`, `gh release create` z notką licencyjną;
- zip ma ok. 108 MB (chart_lab, Gradio); u nas oczekuję mniej, bo nie ma geopandas/pandas/scipy;
- lekcja z chart_lab: błąd w zamrożonej wersji wychodzi dopiero po **uruchomieniu zbudowanego exe**, nie po samym buildzie. Dlatego każdy milestone kończy się uruchomieniem exe.

Różnice u nas: okno pywebview zamiast Gradio w przeglądarce, `console=False` (okno bez czarnej konsoli), tag `viz-v*`, osobny zip demo.

## Zasady wspólne dla milestone’ów

- Każdy milestone to osobny commit `wizualizer: <co>` (trailer Co-Authored-By), bez pusha i bez merge.
- Przed commitem: `uv run --group viz pytest viz_player/tests -q` (72 testy) i smoke na runie z repo. Wynik wpisuję do `wizualizer_postep.md` razem z dowodem.
- Dokumentacja z każdym milestone’em: `wizualizer_postep.md`, `PROGRESS.md`, `ROADMAP.md`, `docs/research/wizualizer_odtwarzacz.md`, w razie decyzji `DECISIONS.md`.
- Gdy po drodze trzeba coś rozstrzygnąć (nazwa, ikona, licencja, dane demo), pytam właściciela, a nie zgaduję.
- Pliki, które trafią do nowego repo, trzymam rozpoznawalnie: `viz_player/`, `pipeline/viz_*.py`, ich testy, `scripts/viz_*`, jeden workflow. Nie dopisuję do nich zależności od reszty repo.

## Milestone’y

### M1. Ścieżki: zasoby do odczytu osobno od danych do zapisu

Dlaczego: dziś `ROOT = parents[1]`, a zapisy idą do `ROOT/output/...` (stan, usługi WMS, rastry, profil WebView2, katalog strony). W paczce katalog programu bywa tylko do odczytu, a `pipeline/` trzeba znaleźć.

- Nowy `viz_player/paths.py`: `RES` (zasoby: `vendor/`, `shell.html`, `engine.js`, `pipeline/`), `DATA` (zapisy). W repo: `RES = ROOT`, `DATA = ROOT/"output"` (nic się nie zmienia dla właściciela). W paczce (`sys.frozen`): `RES = sys._MEIPASS`, `DATA = %LOCALAPPDATA%\easy-matviz`. Zmienna `EASY_MATVIZ_DATA` nadpisuje `DATA` (testy).
- Wszystkie `ROOT / "output" / ...` w `player.py`, `window.py`, `bench.py` przechodzą na `DATA`. `config/viz_basemap.local.toml` przechodzi na `DATA`, bez wymogu pliku.
- Zapamiętany run poza repo musi być zapisywany jako ścieżka bezwzględna (dziś jest względna wobec `ROOT`, gdy leży w repo).

Weryfikacja: 72 testy zielone, nowe testy `paths` (tryb repo, tryb zamrożony przez podmianę `sys.frozen`/`_MEIPASS`, nadpisanie zmienną), smoke w trybie repo bez zmian wyniku, `git diff` nie dotyka `output/`.

### M2. Zachowanie aplikacji uruchomionej dwuklikiem

Dlaczego: bez argumentu i bez zapisanego runu program dziś kończy się komunikatem w konsoli. Aplikacja okienkowa nie ma konsoli (`print` przy `sys.stdout is None` wywali program).

- Start bez runu: okno wyboru folderu (stdlib `tkinter.filedialog`, bez nowych zależności). Anulowanie kończy po cichu. Zapamiętany run nadal otwiera się bez pytania.
- Komunikaty (`note`, `print`) bezpieczne bez konsoli, zapis do `DATA/easy-matviz.log` (rotacja do kilku MB).
- Błędy startu pokazane oknem komunikatu (brak WebView2 z linkiem do instalatora, folder bez eventów, uszkodzony indeks), a nie znikającym oknem.
- Budowa indeksu przy pierwszym otwarciu runu (ok. 80 s przy 100%) z widocznym postępem, bo bez konsoli użytkownik widziałby pustkę. Do ustalenia z właścicielem, czy wystarczy napis „Buduję indeks…” z licznikiem, czy pełny pasek.
- Wersja aplikacji w jednym miejscu (`viz_player/__init__.py`: `__version__`), widoczna w tytule okna/stopce i w `--version`.

Weryfikacja: testy; start bez argumentu na pustym `EASY_MATVIZ_DATA` (okno wyboru, wybór runu z indeksem, wybór runu bez indeksu: postęp, potem odtwarzanie); smoke; uruchomienie z `pythonw`, żeby sprawdzić brak konsoli; zrzut okna z postępem.

### M3. Pierwsza paczka lokalnie (PyInstaller onedir)

- `viz_player/requirements.txt` (szczupły zestaw: numpy, pyproj, zstandard, lxml, Pillow, pywebview, PyInstaller z przypiętymi wersjami; bez geopandas/pandas/scipy/matplotlib). Budowa w osobnym venv, tak jak chart_lab, żeby PyInstaller nie skanował ciężkich pakietów z głównego projektu.
- `viz_player/easy-matviz.spec`: `pathex=[pipeline]`, `hiddenimports` dla `viz_*`, `datas` z `vendor/`, `shell.html`, `engine.js`, `collect_data_files("pyproj")` (proj.db), tkinter, `excludes` dla zbędnych, `console=False`, ikona `.ico`, wersja w metadanych exe.
- `scripts/build_viz.bat` (jedyne źródło prawdy budowania, tak jak `build_installer.bat`): venv, `pip install -r`, PyInstaller, zip `easy-matviz-windows.zip`.
- Ikona: potrzebna decyzja właściciela (własny plik czy prosty znaczek generowany przeze mnie).

Weryfikacja (to jest właściwy test): `easy-matviz.exe --smoke <run>` na zbudowanym folderze, uruchomiony z **okrojonym PATH** (bez `uv`, Pythona i `.venv`) i z `EASY_MATVIZ_DATA` w pustym katalogu. Smoke obejmuje budynki 3D, WMS, rastry i układy współrzędnych, więc brak `proj.db`, `lxml` czy modeli wyjdzie od razu. Do tego zrzut okna i pomiar: rozmiar folderu i zipa, czas startu do pierwszej klatki.

### M4. Test na „czystym” komputerze

- Windows Sandbox (Windows 10 Pro to ma, wymaga włączenia funkcji i restartu: **pytanie do właściciela**) albo drugi komputer. Zip rozpakowany w innej ścieżce, w tym ze spacją i polskimi znakami, i uruchomiony z konta bez narzędzi deweloperskich.
- Przypadki: pierwszy start bez danych, otwarcie runu, zamknięcie i ponowny start (zapamiętany run), brak sieci (WMS pokazuje błąd, reszta działa), start bez GPU (SwiftShader, wolno, ale ma się uruchomić i pokazać komunikat), brak WebView2 (komunikat M2, sprawdzany na maszynie/Sandboxie bez Edge, jeśli się da).
- Z Sandboxa poprawka: wszystko, czego brakuje, wraca do M3.

Weryfikacja: lista przypadków z wynikiem (przeszło / nie) w `wizualizer_postep.md`, zrzuty.

### M5. Run demo

- Wybór runu: najmniejszy sensowny (Kutno 10% lub 25%), do uzgodnienia z właścicielem po sprawdzeniu rozmiarów (`events`, indeks `viz/`, sieć).
- Zip `demo-kutno.zip` z gotowym indeksem `viz/`, żeby pierwsze otwarcie było natychmiastowe. Sprawdzić, czy zawiera tylko dane publiczne i wyprowadzone (GUS CC BY 4.0, OSM ODbL, bez TomTom/HERE, bez kluczy), plus `LICENSE-DATA` i atrybucja w README demo.
- Test: aplikacja z M3 otwiera zawartość zipa wypakowaną w nowe miejsce, przez wybór folderu, i pokazuje ruch.

Weryfikacja: smoke na wypakowanym demo, rozmiar zipa, przegląd listy plików pod kątem danych objętych licencją (TomTom: tylko agregaty w repo, bez porównań; zgodnie z memory).

### M6. Release engineering

- `LICENSE` (GPL-3.0-or-later) i `THIRD_PARTY.md` w zipie: MapLibre GL JS (BSD-3), deck.gl (MIT), Quaternius (CC0), pywebview (BSD-3), numpy, pyproj, lxml, Pillow, PyInstaller (wyjątek bootloadera), dane mapowe (OSM ODbL, kafelki: atrybucja).
- `docs/viz/README_pl.md` dla użytkownika: pobranie, SmartScreen, wymagania (Windows 10 22H2+/11 x64, WebView2), jak otworzyć run i demo, gdzie są logi i dane (`%LOCALAPPDATA%\easy-matviz`), jak odinstalować (skasować folder).
- `.github/workflows/viz_release.yml` wzorowany na `chart_lab_release.yml`: tag `viz-v*` + `workflow_dispatch`, `windows-latest`, idempotencja, woła `scripts\build_viz.bat`, zipuje, `gh release create` z notką i oba zipy (aplikacja + demo, jeśli demo jest w repo lub osobnym assecie). **Nie odpalam go**: bez pusha nie ruszy.
- Schemat wersji: `viz-v0.1.0`, wersja w `__version__` musi się zgadzać z tagiem (krok w workflow to sprawdza).
- Weryfikacja bez pusha: czysty klon repo w katalogu tymczasowym → `scripts\build_viz.bat` → smoke z M3 na wyniku (to dokładnie to, co zrobi CI); składnia workflow sprawdzona narzędziem do YAML/actionlint, jeśli da się je zdobyć bez instalowania czegokolwiek ryzykownego; lista komend dla właściciela (`git push`, tag, dispatch).

### M7. Przeniesienie do nowego repo (później, po Twoim „teraz”)

Osobne zlecenie po założeniu repo: lista plików do przeniesienia (`viz_player/`, `pipeline/viz_*.py` z testami, workflow, README, licencje), co zostaje (`g6_bake.py`, reszta pipeline), historia (czy przenieść z `git filter-repo`), aktualizacja ścieżek w workflow. Nie zaczynam, dopóki nie dostanę sygnału.

## Ryzyka

| Ryzyko | Co robię |
|---|---|
| Brakujące zasoby w paczce (proj.db, modele, vendor) | Smoke zbudowanego exe z okrojonym PATH w każdym milestone’ie od M3. |
| Antywirus / SmartScreen na niepodpisanym exe | Onedir (nie onefile), opis w README, ewentualnie zgłoszenie fałszywego alarmu do Microsoftu. Podpis kodu to osobna decyzja z kosztem. |
| Brak WebView2 na starym Windows 10 | Komunikat z linkiem (M2); weryfikacja w M4. |
| PyInstaller i pythonnet (pywebview) w wersji Pythona 3.12/3.13 | Wersje przypięte w `requirements.txt`; najpierw lokalny build (M3), CI dopiero po nim. |
| Rozmiar zipa | Pomiar w M3; jeśli > 150 MB, wykluczenia i przegląd zależności. |
| Zależność od `pipeline/` przy przenosinach do nowego repo | Pliki `viz_*` są samodzielne (zależności tylko numpy/zstandard/pyproj); sprawdzone w M7. |

## Ustalenia z M1 (2026-10-22)

- Nazwa aplikacji: **easy-matanimation** (ścieżka danych `%LOCALAPPDATA%\easy-matanimation`, plik `easy-matanimation.exe`, zip `easy-matanimation-windows.zip`). Tytuły okien i `user_agent` zmieniam w M2.
- **Źródło OSM (decyzja właściciela 2026-10-22):** domyślnie sieć z `network` runu (proste odcinki, bez budynków), opcjonalnie własny `.osm.pbf` wskazany przyciskiem (drogi zakręcone i budynki 3D, wynik w cache przy runie, ok. 5 MB). Demo niesie gotowe cache. Bez pobierania z Overpass/Geofabrik. Poprawka `build` bez PBF: zrobiona (A1b).

## Pytania do właściciela w trakcie (nie blokują M1)

1. Ikona aplikacji (M3): dostarczysz plik czy generuję prosty znaczek?
2. Pasek postępu indeksu (M2): sam napis z licznikiem czy pełny pasek?
3. Windows Sandbox (M4): czy mogę poprosić o włączenie funkcji (restart), czy masz drugi komputer?
4. Który run jako demo (M5), po sprawdzeniu rozmiarów.
5. Nazwa aplikacji i pliku: `easy-matviz` (taka jest dziś w tytule okna) czy `easy-matanimation` (nazwa projektu w D26)?
