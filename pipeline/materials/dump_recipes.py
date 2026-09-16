#!/usr/bin/env python3
"""Dump macOS CoreMaterial recipes (the system "materials" behind NSVisualEffectView / glass) into one table.

Source: /System/Library/PrivateFrameworks/CoreMaterial.framework/Versions/A/Resources/*.materialrecipe,
*.descendantrecipe (a recipe that inherits from another and overrides keys), *.visualstyleset and
*.descendantstyleset (the fill/stroke layer styles a recipe points to).  All are plain XML plists.

    dump_recipes.py --json out.json --tsv out.tsv
"""
import argparse
import glob
import json
import os
import plistlib

RES = '/System/Library/PrivateFrameworks/CoreMaterial.framework/Versions/A/Resources'


def load(path):
    with open(path, 'rb') as f:
        return plistlib.load(f)


def matrix(m):
    """colorMatrix dict {m11..m45} -> 4 rows of 5 (r,g,b,a,bias)"""
    return [[m.get('m%d%d' % (r, c), 0) for c in range(1, 6)] for r in range(1, 5)]


def color(c):
    if c is None:
        return None
    if 'white' in c:
        return {'white': c['white'], 'alpha': c.get('alpha', 1)}
    return {k: c[k] for k in ('red', 'green', 'blue', 'alpha') if k in c}


def flatten_filtering(f):
    out = {}
    for k, v in f.items():
        if k == 'colorMatrix':
            out['colorMatrix'] = matrix(v)
        else:
            out[k] = v
    return out


def merge(a, b):
    """deep-merge b over a"""
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def recipe_row(name, d, kind, all_recipes):
    inherits = d.get('ancestorRecipe')
    if inherits:                                   # .descendantrecipe: ancestor + overrides
        d = merge(all_recipes[inherits], d.get('descendantDescription', {}))
    base = d.get('baseMaterial', {})
    row = {'name': name, 'kind': kind, 'version': d.get('materialSettingsVersion'),
           'inherits': inherits,
           'styles': d.get('styles'), 'filtering': flatten_filtering(base.get('materialFiltering', {})),
           'tinting': base.get('tinting'), 'other_baseMaterial_keys': sorted(k for k in base if k not in ('materialFiltering', 'tinting')),
           'other_top_keys': sorted(k for k in d if k not in ('baseMaterial', 'styles', 'materialSettingsVersion', 'ancestorRecipe', 'descendantDescription'))}
    for k in row['other_top_keys']:
        row[k] = d[k]
    for k in row['other_baseMaterial_keys']:
        row['baseMaterial.' + k] = base[k]
    return row


def styleset_row(name, d, kind):
    styles = {}
    for sname, s in d.get('styles', {}).items():
        e = {}
        if 'tinting' in s:
            e['tintColor'] = color(s['tinting'].get('tintColor'))
            for k in s['tinting']:
                if k != 'tintColor':
                    e['tinting.' + k] = s['tinting'][k]
        if 'filtering' in s:
            e['filterType'] = s['filtering'].get('filterType')
            fp = s['filtering'].get('filterProperties', {})
            for k, v in fp.items():
                e[k] = matrix(v) if k == 'inputColorMatrix' else v
        for k in s:
            if k not in ('tinting', 'filtering'):
                e[k] = s[k]
        styles[sname] = e
    slots = {k: v for k, v in d.items() if k != 'styles'}
    return {'name': name, 'kind': kind, 'slots': slots, 'styles': styles}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json')
    ap.add_argument('--tsv')
    a = ap.parse_args()
    recipes, stylesets = [], []
    raw = {}
    for p in sorted(glob.glob(RES + '/*')):
        name, ext = os.path.splitext(os.path.basename(p))
        if ext in ('.materialrecipe', '.descendantrecipe', '.visualstyleset', '.descendantstyleset'):
            raw[name] = (ext[1:], load(p))
    for name, (kind, d) in raw.items():
        if kind.endswith('recipe'):
            recipes.append(recipe_row(name, d, kind, {n: v for n, (k, v) in raw.items()}))
        else:
            if 'ancestorStyleSet' in d or 'ancestorRecipe' in d:
                anc = d.get('ancestorStyleSet') or d.get('ancestorRecipe')
                d = merge(raw[anc][1], d.get('descendantDescription', {}))
                d['inherits'] = anc
            stylesets.append(styleset_row(name, d, kind))
    out = {'source': RES, 'recipes': recipes, 'stylesets': stylesets}
    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1)
    if a.tsv:
        cols = ['name', 'kind', 'inherits', 'fill', 'stroke', 'blurRadius', 'blurAtEnd', 'backdropScale', 'saturation', 'brightness', 'luminanceAmount', 'luminanceValues', 'colorMatrix', 'other']
        with open(a.tsv, 'w') as f:
            f.write('\t'.join(cols) + '\n')
            for r in recipes:
                fl = r['filtering']
                st = r['styles'] or {}
                other = {k: v for k, v in fl.items() if k not in cols}
                for k in r['other_top_keys'] + ['baseMaterial.' + k for k in r['other_baseMaterial_keys']]:
                    other[k] = r[k]
                vals = [r['name'], r['kind'], r['inherits'] or '', st.get('fill', ''), st.get('stroke', ''),
                        fl.get('blurRadius', ''), fl.get('blurAtEnd', ''), fl.get('backdropScale', ''), fl.get('saturation', ''), fl.get('brightness', ''),
                        fl.get('luminanceAmount', ''), json.dumps(fl['luminanceValues']) if 'luminanceValues' in fl else '',
                        json.dumps(fl['colorMatrix']) if 'colorMatrix' in fl else '', json.dumps(other, default=str) if other else '']
                f.write('\t'.join(str(v) for v in vals) + '\n')
    print(len(recipes), 'recipes', len(stylesets), 'style sets')


if __name__ == '__main__':
    main()
