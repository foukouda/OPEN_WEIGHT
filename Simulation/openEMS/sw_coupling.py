"""Coupling from the TPS61086 boost stage to the AD7190 analog nets, on the real layout.

The copper of the four layers (geometry.json, written by export_kicad_geometry.py) is meshed in
openEMS and one source of the boost stage is driven at a time:

    sw    the switch node voltage, against the L2 ground plane at IC2. Every analog net is tied to
          ground through a 50 ohm probe port; with the victim held near ground the port current is
          jw.Cm.Vsw, which gives the mutual capacitance Cm between the switch node and that net.
    loop  the current of the commutation loop IC2 - D3 - C19/C20, the diode and the +6V capacitors
          being fitted as wires. The analog nets are closed where they really are: the connector
          tracks at the load cell end, the two legs of each input by their filter capacitors. Probe
          ports read what is induced along the connector tracks, around the two filter capacitors
          to ground and between the two pins of the ADC: jw.M.I, which gives the mutual inductance
          M to the driven loop.
    input the same for the input loop C21/C22 - L1 - IC2, which carries the inductor current. L1 is
          a wire from one pad to the other at mid height: its path through the part, not its winding.
    coil  the same for a current loop of the size of L1, at its place: the stray field of the inductor.

Three cases are compared: bare board, WE-SHC frame H5 alone, frame fitted with its cover.
measurement_quality.py then turns Cm and M into a voltage at the AD7190 inputs.

The board has 0.15-0.2 mm clearances, too tight for a 0.2 mm FDTD mesh to keep nets apart on its
own. The script therefore decides itself which mesh edges are metal (class Raster), gives way to
the tracks where two nets would touch, checks that every net of interest is still in one piece
and isolated, and hands openEMS exactly that set of edges.

Run with the Python that has the openEMS wheels:
    C:\\openEMS\\venv\\Scripts\\python.exe sw_coupling.py        (12 runs, about 13 min each on 8 cores)
    ... --drive loop   one source only: sw, loop, input or coil
    ... --case shield  one case only: open, frame or shield
    ... --check        only mesh the board and verify the nets
    ... --view         open the copper model in AppCSXCAD instead of simulating
    ... --post-only    recompute the results from the existing run/ data
    ... --res 0.15     another mesh step, in run/<case>_0.15mm (convergence check)
    ... --movie        also store the field over time (run/<case>_movie), then run make_video.py

Not modelled: the connectors J2/J4 and their pins above the board, the load cell and its cable,
solder mask, copper thickness. L1 is a bare current loop: how much of its field really leaks out of
the shielded part is not known, measurement_quality.py bounds it. The supply rails are ideal AC
grounds, so the resonances of the real decoupling network are left out.
"""
import argparse
import json
import os
import re
import sys
import time

import numpy as np
from matplotlib.path import Path
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

HERE = os.path.dirname(os.path.abspath(__file__))
GEOM = os.path.join(HERE, 'geometry.json')
RUN = os.path.join(HERE, 'run')

C0, EPS0 = 299792458.0, 8.8541878128e-12

# excitation: gaussian pulse covering 0..500 MHz, then time for the ports to settle. The model has
# almost no loss, so any resonance inside the band would ring for far longer than the run.
F0 = FC = 250e6
T_SETTLE = 3e-9
R_PORT = 50.0
F_FIT = (30e6, 200e6)        # band where the coupling is quasi-static (20 dB/decade)
R2_MIN = 0.9                 # fit quality below which a net is reported as an upper bound only
F_DUMP = 100e6               # frequency of the E-field maps
# The solver works in single precision and its rounding noise is broadband. Stored every 880 timesteps
# (the default) that noise folds back into the band and hides anything below -140 dB; stored every 3
# timesteps it stays where it is, and the weak nets come out 20 to 30 dB cleaner.
OVERSAMPLING = 1000
MOVIE_OVERSAMPLING = 20      # --movie: one field frame every 1 / (2 (F0 + FC) x this) = 0.05 ns

# mesh: RES inside the window holding the boost stage and the analog front end, coarser elsewhere
RES = 0.2
FINE_X, FINE_Y = (-24.0, 14.0), (-16.6, 18.6)
AIR = 15.0

