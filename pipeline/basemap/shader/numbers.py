#!/usr/bin/env python3
"""Build basemap/data/shader/shader-numbers.json from capture.m output directories.

    numbers.py --light cap-globe --dark cap-dark [--zoomed cap-pitch] -o basemap/data/shader/shader-numbers.json

Everything numeric in the JSON is copied from the captured uniform buffers / textures (see capture.m) or from
groundSettings.json; the formulas and the decompile-derived constants are documented in SHADER-NUMBERS.md.
Colours in the captured textures and buffers are *linear* RGB (the sheet's sRGB values linearised by VectorKit);
the JSON keeps them linear and adds the sRGB encoding next to them.
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'styl'))

GROUND_SETTINGS = '/System/Library/PrivateFrameworks/VectorKit.framework/Versions/A/Resources/groundSettings.json'
GROUND_SETTINGS_NIGHT = '/System/Library/PrivateFrameworks/VectorKit.framework/Versions/A/Resources/groundSettingsNight.json'


def srgb(c):
    return round((c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055) * 255)


def hexs(rgb):
    return '#%02x%02x%02x' % tuple(rgb)


def lin8_to_srgb_hex(rgb8):
    return hexs([srgb(c / 255) for c in rgb8])


def load(cap):
    return json.load(open(os.path.join(cap, 'capture.json'))), cap


def buffer(d, key, size):
    """first distinct captured blob for a `function|stage|index` key"""
    for r in d['buffers'].get(key, []):
        return bytes.fromhex(r['hex'])[:size]
    return None


def half4(b, off):
    return [round(v, 5) for v in struct.unpack_from('<4e', b, off)]


def half2(b, off):
    return [round(v, 5) for v in struct.unpack_from('<2e', b, off)]


def f32(b, off, n=1):
    v = [round(x, 6) for x in struct.unpack_from('<%df' % n, b, off)]
    return v[0] if n == 1 else v


def texture(d, cap, index, stage='F', fn='DaVinci::ground_fragment'):
    for t in d['textures']:
        if t['function'] == fn and t['stage'] == stage and t['index'] == index and t.get('raw'):
            return t, open(os.path.join(cap, t['raw']), 'rb').read()
    return None, None


def lighting(d):
    v = buffer(d, 'DaVinci::ground_base_vertex|V|5', 16)
    st = buffer(d, 'DaVinci::ground_base_vertex|V|7', 8)
    sm = buffer(d, 'DaVinci::ground_base_vertex|V|8', 4)
    tr = buffer(d, 'DaVinci::ground_base_vertex|V|9', 2)
    L = half4(st, 0)
    import math
    az = (math.degrees(math.atan2(L[0], L[1])) + 360) % 360
    alt = math.degrees(math.asin(L[2] / math.sqrt(L[0] ** 2 + L[1] ** 2 + L[2] ** 2)))
    return {
        'lightColor_linear': half4(v, 0), 'ambientLightColor_linear': half4(v, 8),
        'tileLightDirection': L[:3], 'tileLightDirection_w': L[3],
        'azimuth_deg_clockwise_from_north': round(az, 2), 'altitude_deg': round(alt, 2),
        'sunMatrixCosSin': half2(sm, 0), 'transitionToFlatLighting': round(struct.unpack_from('<e', tr, 0)[0], 5),
        'space': 'tile/view space: x right (east), y up (north), z toward viewer; constant for every zoom, pitch and heading tested',
    }


def ground_atmosphere(d):
    b = buffer(d, 'DaVinci::ground_fragment|F|10', 32)
    fog = half4(b, 16)
    return {
        'skyBottomColor_linear': half4(b, 0), 'skyBottomColor_srgb': lin8_to_srgb_hex([round(c * 255) for c in half4(b, 0)[:3]]),
        'skyTopColor_linear': half4(b, 8), 'skyTopColor_srgb': lin8_to_srgb_hex([round(c * 255) for c in half4(b, 8)[:3]]),
        'fogParameters': [None if v != v or v in (float('inf'), float('-inf')) else v for v in fog] if any(v in (float('inf'), float('-inf')) for v in fog) else fog,
        'fogParameters_raw': ['-inf' if v == float('-inf') else 'inf' if v == float('inf') else v for v in fog],
        'horizonGlowParameters': half2(b, 24),
    }


def gradient(d, cap):
    p = buffer(d, 'DaVinci::ground_fragment|F|14', 32)
    t, raw = texture(d, cap, 11)
    tex = [raw[i * 4:i * 4 + 4] for i in range(t['width'])]
    return {
        'depthGradientScale': f32(p, 0), 'depthGradientOffset': f32(p, 4), 'blendFactor': f32(p, 8), 'blendColor': f32(p, 16, 4),
        'lookup': 't = saturate((log2(waterDepth_m) + depthGradientOffset) * depthGradientScale); colour = gradient1Texture[t]',
        'texture_width': t['width'], 'pixelFormat': 'RGBA8Unorm (linear)',
        'texels_linear_rgba8': [list(x) for x in tex],
        'texels_srgb_hex': [lin8_to_srgb_hex(x[:3]) for x in tex],
        'depth_m_at_t': {str(i): round(2 ** (i / (t['width'] - 1) / f32(p, 0) - f32(p, 4)), 3) for i in range(0, t['width'], 32)},
    }


def irradiance(d, cap):
    t, raw = texture(d, cap, 0, 'V', 'DaVinci::ground_base_vertex')
    w, h = t['width'], t['height']
    faces = []
    for s in range(6):
        face = []
        for y in range(h):
            row = []
            for x in range(w):
                o = ((s * h + y) * w + x) * 4
                row.append(hexs(raw[o:o + 3]))
            face.append(row)
        faces.append(face)
    avg = []
    for s in range(6):
        vals = [raw[((s * h + y) * w + x) * 4 + c] for y in range(h) for x in range(w) for c in range(3)]
        avg.append(round(sum(vals) / len(vals) / 255, 4))
    return {'size': [w, h], 'faces_order': ['+x', '-x', '+y', '-y', '+z', '-z'], 'pixelFormat': 'RGBA8Unorm (linear)',
            'face_mean': avg, 'faces_hex': faces,
            'use': 'indirect = ambient_cube.sample(normal).rgb * ambientLightColor'}


def palettes(d, cap):
    """every distinct 9-cell class palette seen in this capture: base (row 1, col 1) + the 3x3 climate cells"""
    out = {}
    for t in d['textures']:
        if t['function'] != 'DaVinci::ground_fragment' or t['stage'] != 'F' or t['index'] != 8 or not t.get('raw'):
            continue
        raw = open(os.path.join(cap, t['raw']), 'rb').read()
        w, h = t['width'], t['height']
        for i in range(h // 3):
            cells = []
            for a in range(3):
                row = []
                for tt in range(3):
                    o = ((3 * i + a) * w + tt) * 4
                    row.append(list(raw[o:o + 4]))
                cells.append(row)
            base = cells[1][1]
            key = hexs(base[:3]) + ('/a0' if base[3] == 0 else '')
            if key in out:
                continue
            out[key] = {'base_linear_rgba8': base, 'base_srgb': lin8_to_srgb_hex(base[:3]) if base[3] else 'transparent (water: depth gradient instead)',
                        'tinted': len({tuple(c) for r in cells for c in r}) > 1,
                        'cells_linear_hex[aridity: wet, base, dry][temperature: arctic, base, hot]': [[hexs(c[:3]) for c in r] for r in cells]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--light', required=True)
    ap.add_argument('--dark')
    ap.add_argument('--zoomed', help='a capture at z>=8 (different groundSettings band)')
    ap.add_argument('-o', '--out', required=True)
    a = ap.parse_args()
    dl, cl = load(a.light)
    out = {
        'what': 'Constants and lookup textures VectorKit binds to its DaVinci ground / globe shaders, captured in-process from MKMapView (realistic elevation) with pipeline/basemap/shader/capture.m; formulas in SHADER-NUMBERS.md',
        'colour_space': 'linear RGB unless a key says _srgb; the render target is sRGB so shader output is encoded on write',
        'lighting': lighting(dl),
        'ground_atmosphere': {'light': ground_atmosphere(dl)},
        'water_depth_gradient': {'light': gradient(dl, cl)},
        'ambient_irradiance_cube': irradiance(dl, cl),
        'landCoverSettings': {'maxIndex': f32(buffer(dl, 'DaVinci::ground_fragment|F|6', 4), 0)},
        'climate_tinting': {
            'groundSettings.json': json.load(open(GROUND_SETTINGS)),
            'groundSettingsNight.json': json.load(open(GROUND_SETTINGS_NIGHT)),
            'palette_layout': 'styleTexture is 3 columns x (3 * classes) rows; column = temperature (arctic, base, veryHot), row within a class = aridity (veryWet, base, veryDry); cell = HSV(base_linear) + temperatureAdjustment + aridityAdjustment (hue deg, sat, val; additive, clamped); zoom band from groundSettings.json keyed by tile zoom; untinted classes repeat the base in all 9 cells',
            'texture_lookup': 'u = ((temperatureTexture.r - 3/255) * 85 + 1.5) / width; v = (index * 3 + 1.5 + (aridityTexture.r >= 3/255 ? 127.5 : 85) * (aridityTexture.r - 3/255)) / height; index = rint(styleIndexTexture.r * maxIndex); temperature codes 0/3/6 -> columns 0/1/2, aridity codes 0/3/5 -> rows 0/1/2, intermediate codes interpolate',
            'verified': 'HSV model reproduces every tinted cell of the captured palettes within 2/255',
        },
        'landcover_palettes': {'light_z5': palettes(dl, cl)},
    }
    if a.dark:
        dd, cd = load(a.dark)
        out['ground_atmosphere']['dark'] = ground_atmosphere(dd)
        out['water_depth_gradient']['dark'] = gradient(dd, cd)
        out['landcover_palettes']['dark_z5'] = palettes(dd, cd)
        out['lighting_dark'] = lighting(dd)
    if a.zoomed:
        dz, cz = load(a.zoomed)
        out['landcover_palettes']['light_z8'] = palettes(dz, cz)
    json.dump(out, open(a.out, 'w'), indent=1, ensure_ascii=False)
    print('wrote', a.out)


if __name__ == '__main__':
    main()
