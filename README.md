# easy-matanimation

Odtwarzacz wyników symulacji [MATSim](https://matsim.org/): ruch samochodów na mapie w 2D i 3D, z budynkami. Aplikacja okienkowa na Windows, bez instalacji i bez Pythona.

Opis dla użytkownika: [docs/viz/README_pl.md](docs/viz/README_pl.md). Postęp i decyzje: [docs/projekt/wizualizer_postep.md](docs/projekt/wizualizer_postep.md).

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

## Licencje

Kod: GPL-3.0-or-later ([LICENSE](LICENSE)). Dane: [LICENSE-DATA.md](LICENSE-DATA.md).
