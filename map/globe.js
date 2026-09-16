// Globe-only page (step 0 of the one-map rebuild). MapLibre 5.6 globe projection,
// Natural Earth bathymetry / land, Koppen-driven land tint, terrarium hill-shade,
// DOM labels in the system font. Every number is read from data/meta.json, which
// globe-data.py copied out of ui/basemap/*.json (Apple renderer sampled 2026-09-16).
// No UI, no data layers: the URL hash is the only control.
//   #z/lat/lng                     MapLibre's own hash
//   #ll=30,125&spn=50,60           a MapKit-style region, fitted like MKMapSnapshotter
(async function () {
  const meta = await (await fetch('data/meta.json')).json();
  const mq = matchMedia('(prefers-color-scheme: dark)');
  const mode = () => (mq.matches ? 'dark' : 'light');

  // ---- stars: density, size and brightness distribution from the Maps App screenshot ----
  const stars = document.getElementById('stars');
  function drawStars() {
    const dpr = devicePixelRatio || 1;
    const w = innerWidth, h = innerHeight;
    stars.width = w * dpr; stars.height = h * dpr;
    const ctx = stars.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = meta.background.space;
    ctx.fillRect(0, 0, w, h);
    // deterministic LCG so reloads and screenshots match
    let seed = 20260916;
    const rnd = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
    const n = Math.round(meta.background.stars_per_100x100_pt * (w * h) / 1e4);
    const [p10, p50, p90] = meta.background.star_gray_p10_p50_p90;
    const s = meta.background.star_size_pt;
    for (let i = 0; i < n; i++) {
      const u = rnd();
      // piecewise-linear inverse of the measured p10/p50/p90 brightness
      const g = u < 0.5 ? p10 + (p50 - p10) * ((u - 0.1) / 0.4) : p50 + (p90 - p50) * ((u - 0.5) / 0.4);
      const v = Math.max(0, Math.min(255, Math.round(g)));
      ctx.fillStyle = `rgb(${v},${v},${v})`;
      ctx.fillRect(rnd() * w, rnd() * h, s, s);
    }
  }
  drawStars();
  addEventListener('resize', drawStars);

  // ---- style ----------------------------------------------------------------------------
  const TERRARIUM = meta.sources.hillshade.url;
  // Two palettes are stored (ui/basemap): 'flat' = the snapshotter's flat style (palette-ocean/land,
  // light + dark) and 'globe' = the App's globe style sampled off its screenshot through the fitted
  // camera (palette-globe, light only). Light mode defaults to 'globe' — that is what the App shows;
  // '#...&pal=flat' forces the flat one. Dark mode has only the flat dark palette.
  function paletteName(m) {
    const h = location.hash.replace(/^#/, '');
    const q = new URLSearchParams(h.includes('=') ? h : '');
    const want = q.get('pal') || 'globe';
    return (m === 'light' && want === 'globe' && meta.globe_palette) ? 'globe' : 'flat';
  }
  function colours(m) {
    const pal = paletteName(m);
    if (pal === 'globe') {
      const gb = meta.globe_palette.ocean_bands;
      const last = gb[gb.length - 1].light;
      return {
        pal,
        ocean: meta.ocean_bands.map(b => ({ depth_min_m: b.depth_min_m, c: (gb.find(x => x.depth_min_m === b.depth_min_m) || { light: last }).light })),
        land: meta.globe_palette.land_tints.humid,
        climate: 'globe',
      };
    }
    return { pal, ocean: meta.ocean_bands.map(b => ({ depth_min_m: b.depth_min_m, c: b[m] })),
             land: meta.land_tints.humid[m + '_hex'], climate: m };
  }
  function style(m) {
    const col = colours(m);
    const layers = [
      // the sphere itself: shallow-water colour so coast gaps between NE land and NE ocean read as shelf
      { id: 'bg', type: 'background', paint: { 'background-color': col.ocean[0].c } },
    ];
    const sources = {};
    for (const b of col.ocean) {
      // one source per level: the 12 files parse in parallel workers and paint as they arrive
      sources['bathy-' + b.depth_min_m] = { type: 'geojson', data: 'data/bathy-' + b.depth_min_m + '.geojson', tolerance: 0.5 };
      layers.push({ id: 'bathy-' + b.depth_min_m, type: 'fill', source: 'bathy-' + b.depth_min_m,
        paint: { 'fill-color': b.c, 'fill-antialias': false } });
    }
    layers.push({ id: 'land', type: 'fill', source: 'land',
      paint: { 'fill-color': col.land, 'fill-antialias': true, 'fill-outline-color': col.land } });
    layers.push({ id: 'climate', type: 'raster', source: 'climate-' + col.climate,
      paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0 } });
    // hill-shade: light from the azimuth fitted on Apple's own render; exaggeration calibrated per zoom
    const stops = [];
    for (const z of Object.keys(HILLSHADE_K).map(Number).sort((a, b) => a - b)) stops.push(z, HILLSHADE_K[z]);
    layers.push({ id: 'hillshade', type: 'hillshade', source: 'dem',
      paint: {
        'hillshade-illumination-direction': meta.hillshade.illumination_direction_deg,
        'hillshade-illumination-anchor': 'map',
        'hillshade-exaggeration': ['interpolate', ['linear'], ['zoom'], ...stops],
        'hillshade-shadow-color': '#000000',
        'hillshade-highlight-color': '#ffffff',
        'hillshade-accent-color': '#000000',
      } });
    return {
      version: 8,
      projection: { type: 'globe' },
      sky: { 'atmosphere-blend': ATMOSPHERE_BLEND },
      sources: {
        ...sources,
        land: { type: 'geojson', data: 'data/land.geojson' },
        ['climate-' + col.climate]: { type: 'image', url: 'data/climate-' + col.climate + '.png', coordinates: meta.climate_image.bounds },
        dem: { type: 'raster-dem', tiles: [TERRARIUM], encoding: 'terrarium', tileSize: 256, maxzoom: 15,
               attribution: 'Terrain: AWS Terrain Tiles (Mapzen terrarium)' },
      },
      layers,
    };
  }
  // MapLibre's own atmosphere is a sun-lit Rayleigh shader (one bright side); Apple's limb glow is
  // uniform, so it is drawn by drawLimb() from the measured profile and MapLibre's is switched off.
  const ATMOSPHERE_BLEND = 0.0;
  // hill-shade exaggeration by zoom, calibrated against the Apple renders (pipeline/basemap/calibrate.py):
  // luminance amplitude over the 5-95% hill-shade range must match 14.3 at the z~9 Alps probe and
  // the ~0 directional shading measured at the z~4 globe view (palette-land: humid lit vs shaded).
  const HILLSHADE_K = meta.hillshade.exaggeration_by_zoom || { 4: 0.1, 9: 0.5 };

  // ---- camera from hash -------------------------------------------------------------------
  function regionFromHash() {
    const h = location.hash.replace(/^#/, '');
    const q = new URLSearchParams(h.includes('=') ? h : '');
    if (!q.get('ll')) return null;
    const [lat, lng] = q.get('ll').split(',').map(Number);
    const [dlat, dlng] = (q.get('spn') || '50,60').split(',').map(Number);
    return [[lng - dlng / 2, lat - dlat / 2], [lng + dlng / 2, lat + dlat / 2]];
  }
  const region = regionFromHash();
  const map = new maplibregl.Map({
    container: 'map',
    style: style(mode()),
    center: [125, 30], zoom: 1.5,
    hash: !region,
    attributionControl: false,
    maxPitch: 0,
    fadeDuration: 0,
    canvasContextAttributes: { antialias: true, preserveDrawingBuffer: true },
  });
  if (region) {
    // MKMapSnapshotter fits the whole region into the view (the limiting axis decides the zoom);
    // refit on resize so a viewport set after load (screenshot tools) does not leave a stale camera
    const refit = () => map.fitBounds(region, { padding: 0, animate: false });
    map.once('load', refit);
    addEventListener('resize', () => setTimeout(refit, 50));
  }

  // ---- labels: DOM markers in the system font --------------------------------------------
  const labelSpec = meta.labels;
  const oceanSize = median(meta.ocean_sizes_pt.ocean), seaSize = median(meta.ocean_sizes_pt.sea);
  function median(a) { const s = [...a].sort((x, y) => x - y); return s[(s.length - 1) >> 1]; }
  const KIND = {
    continent: { spec: 'continent', size: labelSpec.continent.size_pt },
    country: { spec: 'country', size: labelSpec.country.size_pt },
    ocean: { spec: 'ocean', size: oceanSize },
    sea: { spec: 'ocean', size: seaSize },
  };
  const WEIGHT = { regular: 400, medium: 500, semibold: 600, bold: 700, heavy: 800, black: 900 };
  function breakLines(name, kind) {
    if (kind !== 'ocean' && kind !== 'sea') return [name];
    // Apple sets water names one word per line, gluing short particles ("of") to the line before
    const out = [];
    for (const w of name.split(' ')) {
      if (out.length && (w.length <= 3 || out[out.length - 1].length <= 3)) out[out.length - 1] += ' ' + w;
      else out.push(w);
    }
    return out;
  }
  function styleLabel(el, kind, m) {
    const k = KIND[kind], s = labelSpec[k.spec];
    el.className = 'lbl' + (s.case === 'upper' ? ' upper' : '') + (s.italic ? ' italic' : '') + (s.halo ? ' halo' : '');
    el.style.fontSize = k.size + 'px';
    el.style.fontWeight = WEIGHT[s.weight];
    el.style.letterSpacing = Math.max(0, s.tracking_pt) + 'px';   // negative tracking measured within noise -> 0
    el.style.color = s[m] || s.light;
    if (s.halo) {
      // measured halo is the distance beyond the glyph edge at 2x; CSS stroke is centred on the edge
      el.style.webkitTextStroke = (s.halo_width_px_2x / 2 * 2).toFixed(2) + 'px ' + (m === 'dark' ? 'rgba(0,0,0,0)' : s.halo);
    }
  }
  const labels = (await (await fetch('data/labels.geojson')).json()).features;
  const markers = [];
  for (const f of labels) {
    const p = f.properties;
    if (!KIND[p.kind]) continue;
    const el = document.createElement('div');
    el.innerHTML = breakLines(p.name, p.kind).map(escapeHtml).join('<br>');
    styleLabel(el, p.kind, mode());
    const mk = new maplibregl.Marker({ element: el, anchor: 'center', opacityWhenCovered: '0' })
      .setLngLat(f.geometry.coordinates);
    markers.push({ mk, p, el, added: false });
  }
  function escapeHtml(s) { return s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c])); }
  // A label is shown when: inside NE's zoom range, in front of the globe and inside the disc
  // (checked every frame — MapLibre's own opacityWhenCovered lags the mercator->globe switch, which
  // put VIETNAM / INDONESIA in space on 2026-09-16), and not colliding with a more important label.
  function inRange(it, z) { return z >= (it.p.min_label ?? 0) && z <= (it.p.max_label ?? 99); }
  // great-circle distance (deg) between two lng/lat points
  function gcDeg(a, b) {
    const la1 = a.lat * Math.PI / 180, la2 = b.lat * Math.PI / 180, dl = (b.lng - a.lng) * Math.PI / 180;
    return Math.acos(Math.max(-1, Math.min(1, Math.sin(la1) * Math.sin(la2) + Math.cos(la1) * Math.cos(la2) * Math.cos(dl)))) * 180 / Math.PI;
  }
  function visibleOnGlobe(it) {
    const ll = it.mk.getLngLat();
    const g = lastGlobe;   // disc geometry + visible-cap angle from drawLimb()
    // geometry first: a label further from the view centre than the horizon is behind the globe,
    // whatever MapLibre's occlusion/projection say for that point (they are not trusted near the limb)
    if (g && g.capDeg && gcDeg(map.getCenter(), ll) > g.capDeg - 1) return false;
    const tr = map.transform;
    if (tr.isLocationOccluded && tr.isLocationOccluded(ll)) return false;
    const pt = map.project(ll);
    if (!Number.isFinite(pt.x) || !Number.isFinite(pt.y)) return false;
    if (!(pt.x > -200 && pt.x < innerWidth + 200 && pt.y > -200 && pt.y < innerHeight + 200)) return false;
    // the whole label box must sit inside the projected disc
    if (g && Math.hypot(pt.x - g.cx, pt.y - g.cy) + Math.hypot(it.w || 0, it.h || 0) / 2 > g.r - 2) return false;
    return true;
  }
  function apply(it) { it.el.style.visibility = (it.front && !it.collided) ? 'visible' : 'hidden'; }
  function updateLabels() {
    const z = map.getZoom();
    for (const it of markers) {
      const on = inRange(it, z);
      if (on && !it.added) { it.mk.addTo(map); it.added = true; it.w = it.el.offsetWidth; it.h = it.el.offsetHeight; }
      else if (!on && it.added) { it.mk.remove(); it.added = false; }
    }
    syncFront();
    collide();
  }
  function syncFront() {
    for (const it of markers) if (it.added) { it.front = visibleOnGlobe(it); apply(it); }
  }
  // greedy collision on projected boxes (map.project + measured element size, independent of when
  // MapLibre last positioned the DOM): more important first (lower min_label, then lower rank)
  function collide() {
    const shown = markers.filter(it => it.added && it.front)
      .sort((a, b) => (a.p.min_label - b.p.min_label) || (a.p.rank - b.p.rank));
    const kept = [];
    for (const it of shown) {
      const c = map.project(it.mk.getLngLat());
      if (!(it.w > 0 && it.w < 400 && it.h > 0)) {   // size not measured yet (or absurd): measure now
        const r = it.el.getBoundingClientRect(); it.w = r.width; it.h = r.height;
      }
      const box = { l: c.x - it.w / 2 - 2, t: c.y - it.h / 2 - 2, r: c.x + it.w / 2 + 2, b: c.y + it.h / 2 + 2 };
      it.collided = kept.some(k => box.l < k.r && box.r > k.l && box.t < k.b && box.b > k.t);
      if (!it.collided) kept.push(box);
      apply(it);
    }
  }
  map.on('load', updateLabels);
  map.on('zoomend', updateLabels);
  map.on('moveend', () => { syncFront(); collide(); });
  map.on('idle', () => { syncFront(); collide(); setTimeout(() => { syncFront(); collide(); }, 800); });   // after every source finished loading and rendering
  addEventListener('resize', () => setTimeout(() => { syncFront(); collide(); }, 300));
  map.on('render', syncFront);

  // ---- limb glow: the Maps App's atmosphere rim, replayed from the measured radial profile ------
  // Apple (native.png row 800 @2x): the ocean greys/brightens toward the limb over ~60 pt (inner haze),
  // then falls from ~(118,142,170) to black in 14 px = 7 pt outside the solid disc.
  const limb = document.createElement('canvas');
  limb.id = 'limb';
  document.getElementById('map').appendChild(limb);
  const OUTER = meta.background.limb_profile_2x;                 // 15 samples, 1 px @2x each, inward -> outward
  const INNER = meta.background.limb_inner_haze_every_2px_2x;    // 53 samples, 2 px @2x each, 60 pt -> 7 pt inside
  function globeRadiusPx() {
    // bisection on the great-circle distance from the view centre to the first occluded point
    const tr = map.transform;
    const c = map.getCenter();
    const pt = (deg) => {
      const lat = c.lat * Math.PI / 180, lng = c.lng * Math.PI / 180, d = deg * Math.PI / 180;
      // point d radians due east along the great circle through the centre
      const lat2 = Math.asin(Math.cos(lat) * Math.sin(d) * 0 + Math.sin(lat) * Math.cos(d));
      const lng2 = lng + Math.atan2(Math.sin(d) * Math.cos(lat), Math.cos(d) - Math.sin(lat) * Math.sin(lat2));
      return new maplibregl.LngLat(lng2 * 180 / Math.PI, lat2 * 180 / Math.PI);
    };
    let lo = 0, hi = 179;
    if (!tr.isLocationOccluded(pt(hi))) return null;      // not in globe mode / fully zoomed in
    for (let i = 0; i < 30; i++) {
      const mid = (lo + hi) / 2;
      if (tr.isLocationOccluded(pt(mid))) hi = mid; else lo = mid;
    }
    const p = map.project(pt(lo)), cpx = map.project(c);
    return { r: Math.hypot(p.x - cpx.x, p.y - cpx.y), cx: cpx.x, cy: cpx.y, capDeg: lo };
  }
  let lastGlobe = null;   // {r, cx, cy} of the projected disc, refreshed every frame by drawLimb()
  function drawLimb() {
    const dpr = devicePixelRatio || 1;
    const w = innerWidth, h = innerHeight;
    limb.width = w * dpr; limb.height = h * dpr;
    limb.style.width = w + 'px'; limb.style.height = h + 'px';
    const ctx = limb.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const g = globeRadiusPx();
    lastGlobe = (g && g.r > 10 && g.r < 6000) ? g : null;
    if (!lastGlobe) return;
    // outer fall-off: additive-looking glow over black -> paint the measured colours with alpha 1
    const outer = ctx.createRadialGradient(g.cx, g.cy, g.r, g.cx, g.cy, g.r + OUTER.length / 2);
    OUTER.forEach((rgb, i) => outer.addColorStop(Math.min(1, i / (OUTER.length - 1)), `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`));
    ctx.fillStyle = outer;
    ctx.beginPath(); ctx.arc(g.cx, g.cy, g.r + OUTER.length / 2, 0, Math.PI * 2); ctx.arc(g.cx, g.cy, g.r, 0, Math.PI * 2, true); ctx.fill();
    // inner haze: the measured colours (ocean seen through atmosphere) painted with an alpha ramp
    // 0 -> HAZE_ALPHA over the 60 pt. The profile was sampled over ocean only, so the pure haze colour
    // and its opacity cannot be separated from one background: HAZE_ALPHA is the one unmeasured constant
    // here (see map/README.md), to be fitted once a Maps screenshot with land at the limb exists.
    const span = INNER.length * 1;                          // 2 px @2x = 1 pt per sample
    const inner = ctx.createRadialGradient(g.cx, g.cy, Math.max(0, g.r - span), g.cx, g.cy, g.r);
    INNER.forEach((rgb, i) => {
      const t = i / (INNER.length - 1);
      inner.addColorStop(t, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${(HAZE_ALPHA * t * t).toFixed(3)})`);
    });
    ctx.fillStyle = inner;
    ctx.beginPath(); ctx.arc(g.cx, g.cy, g.r, 0, Math.PI * 2); ctx.fill();
  }
  const HAZE_ALPHA = meta.background.haze_alpha || 0.5;
  map.on('render', drawLimb);
  addEventListener('resize', drawLimb);

  // ---- light / dark follow the system -----------------------------------------------------
  mq.addEventListener('change', () => {
    const m = mode();
    map.setStyle(style(m));
    for (const it of markers) styleLabel(it.el, it.p.kind, m);
  });
  window.__globe = {
    map, meta,
    setHillshade: (k) => map.setPaintProperty('hillshade', 'hillshade-exaggeration', k),
    globeRadiusPx,
  };
})();
