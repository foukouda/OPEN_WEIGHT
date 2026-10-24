# Changelog

All notable changes to this board are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/) (tag `X.Y.Z`, no `v` prefix).
Keep entries short: the `[Unreleased]` section is printed on the schematic Revision History page.

## [Unreleased]

### Added

-   AD7190 front-end, 2 load-cell inputs
-   +3.3V -> TPS61086 6 V -> LT3042 +5VA
-   Self-contained libs and 3D models (lib/)
-   JLCPCB 4-layer rules and stackup
-   LTspice simulations (Simulation/LTspice)
-   openEMS layout coupling (Simulation/openEMS)

### Changed

-   Renamed to OPEN_WEIGHT, KiCad 10
-   Schematic restyled like OPEN_PHASE: A3 sheets, note panels, logo in title block
-   Boost and LDO sheets merged into Power Supply - Analog Rails (page 5)
-   Bottom silkscreen: test point tags, J1 pinout, load-cell wiring panel
-   3D animation re-rendered with kicad-cli, OPEN_PHASE style

### Fixed

-   Connectors not linked to ADC in schematic
-   AD7190 solder-mask bridges
