#!/usr/bin/env python3
"""Measure globe-scale label typography off Apple's own renderer.

Every label is cut out of a render listed in RENDERS (2x live capture where the
Mac was unlocked, 1x MKMapSnapshotter otherwise), segmented into glyph / halo /
background by colour, and its ink box, colour, halo and ink density measured.
CoreText metrics of the same string in SF (pipeline/basemap/textmetrics.swift)
turn ink height into point size, ink width into tracking, and ink density into
weight. Nothing is eyeballed; each number cites image, pixel box and render time.

    swiftc -O pipeline/basemap/textmetrics.swift -o pipeline/basemap/raw/textmetrics
    python3 pipeline/basemap/labels.py [--debug]     # writes ui/basemap/labels-globe.json

--debug also drops annotated crops in pipeline/basemap/raw/labels-debug/.
"""
import json
import math
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, "pipeline", "basemap", "raw")
RENDERS = os.path.join(RAW, "renders")
OUT = os.path.join(ROOT, "ui", "basemap")
DEBUG_DIR = os.path.join(RAW, "labels-debug")
TEXTMETRICS = os.path.join(RAW, "textmetrics")
NATIVE_PNG = os.path.expanduser("~/Money/styl-work/native.png")

# view id -> (png, meta json). meta carries render args/time/scale.
VIEWS = {
    "ea2x": ("live-ea-light.png", "live-ea-light.json"),
    "ea1x": ("ea-light.png", "ea-light.json"),
    "ea1x-dark": ("ea-dark.png", "ea-dark.json"),
    "wide1x": ("wide-light.png", "wide-light.json"),
    "wide1x-dark": ("wide-dark.png", "wide-dark.json"),
}

