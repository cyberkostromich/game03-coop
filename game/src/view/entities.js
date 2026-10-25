// Scene-side mirror of the simulation: one view per entity, interpolated
// between ticks, animated from the sim's anim state.
import * as THREE from 'three';
import { Models, placeholder } from './models.js';
import { ringTexture } from './textures.js';
import { buildTrees } from './props.js';

const UNIT_SCALE = 1.45;
const tmpV = new THREE.Vector3();

export const toThree = (x, y, h = 0) => tmpV.set(x, h, -y);
export const yaw = f => f + Math.PI / 2;           // sim facing -> model rotation (model faces +Z)

export class EntityViews {
  constructor(app) {
    this.app = app;
    this.w = app.world;
    this.D = app.D;
    this.scene = app.scene;
    this.models = new Models(app.fog, app.renderer);
    this.views = new Map();
    this.group = new THREE.Group();
    this.scene.add(this.group);
    this.ringTex = ringTexture();
    this.ringGeo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
    this.ringMats = {};
    this.trees = null;
  }

  async preload(progress) {
    const D = this.D, jobs = [];
    const units = new Set(), blds = new Set();
    for (const p of this.w.players) {
      const F = D.factions[p.faction];
      for (const b of Object.values(this.w.defs.buildings)) if (b.faction === p.faction) blds.add(b.model);
      for (const u of Object.values(this.w.defs.units)) if (u.faction === p.faction) units.add(u.model);
      void F;
    }
    for (const u of ['rat_raider', 'rat_plague_doctor', 'rat_king']) units.add(u);
    for (const b of ['gold_mine', 'mill', 'rat_pit']) blds.add(b);
    for (const id of units) if (D.unitAssets[id]) jobs.push(this.models.load('units', id, D.unitAssets[id]));
    for (const id of blds) if (D.buildingAssets[id]) jobs.push(this.models.load('buildings', id, D.buildingAssets[id]));
    let done = 0;
    await Promise.all(jobs.map(j => j.then(() => progress(++done / jobs.length))));
    this.trees = await buildTrees(this.app, this.models);
    this.scene.add(this.trees.group);
  }

  ringMat(color) {
    if (!this.ringMats[color]) this.ringMats[color] = new THREE.MeshBasicMaterial({
      map: this.ringTex, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0.95,
      polygonOffset: true, polygonOffsetFactor: -4,
    });
    return this.ringMats[color];
  }

  colorOf(e) {
    const P = this.w.players[e.owner];
    if (P) return P.color;
    if (e.owner === 4) return '#5b4a3a';
    return '#7a7a7a';
  }

  create(e) {
    if (e.kind === 'tree' || e.kind === 'shoal') return null;
    const v = { e, root: new THREE.Group(), inst: null, anim: null, animT: -1, sel: null, alpha: 1, sink: 0 };
    const color = this.colorOf(e);
    if (e.kind === 'unit') {
      const model = e.def.model;
      v.inst = this.models.instance('units', model, color);
      v.meta = this.D.unitAssets[model];
      const s = UNIT_SCALE * (e.def.boss ? 1.9 : 1) * (e.illusion ? 1 : 1);
      if (v.inst) { v.inst.root.scale.setScalar(s); v.root.add(v.inst.root); }
      else v.root.add(placeholder('unit', 1.3 * s, color));
      v.height = (v.meta?.height || 1.3) * s;
      v.scale = s;
    } else {
      const meta = this.D.buildingAssets[e.def.model];
      v.inst = this.models.instance('buildings', e.def.model, color);
      if (v.inst) v.root.add(v.inst.root);
      else v.root.add(placeholder('building', [e.def.w, e.def.h, Math.max(2, e.def.w * 0.8)], e.type === 'gold_mine' ? '#c8a040' : color));
      v.height = meta?.height || Math.max(2, e.def.w * 0.8);
      if (v.inst?.actions.Idle) v.inst.actions.Idle.play();
    }
    v.root.position.copy(toThree(e.x, e.y, this.w.grid.heightAt(e.x, e.y)));
    v.root.rotation.y = yaw(e.facing);
    v.px = e.x; v.py = e.y; v.pf = e.facing;
    this.group.add(v.root);
    this.views.set(e.id, v);
    return v;
  }

  remove(id) {
    const v = this.views.get(id);
    if (!v) return;
    this.group.remove(v.root);
    v.inst?.mixer.stopAllAction();
    this.views.delete(id);
  }

  // called right before each sim step so frames can interpolate
  snapshot() {
    for (const v of this.views.values()) { v.px = v.e.x; v.py = v.e.y; v.pf = v.e.facing; v.ph = v.e.hop || 0; }
  }

