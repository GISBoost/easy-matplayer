# Research: interfejs na szerokim ekranie (desktop, web na komputerze)

Stan na 2026-10-31. Cel: przenieść język wizualny z wersji na telefon (ciemny, pływające kapsuły, szkło) na ekran poziomy, bez psucia aplikacji okienkowej. Streszczenia własnymi słowami. Oznaczenia: **[Z]** zweryfikowane w źródle, które otworzyłem w tej sesji; **[W]** z mojej wiedzy, nie sprawdzone; **[H]** hipoteza do pomiaru.

## Ograniczenia tego researchu (uczciwie)

- Strony `developer.apple.com` są renderowane skryptem, więc czytałem **kopię treści HIG w pakiecie `apple-hig-mcp@1.1.3` (unpkg)**, jak w researchu mobilnym. To kopia strony trzeciej, nie oryginał, i zawiera już język o „Liquid Glass”.
- Nie widziałem na żywo Apple Maps na Macu, Pogody, Znajdź, Podcasts, Arc, Linear ani Figmy. Wzorce z tych aplikacji są poniżej oznaczone **[W]**. Wyszukiwanie wzorców panelu w Kepler.gl i Felt nic użytecznego nie zwróciło.
- Wydajności `backdrop-filter` nad WebGL w WebView2 **nie zmierzyłem**. Znalazłem tylko anegdoty (niżej).

## Pytania i odpowiedzi

### 1. Co mówi Apple HIG o materiałach i panelach?

