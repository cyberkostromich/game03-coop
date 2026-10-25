// Icon painter: command and ability icons drawn as small paintings
// (gradient ground, lit glyph with dark outline, bevelled frame), plus unit
// icons rendered from the actual 3D models.
import * as THREE from 'three';

const S = 128;
const cache = new Map();

function canvas() { const c = document.createElement('canvas'); c.width = c.height = S; return c; }

function ground(g, c1, c2) {
  const gr = g.createRadialGradient(S * 0.35, S * 0.3, S * 0.05, S * 0.5, S * 0.5, S * 0.75);
  gr.addColorStop(0, c1); gr.addColorStop(1, c2);
  g.fillStyle = gr; g.fillRect(0, 0, S, S);
  // painterly speckle
  for (let i = 0; i < 60; i++) { g.fillStyle = `rgba(255,255,255,${Math.random() * 0.05})`; g.beginPath(); g.arc(Math.random() * S, Math.random() * S, 2 + Math.random() * 8, 0, 7); g.fill(); }
}

function finish(g) {
  // inner bevel + vignette like WC3 buttons
  const v = g.createRadialGradient(S / 2, S / 2, S * 0.35, S / 2, S / 2, S * 0.72);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.55)');
  g.fillStyle = v; g.fillRect(0, 0, S, S);
  g.strokeStyle = 'rgba(255,240,200,0.35)'; g.lineWidth = 3; g.strokeRect(2.5, 2.5, S - 5, S - 5);
  g.strokeStyle = 'rgba(0,0,0,0.7)'; g.lineWidth = 2; g.strokeRect(6, 6, S - 12, S - 12);
}

// glyph drawn three times: shadow, dark outline, lit fill with top highlight
function glyph(g, path, fill = '#f3e2b0', light = '#fffbe8') {
  g.save();
  g.translate(3, 4); g.fillStyle = 'rgba(0,0,0,0.55)'; g.strokeStyle = 'rgba(0,0,0,0.55)'; g.lineWidth = 10; g.lineJoin = g.lineCap = 'round';
  path(g, true); g.restore();
  g.save(); g.strokeStyle = '#1c130a'; g.fillStyle = '#1c130a'; g.lineWidth = 10; g.lineJoin = g.lineCap = 'round'; path(g, true); g.restore();
  g.save();
  const gr = g.createLinearGradient(0, S * 0.15, 0, S * 0.9);
  gr.addColorStop(0, light); gr.addColorStop(0.5, fill); gr.addColorStop(1, shade(fill));
  g.fillStyle = gr; g.strokeStyle = gr; g.lineWidth = 5; g.lineJoin = g.lineCap = 'round';
  path(g, false); g.restore();
}

function shade(hex) {
  const n = parseInt(hex.slice(1), 16);
  const f = v => Math.round(v * 0.55).toString(16).padStart(2, '0');
  return '#' + f(n >> 16 & 255) + f(n >> 8 & 255) + f(n & 255);
}

