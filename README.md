# easy-matplayer

A player for [MATSim](https://matsim.org/) simulation results: car traffic on a map, in 2D and 3D, with buildings. A desktop app for Windows, with no installation and no Python needed.

User guide: [docs/viz/README.md](docs/viz/README.md). Progress and decisions (in Polish): [docs/projekt/wizualizer_postep.md](docs/projekt/wizualizer_postep.md).

Polish version: [README_pl.md](README_pl.md).

## Running from source

```
uv run --group viz python -m viz_player <MATSim run folder>
uv run --group viz pytest viz_player/tests -q
```

## Package and release

```
scripts\viz_build.bat
```

Release: a tag `viz-v<version>` starts `.github/workflows/viz_release.yml`.

## Browser version

```
uv run --group viz python scripts/web_build.py <folder with runs> _site
```

Builds a static site (scenario list, the same client as the app, data per scenario) for GitHub Pages; workflow `.github/workflows/web_pages.yml`. Plan: [docs/projekt/wizualizer_web.md](docs/projekt/wizualizer_web.md) (Polish).

## Licences

Code: GPL-3.0-or-later ([LICENSE](LICENSE)). Data: [LICENSE-DATA.en.md](LICENSE-DATA.en.md) (English translation of [LICENSE-DATA.md](LICENSE-DATA.md), which is binding).
