// Globe post-pass: Apple's DaVinci lighting and GlobeAtmosphere rim, run over MapLibre's rendered globe.
// Formulas and constants: SHADER-NUMBERS.md 3.1 / 3.3 / 4.1 and basemap/data/shader/shader-numbers.json
// (captured from VectorKit, 2026-09-16). MapLibre paints every surface colour as albedo x light(0,0,1)
// (the flat renderer's value, so the same colours serve the flat map); this pass reads those pixels back,
// linearises them, and re-lights per pixel:
//   light(n)  = ambientLightColor * cube(n) + lightColor * max(n.L, 0)        (linear RGB; n = sphere normal in view space)
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
    uniform vec3 u_mid;               // rim mid colour, linear
    uniform float u_rimPx;            // 75 km at limb scale, device px
    uniform float u_rimLight;         // AtmosphereConstants.lightingEnabled (1 = far camera)
    uniform float u_alpha;            // fade (morph to flat)
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
        vec4 m = texture2D(u_map, uv);
        vec3 base = m.a > 0.001 ? m.rgb / m.a : vec3(0.0);
        vec3 lin = toLin(base);
        float light = u_amb * textureCube(u_cube, n).r + u_lc * max(dot(n, u_L), 0.0);
        vec3 col = lin * light / u_lightC;
        // MapLibre's own antialiased edge: where its disc has faded, show the rim start instead of black
        vec2 dir = normalize(vec2(d.x, -d.y));
        float I = 0.25 * pow(dot(u_L, vec3(dir, 0.0)) + 1.0, 2.0);
        float rimL = mix(1.0, u_lc * I + u_amb, u_rimLight);
        vec3 rim = u_mid * rimL;
        col = mix(rim, col, m.a);
        gl_FragColor = vec4(toSrgb(col) * u_alpha, u_alpha);
      } else if (rho - u_r < u_rimPx) {
        float t2 = clamp((rho - u_r) / u_rimPx, 0.0, 1.0);
        vec2 dir = normalize(vec2(d.x, -d.y));
        float I = 0.25 * pow(dot(u_L, vec3(dir, 0.0)) + 1.0, 2.0);
        float rimL = mix(1.0, u_lc * I + u_amb, u_rimLight);
        vec3 col = u_mid * (1.0 - t2) * rimL;                            // mix(midColor, endColor = black, t2)
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
    const U = {}; for (const name of ['u_map', 'u_cube', 'u_size', 'u_c', 'u_r', 'u_D', 'u_f', 'u_L', 'u_lc', 'u_amb', 'u_lightC', 'u_mid', 'u_rimPx', 'u_rimLight', 'u_alpha']) U[name] = gl.getUniformLocation(prog, name);
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
    gl.uniform1i(U.u_map, 0); gl.uniform1i(U.u_cube, 1);
    gl.uniform3f(U.u_L, L[0], L[1], L[2]); gl.uniform1f(U.u_lc, lc); gl.uniform1f(U.u_amb, amb); gl.uniform1f(U.u_lightC, lightC);
    gl.disable(gl.DEPTH_TEST); gl.disable(gl.BLEND);
    let lastW = 0, lastH = 0;
    return {
      lightC, centreZ,
      /** geom: {cx, cy, r, capDeg} in CSS px (y down); mid: [r,g,b] linear; rimPx CSS px; alpha 0..1 */
      draw(mapCanvas, geom, dpr, mid, rimPx, rimLight, alpha) {
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
        gl.uniform3f(U.u_mid, mid[0], mid[1], mid[2]); gl.uniform1f(U.u_rimPx, rimPx * dpr); gl.uniform1f(U.u_rimLight, rimLight); gl.uniform1f(U.u_alpha, alpha);
        gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      },
      clear() { gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT); },
    };
  }
  window.__globeLight = { create };
})();
