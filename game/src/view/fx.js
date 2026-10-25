// Effects: projectiles with arcs, additive particles, spell zones, order
// markers. Everything is driven by sim events; nothing here feeds back.
import * as THREE from 'three';
import { radialTexture } from './textures.js';

const MAXP = 4000;

class Particles {
  constructor(scene) {
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(MAXP * 3);
    this.col = new Float32Array(MAXP * 4);
    this.size = new Float32Array(MAXP);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('color', new THREE.BufferAttribute(this.col, 4).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('size', new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage));
    this.geo = g;
    this.mat = new THREE.ShaderMaterial({
      uniforms: { tex: { value: radialTexture(64, [[0, 'rgba(255,255,255,1)'], [0.35, 'rgba(255,255,255,0.6)'], [1, 'rgba(255,255,255,0)']]) }, scale: { value: 600 } },
      vertexShader: `attribute float size; attribute vec4 color; varying vec4 vC;
        uniform float scale;
        void main() { vC = color; vec4 mv = modelViewMatrix * vec4(position, 1.0); gl_PointSize = size * scale / -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform sampler2D tex; varying vec4 vC;
        void main() { vec4 t = texture2D(tex, gl_PointCoord); gl_FragColor = vec4(vC.rgb * t.rgb, vC.a * t.a); }`,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    });
    this.pts = new THREE.Points(g, this.mat);
    this.pts.frustumCulled = false;
    this.pts.renderOrder = 5;
    scene.add(this.pts);
    this.list = [];
  }

  emit(o) { if (this.list.length < MAXP) this.list.push({ life: 0, ...o }); }

  burst(x, y, z, n, opt) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, u = Math.random() * 2 - 1, sp = (opt.speed || 3) * (0.4 + Math.random() * 0.8);
      const r = Math.sqrt(1 - u * u);
      this.emit({
        x, y, z, vx: Math.cos(a) * r * sp, vy: Math.abs(u) * sp * (opt.up ?? 1) + (opt.lift || 0), vz: Math.sin(a) * r * sp,
        ttl: (opt.ttl || 0.6) * (0.6 + Math.random() * 0.8), size: (opt.size || 0.3) * (0.6 + Math.random() * 0.8),
        c: opt.color || [1, 0.8, 0.4], g: opt.gravity ?? 3, drag: opt.drag ?? 1.5, a: opt.alpha ?? 1, grow: opt.grow || 0,
      });
    }
  }

  update(dt) {
    const L = this.list;
    let n = 0;
    for (let i = 0; i < L.length; i++) {
      const p = L[i];
      p.life += dt;
      if (p.life >= p.ttl) continue;
      p.vy -= p.g * dt;
      const d = Math.max(0, 1 - p.drag * dt);
      p.vx *= d; p.vy *= d; p.vz *= d;
      p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
      const k = p.life / p.ttl, fade = k < 0.15 ? k / 0.15 : 1 - (k - 0.15) / 0.85;
      this.pos[n * 3] = p.x; this.pos[n * 3 + 1] = p.y; this.pos[n * 3 + 2] = p.z;
      this.col[n * 4] = p.c[0]; this.col[n * 4 + 1] = p.c[1]; this.col[n * 4 + 2] = p.c[2]; this.col[n * 4 + 3] = p.a * fade;
      this.size[n] = p.size * (1 + p.grow * k);
      L[n++] = p;
    }
    L.length = n;
    this.geo.setDrawRange(0, n);
    for (const k of ['position', 'color', 'size']) this.geo.attributes[k].needsUpdate = true;
  }
}

const PROJ = {
  arrow: { len: 0.7, w: 0.035, col: '#d8c79a', trail: [1, 0.95, 0.8], arc: 0.18 },
  bolt: { len: 0.5, w: 0.05, col: '#9a9488', trail: [1, 0.9, 0.7], arc: 0.06 },
  seed: { len: 0.16, w: 0.1, col: '#3b2c1c', trail: null, arc: 0.12 },
  magic: { len: 0.25, w: 0.25, col: '#c9a2ff', trail: [0.75, 0.55, 1], arc: 0.04, glow: true },
  flask: { len: 0.22, w: 0.18, col: '#7cd04a', trail: [0.5, 1, 0.3], arc: 0.3, glow: true },
  stick: { len: 0.6, w: 0.06, col: '#8a5c32', trail: [1, 0.9, 0.6], arc: 0.08, spin: true },
};

