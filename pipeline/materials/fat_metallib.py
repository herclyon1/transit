#!/usr/bin/env python3
"""Split a fat (cafebabe) .metallib into its slices and keep the ones that are MTLB containers.

Apple's system metallibs (e.g. QuartzCore.framework/Resources/default.metallib, 21 slices) wrap one AIR-bitcode
slice (cputype 0x1000017) and per-GPU Mach-O slices; only the AIR slice can be read by
pipeline/basemap/shader/metallib_dump.py.

Usage: fat_metallib.py default.metallib outdir
"""
import os
import struct
import sys


def main(path, outdir):
    b = open(path, 'rb').read()
    magic, n = struct.unpack('>II', b[:8])
    if magic != 0xcafebabe:
        sys.exit('not a fat file (magic %#x)' % magic)
    os.makedirs(outdir, exist_ok=True)
    for i in range(n):
        ct, cst, off, size, _ = struct.unpack('>IIIII', b[8 + 20 * i: 28 + 20 * i])
        sl = b[off:off + size]
        kind = 'MTLB' if sl[:4] == b'MTLB' else 'macho' if sl[:4] == b'\xcf\xfa\xed\xfe' else sl[:4].hex()
        print(f'{i:2d} cputype {ct:#x} subtype {cst:#x} {size:9d} B {kind}')
        if kind == 'MTLB':
            out = os.path.join(outdir, f'slice{i}_{ct:x}_{cst:x}.metallib')
            open(out, 'wb').write(sl)
            print('   ->', out)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