GND, SW_NET = 'GND', 'Net-(D3-A)'
SOURCE = ('IC2', '6')        # SW pin of the TPS61086
RAILS = ('+5VA', '+3.3V', '+6V')   # taken as ideally decoupled, see plan()
DECOUPLING_PITCH = 2.0             # mm
DRIVES = ('sw', 'loop', 'input', 'coil')     # switch node voltage, commutation loop, input loop, stray field of L1
# fitted as wires: the diode and the +6V capacitors for the loop drive, L1 and the +3.3V capacitors for the input drive
LOOPS = {'loop': ('D3', 'C19', 'C20', 'C16'), 'input': ('L1', 'C21', 'C22', 'C1', 'C2')}
PART_HEIGHT = 0.4                        # where the current runs in a fitted part: half the height of an 0603, mm
L1_BODY = (6.2, 5.9, 3.3)                # WE-PD 6033 (7447785004): length along the pads, width, height, mm
# label, net, pad carrying the probe port for the sw drive, then for the magnetic drives, and what
# closes the net to ground in the magnetic drives: a part fitted as a wire, or a pad tied to the plane.
# There the ADC side is probed at the pin, past its filter: what the AD7190 sees unfiltered.
VICTIMS = [
    ('CH1 IN+  J4 > R4', 'IN-OUT+', ('R4', '1'), ('R4', '1'), [('J4', '1')]),
    ('CH1 IN-  J4 > R5', 'IN-OUT-', ('R5', '1'), ('R5', '1'), [('J4', '2')]),
    ('CH1 AIN2 R4 > U1', 'OUT+', ('R4', '2'), ('U1', '12'), []),
    ('CH1 AIN1 R5 > U1', 'OUT-', ('R5', '2'), ('U1', '11'), []),
    ('CH2 IN+  J2 > R2', 'IN-OUT+2', ('R2', '1'), ('R2', '1'), [('J2', '1')]),
    ('CH2 IN-  J2 > R1', 'IN-OUT-2', ('R1', '1'), ('R1', '1'), [('J2', '2')]),
    ('CH2 AIN4 R2 > U1', 'OUT-2', ('R2', '2'), ('U1', '14'), []),
    ('CH2 AIN3 R1 > U1', 'OUT+2', ('R1', '2'), ('U1', '13'), []),
    ('SENSE+ (REFIN+)', 'SENSE+', ('U1', '15'), ('U1', '15'), ['C7', 'C11', 'C23']),
    ('SENSE- (REFIN-)', 'SENSE-', ('U1', '16'), ('U1', '16'), ['C9']),
]
# What the AD7190 converts: the two legs of each input, as (net on the connector side, net at the pin)
INPUTS = {
    'CH1': (('IN-OUT+', 'OUT+'), ('IN-OUT-', 'OUT-')),          # J4 -> AIN2, AIN1
    'CH2': (('IN-OUT-2', 'OUT+2'), ('IN-OUT+2', 'OUT-2')),      # J2 -> AIN3, AIN4
    'REF': ((None, 'SENSE+'), (None, 'SENSE-')),                # REFIN1(+), REFIN1(-)
}
# The input filter in the magnetic drives: the capacitor across the pair, fitted as a wire, and the
# capacitor to ground of each leg, a wire too but with a probe port in it. The two legs, their
# capacitors and the plane make a loop: what is induced there divides onto the capacitor across.
FILTERS = {'CH1': ('C28', 'C27', 'C29'), 'CH2': ('C6', 'C10', 'C8')}
KEY_NETS = [GND, SW_NET] + list(RAILS) + [v[1] for v in VICTIMS]
CASES = ('open', 'frame', 'shield')      # bare board, WE-SHC frame H5 alone, frame with its cover
SHIELD_HALF, SHIELD_HEIGHT = 10.2, 3.0   # WE-SHC 36503205 frame, from its STEP model


def load_geometry():
    with open(GEOM, encoding='utf-8') as f:
        return json.load(f)


# ----------------------------------------------------------------------------- mesh

def build_mesh(geom):
    def axis(fine, half_board):
        lines = list(np.arange(int(round(fine[0] / RES)), int(round(fine[1] / RES)) + 1) * RES)
        for sign in (-1, 1):
            x, d = (lines[0] if sign < 0 else lines[-1]), RES
            while abs(x) < half_board + AIR:
                d = min(d * 1.3, 0.8 if abs(x) < half_board else 3.0)
                x += sign * d
                lines.insert(0, x) if sign < 0 else lines.append(x)
        return np.array(lines)

    w, h = geom['size_mm']
    zl = [l['z'] for l in geom['layers']]            # L1 (top) .. L4 (bottom, z = 0)
    core = zl[2] + (zl[1] - zl[2]) * np.cumsum([0.6, 1, 1, 1])[:4] / 4.2
    below = -np.array([0.12, 0.28, 0.5, 0.8, 1.2, 1.75, 2.5, 3.5, 4.9, 6.8, 9.3, 12.3])
    above = zl[0] + np.array([0.1, 0.24, 0.42, 0.66, 0.96, 1.34, 1.8, 2.36, SHIELD_HEIGHT,
                              3.8, 4.8, 6.1, 7.8, 10.0, 12.5, 15.5])
    z = np.concatenate([below[::-1], [zl[3], zl[2] / 2, zl[2]], core, [zl[1], (zl[1] + zl[0]) / 2, zl[0]], above])
    return {'x': axis(FINE_X, w / 2), 'y': axis(FINE_Y, h / 2), 'z': z, 'zl': zl}


def snap(lines, v):
    return int(np.argmin(np.abs(lines - v)))


# ----------------------------------------------------------------------------- copper -> mesh edges

