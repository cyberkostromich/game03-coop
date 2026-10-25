// Pathing grid (1 m cells) with flow-field navigation.
//
// Static blockers (water, cliffs) come from the map mask; trees, buildings
// and mines stamp reference counts so cutting a tree or razing a hall
// reopens its cells. Group orders share one Dijkstra integration field per
// goal, so a 60-unit move costs one search instead of sixty.

export const CELL = 1;

export class Grid {
  constructor(size, maskRes, mask, heights, hmin, hmax) {
    this.size = size;                       // metres, map spans [-size/2, size/2]
    this.half = size / 2;
    this.n = Math.round(size / CELL);
    const n = this.n;
    this.terrain = new Uint8Array(n * n);   // 1 = walkable ground
    this.block = new Uint16Array(n * n);    // dynamic blocker refcount
    this.owner = new Int32Array(n * n).fill(-1); // entity id occupying the cell (buildings, mines)
    this.version = 1;
    this.closeV = 1;                        // bumps only when cells get blocked
    this.openV = 1;
    this.maskRes = maskRes; this.mask = mask;
    this.heights = heights; this.hmin = hmin; this.hmax = hmax;
    for (let cy = 0; cy < n; cy++) for (let cx = 0; cx < n; cx++) {
      const x = -this.half + (cx + 0.5) * CELL, y = -this.half + (cy + 0.5) * CELL;
      this.terrain[cy * n + cx] = this.maskAt(x, y) ? 1 : 0;
    }
    this.fields = new Map();                // LRU of integration fields
    this.heap = new MinHeap(n * n * 2);
  }

  maskAt(x, y) {
    const r = this.maskRes - 1;
    const c = Math.round((x + this.half) / this.size * r);
    const w = Math.round((this.half - y) / this.size * r);
    if (c < 0 || w < 0 || c > r || w > r) return 0;
    return this.mask[w * this.maskRes + c];
  }

  // bilinear terrain height in metres (north-up rows)
  heightAt(x, y) {
    const r = this.maskRes - 1;
    const fx = Math.min(r, Math.max(0, (x + this.half) / this.size * r));
    const fy = Math.min(r, Math.max(0, (this.half - y) / this.size * r));
    const x0 = Math.floor(fx), y0 = Math.floor(fy), x1 = Math.min(r, x0 + 1), y1 = Math.min(r, y0 + 1);
    const tx = fx - x0, ty = fy - y0, R = this.maskRes, H = this.heights;
    const a = H[y0 * R + x0] * (1 - tx) + H[y0 * R + x1] * tx;
    const b = H[y1 * R + x0] * (1 - tx) + H[y1 * R + x1] * tx;
    return this.hmin + (a * (1 - ty) + b * ty) / 65535 * (this.hmax - this.hmin);
  }

  // re-open forest floor under trees: the authored mask paints forests solid,
  // the trees themselves become the blockers
  openUnderTrees(trees, radius) {
    const n = this.n;
    for (const t of trees) {
      const r = radius + 1.5;
      this.forCells(t.x, t.y, r, (i, x, y) => {
        if (this.heightAt(x, y) > 0.35) this.terrain[i] = 1;
      });
    }
  }

  cx(x) { return Math.floor((x + this.half) / CELL); }
  cy(y) { return Math.floor((y + this.half) / CELL); }
  idx(x, y) {
    const cx = this.cx(x), cy = this.cy(y);
    if (cx < 0 || cy < 0 || cx >= this.n || cy >= this.n) return -1;
    return cy * this.n + cx;
  }
  centre(i) { return [-this.half + (i % this.n + 0.5) * CELL, -this.half + (Math.floor(i / this.n) + 0.5) * CELL]; }
  free(i) { return i >= 0 && this.terrain[i] === 1 && this.block[i] === 0; }
  freeAt(x, y) { return this.free(this.idx(x, y)); }

  forCells(x, y, r, fn) {
    const n = this.n;
    const x0 = Math.max(0, this.cx(x - r)), x1 = Math.min(n - 1, this.cx(x + r));
    const y0 = Math.max(0, this.cy(y - r)), y1 = Math.min(n - 1, this.cy(y + r));
    for (let cy = y0; cy <= y1; cy++) for (let cx = x0; cx <= x1; cx++) {
      const px = -this.half + (cx + 0.5) * CELL, py = -this.half + (cy + 0.5) * CELL;
      if ((px - x) ** 2 + (py - y) ** 2 <= r * r) fn(cy * n + cx, px, py);
    }
  }