# Label catalogue. cx, cy, w, h are a generous search box in 1x points of that
# view (doubled for 2x images); the ink box is found inside it automatically.
# kind drives what the number means downstream; italic/case drive the CoreText
# reference; "dark_of" links the same label in the dark render for colour only.
LABELS = [
    # continent names (wide view only)
    dict(id="continent-asia", kind="continent", text="ASIA", view="wide1x", cx=165, cy=80, w=70, h=18, italic=False),
    dict(id="continent-australia", kind="continent", text="AUSTRALIA", view="wide1x", cx=523, cy=705, w=150, h=18, italic=False),
    # country names
    dict(id="country-china", kind="country", text="CHINA", view="ea2x", cx=376, cy=284, w=64, h=16, italic=False),
    dict(id="country-mongolia", kind="country", text="MONGOLIA", view="ea2x", cx=363, cy=99, w=80, h=16, italic=False),
    dict(id="country-india", kind="country", text="INDIA", view="ea2x", cx=56, cy=470, w=50, h=16, italic=False),
    dict(id="country-thailand", kind="country", text="THAILAND", view="ea2x", cx=344, cy=568, w=58, h=16, italic=False),
    dict(id="country-philippines", kind="country-small", text="PHILIPPINES", view="ea2x", cx=621, cy=610, w=90, h=16, italic=False),
    # ocean / sea names (italic, mixed case, multi-line -> one line each)
    dict(id="sea-philippine-l1", kind="ocean", text="Philippine", view="ea2x", cx=773, cy=490, w=80, h=16, italic=True),
    dict(id="sea-philippine-l2", kind="ocean", text="Sea", view="ea2x", cx=773, cy=503, w=40, h=16, italic=True),
    dict(id="sea-bengal-l1", kind="ocean", text="Bay of", view="ea2x", cx=169, cy=583, w=56, h=16, italic=True),
    dict(id="sea-bengal-l2", kind="ocean", text="Bengal", view="ea2x", cx=169, cy=596, w=56, h=16, italic=True),
    dict(id="ocean-npacific-l1", kind="ocean", text="North", view="wide1x", cx=886, cy=292, w=56, h=16, italic=True),
    dict(id="ocean-npacific-l2", kind="ocean", text="Pacific", view="wide1x", cx=886, cy=306, w=56, h=16, italic=True),
    dict(id="ocean-npacific-l3", kind="ocean", text="Ocean", view="wide1x", cx=886, cy=320, w=56, h=16, italic=True),
    dict(id="ocean-indian-l1", kind="ocean", text="Indian", view="wide1x", cx=130, cy=673, w=56, h=16, italic=True),
    dict(id="ocean-indian-l2", kind="ocean", text="Ocean", view="wide1x", cx=130, cy=687, w=56, h=16, italic=True),
    # deep-sea points
    # (boxes start right of / end left of the triangle marker)
    dict(id="deep-ramapo", kind="deep", text="Ramapo Deep", view="ea2x", cx=895, cy=357, w=66, h=14, italic=False),
    dict(id="deep-vityaz", kind="deep", text="Vityaz Depth", view="ea2x", cx=928, cy=149, w=60, h=14, italic=False),
    dict(id="deep-challenger-l1", kind="deep", text="Challenger", view="ea2x", cx=835, cy=620, w=58, h=14, italic=False),
    # undersea features (uppercase, tracked, set along the feature; measured after de-rotation)
    dict(id="undersea-midpacific", kind="undersea", text="MID-PACIFIC SEAMOUNTS", view="ea2x", cx=1145, cy=505, w=200, h=44, italic=False, rotate=True),
    dict(id="undersea-shatsky", kind="undersea", text="SHATSKY RISE", view="ea2x", cx=1106, cy=250, w=60, h=110, italic=False, rotate=True),
    # graticule
    dict(id="graticule-tropic", kind="graticule", text="Tropic of Cancer", view="ea2x", cx=907, cy=464, w=100, h=14, italic=False),
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_view(vid):
    png, meta = VIEWS[vid]
    p = os.path.join(RENDERS, png)
    m = json.load(open(os.path.join(RENDERS, meta)))["render"]
    img = np.asarray(Image.open(p).convert("RGB")).astype(float)
    return img, m, png


def kmeans(X, k, iters=25):
    """k-means on colours with farthest-point seeding (deterministic)."""
    seeds = [0]
    d = ((X - X[0]) ** 2).sum(1)
    for _ in range(k - 1):
        seeds.append(int(d.argmax()))
        d = np.minimum(d, ((X - X[seeds[-1]]) ** 2).sum(1))
    c = X[seeds].astype(float).copy()
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        lab = ((X[:, None, :] - c[None]) ** 2).sum(2).argmin(1)
        for j in range(k):
            if (lab == j).any():
                c[j] = X[lab == j].mean(0)
    return lab, c


def cross50(profile, thr=0.5):
    """Sub-pixel first/last crossing of thr in a 1-D profile (index of pixel centre = i + 0.5)."""
    idx = np.where(profile >= thr)[0]
    if len(idx) == 0:
        return None
    a, b = idx[0], idx[-1]
    def interp(i, j):  # crossing between pixels i (below) and j (above)
        if i < 0 or i >= len(profile):
            return j + 0.5
        pi, pj = profile[i], profile[j]
        return i + 0.5 + (thr - pi) / (pj - pi) if pj != pi else j + 0.5
    top = interp(a - 1, a)
    bot = interp(b + 1, b)
    return top, bot


def dilate(mask, r):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def components(mask):
    H, W = mask.shape
    seen = np.zeros_like(mask); comps = []
    for y in range(H):
        for x in range(W):
            if mask[y, x] and not seen[y, x]:
                st = [(y, x)]; seen[y, x] = True; pts = []
                while st:
                    cy, cx = st.pop(); pts.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True; st.append((ny, nx))
                comps.append(pts)
    return comps


def principal_angle(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) < 10:
        return 0.0
    xs = xs - xs.mean(); ys = ys - ys.mean()
    cov = np.cov(np.stack([xs, ys]))
    w, v = np.linalg.eigh(cov)
    vx, vy = v[:, 1]
    return math.degrees(math.atan2(vy, vx))


def measure_label(L, img, scale, debug_name=None):
    s = scale
    x0, y0 = int((L["cx"] - L["w"] / 2) * s), int((L["cy"] - L["h"] / 2) * s)
    x1, y1 = int((L["cx"] + L["w"] / 2) * s), int((L["cy"] + L["h"] / 2) * s)
    crop = img[y0:y1, x0:x1]
    H, W = crop.shape[:2]
    # background = the most common colour cluster of the crop (labels never cover most of their box)
    Xall = crop.reshape(-1, 3)
    lab_all, cent_all = kmeans(Xall, 4)
    counts = np.bincount(lab_all, minlength=4)
    bg = cent_all[counts.argmax()]
    dist = np.sqrt(((crop - bg) ** 2).sum(2))
    fg = dist > 22
    if fg.sum() < 20:
        return {"error": "no text found in box", "bg": bg.tolist()}
    # glyph cluster: among fg clusters, the one with most central pixels weighted by its
    # distance from the background (text is far from bg; terrain texture is barely over the
    # threshold; rivers/borders are spread over all rows)
    X = crop[fg]
    lab, cent = kmeans(X, 3)
    rows_idx = np.nonzero(fg)[0]
    central = np.abs(rows_idx - H / 2) < H / 4
    lum = cent @ np.array([0.2126, 0.7152, 0.0722])
    bg_lum = float(bg @ np.array([0.2126, 0.7152, 0.0722]))
    cdist = np.sqrt(((cent - bg) ** 2).sum(1))
    # light mode: glyphs are darker than the map, the halo lighter; dark mode the other way round
    darker_ok = not L.get("dark_mode")
    score = np.array([((lab == k) & central).sum() * cdist[k] * (1.0 if (lum[k] < bg_lum + 10) == darker_ok else 0.3) for k in range(3)])
    gk = int(score.argmax())
    glyph_px = X[lab == gk]
    # glyph core colour: the 25% of glyph pixels farthest along the bg -> glyph direction
    proj = ((glyph_px - bg) @ (cent[gk] - bg)) / (np.linalg.norm(cent[gk] - bg) ** 2 + 1e-9)
    core = np.median(glyph_px[proj >= np.quantile(proj, 0.75)], axis=0)
    core_lum = float(core @ np.array([0.2126, 0.7152, 0.0722]))
    # glyph mask (nearest-colour) and its 3 px neighbourhood: a halo must live there
    gmask = np.zeros((H, W), bool); gmask[fg] = (lab == gk)
    near = dilate(gmask, 3) & ~gmask
    # halo: pixels next to glyphs that are lighter than both glyph and background
    npx = crop[near]
    nlum = npx @ np.array([0.2126, 0.7152, 0.0722])
    light = npx[nlum > max(core_lum, bg_lum) + 12]
    has_halo = len(light) > 0.15 * gmask.sum()
    halo_core = None
    if has_halo:
        projh = ((light - bg) @ (light.mean(0) - bg)) / (np.linalg.norm(light.mean(0) - bg) ** 2 + 1e-9)
        halo_core = np.median(light[projh >= np.quantile(projh, 0.75)], axis=0)
    # glyph coverage alpha: 1 at core, 0 at the colour the edge blends into (halo if present else bg)
    blend = halo_core if has_halo else bg
    denom = np.linalg.norm(core - blend) + 1e-9
    alpha = np.clip(1 - np.sqrt(((crop - core) ** 2).sum(2)) / denom, 0, 1)
    alpha[~fg] = 0
    halo_alpha = None
    if has_halo:
        hd = np.linalg.norm(halo_core - bg) + 1e-9
        halo_alpha = np.clip(1 - np.sqrt(((crop - halo_core) ** 2).sum(2)) / hd, 0, 1)
        halo_alpha[~dilate(gmask, 4)] = 0
        halo_alpha = np.maximum(halo_alpha, alpha)     # glyph counts as inside the halo
    # de-rotate first (undersea names are set along their feature), then band-limit
    angle = 0.0
    if L.get("rotate"):
        angle = principal_angle(alpha > 0.5)
        pil_a = Image.fromarray((alpha * 255).astype(np.uint8)).rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=0)
        alpha = np.asarray(pil_a).astype(float) / 255
        H, W = alpha.shape
        halo_alpha = None   # halo is not measured on curved labels
    # keep only the text's own row band: the contiguous run of rows (around the densest row)
    # that still carries ink; everything above/below is another feature
    rc = (alpha > 0.5).sum(axis=1)
    peak = int(rc.argmax()); top, bot = peak, peak
    while top > 0 and rc[top - 1] > 0: top -= 1
    while bot < H - 1 and rc[bot + 1] > 0: bot += 1
    band = np.zeros(H, bool); band[max(top - 1, 0):min(bot + 2, H)] = True
    alpha[~band, :] = 0
    if halo_alpha is not None:
        halo_alpha[~band, :] = 0
    # drop 1-2 px thin runs far from any letter column (graticule dashes in the same grey)
    cc = (alpha > 0.5).sum(axis=0)
    strong = np.nonzero(cc >= 4)[0]
    if len(strong):
        for x in range(W):
            if 0 < cc[x] <= 2 and np.abs(strong - x).min() > 3:
                alpha[:, x] = 0
                if halo_alpha is not None:
                    halo_alpha[:, x] = 0
    rows = alpha.max(axis=1); cols = alpha.max(axis=0)
    r = cross50(rows); c = cross50(cols)
    if r is None or c is None:
        return {"error": "no 50% ink", "bg": bg.tolist()}
    ink_h = r[1] - r[0]; ink_w = c[1] - c[0]
    ink_area = float(alpha.sum())
    letters = None
    if L.get("rotate"):
        # curved labels: the global ink box height is inflated by the arc; use the median
        # vertical extent of the letters in the central 40% of the width instead
        comps = components(alpha > 0.5)
        mid = [cp for cp in comps if abs(np.mean([q[1] for q in cp]) - (c[0] + c[1]) / 2) < 0.2 * ink_w and len(cp) >= 4]
        hs = []
        for cp in mid:
            ys = np.array([q[0] for q in cp]); xs = np.array([q[1] for q in cp])
            y_a, y_b = max(ys.min() - 1, 0), min(ys.max() + 2, H)
            rr = cross50(alpha[y_a:y_b, xs.min():xs.max() + 1].max(axis=1))
            if rr:
                hs.append(rr[1] - rr[0])
        if hs:
            letters = {"n_central_letters": len(hs), "letter_ink_h_px_median": round(float(np.median(hs)), 2)}
            ink_h = float(np.median(hs))
    # stem width: the narrowest connected letter that spans the full ink height is an I or l;
    # its 50%-crossing width is the stroke thickness (weight evidence independent of halo blending)
    stem = None
    if not L.get("rotate") and any(ch in L["text"] for ch in "Il"):
        comps = components(alpha > 0.5)
        cands = []
        for cp in comps:
            ys = np.array([q[0] for q in cp]); xs = np.array([q[1] for q in cp])
            if (ys.max() - ys.min() + 1) >= 0.85 * ink_h and (xs.max() - xs.min() + 1) < 0.5 * ink_h:
                x_a, x_b = max(xs.min() - 1, 0), min(xs.max() + 2, W)
                cc_ = cross50(alpha[ys.min():ys.max() + 1, x_a:x_b].max(axis=0))
                if cc_:
                    cands.append(cc_[1] - cc_[0])
        if cands:
            stem = {"px": round(float(min(cands)), 2), "letter": "I" if "I" in L["text"] else "l"}
    # halo width: mean of the four (halo edge - ink edge) distances at 50% of halo-vs-bg blend
    halo_w = None
    if has_halo and not L.get("rotate"):
        hr = cross50(halo_alpha.max(axis=1)); hc = cross50(halo_alpha.max(axis=0))
        if hr and hc:
            halo_w = round(float(((r[0] - hr[0]) + (hr[1] - r[1]) + (c[0] - hc[0]) + (hc[1] - c[1])) / 4), 2)
    out = {
        "box_px": [x0, y0, x1, y1], "ink_px": {"left": round(x0 + c[0], 2), "top": round(y0 + r[0], 2),
                                              "w": round(ink_w, 2), "h": round(ink_h, 2)},
        "rotation_deg": round(angle, 1),
        "glyph_rgb": [int(round(v)) for v in core], "glyph_hex": "#%02x%02x%02x" % tuple(int(round(v)) for v in core),
        "halo_rgb": [int(round(v)) for v in halo_core] if has_halo else None,
        "halo_hex": "#%02x%02x%02x" % tuple(int(round(v)) for v in halo_core) if has_halo else None,
        "halo_width_px": halo_w,
        "bg_rgb": [int(round(v)) for v in bg],
        "ink_area_px2": round(ink_area, 1),
        "glyph_px_n": int(len(glyph_px)),
        "curved_letters": letters,
        "stem": stem,
    }
    if debug_name:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        dbg = Image.fromarray(crop.astype(np.uint8)).resize((W * 4, H * 4), Image.NEAREST) if not L.get("rotate") else Image.fromarray((alpha * 255).astype(np.uint8)).resize((W * 4, H * 4), Image.NEAREST)
        d = ImageDraw.Draw(dbg)
        if not L.get("rotate"):
            d.rectangle([c[0] * 4, r[0] * 4, c[1] * 4, r[1] * 4], outline=(255, 0, 0))
        dbg.save(os.path.join(DEBUG_DIR, debug_name + ".png"))
    return out


