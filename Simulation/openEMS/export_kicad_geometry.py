"""Export the copper geometry of OPEN_WEIGHT.kicad_pcb to geometry.json for the openEMS model.

Run with KiCad's own Python (it provides the pcbnew module):
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" export_kicad_geometry.py

Coordinates in the JSON are in mm, origin at the board centre, x to the right and y up
(KiCad's y axis is flipped), so the top side (F.Cu) faces +z.
"""
import json
import os
import re
import sys
from collections import defaultdict

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.normpath(os.path.join(HERE, '..', '..', 'OPEN_WEIGHT.kicad_pcb'))
OUT = os.path.join(HERE, 'geometry.json')

MAX_ERROR = pcbnew.FromMM(0.02)     # arc approximation, well below the FDTD cell size
COPPER = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
mm = pcbnew.ToMM


def read_stackup(path):
    """Dielectric layers (top to bottom) from the (stackup ...) block of the board file."""
    txt = open(path, encoding='utf-8').read()
    start = txt.index('(stackup')
    block = txt[start:txt.index('(copper_finish', start)]
    diel = []
    for name, body in re.findall(r'\(layer "(dielectric \d+)"(.*?)\n\t\t\t\)', block, re.S):
        get = lambda key: float(re.search(r'\(%s ([0-9.]+)\)' % key, body).group(1))
        diel.append({'name': name, 'thickness': get('thickness'), 'epsilon_r': get('epsilon_r'),
                     'loss_tangent': get('loss_tangent')})
    return diel


def simplify(ps):
    try:
        ps.Simplify()
    except TypeError:
        ps.Simplify(pcbnew.SHAPE_POLY_SET.PM_FAST)


def fracture(ps):
    try:
        ps.Fracture()
    except TypeError:
        ps.Fracture(pcbnew.SHAPE_POLY_SET.PM_FAST)


def main():
    board = pcbnew.LoadBoard(BOARD)
    bb = board.GetBoardEdgesBoundingBox()
    cx, cy = mm(bb.GetCenter().x), mm(bb.GetCenter().y)
    tx = lambda p: [round(mm(p.x) - cx, 4), round(-(mm(p.y) - cy), 4)]

    # copper as zero-thickness sheets on the dielectric interfaces, z = 0 on the bottom layer
    diel = read_stackup(BOARD)
    z = [sum(d['thickness'] for d in diel[i:]) for i in range(len(diel) + 1)]
    layers = [{'name': board.GetLayerName(l), 'z': round(z[i], 4)} for i, l in enumerate(COPPER)]

    polys = defaultdict(lambda: [pcbnew.SHAPE_POLY_SET() for _ in COPPER])   # net -> one set per layer
    barrels, pads, parts, tracks = [], [], [], []

    for t in board.GetTracks():
        net = t.GetNetname()
        if t.Type() == pcbnew.PCB_VIA_T:
            for i, l in enumerate(COPPER):
                if t.FlashLayer(l):
                    t.TransformShapeToPolygon(polys[net][i], l, 0, MAX_ERROR, pcbnew.ERROR_INSIDE)
            barrels.append({'net': net, 'xy': tx(t.GetPosition()), 'drill': mm(t.GetDrillValue()), 'kind': 'via'})
        else:
            i = COPPER.index(t.GetLayer())
            t.TransformShapeToPolygon(polys[net][i], t.GetLayer(), 0, MAX_ERROR, pcbnew.ERROR_INSIDE)
            # centre line, an arc being split at its mid point
            pts = [t.GetStart(), t.GetMid(), t.GetEnd()] if t.Type() == pcbnew.PCB_ARC_T else [t.GetStart(), t.GetEnd()]
            tracks.append({'net': net or '<no net>', 'layer': i, 'width': mm(t.GetWidth()), 'pts': [tx(p) for p in pts]})

    for fp in board.GetFootprints():
        fp_pads = []
        for p in fp.Pads():
            net = p.GetNetname()
            on = []
            plated = p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH
            for i, l in enumerate(COPPER):
                if plated and p.IsOnLayer(l) and p.FlashLayer(l):
                    p.TransformShapeToPolygon(polys[net][i], l, 0, MAX_ERROR, pcbnew.ERROR_INSIDE)
                    on.append(i)
            drill = mm(p.GetDrillSize().x)
            if plated and drill > 0:
                barrels.append({'net': net, 'xy': tx(p.GetPosition()), 'drill': drill,
                                'kind': 'pad %s.%s' % (fp.GetReference(), p.GetNumber())})
            bbp = p.GetBoundingBox()
            d = {'ref': fp.GetReference(), 'pad': p.GetNumber(), 'net': net, 'xy': tx(p.GetPosition()),
                 'size': [round(mm(bbp.GetWidth()), 3), round(mm(bbp.GetHeight()), 3)], 'layers': on, 'drill': drill}
            pads.append(d)
            fp_pads.append(d)
        parts.append({'ref': fp.GetReference(), 'value': fp.GetValue(), 'xy': tx(fp.GetPosition()),
                      'top': not fp.IsFlipped(), 'npads': len(fp_pads)})

    for zn in board.Zones():
        if zn.GetIsRuleArea():
            continue
        for i, l in enumerate(COPPER):
            if zn.IsOnLayer(l):
                polys[zn.GetNetname()][i].Append(zn.GetFilledPolysList(l))

    # cross-check: everything KiCad considers copper on each layer
    ref_area = []
    for l in COPPER:
        ps = pcbnew.SHAPE_POLY_SET()
        board.ConvertBrdLayerToPolygonalContours(l, ps)
        simplify(ps)
        ref_area.append(ps.Area() / 1e12)

    nets, area = {}, [0.0] * len(COPPER)
    for net, sets in polys.items():
        per_layer = []
        for i, ps in enumerate(sets):
            simplify(ps)
            area[i] += ps.Area() / 1e12
            fracture(ps)
            outlines = []
            for k in range(ps.OutlineCount()):
                ch = ps.Outline(k)
                outlines.append([tx(ch.CPoint(j)) for j in range(ch.PointCount())])
            per_layer.append(outlines)
        nets[net if net else '<no net>'] = per_layer

    for b in barrels:
        b['net'] = b['net'] or '<no net>'
    for p in pads:
        p['net'] = p['net'] or '<no net>'

    data = {'board': os.path.basename(BOARD), 'origin_kicad_mm': [cx, cy],
            'size_mm': [mm(bb.GetWidth()), mm(bb.GetHeight())],
            'dielectrics': diel, 'layers': layers, 'nets': nets, 'tracks': tracks, 'barrels': barrels,
            'pads': pads, 'parts': parts}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    print('board %.2f x %.2f mm, centre (%.3f, %.3f)' % (mm(bb.GetWidth()), mm(bb.GetHeight()), cx, cy))
    for i, l in enumerate(layers):
        npoly = sum(len(v[i]) for v in nets.values())
        npts = sum(len(o) for v in nets.values() for o in v[i])
        print('  %-16s z=%.4f mm  %4d polygons %6d points  copper %.1f mm2 (KiCad check: %.1f mm2)' % (
            l['name'], l['z'], npoly, npts, area[i], ref_area[i]))
    print('%d nets, %d track segments, %d barrels (vias + plated holes), %d pads -> %s (%.0f kB)' % (
        len(nets), len(tracks), len(barrels), len(pads), OUT, os.path.getsize(OUT) / 1e3))


if __name__ == '__main__':
    sys.exit(main())
