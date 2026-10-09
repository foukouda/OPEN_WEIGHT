"""What the layout coupling means for the measurement: interference at the AD7190 inputs.

    C:\\openEMS\\venv\\Scripts\\python.exe measurement_quality.py

Three things are put together, harmonic by harmonic of the 1.2 MHz switching:
  - the couplings found by sw_coupling.py (run/<case>[_loop|_input|_coil]/results.json): mutual
    capacitance to the switch node, mutual inductance to the two current loops of the boost stage
    (commutation loop with the diode branch current, input loop with the inductor current) and to
    a loop standing for L1;
  - what the boost stage really does: V(SW) and I(L1) of the LTspice ripple run with the bridge
    powered (../LTspice/03_Power_Ripple.raw, written by run_simulations.py --only 03);
  - the input network of the board, read from geometry.json (every R and C sitting on an analog
    net, with its value) and closed by a 350 ohm load cell on each connector.
The result is the voltage left between the two pins of each AD7190 input, to be compared with the
noise of the converter itself. It is written to results.md and Images/Simulation/.

Everything is taken at its worst:
  - the AD7190 samples its inputs at MCLK / 16 = 307.2 kHz and its digital filter does not reject
    what sits on a multiple of that rate. 4 x 307.2 kHz = 1.229 MHz is inside the tolerance of the
    TPS61086 oscillator, so nothing is credited to the digital filter. Two figures are given: the
    switching frequency alone, and every harmonic up to 250 MHz together. The second one is a ceiling:
    the input stage of the AD7190 does not follow tens of MHz, and the LTspice switch commutates in
    no time, which overstates the high harmonics;
  - the two legs of an input, and the mechanisms, add up as if they were in phase; the common
    part of a coupling is turned into a difference by the tolerance of the filter parts;
  - behind the filter nothing attenuates what is induced between the capacitor across the pair and
    the two pins. What is induced around the two capacitors to ground divides onto the capacitor
    across, the 0.8 nH assumed for each capacitor standing for the inductance of that loop;
  - a coupling lost in the solver noise counts for its upper bound;
  - L1 is shielded and how much of its field leaks out is not published: it is given the largest
    dipole moment that its stored energy allows, m <= I.sqrt(6.pi.a^3.L / mu0) for a part that fits in
    a sphere of radius a (all of the energy 1/2.L.I^2 in the field outside the part). That bound is
    reported on its own and not added to the two other mechanisms.

Not included: the load cell cable, the connectors above the board, the response of the AD7190 input
stage to frequencies far above its band, and the ripple conducted through the +5VA rail (LTspice 03, 04).
"""
import json
import os
import re
import sys

import numpy as np

import plot_results as pr
from sw_coupling import CASES, DRIVES, FILTERS, GND, INPUTS, L1_BODY, RAILS, VICTIMS

plt, Line2D = pr.plt, pr.Line2D
HERE = os.path.dirname(os.path.abspath(__file__))
LTSPICE = os.path.normpath(os.path.join(HERE, '..', 'LTspice'))
sys.path.insert(0, LTSPICE)
from ltraw import read_raw  # noqa: E402

F_SW, F_MAX = 1.2e6, 250e6          # harmonics up to the band where the couplings were fitted
T_FFT, DT = (2e-3, 6e-3), 1e-9      # steady state of the ripple run: 4800 switching periods
MU0 = 4e-7 * np.pi
UNIT = {'fF': 1e-15, 'pH': 1e-12}
NETS = [v[1] for v in VICTIMS]