class Raster:
    """Decides which in-plane mesh edges are metal, and for which net.

    own_x[layer, i, j] is the net of the edge from node (i, j) to (i+1, j), own_y the same towards
    (i, j+1); -1 means no metal. An edge is metal when its midpoint lies in the copper (the rule
    openEMS applies to polygons), plus a staircase along every track centre line so that thin
    tracks cannot break. Where edges of two nets meet at a node, or a via barrel runs through
    another net, the lower-ranked net loses its edges there.
    """

    def __init__(self, geom, mesh):
        self.x, self.y = mesh['x'], mesh['y']
        self.nx, self.ny = len(self.x), len(self.y)
        self.names = list(geom['nets'])
        victims = [v[1] for v in VICTIMS]
        self.rank = np.array([3 if n in victims or n == SW_NET else 2 if n in RAILS else 0 if n == GND else 1
                              for n in self.names])
        self.own_x = -np.ones((4, self.nx - 1, self.ny), int)
        self.own_y = -np.ones((4, self.nx, self.ny - 1), int)
        self._polygons(geom)
        self._tracks(geom)
        self.barrels = [(snap(self.x, b['xy'][0]), snap(self.y, b['xy'][1])) for b in geom['barrels']]
        self.barrel_net = [self.names.index(b['net']) for b in geom['barrels']]
        self.removed = self._resolve()
        self._components()

    def _polygons(self, geom):
        xm, ym = (self.x[:-1] + self.x[1:]) / 2, (self.y[:-1] + self.y[1:]) / 2
        for n, name in enumerate(self.names):
            for l, outlines in enumerate(geom['nets'][name]):
                for o in outlines:
                    p = np.asarray(o)
                    path = Path(np.vstack([p, p[:1]]), closed=True)
                    lo, hi = p.min(0), p.max(0)
                    for own, gx, gy in ((self.own_x[l], xm, self.y), (self.own_y[l], self.x, ym)):
                        i0, i1 = np.searchsorted(gx, [lo[0], hi[0]])
                        j0, j1 = np.searchsorted(gy, [lo[1], hi[1]])
                        if i1 <= i0 or j1 <= j0:
                            continue
                        X, Y = np.meshgrid(gx[i0:i1], gy[j0:j1], indexing='ij')
                        inside = path.contains_points(np.c_[X.ravel(), Y.ravel()]).reshape(X.shape)
                        own[i0:i1, j0:j1][inside] = n

    def _tracks(self, geom):
        for t in geom['tracks']:
            n, l = self.names.index(t['net']), t['layer']
            nodes = [(snap(self.x, p[0]), snap(self.y, p[1])) for p in t['pts']]
            for (i, j), (i1, j1) in zip(nodes[:-1], nodes[1:]):
                di, dj, si, sj = abs(i1 - i), abs(j1 - j), np.sign(i1 - i), np.sign(j1 - j)
                cx = cy = 0
                while cx < di or cy < dj:
                    if cy >= dj or (cx < di and (cx + 0.5) * dj <= (cy + 0.5) * di):
                        self.own_x[l, min(i, i + si), j] = n
                        i += si; cx += 1
                    else:
                        self.own_y[l, i, min(j, j + sj)] = n
                        j += sj; cy += 1

    def _around(self, l, ix, iy):
        """The (array, index) of the up to four edges meeting at a node."""
        e = []
        if ix > 0: e.append((self.own_x, (l, ix - 1, iy)))
        if ix < self.nx - 1: e.append((self.own_x, (l, ix, iy)))
        if iy > 0: e.append((self.own_y, (l, ix, iy - 1)))
        if iy < self.ny - 1: e.append((self.own_y, (l, ix, iy)))
        return e

    def _resolve(self):
        size = np.bincount(np.concatenate([self.own_x.ravel(), self.own_y.ravel()]) + 1, minlength=len(self.names) + 1)[1:]
        removed = 0
        for (ix, iy), n in zip(self.barrels, self.barrel_net):      # a barrel keeps other nets away
            for l in range(4):
                for arr, k in self._around(l, ix, iy):
                    if arr[k] not in (-1, n):
                        arr[k] = -1; removed += 1
        for l in range(4):
            stack = -np.ones((4, self.nx, self.ny), int)
            stack[0, 1:, :] = self.own_x[l]; stack[1, :-1, :] = self.own_x[l]
            stack[2, :, 1:] = self.own_y[l]; stack[3, :, :-1] = self.own_y[l]
            hi = stack.max(0)
            lo = np.where(stack >= 0, stack, len(self.names)).min(0)
            for ix, iy in zip(*np.nonzero((hi >= 0) & (lo != hi))):
                edges = self._around(l, ix, iy)
                nets = {int(arr[k]) for arr, k in edges if arr[k] >= 0}
                if len(nets) < 2:
                    continue                                         # already settled from a neighbour
                keep = max(nets, key=lambda n: (self.rank[n], -size[n]))   # thin, important nets win
                for arr, k in edges:
                    if arr[k] not in (-1, keep):
                        arr[k] = -1; removed += 1
        return removed

    def _components(self):
        idx = np.arange(4 * self.nx * self.ny).reshape(4, self.nx, self.ny)
        a, b = [], []
        for l in range(4):
            m = self.own_x[l] >= 0
            a.append(idx[l, :-1, :][m]); b.append(idx[l, 1:, :][m])
            m = self.own_y[l] >= 0
            a.append(idx[l, :, :-1][m]); b.append(idx[l, :, 1:][m])
        for ix, iy in self.barrels:
            a.append(idx[:3, ix, iy]); b.append(idx[1:, ix, iy])
        a, b = np.concatenate(a), np.concatenate(b)
        graph = coo_matrix((np.ones(len(a), bool), (a, b)), shape=(idx.size, idx.size))
        self.labels = connected_components(graph, directed=False)[1].reshape(idx.shape)

    def components_of(self, net):
        """Connected pieces of a net: list of (label, number of edges), largest first."""
        n = self.names.index(net)
        lab = np.concatenate([np.concatenate([self.labels[l, :-1, :][self.own_x[l] == n],
                                              self.labels[l, :, :-1][self.own_y[l] == n]]) for l in range(4)])
        u, c = np.unique(lab, return_counts=True)
        return sorted(zip(u.tolist(), c.tolist()), key=lambda t: -t[1])

    def shorts(self):
        """Groups of different nets that ended up as one conductor."""
        by_label = {}
        for name in self.names:
            for lab, _ in self.components_of(name):
                by_label.setdefault(lab, set()).add(name)
        return [sorted(s) for s in by_label.values() if len(s) > 1]

    def net_nodes(self, layer, net):
        """Nodes of a layer that belong to the main piece of this net."""
        n = self.names.index(net)
        m = np.zeros((self.nx, self.ny), bool)
        ox, oy = self.own_x[layer] == n, self.own_y[layer] == n
        m[:-1, :] |= ox; m[1:, :] |= ox; m[:, :-1] |= oy; m[:, 1:] |= oy
        return m & (self.labels[layer] == self.components_of(net)[0][0])

    def pick_node(self, xy, net, over_ground=False, max_dist=1.2):
        """Mesh node on L1 nearest to xy that belongs to the net (and sits over the L2 plane, off any via)."""
        ok = self.net_nodes(0, net)
        if over_ground:
            ok &= self.net_nodes(1, GND)
            for ix, iy in self.barrels:
                ok[ix, iy] = False
        ix, iy = np.nonzero(ok)
        d = np.hypot(self.x[ix] - xy[0], self.y[iy] - xy[1])
        k = int(np.argmin(d))
        if d[k] > max_dist:
            raise RuntimeError('no usable mesh node for net %s near %s' % (net, xy))
        return int(ix[k]), int(iy[k])


