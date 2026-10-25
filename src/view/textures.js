// Hand-painted terrain tiles, generated at startup with brush strokes on a
// canvas (seamless: every stroke is mirrored across the tile edges). The
// look follows WC3 Reforged ground: saturated mid-tones, painted clumps
// with lit tops and dark bases, crisp highlights, no photo noise.
import * as THREE from 'three';

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), s | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const hex = (h, a = 1) => {
  const n = parseInt(h.slice(1), 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
};
const lerpHex = (a, b, t) => {
  const x = parseInt(a.slice(1), 16), y = parseInt(b.slice(1), 16);
  const c = [16, 8, 0].map(s => Math.round(((x >> s) & 255) * (1 - t) + ((y >> s) & 255) * t));
  return '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
};

function tile(size, seed, paint) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const R = rng(seed);
  // wrap(fn) draws fn at the 9 tile offsets so strokes cross edges seamlessly
  const wrap = fn => { for (const ox of [-size, 0, size]) for (const oy of [-size, 0, size]) { g.save(); g.translate(ox, oy); fn(); g.restore(); } };
  paint(g, R, wrap, size);
  return c;
}

function blob(g, x, y, rx, ry, rot, fill) {
  g.beginPath(); g.ellipse(x, y, rx, ry, rot, 0, Math.PI * 2); g.fillStyle = fill; g.fill();
}

function base(g, size, a, b, R, wrap, n = 140) {
  g.fillStyle = a; g.fillRect(0, 0, size, size);
  for (let i = 0; i < n; i++) {
    const x = R() * size, y = R() * size, r = size * (0.05 + R() * 0.14);
    const col = lerpHex(a, b, R());
    wrap(() => blob(g, x, y, r, r * (0.5 + R() * 0.5), R() * 3, hex(col, 0.35)));
  }
}

export function grassTile(size = 512) {
  return tile(size, 11, (g, R, wrap, S) => {
    base(g, S, '#4f7a26', '#6a9a2e', R, wrap, 160);
    // darker patches for macro breakup
    for (let i = 0; i < 26; i++) {
      const x = R() * S, y = R() * S, r = S * (0.06 + R() * 0.1);
      wrap(() => blob(g, x, y, r, r * 0.7, R() * 3, hex('#3d6420', 0.35)));
    }
    // grass clumps: dark base, mid blade fan, lit tips (top-left light)
    for (let i = 0; i < 900; i++) {
      const x = R() * S, y = R() * S, h = 5 + R() * 9, n = 3 + (R() * 4 | 0);
      const lit = R();
      wrap(() => {
        for (let k = 0; k < n; k++) {
          const a = -Math.PI / 2 + (k - n / 2) * 0.28 + (R() - 0.5) * 0.3;
          g.strokeStyle = hex(lit > 0.5 ? '#86b83a' : '#5c8c28', 0.85);
          g.lineWidth = 1.6;
          g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + Math.cos(a) * h * 0.4, y + Math.sin(a) * h * 0.6, x + Math.cos(a) * h, y + Math.sin(a) * h); g.stroke();
        }
        g.fillStyle = hex('#2f4d17', 0.35); g.fillRect(x - 2, y - 0.5, 4, 1.5);
        g.fillStyle = hex('#b6dc5a', 0.6); g.fillRect(x - 0.5, y - h, 1.2, 1.2);
      });
    }
    // clover and tiny flowers
    for (let i = 0; i < 70; i++) {
      const x = R() * S, y = R() * S, c = R() > 0.75 ? '#f1e9b8' : R() > 0.5 ? '#e8d36a' : '#8fc046';
      wrap(() => { for (let k = 0; k < 3; k++) blob(g, x + Math.cos(k * 2.1) * 2.2, y + Math.sin(k * 2.1) * 2.2, 2.2, 1.8, k, hex(c, 0.9)); });
    }
  });
}

export function dirtTile(size = 512) {
  return tile(size, 23, (g, R, wrap, S) => {
    base(g, S, '#7a5a36', '#987244', R, wrap, 160);
    // packed-earth smears
    for (let i = 0; i < 120; i++) {
      const x = R() * S, y = R() * S, w = 20 + R() * 50;
      wrap(() => blob(g, x, y, w, w * 0.18, R() * 0.5 - 0.25, hex(R() > 0.5 ? '#a9824e' : '#62482a', 0.35)));
    }
    // pebbles: shadow, body, highlight
    for (let i = 0; i < 260; i++) {
      const x = R() * S, y = R() * S, r = 1.5 + R() * 4.5, rot = R() * 3;
      const body = lerpHex('#8d7a64', '#b9a68a', R());
      wrap(() => {
        blob(g, x + 1.2, y + 1.6, r, r * 0.75, rot, hex('#3e2c18', 0.55));
        blob(g, x, y, r, r * 0.75, rot, hex(body, 1));
        blob(g, x - r * 0.3, y - r * 0.3, r * 0.45, r * 0.3, rot, hex('#e8dcc0', 0.75));
      });
    }
  });
}