# not on the board, values as in ../LTspice/03_Power_Ripple.asc
R_BRIDGE = 350.0                    # each arm of the load cell
R_Q1, R_BPDSW = 0.19, 3.0           # the two switches that power it: SENSE+ to +5VA, SENSE- to ground
L1_L = 4.7e-6
# assumed for the parts of the input filter
CAP_ESL, CAP_ESR = 0.8e-9, 0.03     # 0603 ceramic capacitor with its pads
TOL_R, TOL_C = 0.01, 0.10
# yardsticks
ADC_NOISE = 8.5e-9                  # AD7190 data sheet: rms noise at 4.7 Hz, gain 128, its quietest setting
FULL_SCALE = 2e-3 * 5.0             # 2 mV/V load cell under 5 V
MECHANISMS = {'sw': 'Switch node voltage', 'loops': 'Boost current loops', 'coil': 'Inductor stray field, upper bound'}
DRIVE_NAMES = {'sw': 'switch node voltage', 'loop': 'commutation loop', 'input': 'input loop', 'coil': 'inductor stray field, upper bound'}
TOTAL = 'Voltage and loops together'    # the stray field of L1 is only bounded: it is kept out of the sum
LEAK = 0.01                             # share of the energy of L1 used to illustrate how its bound scales


# ----------------------------------------------------------------------------- boost stage waveforms

def boost_spectra():
    """Amplitude of each switching harmonic of V(SW), of the diode branch current and of I(L1)."""
    raw = os.path.join(LTSPICE, '03_Power_Ripple.raw')
    if not os.path.exists(raw):
        raise SystemExit('%s is missing: run "python run_simulations.py --only 03" in Simulation/LTspice' % raw)
    d = read_raw(raw)
    t = np.arange(T_FFT[0], T_FFT[1], DT)
    v, il = (np.interp(t, d['time'], d[k]) for k in ('v(sw)', 'i(l1)'))
    # Switch closed: the node sits within RON x I of ground. A shorter stay there is the ringing of the
    # discontinuous mode crossing zero. Otherwise the inductor current goes through the diode branch.
    k = np.ones(21)
    on = np.convolve(np.convolve(np.abs(v) < 0.05, k, 'same') > k.size - 0.5, k, 'same') > 0.5
    n = np.arange(1, int(F_MAX / F_SW) + 1)
    bins = np.rint(n * F_SW * t.size * DT).astype(int)

    def lines(y):
        a = np.abs(np.fft.rfft(y)) * 2 / t.size
        return np.sqrt(sum(a[bins + s] ** 2 for s in range(-2, 3)))
    return {'f': n * F_SW, 'v_sw': lines(v), 'i_hot': lines(il * ~on), 'i_l': lines(il)}


# ----------------------------------------------------------------------------- input network

def value(text):
    """('R', ohm) or ('C', farad) from a KiCad value such as 100Ω, 0.01µF or 18pf."""
    m = re.fullmatch(r'([0-9.]+)\s*([pnuµμmkM]?)\s*(F|Ω|R)', text.strip(), re.I)
    if m:
        mult = {'': 1, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6, 'm': 1e-3, 'k': 1e3, 'M': 1e6}
        prefix = m.group(2) if m.group(2) in mult else m.group(2).lower()
        return ('C' if m.group(3).upper() == 'F' else 'R'), float(m.group(1)) * mult[prefix]


def network(geom):
    """Every R and C between two analog nets or to ground, as (ref, kind, value, net, net)."""
    ground = {GND, *RAILS}                                  # the rails are AC ground, as in the field model
    elems = []
    for part in geom['parts']:
        nets = [p['net'] for p in geom['pads'] if p['ref'] == part['ref']]
        kv = value(part['value'])
        if kv and len(nets) == 2 and set(nets) & set(NETS):
            assert set(nets) <= set(NETS) | ground, '%s goes to %s' % (part['ref'], nets)
            elems.append((part['ref'], kv[0], kv[1], nets[0], nets[1]))
    for pos, neg in INPUTS.values():
        for net in (pos[0], neg[0]):
            if net:
                elems += [('load cell', 'R', R_BRIDGE, 'SENSE+', net), ('load cell', 'R', R_BRIDGE, net, 'SENSE-')]
    return elems + [('Q1', 'R', R_Q1, 'SENSE+', GND), ('BPDSW', 'R', R_BPDSW, 'SENSE-', GND)]


