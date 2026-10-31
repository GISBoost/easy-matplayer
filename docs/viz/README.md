# easy-matplayer

A player for results of a [MATSim](https://matsim.org/) simulation: car traffic on a map, in 2D and 3D, with buildings. It runs locally on Windows, needs no installation and no Python.

The Polish version of this manual is [README_pl.md](README_pl.md).

## Download and start

1. From [Releases](../../../../releases) download `easy-matplayer-windows.zip` (about 46 MB) and unpack it anywhere (the path may contain spaces and non-ASCII characters).
2. Run `easy-matplayer.exe`. If Windows shows "Windows protected your PC" (SmartScreen), click "More info", then "Run anyway". The file is not signed with a certificate.
3. Select a MATSim run folder. The first time you open a run, the program builds an index (from a dozen seconds to a minute; a progress bar shows). After that the same run opens at once, and the program remembers the last run.

Requirements: Windows 10 22H2 or 11 (64-bit) and the Microsoft Edge WebView2 Runtime (it is in Windows 11 and most Windows 10 installations; if it is missing, the program shows a message with a link to the installer). A graphics card with WebGL support; integrated graphics is enough.

## Language

The interface starts in English. The button next to "open run…" in the panel switches it to Polish (its label then reads "English"). The choice is saved in `%LOCALAPPDATA%\easy-matplayer\viz_player_lang.json`. Changing the language reloads the open run.

## Demo

`easy-matplayer-demo-kutno.zip` (about 59 MB, a separate file in the same release) is a run of Kutno (25% of residents, 100 iterations, a network with turn restrictions from OSM) with a ready index. Unpack it and select the `demo-kutno` folder. It opens in a few seconds, with 3D buildings, and needs no extra files.

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

The log `easy-matplayer.log` sits next to `easy-matplayer.exe` (when you report a problem, send it; if the program folder is write-protected it goes to `%LOCALAPPDATA%\easy-matplayer\`). In `%LOCALAPPDATA%\easy-matplayer\` live the memory of the last run and the OSM file, and the saved language. Uninstalling means deleting the program folder and this folder. The program writes nothing to the registry.

## Network

The base map loads tiles from public WMS/WMTS services (addresses in the map panel). Without the internet, traffic and controls still work; only the base map is missing. The program does not send any data about the run.

## Licences

- Program: GPL-3.0-or-later (file `LICENSE`). Libraries in the package: licence texts in `THIRD_PARTY/` in the program folder.
- Demo: simulation results CC BY 4.0, plans derived from GUS data (CC BY 4.0), network and buildings © OpenStreetMap contributors (ODbL 1.0). Details: `LICENSE-DATA.md` in the demo zip. The demo contains no commercial data.
- Car models: Quaternius, CC0.

## Activity flashes

When a person starts an activity (an `actstart` event) or ends it (`actend`, for example leaving home), a short flash appears at that place on the map. Use the "activity flashes" toggle in the panel; below it are separate checkboxes for start and end and a list of types (for example to switch off the technical `tlo_start` and `tlo_end` of background traffic).

- **Start:** a core only (a dot that fades), no ring.
- **End:** a ring only, expanding from the centre and fading, no core.

Both use the activity type colour, so start and end are told apart by shape. Details (Polish): `blyski_aktywnosci.md`.

Type colours: `home` orange, `work` blue, `edu`/`school` purple, `shop` green, `leis…` pink, other types from a palette.

- The place and time of a flash are the `x`, `y` and time of the `actstart` event. The car disappears earlier (end of the trip) and MATSim adds the walk to the activity as a teleported `walk` leg, which the program does not draw (the result has no route for it). That gap is real.
- Flashes show activity starts of everybody in the events, also people travelling by other modes who have no vehicle on the map. The class filter does not apply to them.
- A flash lasts about 1.5 s on screen at any playback speed (at least 3 s of simulation time at 1×). Dragging the slider works; when paused the flashes stay in their phase. At most the 5,000 newest flashes are drawn per frame.

## Road colour: load

Panel "View" has three settings: `cars` (default, roads in their usual colours), `roads only` (cars hidden, roads coloured by load) and `cars + roads`. In the last two you choose the indicator, `speed` or `flow`, and a window of 1, 5 (default) or 15 simulated minutes. Values come from the traffic events in the window `(t − window, t]`, refreshed 4 times a second. Details (Polish): `predkosc_i_natezenie.md`.

| Indicator | What it shows | Scale |
|---|---|---|
| speed | mean speed on the link (sum of lengths / sum of travel times) divided by the link's free speed | red ≤ 30%, yellow 60%, green ≥ 90% |
| flow | link exits per hour divided by `capacity × flowCapacityFactor` | blue 0, orange 50%, red ≥ 100% |

- A link with no exit in the window is grey: no traffic is not "free flow".
- Flow is in sample scale. The network capacity is full, the simulation scales it by `flowCapacityFactor` from `output_config.xml` (`qsim` module), so we divide by that product and do not extrapolate to the full population. Without `flowCapacityFactor` in the config the "flow" mode is disabled with a message.
- Speed uses only complete link traversals (starting at the start of the link). Entering mid-link (start and end of a trip) counts towards flow, not speed. All vehicles count as one vehicle (transit vehicles have a larger PCE in MATSim).
- Statistics from a 25% sample are noisy on single links (a few cars in the window): a longer window smooths them. In the `cars + roads` view cars are coloured by class (back in `cars` the previous choice returns) so they do not blend into the road. Road colour counts all traffic: the car class buttons hide cars but do not change road colours.
- The selected-link panel has an extra line with the window values, e.g. "last 5 min: 13 km/h (free 42 km/h), 156 veh/h (104% of capacity, sample scale)".

## Known limitations

- Windows only, no code signature and no installer.
- The base map needs the internet.
- Building heights without tags are assumptions, not measurements.

## Building from source

```
scripts\viz_build.bat
```

Requires [uv](https://docs.astral.sh/uv/). The script creates a venv in `build_viz\`, builds the PyInstaller package, checks that the exe starts, adds the library licences and packs the zip. It is the same script the release workflow (`viz-v*`) uses.
