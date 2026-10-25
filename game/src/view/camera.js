// WC3-style RTS camera: fixed pitch, zoom on wheel, pan with edges/WASD/
// arrows/middle drag, ground following, map bounds.
import * as THREE from 'three';

export class RtsCamera {
  constructor(camera, dom, grid) {
    this.cam = camera; this.dom = dom; this.grid = grid;
    this.target = new THREE.Vector3(0, 0, 0);
    this.dist = 30; this.minD = 16; this.maxD = 52;
    this.pitch = THREE.MathUtils.degToRad(56);
    this.yaw = 0;
    this.keys = new Set();
    this.mouse = { x: -1, y: -1, inside: false };
    this.edge = true;
    this.drag = null;
    this.shakeT = 0;
    dom.addEventListener('wheel', e => { e.preventDefault(); this.zoomBy(e.deltaY > 0 ? 1.12 : 1 / 1.12); }, { passive: false });
    addEventListener('keydown', e => { if (!e.target.closest?.('input,textarea')) this.keys.add(e.code); });
    addEventListener('keyup', e => this.keys.delete(e.code));
    addEventListener('blur', () => this.keys.clear());
    dom.addEventListener('pointermove', e => { this.mouse.x = e.clientX; this.mouse.y = e.clientY; this.mouse.inside = true; if (this.drag) this.onDrag(e); });
    document.addEventListener('pointerleave', () => { this.mouse.inside = false; });
    dom.addEventListener('pointerdown', e => { if (e.button === 1) { this.drag = { x: e.clientX, y: e.clientY, t: this.target.clone() }; e.preventDefault(); } });
    addEventListener('pointerup', e => { if (e.button === 1) this.drag = null; });
  }

  zoomBy(k) { this.dist = THREE.MathUtils.clamp(this.dist * k, this.minD, this.maxD); }

  onDrag(e) {
    const s = this.dist / 700;
    this.target.x = this.drag.t.x - (e.clientX - this.drag.x) * s;
    this.target.z = this.drag.t.z - (e.clientY - this.drag.y) * s * 1.3;
    this.clamp();
  }

  lookAt(x, y) { this.target.x = x; this.target.z = -y; this.clamp(); }
  shake(a) { this.shakeT = Math.max(this.shakeT, a); }

  clamp() {
    const h = this.grid.half - 6;
    this.target.x = THREE.MathUtils.clamp(this.target.x, -h, h);
    this.target.z = THREE.MathUtils.clamp(this.target.z, -h + 4, h + 10);
  }

  update(dt, hudRect) {
    const sp = this.dist * 1.25 * dt;
    let dx = 0, dz = 0;
    const K = this.keys;
    if (K.has('ArrowLeft')) dx -= 1; if (K.has('ArrowRight')) dx += 1;
    if (K.has('ArrowUp')) dz -= 1; if (K.has('ArrowDown')) dz += 1;
    if (this.edge && this.mouse.inside && document.hasFocus() && !this.drag) {
      const m = 6, W = innerWidth, H = innerHeight;
      if (this.mouse.x <= m) dx -= 1; else if (this.mouse.x >= W - m) dx += 1;
      if (this.mouse.y <= m) dz -= 1; else if (this.mouse.y >= H - m) dz += 1;
    }
    this.target.x += dx * sp; this.target.z += dz * sp;
    this.clamp();
    // follow terrain so hills don't swallow the view
    const gy = this.grid.heightAt(this.target.x, -this.target.z);
    this.target.y += (Math.max(0, gy) - this.target.y) * Math.min(1, dt * 4);
    const off = new THREE.Vector3(0, Math.sin(this.pitch), Math.cos(this.pitch)).multiplyScalar(this.dist);
    this.cam.position.copy(this.target).add(off);
    if (this.shakeT > 0) {
      this.shakeT = Math.max(0, this.shakeT - dt * 2.5);
      this.cam.position.x += (Math.random() - 0.5) * this.shakeT * 0.6;
      this.cam.position.y += (Math.random() - 0.5) * this.shakeT * 0.6;
    }
    this.cam.lookAt(this.target.x, this.target.y + 1.2, this.target.z - 2);
    void hudRect;
  }

  // ray -> ground intersection by marching the heightfield
  groundAt(ndcX, ndcY, out = new THREE.Vector3()) {
    const ray = new THREE.Raycaster();
    ray.setFromCamera({ x: ndcX, y: ndcY }, this.cam);
    const o = ray.ray.origin, d = ray.ray.direction;
    let t = 0, prev = null;
    for (let i = 0; i < 400; i++) {
      const x = o.x + d.x * t, y = o.y + d.y * t, z = o.z + d.z * t;
      const h = Math.max(this.grid.heightAt(x, -z), -0.3);
      if (y <= h) {
        if (prev) {                                    // refine between last two samples
          let a = prev, b = t;
          for (let k = 0; k < 8; k++) { const m = (a + b) / 2; const yy = o.y + d.y * m, hh = this.grid.heightAt(o.x + d.x * m, -(o.z + d.z * m)); if (yy <= hh) b = m; else a = m; }
          t = b;
        }
        return out.set(o.x + d.x * t, 0, o.z + d.z * t);
      }
      prev = t; t += 0.5;
    }
    return null;
  }
}
