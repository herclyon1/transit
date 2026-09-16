#!/usr/bin/env python3
"""Turn the three material dumps into the tables used by MATERIALS.md.

    summarize.py materials/appkit-materials.json materials/catalyst-materials.json > /tmp/tables.md
"""
import json
import re
import sys

NSVEM = {0: 'appearanceBased', 1: 'light', 2: 'dark', 3: 'titlebar', 4: 'selection', 5: 'menu', 6: 'popover', 7: 'sidebar', 8: 'mediumLight',
         9: 'ultraDark', 10: 'headerView', 11: 'sheet', 12: 'windowBackground', 13: 'hudWindow', 15: 'fullScreenUI', 17: 'toolTip',
         18: 'contentBackground', 21: 'underWindowBackground', 22: 'underPageBackground'}


def layers(l):
    yield l
    for s in l.get('sublayers', []):
        yield from layers(s)


def find_filters(root, ftype):
    return [f for l in layers(root) for f in l.get('filters', []) if f['type'] == ftype]


def fmt(v):
    if isinstance(v, float):
        return ('%.4g' % v)
    if isinstance(v, dict) and 'components' in v:
        return 'rgba(' + ','.join('%.3g' % c for c in v['components']) + ')'
    if isinstance(v, list):
        return '[' + ','.join(fmt(x) for x in v) + ']'
    return str(v)


def backdrop_summary(root):
    """the classic CoreUI material: backdrop filters + tint layers"""
    out = []
    for l in layers(root):
        if l['class'] == 'CABackdropLayer':
            fs = []
            for f in l.get('filters', []):
                ins = {k: v for k, v in f['inputs'].items() if v is not None and k not in ('inputNormalizeEdges', 'inputQuality')}
                fs.append(f['type'] + ('(' + ','.join(f'{k[5:]}={fmt(v)}' for k, v in sorted(ins.items())) + ')' if ins else ''))
            out.append('backdrop[scale %s]: %s' % (fmt(l.get('scale', '')), ' → '.join(fs)))
        elif l['class'] in ('CALayer', 'NSViewBackingLayer') and 'backgroundColor' in l and l['backgroundColor']['components'] not in ([1, 1, 1, 1], [0, 0], [0, 0, 0, 0]):
            c = l['backgroundColor']['components']
            comp = l.get('compositingFilter')
            comp = comp if isinstance(comp, str) else (comp['type'] if comp else 'normal')
            op = l.get('opacity', 1)
            out.append('fill %s%s%s' % ('rgba(' + ','.join('%.3g' % x for x in c) + ')', ' ×%.3g' % op if op != 1 else '', ' ' + comp if comp != 'normal' else ''))
        elif l['class'] == 'CAChameleonLayer':
            out.append('chameleon ×%.3g' % l.get('opacity', 1))
    return out


def glass_params(root):
    fs = find_filters(root, 'glassBackground')
    if not fs:
        return None
    return {k: v for k, v in fs[0]['inputs'].items() if v is not None}


def main():
    ak = json.load(open(sys.argv[1]))
    cat = json.load(open(sys.argv[2]))
    print('## A. AppKit NSVisualEffectMaterial (behindWindow), light | dark\n')
    print('| material | light | dark |\n|---|---|---|')
    for name in sorted(k[13:-13] for k in ak['NSAppearanceNameAqua'] if k.startswith('visualEffect.') and k.endswith('.behindWindow')):
        l = backdrop_summary(ak['NSAppearanceNameAqua']['visualEffect.%s.behindWindow' % name])
        d = backdrop_summary(ak['NSAppearanceNameDarkAqua']['visualEffect.%s.behindWindow' % name])
        print('| %s | %s | %s |' % (name, '<br>'.join(l), '<br>'.join(d)))
    print('\n## B. UIBlurEffect on Mac Catalyst → the AppKit material it becomes\n')
    print('| UIBlurEffectStyle | effect description | NSVisualEffectMaterial | light tree | dark tree |\n|---|---|---|---|---|')
    for k in sorted(cat['light']):
        if not k.startswith('blur.'):
            continue
        desc = cat['light'][k]['views'].get('effect', '')
        m = re.search(r'material=(\d+)', desc)
        mat = int(m.group(1)) if m else None
        print('| %s | `%s` | %s | %s | %s |' % (k[5:], desc.split('> ')[-1], f'{mat} = {NSVEM.get(mat, "?")}' if mat is not None else '?',
                                              '<br>'.join(backdrop_summary(cat['light'][k]['layers'])), '<br>'.join(backdrop_summary(cat['dark'][k]['layers']))))
    print('\n## C. Liquid Glass recipes (the `glassBackground` CoreAnimation filter on a CABackdropLayer)\n')
    variants = []
    for mode, app in (('light', 'NSAppearanceNameAqua'), ('dark', 'NSAppearanceNameDarkAqua')):
        for k in ('glass.style0', 'glass.style1', 'glass.style0.tinted', 'popover.NSPopover'):
            g = glass_params(ak[app][k]['layers'] if k.startswith('popover') else ak[app][k])
            if g:
                variants.append(('AppKit ' + {'glass.style0': 'NSGlassEffectView regular', 'glass.style1': 'NSGlassEffectView clear', 'glass.style0.tinted': 'NSGlassEffectView regular tinted', 'popover.NSPopover': 'NSPopover frame'}[k] + ' / ' + mode, g))
    for mode in ('light', 'dark'):
        for k in sorted(cat[mode]):
            root = cat[mode][k].get('window') or cat[mode][k]['layers']
            g = glass_params(root)
            if g:
                variants.append(('UIKit(Catalyst) %s / %s' % (k, mode), g))
    base_name, base = variants[0]
    keys = sorted(set().union(*[set(v.keys()) for _, v in variants]))
    print('Baseline = **%s**, every parameter:\n' % base_name)
    print('| parameter | value |\n|---|---|')
    for k in keys:
        print('| %s | %s |' % (k[5:], fmt(base.get(k, '—'))))
    print('\nDeltas of the other variants against the baseline (only differing parameters):\n')
    for name, g in variants[1:]:
        diff = {k: g.get(k) for k in keys if g.get(k) != base.get(k)}
        print('- **%s**: %s' % (name, ', '.join('%s=%s' % (k[5:], fmt(v)) for k, v in sorted(diff.items())) or 'identical'))
    print('\n## D. Vibrant colour matrices attached next to the glass (CASDFLayer, opacity 0 = content vibrancy source)\n')
    for mode in ('light', 'dark'):
        for k in ('glass.style0.plain', 'glass.style1.plain', 'splitView.sidebar'):
            root = cat[mode][k].get('window') or cat[mode][k]['layers']
            for f in find_filters(root, 'vibrantColorMatrix'):
                m = f['inputs'].get('inputColorMatrix')
                if isinstance(m, list) and len(m) == 20:
                    print('- %s / %s: rows %s' % (k, mode, ' ; '.join('[' + ','.join('%.4g' % x for x in m[i:i + 5]) + ']' for i in range(0, 20, 5))))
    print('\n## E. QuartzCore SDF glass effect defaults\n')
    print('```\n' + json.dumps(ak['QuartzCore.SDFGlassEffects'], indent=1) + '\n```')


if __name__ == '__main__':
    main()