const P = {
  sword(g) { g.beginPath(); g.moveTo(92, 22); g.lineTo(104, 24); g.lineTo(102, 36); g.lineTo(52, 86); g.lineTo(42, 76); g.closePath(); g.fill(); g.stroke();
    g.beginPath(); g.moveTo(30, 70); g.lineTo(58, 98); g.stroke(); g.beginPath(); g.moveTo(38, 92); g.lineTo(24, 106); g.stroke(); },
  boot(g) { g.beginPath(); g.moveTo(44, 24); g.lineTo(70, 24); g.lineTo(72, 72); g.lineTo(102, 84); g.lineTo(102, 102); g.lineTo(40, 102); g.closePath(); g.fill(); g.stroke(); },
  hand(g) { g.beginPath(); g.arc(64, 72, 26, 0, Math.PI * 2); g.fill(); g.stroke(); for (let k = 0; k < 4; k++) { g.beginPath(); g.roundRect(42 + k * 12, 26 + Math.abs(k - 1.5) * 6, 10, 40, 5); g.fill(); g.stroke(); } },
  shield(g) { g.beginPath(); g.moveTo(64, 20); g.lineTo(100, 32); g.quadraticCurveTo(100, 84, 64, 108); g.quadraticCurveTo(28, 84, 28, 32); g.closePath(); g.fill(); g.stroke(); },
  patrol(g) { g.lineWidth = 9; g.beginPath(); g.arc(64, 64, 32, 0.3, Math.PI * 1.5); g.stroke(); g.beginPath(); g.moveTo(64, 18); g.lineTo(80, 32); g.lineTo(62, 44); g.closePath(); g.fill(); },
  hammer(g) { g.beginPath(); g.roundRect(30, 28, 56, 26, 6); g.fill(); g.stroke(); g.beginPath(); g.moveTo(58, 54); g.lineTo(84, 104); g.stroke(); g.lineWidth = 9; g.beginPath(); g.moveTo(58, 54); g.lineTo(84, 104); g.stroke(); },
  pick(g) { g.beginPath(); g.moveTo(22, 46); g.quadraticCurveTo(64, 10, 106, 46); g.quadraticCurveTo(64, 30, 22, 46); g.fill(); g.stroke(); g.lineWidth = 9; g.beginPath(); g.moveTo(64, 30); g.lineTo(64, 108); g.stroke(); },
  sack(g) { g.beginPath(); g.moveTo(48, 36); g.lineTo(80, 36); g.quadraticCurveTo(108, 70, 96, 100); g.lineTo(32, 100); g.quadraticCurveTo(20, 70, 48, 36); g.fill(); g.stroke(); g.beginPath(); g.ellipse(64, 30, 18, 8, 0, 0, 7); g.fill(); g.stroke(); },
  flag(g) { g.lineWidth = 7; g.beginPath(); g.moveTo(40, 108); g.lineTo(40, 20); g.stroke(); g.beginPath(); g.moveTo(42, 22); g.lineTo(100, 34); g.lineTo(80, 48); g.lineTo(100, 62); g.lineTo(42, 62); g.closePath(); g.fill(); g.stroke(); },
  up(g) { g.beginPath(); g.moveTo(64, 18); g.lineTo(104, 62); g.lineTo(80, 62); g.lineTo(80, 106); g.lineTo(48, 106); g.lineTo(48, 62); g.lineTo(24, 62); g.closePath(); g.fill(); g.stroke(); },
  crown(g) { g.beginPath(); g.moveTo(22, 92); g.lineTo(26, 40); g.lineTo(46, 62); g.lineTo(64, 30); g.lineTo(82, 62); g.lineTo(102, 40); g.lineTo(106, 92); g.closePath(); g.fill(); g.stroke(); },
  cross(g) { g.lineWidth = 16; g.beginPath(); g.moveTo(34, 34); g.lineTo(94, 94); g.moveTo(94, 34); g.lineTo(34, 94); g.stroke(); },
  book(g) { g.beginPath(); g.moveTo(20, 34); g.quadraticCurveTo(44, 24, 64, 36); g.quadraticCurveTo(84, 24, 108, 34); g.lineTo(108, 98); g.quadraticCurveTo(84, 88, 64, 100); g.quadraticCurveTo(44, 88, 20, 98); g.closePath(); g.fill(); g.stroke(); },
  plus(g) { g.lineWidth = 18; g.beginPath(); g.moveTo(64, 26); g.lineTo(64, 102); g.moveTo(26, 64); g.lineTo(102, 64); g.stroke(); },
  claw(g) { g.lineWidth = 9; for (let k = 0; k < 3; k++) { g.beginPath(); g.moveTo(30 + k * 20, 22); g.quadraticCurveTo(58 + k * 14, 64, 40 + k * 22, 106); g.stroke(); } },
  moon(g) { g.beginPath(); g.arc(64, 64, 40, 0.6, Math.PI * 2 - 0.6); g.arc(84, 54, 30, Math.PI * 2 - 0.9, 0.9, true); g.closePath(); g.fill(); g.stroke(); },
  heart(g) { g.beginPath(); g.moveTo(64, 104); g.bezierCurveTo(10, 66, 30, 18, 64, 44); g.bezierCurveTo(98, 18, 118, 66, 64, 104); g.fill(); g.stroke(); },
  bolt(g) { g.beginPath(); g.moveTo(72, 14); g.lineTo(34, 70); g.lineTo(60, 70); g.lineTo(50, 114); g.lineTo(94, 52); g.lineTo(66, 52); g.closePath(); g.fill(); g.stroke(); },
  eye(g) { g.beginPath(); g.moveTo(16, 64); g.quadraticCurveTo(64, 14, 112, 64); g.quadraticCurveTo(64, 114, 16, 64); g.fill(); g.stroke(); g.fillStyle = '#1c130a'; g.beginPath(); g.arc(64, 64, 14, 0, 7); g.fill(); },
  wheel(g) { g.lineWidth = 9; g.beginPath(); g.arc(64, 64, 38, 0, 7); g.stroke(); for (let k = 0; k < 6; k++) { const a = k * Math.PI / 3; g.beginPath(); g.moveTo(64, 64); g.lineTo(64 + Math.cos(a) * 38, 64 + Math.sin(a) * 38); g.stroke(); } g.beginPath(); g.arc(64, 64, 9, 0, 7); g.fill(); },
  coin(g) { for (const [x, y] of [[48, 74], [80, 74], [64, 46]]) { g.beginPath(); g.ellipse(x, y, 22, 22, 0, 0, 7); g.fill(); g.stroke(); } },
  paw(g) { g.beginPath(); g.ellipse(64, 78, 24, 20, 0, 0, 7); g.fill(); g.stroke(); for (const [x, y] of [[36, 48], [54, 32], [74, 32], [92, 48]]) { g.beginPath(); g.ellipse(x, y, 10, 13, 0, 0, 7); g.fill(); g.stroke(); } },
  spiral(g) { g.lineWidth = 8; g.beginPath(); for (let a = 0; a < 14; a += 0.2) { const r = 4 + a * 3; g.lineTo(64 + Math.cos(a) * r, 64 + Math.sin(a) * r); } g.stroke(); },
  arrow(g) { g.lineWidth = 7; g.beginPath(); g.moveTo(24, 104); g.lineTo(96, 32); g.stroke(); g.beginPath(); g.moveTo(104, 24); g.lineTo(78, 32); g.lineTo(96, 50); g.closePath(); g.fill(); g.stroke(); g.beginPath(); g.moveTo(24, 104); g.lineTo(26, 86); g.moveTo(24, 104); g.lineTo(42, 102); g.stroke(); },
  rain(g) { g.lineWidth = 6; for (let k = 0; k < 6; k++) { const x = 24 + k * 16; g.beginPath(); g.moveTo(x + 10, 20 + (k % 2) * 10); g.lineTo(x - 6, 76 + (k % 2) * 10); g.stroke(); } g.beginPath(); g.ellipse(64, 100, 40, 10, 0, 0, 7); g.fill(); },
  carrot(g) { g.beginPath(); g.moveTo(40, 40); g.lineTo(96, 108); g.lineTo(60, 30); g.closePath(); g.fill(); g.stroke(); g.lineWidth = 6; g.beginPath(); g.moveTo(44, 36); g.lineTo(30, 14); g.moveTo(50, 34); g.lineTo(52, 12); g.moveTo(42, 40); g.lineTo(18, 30); g.stroke(); },
  bush(g) { for (const [x, y, r] of [[44, 74, 26], [84, 74, 26], [64, 50, 28]]) { g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); g.stroke(); } },
  burrow(g) { g.beginPath(); g.ellipse(64, 80, 44, 24, 0, 0, 7); g.fill(); g.stroke(); g.fillStyle = '#1c130a'; g.beginPath(); g.ellipse(64, 82, 28, 13, 0, 0, 7); g.fill(); },
  swords(g) { g.lineWidth = 9; g.beginPath(); g.moveTo(24, 24); g.lineTo(96, 96); g.moveTo(104, 24); g.lineTo(32, 96); g.stroke(); g.beginPath(); g.moveTo(80, 104); g.lineTo(104, 80); g.moveTo(24, 80); g.lineTo(48, 104); g.stroke(); },
  hare(g) { g.beginPath(); g.ellipse(64, 80, 26, 22, 0, 0, 7); g.fill(); g.stroke(); g.beginPath(); g.ellipse(50, 36, 8, 26, -0.2, 0, 7); g.fill(); g.stroke(); g.beginPath(); g.ellipse(76, 36, 8, 26, 0.2, 0, 7); g.fill(); g.stroke(); },
  howl(g) { g.beginPath(); g.arc(64, 64, 22, 0, 7); g.fill(); g.stroke(); g.lineWidth = 6; for (let k = 1; k < 4; k++) { g.beginPath(); g.arc(64, 64, 22 + k * 12, -0.9, 0.9); g.stroke(); g.beginPath(); g.arc(64, 64, 22 + k * 12, Math.PI - 0.9, Math.PI + 0.9); g.stroke(); } },
  zzz(g) { g.lineWidth = 8; for (const [x, y, s] of [[30, 90, 26], [62, 60, 20], [88, 34, 15]]) { g.beginPath(); g.moveTo(x, y - s); g.lineTo(x + s, y - s); g.lineTo(x, y); g.lineTo(x + s, y); g.stroke(); } },
};

