# Handoff: styl interfejsu easy-matplayer (wersja mobilna jako wzorzec)

Dla następnego agenta, który ma przenieść ten styl na aplikację okienkową (Windows, pywebview/WebView2) i na stronę otwieraną na komputerze. Stan na 2026-10-31. Autor: Claude (sesja o układzie na telefon). Decyzje wizualne podjął właściciel (Michał Kaczorowski), poniżej jest to, co zostało wybrane i dlaczego.

## 1. Co to jest i gdzie leży

- Jeden plik klienta dla wszystkich wersji: `viz_player/shell.html` (HTML, CSS, JS) plus `viz_player/engine.js`. Używają go aplikacja okienkowa i strona na GitHub Pages (`https://gisboost.github.io/easy-matplayer/`, tryb web wykrywa się po `?run=`, stała `WEB`).
- **Styl mobilny to jeden blok `@media (max-width: 700px)`** na końcu `<style>` w `shell.html` (od komentarza „Telefon (≤ 700 px)”) plus ok. 60 linii JS po `translateStatic()` (arkusz, pigułka, odtwarzacz). Poniżej 700 px jest „nowy” wygląd, powyżej dalej stary, ciemny, techniczny układ (mapa + panel 320 px po prawej + dolny pasek 52 px).
- **Moodboard (wybór wariantu): `docs/projekt/mobile_moodboard.html`.** Otwórz go w przeglądarce, to samodzielny plik bez zależności. Zawiera stan obecny, język wizualny, trzy propozycje (A arkusz, B zakładki, C kapsuła), tabelę „gdzie trafia każdy element”, porównanie i źródła. Skopiuj jego formę (makiety w prawdziwych wymiarach, skalowane, ciemne tło, tabela mapowania, rekomendacja), gdy będziesz robić moodboard dla desktopu.
- Dziennik decyzji i dowodów: `docs/projekt/wizualizer_postep.md`, sekcje „Telefon: …” (3 sekcje, 2026-10-31).
- Dokumentacja użytkownika: `docs/viz/README_pl.md` i `README.md`, sekcja „Telefon”.

## 2. Decyzja właściciela (mobilna)

Wariant A z moodboardu (mapa cały czas widoczna, panel to arkusz u dołu), ale z dwiema zmianami:
- **Odtwarzacz z wariantu B1**: osobna pływająca karta, nie część arkusza. **Dolnego paska z 4 zakładkami właściciel nie chce.**
- **Pływająca pigułka zegara** u góry (czas, liczba aut) zostaje.
- Odtwarzacz ma motyw szkła (rozmycie tła).

Co właściciel mówił dosłownie: „fajne że mapa jest cały czas widoczna”, „ten odtwarzacz na dole też może być pływający i z motywem szkła”, „ta pływająca pigułka albo ‘tabletka’ zegara niech też będzie”. Po teście na telefonie: legenda ma być na dole tuż nad odtwarzaczem, podpis OSM nie może być osobną tabliczką na mapie (ma być w karcie odtwarzacza / w ustawieniach i skrócony), zegar bez sekund.

Ocena właściciela na desktop: chce „design w miarę podobny do tego, co jest teraz mobilnie” (pływające kształty, zaokrąglenia, szkło, trochę Apple, nowocześnie, minimalistycznie, ciemny motyw).

## 3. Język wizualny (to trzeba odtworzyć)

Wartości z kodu i moodboardu, nie do zgadywania:

| Element | Wartość |
|---|---|
| Tło mapy / podkład | `#121418` (tło okna `#0b0b0d` w moodboardzie) |
| Szkło (pływające elementy) | `rgba(44,44,46,.72)` + `backdrop-filter: blur(24px) saturate(1.8)` + obramowanie `.5px solid rgba(255,255,255,.14)` (zmienna `--glass`) |
| Lita szarość (arkusz, listy) | `#1c1c1e`; uchwyt arkusza też `#1c1c1e` (przy innym kolorze widać szew) |
| Powierzchnie wtórne (pigułki, chipy, kontrolki segmentowane) | `rgba(118,118,128,.24)` do `.28`; aktywny segment `#636366` |
| Akcent | `#0a84ff` (przycisk start, aktywne chipy: tło `rgba(10,132,255,.22)` + obrys `#0a84ff`); jaśniejszy `#7eb6ff` dla linków |
| Przełączniki | styl iOS: `appearance:none`, 46×28 px, włączony `#30d158` (zielony), gałka biała z cieniem |
| Tekst | główny `#f2f2f7`, wtórny `rgba(235,235,245,.6–.85)`, mute `#9aa3b2` |
| Kształty | kapsuły (promień = pół wysokości: pigułka 36 px → 18 px, pigułka mnożnika 44 px → 22 px), karta odtwarzacza 28 px, arkusz 26 px, grupy list 12 px, chipy ≥ 40 px |
| Typografia | `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, system-ui`; treść 16–17 px, etykiety 13 px, `font-variant-numeric: tabular-nums` dla zegara i liczb |
| Ikony | liniowe SVG 24 px, `stroke: currentColor; stroke-width: 1.8; round caps/joins`, bez wypełnienia |
| Cele dotyku | min. 44×44 px (na desktopie można mniej, ale zostaw ten sam język, nie 28 px jak w starym panelu) |
| Ruch | 0,32 s `cubic-bezier(.2,.8,.2,1)` dla arkusza, bez migania |
| Kolory danych | **bez zmian**: klasy aut, skala prędkości (czerwony → żółty → cyjan), kolory typów aktywności, kolory dróg OSM |

