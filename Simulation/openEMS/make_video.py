"""Video of the switch-node test pulse spreading over the board (needs ffmpeg on the PATH).

    C:\\openEMS\\venv\\Scripts\\python.exe sw_coupling.py --movie --case open
    C:\\openEMS\\venv\\Scripts\\python.exe sw_coupling.py --movie --case shield
    C:\\openEMS\\venv\\Scripts\\python.exe make_video.py

Reads the time-domain E-field stored in run/<case>_movie and writes
../../Images/Simulation/openems_sw_efield.mp4: field strength just above the top copper and in a
vertical cut through the switch node, with the drive voltage underneath.
"""
import json
import os

import h5py
import numpy as np

# plot_results also selects the Agg backend and sets the common plot style
from plot_results import BLUES, C2, CASES, FIG_DIR, HERE, INK, INK2, RUN, SHIELD_HALF, SHIELD_HEIGHT

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402

SPAN = 100            # colour range, dB below the strongest field of the whole run
T_WINDOW = (1.5, 11.5)  # ns shown: the pulse, without the idle time before and after
FPS = 25
PIXEL = 0.2           # mm, the fields are resampled on a regular grid for display


def load(case, name):
    """|E| over time of a dump: (x, y, z in mm), t in ns, magnitude[t, z, y, x]."""
    with h5py.File(os.path.join(RUN, case + "_movie", name + ".h5"), "r") as f:
        mesh = [f["Mesh"][a][...] * 1e3 for a in "xyz"]
        td = f["FieldData/TD"]
        keys = sorted(td)
        t = np.array([td[k].attrs["time"][0] for k in keys]) * 1e9
        mag = np.stack([np.sqrt((td[k][...] ** 2).sum(0)) for k in keys])
    return mesh, t, mag


def regular(axis, step=PIXEL):
    """Extent of a non-uniform axis and the indices that resample it on a regular grid."""
    u = np.arange(axis[0], axis[-1] + step / 2, step)
    return (axis[0] - step / 2, u[-1] + step / 2), np.abs(axis[None, :] - u[:, None]).argmin(1)