  rectCells(x, y, w, h) {
    const out = [];
    const x0 = this.cx(x - w / 2 + 0.01), x1 = this.cx(x + w / 2 - 0.01);
    const y0 = this.cy(y - h / 2 + 0.01), y1 = this.cy(y + h / 2 - 0.01);
    for (let cy = y0; cy <= y1; cy++) for (let cx = x0; cx <= x1; cx++)
      if (cx >= 0 && cy >= 0 && cx < this.n && cy < this.n) out.push(cy * this.n + cx);
    return out;
  }

  stamp(cells, d, id = -1) {
    if (d > 0) this.closeV++; else this.openV++;
    for (const i of cells) {
      this.block[i] += d;
      if (d > 0 && id >= 0) this.owner[i] = id;
      if (d < 0 && this.block[i] === 0) this.owner[i] = -1;
    }
    this.version++;
  }

  // can a building of size w x h be placed here (all cells open ground)?
  canPlace(x, y, w, h) {
    const cells = this.rectCells(x, y, w, h);
    if (cells.length < Math.round(w) * Math.round(h) * 0.9) return false;
    return cells.every(i => this.free(i) && this.heightAt(...this.centre(i)) > 0.2);
  }

  nearestFree(x, y, maxR = 12) {
    const i0 = this.idx(x, y);
    if (this.free(i0)) return [x, y];
    const cx0 = this.cx(x), cy0 = this.cy(y), n = this.n;
    for (let r = 1; r <= maxR; r++) {
      let best = -1, bd = 1e9;
      for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
        const cx = cx0 + dx, cy = cy0 + dy;
        if (cx < 0 || cy < 0 || cx >= n || cy >= n) continue;
        const i = cy * n + cx;
        if (!this.free(i)) continue;
        const [px, py] = this.centre(i);
        const d = (px - x) ** 2 + (py - y) ** 2;
        if (d < bd) { bd = d; best = i; }
      }
      if (best >= 0) return this.centre(best);
    }
    return null;
  }

  // supercover line-of-sight between two points over walkable cells,
  // inflated by `pad` metres sideways so units don't clip corners
  los(x0, y0, x1, y1, pad = 0.3) {
    const dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy);
    if (L < 1e-4) return true;
    const steps = Math.ceil(L / 0.35);
    const nx = -dy / L * pad, ny = dx / L * pad;
    for (let s = 1; s <= steps; s++) {
      const t = s / steps, x = x0 + dx * t, y = y0 + dy * t;
      if (!this.freeAt(x, y) || !this.freeAt(x + nx, y + ny) || !this.freeAt(x - nx, y - ny)) return false;
    }
    return true;
  }

  walkable() {
    if (this._wv === this.version) return this._w;
    const N = this.n * this.n;
    if (!this._w) this._w = new Uint8Array(N);
    const W = this._w, T = this.terrain, B = this.block;
    for (let i = 0; i < N; i++) W[i] = T[i] && !B[i] ? 1 : 0;
    this._wv = this.version;
    return W;
  }

  // A field stays usable when cells only opened up (felled trees) for a few
  // seconds: paths are still valid, merely not the shortest.
  fresh(f) {
    if (f.version === this.version) return true;
    return f.closeV === this.closeV && (this.tick || 0) - f.made < 200;
  }

  // Integration field from a set of goal cells (Dijkstra, octile costs, no
  // corner cutting). Cached by key until the grid changes.
  field(key, goals) {
    const hit = this.fields.get(key);
    if (hit && this.fresh(hit)) { hit.used = this.tick || 0; return hit; }
    const n = this.n, N = n * n;
    const cost = hit && hit.cost.length === N ? hit.cost : new Float32Array(N);
    cost.fill(Infinity);
    const heap = this.heap; heap.clear();
    for (const g of goals) if (g >= 0 && g < N) { cost[g] = 0; heap.push(g, 0); }
    const W = this.walkable();
    const D = Math.SQRT2;
    while (heap.size) {
      const i = heap.popKey(), c = heap.lastV;
      if (c > cost[i]) continue;
      const x = i % n;
      const fl = x > 0 && W[i - 1], fr = x < n - 1 && W[i + 1];
      const fd = i >= n && W[i - n], fu = i < N - n && W[i + n];
      let j, v;
      if (fl && (v = c + 1) < cost[j = i - 1]) { cost[j] = v; heap.push(j, v); }
      if (fr && (v = c + 1) < cost[j = i + 1]) { cost[j] = v; heap.push(j, v); }
      if (fd && (v = c + 1) < cost[j = i - n]) { cost[j] = v; heap.push(j, v); }
      if (fu && (v = c + 1) < cost[j = i + n]) { cost[j] = v; heap.push(j, v); }
      if (fl && fd && W[j = i - 1 - n] && (v = c + D) < cost[j]) { cost[j] = v; heap.push(j, v); }
      if (fr && fd && W[j = i + 1 - n] && (v = c + D) < cost[j]) { cost[j] = v; heap.push(j, v); }
      if (fl && fu && W[j = i - 1 + n] && (v = c + D) < cost[j]) { cost[j] = v; heap.push(j, v); }
      if (fr && fu && W[j = i + 1 + n] && (v = c + D) < cost[j]) { cost[j] = v; heap.push(j, v); }
    }
    const f = { cost, version: this.version, closeV: this.closeV, openV: this.openV, made: this.tick || 0, used: this.tick || 0, goals };
    this.fields.set(key, f);
    if (this.fields.size > 48) {                // evict least recently used
      let oldK = null, oldU = Infinity;
      for (const [k, v] of this.fields) if (v.used < oldU && k !== key) { oldU = v.used; oldK = k; }
      this.fields.delete(oldK);
    }
    return f;
  }

  // Next steering point for a unit following a field: walk the descent chain
  // a few cells ahead and take the furthest cell still in straight sight.
  steer(f, x, y, pad) {
    const n = this.n, cost = f.cost;
    let i = this.idx(x, y);
    if (i < 0) return null;
    if (!isFinite(cost[i])) {                    // standing on a blocked cell: step to the best neighbour
      let best = -1, bc = Infinity;
      for (const j of this.neigh(i)) if (cost[j] < bc) { bc = cost[j]; best = j; }
      return best >= 0 ? this.centre(best) : null;
    }
    let target = null;
    for (let k = 0; k < 7; k++) {
      if (cost[i] === 0) break;
      let best = -1, bc = cost[i];
      for (const j of this.neigh(i)) if (cost[j] < bc) { bc = cost[j]; best = j; }
      if (best < 0) break;
      i = best;
      const [px, py] = this.centre(i);
      if (k < 1 || this.los(x, y, px, py, pad)) target = [px, py]; else break;
    }
    return target;
  }

  neigh(i) {
    const n = this.n, x = i % n, y = (i - x) / n, out = [];
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (!dx && !dy) continue;
      const cx = x + dx, cy = y + dy;
      if (cx < 0 || cy < 0 || cx >= n || cy >= n) continue;
      if (dx && dy && (!this.free(y * n + cx) || !this.free(cy * n + x))) continue;
      out.push(cy * n + cx);
    }
    return out;
  }
}

