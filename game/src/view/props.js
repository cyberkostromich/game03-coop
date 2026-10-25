// Forests and doodads as instanced meshes. Uses the baked prop GLBs when
// present, otherwise a painted low-poly fallback in the same style.
import * as THREE from 'three';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
const UP = new THREE.Vector3(0, 1, 0);

function painted(geo, top, bottom, jitter = 0.08, seed = 1) {
  geo = mergeVertices(geo.index ? geo.toNonIndexed() : geo, 1e-4);
  geo.computeBoundingBox();
  const bb = geo.boundingBox, pos = geo.attributes.position, n = pos.count;
  const col = new Float32Array(n * 3), a = new THREE.Color(top), b = new THREE.Color(bottom), c = new THREE.Color();
  let r = seed;
  for (let i = 0; i < n; i++) {
    const t = (pos.getY(i) - bb.min.y) / Math.max(1e-4, bb.max.y - bb.min.y);
    r = (r * 16807) % 2147483647;
    c.copy(b).lerp(a, Math.pow(t, 0.8)).multiplyScalar(1 - jitter + (r / 2147483647) * jitter * 2);
    col.set([c.r, c.g, c.b], i * 3);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  geo.computeVertexNormals();
  return geo;
}

function blobGeo(r, detail = 1, squash = 0.85, seed = 3) {
  const g = new THREE.IcosahedronGeometry(r, detail);
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const n = 1 + 0.12 * Math.sin(x * 5.1 + seed) * Math.cos(z * 4.3 + seed) + 0.08 * Math.sin(y * 7 + seed);
    pos.setXYZ(i, x * n, y * n * squash, z * n);
  }
  return g;
}

function fallbackTree(type) {
  const parts = [];
  if (type === 'pine') {
    const trunk = new THREE.CylinderGeometry(0.13, 0.22, 1.6, 7).translate(0, 0.8, 0);
    parts.push(painted(trunk, '#6d4a2c', '#3b2616'));
    for (let k = 0; k < 4; k++) {
      const r = 1.55 - k * 0.32, h = 1.7 - k * 0.2;
      const cone = new THREE.ConeGeometry(r, h, 9, 1).translate(0, 1.5 + k * 0.95 + h / 2, 0);
      parts.push(painted(cone, '#4f8a3a', '#1d3d1e', 0.1, k + 7));
    }
  } else if (type === 'birch') {
    const trunk = new THREE.CylinderGeometry(0.1, 0.17, 3.2, 7).translate(0, 1.6, 0);
    parts.push(painted(trunk, '#efe9dc', '#8b8478'));
    for (const [x, y, z, r] of [[0, 3.5, 0, 1.15], [0.6, 3.0, 0.3, 0.8], [-0.55, 3.2, -0.25, 0.85], [0.1, 4.2, 0.1, 0.75]])
      parts.push(painted(blobGeo(r, 1, 0.9, x * 9).translate(x, y, z), '#b8d860', '#4a7a26', 0.1, r * 31));
  } else {
    const trunk = new THREE.CylinderGeometry(0.2, 0.36, 2.4, 8).translate(0, 1.2, 0);
    parts.push(painted(trunk, '#7a5634', '#3a2614'));
    for (const [x, y, z, r] of [[0, 3.1, 0, 1.6], [1.0, 2.6, 0.4, 1.15], [-0.95, 2.7, -0.3, 1.2], [0.2, 2.5, -1.0, 1.05], [-0.2, 3.9, 0.3, 1.1]])
      parts.push(painted(blobGeo(r, 1, 0.82, x * 7 + z).translate(x, y, z), '#8cc045', '#2f5a1f', 0.1, r * 17 + x));
  }
  return mergeGeometries(parts.map(g => { const ng = g.index ? g.toNonIndexed() : g; return ng; }), false);
}

