"""Run the OPEN_WEIGHT LTspice simulations and plot the results.

Usage (from this folder):
    python run_simulations.py            # run LTspice in batch mode, then plot
    python run_simulations.py --no-run   # only re-plot existing .raw files

Figures are written to ../../Images/Simulation/ (referenced by the README),
the .meas results to results.md.
"""
import argparse
import os
import re
import subprocess
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from ltraw import read_raw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Images", "Simulation"))
SIMS = ["01_Power_Chain_Startup", "02_LT3042_Startup", "03_Power_Ripple",
        "04_LT3042_PSRR", "05_AD7190_Input_Filter"]
LTSPICE = os.path.expandvars(r"%LOCALAPPDATA%\Programs\ADI\LTspice\LTspice.exe")

# reference palette (light), fixed categorical order
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
})


def run(name):
    print(f"  LTspice: {name}.asc", flush=True)
    subprocess.run([LTSPICE, "-b", os.path.join(HERE, name + ".asc")], check=True, cwd=HERE)


def meas(name):
    """Return {measure: value-string} parsed from the LTspice log."""
    out = {}
    with open(os.path.join(HERE, name + ".log"), encoding="utf-8", errors="replace") as f:
        for line in f:
            m = re.match(r"^(\w+):\s*(.*)$", line.strip())
            if m and "=" in m.group(2) and m.group(1) != "Options" and not line.startswith(("C:", "WARNING")):
                out[m.group(1)] = m.group(2)
    return out


def num(s):
    """Last number in a .meas result (for 'AT' results the value is the abscissa)."""
    if "dB" in s:
        return float(re.search(r"\(([-\d.eE+]+)dB", s).group(1))
    return float(re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s.split("=")[-1])[0])


def save(fig, fname):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, fname), dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  figure: Images/Simulation/{fname}")


def decimate(t, *ys, n=6000):
    """Min/max decimation so dense switching traces keep their envelope."""
    if len(t) <= 2 * n:
        return (t,) + ys
    edges = np.linspace(0, len(t), n + 1).astype(int)
    tt, outs = [], [[] for _ in ys]
    for a, b in zip(edges[:-1], edges[1:]):
        tt += [t[a], t[b - 1]]
        for o, y in zip(outs, ys):
            seg = y[a:b]
            o += [seg.min(), seg.max()]
    return (np.array(tt),) + tuple(np.array(o) for o in outs)


# ------------------------------------------------------------------ figures
def fig01():
    d = read_raw(os.path.join(HERE, "01_Power_Chain_Startup.raw"))
    t = d["time"] * 1e3
    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True,
                               gridspec_kw={"height_ratios": [2, 1]})
    for key, lab, col in (("v(+3.3v)", "+3.3V (host)", C1), ("v(+6v)", "+6V (TPS61086)", C2),
                          ("v(+5va)", "+5VA (LT3042)", C3), ("v(ss)", "SS pin", C4)):
        tt, y = decimate(t, d[key])
        a.plot(tt, y, color=col, label=lab, lw=1.6)
    a.set_ylabel("Voltage (V)")
    a.set_title("01 - Power-chain start-up (switching simulation)")
    a.legend(loc="lower right", ncol=2)
    tt, il = decimate(t, d["i(l1)"])
    b.plot(tt, il, color=C1, lw=0.8)
    b.set_ylabel("I(L1) (A)")
    b.set_xlabel("Time (ms)")
    b.set_xlim(0, t[-1])
    save(fig, "sim01_power_startup.png")


