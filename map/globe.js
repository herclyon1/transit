// Globe-only page (step 0 of the one-map rebuild). MapLibre 5.6 globe projection,
// Natural Earth bathymetry / land, Koppen-driven land tint, terrarium hill-shade,
// DOM labels in the system font. Every number is read from data/meta.json, which
// globe-data.py copied out of ui/basemap/*.json (Apple renderer sampled 2026-09-16).
// No UI, no data layers: the URL hash is the only control.
//   #z/lat/lng                     MapLibre's own hash
//   #ll=30,125&spn=50,60           a MapKit-style region, fitted like MKMapSnapshotter
(async function () {
  // data/meta.json = data sources (shared with the data session); meta-ui.json = palettes, camera,
  // haze, shading, label styles (this page's own numbers). Merged into one object here.
  const [metaData, metaUi, flatLight, flatDark] = await Promise.all([
    fetch('data/meta.json').then(r => r.json()), fetch('meta-ui.json').then(r => r.json()),
    fetch('style-flat-light.json').then(r => r.json()).catch(() => null), fetch('style-flat-dark.json').then(r => r.json()).catch(() => null)]);
  const meta = { ...metaData, ...metaUi, sources: metaData.sources };
  // globe -> flat hand-over: the sphere flattens to Mercator between GLOBE_Z0 and GLOBE_Z1 (MapLibre
  // projection expression) while the globe layers fade out and the data session's flat style
  // (map/style-flat-*.json, OpenFreeMap vector tiles, pipeline/basemap/styl/to_maplibre.py) fades in
  const GLOBE_Z0 = 5, GLOBE_Z1 = 6;
  const fadeIn = ['interpolate', ['linear'], ['zoom'], GLOBE_Z0, 0, GLOBE_Z1, 1];
  const fadeOut = ['interpolate', ['linear'], ['zoom'], GLOBE_Z0, 1, GLOBE_Z1, 0];
  const OPACITY_PROP = { fill: ['fill-opacity'], line: ['line-opacity'], symbol: ['text-opacity', 'icon-opacity'],
                         background: ['background-opacity'], raster: ['raster-opacity'], 'fill-extrusion': ['fill-extrusion-opacity'], circle: ['circle-opacity'] };
  function withFade(layer, fade, minzoom) {
    const l = JSON.parse(JSON.stringify(layer));
    l.paint = l.paint || {};
    for (const prop of OPACITY_PROP[l.type] || []) {
      const cur = l.paint[prop];
      // existing opacities in the flat style are plain numbers; scale the fade's end value by them
      l.paint[prop] = (typeof cur === 'number') ? fade.map((v, i) => (i === fade.length - 1 ? v * cur : v)) : fade;
    }
    if (minzoom != null) l.minzoom = Math.max(l.minzoom || 0, minzoom);
    return l;
  }
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
  const TERRARIUM = (meta.sources.hillshade && meta.sources.hillshade.url) || meta.hillshade.url;
  // Two palettes are stored (ui/basemap): 'flat' = the snapshotter's flat style (palette-ocean/land,
  // light + dark) and 'globe' = the App's globe style sampled off its screenshot through the fitted
  // camera (palette-globe, light only). Light mode defaults to 'globe' — that is what the App shows;
  // '#...&pal=flat' forces the flat one. Dark mode has only the flat dark palette.
  function paletteName(m) {
    const h = location.hash.replace(/^#/, '');
    const q = new URLSearchParams(h.includes('&') ? h.slice(h.indexOf('&') + 1) : (h.includes('=') ? h : ''));
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
      if (b.depth_min_m === 0 && col.pal === 'globe' && meta.shelf) {
        // shelf grading inside the 0-200 m band: depth-coloured raster (palette-shelf.json ramp, terrarium
        // z5), drawn above the 0-200 fill and below the deeper fills, so NE's 200 m contour still wins
        sources['shelf'] = { type: 'image', url: 'data/shelf-globe.png', coordinates: meta.shelf.bounds };
        layers.push({ id: 'shelf', type: 'raster', source: 'shelf', paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0 } });
      }
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
    if (meta.labels_app && meta.labels_app.graticule_line && col.pal === 'globe') {
      // tropics + equator: dashed line, colour/width/dash from the App screenshot (labels_app.graticule_line)
      const gl = meta.labels_app.graticule_line;
      sources['graticule'] = { type: 'geojson', data: 'data/graticule.geojson' };
      layers.push({ id: 'graticule', type: 'line', source: 'graticule', filter: ['==', ['geometry-type'], 'LineString'],
        paint: { 'line-color': gl.colour, 'line-width': gl.width_pt, 'line-dasharray': gl.dash_pt } });
    }
    // globe layers fade out over the hand-over (background and hill-shade stay: the flat background
    // covers the ocean colour, the hill-shade is calibrated at country zoom as well)
    const globeLayers = layers.map(l => (l.type === 'background' || l.type === 'hillshade') ? l : withFade(l, fadeOut));
    const flat = m === 'dark' ? flatDark : flatLight;
    const flatSources = {}, flatLayers = [];
    let glyphs;
    if (flat) {
      Object.assign(flatSources, flat.sources);
      glyphs = flat.glyphs;
      for (const l of flat.layers) flatLayers.push(withFade({ ...l, id: 'flat-' + l.id }, fadeIn, GLOBE_Z0));
    }
    // the hill-shade goes above the flat fills but below its lines/labels: re-order it after the flat land use
    const hs = globeLayers.splice(globeLayers.findIndex(l => l.id === 'hillshade'), 1)[0];
    const firstLine = flatLayers.findIndex(l => l.type === 'line' || l.type === 'symbol');
    const ordered = firstLine >= 0 ? [...globeLayers, ...flatLayers.slice(0, firstLine), hs, ...flatLayers.slice(firstLine)] : [...globeLayers, hs, ...flatLayers];
    return {
      version: 8,
      // sphere from GLOBE_Z0 down, Mercator from GLOBE_Z1 up, morph in between (MapLibre's own 'globe' preset is 11->12)
      projection: { type: ['interpolate', ['linear'], ['zoom'], GLOBE_Z0, 'vertical-perspective', GLOBE_Z1, 'mercator'] },
      sky: { 'atmosphere-blend': ATMOSPHERE_BLEND },
      ...(glyphs ? { glyphs } : {}),
      sources: {
        ...sources,
        ...flatSources,
        land: { type: 'geojson', data: 'data/land.geojson' },
        ['climate-' + col.climate]: { type: 'image', url: 'data/climate-' + col.climate + '.png', coordinates: meta.climate_image.bounds },
        dem: { type: 'raster-dem', tiles: [TERRARIUM], encoding: 'terrarium', tileSize: 256, maxzoom: 15,
               attribution: 'Terrain: AWS Terrain Tiles (Mapzen terrarium)' },
      },
      layers: ordered,
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
  //   #z/lat/lng[&k=v...]            MapLibre-style camera, parsed here (MapLibre's own hash parser
  //                                  cannot carry extra parameters)
  //   #ll=30,125&spn=50,60[&k=v...]  MapKit-style region, fitted like MKMapSnapshotter
  //   extras: pal=flat|globe, padr/padl/padt/padb=<px> (camera padding; the Maps App draws its globe
  //   centre 7 pt left of the window centre when the sidebar is closed: 632.7 vs 640 @1x -> padr=14)
  function parseHash() {
    const h = location.hash.replace(/^#/, '');
    const [cam, ...rest] = h.split('&');
    const q = new URLSearchParams(rest.join('&'));
    const out = { q, region: null, camera: null };
    if (cam.includes('ll=')) {
      const qq = new URLSearchParams(h);
      const [lat, lng] = qq.get('ll').split(',').map(Number);
      const [dlat, dlng] = (qq.get('spn') || '50,60').split(',').map(Number);
      out.region = [[lng - dlng / 2, lat - dlat / 2], [lng + dlng / 2, lat + dlat / 2]];
    } else {
      const parts = cam.split('/').map(Number);
      if (parts.length >= 3 && parts.every(Number.isFinite)) out.camera = { zoom: parts[0], center: [parts[2], parts[1]] };
    }
    out.padding = { top: +(q.get('padt') || 0), right: +(q.get('padr') || 0), bottom: +(q.get('padb') || 0), left: +(q.get('padl') || 0) };
    return out;
  }
  const hashState = parseHash();
  const region = hashState.region;
  const map = new maplibregl.Map({
    container: 'map',
    style: style(mode()),
    center: hashState.camera ? hashState.camera.center : [125, 30],
    zoom: hashState.camera ? hashState.camera.zoom : 1.5,
    hash: false,
    attributionControl: false,
    maxPitch: 0,
    fadeDuration: 0,
    canvasContextAttributes: { antialias: true, preserveDrawingBuffer: true },
  });
  map.setPadding(hashState.padding);
  // Perspective like the Maps App: its globe camera (palette-globe.json, fitted on the App screenshot,
  // 1280x744 pt) sits D = 2.894 earth radii from the centre with focal length 1569.5 pt, i.e. a
  // vertical field of view of 2*atan(372/1569.5) = 26.7 deg (MapLibre default 36.87). With this fov the
  // same silhouette radius also gives the same centre scale; '&fov=<deg>' overrides.
  const cam = meta.globe_palette && meta.globe_palette.camera;
  const FOV = +(hashState.q.get('fov') || (cam && cam.fov_deg) || 26.7);
  map.setVerticalFieldOfView(FOV);
  if (region) {
    // MKMapSnapshotter fits the whole region into the view (the limiting axis decides the zoom);
    // refit on resize so a viewport set after load (screenshot tools) does not leave a stale camera
    const refit = () => map.fitBounds(region, { padding: hashState.padding, animate: false });
    map.once('load', refit);
    addEventListener('resize', () => setTimeout(refit, 50));
  }
  // keep the hash in MapLibre's z/lat/lng form, preserving the extra parameters (m=, sel=, pal=, fov=, pad*)
  function writeHash() {
    const c = map.getCenter(), z = map.getZoom();
    const extras = [...hashState.q.entries()].map(([k, v]) => `${k}=${v}`).join('&');
    history.replaceState(null, '', `#${z.toFixed(2)}/${c.lat.toFixed(2)}/${c.lng.toFixed(2)}` + (extras ? '&' + extras : ''));
  }
  map.on('moveend', writeHash);
  function setHashExtra(k, v) { if (v == null || v === '') hashState.q.delete(k); else hashState.q.set(k, v); writeHash(); }

  // ---- labels: DOM markers in the system font --------------------------------------------
  // Two style sources: labelSpec (measured on the snapshotter's flat renders, labels-globe.json) and
  // meta.labels_app (measured on the App's GLOBE screenshot). In the globe palette the App-globe numbers
  // win where they exist (country, capital, city, sea, deep, graticule); the flat ones stay for the rest.
  const labelSpec = meta.labels;
  const appSpec = meta.labels_app || {};
  const oceanSize = median(meta.ocean_sizes_pt.ocean), seaSize = median(meta.ocean_sizes_pt.sea);
  function median(a) { const s = [...a].sort((x, y) => x - y); return s[(s.length - 1) >> 1]; }
  const useApp = () => paletteName(mode()) === 'globe';
  // spec fields: weight, size_pt, tracking_pt, italic, case, colour (light), dark, halo, halo_width_px_2x
  function specFor(kind) {
    const A = appSpec;
    const flat = (name, size) => ({ ...labelSpec[name], colour: labelSpec[name].light, size_pt: size ?? labelSpec[name].size_pt });
    if (useApp()) {
      switch (kind) {
        case 'country': return A.country ? { ...A.country, size_pt: countrySize() } : flat('country');
        case 'capital': return A.capital || flat('deep');
        case 'city': return A.city || flat('deep');
        case 'sea': return A.sea || flat('ocean', seaSize);
        case 'ocean': return A.sea ? { ...A.sea, size_pt: oceanSize } : flat('ocean', oceanSize);
        case 'deep': return A.deep || flat('deep');
        case 'graticule': return A.graticule || flat('graticule');
      }
    }
    switch (kind) {
      case 'country': return flat('country');
      case 'capital': case 'city': case 'deep': return flat('deep');
      case 'sea': return flat('ocean', seaSize);
      case 'ocean': return flat('ocean', oceanSize);
      case 'graticule': return flat('graticule');
    }
    return flat('continent');
  }
  // country size follows the .styl Country-Label-Medium height curve, anchored on the App measurement at z 3.12
  function countrySize() {
    const c = appSpec.country_size_curve, z = map ? map.getZoom() : 3.12;
    const h = (zz) => { const zs = c.zoom, hs = c.height; if (zz <= zs[0]) return hs[0]; if (zz >= zs[zs.length - 1]) return hs[hs.length - 1];
      for (let i = 1; i < zs.length; i++) if (zz <= zs[i]) return hs[i - 1] + (hs[i] - hs[i - 1]) * (zz - zs[i - 1]) / (zs[i] - zs[i - 1]); };
    return appSpec.country.size_pt * h(z) / h(c.anchor_zoom);
  }
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
    const s = specFor(kind);
    const txt = el.querySelector('.txt') || el;
    // classList, not className: MapLibre's own 'maplibregl-marker' class (absolute positioning) must survive re-styling
    for (const c of ['upper', 'italic', 'halo', 'continent', 'country', 'ocean', 'sea', 'capital', 'city', 'deep', 'graticule']) el.classList.remove(c);
    el.classList.add('lbl', kind);
    if (s.case === 'upper') el.classList.add('upper');
    if (s.italic) el.classList.add('italic');
    if (s.halo) el.classList.add('halo');
    txt.style.fontSize = s.size_pt + 'px';
    txt.style.fontWeight = WEIGHT[s.weight] || 600;
    txt.style.letterSpacing = Math.max(0, s.tracking_pt || 0) + 'px';   // negative tracking measured within noise -> 0
    txt.style.color = (m === 'dark' && s.dark) ? s.dark : (s.colour || s.light);
    // measured halo is the distance beyond the glyph edge at 2x; CSS stroke is centred on the edge
    txt.style.webkitTextStroke = (s.halo && m !== 'dark') ? (s.halo_width_px_2x || 1).toFixed(2) + 'px ' + s.halo : '0px transparent';
  }
  function makeLabel(p, kind, coords) {
    const el = document.createElement('div');
    if (kind === 'capital' || kind === 'city') {
      // Apple: white disc in a dark ring left of the name, text follows after a small gap
      const mk = appSpec.city_marker || { diameter_pt: 3.5, ring_pt: 1, ring_colour: '#5c5c5c', fill: '#ffffff', gap_to_text_pt: 4 };
      el.innerHTML = `<span class="dot" style="width:${mk.diameter_pt}px;height:${mk.diameter_pt}px;border:${mk.ring_pt}px solid ${mk.ring_colour};background:${mk.fill};margin-right:${mk.gap_to_text_pt}px"></span><span class="txt">${escapeHtml(p.name)}</span>`;
      el.classList.add('point');
    } else if (kind === 'deep') {
      el.innerHTML = `<span class="tri">&#9662;</span><span class="txt">${escapeHtml(p.name)}</span>`;
      el.classList.add('point');
    } else {
      el.innerHTML = `<span class="txt">${breakLines(p.name, kind).map(escapeHtml).join('<br>')}</span>`;
    }
    styleLabel(el, kind, mode());
    const anchor = (kind === 'capital' || kind === 'city' || kind === 'deep') ? 'left' : 'center';
    const mk = new maplibregl.Marker({ element: el, anchor, opacityWhenCovered: '0' }).setLngLat(coords);
    return { mk, p, el, kind, added: false };
  }
  const markers = [];
  const labels = (await (await fetch('data/labels.geojson')).json()).features;
  for (const f of labels) {
    const p = f.properties;
    if (!['continent', 'country', 'ocean', 'sea'].includes(p.kind)) continue;
    markers.push(makeLabel(p, p.kind, f.geometry.coordinates));
  }
  // cities (map/data/cities.geojson from the data session): capitals and cities by their min_zoom,
  // globe_rank <= 3 at globe zooms
  try {
    const cities = (await (await fetch('data/cities.geojson')).json()).features;
    for (const f of cities) {
      const p = f.properties;
      if (p.globe_rank > 3) continue;
      const kind = p.capital === 1 ? 'capital' : 'city';
      markers.push(makeLabel({ name: p.name, min_label: p.min_zoom ?? 3, max_label: 12, rank: p.globe_rank }, kind, f.geometry.coordinates));
    }
  } catch (e) { console.warn('cities', e); }
  // deep-sea points (map/data/undersea.geojson cls 1, type Deep)
  try {
    const und = (await (await fetch('data/undersea.geojson')).json()).features;
    for (const f of und) {
      const p = f.properties;
      if (p.cls !== 1 || p.type !== 'Deep') continue;
      markers.push(makeLabel({ name: p.label, min_label: 3, max_label: 10, rank: 3 }, 'deep', f.geometry.coordinates));
    }
  } catch (e) { console.warn('undersea', e); }
  // graticule labels (map/data/graticule.geojson)
  try {
    const gr = (await (await fetch('data/graticule.geojson')).json()).features;
    for (const f of gr) {
      if (f.geometry.type !== 'Point') continue;
      markers.push(makeLabel(f.properties, 'graticule', f.geometry.coordinates));
    }
  } catch (e) { console.warn('graticule', e); }
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
    const bx = (it.kind === 'capital' || it.kind === 'city' || it.kind === 'deep') ? pt.x + (it.w || 0) / 2 : pt.x;
    if (g && Math.hypot(bx - g.cx, pt.y - g.cy) + Math.hypot(it.w || 0, it.h || 0) / 2 > g.r - 2) return false;
    return true;
  }
  const globeFade = () => Math.max(0, Math.min(1, (GLOBE_Z1 - map.getZoom()) / (GLOBE_Z1 - GLOBE_Z0)));
  function apply(it) {
    const f = globeFade();
    it.el.style.visibility = (f > 0 && it.front && !it.collided) ? 'visible' : 'hidden';
    it.el.style.setProperty('--fade', f.toFixed(3));   // children fade; MapLibre owns the element's own opacity
  }
  function updateLabels() {
    const z = map.getZoom();
    for (const it of markers) {
      const on = inRange(it, z);
      if (on && !it.added) { it.mk.addTo(map); it.added = true; }
      else if (!on && it.added) { it.mk.remove(); it.added = false; }
      if (it.added && it.kind === 'country') styleLabel(it.el, it.kind, mode());   // size follows the zoom curve
      if (it.added) { it.w = it.el.offsetWidth; it.h = it.el.offsetHeight; }
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
      const leftAnchored = it.kind === 'capital' || it.kind === 'city' || it.kind === 'deep';
      const l0 = leftAnchored ? c.x : c.x - it.w / 2;
      const box = { l: l0 - 2, t: c.y - it.h / 2 - 2, r: l0 + it.w + 2, b: c.y + it.h / 2 + 2 };
      it.collided = kept.some(k => box.l < k.r && box.r > k.l && box.t < k.b && box.b > k.t);
      if (!it.collided) kept.push(box);
      apply(it);
    }
  }
  map.on('load', updateLabels);
  map.on('zoomend', updateLabels);
  map.on('moveend', () => { syncFront(); collide(); });
  let idleCount = 0;
  map.on('idle', () => { idleCount++; syncFront(); collide(); setTimeout(() => { syncFront(); collide(); }, 800); });   // after every source finished loading and rendering
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
  const shadeCanvas = document.createElement('canvas');
  let shadeKey = '';
  function drawShading(ctx, g, w, h) {
    const S = meta.shading;
    const D = 1 / Math.cos(g.capDeg * Math.PI / 180);          // camera distance in earth radii
    const fpx = g.r * Math.sqrt(D * D - 1);                     // focal length in CSS px
    const key = [g.r | 0, g.cx | 0, g.cy | 0, w, h].join(',');
    if (key !== shadeKey) {
      shadeKey = key;
      const sw = Math.ceil(w / 2), sh = Math.ceil(h / 2);
      shadeCanvas.width = sw; shadeCanvas.height = sh;
      const sctx = shadeCanvas.getContext('2d');
      const im = sctx.createImageData(sw, sh);
      const [Lx, Ly, Lz] = S.L, a = S.a, b = S.b, norm = S.centre_factor;
      for (let j = 0; j < sh; j++) {
        for (let i = 0; i < sw; i++) {
          const x = i * 2 + 1, y = j * 2 + 1;
          // ray from the camera (0,0,D) through the pixel, intersected with the unit sphere -> normal
          const dx = (x - g.cx) / fpx, dy = -(y - g.cy) / fpx;
          const A = dx * dx + dy * dy + 1, B = -2 * D, C = D * D - 1;
          const disc = B * B - 4 * A * C;
          const o = (j * sw + i) * 4;
          if (disc < 0) { im.data[o + 3] = 0; continue; }
          const t = (-B - Math.sqrt(disc)) / (2 * A);
          const nx = dx * t, ny = dy * t, nz = D - t;
          const factor = (a + b * (nx * Lx + ny * Ly + nz * Lz)) / norm;
          if (factor < 1) { im.data[o] = im.data[o + 1] = im.data[o + 2] = 0; im.data[o + 3] = Math.min(255, Math.round((1 - factor) * 255)); }
          else { im.data[o] = im.data[o + 1] = im.data[o + 2] = 255; im.data[o + 3] = Math.min(255, Math.round((factor - 1) * 255)); }
        }
      }
      sctx.putImageData(im, 0, 0);
    }
    ctx.save();
    ctx.beginPath(); ctx.arc(g.cx, g.cy, g.r, 0, Math.PI * 2); ctx.clip();
    ctx.drawImage(shadeCanvas, 0, 0, w, h);
    ctx.restore();
  }
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
    // lit sphere: the App's globe brightness follows a + b*(n.L) (shading-globe.json, r2 0.85 on 100k
    // deep-ocean samples; L from screen-left/below). Painted per pixel at half resolution as a black
    // (factor < 1) or white (factor > 1) overlay, normalised to 1 at the disc-centre normal.
    if (meta.shading && paletteName(mode()) === 'globe') drawShading(ctx, g, w, h);
    if (meta.haze) {
      // inner haze solved from land+sea pixels on the same limb (haze-globe.json): overlay colour H and
      // opacity a per r/limb bin, meaningful from r/limb ~0.91 (a 0.19) to the edge (a 0.94)
      const r0 = meta.haze.starts_at_r * g.r;
      const inner = ctx.createRadialGradient(g.cx, g.cy, r0, g.cx, g.cy, g.r);
      const first = meta.haze.stops[0];
      inner.addColorStop(0, `rgba(${first.rgb[0]},${first.rgb[1]},${first.rgb[2]},0)`);
      for (const s of meta.haze.stops) {
        const t = Math.min(1, Math.max(0, (s.r * g.r - r0) / (g.r - r0)));
        inner.addColorStop(t, `rgba(${s.rgb[0]},${s.rgb[1]},${s.rgb[2]},${s.alpha})`);
      }
      ctx.fillStyle = inner;
      ctx.beginPath(); ctx.arc(g.cx, g.cy, g.r, 0, Math.PI * 2); ctx.fill();
    } else {
      // fallback: the ocean-only profile with an unmeasured opacity (pre-2026-09-16 15:00 behaviour)
      const span = INNER.length * 1;
      const inner = ctx.createRadialGradient(g.cx, g.cy, Math.max(0, g.r - span), g.cx, g.cy, g.r);
      INNER.forEach((rgb, i) => {
        const t = i / (INNER.length - 1);
        inner.addColorStop(t, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${(HAZE_ALPHA * t * t).toFixed(3)})`);
      });
      ctx.fillStyle = inner;
      ctx.beginPath(); ctx.arc(g.cx, g.cy, g.r, 0, Math.PI * 2); ctx.fill();
    }
  }
  const HAZE_ALPHA = meta.background.haze_alpha || 0.5;
  map.on('render', () => { limb.style.opacity = globeFade().toFixed(3); drawLimb(); });
  addEventListener('resize', drawLimb);

  // ---- light / dark follow the system -----------------------------------------------------
  mq.addEventListener('change', () => {
    const m = mode();
    map.setStyle(style(m));
    for (const it of markers) styleLabel(it.el, it.kind, m);
  });
  window.__globe = {
    map, meta, setHashExtra, hashExtras: () => hashState.q,
    get idleCount() { return idleCount; },
    get labelStats() { const m = markers.filter(it => it.added); return { inRange: m.length, front: m.filter(it => it.front).length, visible: m.filter(it => it.front && !it.collided).length }; },
    setHillshade: (k) => map.setPaintProperty('hillshade', 'hillshade-exaggeration', k),
    globeRadiusPx,
  };
})();