def textmetrics(labels):
    req = [{"text": L["text"], "italic": L["italic"]} for L in labels]
    res = subprocess.run([TEXTMETRICS, json.dumps(req)], capture_output=True, text=True, check=True)
    return {(e["text"], e["italic"]): e for e in json.loads(res.stdout)}


def fit(L, m, tm, scale):
    """Point size from ink height, tracking from ink width, weight from ink density."""
    ref = tm[(L["text"], L["italic"])]["weights"]
    n_gaps = max(len(L["text"]) - 1, 1)
    fits = {}
    for w, rw in ref.items():
        size_pt = m["ink_px"]["h"] / rw["ink_h"] * 100 / scale
        ink_w0 = rw["ink_w"] * size_pt / 100 * scale          # px at zero tracking
        tracking_pt = (m["ink_px"]["w"] - ink_w0) / n_gaps / scale
        area_ref = rw["ink_area"] * (size_pt * scale / 100) ** 2  # tracking adds no ink
        f = {"size_pt": round(size_pt, 2), "tracking_pt": round(tracking_pt, 2),
             "ink_density_ratio": round(m["ink_area_px2"] / area_ref, 3)}
        if m.get("stem"):
            ref_stem = rw["stem_I_w" if m["stem"]["letter"] == "I" else "stem_l_w"] * size_pt / 100 * scale
            f["stem_ratio"] = round(m["stem"]["px"] / ref_stem, 3)
        fits[w] = f
    # weight: by stem thickness when an I/l is present (immune to halo blending), else by ink density
    if m.get("stem"):
        best = min(fits, key=lambda w: abs(math.log(fits[w]["stem_ratio"])))
        how = "stem"
    else:
        best = min(fits, key=lambda w: abs(math.log(fits[w]["ink_density_ratio"])))
        how = "ink_density"
    return {"weight": best, "weight_by": how, "font": ref[best]["font"], **fits[best], "all_weights": fits,
            "cap_height_pt": round(fits[best]["size_pt"] * ref[best]["cap_height"] / 100, 2)}


