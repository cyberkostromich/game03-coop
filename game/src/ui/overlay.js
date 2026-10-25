// 2D overlay drawn over the 3D view: health/mana bars, drag box, floating
// numbers (bounty gold, misses), screen-edge alerts.
import * as THREE from 'three';

export class Overlay {
  constructor(app) {
    this.app = app;
    this.cv = document.getElementById('overlay');
    this.g = this.cv.getContext('2d');
    this.texts = [];
    this.v3 = new THREE.Vector3();
    this.resize();
    addEventListener('resize', () => this.resize());
  }

  resize() {
    const dpr = Math.min(2, devicePixelRatio || 1);
    this.dpr = dpr;
    this.cv.width = innerWidth * dpr; this.cv.height = innerHeight * dpr;
  }

  float(x, y, z, text, color, size = 18) { this.texts.push({ x, y, z, text, color, size, t: 0 }); }

  project(x, y, z) {
    this.v3.set(x, y, z).project(this.app.camera);
    if (this.v3.z > 1) return null;
    return [(this.v3.x + 1) / 2 * innerWidth, (1 - this.v3.y) / 2 * innerHeight];
  }

  draw(dt) {
    const g = this.g, app = this.app, w = app.world;
    g.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    g.clearRect(0, 0, innerWidth, innerHeight);
    const sel = new Set(app.sel);
    const hover = app.hover;
    const all = app.input.alt || app.showBars;
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    for (const e of w.units.concat(w.blds)) {
      if (!e.alive || e.hidden) continue;
      const v = app.views.views.get(e.id);
      if (!v || !v.root.visible) continue;
      const recent = w.tick - (e.lastCombat ?? -1e9) < 80 && e.hp < e.maxHp;
      if (!(all || sel.has(e.id) || hover === e || recent || (e.kind === 'building' && e.built < 1 && e.owner === app.me))) continue;
      if (e.type === 'gold_mine' || e.type === 'mill') continue;
      const p = v.root.position;
      const sp = this.project(p.x, p.y + (v.height || 1.3) * (e.kind === 'unit' ? 1.12 : 1.02) + 0.25, p.z);
      if (!sp) continue;
      const W = (e.kind === 'building' ? 70 : e.def.hero || e.def.boss ? 52 : 38) * s * 1.4, H = Math.max(4, 6 * s * 1.3);
      const x = sp[0] - W / 2, y = sp[1];
      const f = Math.max(0, e.hp / e.maxHp);
      g.fillStyle = 'rgba(0,0,0,0.85)'; g.fillRect(x - 1, y - 1, W + 2, H + 2);
      g.fillStyle = f > 0.6 ? '#3fd24a' : f > 0.3 ? '#e6c63a' : '#e0402e';
      g.fillRect(x, y, W * f, H);
      g.fillStyle = 'rgba(255,255,255,0.25)'; g.fillRect(x, y, W * f, H * 0.4);
      if (e.maxMana) {
        g.fillStyle = 'rgba(0,0,0,0.85)'; g.fillRect(x - 1, y + H + 1, W + 2, H * 0.7 + 2);
        g.fillStyle = '#4a7cf0'; g.fillRect(x, y + H + 2, W * e.mana / e.maxMana, H * 0.7);
      }
      if (e.kind === 'building' && e.built < 1) {
        g.fillStyle = 'rgba(0,0,0,0.85)'; g.fillRect(x - 1, y + H + 1, W + 2, H * 0.7 + 2);
        g.fillStyle = '#e8b040'; g.fillRect(x, y + H + 2, W * e.built, H * 0.7);
      }
      // team strip so allied units are told apart
      if (e.team === 0 && e.owner !== app.me) { g.fillStyle = app.views.colorOf(e); g.fillRect(x - 4, y - 1, 3, H + 2); }
    }
    // floating text
    this.texts = this.texts.filter(t => {
      t.t += dt;
      const p = this.project(t.x, t.y + t.t * 1.2, t.z);
      if (!p) return t.t < 1.6;
      g.globalAlpha = Math.max(0, 1 - Math.max(0, t.t - 0.9) / 0.7);
      g.font = `800 ${Math.round(t.size * Math.max(0.7, s))}px 'Alegreya Sans', sans-serif`;
      g.textAlign = 'center';
      g.lineWidth = 3; g.strokeStyle = '#000'; g.strokeText(t.text, p[0], p[1]);
      g.fillStyle = t.color; g.fillText(t.text, p[0], p[1]);
      g.globalAlpha = 1;
      return t.t < 1.6;
    });
    // drag box
    const b = app.input.box;
    if (b && (Math.abs(b.x1 - b.x0) > 5 || Math.abs(b.y1 - b.y0) > 5)) {
      g.strokeStyle = '#7aff7a'; g.lineWidth = 1.5;
      g.fillStyle = 'rgba(80,255,80,0.08)';
      const x = Math.min(b.x0, b.x1), y = Math.min(b.y0, b.y1), W = Math.abs(b.x1 - b.x0), H = Math.abs(b.y1 - b.y0);
      g.fillRect(x, y, W, H); g.strokeRect(x + 0.5, y + 0.5, W, H);
    }
    // targeting: ability range / area preview handled in 3D; show tooltip near cursor
    const m = app.input.mode;
    if (m?.kind === 'target' && m.cmd === 'cast') {
      g.font = `700 ${Math.round(16 * Math.max(0.8, s))}px 'Alegreya Sans', sans-serif`;
      g.textAlign = 'left'; g.lineWidth = 3; g.strokeStyle = '#000';
      g.strokeText(m.ability.name, app.input.mouse.x + 22, app.input.mouse.y + 30);
      g.fillStyle = '#ffe68a'; g.fillText(m.ability.name, app.input.mouse.x + 22, app.input.mouse.y + 30);
    }
  }
}
