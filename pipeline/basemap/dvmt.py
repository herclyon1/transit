#!/usr/bin/env python3
"""Decode Apple's DaVinci material resources (tileset 60 `DvMt`, one per material id) from a copy of the geod tile cache.

    python3 pipeline/basemap/dvmt.py tiles.db --table > ui/basemap/dvmt-materials.json     (values only)
    python3 pipeline/basemap/dvmt.py tiles.db > ~/Money/styl-work/apple-data/dvmt-full.json   (full parse, outside the repo)

Format (read off `geo::codec::MaterialSheet::decodeMaterial` in VectorKit against the bytes; byte-aligned):
    'DvMt' u32 version(21) u64 materialId
    u16 kind, u16 nSections, nSections x section,
    u16 nVariants, nVariants x variant
    section  = u8 type, varint size, then: u8 propId, u8 ranged, [ranged: u8 n, n x (u8 zmin, u8 zmax, value)] [else: value]
    variant  = u16 k, u16 nCond, nCond x (u16 attribute, u32 value), u16 nSections, sections, varint (0)
    value by type: 0 rgba8 (Color<float,4>), 7 rgb8 (Color<float,3>), 6 ramp = u8 n, n x (float32 key, rgba8),
                   others kept as hex (the varint size makes them skippable, as the decoder does for types >= 10)
Conditions seen: attribute 1 = 1 night (TimePeriod), 0x45 = 69 map style (client:69), 0x87 = 135, 0 = 3.
"""
import json
import sqlite3
import struct
import sys


def varint(b, i):
    v, s = 0, 0
    while True:
        c = b[i]; i += 1
        v |= (c & 0x7f) << s; s += 7
        if not c & 0x80:
            return v, i


def value(t, b, i):
    if t == 0:
        return '#%02x%02x%02x%02x' % tuple(b[i:i + 4]), i + 4
    if t == 7:
        return '#%02x%02x%02x' % tuple(b[i:i + 3]), i + 3
    if t == 6:
        n = b[i]; i += 1
        stops = []
        for _ in range(n):
            k = struct.unpack_from('<f', b, i)[0]
            stops.append([round(k, 3), '#%02x%02x%02x%02x' % tuple(b[i + 4:i + 8])]); i += 8
        return stops, i
    return None, i


def section(b, i):
    t = b[i]; i += 1
    size, i = varint(b, i)
    end = i + size
    sec = {'type': t, 'size': size}
    if t >= 10:
        sec['raw'] = b[i:end].hex()
        return sec, end
    sec['prop'] = b[i]; sec['ranged'] = b[i + 1]; i += 2
    if sec['ranged']:
        n = b[i]; i += 1
        vals = []
        for _ in range(n):
            lo, hi = b[i], b[i + 1]; i += 2
            v, i2 = value(t, b, i)
            if v is None:
                vals.append([lo, hi, b[i:end].hex()]); i = end; break
            vals.append([lo, hi, v]); i = i2
        sec['bands'] = vals
    else:
        v, i2 = value(t, b, i)
        sec['value'] = v if v is not None else b[i:end].hex()
        i = end if v is None else i2
    if i != end:
        sec['tail'] = b[i:end].hex()
    return sec, end


def parse(blob):
    assert blob[:4] == b'DvMt'
    version, mid = struct.unpack_from('<IQ', blob, 4)
    i = 16
    kind, nsec = struct.unpack_from('<HH', blob, i); i += 4
    secs = []
    for _ in range(nsec):
        s, i = section(blob, i); secs.append(s)
    nvar = struct.unpack_from('<H', blob, i)[0]; i += 2
    variants = []
    for _ in range(nvar):
        k, ncond = struct.unpack_from('<HH', blob, i); i += 4
        conds = []
        for _ in range(ncond):
            a, v = struct.unpack_from('<HI', blob, i); i += 6
            conds.append([a, v])
        ns = struct.unpack_from('<H', blob, i)[0]; i += 2
        vs = []
        for _ in range(ns):
            s, i = section(blob, i); vs.append(s)
        pad, i = varint(blob, i)
        variants.append({'k': k, 'conditions': conds, 'sections': vs, 'tail': pad})
    trailer = blob[i:].hex()          # one 0x00 byte follows the variants in every resource seen
    return {'id': mid, 'id_low': mid & 0xffff, 'version': version, 'kind': kind, 'sections': secs, 'variants': variants, 'bytes': len(blob), 'parsed_to': i, 'trailer': trailer}


