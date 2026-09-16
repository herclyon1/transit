#!/usr/bin/env python3
"""Minimal Mapbox Vector Tile (protobuf) reader / rewriter, no dependencies: read a tile's layers, features and tags, and
write the tile back with extra tags on chosen features while every other byte (geometry, ids, unknown fields) is copied
verbatim.  Used by rail_name_en.py to add `name_en` to tiles/transit.pmtiles without tippecanoe (the tile source lives on
another machine; the archive itself is the only copy here).

MVT spec 2.1: Tile{ repeated Layer layers = 3 }, Layer{ version=15, name=1, repeated Feature features=2, repeated string
keys=3, repeated Value values=4, extent=5 }, Feature{ id=1, packed uint32 tags=2, type=3, packed uint32 geometry=4 },
Value{ string=1, float=2, double=3, int=4, uint=5, sint=6, bool=7 }.
"""
import struct


def varint(b, i):
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7f) << s
        if c < 0x80:
            return r, i
        s += 7


def enc_varint(n):
    out = bytearray()
    while True:
        c = n & 0x7f
        n >>= 7
        if n:
            out.append(c | 0x80)
        else:
            out.append(c)
            return bytes(out)


def fields(b):
    """Yield (field_no, wire_type, raw_value_bytes_or_int, raw_field_bytes) over a protobuf message."""
    i, n = 0, len(b)
    while i < n:
        start = i
        tag, i = varint(b, i)
        f, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = varint(b, i)
        elif wt == 2:
            ln, i = varint(b, i)
            v = b[i:i + ln]
            i += ln
        elif wt == 1:
            v = b[i:i + 8]
            i += 8
        elif wt == 5:
            v = b[i:i + 4]
            i += 4
        else:
            raise ValueError(f'wire type {wt}')
        yield f, wt, v, b[start:i]


def enc_field(f, wt, v):
    if wt == 0:
        return enc_varint(f << 3) + enc_varint(v)
    return enc_varint((f << 3) | 2) + enc_varint(len(v)) + v


def packed(b):
    out, i = [], 0
    while i < len(b):
        v, i = varint(b, i)
        out.append(v)
    return out


def enc_packed(vals):
    return b''.join(enc_varint(v) for v in vals)


def decode_value(b):
    for f, wt, v, _ in fields(b):
        if f == 1:
            return v.decode('utf-8')
        if f == 2:
            return struct.unpack('<f', v)[0]
        if f == 3:
            return struct.unpack('<d', v)[0]
        if f in (4, 5):
            return v
        if f == 6:
            return (v >> 1) ^ -(v & 1)
        if f == 7:
            return bool(v)
    return None


def enc_value(v):
    if isinstance(v, bool):
        return enc_field(7, 0, int(v))
    if isinstance(v, int):
        return enc_field(4, 0, v) if v >= 0 else enc_field(6, 0, (v << 1) ^ (v >> 63))
    if isinstance(v, float):
        return enc_varint((3 << 3) | 1) + struct.pack('<d', v)
    return enc_field(1, 2, str(v).encode('utf-8'))


class Layer:
    def __init__(self, raw):
        self.raw = raw
        self.name = None
        self.keys, self.values, self.features = [], [], []   # features: [raw feature bytes]
        for f, wt, v, _ in fields(raw):
            if f == 1:
                self.name = v.decode('utf-8')
            elif f == 2:
                self.features.append(v)
            elif f == 3:
                self.keys.append(v.decode('utf-8'))
            elif f == 4:
                self.values.append(decode_value(v))

    def props(self, feat):
        """Property dict of a raw feature."""
        for f, wt, v, _ in fields(feat):
            if f == 2:
                t = packed(v)
                return {self.keys[t[i]]: self.values[t[i + 1]] for i in range(0, len(t), 2)}
        return {}

    def rewrite(self, add):
        """add(props) -> dict of extra properties (or None); returns new layer bytes with keys/values appended as needed."""
        kidx = {k: i for i, k in enumerate(self.keys)}
        vidx = {}
        for i, v in enumerate(self.values):
            vidx.setdefault((type(v).__name__, v), i)
        new_keys, new_vals = [], []                 # appended after the layer's own keys / values (order kept = byte-exact roundtrip)
        feats = []
        changed = 0
        for ft in self.features:
            extra = add(self.props(ft))
            if not extra:
                feats.append(None)
                continue
            changed += 1
            fb = bytearray()
            for ff, wwt, vv, rraw in fields(ft):
                if ff != 2:
                    fb += rraw
                    continue
                t = packed(vv)
                for k, val in extra.items():
                    if k not in kidx:
                        kidx[k] = len(self.keys) + len(new_keys)
                        new_keys.append(k)
                    key = (type(val).__name__, val)
                    if key not in vidx:
                        vidx[key] = len(self.values) + len(new_vals)
                        new_vals.append(val)
                    t += [kidx[k], vidx[key]]
                fb += enc_field(2, 2, enc_packed(t))
            feats.append(bytes(fb))
        out = bytearray()
        fi = ki = vi = 0
        for f, wt, v, raw in fields(self.raw):
            if f == 2:
                nb = feats[fi]
                fi += 1
                out += raw if nb is None else enc_field(2, 2, nb)
            elif f == 3:
                out += raw
                ki += 1
                if ki == len(self.keys):
                    for k in new_keys:
                        out += enc_field(3, 2, k.encode('utf-8'))
            elif f == 4:
                out += raw
                vi += 1
                if vi == len(self.values):
                    for val in new_vals:
                        out += enc_field(4, 2, enc_value(val))
            else:
                out += raw
        if not self.keys:
            for k in new_keys:
                out += enc_field(3, 2, k.encode('utf-8'))
        if not self.values:
            for val in new_vals:
                out += enc_field(4, 2, enc_value(val))
        return bytes(out), changed


def read_tile(b):
    return [Layer(v) for f, wt, v, _ in fields(b) if f == 3]


def write_tile(b, layer_bytes):
    """Re-emit the tile with layer i replaced by layer_bytes[i] (None keeps the original bytes)."""
    out, i = bytearray(), 0
    for f, wt, v, raw in fields(b):
        if f == 3:
            nb = layer_bytes[i]
            out += raw if nb is None else enc_field(3, 2, nb)
            i += 1
        else:
            out += raw
    return bytes(out)
