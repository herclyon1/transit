#!/usr/bin/env python3
"""Compare the renderer-measured ocean palette (ui/basemap/palette-ocean.json) with every rgba8 value in a set of .styl files.

For each band (light/dark) prints the nearest style-sheet colours (any property) within a tolerance, so we can see
whether the measured sea colours are style-sheet inputs or renderer outputs (texture / shading).
Usage: match_palette.py palette-ocean.json FILE.styl [FILE.styl ...] [--tol N]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from styl_decode import decode


def colours_in(path):
    ch, info, ps, st = decode(path)
    owners = {}
    for s in st['styles']:
        refs = [s['psi']] + [z['psi'] for z in s['zoom']]
        for c in s['conditional']:
            refs += [c['psi']] + [z['psi'] for z in c['zoom']]
        for p in refs:
            for q in ps['sets'][p]:
                if q['type'] == 'rgba8':
                    r, g, b, a = q['value']['rgba']
                    owners.setdefault((r, g, b, a, q['id']), set()).add(s['name'])
    return owners


def main(argv):
    tol = 12
    if '--tol' in argv:
        i = argv.index('--tol'); tol = int(argv[i + 1]); del argv[i:i + 2]
    pal = json.load(open(argv[1]))
    targets = []
    for band in pal['bands']:
        for mode in ('light', 'dark'):
            targets.append((f"band {band['depth_min_m']}-{band['depth_max_m']}m {mode}", tuple(band[mode]['rgb'])))
    for f in argv[2:]:
        owners = colours_in(f)
        print(f'== {Path(f).name}: {len(owners)} distinct (colour, property) pairs')
        for label, (tr, tg, tb) in targets:
            near = []
            for (r, g, b, a, pid), names in owners.items():
                d = max(abs(r - tr), abs(g - tg), abs(b - tb))
                if d <= tol:
                    near.append((d, (r, g, b, a), pid, sorted(names)[:4]))
            near.sort()
            print(f'   {label:24s} {(tr, tg, tb)} -> {len(near)} within {tol}: ' + '; '.join(f'{c} a{c[3]} p{pid} {names}' for d, c, pid, names in near[:3]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