def fig02():
    d = read_raw(os.path.join(HERE, "02_LT3042_Startup.raw"))
    t = d["time"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    for key, lab, col, ls in (("v(+6v)", "+6V (LT3042 IN)", C2, "-"),
                              ("v(pg)", "PG (pull-up to +6V)", C1, "--"),
                              ("v(+5va)", "+5VA (OUT)", C3, "-"), ("v(set)", "SET", C4, ":")):
        a.plot(t * 1e3, d[key], color=col, label=lab, lw=1.6, ls=ls)
    tpg = t[np.argmax((d["v(+5va)"] > 4.59) & (t > 1e-3))] * 1e3
    a.annotate(f"PG high @ {tpg:.0f} ms\n(+5VA = 4.59 V)", (tpg, 4.6), xytext=(60, 2.2),
               color=INK2, fontsize=9, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    a.axvline(800, color=INK2, lw=1, ls="--")
    a.text(805, 0.4, "Q1 ON\n(P3 low)", color=INK2, fontsize=9)
    a.set_xlabel("Time (ms)")
    a.set_ylabel("Voltage (V)")
    a.set_title("02 - LT3042 start-up and Power-Good")
    a.legend(loc="center right")
    a.set_xlim(0, 1000)
    m = (t > 0.79995) & (t < 0.8003)
    b.plot((t[m] - 0.8) * 1e6, d["v(+5va)"][m], color=C3, label="+5VA", lw=1.6)
    b.set_xlabel("Time after P3 low (us)")
    b.set_ylabel("+5VA (V)")
    b.set_title("Excitation turn-on transient (350 ohm bridge)")
    save(fig, "sim02_ldo_startup.png")


def bw_limit(t, y, f3db=20e6, dt=0.5e-9):
    """Resample on a uniform grid and apply a 1st-order low-pass, like a
    scope's 20 MHz bandwidth limit (removes single-sample switching spikes)."""
    tu = np.arange(t[0], t[-1], dt)
    yu = np.interp(tu, t, y)
    a = 1 - np.exp(-2 * np.pi * f3db * dt)
    out = np.empty_like(yu)
    acc = yu[0]
    for i, v in enumerate(yu):
        acc += a * (v - acc)
        out[i] = acc
    return tu, out


def fig03():
    d = read_raw(os.path.join(HERE, "03_Power_Ripple.raw"))
    t = d["time"]
    # 1 ms steady-state window for the numbers, 40 us for the plot
    w = (t >= 3e-3) & (t <= 4e-3)
    stats = {}
    for key in ("v(+6v)", "v(+5va)"):
        _, yb = bw_limit(t[w], d[key][w])
        stats[key] = (np.ptp(d[key][w]), np.ptp(yb))
    m = (t >= 3.9e-3) & (t <= 3.94e-3)
    t0 = t[m][0]
    fig, (a, b, c) = plt.subplots(3, 1, figsize=(9, 7.5), sharex=True)
    for ax, key, col, scale, unit in ((a, "v(+6v)", C2, 1e3, "mV"), (b, "v(+5va)", C3, 1e6, "uV")):
        y = d[key][m]
        ax.plot((t[m] - t0) * 1e6, (y - y.mean()) * scale, color=GRID, lw=1,
                label=f"raw simulation ({stats[key][0] * scale:.1f} {unit} pp)")
        tb, yb = bw_limit(t[m], y)
        ax.plot((tb - t0) * 1e6, (yb - y.mean()) * scale, color=col, lw=1.4,
                label=f"20 MHz bandwidth ({stats[key][1] * scale:.1f} {unit} pp)")
        ax.set_ylabel(f"{'+6V' if key == 'v(+6v)' else '+5VA'} ripple ({unit})")
        ax.legend(loc="lower right", fontsize=8)
    a.set_title("03 - Steady-state ripple, full load (40 us window)")
    c.plot((t[m] - t0) * 1e6, d["i(l1)"][m] * 1e3, color=C1, lw=1)
    c.set_ylabel("I(L1) (mA)")
    c.set_xlabel("Time (us)")
    save(fig, "sim03_ripple.png")
    for key, (raw, bw) in stats.items():
        print(f"  {key}: raw {raw * 1e3:.3f} mV pp, 20 MHz BW {bw * 1e3:.4f} mV pp")


def fig04():
    d = read_raw(os.path.join(HERE, "04_LT3042_PSRR.raw"))
    f = d["frequency"]
    psrr = -20 * np.log10(np.abs(d["v(+5va)"]))
    fig, a = plt.subplots(figsize=(9, 4.2))
    a.semilogx(f, psrr, color=C1, lw=2)
    i = np.argmin(np.abs(f - 1.2e6))
    a.plot(f[i], psrr[i], "o", color=C1, ms=8, mec=SURFACE, mew=2)
    a.annotate(f"{psrr[i]:.0f} dB @ 1.2 MHz\n(TPS61086 switching)", (f[i], psrr[i]),
               xytext=(-150, -20), textcoords="offset points", color=INK2, fontsize=9,
               arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
    a.set_xlabel("Frequency (Hz)")
    a.set_ylabel("PSRR (dB)")
    a.set_title("04 - LT3042 PSRR, +6V -> +5VA (with board output capacitors)")
    a.set_xlim(f[0], f[-1])
    save(fig, "sim04_psrr.png")


def fig05():
    d = read_raw(os.path.join(HERE, "05_AD7190_Input_Filter.raw"))
    f = d["frequency"]
    dm = 20 * np.log10(np.abs(d["v(outpd)"] - d["v(outnd)"]))
    cm = 20 * np.log10(np.abs(d["v(outpc)"]))
    fig, a = plt.subplots(figsize=(9, 4.2))
    a.semilogx(f, dm, color=C1, label="Differential (signal)")
    a.semilogx(f, cm, color=C2, label="Common-mode")
    for fx, lab, y, ha in ((307.2e3, "AD7190 modulator\nMCLK/16 = 307 kHz ", -60, "right"),
                           (1.2e6, " boost\n 1.2 MHz", -8, "left")):
        a.axvline(fx, color=INK2, lw=1, ls="--")
        a.text(fx, y, lab, color=INK2, fontsize=8, va="top", ha=ha)
    a.set_xlabel("Frequency (Hz)")
    a.set_ylabel("Gain (dB)")
    a.set_title("05 - AD7190 input RC filter (350 ohm bridge source)")
    a.set_ylim(-90, 5)
    a.set_xlim(f[0], f[-1])
    a.legend(loc="lower left")
    save(fig, "sim05_input_filter.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-run", action="store_true")
    args = ap.parse_args()
    if not args.no_run:
        if not os.path.exists(LTSPICE):
            sys.exit(f"LTspice not found at {LTSPICE}")
        for s in SIMS:
            run(s)
    for fn in (fig01, fig02, fig03, fig04, fig05):
        fn()
    with open(os.path.join(HERE, "results.md"), "w", encoding="utf-8") as f:
        f.write("# LTspice .meas results (generated by run_simulations.py)\n\n")
        for s in SIMS:
            f.write(f"## {s}\n\n| Measure | Result |\n| --- | --- |\n")
            for k, v in meas(s).items():
                f.write(f"| `{k}` | `{v}` |\n")
            f.write("\n")
    print("  results.md written")


if __name__ == "__main__":
    main()
