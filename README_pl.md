# easy-matplayer

Odtwarzacz wyników symulacji [MATSim](https://matsim.org/): ruch samochodów na mapie w 2D i 3D, z budynkami. Aplikacja okienkowa na Windows, bez instalacji i bez Pythona.

Opis dla użytkownika: [docs/viz/README_pl.md](docs/viz/README_pl.md). Postęp i decyzje: [docs/projekt/wizualizer_postep.md](docs/projekt/wizualizer_postep.md).

Wersja angielska: [README.md](README.md).

## Uruchomienie z kodu

```
uv run --group viz python -m viz_player <folder runu MATSim>
uv run --group viz pytest viz_player/tests -q
```

## Paczka i wydanie

```
scripts\viz_build.bat
```

Wydanie: tag `viz-v<wersja>` uruchamia `.github/workflows/viz_release.yml`.

## Wersja w przeglądarce

```
uv run --group viz python scripts/web_build.py <folder z runami> _site
```

Buduje statyczną stronę (lista scenariuszy, ten sam klient co aplikacja, dane osobno dla scenariusza) pod GitHub Pages; workflow `.github/workflows/web_pages.yml`. Plan: [docs/projekt/wizualizer_web.md](docs/projekt/wizualizer_web.md).

## Licencje

Kod: GPL-3.0-or-later ([LICENSE](LICENSE)). Dane: [LICENSE-DATA.md](LICENSE-DATA.md).