def edge_runs(raster, layer, net):
    """Metal edges of a net on a layer as straight runs [(x0, y0), (x1, y1)] in mm."""
    n, x, y, out = raster.names.index(net), raster.x, raster.y, []
    for j in range(raster.ny):                                   # runs along x on each y line
        row = np.flatnonzero(np.diff(np.r_[0, raster.own_x[layer][:, j] == n, 0].astype(np.int8)))
        out += [((x[a], y[j]), (x[b], y[j])) for a, b in zip(row[::2], row[1::2])]
    for i in range(raster.nx):                                   # runs along y on each x line
        col = np.flatnonzero(np.diff(np.r_[0, raster.own_y[layer][i, :] == n, 0].astype(np.int8)))
        out += [((x[i], y[a]), (x[i], y[b])) for a, b in zip(col[::2], col[1::2])]
    return out


def pad_xy(geom, ref, pad):
    return next(p for p in geom['pads'] if p['ref'] == ref and p['pad'] == pad)


def plan(geom, mesh, raster, drive):
    """Where the ports, the ground posts and the parts fitted as wires go, as mesh node indices."""
    def port(label, net, ref, pad):
        p = pad_xy(geom, ref, pad)
        assert p['net'] == net, '%s.%s is on %s, expected %s' % (ref, pad, p['net'], net)
        return {'label': label, 'net': net, 'node': raster.pick_node(p['xy'], net, over_ground=True)}

    def wire(ref):          # the two pads of a part, the grounded one first, and the height of the current in it
        a, b = sorted((p for p in geom['pads'] if p['ref'] == ref), key=lambda p: p['net'] != GND)
        return [raster.pick_node(p['xy'], p['net']) for p in (a, b)] + [L1_BODY[2] / 2 if ref == 'L1' else PART_HEIGHT]

    def facing(a, b):
        """Nodes of two neighbouring pads that face each other on a mesh line, with no copper in between."""
        def near(p):
            ix, iy = np.nonzero(raster.net_nodes(0, p['net']))
            d = np.hypot(mesh['x'][ix] - p['xy'][0], mesh['y'][iy] - p['xy'][1])
            return [(int(i), int(j), float(r)) for i, j, r in zip(ix, iy, d) if r < 0.6]

        found = []
        for ia, ja, da in near(a):
            for ib, jb, db in near(b):
                if ia == ib and ja != jb and (raster.own_y[0, ia, min(ja, jb):max(ja, jb)] < 0).all() or \
                        ja == jb and ia != ib and (raster.own_x[0, min(ia, ib):max(ia, ib), ja] < 0).all():
                    found.append((abs(ia - ib) + abs(ja - jb), da + db, (ia, ja), (ib, jb)))
        return min(found)[2:]

    magnetic = drive != 'sw'
    filtered = {leg[1]: name for name in FILTERS for leg in INPUTS[name]} if magnetic else {}
    source = port('SW node', SW_NET, *SOURCE)
    ports, holds, wires = [source], [], []
    rails = list(RAILS)
    if drive in LOOPS:      # the rail of that loop is grounded by its own capacitors, where they really are
        wires = [wire(ref) for ref in LOOPS[drive]]
        rails = [r for r in RAILS if r not in {p['net'] for p in geom['pads'] if p['ref'] in LOOPS[drive]}]
    elif drive == 'coil':   # a loop of the outline of L1 at mid height, the switch node being quiet
        cx, cy = next(p for p in geom['parts'] if p['ref'] == 'L1')['xy']
        i, j = [(snap(mesh[a], c - s / 2), snap(mesh[a], c + s / 2)) for a, c, s in (('x', cx, L1_BODY[0]), ('y', cy, L1_BODY[1]))]
        coil = {'i': i, 'j': j, 'k': snap(mesh['z'], mesh['zl'][0] + L1_BODY[2] / 2), 'gap': (i[0] + i[1]) // 2,
                'area_mm2': float(np.diff(mesh['x'][list(i)])[0] * np.diff(mesh['y'][list(j)])[0])}
        ports = [{'label': 'L1 stray field', 'coil': coil}]
        holds.append(source['node'])
    for label, net, pad_sw, pad_mag, closed_by in VICTIMS:
        if net not in filtered:
            ports.append(port(label, net, *(pad_mag if magnetic else pad_sw)))
        for c in closed_by if magnetic else ():
            if isinstance(c, str):
                wires.append(wire(c))
            else:           # a connector pin: the nearest point of its track that runs over the plane
                holds.append(raster.pick_node(pad_xy(geom, *c)['xy'], net, over_ground=True, max_dist=3.0))
    # Behind the filter the two pins are read against each other, straight from one pad to its neighbour,
    # as the converter does. Two ports to ground would add the loop that their own feet make with the plane.
    pin = {v[1]: pad_xy(geom, *v[3]) for v in VICTIMS}
    for name, (across, *legs) in FILTERS.items() if magnetic else ():
        wires.append(wire(across))
        ports.append({'label': '%s pins' % name, 'net': name + ' pin', 'between': facing(*[pin[leg[1]] for leg in INPUTS[name][::-1]])})
        ports += [{'label': '%s filter %s' % (name, ref), 'net': ref, 'cap': wire(ref)} for ref in legs]
    # Supply rails are AC ground: every DECOUPLING_PITCH they are tied to the ground copper right
    # below (L1 -> L2, L3 -> L4). Shorting only the real capacitors leaves the +5VA plane resonating
    # with their inductance near 350 MHz, which then rings on every net crossing the planes.
    step = max(1, int(round(DECOUPLING_PITCH / RES)))
    grid = np.zeros((raster.nx, raster.ny), bool)
    grid[::step, ::step] = True
    for ix, iy in raster.barrels:
        grid[ix, iy] = False
    posts = []
    for rail in rails:
        for upper, lower in ((0, 1), (2, 3)):
            ok = grid & raster.net_nodes(upper, rail) & raster.net_nodes(lower, GND)
            posts += [(int(ix), int(iy), upper, lower) for ix, iy in zip(*np.nonzero(ok))]
    nodes = [p['node'] for p in ports if 'node' in p]
    assert len(set(nodes)) == len(nodes) and not set(nodes) & set(holds), 'two ports, or a port and a ground post, share a node'
    return {'drive': drive, 'ports': ports, 'posts': posts, 'holds': holds, 'wires': wires, 'rails': rails}


