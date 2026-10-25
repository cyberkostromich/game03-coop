// GLB model library: loads each asset once, hands out skinned clones with
// per-player team colour and a ready AnimationMixer.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';
import { ASSETS } from '../data.js';

const ONCE = new Set(['Attack', 'Hit', 'Death', 'Cast', 'Work1']);

export class Models {
  constructor(fog, renderer) {
    this.fog = fog;
    this.loader = new GLTFLoader();
    this.cache = new Map();          // key -> Promise<gltf>
    this.ready = new Map();          // key -> gltf
    this.teamMats = new Map();       // material uuid + colour -> material
    this.renderer = renderer;
  }

  url(kind, id, meta) { return `${ASSETS}${kind}/${meta?.file || id + '.glb'}`; }

  load(kind, id, meta) {
    const key = kind + '/' + id;
    if (!this.cache.has(key)) {
      this.cache.set(key, this.loader.loadAsync(this.url(kind, id, meta)).then(g => {
        g.scene.traverse(o => {
          if (o.isMesh) {
            o.castShadow = true; o.receiveShadow = true;
            o.frustumCulled = false;                 // skinned bounds are unreliable; units are small
            const m = o.material;
            if (m) this.prepMaterial(m);
          }
        });
        g.clipMap = Object.fromEntries(g.animations.map(c => [c.name, c]));
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

  prepMaterial(m) {
    if (m.userData.prepped) return;
    m.userData.prepped = true;
    if (m.name === 'glow') { m.emissive = new THREE.Color(1, 0.75, 0.35); m.emissiveIntensity = 1.4; m.emissiveMap = m.map; }
    if (m.name === 'gold' || m.name === 'metal') m.envMapIntensity = 1.2;
    m.envMapIntensity = m.envMapIntensity ?? 1;
    this.fog.patch(m);
  }

  teamMaterial(m, color) {
    const key = m.uuid + color;
    let t = this.teamMats.get(key);
    if (!t) {
      t = m.clone();
      t.color = new THREE.Color(color);

      t.userData = { ...m.userData, fogPatched: false };
      this.fog.patch(t);
      this.teamMats.set(key, t);
    }
    return t;
  }

  // a skinned, team-coloured instance ready to animate
  instance(kind, id, color) {
    const g = this.get(kind, id);
    if (!g) return null;
    const root = SkeletonUtils.clone(g.scene);
    root.traverse(o => {
      if (!o.isMesh) return;
      const swap = m => (m.name === 'team' || m.name === 'roof') && color ? this.teamMaterial(m, color) : m;
      o.material = Array.isArray(o.material) ? o.material.map(swap) : swap(o.material);
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
