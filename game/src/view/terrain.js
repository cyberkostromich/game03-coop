// Terrain mesh from the heightmap, splat-blended painted tiles, water.
import * as THREE from 'three';
import { grassTile, dirtTile, sandTile, rockTile, canvasTexture } from './textures.js';
import { FOG_HEAD } from './fog.js';

export function buildTerrain(D, world, renderer, fog, splatImg) {
  const M = D.map, R = M.resolution, size = M.size, half = size / 2;
  const H = D.mapBin.height, hmin = M.height_min, hmax = M.height_max;
  const geo = new THREE.PlaneGeometry(size, size, R - 1, R - 1);
  geo.rotateX(-Math.PI / 2);                     // XZ plane, +Z = south
  const pos = geo.attributes.position;
  // PlaneGeometry rows go from +y (top) to -y; after rotateX top row sits at z = -half (north)
  for (let i = 0; i < pos.count; i++) {
    const col = i % R, row = Math.floor(i / R);  // row 0 = north, same as the image rows
    pos.setY(i, hmin + H[row * R + col] / 65535 * (hmax - hmin));
  }
  geo.computeVertexNormals();
  geo.computeBoundingSphere();

  const splat = new THREE.Texture(splatImg);
  splat.colorSpace = THREE.NoColorSpace;
  splat.flipY = false;                           // image row 0 = north = uv.y 0 below
  splat.needsUpdate = true;
  const tiles = [grassTile(), dirtTile(), sandTile(), rockTile()].map(c => canvasTexture(c, renderer));

  const heightTex = new THREE.DataTexture(new Float32Array(R * R), R, R, THREE.RedFormat, THREE.FloatType);
  for (let i = 0; i < R * R; i++) heightTex.image.data[i] = hmin + H[i] / 65535 * (hmax - hmin);
  heightTex.magFilter = heightTex.minFilter = THREE.LinearFilter;
  heightTex.needsUpdate = true;

  const mat = new THREE.MeshStandardMaterial({ roughness: 0.92, metalness: 0 });
  const U = {
    tGrass: { value: tiles[0] }, tDirt: { value: tiles[1] }, tSand: { value: tiles[2] }, tRock: { value: tiles[3] },
    tSplat: { value: splat }, mapHalf: { value: half }, mapSize: { value: size }, tileScale: { value: 1 / 7 },
    waterLevel: { value: M.water_level },
  };
  mat.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, U, fog.uniforms);
    sh.vertexShader = 'varying vec3 vTW; varying vec3 vTN; varying vec2 vFogW;\n' + sh.vertexShader.replace('#include <project_vertex>', `#include <project_vertex>
  vTW = (modelMatrix * vec4(transformed, 1.0)).xyz; vTN = normal; vFogW = vTW.xz;`);
    sh.fragmentShader = `uniform sampler2D tGrass, tDirt, tSand, tRock, tSplat;
uniform float mapHalf, mapSize, tileScale, waterLevel;
varying vec3 vTW; varying vec3 vTN;
${FOG_HEAD}
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
vec3 tileSample(sampler2D t, vec2 uv) {
  // two rotated scales break up repetition
  vec3 a = texture2D(t, uv).rgb;
  vec2 r = mat2(0.8, -0.6, 0.6, 0.8) * uv * 0.37 + 0.31;
  vec3 b = texture2D(t, r).rgb;
  return mix(a, b, 0.33);
}
` + sh.fragmentShader.replace('#include <map_fragment>', `
  vec2 suv = vec2((vTW.x + mapHalf) / mapSize, (vTW.z + mapHalf) / mapSize);
  vec4 w = texture2D(tSplat, suv);
  vec2 tuv = vTW.xz * tileScale;
  vec3 cg = tileSample(tGrass, tuv), cd = tileSample(tDirt, tuv * 1.1), cs = tileSample(tSand, tuv * 0.9), cr = tileSample(tRock, tuv * 0.6);
  // slope pushes towards rock, height-based blend keeps edges crisp and painterly
  float slope = 1.0 - clamp(normalize(vTN).y, 0.0, 1.0);
  w.a = max(w.a, smoothstep(0.28, 0.5, slope));
  float n = vnoise(vTW.xz * 0.35) * 0.5 + vnoise(vTW.xz * 1.3) * 0.25;
  vec4 hgt = vec4(dot(cg, vec3(0.33)), dot(cd, vec3(0.33)), dot(cs, vec3(0.33)), dot(cr, vec3(0.33)));
  vec4 bw = w * (1.0 + 1.6 * (hgt + n * 0.6));
  float mx = max(max(bw.r, bw.g), max(bw.b, bw.a));
  bw = max(bw - (mx - 0.55), 0.0);
  bw /= max(dot(bw, vec4(1.0)), 1e-4);
  vec3 col = cg * bw.r + cd * bw.g + cs * bw.b + cr * bw.a;
  // macro tint variation (lush/dry patches) and wet shoreline
  float m = vnoise(vTW.xz * 0.045);
  col *= mix(vec3(0.9, 0.96, 0.86), vec3(1.08, 1.04, 0.94), m);
  float wet = 1.0 - smoothstep(waterLevel + 0.05, waterLevel + 0.7, vTW.y);
  col = mix(col, col * vec3(0.55, 0.52, 0.48), wet * 0.8);
  diffuseColor.rgb = col;
`).replace('#include <dithering_fragment>', `#include <dithering_fragment>
  gl_FragColor.rgb *= fogFactor(vFogW);`);
  };
  mat.customProgramCacheKey = () => 'terrain';
  const mesh = new THREE.Mesh(geo, mat);
  mesh.receiveShadow = true;
  mesh.name = 'terrain';

  const water = buildWater(M, heightTex, fog);
  return { mesh, water, heightTex, uniforms: U };
}

