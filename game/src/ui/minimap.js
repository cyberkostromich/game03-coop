// Minimap: painted terrain backdrop, fog, units, camera trapezoid, pings.
import * as THREE from 'three';

export class Minimap {
  constructor(app, splatImg) {
    this.app = app;
    this.w = app.world;
    this.cv = document.getElementById('minimap');
    this.g = this.cv.getContext('2d');
    this.S = this.cv.width;
    this.terrain = true;
    this.pings = [];
    this.t = 0;
    this.bg = this.paintBackdrop(splatImg);
    this.fogCv = document.createElement('canvas');
    this.fogCv.width = this.fogCv.height = this.w.grid.n;
    this.fogG = this.fogCv.getContext('2d');
    this.fogImg = this.fogG.createImageData(this.w.grid.n, this.w.grid.n);
    let down = false;
    const at = e => {
      const r = this.cv.getBoundingClientRect();
      const u = (e.clientX - r.left) / r.width, v = (e.clientY - r.top) / r.height;
      const half = this.w.grid.half;
      return { x: -half + u * half * 2, y: half - v * half * 2 };
    };
    this.cv.addEventListener('pointerdown', e => {
      e.stopPropagation();
      const p = at(e);
      if (e.button === 0 && (e.altKey || app.input.mode?.kind === 'ping')) { app.ping(p.x, p.y); app.input.setMode(null); return; }
      if (e.button === 0 && app.input.mode?.kind === 'target') { app.input.applyModeAt(p); return; }
      if (e.button === 0) { down = true; app.cam.lookAt(p.x, p.y); this.cv.setPointerCapture(e.pointerId); }
      if (e.button === 2) app.input.smart(0, 0, e.shiftKey, p);
    });
    this.cv.addEventListener('pointermove', e => { if (down) { const p = at(e); app.cam.lookAt(p.x, p.y); } });
    this.cv.addEventListener('pointerup', () => { down = false; });
    this.cv.addEventListener('contextmenu', e => e.preventDefault());
  }