Elementy, które istnieją i są wzorcem do powtórzenia na desktopie:
- `#mpill`: pływająca pigułka z zegarem i licznikiem aut (zegar bez sekund tylko w pigułce; pasek desktopowy pokazuje sekundy).
- `#mstack`: pionowy szklany stos przycisków 44 px (3D, dopasuj widok, ustawienia), przyciski rozdzielone cienką linią `.5px`.
- `#bar` jako pływająca karta: siatka `48px | 1fr | auto` (start, suwak, pigułka mnożnika), drugi rząd (po dotknięciu mnożnika) ◀ 1× 10× 60× 300× ▶, trzeci rząd: próbka, uwagi o runie, skrócona atrybucja.
- `#panel` jako arkusz z uchwytem (`#grab`), trzy wysokości (zamknięty / ok. 46% / wysoko), zawartość uporządkowana CSS-em `order` (szczegóły, widok, klasy, przełączniki, wyszukiwarka, podkłady, o runie).

## 4. Co stosować, czego nie

**Stosuj:**
- Szkło tylko na elementach pływających nad mapą (pigułka, stos przycisków, karta odtwarzacza). Lita szarość `#1c1c1e` na dużych powierzchniach z tekstem (arkusz, listy), bo szkło nad mapą psuje czytelność.
- Jeden rodzaj kontrolki na jedną funkcję: przełączniki iOS na włącz/wyłącz, kontrolka segmentowana na wybór 2–4 opcji, chipy na wielokrotny wybór (klasy aut), pigułka na pojedynczą wartość (mnożnik).
- Ukrywaj zaawansowane rzeczy (WMS, obrazy, otwórz run, plik OSM) głębiej, nie usuwaj ich z aplikacji desktop.
- Zasada „mapa jest bohaterem”: nic stałego nie zajmuje mapy, kontrolki pływają z marginesem 12 px, a nie są doklejonymi paskami.
- `env(safe-area-inset-*)` tylko na telefonie; na desktopie nie potrzeba.

**Nie stosuj:**
- Dolnego paska zakładek (wprost odrzucone przez właściciela).
- Osobnych „tabliczek” na drobne napisy (np. atrybucja) rozrzuconych po rogach mapy. Drobne teksty mają mieszkać w karcie odtwarzacza albo w ustawieniach.
- `display: none` na kontenerach MapLibre, jeśli nie masz pewności, co jest w środku (patrz pułapki).
- Zmiany kolorów danych (auta, drogi, skala) przy okazji zmiany stylu.
- Nowych bibliotek CSS/JS (projekt jest bez bundlera, bez frameworka; wszystko inline w `shell.html`). Brak dodatkowych zależności bez pytania właściciela.
- Tekstu bez tłumaczenia: interfejs jest dwujęzyczny (`viz_player/i18n.py`, klucze to polskie teksty). Każdy nowy napis dodaj do `i18n.py` (EN).

## 5. Pułapki (kosztowały błędy, nie powtarzaj)

1. **deck.gl montuje kanwę w `.maplibregl-ctrl-top-left`.** Ukrycie tego kontenera wyzerowało rysowanie aut, dróg i budynków (kanwa 1×1). Chowaj tylko `.maplibregl-ctrl-group`. Test regresyjny: `test_phone_css_keeps_deck_container`.
2. **Funkcja `dragEnd` już istnieje** (przeciąganie obrazów). Nowa funkcja o tej samej nazwie nadpisuje ją po cichu. Nazywaj funkcje unikalnie (`sheetDragEnd`) i szukaj grepem przed dodaniem.
3. **`showPanel` jest wołane co 250 ms** przy zaznaczonym obiekcie. Nie wkładaj do niego efektów ubocznych typu „otwórz panel”; efekty idą do handlera akcji użytkownika.
4. **Specyficzność CSS:** `[hidden]{display:none!important}` i reguły `#id` mieszają się; przełączniki w panelu wymagały `order` i jawnych reguł (patrz bloki `#flash-types`).
5. **Atrybucja OSM** ma być widoczna (licencja). Skrót „© OpenStreetMap” w karcie, pełny tekst w ustawieniach. Nie usuwaj bez zastąpienia.
6. **Desktop ma asercję w smoke.** `viz_player/window.py` sprawdza układ komputerowy przy 1440 px (`desk != ["none","none","none","static","static",320]` zgłasza błąd, są tam: `#mpill`, `#mstack`, `#grab` ukryte, `#bar` i `#panel` `static`, kolumna 320). **Jeśli zmieniasz układ desktopu, zaktualizuj tę asercję świadomie i opisz w `wizualizer_postep.md`.** To nie jest obejście, to element testu.
7. **Dwie zasady z CLAUDE.md:** nie psuj aplikacji okienkowej (smoke na prawdziwym runie + po zmianach dotykających paczki exe z okrojonym PATH i pustym `EASY_MATPLAYER_DATA`) i nie rób pusha, merge ani tagów (to robi właściciel).
8. **Serwer testowy:** `python -m http.server` na Windows może podawać `.mjs` jako `text/plain` (moduł się nie ładuje: „Failed to fetch dynamically imported module”). Użyj własnego serwera z `mimetypes.add_type("text/javascript", ".mjs")`. Chrome cache’uje błędny typ per origin, więc zmień port.
9. **Serwery kafelków OSM blokują (HTTP 418)** po wielokrotnym ładowaniu z jednego adresu w krótkim czasie. To nie jest błąd aplikacji; nie ładuj mapy co chwilę w pętli testów.