function buildWater(M, heightTex, fog) {
  const size = M.size;
  const geo = new THREE.PlaneGeometry(size, size, 1, 1);
  geo.rotateX(-Math.PI / 2);
  const U = {
    tHeight: { value: heightTex }, mapHalf: { value: size / 2 }, mapSize: { value: size },
    level: { value: M.water_level }, time: { value: 0 },
    sunDir: { value: new THREE.Vector3(0.4, 0.8, 0.3).normalize() }, sunCol: { value: new THREE.Color(1, 0.95, 0.85) },
    skyCol: { value: new THREE.Color(0.55, 0.72, 0.9) }, dayLight: { value: 1 },
    ...fog.uniforms,
  };
  const mat = new THREE.ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false,
    vertexShader: `varying vec3 vW; varying vec2 vFogW;
      void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; vFogW = w.xz; gl_Position = projectionMatrix * viewMatrix * w; }`,
    fragmentShader: `uniform sampler2D tHeight; uniform float mapHalf, mapSize, level, time, dayLight;
      uniform vec3 sunDir, sunCol, skyCol; varying vec3 vW;
      ${FOG_HEAD}
      float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
      float vn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y); }
      float waves(vec2 p) { return vn(p * 0.9 + time * vec2(0.25, 0.12)) * 0.5 + vn(p * 2.1 - time * vec2(0.18, 0.3)) * 0.3 + vn(p * 5.0 + time * 0.6) * 0.2; }
      void main() {
        vec2 uv = vec2((vW.x + mapHalf) / mapSize, (vW.z + mapHalf) / mapSize);
        float h = texture2D(tHeight, uv).r;
        float depth = level - h;
        if (depth < -0.02) discard;
        float e = 0.08;
        float c = waves(vW.xz), cx = waves(vW.xz + vec2(e, 0.0)), cz = waves(vW.xz + vec2(0.0, e));
        vec3 n = normalize(vec3((c - cx) * 2.2, 1.0, (c - cz) * 2.2));
        vec3 V = normalize(cameraPosition - vW);
        float fres = pow(1.0 - max(dot(n, V), 0.0), 3.0);
        vec3 shallow = vec3(0.16, 0.42, 0.40), deep = vec3(0.04, 0.16, 0.24);
        vec3 col = mix(shallow, deep, smoothstep(0.1, 2.2, depth));
        col = mix(col, skyCol * 0.85, fres * 0.6);
        vec3 Hh = normalize(sunDir + V);
        col += sunCol * pow(max(dot(n, Hh), 0.0), 160.0) * 1.4 * dayLight;
        // painted shore foam
        float edge = smoothstep(0.16, 0.0, depth);
        float foam = edge * smoothstep(0.45, 0.75, vn(vW.xz * 1.7 + time * 0.3) * 0.6 + edge * 0.6);
        col = mix(col, vec3(0.92, 0.96, 0.92), clamp(foam, 0.0, 1.0) * 0.85);
        col *= mix(0.35, 1.0, dayLight);
        float a = mix(0.55, 0.92, smoothstep(0.0, 1.2, depth));
        a = max(a * smoothstep(-0.02, 0.12, depth), foam * 0.9);
        gl_FragColor = vec4(col * fogFactor(vFogW), a);
        #include <colorspace_fragment>
      }`,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.y = M.water_level;
  mesh.renderOrder = 2;
  mesh.name = 'water';
  return { mesh, uniforms: U };
}
