// Fog of war: one small texture (R = visible, G = explored) smoothed on the
// CPU every frame and sampled by every lit material through a shader patch.
import * as THREE from 'three';

export class Fog {
  constructor(world) {
    this.w = world;
    const n = world.grid.n;
    this.n = n;
    this.cur = new Float32Array(n * n * 2);
    this.data = new Uint8Array(n * n * 4);
    this.tex = new THREE.DataTexture(this.data, n, n, THREE.RGBAFormat);
    this.tex.magFilter = THREE.LinearFilter;
    this.tex.minFilter = THREE.LinearFilter;
    this.tex.needsUpdate = true;
    this.uniforms = {
      fogTex: { value: this.tex },
      fogHalf: { value: world.grid.half },
      fogSize: { value: world.grid.size },
      fogOn: { value: 1 },
    };
    this.update(1);
  }

  update(dt) {
    const w = this.w, c = this.cur, d = this.data, n = this.n;
    if (this.blurV !== w.visVersion) {          // soften the cell-sized steps once per vision update
      this.blurV = w.visVersion;
      this.tv = blur(w.vis, n, this.tv); this.te = blur(w.explored, n, this.te);
    }
    const V = this.tv, X = this.te;
    const k = Math.min(1, dt * 5);
    for (let i = 0; i < V.length; i++) {
      const v = c[i * 2] += (V[i] - c[i * 2]) * k;
      const e = c[i * 2 + 1] += (X[i] - c[i * 2 + 1]) * k;
      // texture rows: row 0 = south edge (cy = 0), matches sim grid
      d[i * 4] = v * 255; d[i * 4 + 1] = e * 255;
    }
    this.tex.needsUpdate = true;
  }

  // brightness multiplier at a world point, for CPU-side decisions
  at(x, y) {
    const i = this.w.grid.idx(x, y);
    return i < 0 ? 0 : this.cur[i * 2];
  }

  patch(material) {
    if (material.userData.fogPatched) return material;
    material.userData.fogPatched = true;
    const U = this.uniforms;
    const prev = material.onBeforeCompile;
    material.onBeforeCompile = (sh, r) => {
      if (prev) prev(sh, r);
      Object.assign(sh.uniforms, U);
      sh.vertexShader = 'varying vec2 vFogW;\n' + sh.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>
  {
    vec4 fw = vec4(transformed, 1.0);
    #ifdef USE_INSTANCING
      fw = instanceMatrix * fw;
    #endif
    fw = modelMatrix * fw;
    vFogW = fw.xz;
  }`);
      sh.fragmentShader = FOG_HEAD + sh.fragmentShader.replace('#include <dithering_fragment>', `#include <dithering_fragment>
  gl_FragColor.rgb *= fogFactor(vFogW);`);
    };
    material.customProgramCacheKey = () => (prev ? 'fogp' : 'fog') + material.type;
    material.needsUpdate = true;
    return material;
  }
}

function blur(src, n, out) {
  out ||= new Float32Array(n * n);
  const tmp = new Float32Array(n * n);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    let s = 0, c = 0;
    for (let k = -2; k <= 2; k++) { const xx = x + k; if (xx >= 0 && xx < n) { s += src[y * n + xx]; c++; } }
    tmp[y * n + x] = s / c;
  }
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    let s = 0, c = 0;
    for (let k = -2; k <= 2; k++) { const yy = y + k; if (yy >= 0 && yy < n) { s += tmp[yy * n + x]; c++; } }
    out[y * n + x] = s / c;
  }
  return out;
}

export const FOG_HEAD = `
uniform sampler2D fogTex;
uniform float fogHalf, fogSize, fogOn;
varying vec2 vFogW;
float fogFactor(vec2 w) {
  // three.js z points south; the sim's +y is north
  vec2 uv = vec2((w.x + fogHalf) / fogSize, (-w.y + fogHalf) / fogSize);
  vec2 f = texture2D(fogTex, uv).rg;
  float lit = mix(0.1, mix(0.5, 1.0, smoothstep(0.0, 0.85, f.r)), smoothstep(0.0, 0.8, f.g));
  return mix(1.0, lit, fogOn);
}
`;
