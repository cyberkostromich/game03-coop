// GLB model library: loads each asset once, merges its material parts into
// a single skinned mesh (they share one baked atlas), and hands out clones
// with per-player team colour and a ready AnimationMixer.
//
// Merging matters for an RTS: a unit exported with six materials would be
// six draw calls (twelve with shadows); merged it is one. Per-part metal,
// roughness, team mask and glow ride along as a vertex attribute.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { ASSETS } from '../data.js';

const ONCE = new Set(['Attack', 'Hit', 'Death', 'Cast']);
const TEAM_PARTS = new Set(['team', 'roof']);

export class Models {
  constructor(fog, renderer) {
    this.fog = fog;
    this.loader = new GLTFLoader();
    this.cache = new Map();          // key -> Promise<gltf>
    this.ready = new Map();          // key -> gltf
    this.mats = new Map();           // base material uuid + colour -> merged material
    this.renderer = renderer;
  }

  url(kind, id, meta) { return `${ASSETS}${kind}/${meta?.file || id + '.glb'}`; }

  load(kind, id, meta) {
    const key = kind + '/' + id;
    if (!this.cache.has(key)) {
      this.cache.set(key, this.loader.loadAsync(this.url(kind, id, meta)).then(g => {
        if (kind !== 'props') this.merge(g.scene);
        g.scene.traverse(o => {
          if (!o.isMesh) return;
          o.castShadow = true; o.receiveShadow = true;
          o.frustumCulled = false;                 // skinned bounds are unreliable; units are small
          if (!o.material.userData.merged) this.fog.patch(o.material);
        });
        const box = new THREE.Box3().setFromObject(g.scene);
        g.height = box.max.y - box.min.y;
        g.radius = Math.max(box.max.x - box.min.x, box.max.z - box.min.z) / 2;
        this.ready.set(key, g);
        return g;
      }).catch(err => { console.warn('model missing', key, err.message); this.ready.set(key, null); return null; }));
    }
    return this.cache.get(key);
  }

  get(kind, id) { return this.ready.get(kind + '/' + id); }

  // collapse sibling skinned primitives into one mesh with a per-vertex
  // material record: (metalness, roughness, team mask, glow)
  merge(root) {
    const groups = new Map();
    root.traverse(o => {
      if (!o.isSkinnedMesh) return;
      const k = o.parent.uuid + o.skeleton.uuid;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(o);
    });
    for (const list of groups.values()) {
      if (list.length < 2) continue;
      const map = list.find(o => o.material.map)?.material.map || null;
      const nrm = list.find(o => o.material.normalMap)?.material.normalMap || null;
      const geos = list.map(o => {
        const m = o.material, g = o.geometry.clone();
        const n = g.attributes.position.count;
        const rec = new Float32Array(n * 4);
        const glow = m.name === 'glow' ? 1 : 0;
        for (let i = 0; i < n; i++) rec.set([m.metalness ?? 0, m.roughness ?? 0.8, TEAM_PARTS.has(m.name) ? 1 : 0, glow], i * 4);
        g.setAttribute('mrt', new THREE.BufferAttribute(rec, 4));
        for (const a of Object.keys(g.attributes)) if (!['position', 'normal', 'uv', 'skinIndex', 'skinWeight', 'mrt'].includes(a)) g.deleteAttribute(a);
        return g;
      });
      const geo = mergeGeometries(geos, false);
      if (!geo) continue;
      const first = list[0];
      const mesh = new THREE.SkinnedMesh(geo, this.material(map, nrm, null));
      mesh.name = first.name;
      mesh.position.copy(first.position); mesh.quaternion.copy(first.quaternion); mesh.scale.copy(first.scale);
      first.parent.add(mesh);
      mesh.bind(first.skeleton, first.bindMatrix);
      for (const o of list) o.parent.remove(o);
    }
  }

  material(map, nrm, color, ghost = 0) {
    const key = (map?.uuid || '-') + (color || 'base') + ghost;
    let m = this.mats.get(key);
    if (m) return m;
    m = new THREE.MeshStandardMaterial({ map, normalMap: nrm, metalness: 1, roughness: 1 });
    if (ghost) { m.transparent = true; m.opacity = ghost; m.depthWrite = false; }
    m.userData.merged = true;
    m.userData.base = { map, nrm, color };
    m.envMapIntensity = 1.15;
    const team = { value: new THREE.Color(color || '#2b3f8f') };
    m.onBeforeCompile = sh => {
      sh.uniforms.teamColor = team;
      sh.vertexShader = 'attribute vec4 mrt;\nvarying vec4 vMrt;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n  vMrt = mrt;');
      sh.fragmentShader = 'uniform vec3 teamColor;\nvarying vec4 vMrt;\n' + sh.fragmentShader
        .replace('#include <map_fragment>', '#include <map_fragment>\n  diffuseColor.rgb *= mix(vec3(1.0), teamColor, vMrt.z);')
        .replace('#include <metalnessmap_fragment>', 'float metalnessFactor = vMrt.x;')
        .replace('#include <roughnessmap_fragment>', 'float roughnessFactor = vMrt.y;')
        .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  totalEmissiveRadiance += diffuseColor.rgb * vMrt.w * 2.5;');
    };
    m.userData.progKey = 'merged-unit';
    this.fog.patch(m);
    this.mats.set(key, m);
    return m;
  }

  // translucent twin of a material (invisibility, placement ghosts)
  ghostOf(m, opacity = 0.4) {
    if (m.userData.merged) { const b = m.userData.base; return this.material(b.map, b.nrm, b.color, opacity); }
    const c = m.clone(); c.transparent = true; c.opacity = opacity; c.depthWrite = false;
    c.userData = { ...m.userData, fogPatched: false };
    this.fog.patch(c);
    return c;
  }

  // a skinned, team-coloured instance ready to animate
  instance(kind, id, color) {
    const g = this.get(kind, id);
    if (!g) return null;
    const root = SkeletonUtils.clone(g.scene);
    root.traverse(o => {
      if (!o.isMesh || !o.material.userData.merged) return;
      const b = o.material.userData.base;
      o.material = this.material(b.map, b.nrm, color);
    });
    const mixer = new THREE.AnimationMixer(root);
    const actions = {};
    for (const c of g.animations) {
      const a = mixer.clipAction(c);
      if (ONCE.has(c.name)) { a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; }
      actions[c.name] = a;
    }
    return { root, mixer, actions, gltf: g };
  }
}

// placeholder while an asset is missing: painted capsule / block in team colour
export function placeholder(kind, size, color) {
  const g = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({ color: color || '#999', roughness: 0.7 });
  if (kind === 'unit') {
    const m = new THREE.Mesh(new THREE.CapsuleGeometry(size * 0.35, size * 0.6, 4, 10), mat);
    m.position.y = size * 0.65; m.castShadow = true;
    g.add(m);
  } else {
    const m = new THREE.Mesh(new THREE.BoxGeometry(size[0] * 0.95, size[2], size[1] * 0.95), mat);
    m.position.y = size[2] / 2; m.castShadow = true; m.receiveShadow = true;
    g.add(m);
  }
  return g;
}