def main():
    cases = [c for c in ("open", "shield") if os.path.exists(os.path.join(RUN, c + "_movie", "Et_top.h5"))]
    if not cases:
        raise SystemExit("no run/<case>_movie data, run sw_coupling.py --movie first")
    with open(os.path.join(HERE, "geometry.json"), encoding="utf-8") as f:
        geom = json.load(f)
    w, h = geom["size_mm"]
    z_top = geom["layers"][0]["z"]
    outline = [o for net in geom["nets"] if net == "Net-(D3-A)" or net.startswith(("IN-OUT", "OUT", "SENSE"))
               for o in geom["nets"][net][0]]

    tops = {c: load(c, "Et_top") for c in cases}
    cuts = {c: load(c, "Et_cut") for c in cases}
    ref = max(m.max() for _, _, m in tops.values())
    db = lambda m: 20 * np.log10(np.maximum(m / ref, 1e-9))
    drive = np.loadtxt(os.path.join(RUN, cases[0] + "_movie", "port_ut_1"), comments="%")
    t_drive, v_drive = drive[:, 0] * 1e9, drive[:, 1] / np.abs(drive[:, 1]).max()
    t = tops[cases[0]][1]
    frames = np.flatnonzero((t >= T_WINDOW[0]) & (t <= T_WINDOW[1]))

    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    # the cut is 12.5 mm high against 52 mm for the map: with these ratios both keep the same x scale
    grid = fig.add_gridspec(3, len(cases) + 1, width_ratios=[1] * len(cases) + [0.035], height_ratios=[4.6, 1.1, 0.8],
                            left=0.06, right=0.93, top=0.86, bottom=0.08, hspace=0.32, wspace=0.08)
    images = []
    for k, c in enumerate(cases):
        (x, y, _), _, m = tops[c]
        (ex, ix), (ey, iy) = regular(x), regular(y)
        a = fig.add_subplot(grid[0, k])
        im = a.imshow(db(m[0, 0])[np.ix_(iy, ix)], cmap=BLUES, vmin=-SPAN, vmax=0, origin="lower", extent=ex + ey,
                      interpolation="bilinear")
        images.append((im, m[:, 0], (iy, ix)))
        a.plot([-w / 2, w / 2, w / 2, -w / 2, -w / 2], [-h / 2, -h / 2, h / 2, h / 2, -h / 2], color=INK2, lw=0.8)
        for o in outline:
            p = np.array(o + o[:1])
            a.plot(p[:, 0], p[:, 1], color=INK, lw=0.35, alpha=0.6)
        if c == "shield":
            s = SHIELD_HALF
            a.plot([-s, s, s, -s, -s], [-s, -s, s, s, -s], color=INK, lw=1.4)
            a.text(0, -s - 0.6, "shield H5", ha="center", va="top", fontsize=9)
        a.annotate("switch node", (-20.5, -12.0), xytext=(-25.5, -21.5), fontsize=9, arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
        a.text(-10.5, 20.0, "J2 (channel 2)", ha="center", fontsize=9)
        a.text(10.5, 20.0, "J4 (channel 1)", ha="center", fontsize=9)
        a.set_xlim(-w / 2 - 2, w / 2 + 2); a.set_ylim(-h / 2 - 2, h / 2 + 2)
        a.set_aspect("equal"); a.grid(False)
        a.set_title(CASES[c], loc="left")
        a.tick_params(labelbottom=False, labelleft=k == 0)
        if k == 0:
            a.set_ylabel("y (mm)")

        (x, _, z), _, m = cuts[c]
        (ex, ix), (ez, iz) = regular(x), regular(z - z_top, PIXEL / 2)
        b = fig.add_subplot(grid[1, k])
        im = b.imshow(db(m[0, :, 0])[np.ix_(iz, ix)], cmap=BLUES, vmin=-SPAN, vmax=0, origin="lower", extent=ex + ez,
                      interpolation="bilinear")
        images.append((im, m[:, :, 0], (iz, ix)))
        b.plot([-w / 2, w / 2, w / 2, -w / 2, -w / 2], [-z_top, -z_top, 0, 0, -z_top], color=INK2, lw=0.8)
        if c == "shield":
            s = SHIELD_HALF
            b.plot([-s, -s, s, s], [0.1, SHIELD_HEIGHT, SHIELD_HEIGHT, 0.1], color=INK, lw=1.4)
        b.set_xlim(-w / 2 - 2, w / 2 + 2); b.set_ylim(-3 - z_top, 8)
        b.set_aspect("equal"); b.grid(False)
        b.set_xlabel("x (mm)")
        b.tick_params(labelleft=k == 0)
        if k == 0:
            b.set_ylabel("height (mm)")

    bar = fig.colorbar(images[0][0], cax=fig.add_subplot(grid[:2, -1]))
    bar.set_label("E-field, dB below the strongest value of the run")
    bar.outline.set_visible(False)

    v = fig.add_subplot(grid[2, :len(cases)])
    v.plot(t_drive, v_drive, color=INK2, lw=1.5)
    cursor = v.axvline(t[frames[0]], color=C2, lw=2)
    v.set_xlim(*T_WINDOW); v.set_ylim(-1.15, 1.15)
    v.set_yticks([]); v.grid(axis="y", visible=False)
    v.spines["left"].set_visible(False)
    v.set_xlabel("time (ns)")
    v.text(0.995, 0.92, "voltage on the switch node (test pulse, 0-500 MHz)", transform=v.transAxes, color=INK2, fontsize=9,
           va="top", ha="right")

    fig.text(0.06, 0.95, "Electric field of the TPS61086 switch node, simulated on the routed copper", fontsize=13, fontweight="bold")
    fig.text(0.06, 0.915, "Top: 0.05 mm above the top copper, analog nets outlined.  Middle: vertical cut through the switch node.  "
             "1 s of video = %.2g ns." % (FPS * (t[1] - t[0])), color=INK2, fontsize=9)
    clock = fig.text(0.93, 0.95, "", fontsize=13, fontweight="bold", ha="right")

    os.makedirs(FIG_DIR, exist_ok=True)
    out = os.path.join(FIG_DIR, "openems_sw_efield.mp4")
    writer = FFMpegWriter(fps=FPS, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-crf", "18"])
    with writer.saving(fig, out, dpi=100):
        for n in frames:
            for im, m, idx in images:
                im.set_data(db(m[n])[np.ix_(*idx)])
            cursor.set_xdata([t[n], t[n]])
            clock.set_text("t = %.2f ns" % t[n])
            writer.grab_frame()
    plt.close(fig)
    print("  video: Images/Simulation/openems_sw_efield.mp4 (%d frames, %.1f s, %.1f MB)" % (
        len(frames), len(frames) / FPS, os.path.getsize(out) / 1e6))


if __name__ == "__main__":
    main()
