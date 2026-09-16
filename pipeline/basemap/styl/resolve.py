"""Resolve a GeoCSS style's cascade: inherited styles (depth-first, parents first, later parents override earlier),
then the style's own base set, then its zoom-banded sets.  Conditional styles are ignored (Light/Dark/Explore/JPN
variants are separate leaf styles, so the remaining conditions are Muted/IncreaseContrast/etc.).

Zoom semantics (assumed from gss::RenderStyle::hasValueForKeyAtZAtEnd): for a property at zoom z the last cascade
entry whose band covers z (zmin <= z < zmax) wins; base-set values are the fallback.
"""
from styl_decode import decode


class Resolver:
    def __init__(self, path):
        self.ch, self.info, self.ps, self.st = decode(path)
        self.sets = self.ps['sets']
        self.styles = self.st['styles']
        self.by_name = {s['name']: s for s in self.styles}

    def chain(self, name, seen=None):
        """Cascade order: ancestors first (depth-first), self last."""
        seen = seen if seen is not None else set()
        s = self.by_name[name]
        out = []
        for i in s['inherits']:
            p = self.styles[i]['name']
            if p not in seen:
                seen.add(p)
                out += self.chain(p, seen)
        out.append(name)
        return out

    def entries(self, name):
        """[(style, zmin, zmax, props{pid: value})] in cascade order; base sets get zmin=None."""
        out = []
        for n in self.chain(name):
            s = self.by_name[n]
            out.append((n, None, None, {p['id']: p['value'] for p in self.sets[s['psi']]}))
            for z in s['zoom']:
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
