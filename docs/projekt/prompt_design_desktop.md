# Prompt dla agenta: design desktopu i web na komputerze (research, moodboard, kod)

Wklej całość poniżej jako pierwszą wiadomość nowej sesji w folderze `C:\Users\Michal\Desktop\MATSim\easy-matanimation`. Przed tym przeczytaj w repo `docs/projekt/design_handoff_styl.md` (agent też ma to zrobić jako krok 0).

---

## Zadanie

Jesteś agentem projektu **easy-matplayer** (odtwarzacz wyników MATSim; aplikacja okienkowa Windows w pywebview/WebView2 oraz strona na GitHub Pages; jeden klient: `viz_player/shell.html` + `engine.js`). Właściciel to Michał Kaczorowski, rozmawiaj po polsku, krótko i konkretnie.

Układ na telefon (szerokość ≤ 700 px) jest już zrobiony i zaakceptowany: ciemny motyw, trochę Apple, minimalizm, pływające zaokrąglone kształty, szkło (patrz handoff i `docs/projekt/mobile_moodboard.html`). **Cel: ten sam charakter wizualny na szerokim ekranie**, czyli (a) w aplikacji okienkowej na desktopie i (b) na stronie web otwieranej na komputerze (ekran poziomy, laptop, monitor, ewentualnie tablet poziomo). Dziś szeroki układ to stary, techniczny wygląd: mapa + panel 320 px po prawej + dolny pasek 52 px z ok. 14 elementami.

Pracujesz etapami. **Między etapami masz się zatrzymać i zapytać właściciela** (punkty STOP poniżej). Nie przechodź dalej bez jego odpowiedzi. Nie koduj nic przed STOP 2.

## Zasady (twarde)

1. Przeczytaj `CLAUDE.md` w repo i trzymaj się go. W szczególności: **push, merge do `main`, tagi i wydania robi właściciel** (ty tylko lokalny commit po zaliczonym kroku); nie wymyślaj danych; nie zmieniaj kolorów danych (klasy aut, skala prędkości, typy aktywności, kolory dróg); dokumentuj w `docs/projekt/wizualizer_postep.md`; commit w formacie `wizualizer: <co>` z trailerem `Co-Authored-By` podanym w systemie; nie dotykaj nieśledzonego `CLAUDE.md`, jeśli nie jest Twój.
2. **Aplikacja okienkowa nie może się zepsuć.** Po każdym kroku: `uv run --group viz pytest viz_player/tests -q` oraz `uv run --group viz python -m viz_player --smoke <run>` na prawdziwym runie (demo Kutno z wydania `viz-v0.1.0`, `easy-matplayer-demo-kutno.zip`). Smoke ma asercję układu desktopowego w `viz_player/window.py` (pole `desk`, okno 1440 px). Jeśli zmieniasz układ desktopu, **zaktualizuj ją świadomie** do nowego układu i opisz to w postępie; nie wyłączaj i nie osłabiaj testu.
3. Układ telefonu (≤ 700 px) ma po Twoich zmianach działać tak samo jak teraz. Sprawdź na emulatorze (instrukcja w handoffie, pkt 7).
4. Bez nowych bibliotek i bundlera: wszystko inline w `shell.html`. Każdy nowy napis w `viz_player/i18n.py` (EN).
5. Research: **podawaj źródła z adresami**, rozróżniaj „zweryfikowane w źródle” od „z mojej wiedzy”. Nie kopiuj treści chronionych prawem autorskim; streszczaj własnymi słowami, krótkie cytaty tylko z atrybucją. Nie wymyślaj parametrów (np. wartości rozmycia) i nie podawaj ich jako faktów, jeśli ich nie sprawdziłeś.
6. Nie rób nic poza zakresem (żadnych zmian w silniku, danych, eksporcie). Jeśli widzisz błąd poza zakresem, zanotuj go na końcu raportu, nie naprawiaj po cichu.

## Plan działania

### Krok 0: przygotowanie (bez pytań)
- Przeczytaj: `CLAUDE.md`, `docs/projekt/design_handoff_styl.md` (styl, tokeny, pułapki, jak testować), `docs/projekt/mobile_moodboard.html` (otwórz w przeglądarce i obejrzyj; weź jego formę jako wzór), sekcje „Telefon …” w `docs/projekt/wizualizer_postep.md`, blok `@media (max-width: 700px)` i JS arkusza w `shell.html`.
- Zbuduj stronę lokalnie (instrukcja w handoffie) i obejrzyj obecny układ szeroki w przeglądarce Claude Desktop (`mcp__Claude_Browser__*`), w trzech szerokościach okna (ok. 1440, 1024, 800 px) i w aplikacji okienkowej (`--smoke` robi zrzut `smoke.png`).

