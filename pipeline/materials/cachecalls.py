"""cachecalls.py <extracted-dylib> <selector-substring>...: in a dylib extracted from the dyld cache, find every bl to a
cache objc_msgSend$ stub whose selector matches, print the immediate loaded into w2/x2 (2nd argument) just before it
and the enclosing symbol."""
import re, subprocess, sys
import os; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dsc_read.py')).read().split("if __name__")[0])
b = sys.argv[1]
wants = sys.argv[2:]
out = subprocess.run(['otool', '-l', b], capture_output=True, text=True).stdout
m = re.search(r'sectname __text\n\s+segname (\S+)\n\s+addr 0x([0-9a-f]+)\n\s+size 0x([0-9a-f]+)', out)
ta, ts = int(m.group(2), 16), int(m.group(3), 16)
syms = []
for line in subprocess.run(['nm', '-n', b], capture_output=True, text=True).stdout.splitlines():
    p = line.split(' ', 2)
    if len(p) == 3 and p[1] in 'tT' and p[0]:
        syms.append((int(p[0], 16), p[2]))
def symfor(a):
    lo, hi = 0, len(syms) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if syms[mid][0] <= a: lo = mid
        else: hi = mid - 1
    return syms[lo][1] if syms and syms[lo][0] <= a else '?'
dis = subprocess.run(['xcrun', 'llvm-objdump', '-d', '--no-show-raw-insn', '--start-address=%#x' % ta, '--stop-address=%#x' % (ta + ts), b], capture_output=True).stdout.decode('utf-8', 'replace').splitlines()
cache = {}
def sel(t):
    if t not in cache:
        cache[t] = stub_selector(t)
    return cache[t]
last = {}
for line in dis:
    m = re.match(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$', line)
    if not m: continue
    a, op, args = int(m.group(1), 16), m.group(2), m.group(3)
    if op in ('mov', 'movz', 'orr'):
        mm = re.match(r'(w2|x2),\s+(?:wzr,\s+)?#(0x[0-9a-f]+|-?\d+)', args)
        if mm: last['x2'] = (int(mm.group(2), 0), a)
        mr = re.match(r'(w2|x2),\s+([wx]\d+)$', args)
        if mr: last['x2'] = ('reg ' + mr.group(2), a)
    if op == 'bl':
        t = int(re.search(r'0x([0-9a-f]+)', args).group(1), 16)
        if 0x2c0000000 <= t < 0x2c8000000:
            s = sel(t)
            if s and any(w in s for w in wants):
                v = last.get('x2')
                print(hex(a), s, 'arg2 =', (v[0] if v and a - v[1] < 80 else '?'), '|', symfor(a))
