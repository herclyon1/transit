#!/usr/bin/env python3
"""Decoder for Apple Maps compiled GeoCSS style sheets (`*.styl`, magic `STYL`).

Format recovered 2026-09-16 from the macOS 27 VectorKit binary (gss::StyleSheet<PropertyID>::decodeStyl,
geo::ibitstream) plus the iOS 26.1 decompilation; see STYL-FORMAT.md at the repo root.

Container: `STYL` + u16 chapter count, then per chapter {u16 id, u32 start, u32 end, u32 uncompressed size};
every chapter is a zlib stream.  Chapter ids: 1 = stylesheet info, 10 = global properties, 20 = property sets,
21 = styles, 30 = style matching tree.  Chapter bodies are MSB-first bit streams (see BitReader).

Usage:
  styl_decode.py FILE.styl                         summary (chapter sizes, counts)
  styl_decode.py FILE.styl --json OUT.json         full decode of chapters 1/20/21
  styl_decode.py FILE.styl --tsv OUT.tsv           one row per (style, property set, property) with resolved values
  styl_decode.py FILE.styl --show NAME [NAME...]   print styles whose name contains NAME (case-insensitive)
  styl_decode.py FILE.styl --color R,G,B [TOL]     list styles using an rgba8 value within TOL of the colour
"""
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from decoder_table import DECODER          # stream property id -> gss decoder function (macOS 27 VectorKit)
from property_names import PROPS           # stream property id -> (gss::PropertyID, decoder, kDefault* name, default)
from inferred_names import name_of         # kDefault* name, else name inferred from callers/styles/values

CHAPTER_INFO, CHAPTER_GLOBAL, CHAPTER_PROPERTY_SETS, CHAPTER_STYLES, CHAPTER_MATCHING_TREE = 1, 10, 20, 21, 30


class BitReader:
    """geo::ibitstream: MSB-first bit cursor over a byte string."""

    def __init__(self, data):
        self.d = data
        self.pos = 0        # byte position
        self.bit = 0        # bit offset inside the byte, 0..7

    def tell(self):
        return self.pos * 8 + self.bit

    def seek(self, bitpos):
        self.pos, self.bit = divmod(bitpos, 8)

    def bits_left(self):
        return len(self.d) * 8 - self.tell()

    def byte(self):
        """8 bits starting at the current (possibly unaligned) position."""
        cur = self.d[self.pos] if self.pos < len(self.d) else 0
        nxt = self.d[self.pos + 1] if self.pos + 1 < len(self.d) else 0
        v = ((cur << self.bit) & 0xff) | (nxt >> (8 - self.bit)) if self.bit else cur
        self.pos += 1
        return v

    def bits(self, n):
        """n bits MSB-first (flags, small counts, chars, big-endian 16-bit fixed point)."""
        v = 0
        while n >= 8:
            v = (v << 8) | self.byte()
            n -= 8
        if n:
            cur = self.d[self.pos] if self.pos < len(self.d) else 0
            nxt = self.d[self.pos + 1] if self.pos + 1 < len(self.d) else 0
            b = ((cur << self.bit) & 0xff) | (nxt >> (8 - self.bit)) if self.bit else cur
            v = (v << n) | (b >> (8 - n))
            self.bit += n
            if self.bit >= 8:
                self.bit -= 8
                self.pos += 1
        return v

    def flag(self):
        return self.bits(1)

    def uint(self, n):
        """geo::ibitstream::readUIntBits: n//8 whole bytes little-endian, then n%8 bits as the top partial byte."""
        bs = [self.byte() for _ in range(n >> 3)]
        if n & 7:
            bs.append(self.bits(n & 7))
        v = 0
        for i, b in enumerate(bs):
            v |= b << (8 * i)
        return v

    def varint(self):
        """LEB128 over 8-bit groups (7 payload bits + continuation bit), max 10 groups."""
        v = 0
        shift = 0
        for _ in range(10):
            b = self.byte()
            v |= (b & 0x7f) << shift
            if not b & 0x80:
                return v
            shift += 7
        raise ValueError('varint too long')

    def string(self):
        """NUL-terminated 8-bit chars at the current bit position (geo::ibitstream::readString)."""
        out = bytearray()
        while True:
            c = self.byte()
            if c == 0:
                return out.decode('latin1')
            out.append(c)

    def float32(self):
        return struct.unpack('<f', bytes(self.byte() for _ in range(4)))[0]


def read_container(path):
    b = Path(path).read_bytes()
    if b[:4] != b'STYL':
        raise ValueError('not a STYL file')
    nchap = struct.unpack_from('<H', b, 4)[0]
    chapters = {}
    off = 6
    for _ in range(nchap):
        cid, start, end, usize = struct.unpack_from('<HIII', b, off)
        off += 14
        d = zlib.decompress(b[start:end])
        assert len(d) == usize, (cid, len(d), usize)
        chapters[cid] = d
    return chapters