function fallbackDoodad(type) {
  if (type === 'bush') return mergeGeometries([0, 1, 2].map(k => painted(blobGeo(0.55 - k * 0.08, 1, 0.75, k).translate(Math.cos(k * 2.1) * 0.35, 0.4, Math.sin(k * 2.1) * 0.35), '#7fb43c', '#2c5219', 0.12, k + 3).toNonIndexed()));
  if (type === 'mushrooms') return mergeGeometries([0, 1, 2].map(k => {
    const st = new THREE.CylinderGeometry(0.04, 0.05, 0.22, 6).translate(0, 0.11, 0);
    const cap = new THREE.SphereGeometry(0.13, 8, 5, 0, Math.PI * 2, 0, Math.PI / 2).translate(0, 0.22, 0);
    const g = mergeGeometries([painted(st, '#efe6d0', '#c9bda4').toNonIndexed(), painted(cap, '#d8432c', '#a12a1c').toNonIndexed()]);
    return g.scale(1 - k * 0.2, 1 - k * 0.2, 1 - k * 0.2).translate(Math.cos(k * 2.3) * 0.25, 0, Math.sin(k * 2.3) * 0.25);
  }));
  if (type === 'reeds') return mergeGeometries([0, 1, 2, 3, 4, 5].map(k => painted(new THREE.ConeGeometry(0.03, 1.1 + (k % 3) * 0.25, 4).translate(Math.cos(k * 1.7) * 0.25, 0.55, Math.sin(k * 1.7) * 0.25), '#b2c46a', '#4f6b2a').toNonIndexed()));
  if (type === 'flowers') return mergeGeometries([0, 1, 2, 3].map(k => painted(blobGeo(0.09, 0, 1, k).translate(Math.cos(k * 1.6) * 0.3, 0.18, Math.sin(k * 1.6) * 0.3), k % 2 ? '#f2d24a' : '#e86aa0', '#c0a030').toNonIndexed()));
  if (type === 'rocks') return mergeGeometries([0, 1].map(k => painted(blobGeo(0.4 - k * 0.15, 0, 0.6, k).translate(k * 0.45, 0.12, k * 0.2), '#a8a294', '#5d5850').toNonIndexed()));
  return painted(blobGeo(0.3, 0, 0.6), '#888', '#555').toNonIndexed();
}

async function propSource(app, models, id) {
  const meta = app.D.propAssets?.[id];
  if (!meta) return null;
  const g = await models.load('props', id, meta);
  if (!g) return null;
  const out = [];
  g.scene.updateMatrixWorld(true);
  g.scene.traverse(o => { if (o.isMesh) out.push({ geo: o.geometry.clone().applyMatrix4(o.matrixWorld), mat: o.material }); });
  return out;
}

function fallbackBridge() {
  const parts = [];
  const plank = (x, w) => painted(new THREE.BoxGeometry(w, 0.16, 3.6).translate(x, 0, 0), '#a77a48', '#6a4a2a', 0.12, x * 13 + 7).toNonIndexed();
  for (let k = -12; k <= 12; k++) parts.push(plank(k * 0.54, 0.5).translate(0, 0.3 + 0.55 * Math.cos(Math.PI * k * 0.54 / 13), 0));
  for (const z of [-1.75, 1.75]) {
    parts.push(painted(new THREE.BoxGeometry(13.2, 0.14, 0.14).translate(0, 0.85, z), '#8a6238', '#5a3e22').toNonIndexed());
    for (let k = -6; k <= 6; k += 2) parts.push(painted(new THREE.CylinderGeometry(0.09, 0.11, 2.6, 6).translate(k, -0.45, z), '#7a5432', '#3a2614').toNonIndexed());
  }
  for (const z of [-1.9, 1.9]) parts.push(painted(new THREE.BoxGeometry(13.4, 0.26, 0.2).translate(0, -0.08, z), '#6e4c2c', '#4a3018').toNonIndexed());
  return mergeGeometries(parts);
}

// deck height of a bridge under (x, y), or -Infinity
export function deckAt(map, x, y) {
  for (const c of map.crossings) {
    if (c.kind !== 'bridge') continue;
    const a = c.angle * Math.PI / 180, dx = Math.cos(a), dy = Math.sin(a);
    const along = (x - c.x) * dx + (y - c.y) * dy, across = -(x - c.x) * dy + (y - c.y) * dx;
    if (Math.abs(along) < 6.6 && Math.abs(across) < 1.9) return BRIDGE_DECK + 0.55 * Math.cos(Math.PI * Math.min(6.5, Math.abs(along)) / 13);
  }
  return -Infinity;
}
export const BRIDGE_DECK = 0.36;     // deck top at the abutments; the span arches 0.55 m higher (matches props.bridge)

export async function buildBridges(app, models) {
  const group = new THREE.Group();
  const mat = app.fog.patch(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8 }));
  const src = await propSource(app, models, 'bridge');
  for (const c of app.D.map.crossings) {
    if (c.kind !== 'bridge') continue;
    const g = new THREE.Group();
    if (src) for (const { geo, mat: m } of src) g.add(new THREE.Mesh(geo, m));
    else g.add(new THREE.Mesh(fallbackBridge(), mat));
    g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    g.position.set(c.x, 0, -c.y);
    g.rotation.y = c.angle * Math.PI / 180;
    group.add(g);
  }
  return group;
}