const THEMES = {
  red: ['#c4432c', '#3a0d08'], gold: ['#d8a83c', '#3b2508'], blue: ['#3e74c4', '#0b1a38'], green: ['#4fa040', '#0d2a0b'],
  purple: ['#7f4fc4', '#1d0b35'], stone: ['#8a8070', '#25201a'], night: ['#3a3f7a', '#07081c'], fire: ['#e08a2c', '#3a1404'],
};

export function icon(glyphName, theme = 'stone', fill = '#f3e2b0') {
  const key = glyphName + theme + fill;
  if (cache.has(key)) return cache.get(key);
  const c = canvas(), g = c.getContext('2d');
  const [a, b] = THEMES[theme] || THEMES.stone;
  ground(g, a, b);
  glyph(g, (gg) => (P[glyphName] || P.shield)(gg), fill);
  finish(g);
  const url = c.toDataURL();
  cache.set(key, url);
  return url;
}

// ability -> glyph and theme from its effect kinds and vfx tag
const KIND_GLYPH = {
  damage: 'sword', dot: 'claw', aura: 'howl', revive: 'heart', invisible: 'moon', dash: 'arrow', reflect_melee: 'shield', leap: 'hare',
  duel: 'swords', heal_area: 'heart', buff: 'up', miss_zone: 'eye', root_area: 'spiral', stun_cone: 'howl', redirect_damage: 'shield',
  summon: 'paw', hold: 'hand', damage_reduction: 'shield', taunt: 'howl', reveal: 'eye', projectile_bounce: 'arrow', ward: 'flag',
  grant_gold: 'coin', convert_neutral: 'coin', team_resources: 'coin', line_damage: 'wheel', turret: 'wheel', invulnerable_heal: 'zzz',
  stun_area: 'hare', invisible_when: 'moon', army_leap: 'hare', evasion: 'hare', illusions: 'eye', rain: 'rain', barrier: 'bush',
  grant_food: 'carrot', teleport_squad: 'burrow', train_speed: 'carrot', summon_waves: 'hare',
};
const KIND_THEME = { damage: 'red', dot: 'red', heal_area: 'green', invisible: 'night', invisible_when: 'night', buff: 'gold', aura: 'blue',
  revive: 'gold', summon: 'blue', rain: 'fire', line_damage: 'fire', grant_gold: 'gold', team_resources: 'gold', barrier: 'green',
  miss_zone: 'purple', root_area: 'purple', duel: 'red', stun_cone: 'gold', evasion: 'green', illusions: 'purple', reveal: 'gold' };

