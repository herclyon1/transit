"""Minimal dyld shared cache reader: resolves an unslid address to (subcache file, offset) through each subcache's
mapping table, decodes an objc_msgSend$ stub (adrp x1/ldr x1) to its selector name."""
import glob, os, struct, sys

CACHE = '/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_arm64e'
files = [CACHE] + sorted(glob.glob(CACHE + '.[0-9][0-9]*'))
maps = []
for f in files:
    with open(f, 'rb') as fh:
        hdr = fh.read(0x200)
        if hdr[:16].rstrip(b'\0').decode('ascii', 'replace').startswith('dyld_v1') is False:
            continue
        mapping_off, mapping_cnt = struct.unpack_from('<II', hdr, 16)
        fh.seek(mapping_off)
        for i in range(mapping_cnt):
            addr, size, foff, maxp, initp = struct.unpack_from('<QQQII', fh.read(32))
            maps.append((addr, size, foff, f))

def read(addr, n):
    for a, s, fo, f in maps:
        if a <= addr < a + s:
            with open(f, 'rb') as fh:
                fh.seek(fo + addr - a)
                return fh.read(n)
    return None

def cstr(addr):
    b = read(addr, 200)
    return b.split(b'\0')[0].decode('utf-8', 'replace') if b else None

def stub_selector(addr):
    b = read(addr, 8)
    if not b: return None
    w0, w1 = struct.unpack('<II', b)
    if (w0 & 0x9f000000) != 0x90000000:
        return None
    immlo = (w0 >> 29) & 3; immhi = (w0 >> 5) & 0x7ffff
    imm = (immhi << 2) | immlo
    if imm & (1 << 20): imm -= 1 << 21
    page = (addr & ~0xfff) + (imm << 12)
    if (w1 & 0xffc00000) == 0xf9400000:            # ldr x1, [x1, #off] -> selref -> string
        p = read(page + ((w1 >> 10) & 0xfff) * 8, 8)
        if not p: return None
        v = struct.unpack('<Q', p)[0] & 0xffffffffff
        if v < 0x180000000: v += 0x180000000
        return cstr(v)
    if (w1 & 0xff800000) == 0x91000000:            # add x1, x1, #imm12 -> the string itself (cache-optimised stub)
        return cstr(page + ((w1 >> 10) & 0xfff))
    return None

if __name__ == '__main__':
    print(len(maps), 'mappings from', len(files), 'files')
    for a in sys.argv[1:]:
        addr = int(a, 16)
        print(a, stub_selector(addr))
