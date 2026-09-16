// The one map's basemap: MapLibre 5.6 globe -> Mercator, Apple's renderer reproduced from its decoded files.
// Numbers come from three places, in this order of authority (CLAUDE.md, 2026-09-16 evening):
//   1. decoded originals — basemap/data/shader/shader-numbers.json (SHADER-NUMBERS.md: light direction, light
//      colours, irradiance cube, water-depth ramp, sky colours, groundSettings HSV tints), the .styl sheets
//      (Landcover colours via pipeline/basemap/ground.py, everything in style-flat-*.json), groundSettings.json
//      (groundElevationScale -> hill-shade strength, see hillshadeAlpha())
//   2. values still SAMPLED off App screenshots and marked pending in meta-ui.json: the globe's own pastel
//      palette (globe_palette, shelf, climate-globe.png — the globe texture path is not decoded), the inner limb
//      haze table (haze), the label styles measured on the App globe (labels_app)
// No UI here: the URL hash is the only control.
//   #z/lat/lng                     MapLibre-style camera
//   #ll=30,125&spn=50,60           a MapKit-style region, fitted like MKMapSnapshotter
(async function () {
  // data/meta.json = data sources (shared with the data session); meta-ui.json = this page's numbers;
  // shader-numbers.json = the renderer constants (data session, repo root basemap/data/shader)
  const [metaData, metaUi, flatLight, flatDark, shaderNums] = await Promise.all([
    fetch('data/meta.json').then(r => r.json()), fetch('meta-ui.json').then(r => r.json()),
    fetch('style-flat-light.json').then(r => r.json()).catch(() => null), fetch('style-flat-dark.json').then(r => r.json()).catch(() => null),
    fetch('../basemap/data/shader/shader-numbers.json').then(r => r.json()).catch(() => null)]);
  const meta = { ...metaData, ...metaUi, sources: metaData.sources };
  const SN = shaderNums;
  if (!SN) (window.__errs = window.__errs || []).push('shader-numbers.json missing: lighting/ocean ramp fall back to meta-ui values');
  // Zoom bands (2026-09-16, acceptance):
  //   PAL 4.6-5.0  the globe's sampled palette hands over to the decoded flat colours, and the flat style (fills,
  //                lines, .styl labels) fades in while the DOM globe labels fade out — the App's flat renderer owns
  //                z >= 5, so at the z5.1 acceptance view everything flat is fully on
  //   MORPH 5-6    the sphere flattens (projection expression) — nothing else changes
  //   OVER 7-8     the NE/raster drawing (ground rasters, ocean ramp, deep/graticule DOM labels) fades out;
  //                asked for as 8-9, kept at 7-8 because the 0.1 deg Koppen tint and NE coastlines stair-step from z ~7;
  //                &over=8,9 overrides for comparison
  const GLOBE_Z0 = 5, GLOBE_Z1 = 6;
  const PAL_Z0 = 4.6, PAL_Z1 = 5.0;
  const overQ = (location.hash.match(/[&#]over=([\d.]+),([\d.]+)/) || []).slice(1).map(Number);
  const OVER_Z0 = overQ[0] || 7, OVER_Z1 = overQ[1] || 8;
  const fadeIn = ['interpolate', ['linear'], ['zoom'], PAL_Z0, 0, PAL_Z1, 1];
  const fadeOut = ['interpolate', ['linear'], ['zoom'], OVER_Z0, 1, OVER_Z1, 0];
  const palIn = ['interpolate', ['linear'], ['zoom'], PAL_Z0, 0, PAL_Z1, 1];
  const palOut = ['interpolate', ['linear'], ['zoom'], PAL_Z0, 1, PAL_Z1, 0];
  const OPACITY_PROP = { fill: ['fill-opacity'], line: ['line-opacity'], symbol: ['text-opacity', 'icon-opacity'],
                         background: ['background-opacity'], raster: ['raster-opacity'], 'color-relief': ['color-relief-opacity'], 'fill-extrusion': ['fill-extrusion-opacity'], circle: ['circle-opacity'] };
  function withFade(layer, fade, minzoom) {
    const l = JSON.parse(JSON.stringify(layer));
    l.paint = l.paint || {};
    for (const prop of OPACITY_PROP[l.type] || []) {
      const cur = l.paint[prop];
      if (Array.isArray(cur) && cur[0] === 'interpolate' && fade === fadeOut) {
        // a ramp already there (palIn 4.6->5): append the OVER fade-out stops, scaled by the ramp's end value
        const end = cur[cur.length - 1];
        l.paint[prop] = [...cur, OVER_Z0, end, OVER_Z1, 0];
      } else {
        // existing opacities in the flat style are plain numbers; scale the fade's end value by them
        l.paint[prop] = (typeof cur === 'number') ? fade.map((v, i) => (i === fade.length - 1 ? v * cur : v)) : fade;
      }
    }
    if (minzoom != null) l.minzoom = Math.max(l.minzoom || 0, minzoom);
    return l;
  }
  const mq = matchMedia('(prefers-color-scheme: dark)');
  const mode = () => (mq.matches ? 'dark' : 'light');

  // ---- colour maths (linear RGB as the shader; sRGB on output) --------------------------------
  const toLin = c => (c /= 255, c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const toSrgb8 = v => { v = Math.max(0, Math.min(1, v)); return Math.round((v <= 0.0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - 0.055) * 255); };
  const hex = rgb => '#' + rgb.map(v => v.toString(16).padStart(2, '0')).join('');
  // flat ground light: ambientLightColor * cube(+z face mean) + lightColor * L.z  (SHADER-NUMBERS 4.1; = 1.0455)
  const LIGHT = SN ? (SN.lighting.ambientLightColor_linear[0] * SN.ambient_irradiance_cube.face_mean[SN.ambient_irradiance_cube.faces_order.indexOf('+z')]
                      + SN.lighting.lightColor_linear[0] * SN.lighting.tileLightDirection[2]) : 1.0455;
  const lit = rgb8 => hex(rgb8.map(v => toSrgb8(toLin(v) * LIGHT)));   // sheet colour -> what the flat renderer shows on flat ground

  // space: black until the star catalogue is drawn (drawStars, after the overlay geometry exists)
  const stars = document.getElementById('stars');
  stars.width = innerWidth * (devicePixelRatio || 1); stars.height = innerHeight * (devicePixelRatio || 1);
  stars.getContext('2d').fillStyle = meta.background.space; stars.getContext('2d').fillRect(0, 0, stars.width, stars.height);

  // ---- ocean: the water-depth ramp (SHADER-NUMBERS 4.3 / RENDER-PIPELINE 2.3) as a color-relief layer ----------
  // t = saturate((log2(depth_m) + depthGradientOffset) * depthGradientScale); colour = gradient1Texture[t] (linear
  // RGBA8, 256 texels) x light(0,0,1), sRGB-encoded. MapLibre 5.6's color-relief layer colours the raster-dem tiles
  // (the same terrarium tiles the hill-shade uses) by elevation, linear between stops: 35 stops on log-spaced depths.
  // Land (elevation >= 0) is transparent; ETOPO1 depths are integer metres, so the sea is opaque from 1 m.
  function rampColour(m, depth) {
    const g = SN.water_depth_gradient[m];
    const t = Math.max(0, Math.min(1, (Math.log2(depth) + g.depthGradientOffset) * g.depthGradientScale));
    const i = t * 255, i0 = Math.floor(i), i1 = Math.min(255, i0 + 1), f = i - i0;
    const tx = g.texels_linear_rgba8;
    return hex([0, 1, 2].map(k => toSrgb8((tx[i0][k] / 255 * (1 - f) + tx[i1][k] / 255 * f) * LIGHT)));
  }
  // the Mac App GLOBE's water: DvMt material 318 (Water) depth ramp, client:69 = 0, day / night (meta.dvmt_globe.water_*,
  // RENDER-PIPELINE 2.3 / 6): 15 stops 0 m .. 7 km in sRGB; interpolated in linear light, x light(0,0,1), sRGB-encoded.
  // Verification: sampled palette-globe 1000-2000 m band #a9d6f1 vs ramp(1000 m) x light #a2ddf9.
  function dvmtRampColour(m, depth) {
    const ramp = meta.dvmt_globe['water_' + m];
    let i = 0; while (i < ramp.length - 1 && ramp[i + 1][0] <= depth) i++;
    const [d0, c0] = ramp[i], [d1, c1] = ramp[Math.min(i + 1, ramp.length - 1)];
    const f = d1 > d0 ? Math.max(0, Math.min(1, (depth - d0) / (d1 - d0))) : 0;
    const a = [1, 3, 5].map(k => toLin(parseInt(c0.slice(k, k + 2), 16))), b = [1, 3, 5].map(k => toLin(parseInt(c1.slice(k, k + 2), 16)));
    return hex(a.map((v, k) => toSrgb8((v * (1 - f) + b[k] * f) * LIGHT)));
  }
  const RAMP_DEPTHS = [11000, 8000, 6000, 4500, 3500, 2800, 2200, 1700, 1300, 1000, 800, 650, 520, 420, 350, 300, 250, 200, 160, 130, 100, 80, 60, 45, 35, 25, 18, 13, 9, 6, 4, 3, 2, 1.5, 1];
  function oceanLayers(m, opacity, id = 'ocean', colour = rampColour) {
    if (!SN) return [];
    const stops = RAMP_DEPTHS.flatMap(d => [-d, colour(m, d)]);
    return [{ id, type: 'color-relief', source: 'dem',
      paint: { 'color-relief-color': ['interpolate', ['linear'], ['elevation'], ...stops, -0.5, colour(m, 0.5), 0, 'rgba(0,0,0,0)'], 'color-relief-opacity': opacity } }];
  }
  // DvMt globe land material colour for a class at the Apple zoom of the sheet band used for the rasters (z3)
  function dvmtLand(m, cls, appleZ = 3) {
    const bands = meta.dvmt_globe && meta.dvmt_globe[m] && meta.dvmt_globe[m][cls];
    if (!bands) return null;
    const b = bands.find(x => x[0] <= appleZ && appleZ < x[1]) || bands[bands.length - 1];
    return b[2];
  }

  // ---- hill-shade strength from groundSettings.json (SHADER-NUMBERS 4.4 table, groundElevationScale) --------
  // Apple lights the terrain normal n = normalize(-s*dh/dx, -s*dh/dy, 1) with s = groundElevationScale(Apple z):
  //   f(n) = (ambient*cube(n) + lightColor*max(n.L,0)) / light(0,0,1);  for a slope of gradient g facing away from
  //   the light, small g:  1 - f = lightColor*cos(alt)/light(0,0,1) * s*g = 0.2864 * s*g   (linear light)
  // MapLibre 'standard' hill-shade with exaggeration 0.5 (no slope warp) darkens by  alpha * sin(atan(0.625 * g *
  //   2^(0.3*(15 - zT))))  in sRGB (zT = DEM tile zoom = map z + 1 for 256-px tiles), i.e. ~ alpha*0.625*2^(0.3(15-zT))*g.
  // Equating the small-slope terms with sRGB ~ linear^(1/2.2):  alpha(z) = (0.2864/2.2) * s(zT) / (0.625 * 2^(0.3*(15-zT)))
  // Apple z = MapLibre z + 1 = zT, so both zoom shifts cancel. Highlight (lit side) uses the same alpha with white: the
  // formula's lit gain is <= +6 % linear (n.L max 1 vs 0.906), the white overlay is its small-slope approximation.
  function hillshadeAlpha(zMap) {
    const zT = zMap + 1;
    const gs = SN ? SN.climate_tinting['groundSettings.json'] : null;
    const s = gs ? (gs[String(Math.min(20, Math.max(1, Math.round(zT))))] || {}).groundElevationScale || 1 : 1;
    const L = SN ? SN.lighting : { lightColor_linear: [0.7085], tileLightDirection: [-0.366, -0.211, 0.906] };
    const cosAlt = Math.hypot(L.tileLightDirection[0], L.tileLightDirection[1]);
    const k = L.lightColor_linear[0] * cosAlt / LIGHT / 2.2;          // 0.1302
    const ml = 0.625 * Math.pow(2, zT < 15 ? 0.3 * (15 - zT) : 0);    // MapLibre's slope scale at this tile zoom
    return k * s / ml;
  }
  function hillshadeStops(colour) {
    // below PAL the globe post-pass shades Apple's own mesh (globe-light.js terrain term); the MapLibre hill-shade on the
    // terrarium DEM takes over across PAL 4.6-5
    const out = [PAL_Z0, `rgba(${colour},0)`];
    for (let z = Math.ceil(PAL_Z1); z <= 18; z++) out.push(z, `rgba(${colour},${hillshadeAlpha(z).toFixed(4)})`);
    return ['interpolate', ['linear'], ['zoom'], ...out];
  }
  // groundElevationScale at the Apple zoom of the current view (groundSettings.json, RENDER-PIPELINE 2.5: z1 14, z2 9, z3 7, z4 5 ...)
  function groundElevationScale(zMap) {
    const gs = SN ? SN.climate_tinting['groundSettings.json'] : null;
    const z = Math.min(20, Math.max(1, Math.round(zMap + 1)));
    return gs && gs[String(z)] ? gs[String(z)].groundElevationScale : 1;
  }

  // ---- style ----------------------------------------------------------------------------
  const TERRARIUM = (meta.sources.hillshade && meta.sources.hillshade.url) || meta.hillshade.url;
  // Palettes: 'globe' = the App's globe style sampled off its screenshot (palette-globe.json; pending — the globe
  // texture path is not decoded), light only, below PAL; 'flat' = decoded originals (ocean ramp, Landcover sheet
  // colours, ground rasters). Light mode shows the globe palette below z 4.6; '#...&pal=flat' forces flat throughout.
  function paletteName(m) {
    // 'globe' below PAL = the Mac App globe's own materials (DvMt, client:69 = 0) on Apple's class/climate rasters;
    // '#...&pal=flat' forces the flat colours at every zoom (debug)
    const h = location.hash.replace(/^#/, '');
    const q = new URLSearchParams(h.includes('&') ? h.slice(h.indexOf('&') + 1) : (h.includes('=') ? h : ''));
    return (q.get('pal') === 'flat' || !meta.dvmt_globe) ? 'flat' : 'globe';
  }
  const G = meta.ground;   // ui/basemap/ground.json via globe-data.py: sheet colours, bounds of the ground rasters
  const GG = meta.ground_globe;   // ui/basemap/ground-globe.json (data session): Apple's own globe rasters, bounds, groundElevationScale table
  function landFill(m) {
    // NE land fill under the ground rasters: Forest sheet colour (the default class) x light; sheet band for Apple z6
    const bands = G && G.sheet.colours.Forest && G.sheet.colours.Forest[m];
    const b = bands && (bands.find(x => x.zmin <= G.sheet.apple_zoom_used && G.sheet.apple_zoom_used < x.zmax) || bands[bands.length - 1]);
    return b ? lit(b.rgb) : (m === 'dark' ? meta.land_tints.humid.dark_hex : meta.land_tints.humid.light_hex);
  }
  function style(m) {
    const pal = paletteName(m);
    const flatLand = landFill(m);
    const sources = {};
    const layers = [];
    // the sphere itself (background = ocean where nothing else is drawn): globe = DvMt water ramp at 0.5 m, flat = the
    // shader ramp's coast colour (the flat sheet's Water fill (141,220,247) is within 6/255 of it)
    const globeLand = pal === 'globe' ? lit([1, 3, 5].map(k => parseInt(dvmtLand(m, 'Ground').slice(k, k + 2), 16))) : null;
    // background = what shows where no raster covers: the antialiased disc edge (MapLibre) and gaps -> a deep-ocean colour
    // (3000 m) so the limb pixels read as sea, not as the bright coast colour (the cyan jagged line the acceptance saw)
    const bgColour = pal === 'globe' ? dvmtRampColour(m, 3000) : (SN ? rampColour(m, 0.5) : meta.ocean_bands[0][m]);
    layers.push({ id: 'bg', type: 'background', paint: { 'background-color': bgColour } });
    // ocean: DvMt globe ramp below PAL, the flat renderer's ramp from PAL (both color-relief on the terrarium DEM)
    if (pal === 'globe') layers.push(...oceanLayers(m, palOut, 'ocean-globe', dvmtRampColour));
    layers.push(...oceanLayers(m, pal === 'globe' ? palIn : 1));
    // land: NE land fill (globe: DvMt Ground material; flat: Forest sheet colour) + ground rasters
    const landColour = pal === 'globe' ? ['interpolate', ['linear'], ['zoom'], PAL_Z0, globeLand, PAL_Z1, flatLand] : flatLand;
    layers.push({ id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': landColour, 'fill-antialias': true, 'fill-outline-color': landColour } });
    if (pal === 'globe' && m === 'light') {
      // no-tile fallback under Apple's rasters (southern hemisphere, Americas): the sampled pastel tints (pending)
      layers.push({ id: 'climate', type: 'raster', source: 'climate-globe', paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0, 'raster-opacity': palOut } });
      sources['climate-globe'] = { type: 'image', url: 'data/climate-globe.png', coordinates: meta.climate_image.bounds };
    }
    if (G) {
      sources['ground'] = { type: 'image', url: 'data/ground-' + m + '.png', coordinates: G.global.bounds };
      sources['ground-ea'] = { type: 'image', url: 'data/ground-ea-' + m + '.png', coordinates: G.east_asia.bounds };
      const op = pal === 'globe' ? palIn : 1;
      layers.push({ id: 'ground', type: 'raster', source: 'ground', paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0, 'raster-opacity': op } });
      layers.push({ id: 'ground-ea', type: 'raster', source: 'ground-ea', paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0, 'raster-opacity': op } });
    }
    if (GG && pal === 'globe') {
      // below PAL: Apple's own land-cover class + climate rasters (RENDER-PIPELINE 2.4b) recoloured at load with the
      // Mac App globe's DvMt materials (buildGlobeGround -> canvas source 'ground-globe-dvmt', added once built);
      // until the canvas is ready the data session's sheet-coloured raster stands in
      sources['ground-globe'] = { type: 'image', url: 'data/ground-globe-' + m + '.png', coordinates: GG.world.coordinates };
      layers.push({ id: 'ground-globe', type: 'raster', source: 'ground-globe', paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0, 'raster-opacity': palOut } });
    }
    // hill-shade: light az 240 / alt 65 (SHADER-NUMBERS 4.1), strength from groundElevationScale (hillshadeAlpha);
    // drawn above the land and BELOW every water layer — the ground shader has no relief on water (waterDepth path)
    layers.push({ id: 'hillshade', type: 'hillshade', source: 'dem',
      paint: {
        'hillshade-method': 'standard', 'hillshade-exaggeration': 0.5,
        'hillshade-illumination-direction': SN ? SN.lighting.azimuth_deg_clockwise_from_north : 240,
        'hillshade-illumination-anchor': 'map',
        'hillshade-shadow-color': hillshadeStops('0,0,0'),
        'hillshade-highlight-color': hillshadeStops('255,255,255'),
        'hillshade-accent-color': 'rgba(0,0,0,0)',
      } });
    // everything drawn here except the background and the hill-shade fades out at OVER
    const globeLayers = layers.map(l => (l.type === 'background' || l.type === 'hillshade') ? l : withFade(l, fadeOut));
    const flat = m === 'dark' ? flatDark : flatLight;
    const flatSources = {}, flatFills = [], flatWater = [], flatLines = [], flatSymbols = [], flatAlways = [];
    let glyphs;
    if (flat) {
      Object.assign(flatSources, flat.sources);
      glyphs = flat.glyphs;
      for (const l0 of flat.layers) {
        const l = { ...l0, id: 'flat-' + l0.id };
        // tropics / equator / polar circles (style-flat v6 geoline-*, Geolines-* rows, RENDER-PIPELINE 7.13/7.16):
        // drawn at every zoom — the App has them on the globe — above the ocean ramp, no fade
        if (l0.id.startsWith('geoline-')) { flatAlways.push(l); continue; }
        if (l.type === "symbol" || l.type === "circle") flatSymbols.push(withFade(l, fadeIn, PAL_Z0));   // .styl label styles (+ city dots) take over at PAL
        else if (l.type === 'line') flatLines.push(withFade(l, fadeIn, PAL_Z0));
        else if (l0.id === 'water') flatWater.push(withFade(l, fadeIn, PAL_Z0));
        else flatFills.push(withFade(l, fadeIn, PAL_Z0));            // background, landcover, landuse, park, building
      }
    }
    // order (bottom -> top): globe background · flat background/land fills · NE land + ground rasters · hill-shade ·
    // flat water (lakes over the land; OSM ocean under the ramp) · globe isobaths + shelf · ocean ramp · graticule ·
    // flat lines · flat symbols. The ocean ramp is opaque wherever the terrarium says depth >= 1 m, so the hill-shade
    // never shows on water; NE coastlines sit over OSM's until z 8 where the ramp has faded.
    const pick = ids => globeLayers.filter(l => ids.includes(l.id));
    const hs = pick(['hillshade'])[0];
    const gBg = globeLayers.filter(l => l.type === 'background');
    const gLand = pick(['land', 'climate', 'ground', 'ground-ea', 'ground-globe']);
    const gSea = globeLayers.filter(l => !gBg.includes(l) && !gLand.includes(l) && l !== hs);
    const ordered = [...gBg, ...flatFills, ...gLand, hs, ...flatWater, ...gSea, ...flatAlways, ...flatLines, ...flatSymbols];
    return {
      version: 8,
      // sphere from GLOBE_Z0 down, Mercator from GLOBE_Z1 up, morph in between (MapLibre's own 'globe' preset is 11->12)
      projection: { type: ['interpolate', ['linear'], ['zoom'], GLOBE_Z0, 'vertical-perspective', GLOBE_Z1, 'mercator'] },
      sky: { 'atmosphere-blend': 0.0 },   // Apple's rim is drawn by the post-pass (globe-light.js); MapLibre's Rayleigh sky off
      ...(glyphs ? { glyphs } : {}),
      sources: {
        ...sources,
        ...flatSources,
        land: { type: 'geojson', data: 'data/land.geojson' },
        dem: { type: 'raster-dem', tiles: [TERRARIUM], encoding: 'terrarium', tileSize: 256, maxzoom: 15,
               attribution: 'Terrain: AWS Terrain Tiles (Mapzen terrarium)' },
      },
      layers: ordered,
    };
  }

  // ---- Apple's globe ground recoloured with the Mac App globe's own materials -----------------------------
  // Inputs (data session, RENDER-PIPELINE 2.4b): data/spr-class-globe.png (4096^2, class index per pixel, 255 = no tile),
  // data/climate-{temp,arid}-globe.png (1024^2 codes). Colours: DvMt materials, client:69 = 0, day / night, Apple z4 band
  // (meta.dvmt_globe); climate tint = groundSettings HSV cells sampled bilinearly by the codes (SHADER-NUMBERS 3.2, 4.4);
  // x light(0,0,1); sRGB. Done here at load (a 924-entry LUT, one pass over 16.7 M pixels) so that no new Apple-derived
  // raster enters the repository. Verification: sampled palette-globe humid #e9f6d8 vs Forest #deecd3 x light = #e3f1d8.
  const CLASS_UNTINTED = new Set(['Ground', 'DryLake', 'Water']);   // DvMt k = 0 materials carry no climate cells
  function hsvAdjust(lin, dh, ds, dv) {
    const [r, g, b] = lin; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
    let h = 0; if (d > 1e-9) { h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; if (h < 0) h += 360; }
    let sat = mx > 1e-9 ? d / mx : 0, v = mx;
    h = (h + dh + 360) % 360; sat = Math.max(0, Math.min(1, sat + ds)); v = Math.max(0, Math.min(1, v + dv));
    const c = v * sat, hp = h / 60, x = c * (1 - Math.abs(hp % 2 - 1)), m0 = v - c, i = Math.floor(hp) % 6;
    const rgb = [[c, x, 0], [x, c, 0], [0, c, x], [0, x, c], [x, 0, c], [c, 0, x]][i];
    return [rgb[0] + m0, rgb[1] + m0, rgb[2] + m0];
  }
  async function buildGlobeGround(m) {
    if (!GG || !meta.dvmt_globe) return null;
    const load = async url => createImageBitmap(await (await fetch(url)).blob());
    const [cls, temp, arid] = await Promise.all(['data/spr-class-globe.png', 'data/climate-temp-globe.png', 'data/climate-arid-globe.png'].map(load));
    const px = (bm) => { const c = document.createElement('canvas'); c.width = bm.width; c.height = bm.height; const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(bm, 0, 0); return { d: x.getImageData(0, 0, bm.width, bm.height).data, w: bm.width }; };
    const C = px(cls), T = px(temp), A = px(arid);
    const adj = GG.climate.hsv_deltas[m];
    const tAdj = [adj.arcticHSVAdjustment, [0, 0, 0], adj.veryHotHSVAdjustment], aAdj = [adj.veryWetHSVAdjustment, [0, 0, 0], adj.veryDryHSVAdjustment];
    const classes = GG.classes;                       // index -> class name (spr-class-globe.png values)
    // LUT[class][T 0..6][A 0..5] -> [r,g,b] sRGB bytes
    const lut = classes.map(name => {
      // Water: the material's ramp at 0.5 m (lakes; the sea is covered by the color-relief ramp drawn above)
      const hexc = name === 'Water' ? dvmtRampColour(m, 0.5) : dvmtLand(m, name, 4);
      if (!hexc) return null;
      const base = [1, 3, 5].map(k => (name === 'Water' ? toLin(parseInt(hexc.slice(k, k + 2), 16)) / LIGHT : toLin(parseInt(hexc.slice(k, k + 2), 16))));
      const cells = [];                               // cells[a][t]
      for (let a = 0; a < 3; a++) { cells.push([]); for (let t = 0; t < 3; t++) cells[a].push(CLASS_UNTINTED.has(name) ? base : hsvAdjust(base, tAdj[t][0] + aAdj[a][0], tAdj[t][1] + aAdj[a][1], tAdj[t][2] + aAdj[a][2])); }
      const out = [];
      for (let tc = 0; tc < 7; tc++) { out.push([]); for (let ac = 0; ac < 6; ac++) {
        const tcell = Math.max(0, Math.min(2, 1 + (tc - 3) / 3)), acell = Math.max(0, Math.min(2, ac < 3 ? 1 + (ac - 3) / 3 : 1 + (ac - 3) / 2));   // ground-globe.json climate
        const t0 = Math.min(1, Math.floor(tcell)), a0 = Math.min(1, Math.floor(acell)), ft = tcell - t0, fa = acell - a0;
        const c = [0, 1, 2].map(k => ((cells[a0][t0][k] * (1 - ft) + cells[a0][t0 + 1][k] * ft) * (1 - fa) + (cells[a0 + 1][t0][k] * (1 - ft) + cells[a0 + 1][t0 + 1][k] * ft) * fa) * LIGHT);
        out[tc].push(c.map(toSrgb8));
      } }
      return out;
    });
    const N = C.w, out = new Uint8ClampedArray(N * N * 4), ratio = T.w / N;
    for (let y = 0; y < N; y++) {
      const ty = Math.floor(y * ratio) * T.w;
      for (let x = 0; x < N; x++) {
        const i = y * N + x, ci = C.d[i * 4];
        const table = ci < classes.length ? lut[ci] : null;
        if (!table) continue;                          // 255 = no tile -> alpha 0
        const ti = (ty + Math.floor(x * ratio)) * 4;
        const tc = T.d[ti] === 255 ? 3 : Math.min(6, T.d[ti]), ac = A.d[ti] === 255 ? 3 : Math.min(5, A.d[ti]);
        const c = table[tc][ac]; const o = i * 4;
        out[o] = c[0]; out[o + 1] = c[1]; out[o + 2] = c[2]; out[o + 3] = 255;
      }
    }
    const canvas = document.createElement('canvas'); canvas.width = N; canvas.height = N;
    canvas.getContext('2d').putImageData(new ImageData(out, N, N), 0, 0);
    return canvas;
  }
  let globeGroundCanvas = null, globeGroundMode = null, globeGroundUrl = null;
  async function attachGlobeGround() {
    const m = mode();
    if (paletteName(m) !== 'globe' || !GG) return;
    if (!globeGroundCanvas || globeGroundMode !== m) {
      globeGroundCanvas = await buildGlobeGround(m); globeGroundMode = m;
      // an image source (blob URL) rather than a canvas source: MapLibre 5.6 drew the 4096^2 canvas source black
      if (globeGroundUrl) URL.revokeObjectURL(globeGroundUrl);
      globeGroundUrl = globeGroundCanvas ? URL.createObjectURL(await new Promise(r => globeGroundCanvas.toBlob(r, 'image/png'))) : null;
    }
    if (!globeGroundUrl || !map.getLayer('ground-globe')) return;
    if (map.getSource('ground-globe-dvmt')) { map.removeLayer('ground-globe-dvmt'); map.removeSource('ground-globe-dvmt'); }
    map.addSource('ground-globe-dvmt', { type: 'image', url: globeGroundUrl, coordinates: GG.world.coordinates });
    map.addLayer({ id: 'ground-globe-dvmt', type: 'raster', source: 'ground-globe-dvmt', paint: { 'raster-resampling': 'linear', 'raster-fade-duration': 0, 'raster-opacity': palOut } }, 'hillshade');
    map.setPaintProperty('ground-globe', 'raster-opacity', 0);     // the sheet-coloured stand-in steps back
  }

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
  // the flat style (v5+) reads tiles/transit.pmtiles (N02 railways) through the pmtiles protocol
  if (window.pmtiles && maplibregl.addProtocol) maplibregl.addProtocol('pmtiles', new pmtiles.Protocol().tile);
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
  map.on('error', e => { const m = 'map: ' + (e && e.error && e.error.message || e); (window.__errs = window.__errs || []).push(m); console.error(m); });
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
  // Globe labels (below the morph): labelSpec (snapshotter flat renders, labels-globe.json) and meta.labels_app
  // (measured on the App's GLOBE screenshot) — both sampled, pending the label sheet decode. From the morph on,
  // the flat style's symbol layers (.styl City-Style / Country-Label / Ocean-Label via to_maplibre.py) take over;
  // only deep-sea names and the graticule labels (nothing in the flat style replaces them) stay to OVER.
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
        case 'graticule': return geoLabel() || A.graticule || flat('graticule');
      }
    }
    if (kind === 'graticule' && geoLabel()) return geoLabel();
    switch (kind) {
      case 'country': return flat('country');
      case 'capital': case 'city': case 'deep': return flat('deep');
      case 'sea': return flat('ocean', seaSize);
      case 'ocean': return flat('ocean', oceanSize);
      case 'graticule': return flat('graticule');
    }
    return flat('continent');
  }
  // country size between two measurements: the App globe at z 3.12 (labels_app.country 10.5 pt) and the
  // flat render at z 4.2 (labels.country 11.0 pt); flat beyond. The .styl labelInfo.height curve
  // (9.5 -> 14 over z 3-5) is not a font size (it overshoots both measurements) and is not used.
  function countrySize() {
    const z = map ? map.getZoom() : 3.12;
    const a = { z: 3.12, s: appSpec.country.size_pt }, b = { z: 4.2, s: labelSpec.country.size_pt };
    if (z <= a.z) return a.s; if (z >= b.z) return b.s;
    return a.s + (b.s - a.s) * (z - a.z) / (b.z - a.z);
  }
  // Geolines label: textColor, labelInfo.height (Apple z bands, linear inside a band to heightCurveLimit),
  // fontSpec %$default,medium-G3,width=90 -> weight medium; halo rgb(194,219,234) alpha 0.15 (RENDER-PIPELINE 7.13).
  // labelColorLumAdjustment (-25) is not applied: the App's label reads lighter than the sheet colour, not darker.
  function geoLabel() {
    const gs = meta.geolines && meta.geolines.styles[`Geolines-Tropics.Explore-${mode() === 'dark' ? 'Dark' : 'Light'}-Elevated`];
    if (!gs) return null;
    const zA = (map ? map.getZoom() : 3.12) + 1;
    const li = gs.labelInfo.find(b => b.zmin <= zA && zA < b.zmax) || gs.labelInfo[gs.labelInfo.length - 1];
    const v = li.value, size = v.heightCurveLimit ? v.height + (v.heightCurveLimit - v.height) * (zA - li.zmin) / (li.zmax - li.zmin) : v.height;
    const tc = gs.textColor[0].value.rgb, hc = gs.labelHaloColor && gs.labelHaloColor[0].value;
    return { weight: 'medium', size_pt: Math.round(size * 100) / 100, tracking_pt: 0, italic: false, case: null, colour: hex(tc), dark: hex(tc),
             halo: hc && hc.alpha > 0.2 ? hex(hc.rgb) : null, halo_width_px_2x: 1 };
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
    // continents: the globe sheet hides Continent-PointLabel from Apple z3 (= MapLibre z2), whatever NE's max_label says
    if (p.kind === 'continent') p.max_label = Math.min(p.max_label ?? 99, 2.0);
    markers.push(makeLabel(p, p.kind, f.geometry.coordinates));
  }
  // cities (map/data/cities.geojson from the data session): capitals and cities by their min_zoom, globe_rank <= 4
  try {
    const cities = (await (await fetch('data/cities.geojson')).json()).features;
    for (const f of cities) {
      const p = f.properties;
      if (p.globe_rank > 4) continue;   // min_zoom (data session's ranking) decides when a city appears
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
    const g = lastGlobe;   // disc geometry + visible-cap angle from drawOverlay()
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
  const globeFade = () => Math.max(0, Math.min(1, (OVER_Z1 - map.getZoom()) / (OVER_Z1 - OVER_Z0)));
  const morphFade = () => Math.max(0, Math.min(1, (GLOBE_Z1 - map.getZoom()) / (GLOBE_Z1 - GLOBE_Z0)));
  const palFade = () => Math.max(0, Math.min(1, (PAL_Z1 - map.getZoom()) / (PAL_Z1 - PAL_Z0)));
  const LATE_KINDS = new Set(['deep', 'graticule']);      // nothing in the flat style replaces these: stay to OVER
  function apply(it) {
    const f = LATE_KINDS.has(it.kind) ? globeFade() : palFade();
    it.el.style.visibility = (f > 0 && it.front && !it.collided) ? 'visible' : 'hidden';
    it.el.style.setProperty('--fade', f.toFixed(3));   // children fade; MapLibre owns the element's own opacity
  }
  function updateLabels() {
    const z = map.getZoom();
    for (const it of markers) {
      const on = inRange(it, z);
      if (on && !it.added) { it.mk.addTo(map); it.added = true; }
      else if (!on && it.added) { it.mk.remove(); it.added = false; }
      if (it.added && (it.kind === 'country' || it.kind === 'graticule')) styleLabel(it.el, it.kind, mode());   // size follows the zoom curve
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
  map.once('load', () => { attachGlobeGround().catch(e => (window.__errs = window.__errs || []).push('globe ground: ' + (e && e.message || e))); });
  map.on('zoomend', updateLabels);
  map.on('moveend', () => { syncFront(); collide(); });
  let idleCount = 0;
  map.on('idle', () => { idleCount++; syncFront(); collide(); setTimeout(() => { syncFront(); collide(); }, 800); });   // after every source finished loading and rendering
  addEventListener('resize', () => setTimeout(() => { syncFront(); collide(); }, 300));
  map.on('render', syncFront);

  // ---- globe overlay: lighting + rim (globe-light.js, decoded). The former haze table (haze-globe.json) is not
  // drawn: RENDER-PIPELINE 6 — the inner darkening is the n.L term plus the rim, both in the post-pass.
  // #light: WebGL post-pass over MapLibre's globe pixels; #limb: 2D fallback canvas when WebGL is unavailable.
  const lightCanvas = document.createElement('canvas');
  lightCanvas.id = 'light';
  document.getElementById('map').appendChild(lightCanvas);
  const limb = document.createElement('canvas');
  limb.id = 'limb';
  document.getElementById('map').appendChild(limb);
  let post = null;
  try { post = (SN && window.__globeLight) ? window.__globeLight.create(lightCanvas, SN) : null; if (post) post.onHeightLoaded = () => map.triggerRepaint(); }
  catch (e) { (window.__errs = window.__errs || []).push(String(e && e.message || e)); console.error(e); }
  // rim: GlobeAtmosphere far-camera constants (SHADER-NUMBERS 3.3 / 4.5, RENDER-PIPELINE 2.2): R = 6356752.31 m, corona
  // thickness maxHeight 150 km, colorMidpoint 0.5; on screen the corona is centred on the silhouette (App limb profile at
  // 2x, map/README.md "Rim geometry"): horizonColor -> midColor over the disc's last 75 km, midColor -> black over 75 km
  // outside. Colours = the sheet's Sky-Standard-Day fillColor (155,196,237) / prop 202 (212,226,240), Night (35,76,122) /
  // (86,109,165), linearised — byte-identical to the captured skyTopColor / skyBottomColor (shader-numbers.json
  // ground_atmosphere); lighting on (h >= 2 * maxHeight)
  const RIM = { R: 6356752.31, maxHeight: 150000, colorMidpoint: 0.5,
                mid: { light: [155, 196, 237], dark: [35, 76, 122] }, horizon: { light: [212, 226, 240], dark: [86, 109, 165] } };
  // fogParameters.w of the globe tiles (the only constant of the atmos term not captured — FITTED, map/README.md "Still
  // sampled"): least squares on 108 deep-ocean samples along six rays of native-nosidebar.png at r/limb 0.80-0.975 (inside
  // the corona's inner edge) vs our render without the term: rms 0.0446 linear at w = 1.15 (0.0507 without the term)
  const ATMOS_W = 1.15;
  const rimPx = r => r * (RIM.maxHeight * RIM.colorMidpoint) / RIM.R;      // half the corona (75 km) in CSS px at the limb
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
  let lastGlobe = null;   // {r, cx, cy, capDeg} of the projected disc, refreshed every frame
  // ---- stars: Apple's catalogue (basemap/data/globe/stars.bin, RENDER-PIPELINE 2.1) ------------------------
  // 10000 x float32[3]: angle 0-2pi, angle +-1.54 rad, brightness 14.08 -> 10.02. Frame and the GlobeStars
  // point-size/alpha formula are not decoded (stars-format.md): the two angles are taken as right ascension /
  // declination in the earth-fixed frame (no sidereal rotation), projected through the page camera; alpha =
  // (brightness - 10) / 4.1; size = 1.2 pt (measured on the App, pending). Drawn once per camera change.
  let starCat = null, starsDrawn = 0;
  fetch('../basemap/data/globe/stars.bin').then(r => r.ok ? r.arrayBuffer() : null).then(buf => { if (buf) { starCat = new Float32Array(buf); drawStars(true); } }).catch(() => {});
  let lastStarKey = '';
  function drawStars(force) {
    const dpr = devicePixelRatio || 1;
    const w = innerWidth, h = innerHeight;
    const g = lastGlobe, c = map ? map.getCenter() : null;
    const key = g && c ? [w, h, g.r | 0, g.cx | 0, g.cy | 0, c.lat.toFixed(2), c.lng.toFixed(2)].join(',') : [w, h].join(',');
    if (!force && key === lastStarKey) return;
    lastStarKey = key;
    stars.width = w * dpr; stars.height = h * dpr;
    const ctx = stars.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = meta.background.space;
    ctx.fillRect(0, 0, w, h);
    if (!starCat || !g || !c) return;
    const D = 1 / Math.cos(g.capDeg * Math.PI / 180), f = g.r * Math.sqrt(D * D - 1);
    const la = c.lat * Math.PI / 180, lo = c.lng * Math.PI / 180;
    // view frame in ECEF: forward = -camera direction, right = east, up = north
    const fw = [-Math.cos(la) * Math.cos(lo), -Math.cos(la) * Math.sin(lo), -Math.sin(la)];
    const rt = [-Math.sin(lo), Math.cos(lo), 0];
    const up = [-Math.sin(la) * Math.cos(lo), -Math.sin(la) * Math.sin(lo), Math.cos(la)];
    const s = meta.background.star_size_pt;
    let drawn = 0;
    for (let i = 0; i < starCat.length; i += 3) {
      const ra = starCat[i], dec = starCat[i + 1], br = starCat[i + 2];
      const v = [Math.cos(dec) * Math.cos(ra), Math.cos(dec) * Math.sin(ra), Math.sin(dec)];
      const z = v[0] * fw[0] + v[1] * fw[1] + v[2] * fw[2];
      if (z <= 0.05) continue;
      const x = g.cx + f * (v[0] * rt[0] + v[1] * rt[1] + v[2] * rt[2]) / z;
      const y = g.cy - f * (v[0] * up[0] + v[1] * up[1] + v[2] * up[2]) / z;
      if (x < 0 || y < 0 || x > w || y > h) continue;
      if (Math.hypot(x - g.cx, y - g.cy) < g.r) continue;      // behind the globe
      const a = Math.max(0, Math.min(1, (br - 10) / 4.1));
      ctx.fillStyle = `rgba(255,255,255,${a.toFixed(3)})`;
      ctx.fillRect(x, y, s, s);
      drawn++;
    }
    starsDrawn = drawn;
  }
  addEventListener('resize', () => drawStars(true));

  const OUTER = meta.background.limb_profile_2x;   // measured rim profile (pending, only used when the post-pass is unavailable)
  function drawOverlay() {
    const dpr = devicePixelRatio || 1;
    const w = innerWidth, h = innerHeight;
    const g = globeRadiusPx();
    lastGlobe = (g && g.r > 10 && g.r < 6000) ? g : null;
    const fade = morphFade();
    limb.width = w * dpr; limb.height = h * dpr;
    limb.style.width = w + 'px'; limb.style.height = h + 'px';
    const ctx = limb.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!lastGlobe || fade <= 0) { if (post) post.clear(); drawStars(); return; }
    lightCanvas.style.width = w + 'px'; lightCanvas.style.height = h + 'px';
    if (post) {
      const rim = { mid: RIM.mid[mode()].map(toLin), horizon: RIM.horizon[mode()].map(toLin), px: rimPx(g.r) };
      const c = map.getCenter();
      // Apple's ground shader on the globe: the sphere normal tilted by its mesh heights x groundElevationScale(Apple z),
      // fading out over PAL where the terrarium hill-shade takes over (globe-light.js)
      // ground atmosphere (SHADER-NUMBERS 3.1 / 4.2): skyBottomColor + horizonGlowParameters captured; the globe tiles'
      // fogParameters.w was not (MKMapView never enters the globe path) -> ATMOS_W fitted on the App's limb profile
      const ga = SN.ground_atmosphere[mode()];
      post.draw(map.getCanvas(), g, dpr, rim, 1, fade, GG ? { lat: c.lat, lng: c.lng, scale: groundElevationScale(map.getZoom()), amount: palFade() } : null,
                { sky: ga.skyBottomColor_linear.slice(0, 3), hg: ga.horizonGlowParameters, w: ATMOS_W });
    } else {
      // fallback without WebGL: the measured rim profile (pending)
      const outer = ctx.createRadialGradient(g.cx, g.cy, g.r, g.cx, g.cy, g.r + OUTER.length / 2);
      OUTER.forEach((rgb, i) => outer.addColorStop(Math.min(1, i / (OUTER.length - 1)), `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`));
      ctx.fillStyle = outer;
      ctx.beginPath(); ctx.arc(g.cx, g.cy, g.r + OUTER.length / 2, 0, Math.PI * 2); ctx.arc(g.cx, g.cy, g.r, 0, Math.PI * 2, true); ctx.fill();
    }
    drawStars();   // catalogue stars move with the camera; keyed on the disc geometry
  }
  map.on('render', drawOverlay);
  addEventListener('resize', drawOverlay);

  // ---- light / dark follow the system -----------------------------------------------------
  mq.addEventListener('change', () => {
    const m = mode();
    map.setStyle(style(m));
    map.once('styledata', () => attachGlobeGround().catch(() => {}));
    for (const it of markers) styleLabel(it.el, it.kind, m);
  });
  window.__globe = {
    map, meta, shader: SN, setHashExtra, hashExtras: () => hashState.q,
    get idleCount() { return idleCount; },
    get labelStats() { const m = markers.filter(it => it.added); return { inRange: m.length, front: m.filter(it => it.front).length, visible: m.filter(it => it.front && !it.collided).length }; },
    hillshadeAlpha, rampColour, dvmtRampColour, dvmtLand, LIGHT, post, groundElevationScale, buildGlobeGround, get globeGroundCanvas() { return globeGroundCanvas; },
    get starsDrawn() { return starsDrawn; },
    globeRadiusPx,
  };
})();