CLASSES = {223: 'Ground', 226: 'Herbaceous', 228: 'Shrubland', 235: 'Wetlands', 264: 'overlay-264', 271: 'Cultivated', 272: 'Barren', 274: 'Forest',
           275: 'IceSnow', 310: 'overlay-310', 318: 'Water', 330: 'Vegetation', 801: 'Sand', 30813: 'DryLake'}   # basemap/data/globe/spr-materials.json
PROPS = {8: 'fillColor rgba', 27: 'fillColor rgb', 17: 'waterDepthRamp (depth m -> rgba)', 23: 'colour2 rgba (with attribute 0 = 3)', 9: 'u32 (order?)', 11: 'u8 flag', 16: 'u8 flag', 26: 'type-3 value', 6: 'type-3 value'}
CONDS = {1: 'TimePeriod: 0 day / 1 night (client:1)', 69: 'map style (client:69): 0 = the globe (the Mac App globe paints these), 1 = standard, 2 = Elevated (the Mac flat map = the sheet Landcover colours)', 135: '? = 1', 0: '? = 3'}


def table(materials):
    """The numeric colour tables per material and condition set (for ui/basemap/dvmt-materials.json)."""
    out = {'what': 'DaVinci ground material colour tables decoded from the DvMt resources (tileset 60) of the local geod cache: per material, the base value and every conditioned variant (conditions = (client attribute, value)), colour bands by Apple zoom [zmin, zmax) and the water depth ramps',
           'source': 'pipeline/basemap/dvmt.py (format from geo::codec::MaterialSheet::decodeMaterial in VectorKit); values only, the resources themselves stay outside the repo',
           'conditions': CONDS, 'props': PROPS, 'materials': {}}
    for m in materials:
        if 'id' not in m:
            continue
        low = m['id_low']
        entry = {'id': m['id'], 'class': CLASSES.get(low), 'kind': m['kind'], 'base': {}, 'variants': []}
        def put(dst, secs):
            for s in secs:
                if s['type'] >= 10 or s.get('prop') is None:
                    continue
                dst[str(s['prop'])] = s.get('bands') if s['ranged'] else s.get('value')
        put(entry['base'], m['sections'])
        for v in m['variants']:
            vv = {'conditions': {str(a): val for a, val in v['conditions']}, 'k': v['k'], 'values': {}}
            put(vv['values'], v['sections'])
            entry['variants'].append(vv)
        out['materials'][str(low) if low in CLASSES else str(m['id'])] = entry
    return out


def main():
    db = sqlite3.connect(sys.argv[1])
    out = []
    for blob, in db.execute("select d.data from tiles t join data d on d.rowid=t.data_pk where ((tileset>>8)&255) = 60"):
        try:
            out.append(parse(bytes(blob)))
        except Exception as e:  # keep going, report
            out.append({'error': repr(e), 'head': bytes(blob[:32]).hex()})
    out.sort(key=lambda m: m.get('id', 0))
    if '--table' in sys.argv:
        json.dump(table(out), sys.stdout, indent=1)
    else:
        json.dump(out, sys.stdout, indent=1)
    ok = sum(1 for m in out if 'id' in m and m['trailer'] in ('', '00'))
    print(f'{len(out)} materials, {ok} parsed to the end (trailer 00)', file=sys.stderr)


if __name__ == '__main__':
    main()