- **[Z]** Materiały dają głębię i oddzielają pierwszy plan (tekst, kontrolki) od tła. Są dwa rodzaje: Liquid Glass (osobna warstwa funkcyjna kontrolek i nawigacji, np. pasków kart i sidebarów, unosząca się nad treścią) i materiały standardowe (rozmycie, vibrancy, tryby mieszania, do strukturyzowania samej treści). Źródło: [HIG Materials, kopia](https://unpkg.com/apple-hig-mcp@1.1.3/content/materials.md).
- **[Z]** Liquid Glass ma być osobną warstwą kontrolek, **nie** częścią warstwy treści; stosować oszczędnie. Grubsze, bardziej nieprzezroczyste materiały dają lepszy kontrast dla drobnego tekstu, cieńsze zachowują poczucie kontekstu. Kolory „vibrant” kładzie się na materiałach. Ta sama kopia.
- **[Z]** Wniosek dla nas: zasada z wersji mobilnej (szkło na małych pływających elementach, lita szarość na dużych powierzchniach z tekstem) jest zgodna z kierunkiem HIG, ale to nasza interpretacja, nie cytat.
- **[Z]** Sidebar (HIG): nie ukrywać domyślnie, bo użytkownik może nie wrócić; na macOS pokazać przycisk pokaż/ukryj i polecenie w menu; hierarchia do dwóch poziomów; treść może rozciągać się pod sidebar, tak że wygląda jakby unosił się; nie umieszczać krytycznych elementów przy dolnej krawędzi. Źródło: [HIG Sidebars, kopia](https://unpkg.com/apple-hig-mcp@1.1.3/content/sidebars.md). Brak liczb szerokości.
- **[Z]** Pasek narzędzi macOS (HIG): trzy strefy (początek: nawigacja i przycisk sidebaru; środek: wspólne kontrolki, zwijane do menu przy wąskim oknie; koniec: elementy niezbędne, inspektor, szukaj, jedna akcja główna); najwyżej trzy grupy; mniej ważne akcje do menu „Więcej”. Źródło: [HIG Toolbars, kopia](https://unpkg.com/apple-hig-mcp@1.1.3/content/toolbars.md).
- **[Z]** Układ adaptacyjny (HIG): trzymać pełny układ jak najdłużej, przełączać na zwarty dopiero gdy się nie mieści; w złożonych widokach dzielonych najpierw chować trzeciorzędne kolumny (inspektory). Źródło: [HIG Layout, kopia](https://unpkg.com/apple-hig-mcp@1.1.3/content/layout.md).
- **Nie znalazłem** w HIG liczb dla rozmiarów kontrolek pod wskaźnik myszy (strona układu ich nie podaje). Strona o urządzeniach wskazujących (`pointing-devices.md`) dała 404 w tej wersji pakietu; nie czytałem jej.

### 2. Rozmiary celów na desktopie

- **[Z]** WCAG 2.2, SC 2.5.8 (poziom AA): cel wskaźnika min. 24×24 CSS px albo odpowiedni odstęp; wyjątki m.in. dla gęstych znaczników mapy. Źródło: [Understanding SC 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).
- **[W]** Apple podaje 44 pt na dotyk; na Macu kontrolki bywają ok. 22–28 pt. Nie zweryfikowane w tej sesji.
- Wniosek: na desktopie 32–36 px na przyciski i 36–40 px na pola daje zapas ponad 24 px i zachowuje kapsułowy język (pigułka 36 px z telefonu jest już poprawnym rozmiarem).

### 3. Szkło na webie i wydajność

- **[Z]** `backdrop-filter` jest „Baseline 2024, newly available” (od września 2024 w najnowszych przeglądarkach). Działa na to, co jest **za** elementem, wymaga częściowej przezroczystości tła, a rodzic z `opacity < 1`, `filter`, `mask`, `clip-path` itp. staje się „backdrop root” i **wygasza efekt** (blur obejmuje wtedy tylko to, co między rodzicem a dzieckiem). To realne ryzyko przy animacji pojawiania panelu przez `opacity`. Źródło: [MDN backdrop-filter](https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter).
- **[Z]** web.dev: stosować w `@supports`, a jako zapas dać nieprzezroczyste tło (autorzy proponują obraz, nie polyfill); ostrzegają, że efekt „może szkodzić wydajności”. Źródło: [web.dev, backdrop-filter](https://web.dev/articles/backdrop-filter).
- **Anegdoty o WebGL pod rozmyciem, nie pomiar [H]:** zgłoszenia na GitHubie opisują, że kanwa WebGL pod elementem z `backdrop-filter` zmusza kompozytor do ciągłego ponownego mieszania tekstury z rozmytą warstwą, a autorzy usuwali rozmycie lub zastępowali je półprzezroczystym, nieprzezroczystszym tłem; np. [Omi #8902](https://github.com/BasedHardware/omi/pull/8902), [Memex #88](https://github.com/memex-lab/memex/pull/88). To dotyczy innych aplikacji, nie WebView2 w naszej wersji. Nasz odtwarzacz ma właśnie takie położenie (szkło nad kanwą deck.gl i MapLibre), więc **trzeba zmierzyć** (czas klatki z szkłem i bez) na RTX 4070 i, jeśli się da, na zintegrowanej grafice.
- Wniosek: ograniczyć szkło do małych, niezmiennych powierzchni (kapsuła odtwarzacza, pigułka, stos przycisków), a duże, przewijane powierzchnie z tekstem (panel) zrobić z **litego koloru** (zgodnie z wersją mobilną). Dać wyłącznik przez `@supports not` i `prefers-reduced-transparency`.

### 4. Dostępność: kontrast, przezroczystość, fokus

- **[Z]** WCAG 1.4.3: tekst zwykły ≥ 4,5:1, duży ≥ 3:1; kontrast mierzy się względem tła w miejscu, gdzie tekst leży (przy obrazie: najjaśniejszy/najciemniejszy fragment). Wyjątki nie obejmują zwykłych etykiet na szkle. Źródła: [Understanding 1.4.3](https://w3c.github.io/wcag/understanding/contrast-minimum.html) (z wyników wyszukiwania, strony nie otwierałem; treść streszczona z wyników), [F83](https://www.w3.org/WAI/WCAG22/Techniques/failures/F83). Wniosek dla szkła jest **moją inferencją**: testować na najjaśniejszym podkładzie (ortofotomapa, jasny OSM), nie na jednym zrzucie; tint szkła powinien gwarantować kontrast.
- **[Z]** `prefers-reduced-transparency` (`reduce` / `no-preference`): ustawienie w Windows to Ustawienia → Personalizacja → Kolory → Efekty przezroczystości; MDN oznacza funkcję jako **ograniczoną dostępność / eksperymentalną**; jedno źródło podaje wsparcie Chrome/Edge od 119, Firefox i Safari nie. Źródło: [MDN](https://developer.mozilla.org/docs/Web/CSS/@media/prefers-reduced-transparency). Sprawdzić w tabeli zgodności MDN przed poleganiem; w WebView2 (Chromium) powinno działać, ale **nie sprawdziłem**.
- **[Z]** `prefers-contrast` (`more`/`less`/`custom`) jest „Baseline: widely available” od maja 2022; `custom` odpowiada `forced-colors: active`. Powiązanie z wysokim kontrastem Windows to moja wiedza. Źródło: [MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast).
- **[Z]** Suwak (ARIA APG): `role="slider"`, `aria-valuenow/min/max`, `aria-valuetext` gdy liczba nic nie mówi (nasz suwak czasu: tekst zegara), strzałki ±krok, Home/End. Natywny `<input type=range>` robi to sam, więc **nie** zastępujemy go własnym widgetem. Źródło: [APG Slider](https://www.w3.org/WAI/ARIA/apg/patterns/slider/).
- **[W]** Kontrolka segmentowana: `role="radiogroup"` z `role="radio"` (albo natywne `input type=radio` ze stylem); przełącznik: `role="switch"` (natywny checkbox stylowany jak dziś jest akceptowalny). Fokus klawiaturą: `:focus-visible` z widocznym pierścieniem (np. 2 px akcent), bo szkło nie zastępuje wskaźnika fokusu.

### 5. Wzorce aplikacji mapowych i danych (tylko wiedza własna)

- **[W]** Apple Maps (iPad/Mac): karta wyszukiwania i szczegółów jako pływający panel przy lewej krawędzi z marginesem, kontrolki mapy w pływającym pionowym stosie po prawej, mapa pod całością. Nasz stos `#mstack` ma ten sam układ.
- **[W]** Odtwarzacze (Apple Music/Podcasts): miniodtwarzacz jako węższa, wyśrodkowana kapsuła nad treścią, z możliwością rozwinięcia. Pasuje do decyzji „wyśrodkowana kapsuła, max ok. 720 px”.
- **[W]** Narzędzia do danych (Kepler.gl, Mapbox Studio, Felt, Figma): panele boczne zwijane, sekcje jako rozwijane grupy, jeden panel kontekstowy zamiast wielu. **Nie zweryfikowałem**; Kepler.gl nie dał wyników wyszukiwania na ten temat.
- Wniosek wspólny: przy 12 sekcjach panel potrzebuje **grup rozwijanych** (jak sekcje HIG do dwóch poziomów), inaczej wyspa urośnie w ścianę tekstu. To rekomendacja projektowa, nie wymóg źródła.

### 6. Szerokie układy: punkty przełamania

- **[Z]** HIG Layout (kopia): trzymać pełny układ jak najdłużej, chować rzeczy trzeciorzędne najpierw. Konkretne progi w pikselach HIG nie podaje.
- **[W]** Powszechne progi: 701 (koniec telefonu w projekcie), 1024 (laptop/tablet poziomo), 1440 (desktop). To progi robocze, nie normatywne.
- Nasza decyzja (STOP 1): jeden układ pływający dla ≥ 701 px, węższa wyspa przy ≤ 1024 px.

## Wnioski dla easy-matplayer

1. **Szkło tylko na małych, stałych pływających elementach** (pigułka, stos, kapsuła odtwarzacza); **panel jako lita szarość** `#1c1c1e` z dużym promieniem. Ma to uzasadnienie w HIG (osobna warstwa kontrolek, grubsze materiały dla tekstu) i w ostrożności wobec kosztu rozmycia nad WebGL.
2. Unikać `opacity` i `filter` na rodzicach szkła (backdrop root); animować panel przez `transform` i `visibility`.
3. Fallback: `@supports not (backdrop-filter: blur(1px))` oraz `@media (prefers-reduced-transparency: reduce)` → nieprzezroczyste tło `#2c2c2e`; `prefers-contrast: more` → mocniejszy obrys i tekst.
4. Cele min. 32 px (zapas ponad 24 px WCAG), `:focus-visible` na wszystkim, natywne suwaki zostają.
5. Panel: grupy rozwijane, tryb zwinięty (przycisk w stosie), brak domyślnego ukrycia na starcie (HIG).

## Ryzyka

| Ryzyko | Skutek | Jak sprawdzić |
|---|---|---|
| Szkło nad kanwą WebGL w WebView2 | spadek FPS, grzanie GPU | czas klatki z i bez szkła na Kutnie 100%, RTX 4070; zintegrowana grafika (krok 8 odłożony) |
| `opacity`/`filter` na rodzicu szkła | rozmycie znika | test wizualny po każdej animacji |
| Kontrast tekstu na jasnym podkładzie | tekst nieczytelny | zrzut na ortofotomapie i jasnym OSM, pomiar kontrastu |
| `prefers-reduced-transparency` bez wsparcia | brak wyłącznika | tabela zgodności MDN; własny przełącznik „bez szkła” jako plan B |
| Hover nie istnieje na dotyku (tablet poziomo) | funkcja tylko w hoverze znika | każda informacja z hovera ma też wariant z kliknięciem |

## Źródła

- https://unpkg.com/apple-hig-mcp@1.1.3/content/materials.md, `sidebars.md`, `toolbars.md`, `layout.md` (kopia HIG, strona trzecia)
- https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter
- https://web.dev/articles/backdrop-filter
- https://developer.mozilla.org/docs/Web/CSS/@media/prefers-reduced-transparency
- https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast
- https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html
- https://www.w3.org/WAI/WCAG22/Techniques/failures/F83
- https://www.w3.org/WAI/ARIA/apg/patterns/slider/
- Anegdoty o WebGL i blurze: https://github.com/BasedHardware/omi/pull/8902, https://github.com/memex-lab/memex/pull/88
