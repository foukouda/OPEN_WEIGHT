"""Figures of the openEMS switch-node coupling study, written to ../../Images/Simulation/.

    C:\\openEMS\\venv\\Scripts\\python.exe plot_results.py

Reads run/<case>/results.json and the E-field dumps left by the sw drive of sw_coupling.py.
measurement_quality.py draws what the three drives mean for the AD7190.
"""
import json
import os

import h5py
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, "run")
FIG_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "Images", "Simulation"))
F_FIT = (30e6, 200e6)
SHIELD_HALF, SHIELD_HEIGHT = 10.2, 3.0
CASES = {"open": "Bare board", "frame": "Shield frame H5, no cover", "shield": "Shield H5 with its cover"}
FILL = {"open": 0.0, "frame": 0.45, "shield": 1.0}     # marker fill: the more shielding, the fuller

# reference palette (light), fixed categorical order - same as Simulation/LTspice/run_simulations.py
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUES = LinearSegmentedColormap.from_list("blues", [SURFACE, "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
                                                    "#256abf", "#184f95", "#0d366b"])
GROUPS = [("IN-OUT", "Connector side (J2/J4 to the 100 Ω)", C1),
          ("OUT", "ADC side (100 Ω to the AD7190)", C2),
          ("SENSE", "Excitation / reference (SENSE±)", C3)]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
})