export function sandTile(size = 512) {
  return tile(size, 37, (g, R, wrap, S) => {
    base(g, S, '#c9ad72', '#dcc48a', R, wrap, 120);
    // ripples
    for (let i = 0; i < 90; i++) {
      const x = R() * S, y = R() * S, w = 30 + R() * 60;
      wrap(() => {
        g.strokeStyle = hex('#a98d58', 0.45); g.lineWidth = 2;
        g.beginPath(); g.moveTo(x - w / 2, y); g.quadraticCurveTo(x, y - 6, x + w / 2, y); g.stroke();
        g.strokeStyle = hex('#f2e2b0', 0.5); g.lineWidth = 1.3;
        g.beginPath(); g.moveTo(x - w / 2, y - 2); g.quadraticCurveTo(x, y - 8, x + w / 2, y - 2); g.stroke();
      });
    }
    for (let i = 0; i < 160; i++) {
      const x = R() * S, y = R() * S, r = 1 + R() * 2.5;
      wrap(() => { blob(g, x + 0.8, y + 1, r, r * 0.7, 0, hex('#7c6237', 0.45)); blob(g, x, y, r, r * 0.7, 0, hex('#e9d9ad', 0.9)); });
    }
  });
}

export function rockTile(size = 512) {
  return tile(size, 51, (g, R, wrap, S) => {
    base(g, S, '#6f6b63', '#8b867b', R, wrap, 100);
    // slabs: plates with lit top edge and dark crack
    for (let i = 0; i < 70; i++) {
      const x = R() * S, y = R() * S, w = 30 + R() * 60, h = 18 + R() * 30, rot = (R() - 0.5) * 0.6;
      const c = lerpHex('#77726a', '#a19b8e', R());
      wrap(() => {
        g.save(); g.translate(x, y); g.rotate(rot);
        g.fillStyle = hex('#3c3934', 0.8); roundRect(g, -w / 2 + 2, -h / 2 + 3, w, h, 6); g.fill();
        g.fillStyle = hex(c, 1); roundRect(g, -w / 2, -h / 2, w, h, 6); g.fill();
        g.fillStyle = hex('#c9c3b4', 0.55); roundRect(g, -w / 2 + 2, -h / 2 + 1, w - 4, 4, 2); g.fill();
        g.restore();
      });
    }
    for (let i = 0; i < 90; i++) {
      const x = R() * S, y = R() * S;
      wrap(() => { g.strokeStyle = hex('#34312c', 0.6); g.lineWidth = 1.2; g.beginPath(); g.moveTo(x, y); for (let k = 0; k < 4; k++) g.lineTo(x + (R() - 0.5) * 30, y + (R() - 0.5) * 30); g.stroke(); });
    }
    // moss tufts in the crevices
    for (let i = 0; i < 60; i++) {
      const x = R() * S, y = R() * S, r = 3 + R() * 6;
      wrap(() => blob(g, x, y, r, r * 0.6, R() * 3, hex('#5c7a2c', 0.55)));
    }
  });
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath();
  g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}

export function canvasTexture(canvas, renderer, srgb = true) {
  const t = new THREE.CanvasTexture(canvas);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.needsUpdate = true;
  return t;
}

// soft radial blob used for selection glows, blob shadows and particles
export function radialTexture(size = 128, stops = [[0, 'rgba(255,255,255,1)'], [1, 'rgba(255,255,255,0)']]) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  for (const [o, col] of stops) gr.addColorStop(o, col);
  g.fillStyle = gr; g.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// WC3 selection ring: bright rim with soft inner falloff
export function ringTexture(size = 128) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const m = size / 2;
  const gr = g.createRadialGradient(m, m, m * 0.62, m, m, m * 0.98);
  gr.addColorStop(0, 'rgba(255,255,255,0)');
  gr.addColorStop(0.55, 'rgba(255,255,255,0.35)');
  gr.addColorStop(0.8, 'rgba(255,255,255,1)');
  gr.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = gr; g.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