### Krok 1: audyt obecnego desktopu (bez pytań, potem STOP 1)
Zrób zwięzłą listę: co jest na ekranie, co jest ciasne lub brzydkie, które elementy mają odpowiednik w wersji mobilnej (pigułka zegara, stos przycisków, karta odtwarzacza, arkusz), a które nie (np. WMS, obrazy, otwórz run, plik OSM, podpowiedź klawiszowa, spacja/strzałki, prawy przycisk myszy). Zanotuj ograniczenia: dwa środowiska (WebView2 w aplikacji i przeglądarki), `backdrop-filter` w WebView2, desktop ma mysz i klawiaturę (skróty, hover), panel ma 12+ sekcji.

**STOP 1.** Pokaż właścicielowi audyt (1 ekran tekstu + 2–3 zrzuty) i zadaj maksymalnie 4 pytania, które zmieniają kierunek, np.:
- panel boczny: zostaje kolumną, ma być pływającą szklaną wyspą, czy oba;
- odtwarzacz: pływająca karta jak na telefonie czy węższy, wyśrodkowany pasek;
- czy aplikacja okienkowa i web na desktopie mają wyglądać identycznie (domyślnie tak, to jeden plik);
- czy poziomy tablet/telefon ma dostać układ pośredni.
Czekaj na odpowiedź.

### Krok 2: research (po STOP 1)
Zbadaj nowoczesny, minimalistyczny, „trochę Apple” interfejs **aplikacji webowych i desktopowych o szerokim ekranie**, ciemny motyw, pływające zaokrąglone kształty, szkło. Szukaj wzorców dla aplikacji mapowych/danych (nie ogólnych landingów). Konkretne tematy:
- Apple HIG dla macOS/iPadOS: okna, paski narzędzi, panele boczne (sidebars), inspektory, materiały i „vibrancy”, pływające paleta/popover, rozmiary kontrolek na wskaźniku myszy (nie 44 px dotyku), stany hover/focus, skróty klawiszowe;
- aplikacje referencyjne: Apple Maps na Macu i iPadzie, Apple Weather, Znajdź, Podcasts/Music (miniplayer), Linear, Arc, Figma (panele), Mapbox Studio/Felt/Kepler.gl/deck.gl demos (jak pływające panele nad mapą radzą sobie z gęstym interfejsem);
- szkło na webie: wydajność `backdrop-filter` nad kanwą WebGL (MapLibre/deck.gl), zachowanie w WebView2, kontrast tekstu na szkle (WCAG), `prefers-reduced-transparency`/`prefers-contrast`, fallback bez rozmycia;
- układ responsywny szeroki: punkty przełamania (≥ 700, ≥ 1024, ≥ 1440), jak skalować pływające panele, maksymalne szerokości, układ poziomy tabletu;
- dostępność na desktopie: fokus klawiaturą, skróty, ARIA dla suwaków i kontrolek segmentowanych.
Zapisz wynik w `docs/research/wizualizer_design_desktop.md`: pytania, znalezione wzorce (z linkami), co zweryfikowane vs z wiedzy własnej, wnioski dla naszego projektu, ryzyka (wydajność szkła nad WebGL). Streszczaj własnymi słowami.

### Krok 3: moodboard desktop (po researchu, potem STOP 2)
Zrób `docs/projekt/desktop_moodboard.html`: **samodzielny plik HTML bez zależności**, w formie jak `mobile_moodboard.html` (ciemny, makiety w prawdziwych wymiarach skalowane w dół, podpisy, tabela „gdzie trafia każdy element”, porównanie, rekomendacja, źródła). Zawartość:
- stan obecny (zrzut lub makieta z audytu) i tokeny wspólne z wersją mobilną (te z handoffu), żeby było widać ciągłość;
- **3 propozycje** różniące się kierunkiem, np.: (A) pływające wyspy: panel jako szklana wyspa po prawej lub lewej, karta odtwarzacza na dole pośrodku, pigułka zegara u góry, stos przycisków; (B) pasek narzędzi na górze + inspektor wysuwany z boku + minikarta odtwarzacza; (C) układ „wydawca”: wąska szyna ikon po lewej, panel kontekstowy, odtwarzacz jako duża kapsuła. Dopasuj do wniosków z researchu i odpowiedzi ze STOP 1; propozycje mają być wyraźnie różne, nie warianty koloru;
- dla każdej: ekran domyślny, ekran z otwartym panelem/ustawieniami, ekran z zaznaczonym autem/drogą, wariant ~1024 px; stany hover/fokus na jednym przykładzie;
- mapowanie wszystkich elementów dzisiejszego paska i panelu (łącznie z elementami tylko-aplikacja: WMS, obrazy, otwórz run, plik OSM, język);
- zasady wspólne: jak to zgadza się z mobilnym (ten sam język, inne proporcje), co się zmienia przy przejściu między szerokościami;
- uczciwa lista kompromisów (miejsce na mapę, gęstość panelu, koszt szkła nad WebGL, nakład kodu).
Sprawdź plik w przeglądarce Claude Desktop (zrzuty, brak błędów w konsoli, czytelny w 1440 i 1024 px).

