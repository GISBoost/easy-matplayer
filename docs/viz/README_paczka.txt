easy-matplayer: odtwarzacz wyników symulacji MATSim (Windows 10/11, 64-bit)

Bez instalacji i bez Pythona. Nic nie zapisuje w rejestrze.

JAK URUCHOMIĆ
1. Rozpakuj cały zip w dowolne miejsce, najlepiej do folderu, do którego masz prawo zapisu
   (Pulpit, Dokumenty). Ścieżka może mieć spacje i polskie znaki. Nie uruchamiaj exe z wnętrza zipa.
2. Uruchom easy-matplayer.exe (dwuklik).
   Jeśli Windows pokaże "Chroniony komputer" (SmartScreen): "Więcej informacji", potem "Uruchom mimo to".
   Plik nie jest podpisany certyfikatem.
3. Pojawi się okno wyboru folderu. Wskaż folder runu MATSim. Do próby jest gotowy run w tej paczce:
   folder demo-kutno (obok exe). Otwiera się w kilka sekund, z budynkami 3D.
4. Własny run: folder z plikami output_events.xml.zst, output_network.xml.zst, output_plans.xml.zst
   (i najlepiej output_config.xml). Pierwsze otwarcie buduje indeks (od kilkunastu sekund do minuty,
   widać pasek postępu), potem ten sam run otwiera się od razu.

WYMAGANIA
- Windows 10 22H2 albo 11, 64-bit.
- Microsoft Edge WebView2 Runtime (jest w Windows 11 i w większości Windows 10). Jeśli go brakuje,
  program pokaże komunikat z linkiem do instalatora.
- Karta graficzna z WebGL (zintegrowana wystarcza). Mapa tła wymaga internetu; bez niego ruch działa,
  brakuje tylko podkładu.

JEŚLI COŚ NIE DZIAŁA
Dziennik programu to plik easy-matplayer.log w TYM SAMYM folderze co easy-matplayer.exe.
(Jeśli folder jest chroniony przed zapisem, dziennik trafia do %LOCALAPPDATA%\easy-matplayer\.)
Wyślij ten plik (i easy-matplayer.log.1, jeśli jest) razem z opisem:
- co kliknąłeś i co zobaczyłeś (najlepiej zrzut ekranu),
- wersja Windows, karta graficzna, czy WebView2 był zainstalowany wcześniej
  (Ustawienia > Aplikacje > "Microsoft Edge WebView2 Runtime"),
- ile sekund trwało otwarcie demo.

Przy testach sprawdź też: czy po zamknięciu okna krzyżykiem nie zostaje proces easy-matplayer.exe
ani msedgewebview2.exe w Menedżerze zadań, i czy drugie uruchomienie otwiera ten sam run od razu.

GDZIE SĄ DANE PROGRAMU
%LOCALAPPDATA%\easy-matplayer\: pamięć ostatniego runu, pliku OSM i języka, profil okna.
Odinstalowanie: usuń folder programu i ten folder.

DEMO I LICENCJE
demo-kutno: ruch samochodów w Kutnie (MATSim, 25% mieszkańców). Dane syntetyczne GUS (CC BY 4.0),
sieć i budynki © współtwórcy OpenStreetMap (ODbL), wyniki symulacji CC BY 4.0. Szczegóły: LICENSE-DATA.md.
Wysokości budynków to założenia, nie pomiar. Program: GPL-3.0-or-later; licencje bibliotek w THIRD_PARTY\.
Pełna instrukcja: docs/viz/README_pl.md w repozytorium.
