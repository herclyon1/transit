#!/usr/bin/env python3
"""Turn the LLVM IR of a Metal AIR shader (clang -x ir -S -emit-llvm on a bitcode extracted by metallib_dump.py) into
short pseudo-code: SSA values used once are inlined, uniform loads are named after the struct member
(air.struct_type_info metadata), air.* intrinsics become function calls, vector shuffles become swizzles.

Usage: ir2pseudo.py shader.ll [--all]      (default prints only the entry function's blocks)
"""
import re
import sys
from collections import Counter, defaultdict


def parse_struct_info(text):
    """function arg index -> (arg name, {byte offset: member name}) and struct type name -> members"""
    args = {}
    members = {}
    for m in re.finditer(r'^!(\d+) = !\{i32 (\d+), (.*)\}$', text, re.M):
        body = m.group(3)
        an = re.search(r'!"air.arg_name", !"([^"]+)"', body)
        if not an:
            continue
        name = an.group(1)
        st = re.search(r'!"air.struct_type_info", !(\d+)', body)
        tn = re.search(r'!"air.arg_type_name", !"([^"]+)"', body)
        args[int(m.group(2))] = (name, tn.group(1) if tn else '?', st.group(1) if st else None)
    for node in {a[2] for a in args.values() if a[2]}:
        body = re.search(r'^!' + node + r' = !\{(.*)\}$', text, re.M).group(1)
        members[node] = {int(off): nm for off, sz, t, nm in re.findall(r'i32 (\d+), i32 (\d+), i32 \d+, !"([^"]+)", !"([^"]+)"', body)}
    return args, members


def struct_layout(text):
    """LLVM struct type name -> byte offset of each member (gep index -> offset), sizes computed recursively so that
    padding members ([N x i8]) and nested matrix structs are accounted for."""
    decls = {m.group(1): (m.group(2) == '<', m.group(3)) for m in
             re.finditer(r'^(%"struct\.[^"]+") = type (<?)\{ (.*?) \}>?$', text, re.M)}
    base = {'float': 4, 'half': 2, 'i32': 4, 'i16': 2, 'i8': 1, 'i1': 1, 'i64': 8, 'double': 8}

    def split(body):
        out, depth, cur = [], 0, ''
        for ch in body:
            if ch in '<[{(': depth += 1
            if ch in '>]})': depth -= 1
            if ch == ',' and depth == 0:
                out.append(cur.strip()); cur = ''
            else:
                cur += ch
        if cur.strip():
            out.append(cur.strip())
        return out

    def size_align(t):
        t = t.strip()
        if t in base:
            return base[t], base[t]
        m = re.match(r'<(\d+) x (.+)>$', t)
        if m:
            n, (sz, al) = int(m.group(1)), size_align(m.group(2))
            n2 = 4 if n == 3 else n          # float3 / half3 occupy 4 lanes
            return n2 * sz, n2 * sz
        m = re.match(r'\[(\d+) x (.+)\]$', t)
        if m:
            n, (sz, al) = int(m.group(1)), size_align(m.group(2))
            return n * sz, al
        if t in decls:
            packed, body = decls[t]
            off, maxal = 0, 1
            for mem in split(body):
                sz, al = size_align(mem)
                if not packed:
                    off = (off + al - 1) // al * al
                off += sz; maxal = max(maxal, al)
            if not packed:
                off = (off + maxal - 1) // maxal * maxal
            return off, (1 if packed else maxal)
        return 4, 4

    out = {}
    for name, (packed, body) in decls.items():
        offs, off = [], 0
        for mem in split(body):
            sz, al = size_align(mem)
            if not packed:
                off = (off + al - 1) // al * al
            offs.append(off); off += sz
        out[name] = offs
    return out


def main(argv):
    text = open(argv[1]).read()
    args, members = parse_struct_info(text)
    layouts = struct_layout(text)
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('define '):
            m = re.match(r'define ([^@]*)@"?([^"(]+)"?\(', line)
            head, name = m.group(1), m.group(2)
            j = m.end()
            depth, k = 1, j
            while depth:
                depth += {'(': 1, ')': -1}.get(line[k], 0); k += 1
            params = line[j:k - 1]
            body = []
            i += 1
            while i < len(lines) and lines[i] != '}':
                body.append(lines[i]); i += 1
            if '--all' in argv or 'internal' not in head:
                emit(name, params, '\n'.join(body), args, members, layouts)
        i += 1