def report_plan(mesh, raster, pl):
    print('%s drive:' % pl['drive'])
    for p in pl['ports']:
        if 'coil' in p:
            c = p['coil']
            print('  port %-18s loop of %.1f mm2 around (%.2f, %.2f), %.2f mm above the board' % (
                p['label'], c['area_mm2'], mesh['x'][list(c['i'])].mean(), mesh['y'][list(c['j'])].mean(),
                mesh['z'][c['k']] - mesh['zl'][0]))
        elif 'cap' in p or 'between' in p:
            print('  port %-18s %s (%.2f, %.2f) to (%.2f, %.2f)' % (
                p['label'], 'in the wire fitted from' if 'cap' in p else 'on the copper layer, from',
                *[v for ix, iy in (p.get('cap') or p['between'])[:2] for v in (mesh['x'][ix], mesh['y'][iy])]))
        else:
            ix, iy = p['node']
            print('  port %-18s on %-10s at (%.2f, %.2f)' % (p['label'], p['net'], mesh['x'][ix], mesh['y'][iy]))
    print('  %d posts tie the rails to ground (%s)' % (len(pl['posts']), ', '.join(
        '%s on L%d: %d' % (rail, up + 1, sum(1 for p in pl['posts'] if p[2] == up and raster.net_nodes(up, rail)[p[0], p[1]]))
        for rail in pl['rails'] for up in (0, 2))))
    if pl['wires'] or pl['holds']:
        print('  %d parts fitted as wires, %d more ground posts at %s' % (len(pl['wires']), len(pl['holds']), ' '.join(
            '(%.1f, %.1f)' % (mesh['x'][ix], mesh['y'][iy]) for ix, iy in pl['holds'])))