class MinHeap {
  constructor(cap) { this.k = new Int32Array(cap); this.v = new Float32Array(cap); this.size = 0; }
  clear() { this.size = 0; }
  push(k, v) {
    if (this.size >= this.k.length) {           // grow (rare: duplicates from lazy deletion)
      const k2 = new Int32Array(this.k.length * 2); k2.set(this.k); this.k = k2;
      const v2 = new Float32Array(this.v.length * 2); v2.set(this.v); this.v = v2;
    }
    let i = this.size++;
    const K = this.k, V = this.v;
    while (i > 0) {
      const p = (i - 1) >> 1;
      if (V[p] <= v) break;
      K[i] = K[p]; V[i] = V[p]; i = p;
    }
    K[i] = k; V[i] = v;
  }
  popKey() {
    const K = this.k, V = this.v;
    const rk = K[0]; this.lastV = V[0];
    this.sift();
    return rk;
  }
  sift() {
    const K = this.k, V = this.v;
    const k = K[--this.size], v = V[this.size];
    let i = 0;
    for (;;) {
      let c = 2 * i + 1;
      if (c >= this.size) break;
      if (c + 1 < this.size && V[c + 1] < V[c]) c++;
      if (V[c] >= v) break;
      K[i] = K[c]; V[i] = V[c]; i = c;
    }
    K[i] = k; V[i] = v;
  }
  pop() {
    const K = this.k, V = this.v;
    const rk = K[0], rv = V[0];
    const k = K[--this.size], v = V[this.size];
    let i = 0;
    for (;;) {
      let c = 2 * i + 1;
      if (c >= this.size) break;
      if (c + 1 < this.size && V[c + 1] < V[c]) c++;
      if (V[c] >= v) break;
      K[i] = K[c]; V[i] = V[c]; i = c;
    }
    K[i] = k; V[i] = v;
    return [rk, rv];
  }
}
