# Data and results licences

> Translation of [LICENSE-DATA.md](LICENSE-DATA.md) (Polish). The Polish text is binding; this translation is for reference only.

The easy-matanimation repository has two licences. The code is under GPL-3.0-or-later (file `LICENSE`). Data, results and reports have the licences described below.

## Code (GPL-3.0-or-later)

Covers the code in `pipeline/`, `matsim/src/`, `blender/`, `docs/research/G4_beeline/` and the scripts in `reports/`. Full text: [LICENSE](LICENSE).

The sample MATSim project in `matsim/` has its own licence, GPL-2.0-or-later (`matsim/LICENSE`). GPL-3.0-or-later is compatible with it.

## Output data from GUS (CC BY 4.0)

Covers data derived from GUS publications: NSP 2021 tables, BDL (P4507, P4508, TABL. 5), commuting matrices, BREC 2021 geometry and district tables. The author of the source data is the Central Statistical Office of Poland (GUS).

Results derived from this data (plans, population, matrices, tables, charts) are under the **Creative Commons Attribution 4.0 (CC BY 4.0)** licence. Attribution is required: "Central Statistical Office" and the name of the publication.

## Data from OpenStreetMap (ODbL 1.0)

Covers the road network, buildings and land use derived from OSM. Source: © OpenStreetMap contributors. Data from OSM is under the **Open Database License 1.0 (ODbL)**.

Under the ODbL, every public, derived database that contains OSM data must be made available under the same licence (ODbL) with attribution. This covers, among others, `scenarios/kutno/network*.xml.gz` and the OSM files in `scenarios/kutno/osm/`, if they are published.

## Data that must not be published

Data from TomTom (variant A, D22) and other commercial APIs is not in the repository. The exception is aggregated metrics and reports. They are not under CC BY or ODbL.

Simulation results (events, network and output plans in the demo runs) are under **CC BY 4.0**, like the input and output files of `matsim-example-project` (`matsim/README.md`, section Licenses). Because they were produced on a network from OSM, the network in them keeps the ODbL.

Data from Senozon AG (proprietary licence) is not used in this project.

## Sources

Each source has a description, status and licence in [docs/ZRODLA.md](docs/ZRODLA.md) (Polish).