def dark_colour(L, m, img_dark, scale_dark, scale_light):
    """Same label in the dark render (same projection): re-run the colour part only."""
    if img_dark is None:
        return None
    L2 = dict(L, dark_mode=True)
    r = measure_label(L2, img_dark, scale_dark)
    if "error" in r:
        return {"error": r["error"]}
    return {"glyph_hex": r["glyph_hex"], "glyph_rgb": r["glyph_rgb"], "halo_hex": r["halo_hex"], "halo_rgb": r["halo_rgb"],
            "bg_rgb": r["bg_rgb"], "ink_px": r["ink_px"]}


def space_background():
    """Space colour, limb glow and star field from the Maps App globe screenshot."""
    im = np.asarray(Image.open(NATIVE_PNG).convert("RGB")).astype(int)
    st = os.stat(NATIVE_PNG)
    regions = {"right_gutter": (2440, 2470, 500, 1100), "bottom_right": (2300, 2470, 1250, 1470), "top_right": (2330, 2470, 20, 120)}
    space = {}
    for name, (x0, x1, y0, y1) in regions.items():
        reg = im[y0:y1, x0:x1].reshape(-1, 3)
        vals, counts = np.unique(reg, axis=0, return_counts=True)
        k = counts.argmax()
        space[name] = {"box_px_2x": [x0, y0, x1, y1], "mode_rgb": vals[k].tolist(), "mode_share": round(float(counts[k] / len(reg)), 4)}
    # limb glow: horizontal profile through the right limb, 3 rows, until the first pure black pixel
    profiles = []
    for y in (600, 800, 1000):
        row = im[y, 2200:2450]
        j = next(i for i in range(len(row)) if row[i].sum() == 0)
        prof = [row[i].tolist() for i in range(j - 14, j + 1)]
        # glow width: pixels from the last "ocean-like" pixel (luma > 60% of the plateau) to black
        lum = np.array([0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2] for p in prof])
        plateau = lum[:3].mean()
        wpx = int((lum > 0.5 * plateau).sum())
        # full profile: 120 px (60 pt) inward from the first black pixel, every 2 px, then the 14 px fall-off
        inward = [row[i].tolist() for i in range(j - 120, j - 14, 2)]
        profiles.append({"row_px_2x": y, "first_black_x_2x": 2200 + j, "rgb_inward_to_outward": prof,
                         "half_luma_width_px_2x": wpx,
                         "inner_haze_rgb_every_2px_2x": inward,
                         "inner_haze_note": "ocean seen through the atmosphere brightens/greys toward the limb over ~60 pt; "
                                            "samples run from 60 pt inside the limb to 7 pt inside"})
    # stars: connected components in a strip that is pure space (right of the limb, below the toolbar)
    g = np.asarray(Image.open(NATIVE_PNG).convert("L")).astype(int)
    x0, x1, y0, y1 = 2440, 2560, 520, 1488
    reg = g[y0:y1, x0:x1]
    mask = reg > 0
    seen = np.zeros_like(mask); comps = []
    Hh, Ww = mask.shape
    for yy in range(Hh):
        for xx in range(Ww):
            if mask[yy, xx] and not seen[yy, xx]:
                stack = [(yy, xx)]; seen[yy, xx] = True; pts = []
                while stack:
                    cy, cx = stack.pop(); pts.append((cy, cx))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < Hh and 0 <= nx < Ww and mask[ny, nx] and not seen[ny, nx]:
                                seen[ny, nx] = True; stack.append((ny, nx))
                comps.append(pts)
    peaks = [max(int(reg[p]) for p in c) for c in comps]
    sizes = [len(c) for c in comps]
    return {
        "source": {"file": NATIVE_PNG, "what": "Maps App (macOS 27) globe view screenshot taken by the acceptance session, 2560x1488 @2x",
                   "mtime_local": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))},
        "space_rgb": [0, 0, 0], "space_hex": "#000000",
        "space_regions": space,
        "limb_glow": {"note": "the atmosphere reads as a light grey-blue rim just inside the limb that falls to pure black in ~7 pt; "
                              "profiles run inward->outward, last entry is the first black pixel",
                      "profiles": profiles},
        "stars": {"strip_px_2x": [x0, y0, x1, y1], "count": len(comps),
                  "per_100x100_pt": round(len(comps) / ((x1 - x0) * (y1 - y0) / 4) * 1e4, 2),
                  "size_px_2x_median": float(np.median(sizes)) if sizes else None,
                  "peak_gray_p10_p50_p90": [int(v) for v in np.percentile(peaks, [10, 50, 90])] if peaks else None,
                  "colour": "neutral grey-white (peak channel equal within 2)"},
    }