## 6. Czego jeszcze nie ma na telefonie (nie przenoś ślepo)

Układ poziomy (telefon na boku dostaje układ komputerowy), przeciąganie arkusza za treść (tylko za uchwyt), Safari na iPhonie (`backdrop-filter`, `100dvh`), prawdziwy telefon (testowane na emulatorze z grafiką programową), wydajność przy dużej liczbie modeli 3D i budynków (plan w roadmapie `wizualizer_postep.md`), pierwszy zoom dopasowany do ruchu zamiast do całej sieci.

## 7. Jak testować (sprawdzone)

- **Desktop / szeroki ekran:** wbudowana przeglądarka Claude Desktop (`mcp__Claude_Browser__*`) otwiera stronę z prawdziwym widokiem desktopowym. Zmiana szerokości okna emulowanym viewportem **nie działa** w tej przeglądarce dla układu mobilnego, więc mobilny testuj w emulatorze.
- **Telefon:** Android Studio w `G:\Android`, AVD `pixel` (Android 35, Chrome). Start: `ANDROID_AVD_HOME=G:\Android\avd`, `emulator -avd pixel -gpu swiftshader_indirect`. Host z emulatora to `10.0.2.2`. Dotknięcia: `adb shell input tap x y` (współrzędne w pikselach 1080×2400), zrzut: `adb exec-out screencap -p`. DevTools: `adb forward tcp:9222 localabstract:chrome_devtools_remote` i skrypt z `websocket-client` (`suppress_origin=True`; wybieraj jedyną otwartą kartę, stare karty zawieszają połączenie).
- **Strona do testów lokalnych:** `scripts/web_build.py <folder z runem demo-kutno> <out>` (demo z wydania `viz-v0.1.0`, plik `easy-matplayer-demo-kutno.zip`), potem własny serwer (pkt 5.8). Szybka iteracja: skopiuj `viz_player/shell.html` do `<out>/player/index.html`.
- **Aplikacja okienkowa:** `uv run --group viz python -m viz_player --smoke <run>`; w smoke widać `zrzut=` do pliku `smoke.png`.
- **Testy:** `uv run --group viz pytest viz_player/tests -q` (130 przechodzi).

## 8. Zapis researchu (mobilny)

Ważne: research był skromny i uczciwie opisany w moodboardzie.
- Zweryfikowane w tym wyszukiwaniu: Apple Human Interface Guidelines, **Sheets** (detenty medium i large, grabber, stopniowe ujawnianie treści) oraz WWDC21 „Customize and resize sheets” (`developer.apple.com/videos/play/wwdc2021/10063/`), kopia treści HIG: `unpkg.com/apple-hig-mcp@1.1.3/content/sheets.md`.
- **Z wiedzy własnej, niezweryfikowane w wyszukiwaniu:** cel dotyku min. 44×44 pt, materiały (rozmycie, „vibrancy”), pasek zakładek, kolory systemowe iOS (`#0a84ff`, `#30d158`, `#1c1c1e`, `#2c2c2e`, `#636366`), wartości rozmycia 24–30 px. Przy desktopie zrób **rzeczywisty research ze źródłami** i oznaczaj, co zweryfikowałeś.
- Wniosek, który zadziałał: wzorzec „mapa na całym ekranie + elementy pływające + arkusz o detentach” (Mapy Apple, Znajdź, Pogoda) jest znany użytkownikom i zostawia mapę widoczną. Jego odpowiednik na desktopie to prawdopodobnie pływające panele (szklane „wyspy”) zamiast pełnej kolumny, ale to hipoteza do zbadania i do wyboru przez właściciela, nie decyzja.

## 9. Pytania, które zostają dla właściciela (nie rozstrzygaj sam)

- Czy panel boczny na desktopie ma pozostać kolumną, stać się pływającą szklaną wyspą, czy mieć obie formy (przełączane)?
- Czy pasek odtwarzacza ma być pływającą kartą jak na telefonie, czy węższym paskiem z wyśrodkowaną kartą?
- Czy aplikacja okienkowa i web na desktopie mają wyglądać identycznie (to jeden plik, więc domyślnie tak)?
- Zegar: z sekundami na desktopie (jak dziś) czy bez?
