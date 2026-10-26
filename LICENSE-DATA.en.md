# Licences: program, libraries, models, demo data and base maps

> Translation of [LICENSE-DATA.md](LICENSE-DATA.md) (Polish). The Polish text is binding; this translation is for reference only.

Applies to the easy-matplayer repository and the release packages (`easy-matplayer-windows.zip`, `easy-matplayer-demo-kutno.zip`). The Polish original of this file is included in the demo zip.

## 1. Program (GPL-3.0-or-later)

The player code (`viz_player/`, `pipeline/`, `scripts/`, tests, `config/viz_buildings.toml`, documentation) is under the **GNU GPL, version 3 or later**. Full text: [LICENSE](LICENSE).

## 2. Libraries in the repository and in the package

| component | licence | where |
|---|---|---|
| MapLibre GL JS 6.0.0 | BSD-3-Clause | `viz_player/vendor/maplibre/` (text in `LICENSE`) |
| deck.gl 9.4.0 | MIT, © vis.gl contributors | `viz_player/vendor/deck.min.js`, text in `viz_player/vendor/deck.LICENSE` |
| LowPoly Car pack (car model), Quaternius | CC0 (public domain) | `viz_player/vendor/quaternius/`, description in `CREDITS.md` |
| Python libraries in the package (numpy, pyproj, pywebview, lxml, Pillow, osmium, zstandard and their dependencies) and the Python runtime | each library's own licence | texts in the `THIRD_PARTY/` folder next to the program (created by `scripts/viz_third_party.py` during the build) |

The BSD and MIT licences require the notice and the licence text to be kept when redistributing. That is why the files in `vendor/` stay in the package together with their licences, and `THIRD_PARTY/` is added to every package.

## 3. Data in the demo zip

The demo (`easy-matplayer-demo-kutno.zip`) contains one MATSim simulation run for Kutno (25% of residents) with a ready index, polyline roads and buildings:

- **Simulation results** (events, output plans): **CC BY 4.0**, like the input and output files of the sample MATSim project (`matsim-example-project`, section Licenses of its README).
- **Population and travel plans**: synthetic data derived from publications of the Central Statistical Office of Poland (GUS: NSP 2021, BDL, commuting matrix). Licence **CC BY 4.0**; attribution is required: "Central Statistical Office (Główny Urząd Statystyczny)" and the name of the publication.
- **Road network, buildings and polyline roads** (in the run and in the `viz/` folder): © OpenStreetMap contributors (https://www.openstreetmap.org/copyright), **Open Database License 1.0 (ODbL)**. A database derived from OSM that we publish stays under the ODbL with attribution.
- The demo contains no commercial data and no data under non-commercial licences (CC BY-NC).

The licence split in the demo (CC BY for results and plans, ODbL for OSM data) describes the project author's current understanding. Before a public release the owner confirms it in `docs/projekt/wizualizer_postep.md` (entry A5, in Polish).

## 4. Runs by other authors

The program opens any MATSim run saved as `.xml.zst`. Runs and scenarios by other authors have their own licences (for example Kelheim and Vienna 2023.2: CC BY-NC 4.0, non-commercial use only; Berlin: CC BY 4.0). **We do not include them in releases or in this repository.** You may open them on your own computer according to their licence. List and links: [docs/viz/README.md](docs/viz/README.md).

## 5. Base maps

The program contains no map tiles. By default the background is plain. The user can add a WMS, WMTS or XYZ service or an own image (map panel). The terms of use, attribution and any cost of each service belong to its provider and to the user. The program shows a service's attribution where the service provides one. Tile requests reveal the viewed map area to the service provider.

The optional CARTO base map (dark map without labels, data © OpenStreetMap contributors © CARTO) works only with a key entered locally in `config/viz_basemap.local.toml`. The key is not in the repository or in the packages.

## 6. What is not in the repository

It contains no GUS or OSM source data, no large OSM files (`*.pbf`, except the small test file `viz_player/selftest/kutno_tiny.osm.pbf`, which is an OSM extract: © OpenStreetMap contributors, ODbL 1.0), no MATSim runs and no access keys. The program opens OSM files chosen by the user and sends no data about the run.
