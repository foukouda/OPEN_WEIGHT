"""Run the OPEN_WEIGHT LTspice simulations and plot the results.

Usage (from this folder):
    python run_simulations.py              # run LTspice in batch mode, then plot
    python run_simulations.py --only 03 04 # run only these simulations, then plot
    python run_simulations.py --no-run     # only re-plot existing .raw files

01 simulates 600 ms of 1.2 MHz switching: about 30 min and a 2.8 GB .raw file.

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
from matplotlib.ticker import EngFormatter  # noqa: E402

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
    t = d["time"]
    v5 = d["v(+5va)"]
    rails = (("v(+3.3v)", "+3.3V (host)", C1), ("v(+6v)", "+6V (TPS61086)", C2),
             ("v(+5va)", "+5VA (LT3042)", C3))
    fig, ((full, soft), (settle, cur)) = plt.subplots(
        2, 2, figsize=(12.5, 6.8), sharex="col",
        gridspec_kw={"width_ratios": [1.2, 1], "height_ratios": [1.25, 1]})
    fig.suptitle("01 - Power-chain start-up (switching simulation)", fontweight="bold", y=0.985)

    # left column: the complete start-up
    tt, y33, y6, y5 = decimate(t, *(d[k] for k, _, _ in rails), n=2500)
    for (_, lab, col), y in zip(rails, (y33, y6, y5)):
        full.plot(tt * 1e3, y, color=col, label=lab, lw=1.6)
    full.set_ylabel("Voltage (V)")
    full.set_title(f"Complete start-up ({t[-1] * 1e3:.0f} ms)")
    full.legend(loc="lower right")

    k25 = np.searchsorted(t, 25e-3)
    ipg = int(np.argmax(d["v(pg)"][:k25] > 3))           # PG high = end of the fast start-up
    t_pg, v_pg = t[ipg], float(v5[ipg])
    i99 = int(np.argmax(v5 >= 4.95))
    tau = 50e3 * 2.2e-6                                    # R9 x C14
    settle.axhline(5, color=INK2, lw=0.8)
    settle.plot(tt * 1e3, y5, color=C3, label="+5VA (simulated)")
    tm = np.linspace(t_pg, t[-1], 400)
    settle.plot(tm * 1e3, 5 - (5 - v_pg) * np.exp(-(tm - t_pg) / tau), color=INK, lw=1, ls="--",
                label=f"5 V - {5 - v_pg:.2f} V x exp(-t / {tau * 1e3:.0f} ms),  R9 x C14")
    for i, txt, xy, ha in ((k25, f"25 ms: {v5[k25]:.3f} V", (10, -4), "left"),
                           (i99, f"99 % at {t[i99] * 1e3:.0f} ms", (8, -8), "left"),
                           (len(t) - 1, f"{t[-1] * 1e3:.0f} ms: {v5[-1]:.3f} V", (-4, -12), "right")):
        settle.plot(t[i] * 1e3, v5[i], "o", color=C3, ms=8, mec=SURFACE, mew=2, zorder=5, clip_on=False)
        settle.annotate(txt, (t[i] * 1e3, v5[i]), xytext=xy, textcoords="offset points",
                        color=INK2, fontsize=9, ha=ha, va="top")
    settle.set_ylim(4.5, 5.04)
    settle.set_xlim(0, t[-1] * 1e3)
    settle.set_ylabel("+5VA (V)")
    settle.set_xlabel("Time (ms)")
    settle.set_title("+5VA settling (vertical zoom)")
    settle.legend(loc="lower right", fontsize=9)

    # right column: the first 25 ms
    tz = t[:k25] * 1e3
    for key, lab, col in rails + (("v(ss)", "SS pin", C4),):
        tt, y = decimate(tz, d[key][:k25])
        soft.plot(tt, y, color=col, label=lab, lw=1.6)
    soft.plot(t_pg * 1e3, v_pg, "o", color=C3, ms=8, mec=SURFACE, mew=2, zorder=5)
    soft.annotate(f"PG high at {t_pg * 1e3:.0f} ms:\nend of the 2 mA fast start-up",
                  (t_pg * 1e3, v_pg), xytext=(10, -8), textcoords="offset points",
                  color=INK2, fontsize=9, va="top")
    soft.set_title("First 25 ms: boost soft-start, LT3042 fast start-up")
    soft.legend(loc="lower right", ncol=2)
    tt, il = decimate(tz, d["i(l1)"][:k25])
    cur.plot(tt, il, color=C1, lw=0.8)
    cur.set_ylabel("I(L1) (A)")
    cur.set_xlabel("Time (ms)")
    cur.set_title("Inductor current")
    cur.set_xlim(0, 25)
    fig.tight_layout()
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


def spectrum(t, y, t0, t1, dt=2e-9):
    """RMS amplitude spectrum of y over [t0, t1): uniform resampling, linear
    detrend, Hann window (amplitudes corrected for its coherent gain)."""
    i0, i1 = np.searchsorted(t, (t0, t1))
    i0, i1 = max(i0 - 1, 0), min(i1 + 1, len(t))
    x = np.arange(int(round((t1 - t0) / dt))) * dt
    yu = np.interp(t0 + x, t[i0:i1], y[i0:i1])
    yu -= np.polyval(np.polyfit(x, yu, 1), x)
    n = len(yu)
    a = np.abs(np.fft.rfft(yu * np.hanning(n))) * 2 / (n * 0.5) / np.sqrt(2)
    return np.fft.rfftfreq(n, dt), a


def band_rms(f, a, lo, hi):
    """Total RMS between lo and hi (1.5 = noise bandwidth of the Hann window, in bins)."""
    m = (f >= lo) & (f < hi)
    return np.sqrt((a[m] ** 2).sum() / 1.5)


def peak_hold(f, a, lo, hi, n=1500):
    """Largest component in each of n log-spaced bins, so that no line is lost when plotting."""
    idx = np.searchsorted(f, np.logspace(np.log10(lo), np.log10(hi), n + 1))
    keep = [i0 + np.argmax(a[i0:i1]) for i0, i1 in zip(idx[:-1], idx[1:]) if i1 > i0]
    return f[keep], a[keep]


def fig_fft():
    """Spectrum of the rails with the bridge powered (03) and in standby (end of 01)."""
    fsw, lo, hi = 1.2e6, 1e3, 50e6
    eng = EngFormatter(unit="V", sep=" ")              # axis ticks
    val = EngFormatter(unit="V", places=1, sep=" ")    # quoted values
    d = read_raw(os.path.join(HERE, "03_Power_Ripple.raw"))
    f, a6 = spectrum(d["time"], d["v(+6v)"], 2e-3, 6e-3)
    _, a5 = spectrum(d["time"], d["v(+5va)"], 2e-3, 6e-3)
    k = np.argmin(np.abs(f - fsw))
    s = read_raw(os.path.join(HERE, "01_Power_Chain_Startup.raw"))
    ts, w0 = s["time"], s["time"][-1] - 10e-3
    fs, as6 = spectrum(ts, s["v(+6v)"], w0, ts[-1])
    il = np.asarray(s["i(l1)"][np.searchsorted(ts, w0):])
    duty = np.sum((il[1:] >= 0.08) & (il[:-1] < 0.08)) / (10e-3 * fsw)   # cycles with a pulse
    sub = (fs >= lo) & (fs < 0.9 * fsw)
    ks = np.flatnonzero(sub)[np.argmax(as6[sub])]                       # strongest sub-harmonic

    fig, (top, bot) = plt.subplots(2, 1, figsize=(9, 7), sharex=True, sharey=True)
    for ax in (top, bot):
        ax.axvline(fsw, color=INK2, lw=1, ls="--")
    top.loglog(*peak_hold(f, a6, lo, hi), color=C2, lw=1.2, label="+6V (TPS61086 output)")
    top.loglog(*peak_hold(f, a5, lo, hi), color=C3, lw=1.2, label="+5VA (LT3042 output)")
    # the +5VA label goes in the empty low-frequency corner, linked to its marker
    for a, col, txt, xy, kw in (
            (a6, C2, f"{val(a6[k])} rms at 1.2 MHz", (0.75 * fsw, a6[k]), {}),
            (a5, C3, f"{val(a5[k])} rms at 1.2 MHz\n({20 * np.log10(a6[k] / a5[k]):.0f} dB below +6V)",
             (20e3, 4e-10), {"arrowprops": dict(arrowstyle="-", color=INK2, lw=0.8)})):
        top.plot(f[k], a[k], "o", color=col, ms=8, mec=SURFACE, mew=2, zorder=5)
        top.annotate(txt, (f[k], a[k]), xytext=xy, color=INK2, fontsize=9, ha="right", va="center", **kw)
    top.set_title("03 - Spectrum of the rails, bridge powered (350 ohm): one pulse per switching cycle")
    top.text(45e6, 3e-3, "Floor between the lines = numerical noise", color=INK2,
             fontsize=9, ha="right", va="center")
    top.legend(loc="upper left")
    bot.loglog(*peak_hold(fs, as6, lo, hi), color=C2, lw=1.2)
    bot.plot(fs[ks], as6[ks], "o", color=C2, ms=8, mec=SURFACE, mew=2, zorder=5)
    bot.annotate(f"{val(as6[ks])} rms at {fs[ks] / 1e3:.0f} kHz", (fs[ks], as6[ks]), xytext=(-12, 2),
                 textcoords="offset points", color=INK2, fontsize=9, ha="right", va="center")
    bot.set_title(f"01 - Spectrum of +6V in standby (Q1 off): Power Save Mode, a pulse in {duty * 100:.0f} % of the cycles")
    bot.set_xlabel("Frequency")
    bot.set_xlim(lo, hi)
    bot.set_ylim(1e-11, 1e-2)
    bot.xaxis.set_major_formatter(EngFormatter(unit="Hz", sep=" "))
    for ax in (top, bot):
        ax.set_ylabel("Amplitude (V rms)")
        ax.yaxis.set_major_formatter(eng)
    fig.tight_layout()
    save(fig, "sim03_spectrum.png")
    return [
        ("+6V at 1.2 MHz, bridge powered", f"{val(a6[k])} rms"),
        ("+6V harmonics 2 / 3 / 4, bridge powered", " / ".join(val(a6[k * h]) for h in (2, 3, 4)) + " rms"),
        ("+6V 1 kHz - 1 MHz, bridge powered", f"{val(band_rms(f, a6, 1e3, 1e6))} rms"),
        ("+5VA at 1.2 MHz, bridge powered", f"{val(a5[k])} rms"),
        ("+5VA 1 kHz - 1 MHz, bridge powered", f"{val(band_rms(f, a5, 1e3, 1e6))} rms"),
        ("+6V -> +5VA rejection at 1.2 MHz", f"{20 * np.log10(a6[k] / a5[k]):.1f} dB"),
        ("Standby: switching cycles with a pulse", f"{duty * 100:.0f} %"),
        ("Standby: strongest +6V line below 1.2 MHz", f"{val(as6[ks])} rms at {fs[ks] / 1e3:.1f} kHz"),
        ("Standby: +6V 1 kHz - 1 MHz", f"{val(band_rms(fs, as6, 1e3, 1e6))} rms"),
        ("Standby: +6V at 1.2 MHz", f"{val(as6[np.argmin(np.abs(fs - fsw))])} rms"),
    ]


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


# figure, simulations it reads
FIGS = ((fig01, ("01",)), (fig02, ("02",)), (fig03, ("03",)), (fig_fft, ("01", "03")),
        (fig04, ("04",)), (fig05, ("05",)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-run", action="store_true")
    ap.add_argument("--only", nargs="+", metavar="NN", help="simulations to run, e.g. --only 03 04")
    args = ap.parse_args()
    names = {s[:2]: s for s in SIMS}
    if not args.no_run:
        if not os.path.exists(LTSPICE):
            sys.exit(f"LTspice not found at {LTSPICE}")
        for n in args.only or names:
            run(names[n])
    fft = None
    for fn, src in FIGS:
        missing = [names[n] for n in src if not os.path.exists(os.path.join(HERE, names[n] + ".raw"))]
        if missing:
            print(f"  {fn.__name__} skipped: no .raw for {', '.join(missing)}")
            continue
        rows = fn()
        if fn is fig_fft:
            fft = rows
    with open(os.path.join(HERE, "results.md"), "w", encoding="utf-8") as f:
        f.write("# LTspice .meas results (generated by run_simulations.py)\n\n")
        for s in SIMS:
            if not os.path.exists(os.path.join(HERE, s + ".log")):
                continue
            f.write(f"## {s}\n\n| Measure | Result |\n| --- | --- |\n")
            for k, v in meas(s).items():
                f.write(f"| `{k}` | `{v}` |\n")
            f.write("\n")
        if fft:
            f.write("## FFT of the steady-state rails (computed by run_simulations.py)\n\n"
                    "Bridge powered: 03_Power_Ripple, 2 to 6 ms. Standby: last 10 ms of 01_Power_Chain_Startup.\n\n"
                    "| Quantity | Result |\n| --- | --- |\n")
            for k, v in fft:
                f.write(f"| {k} | {v} |\n")
            f.write("\n")
    print("  results.md written")


if __name__ == "__main__":
    main()