export async function buildTrees(app, models) {
  const w = app.world, grid = w.grid, M = app.D.map;
  const group = new THREE.Group();
  const fallbackMat = app.fog.patch(new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.85, flatShading: false }));
  const sets = new Map();                    // type -> {meshes: InstancedMesh[], ids: entity ids}
  // instanced per type and per 48 m chunk, so whole chunks get frustum-culled
  const byType = {};
  const CH = 48;
  for (const e of w.ents) if (e.kind === 'tree') {
    const variant = app.D.propAssets?.[e.type + '_b'] && (e.id * 2654435761 >>> 0) % 2 ? e.type + '_b' : e.type;
    const key = variant + ':' + Math.floor((e.x + grid.half) / CH) + ':' + Math.floor((e.y + grid.half) / CH);
    (byType[key] ||= []).push(e);
  }
  const srcCache = {};
  const mk = async (key, list, fallback) => {
    const type = key.split(':')[0];
    if (!(type in srcCache)) srcCache[type] = (await propSource(app, models, type)) || [{ geo: fallback(type), mat: fallbackMat }];
    const src = srcCache[type];
    const meshes = src.map(({ geo, mat }) => {
      const im = new THREE.InstancedMesh(geo, mat, list.length);
      im.castShadow = true; im.receiveShadow = true;
      return im;
    });
    list.forEach((e, i) => {
      const h = grid.heightAt(e.x, e.y);
      const sc = (e.scale || 1) * (type.startsWith('pine') ? 1.0 : 0.9);
      p.set(e.x, h - 0.05, -e.y); q.setFromAxisAngle(UP, (e.rot || 0) * Math.PI / 180); s.setScalar(sc);
      m4.compose(p, q, s);
      for (const im of meshes) im.setMatrixAt(i, m4);
      e.view = { type: key, i, x: e.x, y: e.y, h, sc, rot: (e.rot || 0) * Math.PI / 180, fall: 0, dir: 0 };
    });
    for (const im of meshes) { im.instanceMatrix.needsUpdate = true; im.computeBoundingSphere(); group.add(im); }
    sets.set(key, { meshes, list });
  };
  for (const [type, list] of Object.entries(byType)) await mk(type, list, fallbackTree);
  // doodads are decoration only
  const dd = {};
  for (const d of M.doodads) (dd[d.type] ||= []).push(d);
  for (const [type, list] of Object.entries(dd)) {
    let src = await propSource(app, models, type);
    if (!src) src = [{ geo: fallbackDoodad(type), mat: fallbackMat }];
    for (const { geo, mat } of src) {
      const im = new THREE.InstancedMesh(geo, mat, list.length);
      im.receiveShadow = true; im.castShadow = type === 'rocks' || type === 'bush';
      list.forEach((d, i) => {
        p.set(d.x, grid.heightAt(d.x, d.y) - 0.03, -d.y); q.setFromAxisAngle(UP, d.r * Math.PI / 180); s.setScalar(d.s || 1);
        im.setMatrixAt(i, m4.compose(p, q, s));
      });
      im.instanceMatrix.needsUpdate = true; im.computeBoundingSphere();
      group.add(im);
    }
  }
  const falling = [];
  return {
    group,
    fell(e, from) {
      if (!e.view) return;
      const v = e.view;
      v.dir = from ? Math.atan2(-(e.y - from.y), e.x - from.x) : Math.random() * 6.28;
      falling.push(v);
    },
    shake(e) { if (e.view) e.view.shake = 0.35; },
    update(dt) {
      for (const set of sets.values()) {
        let dirty = false;
        for (const e of set.list) {
          const v = e.view;
          if (!v || (!v.shake && !falling.includes(v))) continue;
          dirty = true;
          let tilt = 0, axis = new THREE.Vector3(Math.sin(v.dir), 0, Math.cos(v.dir));
          if (v.shake) { v.shake = Math.max(0, v.shake - dt); tilt = Math.sin(v.shake * 40) * 0.03 * v.shake * 3; axis.set(1, 0, 0); }
          if (falling.includes(v)) { v.fall += dt; tilt = Math.min(Math.PI / 2, v.fall * v.fall * 2.4); }
          p.set(v.x, v.h - 0.05 - Math.max(0, v.fall - 1.2) * 1.5, -v.y);
          q.setFromAxisAngle(UP, v.rot);
          const qt = new THREE.Quaternion().setFromAxisAngle(axis, tilt);
          q.premultiply(qt);
          s.setScalar(v.fall > 2.2 ? 0 : v.sc);
          m4.compose(p, q, s);
          for (const im of set.meshes) im.setMatrixAt(v.i, m4);
          if (v.fall > 2.2) falling.splice(falling.indexOf(v), 1);
        }
        if (dirty) for (const im of set.meshes) im.instanceMatrix.needsUpdate = true;
      }
    },
  };
}