def emit(name, params, body, args, members, layouts):
    # parameter %N -> arg name
    pnames = {}
    depth, cur, plist = 0, '', []
    for ch in params:
        if ch in '(<[': depth += 1
        if ch in ')>]': depth -= 1
        if ch == ',' and depth == 0:
            plist.append(cur); cur = ''
        else:
            cur += ch
    plist.append(cur)
    for i, p in enumerate(plist):
        mm = re.search(r'(%\d+)\s*$', p)
        if mm:
            pnames[mm.group(1)] = args.get(i, (f'arg{i}',))[0]
    uses = Counter(re.findall(r'%\d+', body))
    for mm in re.finditer(r'^\s*(%\d+) = ', body, re.M):
        uses[mm.group(1)] -= 1
    defs = {}
    order = []
    for line in body.splitlines():
        m = re.match(r'\s*(%\d+) = (.*)$', line)
        if m:
            defs[m.group(1)] = m.group(2); order.append(m.group(1))
    named = {}      # ssa -> pseudo text

    def val(v):
        v = v.strip()
        if v in pnames:
            return pnames[v]
        if v in named:
            return named[v]
        if v in defs:
            return '(' + expr(defs[v]) + ')'
        m = re.match(r'(?:half|float|double|i32|i64|i8|i1) (.+)$', v)
        if m:
            v = m.group(1)
        import struct as st
        m = re.match(r'0xH([0-9A-Fa-f]{4})\b', v)
        if m:
            return v.replace(m.group(0), str(round(st.unpack('>e', bytes.fromhex(m.group(1)))[0], 4)))
        m = re.match(r'0x([0-9A-Fa-f]{16})\b', v)
        if m:
            return v.replace(m.group(0), str(round(st.unpack('>d', bytes.fromhex(m.group(1)))[0], 6)))
        v = re.sub(r'(?<![\w.])0xH([0-9A-Fa-f]{4})', lambda mm: str(round(st.unpack('>e', bytes.fromhex(mm.group(1)))[0], 4)), v)
        v = re.sub(r'(?<![\w.])0x([0-9A-Fa-f]{16})(?![0-9A-Fa-f])', lambda mm: str(round(st.unpack('>d', bytes.fromhex(mm.group(1)))[0], 6)), v)
        return v.replace('splat (', 'splat(')

    def operands(s):
        # split on top-level commas
        out, depth, cur = [], 0, ''
        for ch in s:
            if ch in '(<[': depth += 1
            if ch in ')>]': depth -= 1
            if ch == ',' and depth == 0:
                out.append(cur); cur = ''
            else:
                cur += ch
        out.append(cur)
        return [o.strip() for o in out]

    def expr(d):
        d = re.sub(r', !\w+ ![^,]+', '', d)
        d = re.sub(r' #\d+$', '', d)
        m = re.match(r'(fadd|fsub|fmul|fdiv|add|sub|mul|and|or|xor|shl|lshr) (?:fast |nsw |nuw )*(?:<\d+ x \w+>|\w+) (.+)$', d)
        if m:
            a, b = operands(m.group(2))
            op = {'fadd': '+', 'fsub': '-', 'fmul': '*', 'fdiv': '/', 'add': '+', 'sub': '-', 'mul': '*', 'and': '&', 'or': '|', 'xor': '^', 'shl': '<<', 'lshr': '>>'}[m.group(1)]
            return f'{val(a)} {op} {val(b)}'
        m = re.match(r'fneg (?:fast )?(?:<\d+ x \w+>|\w+) (.+)$', d)
        if m:
            return f'-{val(m.group(1))}'
        m = re.match(r'(?:tail )?call (?:fast )?[^@]*@"?([^"(]+)"?\((.*)\)$', d)
        if m:
            f = m.group(1).replace('air.', '')
            f = re.sub(r'\.(v\d+)?f(16|32)$', '', f).replace('fast_', '')
            ops = [val(re.sub(r'^(?:<\d+ x \w+>|\w+|ptr addrspace\(\d+\)) (?:noundef )?', '', o)) for o in operands(m.group(2))] if m.group(2).strip() else []
            if f.startswith('sample_texture_2d') or f.startswith('sample_depth_2d'):
                return f'sample({ops[0]}, {ops[-4] if len(ops) > 4 else ops[-1]})'
            if f.startswith('convert.'):
                return ops[0]
            return f'{f}({", ".join(ops)})'
        m = re.match(r'load (?:<\d+ x \w+>|\w+|ptr), (?:ptr addrspace\(\d+\)|ptr) (.+)$', d)
        if m:
            src = operands(m.group(1))[0]
            return 'load(' + val(src) + ')'
        m = re.match(r'getelementptr inbounds (%"struct\.[^"]+"(?:\.\d+)?), ptr addrspace\(2\) (%\d+), i64 0, i32 (\d+)(?:, i64 (\d+))?', d)
        if m:
            stn, base, idx = m.group(1), m.group(2), int(m.group(3))
            offs = layouts.get(stn) or []
            off = offs[idx] if idx < len(offs) else None
            aname = pnames.get(base, base)
            info = next((a for a in args.values() if a[0] == aname), None)
            mem = members.get(info[2], {}) if info and info[2] else {}
            field = mem.get(off, f'[{off}]') if off is not None else f'[{idx}]'
            return f'{aname}.{field}' + (f'[{m.group(4)}]' if m.group(4) else '')
        m = re.match(r'getelementptr inbounds \(?(.+)$', d)
        if m:
            return 'gep(' + m.group(1)[:60] + ')'
        m = re.match(r'(fptrunc|fpext|sitofp|uitofp|fptosi|fptoui|zext|sext|trunc|bitcast) (?:<\d+ x \w+>|\w+) (.+) to .+$', d)
        if m:
            return val(m.group(2))
        m = re.match(r'shufflevector (?:<\d+ x \w+>) (.+?), (?:<\d+ x \w+>) (.+?), <\d+ x i32> <(.+)>$', d)
        if m:
            idx = re.findall(r'i32 (\d+|poison)', m.group(3))
            sw = ''.join(('xyzw' + 'ABCDEFGHIJKL')[int(i)] if i != 'poison' and int(i) < 16 else '_' for i in idx)
            if all(i == idx[0] for i in idx):
                return f'{val(m.group(1))}.{sw[0]}'
            return f'{val(m.group(1))}.{sw}'
        m = re.match(r'shufflevector (?:<\d+ x \w+>) (.+?), (?:<\d+ x \w+>) (.+?), <\d+ x i32> zeroinitializer$', d)
        if m:
            return f'splat({val(m.group(1))}.x)'
        m = re.match(r'insertelement (?:<\d+ x \w+>) (.+?), (?:\w+) (.+?), i64 (\d+)$', d)
        if m:
            return f'ins({val(m.group(1))}, {val(m.group(2))}@{m.group(3)})'
        m = re.match(r'extractelement (?:<\d+ x \w+>) (.+?), i64 (\d+)$', d)
        if m:
            return f'{val(m.group(1))}.{("xyzw" + "ABCDEFGHIJKL")[int(m.group(2))] if int(m.group(2)) < 16 else m.group(2)}'
        m = re.match(r'(fcmp|icmp) (?:fast )?(\w+) (?:<\d+ x \w+>|\w+) (.+)$', d)
        if m:
            a, b = operands(m.group(3))
            return f'{val(a)} {m.group(2)} {val(b)}'
        m = re.match(r'select (?:fast )?(?:<\d+ x \w+>|\w+) (.+?), (?:<\d+ x \w+>|\w+) (.+?), (?:<\d+ x \w+>|\w+) (.+)$', d)
        if m:
            return f'({val(m.group(1))} ? {val(m.group(2))} : {val(m.group(3))})'
        m = re.match(r'phi (?:<\d+ x \w+>|\w+) (.+)$', d)
        if m:
            return 'phi(' + ', '.join(f'{val(a)} from %{b}' for a, b in re.findall(r'\[ (.+?), %(\d+) \]', m.group(1))) + ')'
        return d[:90]

    out = []
    for v in order:
        if uses[v] > 1 or defs[v].startswith('phi') or 'call' in defs[v] and 'sample' in defs[v] or len(expr(defs[v])) > 160:
            named[v] = f't{v[1:]}'
    def tidy(t):
        t = re.sub(r'splat\(\(ins\(poison, (.+?)@0\)\)\.x\)', r'\1', t)
        t = re.sub(r'load\(\(([^()]+)\)\)', r'\1', t)
        t = re.sub(r'\(\(([^()]+)\)\)', r'(\1)', t)
        t = t.replace('0.000000e+00', '0').replace('1.000000e+00', '1').replace('half 0xH3C00', '1.0').replace('splat(1.0)', '1.0')
        return t
    out.append(f'== {name}')
    for line in body.splitlines():
        m = re.match(r'\s*(%\d+) = (.*)$', line)
        if m:
            if m.group(1) in named:
                out.append(tidy(f'  {named[m.group(1)]} = {expr(m.group(2))}'))
            continue
        m = re.match(r'^(\d+):', line)
        if m:
            out.append(f' block {m.group(1)}:'); continue
        if line.strip().startswith('br ') or line.strip().startswith('ret ') or line.strip().startswith('store') or 'discard' in line:
            s = line.strip()
            s = re.sub(r'%\d+', lambda mm: val(mm.group(0)), s)
            out.append(tidy('  ' + s[:300]))
    print('\n'.join(out))
    print()


if __name__ == '__main__':
    main(sys.argv)
