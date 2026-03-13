<p align="center" width="100%">
  <img alt="Logo" width="33%" src="Logos/dummy_logo.svg">
</p>

<h1 align="center">OPEN_WEIGHT – AD7190</h1>

<p align="center">
  High-precision load-cell / force measurement PCB based on the AD7190
</p>

<p align="center">
  Sub-project of <a href="https://opentruslab.vercel.app/">OPEN THRUST LAB</a>
</p>

<p align="center" width="100%">
  <a href="https://github.com/foukouda/OPEN_WEIGHT/actions/workflows/ci.yaml">
    <img alt="CI Badge" src="https://github.com/foukouda/OPEN_WEIGHT/actions/workflows/ci.yaml/badge.svg?branch=dev">
  </a>
</p>

<p align="center" width="100%">
    <img alt="Project banner" src="Images/dummy_image.png">
</p>

***

<p align="center">
  <img alt="3D Top Angled" src="Images/Cellule_de_force_V2-angled_top.png" width="45%">
&nbsp; &nbsp; &nbsp; &nbsp;
  <img alt="3D Bottom Angled" src="Images/Cellule_de_force_V2-angled_bottom.png" width="45%">
</p>

***

## OVERVIEW

**OPEN_WEIGHT** is an open-hardware measurement board developed as part of **OPEN THRUST LAB**, a community-driven project focused on building open-source test benches for drone motor characterization.

This board is designed around the **Analog Devices AD7190**, a high-resolution 24-bit ADC well suited for precision bridge-sensor and load-cell measurements. Within the Open Thrust Lab ecosystem, OPEN_WEIGHT is intended to serve as the dedicated **force / thrust measurement interface**, enabling accurate acquisition from load cells for bench instrumentation and performance analysis.

The repository is structured as a full hardware project rather than a simple PCB dump. It includes:
- KiCad source files for schematic and PCB layout
- manufacturing and assembly outputs
- generated schematic and fabrication documentation
- validation reports and test artifacts
- 3D views and project visuals
- automated output generation through **KiBot**
- CI integration for reproducible deliverables

The board currently relies on a mixed power architecture combining:
- **TPS61086** for boost conversion
- **LT3042** for low-noise regulation

This approach is intended to provide both the required supply flexibility and a cleaner analog rail for precision measurement circuitry.

OPEN_WEIGHT is meant to be:
- reproducible
- inspectable
- manufacturable
- easy to iterate on
- aligned with open-hardware development practices

***

## PROJECT CONTEXT

OPEN THRUST LAB is presented as an open-source drone motor test-bench initiative covering hardware, firmware, sensors, data, and analysis. Inside this larger architecture, **OPEN-WEIGHT** is the sub-project dedicated to **precision thrust measurement**, and is described as an open-source load-cell amplifier / measurement PCB designed for integration into the bench.

In the broader bench roadmap, this board contributes to the measurement chain used to characterize motor performance through reliable sensor acquisition and documented hardware design.

***

## DESIGN GOALS

The main objectives of this board are:

- provide a precise measurement front-end for load-cell based sensing
- support force / thrust instrumentation in a modular test-bench architecture
- expose a clean and reusable KiCad project structure
- automate hardware deliverables with KiBot and CI
- make fabrication and assembly easier through generated outputs
- support future revisions, validation, and characterization work

This repository is therefore both a hardware design project and a documentation baseline for future board iterations.

***

## SPECIFICATIONS

| Parameter | Value |
| --- | --- |
| Project Name | OPEN_WEIGHT |
| Board Name | AD7190 |
| Parent Project | OPEN THRUST LAB |
| Primary Function | Precision load-cell / force measurement |
| Main ADC | AD7190 |
| Boost Converter | TPS61086 |
| Low-Noise Regulator | LT3042 |
| CAD Tool | KiCad |
| Automation Tooling | KiBot + GitHub Actions |
| Dimensions | 57.0 × 50.75 mm |
| Repository Status | In active development |
| Hardware License Target | CERN-OHL-P v2 |

***

## REPOSITORY CONTENT

This repository contains both source design files and generated outputs required to review, manufacture, assemble, and validate the board.

The content includes:
- schematic sources
- PCB layout sources
- project architecture and supporting documentation sheets
- manufacturing deliverables
- assembly files
- 3D exports and renders
- validation reports
- test-point documentation
- CI / automation resources

Several documentation-oriented KiCad sheets are also present in the project, including:
- block diagram
- project architecture
- power sequencing
- revision history

This makes the repository suitable not only for fabrication, but also for design review and future scaling inside the Open Thrust Lab ecosystem.

***

## DIRECTORY STRUCTURE

    .
    ├─ Computations       # Design notes, formulas, and miscellaneous calculations
    ├─ HTML               # Generated HTML pages and web outputs
    ├─ Images             # Pictures, renders, and visual assets
    │
    ├─ kibot_resources    # External resources used by KiBot
    │  ├─ colors          # Color themes for KiCad outputs
    │  ├─ fonts           # Fonts used in generated documents
    │  ├─ scripts         # Helper scripts used with KiBot
    │  └─ templates       # Templates for KiBot reports and generated outputs
    │
    ├─ kibot_yaml         # KiBot YAML configuration files
    ├─ KiRI               # KiRI PCB diff viewer files
    │
    ├─ lib                # KiCad footprint and symbol libraries
    │  ├─ 3d_models       # Component 3D models
    │  ├─ lib_fp          # Footprint libraries
    │  └─ lib_sym         # Symbol libraries
    │
    ├─ Logos              # Project logos and branding assets
    │
    ├─ Manufacturing      # Assembly and fabrication documents
    │  ├─ Assembly        # Assembly outputs (BoM, position files, notes)
    │  │
    │  └─ Fabrication     # Fabrication outputs (ZIP packages, notes)
    │     ├─ Drill Tables # CSV drill tables
    │     └─ Gerbers      # Gerber files
    │
    ├─ Report             # ERC / DRC reports and validation outputs
    ├─ Schematic          # Exported schematic PDFs
    ├─ Templates          # Drawing sheets and title block templates
    ├─ Testing
    │  └─ Testpoints      # Test point tables and test documentation
    │
    └─ Variants           # Outputs for project / assembly variants

***

## DEVELOPMENT WORKFLOW

This project is built around a reproducible hardware workflow based on **KiCad**, **KiBot**, and **GitHub Actions**.

The repository CI already supports automated output generation and release-oriented packaging. The current workflow references:
- a main KiBot configuration file
- KiCad 9 based generation
- automatic variant handling
- generated outputs committed back to the repository
- release packaging on semantic version tags

The project also defines multiple build/documentation variants:

- **DRAFT** — schematic in progress, minimal outputs
- **PRELIMINARY** — schematic + PCB outputs, no ERC/DRC
- **CHECKED** — schematic + PCB outputs with ERC/DRC
- **RELEASED** — release-oriented outputs, typically used for tagged versions

This structure makes the project easier to maintain across early design work, internal review, and release packaging.

***

## GENERATED OUTPUTS

Depending on the selected variant and KiBot configuration, the project can generate:

- schematic PDFs
- fabrication notes
- Gerber files
- drill tables
- assembly documentation
- BoM exports
- position / placement files
- 3D exports
- HTML pages
- ERC / DRC reports
- test-point tables
- release artifacts

This automation is especially useful for keeping design files and manufacturing deliverables synchronized over time.

***

## HOW TO USE

The project includes a helper script for launching KiBot locally:

```bash
./kibot_launch.sh