def save(fig, fname):
    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(os.path.join(FIG_DIR, fname), dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  figure: Images/Simulation/{fname}")


def load(drive="sw"):
    """Results of one drive (sw, loop or coil) for every case that has been simulated."""
    res = {}
    for case in CASES:
        path = os.path.join(RUN, case + ("" if drive == "sw" else "_" + drive), "results.json")
        if os.path.exists(path):
            with open(path) as f:
                r = json.load(f)
            if "unit" in r:
                res[case] = r
            else:
                print(f"  {path}: written by an older sw_coupling.py, run it again")
    return res


def group_of(net):
    return next(g for g in GROUPS if net.startswith(g[0]))


def tint(col, amount):
    """Mix the surface colour towards col (0 = surface, 1 = col)."""
    a, b = matplotlib.colors.to_rgb(SURFACE), matplotlib.colors.to_rgb(col)
    return tuple(x + (y - x) * amount for x, y in zip(a, b))


def plot_coupling(res):
    first = next(iter(res.values()))
    order = sorted(range(len(first["victims"])), key=lambda i: [g[0] for g in GROUPS].index(group_of(first["victims"][i]["net"])[0]))
    fig = plt.figure(figsize=(12.5, 6.4))
    grid = fig.add_gridspec(len(res), 2, width_ratios=[1.35, 1], wspace=0.22, hspace=0.3)

    # mutual capacitance per net: one row per net, one marker per shielding case
    # A net whose response is not capacitive sits in the solver noise: it is drawn as an upper bound.
    a = fig.add_subplot(grid[:, 0])
    shown = []
    for row, i in enumerate(order):
        col = group_of(first["victims"][i]["net"])[2]
        pts = [(c, res[c]["victims"][i]) for c in res]
        vals = [abs(v["k"]) if v["resolved"] else v["bound"] for _, v in pts]
        shown += vals
        a.plot([min(vals), max(vals)], [row, row], color=GRID, lw=2, zorder=1, solid_capstyle="round")
        for (c, v), x in zip(pts, vals):
            a.plot(x, row, "o" if v["resolved"] else "<", ms=9, mew=2, mec=col, mfc=tint(col, FILL[c]), zorder=3)
    a.set_yticks(range(len(order)))
    a.set_yticklabels([" ".join(first["victims"][i]["label"].replace(">", "→").split()) for i in order], color=INK)
    a.invert_yaxis()
    a.set_xscale("log")
    a.set_xlim(10 ** np.floor(np.log10(min(shown)) - 0.15), 10 ** np.ceil(np.log10(max(shown)) + 0.15))
    a.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    a.xaxis.set_minor_formatter(NullFormatter())
    a.grid(axis="y", visible=False)
    a.set_xlabel("Mutual capacitance to the switch node (fF)")
    a.set_title("Switch node → analog nets, from the routed copper", loc="left")
    handles = [Line2D([], [], marker="o", ls="", ms=9, mew=2, mec=INK2, mfc=tint(INK2, FILL[c]), label=CASES[c]) for c in res]
    handles += [Line2D([], [], marker="<", ls="", ms=9, mew=2, mec=INK2, mfc=SURFACE, label="in the solver noise: upper bound")]
    handles += [Line2D([], [], marker="s", ls="", ms=8, mew=0, color=g[2], label=g[1]) for g in GROUPS]
    a.legend(handles=handles, loc="upper left", bbox_to_anchor=(-0.02, -0.11), ncol=2, handletextpad=0.3, columnspacing=1.5)

    # transfer functions: the 20 dB/decade slope is what makes the capacitance reading valid
    axes = []
    for k, case in enumerate(res):
        b = fig.add_subplot(grid[k, 1], sharex=axes[0] if axes else None, sharey=axes[0] if axes else None)
        axes.append(b)
        f = np.array(res[case]["f"])
        b.axvspan(*[v / 1e6 for v in F_FIT], color=GRID, alpha=0.5, lw=0)
        for v in res[case]["victims"]:
            b.plot(f / 1e6, 20 * np.log10(v["h_abs"]), color=group_of(v["net"])[2], lw=1.2)
        b.set_xscale("log")
        b.set_xlim(10, 500)
        b.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
        b.set_title(CASES[case], loc="left", fontsize=10)
        b.tick_params(labelbottom=k == len(res) - 1)
    axes[-1].set_xlabel("Frequency (MHz)")
    axes[len(axes) // 2].set_ylabel("V(net) / V(switch node), net loaded by 50 Ω (dB)")
    lo, hi = axes[0].get_ylim()
    axes[0].text(np.sqrt(F_FIT[0] * F_FIT[1]) / 1e6, lo + 0.04 * (hi - lo), "fit band", color=INK2, fontsize=8, ha="center")
    fr = np.array([12.0, 60.0])
    y0 = hi - 0.1 * (hi - lo) - 20 * np.log10(fr[1] / fr[0])
    axes[0].plot(fr, y0 + 20 * np.log10(fr / fr[0]), color=INK2, lw=1, ls="--")
    axes[0].text(fr[0] * 1.15, y0 + 20 * np.log10(fr[1] / fr[0]), "20 dB/decade = capacitive", color=INK2, fontsize=8, va="bottom")
    save(fig, "openems_sw_coupling.png")


def field(case, name):
    """|E| of a frequency-domain dump, as (x, y, z in mm, magnitude[z, y, x])."""
    with h5py.File(os.path.join(RUN, case, name + ".h5"), "r") as f:
        e = f["FieldData/FD/f0_real"][...] + 1j * f["FieldData/FD/f0_imag"][...]
        mesh = [f["Mesh"][a][...] * 1e3 for a in "xyz"]
    return mesh, np.sqrt((np.abs(e) ** 2).sum(0))


def plot_efield(res, geom, span=100):
    cases = list(res)
    tops = {c: field(c, "E_top") for c in cases}
    cuts = {c: field(c, "E_cut") for c in cases}
    ref = max(m[0].max() / res[c]["v_sw_fdump"] for c, (_, m) in tops.items())      # per volt on the switch node
    db = lambda m, c: 20 * np.log10(np.maximum(m / res[c]["v_sw_fdump"] / ref, 1e-12))
    w, h = geom["size_mm"]
    z_top = geom["layers"][0]["z"]
    outline = [(net, o) for net in geom["nets"] if net == "Net-(D3-A)" or net.startswith(("IN-OUT", "OUT", "SENSE"))
               for o in geom["nets"][net][0]]

    fig, axs = plt.subplots(2, len(cases), figsize=(5.2 * len(cases), 6.9), squeeze=False,
                            gridspec_kw={"height_ratios": [4.3, 1], "hspace": 0.16, "wspace": 0.08})
    for k, c in enumerate(cases):
        (x, y, _), m = tops[c]
        a = axs[0, k]
        im = a.pcolormesh(x, y, db(m[0], c), cmap=BLUES, vmin=-span, vmax=0, shading="nearest", rasterized=True)
        a.plot([-w / 2, w / 2, w / 2, -w / 2, -w / 2], [-h / 2, -h / 2, h / 2, h / 2, -h / 2], color=INK2, lw=0.8)
        for _, o in outline:
            p = np.array(o + o[:1])
            a.plot(p[:, 0], p[:, 1], color=INK, lw=0.35, alpha=0.6)
        if c != "open":
            s = SHIELD_HALF
            a.plot([-s, s, s, -s, -s], [-s, -s, s, s, -s], color=INK, lw=1.4)
            a.text(0, -s - 0.6, "shield H5", ha="center", va="top", fontsize=9)
        a.annotate("switch node", (-20.5, -12.0), xytext=(-25.5, -21.5), fontsize=9, arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
        a.text(-10.5, 20.0, "J2 (channel 2)", ha="center", fontsize=9)
        a.text(10.5, 20.0, "J4 (channel 1)", ha="center", fontsize=9)
        a.set_aspect("equal")
        a.set_xlim(-w / 2 - 2, w / 2 + 2); a.set_ylim(-h / 2 - 2, h / 2 + 2)
        a.grid(False)
        a.set_title(CASES[c], loc="left")
        a.set_xlabel("x (mm)")
        if k == 0:
            a.set_ylabel("y (mm)")
        else:
            a.tick_params(labelleft=False)

        (x, y, z), m = cuts[c]
        b = axs[1, k]
        b.pcolormesh(x, z - z_top, db(m[:, 0, :], c), cmap=BLUES, vmin=-span, vmax=0, shading="nearest", rasterized=True)
        b.plot([-w / 2, w / 2, w / 2, -w / 2, -w / 2], [-z_top, -z_top, 0, 0, -z_top], color=INK2, lw=0.8)
        s = SHIELD_HALF
        if c == "shield":
            b.plot([-s, -s, s, s], [0.1, SHIELD_HEIGHT, SHIELD_HEIGHT, 0.1], color=INK, lw=1.4)
        elif c == "frame":
            b.plot([-s, -s], [0.1, SHIELD_HEIGHT], color=INK, lw=1.4)
            b.plot([s, s], [0.1, SHIELD_HEIGHT], color=INK, lw=1.4)
        b.set_aspect("equal")
        b.set_xlim(-w / 2 - 2, w / 2 + 2); b.set_ylim(z.min() - z_top, z.max() - z_top)
        b.grid(False)
        b.set_xlabel("x (mm)")
        if k == 0:
            b.set_ylabel("height (mm)")
        else:
            b.tick_params(labelleft=False)
    bar = fig.colorbar(im, ax=axs, orientation="vertical", fraction=0.025, pad=0.02)
    bar.set_label("E-field, dB below the strongest point")
    bar.outline.set_visible(False)
    fig.suptitle("Electric field of the TPS61086 switch node at 100 MHz, same drive voltage in every case",
                 x=0.125, ha="left", fontweight="bold", y=0.955)
    fig.text(0.125, 0.915, "Top: 0.05 mm above the top copper, with the analog nets outlined.  "
             "Bottom: vertical cut through the switch node (y = %.1f mm)." % cuts[cases[0]][0][1][0], color=INK2, fontsize=9)
    save(fig, "openems_sw_efield.png")


def main():
    res = load()
    if not res:
        raise SystemExit("no results in run/, run sw_coupling.py first")
    with open(os.path.join(HERE, "geometry.json"), encoding="utf-8") as f:
        geom = json.load(f)
    plot_coupling(res)
    plot_efield(res, geom)


if __name__ == "__main__":
    main()