export function abilityIcon(a) {
  const k = a.effects.find(e => KIND_GLYPH[e.kind] && e.kind !== 'damage')?.kind || a.effects[0]?.kind;
  if (a.vfx === 'claw') return icon('claw', 'red');
  if (a.vfx === 'night') return icon('moon', 'night', '#cfd6ff');
  if (a.vfx === 'coins') return icon('coin', 'gold', '#ffd75a');
  if (a.key === 'Q' && a.effects.some(e => e.kind === 'line_damage') && a.range > 10) return icon('arrow', 'fire');
  if (a.effects.some(e => e.kind === 'line_damage') && a.range <= 10) return icon('wheel', 'fire');
  return icon(KIND_GLYPH[k] || 'bolt', KIND_THEME[k] || 'blue');
}

// Unit icons: a 3D bust render of the model into a small canvas.
export class UnitIcons {
  constructor(renderer, models) {
    this.r = renderer; this.models = models;
    this.rt = new THREE.WebGLRenderTarget(S, S, { colorSpace: THREE.SRGBColorSpace });
    this.scene = new THREE.Scene();
    this.cam = new THREE.PerspectiveCamera(26, 1, 0.05, 50);
    const key = new THREE.DirectionalLight(0xfff0dd, 5.5); key.position.set(1.5, 2.5, 3);
    const rim = new THREE.DirectionalLight(0x99bbff, 3.5); rim.position.set(-2, 1.5, -2);
    const fill = new THREE.DirectionalLight(0xffffff, 1.6); fill.position.set(-1, 0.5, 3);
    this.scene.add(fill);
    this.scene.add(key, rim, new THREE.HemisphereLight(0xcfdcff, 0x40302a, 2.2));
    this.urls = new Map();
    this.buf = new Uint8Array(S * S * 4);
  }

