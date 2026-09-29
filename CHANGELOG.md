# Changelog

All notable changes to this board are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/) (tag `X.Y.Z`, no `v` prefix).

## [Unreleased]

### Added

-   AD7190 24-bit load-cell front-end (4-wire Wheatstone bridge, SPI Mode 3)
-   TPS61086 boost 3.3 V → 6 V and LT3042 ultralow-noise LDO 6 V → 5 VA analog supply
-   Load-cell, SPI host and frame connectors; M3 mounting holes and fiducials
-   Mechanical CAD (enclosure / support) in `Mechanical/`

### Changed

-   Project renamed from `Cellule_de_force_V2` to `OPEN_WEIGHT`; schematic sheets renamed after their function
-   Project migrated to KiCad 10; CI now uses KiBot `v2_dk10` (variant `PRELIMINARY` on `dev` until ERC/DRC are clean)
-   README is now generated from `kibot_resources/templates/readme.txt`

### Fixed

-   Sheet name typo `AD7910` → `AD7190`
-   Title blocks: real sheet titles, company name, template leftovers removed from PCB title block