def mismatch(elems):
    """Scale factors that unbalance each input: series resistor and capacitor to ground high on one leg, low on the other."""
    scale = {}
    for pos, neg in INPUTS.values():
        for (conn, pin), sign in ((pos, 1), (neg, -1)):
            for ref, kind, _, a, b in elems:
                if kind == 'R' and {a, b} == {conn, pin}:
                    scale[ref] = 1 + sign * TOL_R
                elif kind == 'C' and pin in (a, b) and not {a, b} & (set(NETS) - {pin}):
                    scale[ref] = 1 + sign * TOL_C
    return scale


def admittance(kind, val, w):
    return np.full(w.size, 1 / val, complex) if kind == 'R' else 1 / (CAP_ESR + 1j * w * CAP_ESL + 1 / (1j * w * val))


def impedance(elems, w, scale=None):
    """Node impedance matrix of the input network at each angular frequency, nets in NETS order."""
    y = np.zeros((w.size, len(NETS), len(NETS)), complex)
    for ref, kind, val, a, b in elems:
        g = admittance(kind, val * (scale or {}).get(ref, 1.0), w)
        for net in (a, b):
            if net in NETS:
                y[:, NETS.index(net), NETS.index(net)] += g
        if a in NETS and b in NETS:
            y[:, NETS.index(a), NETS.index(b)] -= g
            y[:, NETS.index(b), NETS.index(a)] -= g
    return np.linalg.inv(y)


def transfers(elems, w):
    """How each input turns what is coupled into its nets into a voltage between its two pins.

    Per input: for a current injected into the two pin nets or the two connector nets, and for a voltage
    induced along the two connector tracks, the gain of the difference of the two legs (nominal parts)
    and of their common part (parts at the ends of their tolerance). And for a voltage induced around
    the loop of the two filter capacitors to ground, the share that lands on the capacitor across.
    """
    scale = mismatch(elems)
    z, zt = impedance(elems, w), impedance(elems, w, scale)
    out = {}
    for name, (pos, neg) in INPUTS.items():
        def pins(m, net):                                   # between the two pins, for 1 A into a net
            return m[:, NETS.index(pos[1]), NETS.index(net)] - m[:, NETS.index(neg[1]), NETS.index(net)]

        def series(m, sc, leg):                             # ... for 1 V along the track feeding the series resistor
            r = next(val * sc.get(ref, 1.0) for ref, kind, val, a, b in elems if kind == 'R' and {a, b} == set(leg))
            return (pins(m, leg[1]) - pins(m, leg[0])) / r

        t = {'pin_dm': np.abs(pins(z, pos[1]) - pins(z, neg[1])) / 2, 'pin_cm': np.abs(pins(zt, pos[1]) + pins(zt, neg[1]))}
        if pos[0]:
            t.update(conn_dm=np.abs(pins(z, pos[0]) - pins(z, neg[0])) / 2, conn_cm=np.abs(pins(zt, pos[0]) + pins(zt, neg[0])),
                     emf_dm=np.abs(series(z, {}, pos) - series(z, {}, neg)) / 2,
                     emf_cm=np.abs(series(zt, scale, pos) + series(zt, scale, neg)))
        if name in FILTERS:                                 # 1 V in series with the capacitor to ground of one leg
            t['filter'] = np.abs(pins(z, pos[1]) * next(admittance(k, v, w) for ref, k, v, _, _ in elems if ref == FILTERS[name][1]))
        out[name] = t
    return out


# ----------------------------------------------------------------------------- interference at the pins

def results(case, drive, mesh=''):
    path = os.path.join(pr.RUN, case + ('' if drive == 'sw' else '_' + drive) + mesh, 'results.json')
    if os.path.exists(path):
        with open(path) as f:
            r = json.load(f)
        return r if 'pairs' in r else None


