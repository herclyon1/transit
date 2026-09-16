#!/usr/bin/env python3
"""Tropics / equator / polar-circle line and label styles from the flat sheet (RENDER-PIPELINE.md 7.13):
Geolines-{Tropics,Equator,Polar}.Explore-{Light,Dark}-Elevated in default-56689.styl -> ui/basemap/geolines.json.

    python3 pipeline/basemap/geolines.py          # from the repo root

Every value keeps its property id and zoom band (Apple zoom; MapLibre z = Apple z - 1 is applied in globe.js).
Dash patterns (279) are in quarter-points (RENDER-PIPELINE 7.6: [12,12] measured 3/3 pt on the globe).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "styl"))
from resolve import Resolver  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
STYL = os.path.expanduser("~/Money/styl-work/default-56689.styl")
PROPS = {1: "fillColor", 3: "width", 24: "textColor", 25: "labelHaloColor", 23: "fontSpec", 18: "textSizeScale",
         172: "labelInfo", 279: "dashPattern", 463: "labelColorLumAdjustment", 470: "fillColorLumAdjustment",
         464: "labelHaloColorLumAdjustment", 33: "labelTextVisibility", 32: "labelSpacing"}


def bands(R, name, pid):
    out = []
    for zmin, zmax, v in R.bands(name, pid):
        if v is None:
            continue
        if isinstance(v, dict) and "rgba" in v:
            v = {"rgb": v["rgba"][:3], "alpha": round(v["rgba"][3] / 255, 4)}
        out.append({"zmin": zmin, "zmax": zmax, "value": v})
    return out


def main():
    R = Resolver(STYL)
    out = {"source": os.path.basename(STYL), "note": "Apple zoom bands; dash units quarter-pt; lum adjustments are HSL lightness points (RENDER-PIPELINE 7.13)", "styles": {}}
    for line in ("Tropics", "Equator", "Polar"):
        for mode in ("Light", "Dark"):
            name = f"Geolines-{line}.Explore-{mode}-Elevated"
            if name not in R.by_name:
                print(f"{name}: missing", file=sys.stderr)
                continue
            st = {"inherits": R.chain(name)}
            for pid, label in PROPS.items():
                b = bands(R, name, pid)
                if b:
                    st[label] = b
            out["styles"][name] = st
    p = os.path.join(ROOT, "ui", "basemap", "geolines.json")
    json.dump(out, open(p, "w"), indent=1, ensure_ascii=False)
    for name, st in out["styles"].items():
        print(name, {k: (v[0]["value"] if len(v) == 1 else [(b["zmin"], b["zmax"], b["value"]) for b in v]) for k, v in st.items() if k in ("fillColor", "width", "dashPattern", "textColor", "labelInfo")})


if __name__ == "__main__":
    main()