  play(v, name, dur) {
    const A = v.inst?.actions;
    if (!A) return;
    let a = A[name] || (name === 'Cast' ? A.Attack : name === 'Work' ? A.Attack : null) || A.Idle;
    if (!a) return;
    const prev = v.action;
    a.reset();
    a.enabled = true;
    a.setEffectiveWeight(1);
    const clip = a.getClip();
    if (name === 'Attack' || name === 'Cast') a.setEffectiveTimeScale(clip.duration / Math.max(0.2, dur || 1));
    else if (name === 'Death' || name === 'Hit') a.setEffectiveTimeScale(1);
    else a.setEffectiveTimeScale(1);
    if (prev && prev !== a) a.crossFadeFrom(prev, name === 'Death' ? 0.1 : 0.18, false);
    a.play();
    v.action = a;
    v.actionName = name;
  }

  update(dt, alpha) {
    const w = this.w, g = w.grid;
    for (const e of w.ents) {
      if (e.kind === 'tree' || e.kind === 'shoal') continue;
      let v = this.views.get(e.id);
      if (!v) { if (!e.alive && e.kind === 'unit') continue; v = this.create(e); if (!v) continue; }
      const x = v.px + (e.x - v.px) * alpha, y = v.py + (e.y - v.py) * alpha;
      let f = v.pf, df = e.facing - v.pf;
      while (df > Math.PI) df -= 2 * Math.PI; while (df < -Math.PI) df += 2 * Math.PI;
      f += df * alpha;
      const hop = (v.ph ?? 0) + ((e.hop || 0) - (v.ph ?? 0)) * alpha;
      let h = g.heightAt(x, y);
      if (e.kind === 'unit' && h < this.D.map.water_level - 0.05) h = this.D.map.water_level - 0.25;  // wading through fords
      v.root.position.set(x, h + hop, -y);
      v.root.rotation.y = yaw(f);
      // visibility: fog hides enemies, mines hide workers
      let vis = !e.hidden;
      if (vis && e.team !== 0 && e.kind === 'unit') vis = w.visibleTo(0, e) || !e.alive && v.seen;
      if (vis && e.kind === 'unit' && e.team !== 0) v.seen = true;
      if (e.kind === 'building' && e.team !== 0 && !v.revealed) { const i = g.idx(e.x, e.y); v.revealed = i >= 0 && w.explored[i]; vis = v.revealed; }
      v.root.visible = vis;
      if (e.kind === 'unit') this.updateUnit(v, e, dt);
      else this.updateBuilding(v, e, dt);
      if (v.inst && vis) v.inst.mixer.update(dt);
    }
    this.trees?.update(dt);
  }

  updateUnit(v, e, dt) {
    if (!e.alive) {
      if (v.actionName !== 'Death') this.play(v, 'Death');
      const age = (this.w.tick - e.deadT) / 20;
      if (age > 4) v.root.position.y -= Math.min(1.5, (age - 4) * 0.6);
      return;
    }
    if (e.anim !== v.anim || e.animT !== v.animT) {
      const restart = e.anim !== v.anim || e.anim === 'Attack' || e.anim === 'Cast';
      v.anim = e.anim; v.animT = e.animT;
      if (restart) this.play(v, e.anim, e.animDur);
    }
    if (v.actionName === 'Walk' && v.action) {
      const ws = (v.meta?.walk_speed || 0.9) * v.scale;
      v.action.setEffectiveTimeScale(Math.min(2.6, Math.max(0.6, e.def.speed * e.mods.speed / ws / 1.55)));
    }
    // invisible own units turn ghostly
    const ghost = !!e.mods?.invisible;
    if (ghost !== !!v.ghost) this.setGhost(v, ghost);
  }

  setGhost(v, on) {
    v.ghost = on;
    v.root.traverse(o => {
      if (!o.isMesh) return;
      if (on) {
        o.userData.orig = o.material;
        const mk = m => { const c = m.clone(); c.transparent = true; c.opacity = 0.38; c.depthWrite = false; c.userData = { ...m.userData, fogPatched: false }; this.app.fog.patch(c); return c; };
        o.material = Array.isArray(o.material) ? o.material.map(mk) : mk(o.material);
      } else if (o.userData.orig) { o.material = o.userData.orig; }
    });
  }

  updateBuilding(v, e, dt) {
    if (!e.alive) {
      const age = (this.w.tick - e.deadT) / 20;
      v.root.position.y -= Math.min(v.height * 1.1, age * age * 0.9);
      v.root.rotation.z = Math.sin(age * 9) * 0.02 * Math.min(1, age);
      return;
    }
    if (e.built < 1) v.root.position.y -= (1 - e.built) * v.height * 0.92;
  }

  // selection decal under an entity
  setSelected(e, color) {
    const v = this.views.get(e.id);
    if (!v) return;
    if (!color) { if (v.sel) { v.root.remove(v.sel); v.sel = null; } return; }
    if (!v.sel) {
      const r = e.kind === 'unit' ? e.r * 2.6 * (e.def.boss ? 1.6 : 1) : Math.max(e.w, e.h) * 1.25;
      v.sel = new THREE.Mesh(this.ringGeo, this.ringMat(color));
      v.sel.scale.set(r, 1, r);
      v.sel.position.y = 0.06;
      v.sel.renderOrder = 3;
      v.root.add(v.sel);
    } else v.sel.material = this.ringMat(color);
    // keep the ring upright-flat regardless of the unit's rotation
  }
}