def report_check(geom, mesh, raster):
    nx, ny, nz = len(mesh['x']), len(mesh['y']), len(mesh['z'])
    d = [np.diff(mesh[a]).min() for a in 'xyz']
    print('mesh %d x %d x %d = %.2f M cells, smallest cell %.3f x %.3f x %.3f mm' % (
        nx, ny, nz, nx * ny * nz / 1e6, d[0], d[1], d[2]))
    print('%d edges given up where two nets met' % raster.removed)
    ok = True
    print('nets after meshing:')
    for net in KEY_NETS:
        comps = raster.components_of(net)
        stray = sum(c for _, c in comps[1:])
        # a lost crumb of a plane (sliver between two antipads) is harmless, a cut track is not
        good = stray <= 0.005 * comps[0][1] if net == GND or net in RAILS else len(comps) == 1
        ok &= good
        print('  %-12s %6d edges  %s' % (net, comps[0][1], 'one piece' if len(comps) == 1 else
                                         '%s, %d stray edges in %d crumbs' % ('ok' if good else 'SPLIT', stray, len(comps) - 1)))
    shorts = raster.shorts()
    ok &= not shorts
    print('shorts between nets: %d%s' % (len(shorts), ''.join('\n  ' + ' = '.join(s) for s in shorts)))
    return ok


# ----------------------------------------------------------------------------- openEMS model

