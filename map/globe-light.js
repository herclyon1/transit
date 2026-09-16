// Globe post-pass: Apple's DaVinci lighting and GlobeAtmosphere rim, run over MapLibre's rendered globe.
// Formulas and constants: SHADER-NUMBERS.md 3.1 / 3.3 / 4.1 and basemap/data/shader/shader-numbers.json
// (captured from VectorKit, 2026-09-16). MapLibre paints every surface colour as albedo x light(0,0,1)
// (the flat renderer's value, so the same colours serve the flat map); this pass reads those pixels back,
// linearises them, and re-lights per pixel:
//   light(n)  = ambientLightColor * cube(n) + lightColor * max(n.L, 0)        (linear RGB; n in view space)
//   n         = the terrain normal (SHADER-NUMBERS 3.1, globe path): the sphere normal at the pixel, tilted by the slope of
//               Apple's own mesh heights (map/data/height-globe*.png, RENDER-PIPELINE 2.4b) x groundElevationScale(Apple z)
//               (groundSettings.json) in the local east/north/up frame, re-expressed in view space; water is flat (mesh z ~ 0)
//   colour    = albedo * light(n) = pixel_lin * light(n) / light(0,0,1)
//   rim       = mix(midColor, black, t2) * (lightColor * I + ambientLightColor),  I = 0.25 * (L.pos + 1)^2
//               over (outerRadius - innerRadius) * (1 - colorMidPoint) = 75 km outside the silhouette
//               (far camera: outerRadius = R + maxHeight 150 km, colorMidPoint 0.5; the horizon->mid half lies
//               inside the silhouette on screen, see map/README.md)
// No separate "inner haze": RENDER-PIPELINE 6 — the darkening toward the limb is this n.L term plus the rim. The
// ground shader's atmos term (skyBottomColor bleed, fogParameters.w) was not captured for globe tiles; the
// residual it may account for is recorded in map/README.md (rim geometry), not modelled.
(function () {
  const VS = `attribute vec2 a_pos; void main() { gl_Position = vec4(a_pos, 0.0, 1.0); }`;
  const FS = `
    precision highp float;
    uniform sampler2D u_map;          // MapLibre canvas (premultiplied sRGB)
    uniform samplerCube u_cube;       // ambient irradiance cube (linear, 8x8x6)
    uniform vec2 u_size;              // canvas size in device px
    uniform vec2 u_c;                 // disc centre (device px, y down)
    uniform float u_r;                // disc radius (device px)
    uniform float u_D;                // camera distance, earth radii
    uniform float u_f;                // focal length, device px
    uniform vec3 u_L;                 // light direction, view space (x right, y up, z to viewer)
    uniform float u_lc;               // lightColor (grey, linear)
    uniform float u_amb;              // ambientLightColor (grey, linear)
    uniform float u_lightC;           // light(0,0,1) with the same cube sample -> factor 1 at the disc centre
    uniform vec3 u_mid;               // corona mid colour (Sky-Standard fillColor = captured skyTopColor), linear
    uniform vec3 u_horizon;           // corona horizon colour (Sky-Standard prop 202 = captured skyBottomColor), linear
    uniform float u_rimPx;            // half the corona: 75 km at limb scale, device px (inner half over the disc, outer half outside)
    uniform float u_rimLight;         // AtmosphereConstants.lightingEnabled (1 = far camera)
    uniform float u_alpha;            // fade (morph to flat)
    uniform sampler2D u_height;       // Apple mesh heights, world Web-Mercator, terrarium (height-globe.png)
    uniform sampler2D u_heightEa;     // same, East Asia lon 90-180 / lat 0-66.51 (height-globe-ea.png)
    uniform vec2 u_hsize;             // texel counts of the two height textures (world, ea)
    uniform mat3 u_frame;             // columns: east, north, up unit vectors of the view centre in ECEF (view -> ECEF)
    uniform float u_scale;            // groundElevationScale(Apple z)
    uniform float u_terrain;          // 0..1: how much of the terrain tilt to apply (fades out over PAL)
    uniform vec3 u_sky;               // GroundAtmosphere.skyBottomColor, linear (light / dark)
    uniform vec2 u_hg;                // GroundAtmosphere.horizonGlowParameters (2.0, 0.5) [cap]
    uniform float u_atmosW;           // fogParameters.w for globe tiles (not captured; fitted on the App's limb profile, map/README.md)
    const float PI = 3.14159265358979;
    const float EARTH_W = 40075016.686;                                    // Web-Mercator world width, metres
    const float EA_LNG0 = 90.0, EA_LNG1 = 180.0, EA_LAT1 = 66.51326;       // ground-globe.json east_asia
    float mercY(float lat) { return log(tan(PI / 4.0 + lat / 2.0)); }
    float terr(vec4 c) { return (c.r * 256.0 + c.g + c.b / 256.0) * 255.0 - 32768.0; }
    // slope of the height field (metres per metre) in local east/north at lat/lng (radians); terrain normal in that frame
    vec3 terrainNormal(float lat, float lng) {
      float latd = degrees(lat), lngd = degrees(lng);
      bool ea = lngd >= EA_LNG0 && lngd <= EA_LNG1 && latd >= 0.0 && latd <= EA_LAT1;
      vec2 uv; float texels; float span;                                   // span = longitude span of the texture, degrees
      if (ea) { uv = vec2((lngd - EA_LNG0) / (EA_LNG1 - EA_LNG0), (mercY(radians(EA_LAT1)) - mercY(lat)) / (mercY(radians(EA_LAT1)) - 0.0)); texels = u_hsize.y; span = 90.0; }
      else    { uv = vec2((lngd + 180.0) / 360.0, (PI - mercY(lat)) / (2.0 * PI)); texels = u_hsize.x; span = 360.0; }
      float d = 1.0 / texels;
      float mPerTexel = EARTH_W * (span / 360.0) / texels * cos(lat);        // conformal: same east and north
      float hE, hW, hN, hS;
      if (ea) { hE = terr(texture2D(u_heightEa, uv + vec2(d, 0.0))); hW = terr(texture2D(u_heightEa, uv - vec2(d, 0.0)));
                hN = terr(texture2D(u_heightEa, uv - vec2(0.0, d))); hS = terr(texture2D(u_heightEa, uv + vec2(0.0, d))); }
      else    { hE = terr(texture2D(u_height, uv + vec2(d, 0.0)));   hW = terr(texture2D(u_height, uv - vec2(d, 0.0)));
                hN = terr(texture2D(u_height, uv - vec2(0.0, d)));   hS = terr(texture2D(u_height, uv + vec2(0.0, d))); }
      float ge = (hE - hW) / (2.0 * mPerTexel), gn = (hN - hS) / (2.0 * mPerTexel);
      return normalize(vec3(-u_scale * ge, -u_scale * gn, 1.0));
    }
    vec3 toLin(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)); }
    vec3 toSrgb(vec3 v) { v = clamp(v, 0.0, 1.0); return mix(v * 12.92, 1.055 * pow(v, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, v)); }
    void main() {
      vec2 px = vec2(gl_FragCoord.x, u_size.y - gl_FragCoord.y);          // y down like the DOM
      vec2 uv = gl_FragCoord.xy / u_size;
      float dx = (px.x - u_c.x) / u_f, dy = -(px.y - u_c.y) / u_f;
      float A = dx * dx + dy * dy + 1.0, B = -2.0 * u_D, C = u_D * u_D - 1.0;
      float disc = B * B - 4.0 * A * C;
      vec2 d = px - u_c; float rho = length(d);
      if (disc >= 0.0) {
        float t = (-B - sqrt(disc)) / (2.0 * A);
        vec3 n = vec3(dx * t, dy * t, u_D - t);                          // unit sphere -> the normal
        if (u_terrain > 0.0) {
          vec3 ne = u_frame * n;                                          // ECEF
          float lat = asin(clamp(ne.z, -1.0, 1.0)), lng = atan(ne.y, ne.x);
          vec3 tn = terrainNormal(lat, lng);
          // local frame at the pixel, in view space: up = n, east = d/dlng, north = up x east
          vec3 eastE = vec3(-sin(lng), cos(lng), 0.0);
          vec3 eastV = normalize(eastE * u_frame);                          // ECEF -> view: multiply by the transpose
          vec3 northV = cross(n, eastV);
          vec3 nt = normalize(tn.x * eastV + tn.y * northV + tn.z * n);
          n = normalize(mix(n, nt, u_terrain));
        }
        vec4 m = texture2D(u_map, uv);
        vec3 base = m.a > 0.001 ? m.rgb / m.a : vec3(0.0);
        vec3 lin = toLin(base);
        float light = u_amb * textureCube(u_cube, n).r + u_lc * max(dot(n, u_L), 0.0);
        vec3 col = lin * light / u_lightC;
        // ground atmosphere term (SHADER-NUMBERS 3.1): the sky-coloured glow that brightens the ground toward the limb —
        // atmos = clamp((1 - hg.x) + hg.x * clamp((1 - n.V) / w, 0, 1), 0, 1) * hg.y * ambientLightColor * skyBottomColor
        vec3 P = vec3(dx * t, dy * t, u_D - t);
        vec3 V = normalize(vec3(0.0, 0.0, u_D) - P);
        float atm = clamp((1.0 - u_hg.x) + u_hg.x * clamp((1.0 - dot(n, V)) / u_atmosW, 0.0, 1.0), 0.0, 1.0) * u_hg.y;
        col += atm * u_amb * u_sky;
        // corona, inner half (GlobeAtmosphere fragment, RENDER-PIPELINE 2.2): mix(horizonColor, midColor, t1) x light, opaque
        // over the disc's last 75 km (colorMidPoint 0.5 of the 150 km corona falls on the silhouette; App measured, map/README.md)
        vec2 dir = normalize(vec2(d.x, -d.y));
        float I = 0.25 * pow(dot(u_L, vec3(dir, 0.0)) + 1.0, 2.0);
        float rimL = mix(1.0, u_lc * I + u_amb, u_rimLight);
        float t1 = clamp((rho - (u_r - u_rimPx)) / u_rimPx, 0.0, 1.0);
        vec3 rim = mix(u_horizon, u_mid, t1) * rimL;
        col = mix(rim, col, m.a);                                         // MapLibre's antialiased disc edge: rim, not black
        col = mix(col, rim, smoothstep(-1.0, 0.0, rho - (u_r - u_rimPx)));  // 1 device px edge at the corona's inner radius
        gl_FragColor = vec4(toSrgb(col) * u_alpha, u_alpha);
      } else if (rho - u_r < u_rimPx) {
        // corona, outer half: mix(midColor, endColor = black, t2) x light over 75 km outside the silhouette
        float t2 = clamp((rho - u_r) / u_rimPx, 0.0, 1.0);
        vec2 dir = normalize(vec2(d.x, -d.y));
        float I = 0.25 * pow(dot(u_L, vec3(dir, 0.0)) + 1.0, 2.0);
        float rimL = mix(1.0, u_lc * I + u_amb, u_rimLight);
        vec3 col = u_mid * (1.0 - t2) * rimL;
        gl_FragColor = vec4(toSrgb(col) * u_alpha, u_alpha);
      } else {
        discard;
      }
    }`;
  function compile(gl, type, src) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error('globe-light shader: ' + gl.getShaderInfoLog(s));
    return s;
  }
  function create(canvas, sn) {
    const gl = canvas.getContext('webgl', { premultipliedAlpha: true, alpha: true, antialias: false, preserveDrawingBuffer: false });
    if (!gl) return null;
    const prog = gl.createProgram();
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS)); gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error('globe-light link: ' + gl.getProgramInfoLog(prog));
    gl.useProgram(prog);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(prog, 'a_pos'); gl.enableVertexAttribArray(aPos); gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    const U = {}; for (const name of ['u_map', 'u_cube', 'u_size', 'u_c', 'u_r', 'u_D', 'u_f', 'u_L', 'u_lc', 'u_amb', 'u_lightC', 'u_mid', 'u_horizon', 'u_rimPx', 'u_rimLight', 'u_alpha',
                                      'u_height', 'u_heightEa', 'u_hsize', 'u_frame', 'u_scale', 'u_terrain', 'u_sky', 'u_hg', 'u_atmosW']) U[name] = gl.getUniformLocation(prog, name);
    // height textures (units 2, 3): Apple's mesh heights as terrarium PNGs (RENDER-PIPELINE 2.4b); 1x1 zero until loaded
    const hsize = [1, 1];
    const mkTex = (unit) => { const t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([128, 0, 0, 255]));   // 32768 -> 0 m
      for (const [k, v] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
      return t; };
    const heightTex = mkTex(2), heightEaTex = mkTex(3);
    function loadHeight(url, unit, tex, idx) {
      const img = new Image();
      img.onload = () => { gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, tex); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img); hsize[idx] = img.width; if (onHeight) onHeight(); };
      img.src = url;
    }
    let onHeight = null;
    loadHeight('data/height-globe.png', 2, heightTex, 0);
    loadHeight('data/height-globe-ea.png', 3, heightEaTex, 1);
    // map texture (unit 0)
    const mapTex = gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, mapTex);
    for (const [k, v] of [[gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
    // irradiance cube (unit 1): faces_hex are the raw linear RGBA8 bytes; faces_order +x -x +y -y +z -z
    const cube = sn.ambient_irradiance_cube;
    const cubeTex = gl.createTexture(); gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_CUBE_MAP, cubeTex);
    const targets = { '+x': gl.TEXTURE_CUBE_MAP_POSITIVE_X, '-x': gl.TEXTURE_CUBE_MAP_NEGATIVE_X, '+y': gl.TEXTURE_CUBE_MAP_POSITIVE_Y, '-y': gl.TEXTURE_CUBE_MAP_NEGATIVE_Y, '+z': gl.TEXTURE_CUBE_MAP_POSITIVE_Z, '-z': gl.TEXTURE_CUBE_MAP_NEGATIVE_Z };
    const [w, h] = cube.size;
    let centreZ = 0;
    cube.faces_order.forEach((face, fi) => {
      const data = new Uint8Array(w * h * 4);
      cube.faces_hex[fi].forEach((row, j) => row.forEach((hex, i) => {
        const o = (j * w + i) * 4; data[o] = parseInt(hex.slice(1, 3), 16); data[o + 1] = parseInt(hex.slice(3, 5), 16); data[o + 2] = parseInt(hex.slice(5, 7), 16); data[o + 3] = 255;
      }));
      if (face === '+z') { const c = cube.faces_hex[fi]; centreZ = (parseInt(c[3][3].slice(1, 3), 16) + parseInt(c[3][4].slice(1, 3), 16) + parseInt(c[4][3].slice(1, 3), 16) + parseInt(c[4][4].slice(1, 3), 16)) / 4 / 255; }
      gl.texImage2D(targets[face], 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
    });
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_CUBE_MAP, k, v);
    const L = sn.lighting.tileLightDirection, lc = sn.lighting.lightColor_linear[0], amb = sn.lighting.ambientLightColor_linear[0];
    const lightC = amb * centreZ + lc * L[2];       // the same cube sample the shader takes at n = (0,0,1)
    gl.uniform1i(U.u_map, 0); gl.uniform1i(U.u_cube, 1); gl.uniform1i(U.u_height, 2); gl.uniform1i(U.u_heightEa, 3);
    gl.uniform3f(U.u_L, L[0], L[1], L[2]); gl.uniform1f(U.u_lc, lc); gl.uniform1f(U.u_amb, amb); gl.uniform1f(U.u_lightC, lightC);
    gl.disable(gl.DEPTH_TEST); gl.disable(gl.BLEND);
    let lastW = 0, lastH = 0;
    return {
      lightC, centreZ,
      set onHeightLoaded(fn) { onHeight = fn; },
      /** geom: {cx, cy, r, capDeg} in CSS px (y down); rim: {mid, horizon: [r,g,b] linear, px: half thickness, CSS px}; alpha 0..1;
       *  terrain: {lat, lng (deg, view centre), scale (groundElevationScale), amount 0..1} or null */
      draw(mapCanvas, geom, dpr, rim, rimLight, alpha, terrain, atmos) {
        const W = mapCanvas.width, H = mapCanvas.height;      // device px
        if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
        gl.viewport(0, 0, W, H);
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, mapTex);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);   // canvas rows start at the top; texel row 0 must be the bottom for gl_FragCoord
        if (W !== lastW || H !== lastH) { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, mapCanvas); lastW = W; lastH = H; }
        else gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, mapCanvas);
        const D = 1 / Math.cos(geom.capDeg * Math.PI / 180);
        const f = geom.r * dpr * Math.sqrt(D * D - 1);
        gl.uniform2f(U.u_size, W, H); gl.uniform2f(U.u_c, geom.cx * dpr, geom.cy * dpr); gl.uniform1f(U.u_r, geom.r * dpr);
        gl.uniform1f(U.u_D, D); gl.uniform1f(U.u_f, f);
        gl.uniform3f(U.u_mid, rim.mid[0], rim.mid[1], rim.mid[2]); gl.uniform3f(U.u_horizon, rim.horizon[0], rim.horizon[1], rim.horizon[2]);
        gl.uniform1f(U.u_rimPx, rim.px * dpr); gl.uniform1f(U.u_rimLight, rimLight); gl.uniform1f(U.u_alpha, alpha);
        if (atmos) { gl.uniform3f(U.u_sky, atmos.sky[0], atmos.sky[1], atmos.sky[2]); gl.uniform2f(U.u_hg, atmos.hg[0], atmos.hg[1]); gl.uniform1f(U.u_atmosW, atmos.w); }
        else gl.uniform2f(U.u_hg, 0, 0);
        if (terrain && terrain.amount > 0) {
          const la = terrain.lat * Math.PI / 180, lo = terrain.lng * Math.PI / 180;
          // columns east, north, up (ECEF) of the view centre; view x = east, y = north, z = up (bearing 0, pitch 0)
          const east = [-Math.sin(lo), Math.cos(lo), 0], north = [-Math.sin(la) * Math.cos(lo), -Math.sin(la) * Math.sin(lo), Math.cos(la)], up = [Math.cos(la) * Math.cos(lo), Math.cos(la) * Math.sin(lo), Math.sin(la)];
          gl.uniformMatrix3fv(U.u_frame, false, new Float32Array([...east, ...north, ...up]));
          gl.uniform1f(U.u_scale, terrain.scale); gl.uniform1f(U.u_terrain, terrain.amount); gl.uniform2f(U.u_hsize, hsize[0], hsize[1]);
        } else gl.uniform1f(U.u_terrain, 0);
        gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      },
      clear() { gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); },
    };
  }
  window.__globeLight = { create };
})();