def coupling(res, name, side, mode):
    """One pair of nets, difference ('dm') or common part ('cm'): |k|, or its bound if lost in the noise, in SI."""
    e = next(p for p in res['pairs'] if p['input'] == name and p['side'] == side)[mode]
    return (abs(e['k']) if e['resolved'] else e['bound']) * UNIT[res['unit']]


def l1_moment():
    """Largest dipole moment of L1 per ampere, A.m2/A: all of 1/2.L.I^2 in the field outside the part."""
    a = 0.5e-3 * np.linalg.norm(L1_BODY)
    return np.sqrt(6 * np.pi * a ** 3 * L1_L / MU0)


def interference(name, tr, spec, runs):
    """Worst-case amplitude at each harmonic of the voltage between the two pins of an input, per mechanism."""
    w, t, conn, out = 2 * np.pi * spec['f'], tr[name], INPUTS[name][0][0] is not None, {}
    if 'sw' in runs:                                        # jw.Cm.V(SW) injected into the nets
        r = runs['sw']
        z = t['pin_dm'] * coupling(r, name, 'pin', 'dm') + t['pin_cm'] * coupling(r, name, 'pin', 'cm')
        if conn:
            z = z + t['conn_dm'] * coupling(r, name, 'connector', 'dm') + t['conn_cm'] * coupling(r, name, 'connector', 'cm')
        out['sw'] = w * spec['v_sw'] * z
    currents = {'loop': spec['i_hot'], 'input': spec['i_l']}
    if 'coil' in runs:                                      # the loop that was simulated, scaled to the moment of L1
        currents['coil'] = spec['i_l'] * l1_moment() / (runs['coil']['coil_area_mm2'] * 1e-6)
    for drive, current in currents.items():                 # jw.M.I induced along the nets
        if drive in runs:
            r = runs[drive]
            m = coupling(r, name, 'pin', 'dm')              # past the filter: straight onto the pins
            if conn:
                m = m + t['emf_dm'] * coupling(r, name, 'connector', 'dm') + t['emf_cm'] * coupling(r, name, 'connector', 'cm')
            if name in FILTERS:
                m = m + t['filter'] * coupling(r, name, 'filter', 'dm')
            out[drive] = w * current * m
    if 'loop' in out and 'input' in out:
        out['loops'] = out['loop'] + out['input']
    return out


def rms(a):
    return float(np.sqrt(np.sum(np.asarray(a) ** 2) / 2))


def evaluate(tr, spec, mesh=''):
    """{case: {input: {mechanism or 'total': amplitude per harmonic}}} for the cases simulated with the three drives.

    With another mesh step whatever has been simulated is kept: those runs are only compared drive by drive.
    """
    out = {}
    for case in CASES:
        runs = {d: r for d in DRIVES for r in [results(case, d, mesh)] if r}
        if runs and not mesh and len(runs) < len(DRIVES):
            print('%s: only %s simulated so far, left out' % (pr.CASES[case], ', '.join(runs)))
        elif runs:
            out[case] = {}
            for name in INPUTS:
                parts = interference(name, tr, spec, runs)
                out[case][name] = dict(parts, total=sum(parts[m] for m in ('sw', 'loops') if m in parts))
    return out


# ----------------------------------------------------------------------------- report

MEASURES = (('At the switching frequency alone (1.2 MHz)', lambda a: float(a[0] / np.sqrt(2))),
            ('Every harmonic up to %g MHz together: a ceiling' % (F_MAX / 1e6), rms))


def nv(x):
    return '%.2g' % (x * 1e9)


