#!/bin/zsh
# Acceptance views scored with the acceptance session's metric (styl-work/cmp-accept.py).
# Usage: pipeline/basemap/score-views.sh [outdir]   (rangeserver on ACCEPT_BASE, default 8792)
set -e
BASE=${ACCEPT_BASE:-http://127.0.0.1:8792}
OUT=${1:-pipeline/basemap/raw/score}; mkdir -p "$OUT"
CMP=~/Money/styl-work/cmp-accept.py
# headless Chrome occasionally hands back a not-yet-painted (black) frame even after loaded(): retry when the mean is dark
shot() { for i in 1 2 3; do python3 pipeline/basemap/shot.py "$BASE/map/index.html#$1" 1280 744 "$2" --settle "${4:-16}" --wait-js 'window.__shell && __globe.map.loaded() && __globe.map.areTilesLoaded()' ${3:+--dark} >/dev/null 2>&1;
  m=$(python3 -c "from PIL import Image; import numpy as np; print(np.asarray(Image.open('$2').convert('L')).mean())"); if (( m > 40 )); then break; fi; done; }
shot '3.12/30.14/124.45&ui=0'              "$OUT/globe.png"        '' 8;  echo -n "globe  #3.12/30.14/124.45          "; python3 $CMP ~/Money/styl-work/native-nosidebar.png "$OUT/globe.png"
shot 'll=36,138&spn=12,16&ui=0'            "$OUT/japan.png"        '' 14; echo -n "japan  #ll=36,138&spn=12,16 light   "; python3 $CMP ~/Money/styl-work/snap-japan.png "$OUT/japan.png"
shot 'll=36,138&spn=12,16&ui=0'            "$OUT/japan-dark.png"   1  14; echo -n "japan  dark                        "; python3 $CMP ~/Money/styl-work/snap-japan-dark.png "$OUT/japan-dark.png"
shot 'll=34.69,135.50&spn=0.09,0.15&ui=0'  "$OUT/osaka.png"        '' 12; echo -n "osaka  #ll=34.69,135.50 light      "; python3 $CMP ~/Money/styl-work/snap-osaka12.png "$OUT/osaka.png"
shot 'll=34.69,135.50&spn=0.09,0.15&ui=0'  "$OUT/osaka-dark.png"   1  12; echo -n "osaka  dark                        "; python3 $CMP ~/Money/styl-work/snap-osaka12-dark.png "$OUT/osaka-dark.png"
