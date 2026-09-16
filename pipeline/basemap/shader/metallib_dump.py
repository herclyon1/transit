#!/usr/bin/env python3
"""Parse an Apple .metallib container (MTLB) and dump its function list; optionally extract one function's AIR bitcode.

Container layout (Apple's compiled Metal library; layout as documented by the community metallib parsers):
  0x00 'MTLB'  u16 target/version fields ...  0x18 function-list offset/size (u64,u64), 0x28 public metadata off/size,
  0x38 private metadata off/size, 0x48 bitcode off/size.  Function list: u32 count, then per function u32 entry size and
  tagged records (4-char tag, u16 length, payload) until 'ENDT': NAME cstring, TYPE u8 (0 vertex 1 fragment 2 kernel),
  HASH 32 B, OFFT u64 x3 (public md, private md, bitcode offsets relative to their sections), VERS, MDSZ u64 bitcode size.

Usage: metallib_dump.py default.metallib [--list] [--extract NAME out.bc] [--strings NAME]
"""
import struct
import sys
from pathlib import Path


def parse(path):
    b = Path(path).read_bytes()
    assert b[:4] == b'MTLB', 'not a metallib'
    fl_off, fl_size, pub_off, pub_size, priv_off, priv_size, bc_off, bc_size = struct.unpack_from('<8Q', b, 0x18)
    count = struct.unpack_from('<I', b, fl_off)[0]
    pos = fl_off + 4
    funcs = []
    for _ in range(count):
        entry_size = struct.unpack_from('<I', b, pos)[0]
        p, end = pos + 4, pos + entry_size          # entry size counts its own u32
        f = {}
        while p < end:
            tag = b[p:p + 4].decode('latin1')
            if tag == 'ENDT':
                break
            ln = struct.unpack_from('<H', b, p + 4)[0]
            payload = b[p + 6:p + 6 + ln]
            if tag == 'NAME':
                f['name'] = payload.split(b'\0')[0].decode()
            elif tag == 'TYPE':
                f['type'] = {0: 'vertex', 1: 'fragment', 2: 'kernel'}.get(payload[0], payload[0])
            elif tag == 'OFFT':
                f['pub_off'], f['priv_off'], f['bc_off'] = struct.unpack('<3Q', payload)
            elif tag == 'MDSZ':
                f['bc_size'] = struct.unpack('<Q', payload)[0]
            elif tag == 'VERS':
                f['vers'] = struct.unpack('<4H', payload)
            p += 6 + ln
        funcs.append(f)
        pos = end
    return b, {'bc_off': bc_off, 'bc_size': bc_size, 'pub_off': pub_off, 'priv_off': priv_off}, funcs


def bitcode(b, sections, f):
    start = sections['bc_off'] + f['bc_off']
    return b[start:start + f['bc_size']]


def main(argv):
    b, sections, funcs = parse(argv[1])
    if '--list' in argv or len(argv) == 2:
        for f in funcs:
            print(f"{f.get('type', '?'):8s} {f.get('bc_size', 0):8d}  {f.get('name')}")
        print(len(funcs), 'functions; bitcode section', sections)
    if '--extract' in argv:
        i = argv.index('--extract'); name, out = argv[i + 1], argv[i + 2]
        f = next(x for x in funcs if x['name'] == name)
        Path(out).write_bytes(bitcode(b, sections, f))
        print('wrote', out, f['bc_size'], 'bytes')
    if '--strings' in argv:
        import re
        name = argv[argv.index('--strings') + 1]
        f = next(x for x in funcs if x['name'] == name)
        bc = bitcode(b, sections, f)
        for m in re.finditer(rb'[\x20-\x7e]{4,}', bc):
            print(m.group().decode())


if __name__ == '__main__':
    main(sys.argv)