def report(spec, ev, meshes):
    cases = list(ev)
    head = ' | '.join(pr.CASES[c] for c in cases)
    sep = '| --- ' * (len(cases) + 1) + '|'

    def row(label, cell):
        return '| %s | %s |' % (label, ' | '.join(cell(c) for c in cases))

    md = ['# openEMS results (generated by measurement_quality.py)', '',
          'Worst-case voltage left by the boost stage between the two pins of each AD7190 input, in nV rms, with '
          'nothing credited to the digital filter (assumptions at the top of measurement_quality.py).', '',
          'Yardstick: the AD7190 itself has %.1f nV rms of noise at its quietest setting (4.7 Hz, gain 128). '
          'A 2 mV/V load cell under 5 V gives %g mV at full load, so 1 nV is %.1f ppm of full scale.'
          % (ADC_NOISE * 1e9, FULL_SCALE * 1e3, 1e-9 / FULL_SCALE * 1e6), '',
          'The stray field of L1 is kept apart: the part is shielded and what it leaks is not published, so it only '
          'has an upper bound, all of its stored energy taken as stray field. The bound goes with the square root '
          'of the share that really leaks.', '']
    for name in INPUTS:
        if name == 'REF':
            md += ['## Reference input (REFIN1, the bridge excitation)', '',
                   'The reading is a ratio to this voltage: 1 nV on 5 V moves it by 0.2 ppb.', '']
        else:
            md += ['## %s (%s)' % (name, 'J4, AIN1/AIN2' if name == 'CH1' else 'J2, AIN3/AIN4'), '']
        for title, measure in MEASURES:
            md += ['| %s | %s |' % (title, head), sep]
            md += [row(labels, lambda c, m=mech: nv(measure(ev[c][name][m]))) for mech, labels in list(MECHANISMS.items())[:2] + [('total', TOTAL)]]
            if name != 'REF':
                md.append(row('%s, times the noise of the AD7190' % TOTAL, lambda c: '%.2g' % (measure(ev[c][name]['total']) / ADC_NOISE)))
            md.append(row(MECHANISMS['coil'], lambda c: nv(measure(ev[c][name]['coil']))))
            md.append(row('The same if %g %% of the energy of L1 is stray field' % (LEAK * 100), lambda c: nv(measure(ev[c][name]['coil']) * np.sqrt(LEAK))))
            md.append('')
        worst = {c: int(np.argmax(ev[c][name]['total'])) for c in cases}
        md += ['%s, largest single harmonic: %s.' % (TOTAL, ', '.join('%s nV rms at %.1f MHz (%s)' % (
            nv(ev[c][name]['total'][worst[c]] / np.sqrt(2)), spec['f'][worst[c]] / 1e6, pr.CASES[c].lower()) for c in cases)), '']

    md += ['## Couplings found by the field solver', '',
           'Per input and per place (connector tracks, loop of the two filter capacitors to ground, pins): '
           'difference between the two legs, then their common part where both legs were probed. '
           '"<" marks a coupling lost in the solver noise, given as an upper bound.', '']
    for drive, title in (('sw', 'Mutual capacitance to the switch node (fF)'),
                         ('loop', 'Mutual inductance to the commutation loop IC2 - D3 - C19/C20 (pH)'),
                         ('input', 'Mutual inductance to the input loop C21/C22 - L1 - IC2 (pH)'),
                         ('coil', 'Mutual inductance to a loop of the size of L1, at its place (pH)')):
        runs = {c: results(c, drive) for c in cases}
        md += ['**%s**' % title, '', '| Nets | %s |' % head, sep]
        for p in runs[cases[0]]['pairs']:
            for mode, what in (('dm', 'difference'), ('cm', 'common')):
                if mode in p:
                    es = [next(q for q in runs[c]['pairs'] if (q['input'], q['side']) == (p['input'], p['side']))[mode] for c in cases]
                    md.append('| %s %s (%s / %s), %s | %s |' % (p['input'], p['side'], p['nets'][0], p['nets'][1], what, ' | '.join(
                        '%.2g' % abs(e['k']) if e['resolved'] else '< %.2g' % e['bound'] for e in es)))
        md.append('')
    r = results(cases[0], 'coil')
    md += ['The loop driven for L1 has %.1f mm2. L1 is given at most %.2g mA.m2 of dipole moment per ampere, %.0f times that loop.'
           % (r['coil_area_mm2'], l1_moment() * 1e3, l1_moment() / (r['coil_area_mm2'] * 1e-6)), '']

    md += ['## Boost stage, from LTspice 03 (bridge powered)', '', '| Harmonic | V(SW) | Diode branch current | I(L1) |', '| --- | --- | --- | --- |']
    for n in (1, 2, 3, 5, 10, 20, 50, 100, 200):
        if n <= spec['f'].size:
            md.append('| %d (%.1f MHz) | %.3g V | %.3g mA | %.3g mA |' % (
                n, spec['f'][n - 1] / 1e6, spec['v_sw'][n - 1], spec['i_hot'][n - 1] * 1e3, spec['i_l'][n - 1] * 1e3))
    md += ['', 'Amplitudes.', '']

    if meshes and 'open' in ev:
        md += ['## Mesh sensitivity, bare board', '',
               'Same chain with another step of the fine mesh, for the drives simulated again: nV rms at 1.2 MHz alone / every harmonic.', '',
               '| Input, mechanism | %s |' % ' | '.join(['0.2 mm'] + [m.strip('_').replace('mm', ' mm') for m in meshes]), '| --- ' * (len(meshes) + 2) + '|']
        for name in INPUTS:
            for mech, label in DRIVE_NAMES.items():
                if any(mech in e['open'][name] for e in meshes.values()):
                    md.append('| %s, %s | %s |' % (name, label, ' | '.join(
                        ' / '.join(nv(f(e['open'][name][mech])) for _, f in MEASURES) if mech in e['open'][name] else 'not run'
                        for e in [ev] + list(meshes.values()))))
        md.append('')
    text = '\n'.join(md)
    with open(os.path.join(HERE, 'results.md'), 'w', encoding='utf-8') as f:
        f.write(text)
    print(text)


