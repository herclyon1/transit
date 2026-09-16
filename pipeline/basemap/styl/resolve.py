"""Resolve a GeoCSS style's cascade: inherited styles (depth-first, parents first, later parents override earlier),
then the style's own base set, then its zoom-banded sets, then the conditional sets whose conditions hold in the
given context.

Diamond inheritance (v6, RENDER-PIPELINE §7.15): a base reachable through two parents is placed at its *last*
occurrence, so the chain of the later parent overrides — this is what puts Line-LowZoom-Connection-Base (through
Roads-Localized-JPN-Base) after the JPN width tables and gives the 0.5 px expressway at Apple z6-7 that the Mac draws.
The old behaviour (first occurrence) is `Resolver(path, diamond='first')`.

Conditions: each conditional set carries [{attr, values}]; attr >= 65536 is a client attribute (65536 + id, e.g.
65605 = client:69 map style, 65537 = client:1 TimePeriod), otherwise a feature attribute (4 = Country, 1 = LineType,
85 = low-zoom connection class ...).  A conditional set applies when every condition is satisfied by `context`
({'client': {id: value}, 'feature': {id: value}}); a condition on an attribute the context does not know is treated as
not satisfied (the set is skipped), so unknown feature classes fall back to the unconditional rows.

Zoom semantics (assumed from gss::RenderStyle::hasValueForKeyAtZAtEnd): for a property at zoom z the last cascade
entry whose band covers z (zmin <= z < zmax) wins; base-set values are the fallback.
"""
from styl_decode import decode

CLIENT_BASE = 65536


class Resolver:
    def __init__(self, path, context=None, diamond='last'):
        self.ch, self.info, self.ps, self.st = decode(path)
        self.sets = self.ps['sets']
        self.styles = self.st['styles']
        self.by_name = {s['name']: s for s in self.styles}
        self.context = context or {}
        self.diamond = diamond

    def _walk(self, name, out):
        s = self.by_name[name]
        for i in s['inherits']:
            self._walk(self.styles[i]['name'], out)
        out.append(name)

    def chain(self, name):
        """Cascade order: ancestors first (depth-first), self last; a name met more than once keeps its last position
        (diamond='last') or its first (diamond='first')."""
        raw = []
        self._walk(name, raw)
        if self.diamond == 'first':
            seen, out = set(), []
            for n in raw:
                if n not in seen:
                    seen.add(n); out.append(n)
            return out
        last = {n: i for i, n in enumerate(raw)}
        return [n for i, n in enumerate(raw) if last[n] == i]

    def satisfied(self, conditions):
        for c in conditions:
            a = c['attr']
            if a >= CLIENT_BASE:
                v = self.context.get('client', {}).get(a - CLIENT_BASE)
            else:
                v = self.context.get('feature', {}).get(a)
            if v is None or v not in c['values']:
                return False
        return True

    def entries(self, name):
        """[(style, zmin, zmax, props{pid: value})] in cascade order; base sets get zmin=None.  Conditional sets that
        hold in the context follow the style's own sets (base, then zoom bands)."""
        out = []
        for n in self.chain(name):
            s = self.by_name[n]
            out.append((n, None, None, {p['id']: p['value'] for p in self.sets[s['psi']]}))
            for z in s['zoom']:
                out.append((n, z['zmin'], z['zmax'], {p['id']: p['value'] for p in self.sets[z['psi']]}))
            for c in s.get('conditional', []):
                if not self.satisfied(c['conditions']):
                    continue
                if c.get('psi'):
                    out.append((n, None, None, {p['id']: p['value'] for p in self.sets[c['psi']]}))
                for z in c.get('zoom', []):
                    out.append((n, z['zmin'], z['zmax'], {p['id']: p['value'] for p in self.sets[z['psi']]}))
        return out

    def value_at(self, name, pid, z):
        v = None
        for n, zmin, zmax, props in self.entries(name):
            if pid not in props:
                continue
            if zmin is None or zmin <= z < zmax:
                v = props[pid]
        return v

    def bands(self, name, pid):
        """Piecewise-constant value of `pid` over zoom: [(zmin, zmax, value)] with exact band edges, base as fallback."""
        edges = {0.0, 24.0}
        for n, zmin, zmax, props in self.entries(name):
            if pid in props and zmin is not None:
                edges.update((zmin, zmax))
        edges = sorted(edges)
        out = []
        for a, b in zip(edges, edges[1:]):
            v = self.value_at(name, pid, a)
            if out and out[-1][2] == v and out[-1][1] == a:
                out[-1] = (out[-1][0], b, v)
            else:
                out.append((a, b, v))
        return out

    def props_at(self, name, z):
        out = {}
        for n, zmin, zmax, props in self.entries(name):
            if zmin is None or zmin <= z < zmax:
                out.update(props)
        return out


if __name__ == '__main__':
    import sys
    r = Resolver(sys.argv[1])
    for name in sys.argv[2:]:
        print('==', name, '<-', ' <- '.join(r.chain(name)[:-1]))
        for pid, label in ((0, 'visible'), (1, 'fillColor'), (2, 'strokeColor'), (3, 'width'), (6, 'strokeWidth'), (13, 'renderOrder'), (172, 'labelInfo'), (24, 'textColor'), (25, 'haloColor'), (21, 'fontSize'), (23, 'font')):
            b = [(a, c, v) for a, c, v in r.bands(name, pid) if v is not None]
            if b:
                print(f'   {label:12s}', '; '.join(f'z{a:g}-{c:g}: {v}' for a, c, v in b))