export class Fx {
  constructor(app) {
    this.app = app;
    this.scene = app.scene;
    this.parts = new Particles(app.scene);
    this.projs = new Map();
    this.zones = new Map();
    this.markers = [];
    this.projGeo = new THREE.BoxGeometry(1, 1, 1);
    this.projMats = {};
    this.glowTex = radialTexture(64, [[0, 'rgba(255,255,255,1)'], [0.4, 'rgba(255,255,255,0.45)'], [1, 'rgba(255,255,255,0)']]);
    this.discGeo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
  }

  h(x, y) { return this.app.world.grid.heightAt(x, y); }

  heightOf(id) {
    const v = this.app.views.views.get(id);
    return v ? v.height || 1.2 : 1.2;
  }

  projMat(col) {
    if (!this.projMats[col]) this.projMats[col] = new THREE.MeshStandardMaterial({ color: col, roughness: 0.6 });
    return this.projMats[col];
  }

  onEvent(ev) {
    const w = this.app.world;
    switch (ev.k) {
      case 'proj': {
        const src = w.byId.get(ev.src), t = w.byId.get(ev.target);
        if (!src || !t) return;
        const S = PROJ[ev.kind] || PROJ.arrow;
        const obj = new THREE.Group();
        if (S.glow) {
          const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.glowTex, color: S.col, blending: THREE.AdditiveBlending, depthWrite: false }));
          sp.scale.setScalar(0.7); obj.add(sp);
        } else {
          const m = new THREE.Mesh(this.projGeo, this.projMat(S.col));
          m.scale.set(S.w, S.w, S.len); obj.add(m);
        }
        const z0 = ev.z0 ?? (src.kind === 'unit' ? this.heightOf(src.id) * 0.62 : 3);
        const d0 = Math.hypot(t.x - src.x, t.y - src.y);
        this.scene.add(obj);
        this.projs.set(ev.id, { obj, S, z0, d0: Math.max(0.5, d0), last: null, x0: src.x, y0: src.y, tid: t.id });
        break;
      }
      case 'projend': {
        const p = this.projs.get(ev.id);
        if (!p) return;
        this.scene.remove(p.obj);
        this.projs.delete(ev.id);
        if (ev.hit && p.last) this.parts.burst(p.last.x, p.last.y, p.last.z, p.S.glow ? 14 : 4, { color: p.S.trail || [1, 0.85, 0.6], speed: 2.2, ttl: 0.35, size: 0.22 });
        break;
      }
      case 'hit': {
        const t = w.byId.get(ev.id);
        if (!t || ev.amt <= 0) return;
        const z = this.h(t.x, t.y) + (t.kind === 'unit' ? this.heightOf(t.id) * 0.55 : 1.5);
        const blood = t.kind === 'unit' && ev.atk !== 'fire';
        this.parts.burst(t.x, z, -t.y, t.kind === 'building' ? 5 : 3, blood
          ? { color: [0.75, 0.08, 0.05], speed: 2.2, ttl: 0.45, size: 0.16, gravity: 9, alpha: 0.9 }
          : { color: [1, 0.75, 0.4], speed: 3, ttl: 0.3, size: 0.18 });
        break;
      }
      case 'death': {
        const e = w.byId.get(ev.id);
        if (!e) return;
        if (e.kind === 'tree') this.app.views.trees?.fell(e, null);
        else if (e.kind === 'building') {
          this.app.cam.shake(0.8);
          for (let k = 0; k < 6; k++) this.parts.burst(e.x + (Math.random() - 0.5) * e.w, this.h(e.x, e.y) + 1, -e.y + (Math.random() - 0.5) * e.h, 14, { color: [0.45, 0.4, 0.34], speed: 3, ttl: 1.6, size: 1.4, gravity: -0.6, drag: 1.2, alpha: 0.35, grow: 1.5 });
        }
        break;
      }
      case 'chop': { const t = w.byId.get(ev.id); if (t) { this.app.views.trees?.shake(t); this.parts.burst(t.x, this.h(t.x, t.y) + 1, -t.y, 3, { color: [0.85, 0.7, 0.45], speed: 2, ttl: 0.5, size: 0.12, gravity: 8 }); } break; }
      case 'level': {
        const e = w.byId.get(ev.id);
        if (e) this.ring(e.x, e.y, [1, 0.85, 0.35], 2.2, 1.2, e.id), this.parts.burst(e.x, this.h(e.x, e.y) + 0.3, -e.y, 40, { color: [1, 0.85, 0.35], speed: 1.2, lift: 3, ttl: 1.2, size: 0.25, gravity: 0, drag: 0.5 });
        break;
      }
      case 'cast': this.cast(ev); break;
      case 'zone': this.zone(ev); break;
      case 'zoneend': { const z = this.zones.get(ev.id); if (z) { z.dying = 0.5; } break; }
      case 'fx': this.misc(ev); break;
      case 'ackpt': this.marker(ev.x, ev.y, ev.kind === 'amove' ? [1, 0.25, 0.15] : [0.3, 1, 0.35]); break;
      case 'leap': {
        const e = w.byId.get(ev.id);
        if (e) this.parts.burst(ev.x0, this.h(ev.x0, ev.y0) + 0.1, -ev.y0, 10, { color: [0.75, 0.65, 0.5], speed: 2, ttl: 0.6, size: 0.6, gravity: -0.5, alpha: 0.3, grow: 1 });
        break;
      }
      case 'deposit': break;
    }
  }

  ring(x, y, col, r, ttl, follow = 0) {
    const m = new THREE.Mesh(this.discGeo, new THREE.MeshBasicMaterial({ map: this.app.views.ringTex, color: new THREE.Color(...col), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
    m.position.set(x, this.h(x, y) + 0.08, -y);
    this.scene.add(m);
    this.markers.push({ m, t: 0, ttl, r0: r * 0.3, r1: r, follow });
  }

  marker(x, y, col) { this.ring(x, y, col, 1.4, 0.5); this.parts.burst(x, this.h(x, y) + 0.1, -y, 8, { color: col, speed: 1.5, ttl: 0.4, size: 0.15, gravity: 0 }); }

  cast(ev) {
    const w = this.app.world, e = w.byId.get(ev.id);
    if (!e) return;
    const col = VFX_COL[ev.vfx] || [0.8, 0.7, 1];
    const hz = this.h(e.x, e.y);
    this.parts.burst(e.x, hz + 1, -e.y, 24, { color: col, speed: 2.5, ttl: 0.6, size: 0.3, gravity: -1 });
    if (ev.r) this.ring(ev.x, ev.y, col, ev.r * 2, 0.7);
    if (ev.vfx === 'claw' || ev.vfx === 'q') this.parts.burst(ev.x, this.h(ev.x, ev.y) + 1, -ev.y, 18, { color: [1, 0.3, 0.2], speed: 4, ttl: 0.4, size: 0.2 });
    if (ev.vfx === 'night') { this.app.flash([0.1, 0.05, 0.25], 0.9); }
    if (ev.vfx === 'howl' || ev.vfx === 'bark') this.app.cam.shake(0.4);
    if (ev.vfx === 'coins') this.parts.burst(e.x, hz + 1.6, -e.y, 30, { color: [1, 0.85, 0.2], speed: 3, lift: 3, ttl: 1, size: 0.18, gravity: 9 });
  }

  zone(ev) {
    const col = ZONE_COL[ev.kind] || [0.7, 0.7, 1];
    const g = new THREE.Group();
    const disc = new THREE.Mesh(this.discGeo, new THREE.MeshBasicMaterial({ map: this.app.views.ringTex, color: new THREE.Color(...col), transparent: true, opacity: 0.8, depthWrite: false, blending: THREE.AdditiveBlending }));
    disc.scale.set(ev.r * 2, 1, ev.r * 2);
    g.add(disc);
    if (ev.kind === 'barrier') {
      for (let k = -2; k <= 2; k++) {
        const b = new THREE.Mesh(new THREE.IcosahedronGeometry(0.55, 1), new THREE.MeshStandardMaterial({ color: '#4f8a2c', roughness: 0.8 }));
        b.position.set(k * 0.9, 0.4, 0); b.scale.y = 0.8; b.castShadow = true;
        g.add(b);
      }
      g.rotation.y = -(this.app.world.zones.find(z => z.id === ev.id)?.rot || 0);
      disc.visible = false;
    }
    if (ev.kind === 'roller') {
      const big = ev.length > 20;
      const wheel = new THREE.Mesh(new THREE.CylinderGeometry(big ? 2 : 0.8, big ? 2 : 0.8, big ? 1.2 : 0.5, 16), new THREE.MeshStandardMaterial({ color: '#8a5a30', roughness: 0.7 }));
      wheel.rotation.z = Math.PI / 2; wheel.position.y = big ? 2 : 0.8; wheel.castShadow = true;
      const isArrow = this.app.world.zones.find(z => z.id === ev.id)?.style === 'arrow';
      if (!isArrow) g.add(wheel);
      disc.visible = false;
      g.userData.wheel = isArrow ? null : wheel;
      g.userData.arrow = isArrow;
      g.rotation.y = Math.atan2(ev.dx, -ev.dy) + Math.PI / 2;
    }
    g.position.set(ev.x, this.h(ev.x, ev.y) + 0.07, -ev.y);
    this.scene.add(g);
    this.zones.set(ev.id, { g, disc, kind: ev.kind, r: ev.r, col, t: 0, follow: ev.follow });
  }

  misc(ev) {
    const x = ev.x, y = ev.y, h = this.h(x, y);
    switch (ev.fx) {
      case 'burrow': this.parts.burst(x, h + 0.2, -y, 16, { color: [0.45, 0.36, 0.26], speed: 3, ttl: 0.9, size: 0.5, gravity: 4, alpha: 0.5, grow: 0.8 }); break;
      case 'summon': this.parts.burst(x, h + 0.5, -y, 18, { color: [0.6, 0.8, 1], speed: 1.6, lift: 2, ttl: 0.8, size: 0.3, gravity: 0 }); break;
      case 'vanish': this.parts.burst(x, h + 0.6, -y, 14, { color: [0.7, 0.7, 0.9], speed: 1, lift: 1, ttl: 0.7, size: 0.4, gravity: 0, alpha: 0.5 }); break;
      case 'heal': this.parts.burst(x, h + 0.8, -y, 6, { color: [0.4, 1, 0.4], speed: 0.6, lift: 1.5, ttl: 0.8, size: 0.22, gravity: 0 }); break;
      case 'revive': this.ring(x, y, [1, 0.9, 0.5], 3, 1.4); this.parts.burst(x, h + 0.5, -y, 50, { color: [1, 0.9, 0.5], speed: 1, lift: 4, ttl: 1.3, size: 0.3, gravity: 0 }); break;
      case 'slam': this.app.cam.shake(0.35); this.ring(x, y, [1, 0.9, 0.7], (ev.r || 2) * 2, 0.6); this.parts.burst(x, h + 0.1, -y, 26, { color: [0.7, 0.6, 0.45], speed: 4, ttl: 0.8, size: 0.6, gravity: 2, alpha: 0.45, grow: 1 }); break;
      case 'parry': this.parts.burst(x, h + 1, -y, 10, { color: [1, 1, 0.8], speed: 5, ttl: 0.25, size: 0.15 }); break;
    }
  }

  update(dt) {
    const w = this.app.world;
    for (const [id, p] of this.projs) {
      const sp = w.projectiles.find(q => q.id === id);
      const t = w.byId.get(p.tid);
      if (!sp || !t) continue;
      const rem = Math.hypot(t.x - sp.x, t.y - sp.y);
      const k = Math.min(1, 1 - rem / p.d0);
      const zt = this.h(t.x, t.y) + (t.kind === 'unit' ? this.heightOf(t.id) * 0.55 : 1.5);
      const zs = this.h(p.x0, p.y0) + p.z0;
      const z = zs + (zt - zs) * k + Math.sin(k * Math.PI) * p.d0 * p.S.arc;
      const pos = new THREE.Vector3(sp.x, z, -sp.y);
      if (p.last) {
        const dir = pos.clone().sub(p.last);
        if (dir.lengthSq() > 1e-6) p.obj.lookAt(pos.clone().add(dir));
        if (p.S.trail) this.parts.emit({ x: pos.x, y: pos.y, z: pos.z, vx: 0, vy: 0, vz: 0, ttl: 0.25, size: p.S.glow ? 0.45 : 0.12, c: p.S.trail, g: 0, drag: 0, a: 0.6 });
      }
      if (p.S.spin) p.obj.rotateX(dt * 20);
      p.obj.position.copy(pos);
      p.last = pos;
    }
    for (const [id, z] of this.zones) {
      z.t += dt;
      if (z.follow) { const f = w.byId.get(z.follow); if (f && f.alive) z.g.position.set(f.x, this.h(f.x, f.y) + 0.07, -f.y); }
      const sz = w.zones.find(q => q.id === id);
      if (sz && z.kind === 'roller') {
        z.g.position.set(sz.x, this.h(sz.x, sz.y) + 0.05, -sz.y);
        if (z.g.userData.wheel) z.g.userData.wheel.rotation.x += dt * 8;
        if (z.g.userData.arrow) this.parts.burst(sz.x, this.h(sz.x, sz.y) + 1, -sz.y, 2, { color: [1, 0.6, 0.2], speed: 0.5, ttl: 0.3, size: 0.4, gravity: 0 });
        else this.parts.burst(sz.x, this.h(sz.x, sz.y) + 0.2, -sz.y, 1, { color: [0.6, 0.5, 0.4], speed: 1.5, ttl: 0.6, size: 0.5, gravity: 0, alpha: 0.4 });
      }
      z.disc.material.opacity = (0.55 + Math.sin(z.t * 4) * 0.15) * (z.dying != null ? z.dying * 2 : 1);
      if (z.kind === 'rain' && Math.random() < 0.9) {
        const a = Math.random() * 6.28, r = Math.sqrt(Math.random()) * z.r, x = z.g.position.x + Math.cos(a) * r, zz = z.g.position.z + Math.sin(a) * r;
        this.parts.emit({ x, y: z.g.position.y + 7, z: zz, vx: 0, vy: -26, vz: 0, ttl: 0.27, size: 0.18, c: [1, 0.85, 0.5], g: 0, drag: 0, a: 1 });
      }
      if (z.kind === 'heal' && Math.random() < 0.5) {
        const a = Math.random() * 6.28, r = Math.random() * z.r;
        this.parts.emit({ x: z.g.position.x + Math.cos(a) * r, y: z.g.position.y + 0.2, z: z.g.position.z + Math.sin(a) * r, vx: 0, vy: 1.2, vz: 0, ttl: 1, size: 0.25, c: [0.5, 1, 0.5], g: 0, drag: 0, a: 0.8 });
      }
      if (z.dying != null) { z.dying -= dt; if (z.dying <= 0) { this.scene.remove(z.g); this.zones.delete(id); } }
    }
    this.markers = this.markers.filter(m => {
      m.t += dt;
      const k = m.t / m.ttl;
      if (m.follow) { const e = w.byId.get(m.follow); if (e) m.m.position.set(e.x, this.h(e.x, e.y) + 0.08, -e.y); }
      const r = m.r0 + (m.r1 - m.r0) * Math.min(1, k * 1.5);
      m.m.scale.set(r, 1, r);
      m.m.material.opacity = 1 - k;
      if (k >= 1) { this.scene.remove(m.m); m.m.material.dispose(); return false; }
      return true;
    });
    this.parts.update(dt);
  }
}

const VFX_COL = { claw: [1, 0.3, 0.2], night: [0.5, 0.3, 1], bark: [1, 0.85, 0.5], howl: [0.6, 0.7, 1], coins: [1, 0.85, 0.2],
  leap: [0.9, 0.95, 1], exodus: [0.9, 0.95, 1], q: [1, 0.7, 0.4], w: [0.6, 1, 0.6], e: [0.6, 0.8, 1], r: [1, 0.5, 1] };
const ZONE_COL = { heal: [0.4, 1, 0.45], rain: [1, 0.7, 0.3], miss: [0.5, 0.3, 0.9], yarn: [1, 0.5, 0.7], reveal: [1, 0.95, 0.6], ward: [1, 0.9, 0.5],
  duel: [1, 0.25, 0.2], barrier: [0.3, 0.8, 0.3], roller: [0.8, 0.6, 0.4], waves: [0.7, 0.9, 0.5] };