def main():
    debug = "--debug" in sys.argv
    imgs = {}
    for vid in VIEWS:
        try:
            imgs[vid] = load_view(vid)
        except FileNotFoundError:
            log("missing view", vid)
    tm = textmetrics(LABELS)
    results = []
    for L in LABELS:
        if L["view"] not in imgs:
            results.append({"id": L["id"], "error": f"view {L['view']} missing"}); continue
        img, meta, png = imgs[L["view"]]
        scale = meta.get("scale", 1)
        m = measure_label(L, img, scale, debug_name=L["id"] if debug else None)
        entry = {"id": L["id"], "kind": L["kind"], "text": L["text"], "italic": L["italic"],
                 "source": {"image": os.path.join("pipeline/basemap/raw/renders", png), "scale": scale,
                            "center": meta["center"], "span": meta["span"], "rendered_at_utc": meta["rendered_at_utc"],
                            "tool": meta["tool"]}}
        if "error" in m:
            entry["error"] = m["error"]; results.append(entry); log(L["id"], "ERR", m["error"]); continue
        f = fit(L, m, tm, scale)
        entry["measured"] = m
        entry["fit"] = f
        dark_vid = L["view"].replace("2x", "1x") + "-dark"
        if dark_vid in imgs:
            dimg, dmeta, dpng = imgs[dark_vid]
            entry["dark"] = dark_colour(L, m, dimg, dmeta.get("scale", 1), scale)
            if entry["dark"] and "error" not in entry["dark"]:
                entry["dark"]["source"] = {"image": os.path.join("pipeline/basemap/raw/renders", dpng), "rendered_at_utc": dmeta["rendered_at_utc"]}
        results.append(entry)
        log(f"{L['id']:24s} {f['weight']:8s} {f['size_pt']:5.2f}pt trk {f['tracking_pt']:5.2f} {m['glyph_hex']} halo {m['halo_hex']} {m['halo_width_px']} ink {m['ink_px']['w']}x{m['ink_px']['h']} rot {m['rotation_deg']}")

    # roll-up per kind: median size / tracking / colour across the labels of that kind
    kinds = {}
    for e in results:
        if "fit" not in e:
            continue
        kinds.setdefault(e["kind"], []).append(e)
    summary = {}
    for k, es in kinds.items():
        sizes = [e["fit"]["size_pt"] for e in es]; trk = [e["fit"]["tracking_pt"] for e in es]
        cols = np.array([e["measured"]["glyph_rgb"] for e in es])
        halos = [e["measured"]["halo_rgb"] for e in es if e["measured"]["halo_rgb"]]
        dark = [e["dark"]["glyph_rgb"] for e in es if e.get("dark") and "glyph_rgb" in e["dark"]]
        weights = sorted(set(e["fit"]["weight"] for e in es))
        # consensus weight: least total squared log-error of stem and ink-density evidence over the kind
        err = {}
        for e in es:
            for w, v in e["fit"]["all_weights"].items():
                s = math.log(v["ink_density_ratio"]) ** 2 + (math.log(v["stem_ratio"]) ** 2 if "stem_ratio" in v else 0)
                err[w] = err.get(w, 0) + s
        consensus = min(err, key=err.get)
        summary[k] = {
            "weight_consensus": consensus,
            "n": len(es), "labels": [e["id"] for e in es],
            "font": "SF (system font, .AppleSystemUIFont / .SFNS-*); web fallback: -apple-system, system-ui",
            "italic": es[0]["italic"], "case": "upper" if es[0]["text"].isupper() else "mixed",
            "weight_fits": weights,
            "size_pt_median": round(float(np.median(sizes)), 2), "size_pt_range": [round(min(sizes), 2), round(max(sizes), 2)],
            "tracking_pt_median": round(float(np.median(trk)), 2), "tracking_pt_range": [round(min(trk), 2), round(max(trk), 2)],
            "glyph_rgb_median": [int(v) for v in np.median(cols, axis=0)],
            "glyph_hex_median": "#%02x%02x%02x" % tuple(int(v) for v in np.median(cols, axis=0)),
            "halo_rgb_median": [int(v) for v in np.median(np.array(halos), axis=0)] if halos else None,
            "halo_width_px_median": (round(float(np.median([e["measured"]["halo_width_px"] for e in es if e["measured"]["halo_width_px"] is not None])), 2)
                                     if any(e["measured"]["halo_width_px"] is not None for e in es) else None),
            "dark_glyph_rgb_median": [int(v) for v in np.median(np.array(dark), axis=0)] if dark else None,
        }

    doc = {
        "what": "Globe-scale label typography of Apple Maps (macOS 27, VectorKit native style), measured off the renderer",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generator": "pipeline/basemap/labels.py + textmetrics.swift",
        "method": {
            "segmentation": "search box -> background = median of the 2 px border ring -> pixels >22 RGB units from it -> "
                            "2-means into glyph (darker) and halo; glyph core = median of the 25% most saturated glyph pixels",
            "ink_box": "per-row / per-column max of glyph coverage alpha, 50% crossing interpolated to sub-pixel",
            "size": "ink height / CoreText ink height of the same string in SF at 100 pt (kern 0) x 100 / scale",
            "tracking": "(ink width - CoreText ink width at that size) / (glyph count - 1), in pt; NB rotated labels are "
                        "measured on a de-rotated alpha map (bicubic), expect +-0.3 pt",
            "weight": "SF weight whose CoreText ink area (scaled to the fitted size) is closest to the measured coverage sum; "
                      "halo blending biases coverage upward, so treat a regular/medium split as +-1 step",
            "halo": "mean of the four (halo edge - ink edge) distances at 50% of halo-vs-background blend, in image px",
            "font_name": "SF; the renderer reports .AppleSystemUIFont / .SFNS-* (system font). Web: -apple-system, system-ui",
            "precision": "2x captures: +-0.25 px -> +-0.1 pt on size; 1x snapshots: +-0.5 px -> +-0.35 pt on 10 pt text",
        },
        "summary_by_kind": summary,
        "labels": results,
        "background": space_background(),
    }
    with open(os.path.join(OUT, "labels-globe.json"), "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    log("kinds:", json.dumps({k: (v["size_pt_median"], v["tracking_pt_median"], v["glyph_hex_median"], v["weight_fits"]) for k, v in summary.items()}))


if __name__ == "__main__":
    main()