def plot(spec, ev):
    cases = list(ev)
    inputs = [n for n in INPUTS if n != 'REF']
    colour = dict(zip(MECHANISMS, (pr.C1, pr.C2, pr.C3)), total=pr.INK2)
    order = {'sw': MECHANISMS['sw'], 'loops': MECHANISMS['loops'], 'total': TOTAL, 'coil': MECHANISMS['coil']}
    noise = ADC_NOISE * 1e9
    rows = [(k + 0.9 * inputs.index(name), name, mech) for k, (name, mech) in enumerate((n, m) for n in inputs for m in order)]
    shown = [f(ev[c][name][mech]) * 1e9 for _, f in MEASURES for c in cases for _, name, mech in rows] + [noise]
    xlim = 10 ** np.floor(np.log10(min(shown)) - 0.15), 10 ** np.ceil(np.log10(max(shown)) + 0.15)
    fig = plt.figure(figsize=(12.5, 9.0))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.45, 1], hspace=0.5, wspace=0.13)

    # one row per mechanism, one marker per shielding case: left of the dashed line it is below the converter's own noise
    for k, (title, measure) in enumerate(MEASURES):
        a = fig.add_subplot(grid[0, k])
        for y, name, mech in rows:
            vals = [measure(ev[c][name][mech]) * 1e9 for c in cases]
            a.plot([min(vals), max(vals)], [y, y], color=pr.GRID, lw=2, zorder=1, solid_capstyle='round')
            for c, v in zip(cases, vals):
                a.plot(v, y, '<' if mech == 'coil' else 'o', ms=9, mew=2, mec=colour[mech], mfc=pr.tint(colour[mech], pr.FILL[c]), zorder=3)
        a.set_yticks([r[0] for r in rows])
        a.set_yticklabels([order[r[2]] for r in rows], color=pr.INK)
        a.tick_params(labelleft=k == 0)
        a.set_ylim(rows[-1][0] + 0.6, -1.1)
        a.set_xscale('log')
        a.set_xlim(*xlim)
        a.xaxis.set_major_formatter(pr.FuncFormatter(lambda v, _: f'{v:g}'))
        a.xaxis.set_minor_formatter(pr.NullFormatter())
        a.grid(axis='y', visible=False)
        a.axvline(noise, color=pr.INK, lw=1, ls='--', zorder=2)
        a.set_xlabel('Between the two pins of the input (nV rms)')
        a.set_title(title, loc='left', fontsize=10)
        if k == 0:
            for name in inputs:
                a.text(-0.56, min(r[0] for r in rows if r[1] == name) - 0.75, 'Channel %s (%s)' % (name[-1], 'J4' if name == 'CH1' else 'J2'),
                       transform=a.get_yaxis_transform(), fontweight='bold', va='center')
            a.text(noise, 1.0, 'noise of the AD7190 \n%.1f nV rms ' % noise, transform=a.get_xaxis_transform(),
                   ha='right', va='top', fontsize=8, color=pr.INK2)
            handles = [Line2D([], [], marker='o', ls='', ms=9, mew=2, mec=pr.INK2, mfc=pr.tint(pr.INK2, pr.FILL[c]), label=pr.CASES[c]) for c in cases]
            handles.append(Line2D([], [], marker='<', ls='', ms=9, mew=2, mec=pr.INK2, mfc=pr.SURFACE, label='upper bound: L1 leaking all of its energy'))
            a.legend(handles=handles, loc='upper left', bbox_to_anchor=(-0.58, -0.14), ncol=len(handles), handletextpad=0.3, columnspacing=1.5)

    # where it sits in frequency, for the most exposed input on the bare board
    b = fig.add_subplot(grid[1, :])
    case = cases[0]
    name = max(inputs, key=lambda n: rms(ev[case][n]['total']))
    f = spec['f'] / 1e6
    for mech in MECHANISMS:
        b.plot(f, ev[case][name][mech] / np.sqrt(2) * 1e9, color=colour[mech], lw=1.5, ls='--' if mech == 'coil' else '-', label=MECHANISMS[mech])
    b.axhline(noise, color=pr.INK, lw=1, ls=':')
    b.text(f[0], noise, 'noise of the AD7190', ha='left', va='top', fontsize=8, color=pr.INK2)
    b.set_xscale('log'); b.set_yscale('log')
    b.set_xlim(f[0] * 0.9, f[-1] * 1.1)
    b.xaxis.set_major_formatter(pr.FuncFormatter(lambda v, _: f'{v:g}'))
    b.yaxis.set_major_formatter(pr.FuncFormatter(lambda v, _: f'{v:g}'))
    b.set_xlabel('Switching harmonic (MHz)')
    b.set_ylabel('Each harmonic (nV rms)')
    b.set_title('%s, channel %s, harmonic by harmonic' % (pr.CASES[case], name[-1]), loc='left', fontsize=10)
    b.legend(loc='upper left', bbox_to_anchor=(0, -0.2), ncol=3, handlelength=2.2, columnspacing=1.5)
    fig.suptitle('What the boost stage leaves on the AD7190 inputs, worst case', x=0.125, ha='left', fontweight='bold', y=0.95)
    pr.save(fig, 'openems_measurement_quality.png')


def main():
    with open(os.path.join(HERE, 'geometry.json'), encoding='utf-8') as f:
        geom = json.load(f)
    spec = boost_spectra()
    tr = transfers(network(geom), 2 * np.pi * spec['f'])
    ev = evaluate(tr, spec)
    if not ev:
        raise SystemExit('no case simulated with the three drives in run/, run sw_coupling.py first')
    meshes = {m: e for m in ('_0.25mm', '_0.15mm') for e in [evaluate(tr, spec, m)] if e}
    report(spec, ev, meshes)
    plot(spec, ev)


if __name__ == '__main__':
    main()