  paintBackdrop(img) {
    const S = this.S, c = document.createElement('canvas');
    c.width = c.height = S;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0, S, S);
    const D = g.getImageData(0, 0, S, S), d = D.data, grid = this.w.grid, half = grid.half;
    const cols = [[78, 120, 40], [128, 96, 58], [204, 178, 118], [120, 116, 106]];
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const i = (y * S + x) * 4;
      const wx = -half + (x + 0.5) / S * half * 2, wy = half - (y + 0.5) / S * half * 2;
      const h = grid.heightAt(wx, wy);
      const s = [d[i], d[i + 1], d[i + 2], d[i + 3]].map(v => v / 255);
      const tot = s[0] + s[1] + s[2] + s[3] || 1;
      let r = 0, gg = 0, b = 0;
      for (let k = 0; k < 4; k++) { r += cols[k][0] * s[k] / tot; gg += cols[k][1] * s[k] / tot; b += cols[k][2] * s[k] / tot; }
      // hillshade from the north-west
      const dx = grid.heightAt(wx + 1, wy) - grid.heightAt(wx - 1, wy), dy = grid.heightAt(wx, wy + 1) - grid.heightAt(wx, wy - 1);
      const shade = 1 + (-dx + dy) * 0.12 + h * 0.02;
      r *= shade; gg *= shade; b *= shade;
      if (h < this.app.D.map.water_level) { const k = Math.min(1, (0 - h) * 1.5 + 0.4); r = r * (1 - k) + 30 * k; gg = gg * (1 - k) + 80 * k; b = b * (1 - k) + 110 * k; }
      d[i] = r; d[i + 1] = gg; d[i + 2] = b; d[i + 3] = 255;
    }
    g.putImageData(D, 0, 0);
    // forests as dark dabs
    g.fillStyle = 'rgba(18,48,16,0.75)';
    for (const e of this.w.ents) if (e.kind === 'tree') { const [px, py] = this.px(e.x, e.y, S); g.beginPath(); g.arc(px, py, 1.6, 0, 7); g.fill(); }
    return c;
  }

  px(x, y, S = this.S) { const half = this.w.grid.half; return [(x + half) / (half * 2) * S, (half - y) / (half * 2) * S]; }

  ping(x, y, color = '#ffd84a') { this.pings.push({ x, y, t: 0, color }); }

  update(dt) {
    this.t += dt;
    for (const p of this.pings) p.t += dt;
    this.pings = this.pings.filter(p => p.t < 4);
    if (this.t < 0.08) return;
    this.t = 0;
    const g = this.g, S = this.S, w = this.w, app = this.app;
    if (this.terrain) g.drawImage(this.bg, 0, 0); else { g.fillStyle = '#000'; g.fillRect(0, 0, S, S); }
    // fog: grid rows are south-up, canvas rows north-up
    const n = w.grid.n, F = app.fog.cur, d = this.fogImg.data;
    for (let cy = 0; cy < n; cy++) for (let cx = 0; cx < n; cx++) {
      const i = cy * n + cx, o = ((n - 1 - cy) * n + cx) * 4;
      const v = F[i * 2], e = F[i * 2 + 1];
      d[o] = d[o + 1] = d[o + 2] = 0;
      d[o + 3] = (1 - (e * (0.55 + 0.45 * v))) * 205;
    }
    this.fogG.putImageData(this.fogImg, 0, 0);
    g.imageSmoothingEnabled = true;
    g.drawImage(this.fogCv, 0, 0, S, S);
    // structures
    for (const e of w.blds) {
      if (!e.alive) continue;
      const i = w.grid.idx(e.x, e.y);
      if (e.team !== app.myTeam && !(i >= 0 && w.explored[i])) continue;
      const [px, py] = this.px(e.x, e.y);
      const sz = Math.max(5, e.w / (w.grid.size) * S * 1.4);
      g.fillStyle = e.type === 'gold_mine' ? '#ffd84a' : e.type === 'mill' ? '#e0e0e0' : app.views.colorOf(e);
      g.strokeStyle = '#000'; g.lineWidth = 1;
      g.fillRect(px - sz / 2, py - sz / 2, sz, sz); g.strokeRect(px - sz / 2, py - sz / 2, sz, sz);
    }
    // units
    const sel = new Set(app.sel);
    for (const e of w.units) {
      if (!e.alive || e.hidden) continue;
      if (e.team !== app.myTeam && !w.visibleTo(app.myTeam, e)) continue;
      const [px, py] = this.px(e.x, e.y);
      const r = e.def.hero ? 3.2 : e.def.boss ? 4.5 : 2;
      g.fillStyle = sel.has(e.id) ? '#ffffff' : e.owner === 5 ? '#c8c8c8' : app.views.colorOf(e);
      g.fillRect(px - r, py - r, r * 2, r * 2);
      if (e.def.hero) { g.strokeStyle = '#ffe68a'; g.strokeRect(px - r - 1, py - r - 1, r * 2 + 2, r * 2 + 2); }
    }
    // camp markers on explored ground
    for (const c of app.D.map.camps) {
      const i = w.grid.idx(c.x, c.y);
      if (!(i >= 0 && w.explored[i])) continue;
      if (!w.units.some(u => u.alive && u.camp && u.camp.x === c.x && u.camp.y === c.y)) continue;
      const [px, py] = this.px(c.x, c.y);
      g.fillStyle = c.level === 'green' ? '#4fe04f' : c.level === 'yellow' ? '#ffd84a' : '#ff5a3a';
      g.beginPath(); g.arc(px, py, 3, 0, 7); g.fill();
    }
    // camera view trapezoid
    const cam = app.camera, corners = [[-1, 1], [1, 1], [1, -0.55], [-1, -0.55]];
    g.strokeStyle = 'rgba(255,255,255,0.9)'; g.lineWidth = 1.5; g.beginPath();
    corners.forEach(([x, y], k) => {
      const p = app.cam.groundAt(x, y) || this.flat(cam, x, y);
      if (!p) return;
      const [px, py] = this.px(p.x, -p.z);
      if (k === 0) g.moveTo(px, py); else g.lineTo(px, py);
    });
    g.closePath(); g.stroke();
    for (const p of this.pings) {
      const [px, py] = this.px(p.x, p.y);
      const k = (p.t % 1);
      g.strokeStyle = p.color; g.globalAlpha = 1 - k; g.lineWidth = 2.5;
      g.beginPath(); g.arc(px, py, 4 + k * 16, 0, 7); g.stroke();
      g.globalAlpha = 1;
    }
  }

  flat(cam, x, y) {
    const r = new THREE.Raycaster();
    r.setFromCamera({ x, y }, cam);
    const t = -r.ray.origin.y / r.ray.direction.y;
    return t > 0 ? r.ray.origin.clone().add(r.ray.direction.clone().multiplyScalar(t)) : null;
  }
}