  get(kind, id, color, theme = 'stone') {
    const key = kind + id + color;
    if (this.urls.has(key)) return this.urls.get(key);
    const inst = this.models.instance(kind, id, color);
    if (!inst) return icon(kind === 'units' ? 'paw' : 'crown', theme);
    const root = inst.root;
    if (inst.actions.Idle) { inst.actions.Idle.play(); inst.mixer.update(0.4); }
    this.scene.add(root);
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const h = box.max.y - box.min.y;
    if (kind === 'units') {
      const head = box.min.y + h * 0.8;
      this.cam.position.set(h * 0.22, head + h * 0.02, h * 0.95);
      this.cam.lookAt(0, head - h * 0.05, 0);
    } else {
      const c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() * 0.5;
      this.cam.position.set(c.x + r * 0.9, c.y + r * 0.7, c.z + r * 1.9);
      this.cam.lookAt(c);
    }
    // painted backdrop
    const bg = document.createElement('canvas'); bg.width = bg.height = S;
    const g = bg.getContext('2d');
    ground(g, ...(THEMES[theme] || THEMES.stone));
    const old = this.r.getRenderTarget();
    const oldClear = this.r.getClearAlpha();
    this.r.setRenderTarget(this.rt);
    this.r.setClearColor(0x000000, 0);
    this.r.clear();
    this.r.render(this.scene, this.cam);
    this.r.readRenderTargetPixels(this.rt, 0, 0, S, S, this.buf);
    this.r.setRenderTarget(old);
    this.r.setClearAlpha(oldClear);
    this.scene.remove(root);
    const img = g.getImageData(0, 0, S, S);
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
      const si = ((S - 1 - y) * S + x) * 4, di = (y * S + x) * 4, a = this.buf[si + 3] / 255;
      for (let k = 0; k < 3; k++) img.data[di + k] = img.data[di + k] * (1 - a) + this.buf[si + k] * a;
    }
    g.putImageData(img, 0, 0);
    finish(g);
    const url = bg.toDataURL();
    this.urls.set(key, url);
    return url;
  }
}
