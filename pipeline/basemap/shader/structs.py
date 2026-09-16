#!/usr/bin/env python3
"""Print the uniform-buffer structs of a shader (from the AIR metadata `air.struct_type_info`) and, given a
capture.json from capture.m, decode every captured buffer of that shader field by field.

    structs.py ir/DaVinci__ground_fragment.ll                 # struct table only
    structs.py ir/DaVinci__ground_fragment.ll capture.json    # + decoded captured values
"""
import json
import re
import struct
import sys


def bindings(text):
    """buffer location index -> (arg name, type name, struct metadata node id)"""
    out = {}
    for m in re.finditer(r'^!(\d+) = !\{i32 (\d+), (.*)\}$', text, re.M):
        body = m.group(3)
        if '!"air.buffer"' not in body:
            continue
        loc = int(re.search(r'!"air.location_index", i32 (\d+)', body).group(1))
        name = re.search(r'!"air.arg_name", !"([^"]+)"', body).group(1)
        tn = re.search(r'!"air.arg_type_name", !"([^"]+)"', body)
        st = re.search(r'!"air.struct_type_info", !(\d+)', body)
        size = re.search(r'!"air.buffer_size", i32 (\d+)', body)
        out[loc] = (name, tn.group(1) if tn else '?', st.group(1) if st else None, int(size.group(1)) if size else None)
    return out


def members(text, node, prefix=''):
    """flatten one struct_type_info node into [(offset, size, type, name)], recursing into nested structs"""
    body = re.search(r'^!' + node + r' = !\{(.*)\}$', text, re.M).group(1)
    out = []
    # members are: i32 off, i32 size, i32 elems, !"type", !"name", (optional !"air.struct_type_info", !N)
    for m in re.finditer(r'i32 (\d+), i32 (\d+), i32 (\d+), !"([^"]+)", !"([^"]+)"(?:, !"air.struct_type_info", !(\d+))?', body):
        off, size, n, t, nm, sub = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4), m.group(5), m.group(6)
        if sub:
            for so, ss, st, sn in members(text, sub, prefix + nm + '.'):
                out.append((off + so, ss, st, sn))
        else:
            out.append((off, size, t, prefix + nm))
    return out


def decode(t, raw):
    fmt = {'float': ('f', 4), 'half': ('e', 2), 'int': ('i', 4), 'uint': ('I', 4), 'short': ('h', 2), 'ushort': ('H', 2),
           'bool': ('?', 1), 'char': ('b', 1), 'uchar': ('B', 1)}
    m = re.match(r'(float|half|int|uint|short|ushort|bool|char|uchar)(\d)?(?:x(\d))?$', t)
    if not m:
        return raw.hex()
    base, n, k = m.group(1), m.group(2), m.group(3)
    code, sz = fmt[base]
    n = int(n) if n else 1
    if k:                                   # matrix: k columns of n lanes, each column padded to 4 lanes if n == 3
        lanes = 4 if n == 3 else n
        cols = []
        for c in range(int(k)):
            cols.append([round(v, 5) for v in struct.unpack('<%d%s' % (n, code), raw[c * lanes * sz:c * lanes * sz + n * sz])])
        return cols
    vals = [round(v, 5) if isinstance(v, float) else v for v in struct.unpack('<%d%s' % (n, code), raw[:n * sz])]
    return vals[0] if n == 1 else vals


def main(argv):
    text = open(argv[1]).read()
    fn = [m.group(1) for m in re.finditer(r'^define [^@]*@"?([^"(]+)"?\(', text, re.M) if 'internal' not in m.group(0)][0]
    binds = bindings(text)
    cap = json.load(open(argv[2])) if len(argv) > 2 else None
    for loc in sorted(binds):
        name, tn, node, size = binds[loc]
        mem = members(text, node) if node else []
        print(f'[{loc}] {name}: {tn} ({size} B)')
        stage = 'F' if 'fragment' in fn else 'V'
        recs = cap['buffers'].get(f'{fn}|{stage}|{loc}', []) if cap else []
        blobs = [bytes.fromhex(r['hex']) for r in recs]
        seen = set()
        blobs = [b for b in blobs if not (b[:size or 512] in seen or seen.add(b[:size or 512]))]
        for off, sz, t, nm in mem:
            vals = [decode(t, b[off:off + sz]) for b in blobs if off + sz <= len(b)]
            uniq = []
            for v in vals:
                if v not in uniq:
                    uniq.append(v)
            print(f'    +{off:<4}{t:10} {nm:32}' + ('  ' + ' | '.join(json.dumps(v) for v in uniq) if uniq else ''))
        if cap and not blobs:
            print('    (not bound in capture)')


if __name__ == '__main__':
    main(sys.argv)
