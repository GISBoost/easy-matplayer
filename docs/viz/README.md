# easy-matanimation

A player for results of a [MATSim](https://matsim.org/) simulation: car traffic on a map, in 2D and 3D, with buildings. It runs locally on Windows, needs no installation and no Python.

The Polish version of this manual is [README_pl.md](README_pl.md).

## Download and start

1. From [Releases](../../../../releases) download `easy-matanimation-windows.zip` (about 46 MB) and unpack it anywhere (the path may contain spaces and non-ASCII characters).
2. Run `easy-matanimation.exe`. If Windows shows "Windows protected your PC" (SmartScreen), click "More info", then "Run anyway". The file is not signed with a certificate.
3. Select a MATSim run folder. The first time you open a run, the program builds an index (from a dozen seconds to a minute; a progress bar shows). After that the same run opens at once, and the program remembers the last run.

Requirements: Windows 10 22H2 or 11 (64-bit) and the Microsoft Edge WebView2 Runtime (it is in Windows 11 and most Windows 10 installations; if it is missing, the program shows a message with a link to the installer). A graphics card with WebGL support; integrated graphics is enough.

## Language

The interface starts in English. The button next to "open run…" in the panel switches it to Polish (its label then reads "English"). The choice is saved in `%LOCALAPPDATA%\easy-matanimation\viz_player_lang.json`. Changing the language reloads the open run.

## Demo

`easy-matanimation-demo-kutno.zip` (about 59 MB, a separate file in the same release) is a run of Kutno (25% of residents, 100 iterations, a network with turn restrictions from OSM) with a ready index. Unpack it and select the `demo-kutno` folder. It opens in a few seconds, with 3D buildings, and needs no extra files.

## Other public MATSim scenarios

They are not included in the release (each has its own licence). Download one yourself and select its results folder. The program needs `.xml.zst` files, so results saved as `.xml.gz` must be repacked (see below). The program reads the network coordinate system from the run's `output_config.xml` (`coordinateSystem`, an EPSG code). Without that entry, or with a value that is not an EPSG code (MATSim writes `Atlantis` by default), it assumes EPSG:3857 (coordinates as Web Mercator metres). The run still opens, but the traffic may sit in the wrong place on the map. Vienna (EPSG:3416) has been tested; Berlin and Kelheim (EPSG:25832) have not been opened. Buildings and polyline roads from OSM are computed for the network area, so very large networks need an OSM file that covers that area.

| scenario | where | data licence |
|---|---|---|
| Berlin v6.4 (1%, 10%, 25%) | [matsim-berlin](https://github.com/matsim-scenarios/matsim-berlin), results on the [TU Berlin server](https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/berlin/berlin-v6.4/output/) (1% events: about 274 MB) | CC BY 4.0 |
| Kelheim | [matsim-kelheim](https://github.com/matsim-scenarios/matsim-kelheim), results on the [TU Berlin server](https://svn.vsp.tu-berlin.de/repos/public-svn/matsim/scenarios/countries/de/kelheim/) | CC BY-NC 4.0 (non-commercial use only) |
| Vienna 2023.2 | [ait-energy/matsim-model-vienna](https://github.com/ait-energy/matsim-model-vienna) (inputs only; you have to run the results yourself) | CC BY-NC 4.0 (non-commercial use only) |

You may open NC files on your own computer; you may not include them in public packages with this program.

## Your own run

The MATSim run folder must contain `output_events.xml.zst`, `output_network.xml.zst` and `output_plans.xml.zst`. MATSim writes such files when you set `controller` → `compressionType` = `zst` in the configuration. A run saved as `.xml.gz` must be repacked (`gzip -dc output_events.xml.gz | zstd -o output_events.xml.zst`). The program changes nothing in the run folder except the `viz/` subfolder (index, cache).

## Buildings and polyline roads from OpenStreetMap (optional)

By default the roads are straight segments from the run's network, and there are no buildings. To add them, click "OSM file…" in the panel on the right and select an `.osm.pbf` file covering the run area (for example from [Geofabrik](https://download.geofabrik.de/europe/poland.html)). The program cuts out the buildings (with heights from OSM tags, or assumed from the building class) and fits the shape of the roads. The result is saved with the run (`viz/`), so that run can be copied to another computer without the OSM file. "forget file" goes back to straight segments.

## Where the program keeps its data

`%LOCALAPPDATA%\easy-matanimation\`: the log `easy-matanimation.log` (when you report a problem, paste its last lines), the memory of the last run and the OSM file, and the saved language. Uninstalling means deleting the program folder and this folder. The program writes nothing to the registry.

## Network

The base map loads tiles from public WMS/WMTS services (addresses in the map panel). Without the internet, traffic and controls still work; only the base map is missing. The program does not send any data about the run.

## Licences

- Program: GPL-3.0-or-later (file `LICENSE`). Libraries in the package: licence texts in `THIRD_PARTY/` in the program folder.
- Demo: simulation results CC BY 4.0, plans derived from GUS data (CC BY 4.0), network and buildings © OpenStreetMap contributors (ODbL 1.0). Details: `LICENSE-DATA.md` in the demo zip. The demo contains no commercial data.
- Car models: Quaternius, CC0.

## Known limitations

- Windows only, no code signature and no installer.
- The base map needs the internet.
- Building heights without tags are assumptions, not measurements.

## Building from source

```
scripts\viz_build.bat
```

Requires [uv](https://docs.astral.sh/uv/). The script creates a venv in `build_viz\`, builds the PyInstaller package, checks that the exe starts, adds the library licences and packs the zip. It is the same script the release workflow (`viz-v*`) uses.