**STOP 2.** Pokaż moodboard (otwórz go w przeglądarce, podaj ścieżkę) i krótkie podsumowanie rekomendacji. Poproś o wybór: „A”, „C z elementami B”, „A, ale bez …”. Zapytaj też o decyzje otwarte (np. zegar z sekundami czy bez, czy panel ma się zwijać, czy skróty klawiszowe zostają widoczne). **Nie koduj, dopóki właściciel nie wybierze.**

### Krok 4: plan kodowania (po wyborze, potem STOP 3)
Spisz plan: jakie komponenty zmieniasz w `shell.html` (CSS w nowym bloku `@media (min-width: 701px)` czy zmiana bazowych stylów), co dzielisz z blokiem mobilnym (zmienne `--glass`, tokeny), jak uniknąć regresji telefonu, jakie testy dodasz (np. rozszerzenie asercji `desk` w `window.py`, test na obecność elementów, zrzuty w trzech szerokościach), jak podzielisz pracę na małe kroki z commitami. Zaznacz ryzyka (wydajność `backdrop-filter` nad kanwą, WebView2, brak hovera na dotyku).

**STOP 3 (krótki).** Pokaż plan (do 15 linii) i zapytaj tylko o to, co naprawdę blokuje. Jeśli właściciel napisał wcześniej „koduj od razu”, pomiń ten STOP.

### Krok 5: kodowanie (iteracyjnie, STOP-y wizualne)
Pracuj w małych krokach (np. 1. tokeny i szkło, 2. karta odtwarzacza, 3. panel/wyspa, 4. pigułka i stos przycisków, 5. szerokości pośrednie, 6. polerka). Po każdym kroku: testy, smoke, zrzuty w 1440/1024/800 px, kontrola telefonu na emulatorze. Dodaj do `i18n.py` nowe napisy. Dokumentuj w `wizualizer_postep.md` (zmiana, dowód: liczby i zrzuty, czego nie sprawdzono).

**STOP 4 (po ok. połowie kroków, na głównych ekranach).** Wyślij właścicielowi zrzuty (lub link do strony testowej) i zapytaj o opinię przed polerką. Jedno zdanie: „czy kierunek jest dobry, co zmienić”. Wprowadź uwagi.

### Krok 6: domknięcie
- Pełne testy: pytest, smoke na demie Kutno, zrzuty końcowe, telefon na emulatorze (regresja).
- Dla aplikacji okienkowej: jeśli zmieniasz cokolwiek, co trafia do paczki (`viz_player/*`), uruchom zamrożone exe (okrojony PATH, `EASY_MATPLAYER_DATA` w pustym katalogu), tak jak wymaga `CLAUDE.md`. Nie buduj wydania ani nie twórz tagów.
- Dokumentacja: `docs/viz/README_pl.md` i `README.md` (sekcje o wyglądzie i, jeśli zmieniły się, o skrótach klawiszowych), `docs/projekt/design_handoff_styl.md` (zaktualizuj tokeny i zasady o desktop), `docs/projekt/wizualizer_postep.md` (checklista, dziennik, roadmapa).
- Lokalny commit(y). **Bez pusha.** Powiedz właścicielowi, że push i uruchomienie workflow Pages (`web_pages.yml`, wejście `tag=viz-v0.1.0`) są po jego stronie.
- Raport końcowy: krótko (co zrobione, jak, czego nie sprawdzono), bez długich opisów.

## Format rozmowy
- Pytania zadawaj zbiorczo i krótko, z rekomendacją (zaznacz, którą opcję wybierasz domyślnie i dlaczego).
- Wszystko, co pokazujesz, ma być oglądalne jednym kliknięciem (ścieżka do pliku, zrzut). Zrzuty roboczych plików trzymaj w katalogu scratchpad, nie w repo.
- Gdy czegoś nie możesz sprawdzić (np. prawdziwy iPhone, Safari), powiedz to wprost.
