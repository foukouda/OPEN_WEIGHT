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
  <a href="LICENSE">
    <img alt="License: CERN-OHL-P v2" src="https://img.shields.io/badge/License-CERN--OHL--P%20v2-blue">
  </a>
  <img alt="KiCad 9" src="https://img.shields.io/badge/KiCad-9-green">
  <img alt="Status" src="https://img.shields.io/badge/Status-In%20Development-orange">
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
- **TPS61086** for boost conversion (3.3 V → 6 V)
- **LT3042** for low-noise linear regulation (6 V → 5 V AVDD)

This approach provides the supply flexibility required while keeping the analog rail clean for precision measurement. The boost stage allows operation from a standard 3.3 V system rail. The LT3042 then strips the switching noise, delivering a low-noise 5 V analog supply directly to the AD7190 AVDD. This two-stage architecture is a deliberate trade-off: an efficiency cost at the regulator is accepted in exchange for a much cleaner analog measurement floor.

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

### Electrical specifications

| Parameter | Value |
| --- | --- |
| Input voltage (VIN) | 3.3 V (from host system) |
| Boost output (TPS61086) | 6 V |
| Analog supply (LT3042 AVDD) | 5 V (low-noise) |
| Digital supply (DVDD) | 3.3 V (from host) |
| ADC resolution | 24-bit |
| PGA gain range | 1 – 128 |
| Digital interface | SPI (MOSI, MISO, SCLK, CS) |
| Crystal frequency | 4.9152 MHz |
| Voltage reference | Internal (2.5 V) |
| Sensor type | Wheatstone bridge / load cell (4-wire) |

### Power budget

The power chain is: **3.3 V system rail → TPS61086 (boost) → LT3042 (LDO) → AD7190 (AVDD)**

| Stage | Rail | Current | Power |
| --- | --- | --- | --- |
| AD7190 analog | 5 V (AVDD) | ~4 mA | ~20 mW |
| Crystal + misc | 5 V | ~1 mA | ~5 mW |
| LT3042 quiescent | 6 V input | ~2 mA | ~12 mW |
| **LT3042 total input** | **6 V** | **~7 mA** | **~42 mW** |
| AD7190 digital | 3.3 V (DVDD) | ~1 mA | ~3.3 mW |
| TPS61086 total input (η ≈ 87%) | **3.3 V** | **~15 mA** | **~50 mW** |
| **Board total** | **3.3 V** | **~16 mA** | **~53 mW** |

> These are estimated typical values. Actual consumption depends on PGA gain, output data rate (ODR), and SPI activity. Measure at your operating point during validation.

### Physical specifications

| Parameter | Value |
| --- | --- |
| Project Name | OPEN_WEIGHT |
| Board Name | AD7190 |
| Parent Project | OPEN THRUST LAB |
| Primary Function | Precision load-cell / force measurement |
| Main ADC | AD7190 |
| Boost Converter | TPS61086 |
| Low-Noise Regulator | LT3042 |
| CAD Tool | KiCad 9 |
| Automation Tooling | KiBot + GitHub Actions |
| Dimensions | 57.0 × 50.75 mm |
| Repository Status | In active development |
| Hardware License | CERN-OHL-P v2 |

***

## SCHEMATIC ARCHITECTURE

The board is organized into four hierarchical sheets:

| Sheet | Section | Description |
| --- | --- | --- |
| Page 4 | `AD7910_Weight_sensor` | AD7190 24-bit ADC front-end for the load cell (Wheatstone bridge). SPI interface, 4.9152 MHz crystal, 5 V / 3.3 V power decoupling, RC input filtering on SENSE/OUT lines, test points. |
| Page 5 | `LT3042_6V_5VA` | Low-noise 5 V analog supply. Takes +6V_IN from the boost stage and regulates it to +5VA_OUT via SET resistor programming. Input/output decoupling, test points (VIN, VOUT, GND, SET, PGFB). |
| Page 6 | `TPS61086_3.3V_to_6V` | TPS61086-based 3.3 V → 6 V boost supply. Inductor/Schottky power stage, feedback divider for VOUT, soft-start/compensation, decoupling. Test points: +3.3V_IN, +6V_OUT, FB, GND. |
| Page 8 | `Connecteur` | Connector sheet: load cell interface, SPI header, power supply inputs, debug/test access. |