def decode_info(d):
    """Chapter 1: version, mode flags, attribute encodings, property sizes."""
    r = BitReader(d)
    info = {'version': r.varint(), 'debug': r.flag()}
    nmodes = r.bits(8)
    info['modes'] = [r.flag() for _ in range(nmodes)]          # map-mode support flags (3 modes)
    nattr = r.uint(16)
    fbits = r.bits(5) + 1
    cbits = r.bits(5) + 1
    info['feature_attr_bits'] = fbits
    info['client_attr_bits'] = cbits
    attrs = []
    for _ in range(nattr):
        aid = r.uint(fbits) if r.flag() else r.uint(cbits) + 0x10000   # client attributes live at 0x10000+
        attrs.append((aid, r.bits(5) + 1))                              # bits used for this attribute's values
    info['attributes'] = attrs
    pidbits = r.bits(5) + 1
    info['prop_id_bits'] = pidbits
    props = []
    for _ in range(r.uint(pidbits)):
        pid = r.uint(pidbits)
        kind = r.bits(2)                    # 0 = size in bits, 1 = size in bytes, 2 = one bit, 3 = variable (byte length varint inline)
        size = r.varint() if not kind & 2 else None
        props.append((pid, kind, size))
    info['properties'] = props
    return info


def _decode_value(r, dec, nbits):
    """One property value at the current position; the caller re-seeks to start + nbits afterwards."""
    if dec == 'rgba8' and nbits == 32:
        a, b, g, rr = (r.byte() for _ in range(4))       # stored A, B, G, R (sRGB 8-bit)
        return {'rgba': [rr, g, b, a]}
    if dec == 'float' and nbits == 32:
        return r.float32()
    if dec == 'floatPair' and nbits == 64:
        return [r.float32(), r.float32()]
    if dec == 'bool':
        return bool(r.bits(1))
    if dec == 'int32' and nbits == 32:
        return struct.unpack('<i', bytes(r.byte() for _ in range(4)))[0]
    if dec == 'uint64' and nbits == 64:
        return struct.unpack('<Q', bytes(r.byte() for _ in range(8)))[0]
    if dec == 'uint8' and nbits == 8:
        return r.byte()
    if dec == 'fixedPoint12_4' and nbits == 16:
        return r.bits(16) / 16.0
    if dec == 'fixedPoint8_8' and nbits == 16:
        return r.bits(16) / 256.0
    if dec == 'fixedPoint5_3' and nbits == 8:
        return r.byte() / 8.0
    if dec == 'fixedPoint6_2' and nbits == 8:
        return r.byte() / 4.0
    if dec == 'fixedPoint0To1' and nbits == 8:
        return r.byte() / 255.0
    if dec == 'fixedPoint0to2_55' and nbits == 8:
        return r.byte() / 100.0
    if dec == 'fixedPoint8_0' and nbits == 8:
        return float(r.byte())
    if dec == 'string':
        if nbits == 0:                                     # zero-length payload = empty string (no terminator stored)
            return ''
        raw = bytes(r.byte() for _ in range(nbits // 8))
        return raw.split(b'\0', 1)[0].decode('latin1')
    if dec == 'labelInfo':
        # gss::labelInfoDecoder: 7 presence-flagged fields (26.1 VectorKit_11.mm:8415); byte length varint precedes
        out = {}
        for name, kind in (('height', 'f'), ('heightCurve', 'e3'), ('heightCurveLimit', 'f'), ('haloSize', 'f'),
                           ('fontExpansion', 'f'), ('spacing', 'f'), ('arrowHeight', 'f')):
            if r.flag():
                out[name] = r.float32() if kind == 'f' else r.bits(3)
        return out
    if dec == 'traffic':
        # gss::trafficDecoder: presence-flagged fields in the order of its parse messages; widths beyond the
        # colours/floats are guesses (visibility = 1 bit) — values are only kept when they fit inside nbits
        start = r.tell(); out = {}
        for name, kind in (('visibility', 'b'), ('fillColor', 'c'), ('secondaryColor', 'c'), ('pillMiddleLength', 'f'),
                           ('pillSpacing', 'f'), ('secondaryWidth', 'f'), ('width', 'f'), ('minWidth', 'f'),
                           ('secondaryMinWidth', 'f'), ('maxWidth', 'f'), ('secondaryMaxWidth', 'f'), ('gradientMaskColor', 'c')):
            if r.tell() - start >= nbits:
                break
            if r.flag():
                if kind == 'b': out[name] = r.bits(1)
                elif kind == 'c':
                    a, b, g, rr = (r.byte() for _ in range(4)); out[name] = {'rgba': [rr, g, b, a]}
                else: out[name] = r.float32()
        if r.tell() - start > nbits:
            return {'raw_bits': nbits, 'partial': out}
        return out
    if dec == 'dashPattern' and nbits % 16 == 0:
        # little-endian u16 pairs (dash, gap) in pt; (4, 0) = solid.  Railway-Japan: 4,48,4,48; country border: 18,4,10,4,4,4
        vals = [r.byte() | (r.byte() << 8) for _ in range(nbits // 16)]
        return {'dash': vals}
    if dec in ('dashPattern', 'iconGradient', 'animationCurve', 'genericShieldStyle') or nbits > 64:
        return {'raw_bits': nbits}                         # composite types: layout not decoded yet
    return r.uint(nbits)                                   # uint32 and every enum-like decoder read readUIntBits(nbits)


def decode_property_sets(d, info):
    """Chapter 20: 5-bit (property-set-index bits - 1), count, then sets of [count][id, value]..."""
    r = BitReader(d)
    psi_bits = r.bits(5) + 1
    nsets = r.uint(psi_bits)
    pid_bits = info['prop_id_bits']
    sizes = {pid: (k, s) for pid, k, s in info['properties']}
    sets = []
    for _ in range(nsets):
        props = []
        for _ in range(r.uint(pid_bits)):
            pid = r.uint(pid_bits)
            kind, size = sizes[pid]
            if kind == 0:
                nbits = size
            elif kind == 1:
                nbits = size * 8
            elif kind == 2:
                nbits = 1
            else:
                nbits = r.varint() * 8
            start = r.tell()
            dec = DECODER.get(pid, 'unknown')
            try:
                val = _decode_value(r, dec, nbits)
            except Exception as e:                        # keep going; the size table tells us where the next value starts
                val = {'error': str(e)}
            r.seek(start + nbits)
            props.append({'id': pid, 'type': dec, 'bits': nbits, 'value': val})
        sets.append(props)
    return {'psi_bits': psi_bits, 'sets': sets, 'bits_left': r.bits_left()}


def decode_styles(d, info, psi_bits):
    """Chapter 21: six 5-bit width fields, style count, then styles with inheritance / zoom / conditional sets."""
    r = BitReader(d)
    inh_bits, zoom_bits, cond_style_bits, cond_bits, cond_attr_bits, style_bits = (r.bits(5) + 1 for _ in range(6))
    nstyles = r.uint(style_bits)
    attr_bits = dict(info['attributes'])
    fb, cb = info['feature_attr_bits'], info['client_attr_bits']

    def zoom_styles():
        # min/max zoom are stored as zoom*8 (8-bit fixed 5.3); psi = property set index
        return [{'zmin': r.bits(8) / 8, 'zmax': r.bits(8) / 8, 'psi': r.uint(psi_bits)} for _ in range(r.uint(zoom_bits))]

    styles = []
    for i in range(nstyles):
        s = {'index': i, 'name': r.string(), 'score': r.varint()}
        s['inherits'] = [r.uint(style_bits) for _ in range(r.uint(inh_bits))]
        s['psi'] = r.uint(psi_bits)
        s['zoom'] = zoom_styles()
        conds = []
        for _ in range(r.uint(cond_style_bits)):
            clist = []
            for _ in range(r.uint(cond_bits)):
                aid = r.uint(fb) if r.flag() else r.uint(cb) + 0x10000
                clist.append({'attr': aid, 'values': [r.uint(attr_bits[aid]) for _ in range(r.uint(cond_attr_bits))]})
            conds.append({'conditions': clist, 'psi': r.uint(psi_bits), 'zoom': zoom_styles()})
        s['conditional'] = conds
        styles.append(s)
    return {'styles': styles, 'bits_left': r.bits_left(),
            'widths': dict(inherit=inh_bits, zoom=zoom_bits, cond_style=cond_style_bits, cond=cond_bits, cond_attr=cond_attr_bits, style=style_bits)}


def decode(path):
    ch = read_container(path)
    info = decode_info(ch[CHAPTER_INFO])
    ps = decode_property_sets(ch[CHAPTER_PROPERTY_SETS], info)
    st = decode_styles(ch[CHAPTER_STYLES], info, ps['psi_bits'])
    return ch, info, ps, st


HERE = Path(__file__).resolve().parent
FEATURE_ATTRS = [l.strip() for l in (HERE / 'feature_attr_names.txt').read_text().splitlines()]
CLIENT_ATTRS = [l.strip() for l in (HERE / 'client_attr_names.txt').read_text().splitlines()]


def attr_name(aid):
    """Attribute id -> gss::StyleAttribute name.

    Feature attributes: 1-based index into feature_attr_names.txt (bit widths in chapter 1 match: 4=Country 8 bits,
    6=PoiType 9 bits).  Client attributes (0x10000+): only the first three line up with the string table
    (MapMode 3 bits, TimePeriod 1 bit, SelectionState 2 bits); beyond that the enum has gaps the string table
    does not show, so the raw id is kept.  See STYL-FORMAT.md.
    """
    if aid >= 0x10000:
        i = aid - 0x10000
        if i == 37:      # =1 switches labels to pure black on white by day (Continent-PointLabel-Base) and x1.25 label heights
            return 'client:37(~IncreaseContrast)'
        return f'client:{i}(~{CLIENT_ATTRS[i]})' if i < 3 else f'client:{i}'
    # '~Name' = tentative: the string-table order matches the bit widths for the first ids but is unverified beyond
    return f'feature:{aid}(~{FEATURE_ATTRS[aid - 1]})' if 0 < aid <= 6 else f'feature:{aid}'


def prop_label(pid):
    """'id:name' — kDefault* constant name, else inferred name (inferred_names.py), else the decoder type."""
    n = name_of(pid)
    if n == str(pid):
        p = PROPS.get(pid)
        return f'{pid}:{p[1]}' if p else f'{pid}'
    return f'{pid}:{n}'


def fmt_value(v):
    if isinstance(v, dict) and 'rgba' in v:
        r, g, b, a = v['rgba']
        return f'rgb({r},{g},{b}) a={a}'
    if isinstance(v, float):
        return f'{v:g}'
    s = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
    return s.replace('\t', '\\t').replace('\n', '\\n')      # keep one row per line in the TSV


def rows_for_style(s, styles, sets):
    """Flatten one style into (source, zoom range, condition, property, value) rows."""
    def emit(source, zrange, cond, psi):
        for p in sets[psi]:
            yield (s['name'], s['score'], source, zrange, cond, psi, p['id'], prop_label(p['id']), p['type'], fmt_value(p['value']))
    yield from emit('base', '', '', s['psi'])
    for z in s['zoom']:
        yield from emit('zoom', f"{z['zmin']:g}-{z['zmax']:g}", '', z['psi'])
    for c in s['conditional']:
        cond = ' & '.join(f"{attr_name(x['attr'])}={x['values']}" for x in c['conditions'])
        yield from emit('cond', '', cond, c['psi'])
        for z in c['zoom']:
            yield from emit('cond+zoom', f"{z['zmin']:g}-{z['zmax']:g}", cond, z['psi'])


def show(s, styles, sets):
    print(f"== {s['index']} {s['name']}  score={s['score']}  inherits={[styles[i]['name'] for i in s['inherits']]}")
    for row in rows_for_style(s, styles, sets):
        _, _, source, zrange, cond, psi, pid, label, typ, val = row
        print(f"   {source:9s} {zrange:8s} {cond:60.60s} set#{psi:<5d} {label:40s} {typ:20s} {val}")


def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__)
        return 0
    path = argv[1]
    ch, info, ps, st = decode(path)
    styles, sets = st['styles'], ps['sets']
    if len(argv) == 2:
        print({cid: len(d) for cid, d in ch.items()})
        print(f"version {info['version']} modes {info['modes']} attributes {len(info['attributes'])} properties {len(info['properties'])}")
        print(f"property sets {len(sets)} (chapter 20 bits left {ps['bits_left']}), styles {len(styles)} (chapter 21 bits left {st['bits_left']})")
        return 0
    mode = argv[2]
    if mode == '--json':
        out = {'file': Path(path).name, 'info': info, 'property_sets': sets, 'styles': styles}
        Path(argv[3]).write_text(json.dumps(out, indent=0))
    elif mode == '--tsv':
        with open(argv[3], 'w') as f:
            f.write('style\tscore\tsource\tzoom\tcondition\tset\tprop_id\tprop\ttype\tvalue\n')
            for s in styles:
                for row in rows_for_style(s, styles, sets):
                    f.write('\t'.join(str(x) for x in row) + '\n')
    elif mode == '--show':
        for kw in argv[3:]:
            for s in styles:
                if kw.lower() in s['name'].lower():
                    show(s, styles, sets)
    elif mode == '--color':
        target = tuple(int(x) for x in argv[3].split(','))
        tol = int(argv[4]) if len(argv) > 4 else 10
        for s in styles:
            for row in rows_for_style(s, styles, sets):
                p = sets[row[5]]
                for q in p:
                    if q['id'] == row[6] and isinstance(q['value'], dict) and 'rgba' in q['value']:
                        r, g, b, a = q['value']['rgba']
                        if all(abs(x - t) <= tol for x, t in zip((r, g, b), target)):
                            print(f"{s['name']:60s} {row[2]:9s} {row[3]:8s} {row[7]:36s} rgb({r},{g},{b}) a={a}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
