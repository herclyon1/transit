"""Minimal shapefile (.shp/.dbf) reader and Douglas-Peucker simplifier for the
Natural Earth inputs — no GDAL / pyshp on this machine.

Shapes come back as (shape_type, [rings/points], record_dict). Polygons are lists
of rings (numpy (n,2) arrays, x=lng y=lat); points are a (2,) array.
"""
import struct

import numpy as np


def read_dbf(path):
    d = open(path, "rb").read()
    n_rec, hdr_len, rec_len = struct.unpack("<IHH", d[4:12])
    fields, pos = [], 32
    while d[pos] != 0x0D:
        name = d[pos:pos + 11].split(b"\0")[0].decode("latin1")
        ftype = chr(d[pos + 11])
        flen = d[pos + 16]
        fields.append((name, ftype, flen))
        pos += 32
    recs = []
    pos = hdr_len
    for _ in range(n_rec):
        rec = d[pos:pos + rec_len]
        pos += rec_len
        if rec[0:1] == b"*":
            recs.append(None)
            continue
        off, row = 1, {}
        for name, ftype, flen in fields:
            raw = rec[off:off + flen]
            off += flen
            raw = raw.rstrip(b"\0 ")   # NE pads some text fields with NULs instead of spaces
            try:
                txt = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                txt = raw.decode("latin1").strip()
            if ftype in "NF":
                try:
                    row[name] = float(txt) if ("." in txt or "e" in txt.lower()) else int(txt)
                except ValueError:
                    row[name] = None
            else:
                row[name] = txt
        recs.append(row)
    return recs


def read_shp(path):
    d = open(path, "rb").read()
    pos, out = 100, []
    while pos < len(d):
        _, clen = struct.unpack(">ii", d[pos:pos + 8]); pos += 8
        end = pos + clen * 2
        st = struct.unpack("<i", d[pos:pos + 4])[0]
        if st == 5:  # polygon
            nparts, npts = struct.unpack("<ii", d[pos + 36:pos + 44])
            parts = struct.unpack(f"<{nparts}i", d[pos + 44:pos + 44 + 4 * nparts])
            off = pos + 44 + 4 * nparts
            xy = np.frombuffer(d, dtype="<f8", count=2 * npts, offset=off).reshape(npts, 2)
            rings = [xy[parts[i]:(parts[i + 1] if i + 1 < nparts else npts)] for i in range(nparts)]
            out.append(("polygon", rings))
        elif st == 1:  # point
            out.append(("point", np.frombuffer(d, dtype="<f8", count=2, offset=pos + 4)))
        elif st == 0:
            out.append(("null", None))
        else:
            out.append((f"type{st}", None))
        pos = end
    return out


def read_layer(base):
    shapes = read_shp(base + ".shp")
    recs = read_dbf(base + ".dbf")
    assert len(shapes) == len(recs), (len(shapes), len(recs))
    return [(s[0], s[1], r) for s, r in zip(shapes, recs)]


def dp(points, tol):
    """Iterative Douglas-Peucker on an (n,2) array; keeps endpoints."""
    n = len(points)
    if n <= 4:
        return points
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    tol2 = tol * tol
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg = points[a:b + 1]
        p0, p1 = seg[0], seg[-1]
        v = p1 - p0
        L2 = float(v @ v)
        if L2 == 0:
            d2 = ((seg - p0) ** 2).sum(1)
        else:
            t = np.clip(((seg - p0) @ v) / L2, 0, 1)
            proj = p0 + t[:, None] * v
            d2 = ((seg - proj) ** 2).sum(1)
        i = int(d2.argmax())
        if d2[i] > tol2:
            keep[a + i] = True
            stack.append((a, a + i)); stack.append((a + i, b))
    return points[keep]


def ring_area(r):
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def simplify_polygon(rings, tol, min_area):
    """Simplify each ring; drop rings smaller than min_area (deg^2) after simplification."""
    out = []
    for r in rings:
        s = dp(r, tol)
        if len(s) < 4:
            continue
        if not np.array_equal(s[0], s[-1]):
            s = np.vstack([s, s[:1]])
        if abs(ring_area(s)) < min_area:
            continue
        out.append(s)
    return out


def rings_to_geojson_polygons(rings, decimals=3):
    """Shapefile ring list -> GeoJSON MultiPolygon coordinates. Shapefile outer rings are
    clockwise, holes counter-clockwise; assign each hole to the outer ring that contains its
    first vertex (bbox test then even-odd on that ring)."""
    outers, holes = [], []
    for r in rings:
        (outers if ring_area(r) < 0 else holes).append(r)   # shapefile: CW (negative area) = outer
    polys = [[o] for o in outers]
    for h in holes:
        p = h[0]
        placed = False
        for i, o in enumerate(outers):
            if o[:, 0].min() <= p[0] <= o[:, 0].max() and o[:, 1].min() <= p[1] <= o[:, 1].max() and point_in_ring(p, o):
                polys[i].append(h); placed = True; break
        if not placed and outers:
            polys[0].append(h)
    def fmt(r):
        return [[round(float(x), decimals), round(float(y), decimals)] for x, y in r[::-1]]  # GeoJSON wants CCW outer
    return [[fmt(o)] + [fmt(h) for h in hs] for o, *hs in polys]


def point_in_ring(p, ring):
    x, y = p
    xs, ys = ring[:, 0], ring[:, 1]
    x1, y1 = xs[:-1], ys[:-1]; x2, y2 = xs[1:], ys[1:]
    cond = (y1 > y) != (y2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xint = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
    return bool((cond & (x < xint)).sum() % 2)
