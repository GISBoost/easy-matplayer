# Wersja przeglądarkowa: plan (W1, decyzja właściciela 2026-10-26)

Cel: użytkownik wchodzi na stronę, wybiera scenariusz z listy i od razu ogląda nagranie symulacji w przeglądarce, bez instalacji. Ten sam kod klienta co aplikacja desktopowa.

## Decyzje właściciela (2026-10-26)

| Pytanie | Decyzja |
|---|---|
| Priorytet | Przeglądarka na **komputerze**. Telefon i optymalizacja pod telefon są poza zakresem. |
| Kod | **Wspólny**: `viz_player/shell.html`, `engine.js`, `vendor/` i eksport v2 służą obu wersjom. Wersja webowa to ten sam klient bez mostu Pythona (`window.pywebview`). |
| Hosting | **GitHub Pages** (workflow w tym repo, adres `gisboost.github.io/easy-matplayer/`). |
| Wejście z hubu | Karta „symulacja ruchu” w repo `mapy-analizy` (`C:\Users\Michal\Desktop\easy\mapy-analizy`), prowadzi na stronę z listą scenariuszy. Tamto repo ma własne zasady, nie dziedziczy ograniczeń tego. |
| Zakres pierwszej wersji | Scenariusz demo Kutno 25%. Bez panelu zaznaczenia z harmonogramem osoby (osobny, większy krok). |

## Podstawa (zmierzone 2026-10-26)

Statyczny katalog strony zbudowany z demo Kutno 25%: 73 MB (13,6 MB po gzip), 138 plików, porcje czasu do 1,5 MB doczytywane w trakcie odtwarzania. Otwarty zwykłym serwerem plików w przeglądarce: mapa, drogi, panel i 277–280 aut o 06:00, bez błędów rysowania. Python był potrzebny tylko do zbudowania katalogu.

## Układ strony

```
index.html                 lista scenariuszy (z scenarios.json)
player/index.html          klient (shell.html), player/engine.js, player/vendor/
s/<id>/boot.<lang>.json    metadane scenariusza (pl, en)
s/<id>/*.bin               linki i łamane drogi
s/<id>/data/               eksport v2 (manifest, persons, tracks, porcje, budynki)
scenarios.json             lista: id, nazwa, opis, licencja, rozmiar
```

Adres odtwarzacza: `player/?run=<id>`. Bez `?run` klient działa jak w aplikacji (pliki obok strony).

## Różnice web / desktop (jedna baza kodu, przełącznik po `window.pywebview`)

- Ukryte w web: „otwórz run”, plik OSM, WMS / WMTS / XYZ / obraz (wszystko wymaga Pythona).
- Język: przełącznik działa po stronie klienta (`boot.en.json` / `boot.pl.json`, wybór z `localStorage` albo języka przeglądarki).
- Zaznaczone auto: panel z tym, co zna klient (id, klasa, prędkość, typ drogi). Harmonogram osoby (oś czasu) wymaga danych czynności w eksporcie, więc to krok W3.
- Podkład: jednolity z drogami. Dostawca kafelków wymaga osobnej decyzji (warunki użycia, klucz).

## Kroki

- [x] W1. Klient wspólny: tryb web w `shell.html` (prefiks `?run=`, brak mostu, ukryte kontrolki, język po stronie klienta). Testy: istniejące 115 nadal zielone, nowy test trybu web.
- [x] W2. `scripts/web_build.py`: z runów buduje `web/` (strona, scenariusze, `scenarios.json`), bez okna. Test na demo Kutno, otwarcie w przeglądarce z serwera statycznego.
- [ ] W3. (osobno, nie teraz) Panel zaznaczenia w JS: eksport czynności osób i oś czasu.
- [x] W4. (napisany, nie uruchomiony na GitHubie) Workflow `web_pages.yml` (GitHub Pages): ręczny start, pobiera zip demo z wydania, buduje `web/`, publikuje. **Włączenie Pages w ustawieniach repo i push robi właściciel.**
- [x] W5. Karta w `mapy-analizy` (index, README, i18n) z linkiem na `gisboost.github.io/easy-matplayer/`.

## Ograniczenia i ryzyka

- Do publicznego hostingu tylko dane z prawem redystrybucji (demo Kutno: CC BY / ODbL, po potwierdzeniu właściciela, patrz `LICENSE-DATA.md`). Wiedeń i Kelheim (CC BY-NC) nie trafiają na stronę.
- Pages nie gwarantuje kompresji plików `.bin`. Rozmiar to 73 MB na scenariusz (limit witryny 1 GB), a pobierany jest tylko oglądany fragment. Do zmierzenia po pierwszym wdrożeniu.
- WebGL2 jest wymagany (komunikat jak w aplikacji). Wydajność mierzona tylko na GPU właściciela.
- Pozycje aut są syntetyczne (id osób nie są danymi osobowymi), do potwierdzenia przez właściciela przed publikacją.