***

## LOAD CELL CONNECTION

The board accepts a standard **4-wire Wheatstone bridge** load cell.

### Connector pinout

| Pin | Signal | Description |
| --- | --- | --- |
| 1 | EXC+ | Bridge excitation positive (5 V AVDD) |
| 2 | EXC− | Bridge excitation negative (GND) |
| 3 | SIG+ | Bridge signal positive (to AIN1+) |
| 4 | SIG− | Bridge signal negative (to AIN1−) |

> ⚠️ Check the schematic (Page 8 — Connecteur) for the exact physical connector footprint and reference on the PCB. Some load cell cables use different color conventions — always verify with a multimeter before powering up.

### Compatible load cell types

- Any strain-gauge / Wheatstone bridge load cell with a **differential output in the range 0–20 mV/V** at rated excitation
- Typical resistance: **120 Ω to 1000 Ω** full bridge
- With PGA gain 128 and 5 V excitation: full-scale differential input ≈ ±19.5 mV

### SPI header pinout

| Pin | Signal | Direction |
| --- | --- | --- |
| 1 | SCLK | Input (from host) |
| 2 | MOSI (DIN) | Input (from host) |
| 3 | MISO (DOUT) | Output (to host) |
| 4 | CS̄ (active low) | Input (from host) |
| 5 | DRDȲ | Output (to host, active low) |
| 6 | GND | — |

> ⚠️ The AD7190 SPI is **CPOL = 1, CPHA = 1** (Mode 3). Make sure your host controller is configured accordingly.

***

## CALIBRATION

The AD7190 supports two distinct levels of calibration. Both are required for accurate measurements.

### 1. Internal calibration (register-level)

Compensates the ADC's own offset and gain errors. Must be performed after every power-on, after changing the PGA gain, or after changing the filter/ODR settings.

The AD7190 performs this entirely internally — no external weights needed.

```
1. Write MODE register: set MD[2:0] = 0b001  → Internal zero-scale calibration
   Wait for DRDY to go low.
2. Write MODE register: set MD[2:0] = 0b010  → Internal full-scale calibration
   Wait for DRDY to go low.
```

Results are stored in the `ZERO` and `FULLSCALE` registers. You can read them back to verify or save them for faster startup.

### 2. System calibration (physical weights)

Maps the ADC's digital output to real force/mass units. Required once per hardware setup, and any time the mechanical configuration changes (load cell swap, mounting changes, new wiring).

```
1. Apply zero load (tare). Read N samples, average → raw_zero
2. Apply known reference weight W_ref. Read N samples, average → raw_full
3. Scale factor = W_ref / (raw_full − raw_zero)
4. For any measurement: weight = (raw_code − raw_zero) × scale_factor
```

> **Tip:** Perform system calibration at the same temperature as your intended measurements. Thermal drift in both the load cell and the AD7190 gain can affect accuracy at extremes.

### Key registers for your configuration

| Register | Recommended setting | Purpose |
| --- | --- | --- |
| `CONF` — GAIN[2:0] | `0b111` (128×) | Maximizes resolution for low-output load cells |
| `CONF` — REF_SEL | `0b0` (internal 2.5 V ref) | No external reference required |
| `MODE` — SINC | `0b11` (SINC4) | Best noise rejection (50/60 Hz) |
| `MODE` — FS[9:0] | `0x0A` (10 Hz ODR) | Rejects 50/60 Hz mains noise |

> ⚠️ After any change to `CONF` or `MODE` (especially ODR or gain), always re-run internal calibration. The sigma-delta filter settling time resets.

***

## HOW TO USE

### Prerequisites

- **KiCad 9** (for schematic and PCB sources)
- **KiBot** (for automated output generation)
- **Docker** (recommended for reproducible CI runs)
- A Debian/Ubuntu environment or equivalent for the helper script

### Quickstart — generate outputs locally

The project includes a helper script for launching KiBot locally:

```bash
./kibot_launch.sh
```

For a specific variant:

```bash
./kibot_launch.sh --variant CHECKED
```

Available variants:

| Variant | Description |
| --- | --- |
| `DRAFT` | Schematic in progress, minimal outputs |
| `PRELIMINARY` | Schematic + PCB outputs, no ERC/DRC |
| `CHECKED` | Full outputs with ERC/DRC validation |
| `RELEASED` | Release-oriented outputs for tagged versions |

### Quickstart — use a manufactured board

1. Power the board with **3.3 V** on the VIN pin (max 500 mA capable supply recommended)
2. Connect your load cell to the 4-pin bridge connector (see [Load Cell Connection](#load-cell-connection))
3. Connect the SPI header to your host microcontroller (see [SPI pinout](#spi-header-pinout))
4. On your host, configure SPI: **Mode 3** (CPOL=1, CPHA=1), max clock **5 MHz**
5. Run internal calibration (see [Calibration](#calibration))
6. Perform system calibration with a known reference weight
7. Poll `DRDȲ` (active low) before each read — do not read data while DRDȲ is high

### Minimal read example (pseudocode)

```c
// 1. Internal calibration
ad7190_write_mode(MODE_INTERNAL_ZERO_CAL);
while (drdy_is_high());
ad7190_write_mode(MODE_INTERNAL_FULL_CAL);
while (drdy_is_high());

// 2. Continuous conversion, gain=128, SINC4, 10 Hz
ad7190_write_conf(CONF_GAIN_128 | CONF_REF_INT);
ad7190_write_mode(MODE_CONT | MODE_SINC4 | MODE_FS_10HZ);

// 3. Read loop
while (1) {
    while (drdy_is_high());       // Wait for conversion ready
    uint32_t raw = ad7190_read_data();
    float weight = (raw - raw_zero) * scale_factor;
}
```

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

This project is built around a reproducible hardware workflow based on **KiCad 9**, **KiBot**, and **GitHub Actions**.

The repository CI already supports automated output generation and release-oriented packaging. The current workflow references:
- a main KiBot configuration file
- KiCad 9 based generation
- automatic variant handling
- generated outputs committed back to the repository
- release packaging on semantic version tags

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

## TROUBLESHOOTING

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Output always reads 0 or full-scale | Load cell wiring error | Check EXC+/EXC−/SIG+/SIG− polarity |
| Output is very noisy | SPI mode mismatch (CPOL/CPHA) | Set host to Mode 3 |
| Readings drift over time | No internal calibration after power-on | Re-run zero/full-scale internal cal |
| DRDY never goes low | Incorrect crystal frequency or missing crystal | Verify 4.9152 MHz crystal soldering |
| SPI reads all 0xFF | CS̄ not driven low, or SCLK too fast | Reduce SCLK to ≤ 5 MHz, check CS̄ |
| 50/60 Hz interference visible | ODR too high or wrong SINC setting | Use SINC4 + FS = 10 Hz |
| Board draws more than expected | LT3042 or TPS61086 oscillating | Check PCB layout against datasheet, add bulk cap on VIN |

***

## CONTRIBUTING

Contributions are welcome — hardware corrections, documentation improvements, firmware examples, and test reports are all valuable.

### Requirements

- **KiCad 9** — the project is not backwards-compatible with earlier versions
- Follow existing layer naming, reference designator conventions, and title block format

### How to contribute

1. Fork the repository and create a branch from `dev`
2. Make your changes (schematic, PCB, docs, or scripts)
3. Run ERC/DRC with the `CHECKED` variant and fix any violations before submitting
4. Open a Pull Request against `dev` with a clear description of what changed and why

### Reporting issues

Please use GitHub Issues. For hardware bugs, include:
- Board revision (visible on silkscreen or from the revision history sheet)
- Photos or annotated screenshots of the problem area
- ERC/DRC report if applicable

***

## CHANGELOG

See [CHANGELOG.md](CHANGELOG.md) for the board revision history.

> `CHANGELOG.md` will track changes between PCB revisions (V1, V2, …) following [Keep a Changelog](https://keepachangelog.com/) conventions.

***

## LICENSE

Hardware design files in this repository are released under the **CERN Open Hardware Licence Version 2 – Permissive (CERN-OHL-P v2)**.

See [LICENSE](LICENSE) for the full licence text.

> CERN-OHL-P v2 allows use, study, modification, and manufacture without requiring derivative works to remain open. Attribution is required.
