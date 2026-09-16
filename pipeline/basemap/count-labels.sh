#!/bin/zsh
# Reproduce the acceptance session's check: their shotm.py (headless Chrome, swiftshader, DPR 2),
# fresh page, wait 16 s, count visible DOM labels. Usage: count-labels.sh <hash> <out.png> [dark]
#   pipeline/basemap/count-labels.sh '3.12/33.48/125' /tmp/ea.png
SHOTM=${SHOTM:-/private/tmp/claude-501/-Users-herclyon-Claude/1e12f275-12e0-4506-9a32-b9a91cc06547/scratchpad/shotm.py}
BASE=${ACCEPT_BASE:-http://127.0.0.1:8792}
JS='new Promise(r=>setTimeout(()=>{const m=__globe.map; const els=[...document.querySelectorAll(".lbl")]; const vis=els.filter(e=>e.style.visibility==="visible"); const a=els.find(e=>e.textContent.startsWith("Arctic")); const ar=a&&a.getBoundingClientRect(); const g=__globe.globeRadiusPx(); r(JSON.stringify({total:els.length, visible:vis.length, names:vis.map(e=>e.textContent), arctic:a?[a.style.visibility,Math.round(ar.left),Math.round(ar.top)]:null, capDeg:g&&Math.round(g.capDeg), r:g&&Math.round(g.r), z:+m.getZoom().toFixed(2)}))},16000))'
if [[ "$3" == "dark" ]]; then export DARK=1; fi
python3 "$SHOTM" "$BASE/map/index.html#$1" 1280 744 "$JS" "$2"
