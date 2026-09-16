#!/usr/bin/env python3
"""East-Asia class-index raster at native z3 resolution — the companion of ground-globe-ea-*.png so the UI can recolour the
high-resolution East-Asia box in the browser the way it recolours spr-class-globe.png (UI request 2026-09-16 night):

    python3 pipeline/basemap/spr_class_ea.py      # -> map/data/spr-class-globe-ea.png (2048^2, 8-bit class index, 255 = no tile),
                                                  #    map/data/climate-temp-globe-ea.png, climate-arid-globe-ea.png (256^2 codes)

Same box as ground-globe-ea (ui/basemap/ground-globe.json "east_asia": lng 90-180, lat 0-66.51326, z3 tiles x6-7 y2-3), same
class list (spr-materials.json "classes", index into it), same decode (spr_globe.class_raster over the spr_dump tile dumps in
pipeline/basemap/raw/spr).  Climate rasters carry the tile's 128x128 codes per z3 tile (temperature 0-6, aridity 0-5).
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spr_globe as G  # noqa: E402


def main():
    table = json.load(open(G.MATERIALS))
    classes = table["classes"]
    tiles = [G.load_tile(f) for f in sorted(glob.glob(os.path.join(G.RAW, "*.json"))) if os.path.basename(f)[0] == "3" and "-" in os.path.basename(f)]
    ea_cls = np.full((2048, 2048), 255, np.uint8)
    ea_t = np.full((256, 256), 255, np.uint8)
    ea_a = ea_t.copy()
    n = 0
    for t in tiles:
        if t["z"] == 3 and G.EA["x"][0] <= t["x"] < G.EA["x"][1] and G.EA["y"][0] <= t["y"] < G.EA["y"][1]:
            ox, oy = (t["x"] - G.EA["x"][0]) * 1024, (t["y"] - G.EA["y"][0]) * 1024
            ea_cls[oy:oy + 1024, ox:ox + 1024] = G.class_raster(t, table["materials"], classes)
            ea_t[oy // 8:oy // 8 + 128, ox // 8:ox // 8 + 128] = t["temp"]
            ea_a[oy // 8:oy // 8 + 128, ox // 8:ox // 8 + 128] = t["arid"]
            n += 1
    Image.fromarray(ea_cls).save(os.path.join(G.OUT, "spr-class-globe-ea.png"), optimize=True)
    Image.fromarray(ea_t).save(os.path.join(G.OUT, "climate-temp-globe-ea.png"), optimize=True)
    Image.fromarray(ea_a).save(os.path.join(G.OUT, "climate-arid-globe-ea.png"), optimize=True)
    counts = {classes[i]: int(c) for i, c in enumerate(np.bincount(ea_cls[ea_cls != 255], minlength=len(classes))) if c}
    print(f"{n} z3 tiles -> {G.OUT}/spr-class-globe-ea.png (2048^2), climate-*-globe-ea.png (256^2); class pixels {counts}")


if __name__ == "__main__":
    main()