def build_model(geom, mesh, raster, pl, case, polygons=False, movie=False):
    """polygons=True draws the KiCad copper as is (for viewing); otherwise the verified mesh edges.

    movie=True also stores the two E-field maps over time, for make_video.py.
    """
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    x, y, z, zl = mesh['x'], mesh['y'], mesh['z'], mesh['zl']
    z_top, z_air = zl[0], z[snap(z, zl[0]) + 1]      # board surface, first mesh plane above it

    # The run ends on MaxTime. The energy of a driven loop passes through zero twice per period of the
    # pulse carrier, where a usual end criterion (-40 dB) could stop the run in the middle of the pulse.
    fdtd = openEMS(EndCriteria=1e-9, MaxTime=2 * 9 / (2 * np.pi * FC) + T_SETTLE,
                   OverSampling=MOVIE_OVERSAMPLING if movie else OVERSAMPLING)
    fdtd.SetGaussExcite(F0, FC)
    fdtd.SetBoundaryCond(['MUR'] * 6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    grid = csx.GetGrid()
    grid.SetDeltaUnit(1e-3)
    for a in 'xyz':
        grid.AddLine(a, mesh[a])

    w, h = geom['size_mm']
    for d, zb, zt in zip(geom['dielectrics'], zl[1:], zl[:-1]):
        fr4 = csx.AddMaterial('FR4 ' + d['name'], epsilon=d['epsilon_r'],
                              kappa=2 * np.pi * F0 * EPS0 * d['epsilon_r'] * d['loss_tangent'])
        fr4.AddBox([-w / 2, -h / 2, zb], [w / 2, h / 2, zt], priority=0)

    metal, nprim = {}, 0
    for net, per_layer in geom['nets'].items():
        metal[net] = csx.AddMetal(re.sub(r'[^A-Za-z0-9+-]+', '_', net).strip('_') or 'no_net')
        for l in range(4):
            if polygons:
                for o in per_layer[l]:
                    metal[net].AddPolygon(np.asarray(o).T, 'z', zl[l], priority=10)
            else:
                for (x0, y0), (x1, y1) in edge_runs(raster, l, net):
                    metal[net].AddBox([x0, y0, zl[l]], [x1, y1, zl[l]], priority=10)
                    nprim += 1
    for b, (ix, iy) in zip(geom['barrels'], raster.barrels):
        metal[b['net']].AddBox([x[ix], y[iy], zl[3]], [x[ix], y[iy], z_top], priority=10)

    decoupling = csx.AddMetal('rail_decoupling')
    for ix, iy, upper, lower in pl['posts'] + [(ix, iy, 0, 1) for ix, iy in pl['holds']]:
        decoupling.AddBox([x[ix], y[iy], zl[lower]], [x[ix], y[iy], zl[upper]], priority=10)

    fitted = csx.AddMetal('fitted_parts')

    def fit(part, gap=False):
        """A part as a wire: up from one pad, across at the height of its body, down on the other.

        gap=True leaves the middle cell of the wire open, for a port. Returns the two ends of that cell and its height.
        """
        (ia, ja), (ib, jb), height = part
        nodes, z_part = part[:2], z[snap(z, z_top + height)]
        path = ([(i, ja) for i in range(ia, ib, 1 if ib > ia else -1)] +
                [(ib, j) for j in range(ja, jb, 1 if jb > ja else -1)] + [(ib, jb)])
        g = (len(path) - 1) // 2 if gap else -1
        for i, j in nodes:
            fitted.AddBox([x[i], y[j], z_top], [x[i], y[j], z_part], priority=10)
        for k, (a, b) in enumerate(zip(path[:-1], path[1:])):
            if k != g:
                fitted.AddBox([x[a[0]], y[a[1]], z_part], [x[b[0]], y[b[1]], z_part], priority=10)
        return path[g], path[g + 1], z_part

    for part in pl['wires']:
        fit(part)

    if case in ('frame', 'shield'):
        a, z1 = x[snap(x, SHIELD_HALF)], z[snap(z, z_top + SHIELD_HEIGHT)]
        shield = csx.AddMetal('shield_H5')
        for s in (-a, a):       # walls stop one cell above the board so tracks can pass underneath
            shield.AddBox([s, -a, z_air], [s, a, z1], priority=10)
            shield.AddBox([-a, s, z_air], [a, s, z1], priority=10)
        if case == 'shield':    # the frame alone is modelled as its four walls, without the top cross bars
            shield.AddBox([-a, -a, z1], [a, a, z1], priority=10)
        for b, (ix, iy) in zip(geom['barrels'], raster.barrels):
            if b['kind'].startswith('pad H5.'):
                shield.AddBox([x[ix], y[iy], z_top], [x[ix], y[iy], z_air], priority=10)

    em_ports = []
    for n, p in enumerate(pl['ports']):
        if 'coil' in p:         # a square turn, the port sitting in the middle of one side
            (i0, i1), (j0, j1), zc, g = p['coil']['i'], p['coil']['j'], z[p['coil']['k']], p['coil']['gap']
            turn = csx.AddMetal('L1_stray_field')
            for a, b in (((i0, j0), (g, j0)), ((g + 1, j0), (i1, j0)), ((i1, j0), (i1, j1)), ((i1, j1), (i0, j1)), ((i0, j1), (i0, j0))):
                turn.AddBox([x[a[0]], y[a[1]], zc], [x[b[0]], y[b[1]], zc], priority=10)
            em_ports.append(fdtd.AddLumpedPort(n + 1, R_PORT, [x[g], y[j0], zc], [x[g + 1], y[j0], zc], 'x', excite=1.0))
            continue
        if 'cap' in p or 'between' in p:    # read from the grounded side to the net side, or from the negative pin to the positive one
            (i0, j0), (i1, j1), zp = fit(p['cap'], gap=True) if 'cap' in p else (*p['between'], z_top)
            em_ports.append(fdtd.AddLumpedPort(n + 1, R_PORT, [x[i0], y[j0], zp], [x[i1], y[j1], zp], 'x' if j0 == j1 else 'y'))
            continue
        ix, iy = p['node']
        em_ports.append(fdtd.AddLumpedPort(n + 1, R_PORT, [x[ix], y[iy], zl[1]], [x[ix], y[iy], z_top], 'z',
                                           excite=1.0 if n == 0 else 0))

    # E-field at F_DUMP: just above the board, and a vertical cut through the switch node and the shield
    yc = y[snap(y, -9.4)]
    boxes = {'top': ([-w / 2 - 2, -h / 2 - 2, z_air], [w / 2 + 2, h / 2 + 2, z_air]),
             'cut': ([-w / 2 - 2, yc, -3.0], [w / 2 + 2, yc, z_top + 8.0])}
    for name, box in boxes.items() if pl['drive'] == 'sw' else ():
        csx.AddDump('E_' + name, dump_type=10, dump_mode=2, file_type=1, frequency=[F_DUMP]).AddBox(*box)
        if movie:
            csx.AddDump('Et_' + name, dump_type=0, dump_mode=2, file_type=1).AddBox(*box)
    if not polygons:
        print('%s: %d metal runs handed to openEMS' % (case, nprim))
    return fdtd, csx, em_ports


def fit_coupling(w, h):
    """Least-squares fit of h = jw.k / (1 + jw.tau): a quasi-static coupling k seen through one pole.

    For the sw drive k = R.Cm and tau = R.Cg, the net's own capacitance to ground; for the magnetic
    drives k = M and tau = L / R, the inductance of the victim loop. Returns k, tau, the share R2 of
    |h|^2 that this shape explains, and median(|h| / w): when the response does not have that shape
    only the solver noise is left, and that median bounds k.
    """
    s = np.median(np.abs(h) / w)
    a = np.column_stack([1j * w * s, -1j * w * h * 1e-9])                     # unknowns k / s and tau in ns
    k, tau = np.linalg.lstsq(np.vstack([a.real, a.imag]), np.r_[h.real, h.imag], rcond=None)[0]
    if tau < 0:
        k, tau = np.sum(h.imag * w) / np.sum(w ** 2) / s, 0.0
    model = 1j * w * k * s / (1 + 1j * w * tau * 1e-9)
    r2 = float(1 - np.sum(np.abs(h - model) ** 2) / np.sum(np.abs(h) ** 2))
    return float(k * s), float(tau * 1e-9), r2, float(s)


def postprocess(sim, em_ports, pl, case):
    drive = pl['drive']
    f = np.linspace(10e6, F0 + FC, 491)
    for p in em_ports:
        p.CalcPort(sim, f)
    src = em_ports[0]
    fit = (f >= F_FIT[0]) & (f <= F_FIT[1])
    w = 2 * np.pi * f[fit]
    # sw: V(net) / V(switch node) = jw.R.Cm        loop, coil: V(net) / I(driven loop) = jw.M
    ref, unit, scale = (src.uf_tot, 'fF', 1e15 / R_PORT) if drive == 'sw' else (src.if_tot, 'pH', 1e12)
    res = {'case': case, 'drive': drive, 'unit': unit, 'f': f.tolist(), 'victims': [], 'pairs': []}
    z_src = src.uf_tot / src.if_tot
    if drive == 'sw':
        res.update(v_sw_fdump=float(np.interp(F_DUMP, f, np.abs(src.uf_tot))), z_sw_fdump=float(np.interp(F_DUMP, f, np.abs(z_src))))
        print('\n%s: mutual capacitance switch node -> net (fit %g-%g MHz)' % (case, F_FIT[0] / 1e6, F_FIT[1] / 1e6))
    else:
        res['l_src_nH'] = fit_coupling(w, z_src[fit])[0] * 1e9
        if drive == 'coil':
            res['coil_area_mm2'] = pl['ports'][0]['coil']['area_mm2']
        print('\n%s: mutual inductance %s (%.1f nH) -> net (fit %g-%g MHz)' % (
            case, {'loop': 'commutation loop', 'input': 'input loop', 'coil': 'loop at L1'}[drive], res['l_src_nH'], F_FIT[0] / 1e6, F_FIT[1] / 1e6))
    print('  %-24s %11s %9s %6s %11s %9s' % ('net', 'Cm [fF]' if drive == 'sw' else 'M [pH]', 'tau [ns]', 'R2', 'bound', 'end/peak'))

    def entry(h):       # R2 tells whether the response really is a coupling; if not, only the bound is kept
        k, tau, r2, bound = fit_coupling(w, h[fit])
        return {'k': k * scale, 'tau_ns': tau * 1e9, 'r2': r2, 'bound': bound * scale, 'resolved': r2 >= R2_MIN}

    def show(label, e, tail=None):
        print('  %-24s %11.4g %9.3f %6.2f %11.4g %9s%s' % (label, e['k'], e['tau_ns'], e['r2'], e['bound'],
                                                         '' if tail is None else '%.1e' % tail,
                                                         '' if e['resolved'] else '   in the solver noise'))

    h = {}
    for p, spec in zip(em_ports[1:], pl['ports'][1:]):
        h[spec['net']] = p.uf_tot / ref
        tail = float(np.abs(p.ut_tot[-50:]).max() / np.abs(p.ut_tot).max())    # left over when the run stops
        e = dict(entry(h[spec['net']]), label=spec['label'], net=spec['net'], tail=tail, h_abs=np.abs(h[spec['net']]).tolist())
        res['victims'].append(e)
        show(spec['label'], e, tail)
    # The ADC converts a difference: fitted on the difference of the two complex responses, it is
    # not limited by how well each leg is known.
    for name, legs in INPUTS.items():
        sides = dict(zip(('connector', 'pin'), zip(*legs)), filter=FILTERS.get(name, (None,) * 3)[1:])
        for side, (a, b) in sides.items():
            if '%s %s' % (name, side) in h:     # already read as a difference, by one port
                e = {'input': name, 'side': side, 'nets': [a, b], 'dm': entry(h['%s %s' % (name, side)])}
            elif a in h:
                e = {'input': name, 'side': side, 'nets': [a, b], 'dm': entry(h[a] - h[b]), 'cm': entry((h[a] + h[b]) / 2)}
            else:
                continue
            res['pairs'].append(e)
            show('%s %s, difference' % (name, side), e['dm'])
    with open(os.path.join(sim, 'results.json'), 'w') as fo:
        json.dump(res, fo)
    return res


def main():
    global RES
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--drive', choices=DRIVES + ('all',), default='all')
    ap.add_argument('--case', choices=CASES + ('all',), default='all')
    ap.add_argument('--check', action='store_true', help='mesh and verify only')
    ap.add_argument('--view', action='store_true', help='open the model in AppCSXCAD')
    ap.add_argument('--post-only', action='store_true', help='reuse the data in run/')
    ap.add_argument('--threads', type=int, default=0)
    ap.add_argument('--res', type=float, default=RES, help='mesh step in the fine window, mm (convergence check)')
    ap.add_argument('--movie', action='store_true', help='also store the E-field over time, in run/<case>_movie (sw drive)')
    args = ap.parse_args()
    suffix = ('' if args.res == RES else '_%gmm' % args.res) + ('_movie' if args.movie else '')
    RES = args.res

    geom = load_geometry()
    mesh = build_mesh(geom)
    raster = Raster(geom, mesh)
    ok = report_check(geom, mesh, raster)
    plans = [plan(geom, mesh, raster, d) for d in (('sw',) if args.movie else DRIVES if args.drive == 'all' else (args.drive,))]
    for pl in plans:
        report_plan(mesh, raster, pl)
    if args.check:
        return 0 if ok else 1
    if not ok:
        print('the mesh does not reproduce the key nets, aborting')
        return 1

    for pl in plans:
        for case in (CASES if args.case == 'all' else (args.case,)):
            name = case + ('' if pl['drive'] == 'sw' else '_' + pl['drive'])
            sim = os.path.join(RUN, name + suffix)
            fdtd, csx, em_ports = build_model(geom, mesh, raster, pl, case, polygons=args.view, movie=args.movie)
            if args.view:
                from CSXCAD import AppCSXCAD_BIN
                os.makedirs(RUN, exist_ok=True)
                xml = os.path.join(RUN, 'model_%s.xml' % name)
                csx.Write2XML(xml)
                os.system('"%s" "%s"' % (AppCSXCAD_BIN, xml))
                continue
            if not args.post_only:
                t0 = time.time()
                fdtd.Run(sim, cleanup=True, verbose=1, numThreads=args.threads)
                print('%s: simulated in %.1f min' % (name, (time.time() - t0) / 60), flush=True)
            postprocess(sim, em_ports, pl, case)
            sys.stdout.flush()
    if not args.view and not suffix and any(pl['drive'] == 'sw' for pl in plans):
        import plot_results
        plot_results.main()
    return 0


if __name__ == '__main__':
    sys.exit(main())
