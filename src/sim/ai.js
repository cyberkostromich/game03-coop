// The Rat Plague: wave director for "Defense of the Kingdom".
//
// Waves leave the open pits on a timer (data/waves.json), scaled by player
// count and difficulty, and march on the nearest player hall, chewing
// through anything on the way. The final wave brings the Rat King.
import { RATS } from './defs.js';

const HZ = 20;

export class RatDirector {
  constructor(w, setup) {
    this.w = w;
    const W = w.D.waves;
    this.W = W;
    this.n = 0;                                  // waves sent
    this.next = W.first * HZ;
    this.kingSlain = false;
    const players = setup.players.length;
    this.scale = (1 + W.per_player_scale * (players - 1)) * (W.difficulty[w.diff] || 1);
    this.groups = [];
  }

  get total() { return this.W.waves.length; }
  get secondsToNext() { return this.n >= this.total ? -1 : Math.max(0, (this.next - this.w.tick) / HZ); }

  tick() {
    const w = this.w;
    if (this.n < this.total && w.tick >= this.next) this.sendWave();
    if (w.tick % 40 === 0) this.steer();
  }

  openPits() {
    return this.w.blds.filter(e => e.alive && e.type === 'rat_pit' && e.opensAfter <= this.n);
  }

  sendWave() {
    const w = this.w, spec = this.W.waves[this.n];
    const pits = this.openPits();
    this.n++;
    this.next = w.tick + this.W.interval * HZ;
    if (!pits.length) return;
    const raiders = Math.round(spec.raiders * this.scale), doctors = Math.round(spec.doctors * this.scale);
    const list = [];
    for (let i = 0; i < raiders; i++) list.push('rat_raider');
    for (let i = 0; i < doctors; i++) list.push('rat_plague_doctor');
    if (spec.king) list.push('rat_king');
    const group = { units: [], target: null };
    list.forEach((type, i) => {
      const pit = type === 'rat_king' ? pits[0] : pits[i % pits.length];
      const a = i * 2.399, r = pit.w / 2 + 1 + (i % 4) * 0.7;
      const p = w.grid.nearestFree(pit.x + Math.cos(a) * r, pit.y + Math.sin(a) * r, 10);
      if (!p) return;
      const u = w.spawnUnit(type, RATS, p[0], p[1]);
      u.wave = this.n;
      if (type === 'rat_king') { u.armor += 2; w.msg(-1, 'Крыса-Король выходит из подземелья!', 'alert'); }
      group.units.push(u.id);
      w.event({ k: 'fx', fx: 'burrow', x: p[0], y: p[1] });
    });
    this.groups.push(group);
    w.event({ k: 'wave', n: this.n, total: this.total, count: group.units.length });
    w.msg(-1, `Волна ${this.n} из ${this.total}: крысы лезут из провалов (${group.units.length})`, 'alert');
    this.steer(true);
  }

  // re-aim every group at the closest standing player structure
  steer(force = false) {
    const w = this.w;
    for (const g of this.groups) {
      g.units = g.units.filter(id => w.byId.get(id)?.alive);
      if (!g.units.length) continue;
      let cx = 0, cy = 0;
      for (const id of g.units) { const u = w.byId.get(id); cx += u.x; cy += u.y; }
      cx /= g.units.length; cy /= g.units.length;
      let t = null, bd = Infinity;
      for (const b of w.blds) if (b.alive && b.team === 0) { const d = (b.x - cx) ** 2 + (b.y - cy) ** 2; if (d < bd) { bd = d; t = b; } }
      if (!t) continue;
      if (!force && g.target === t.id) {
        // idle stragglers rejoin the march
        for (const id of g.units) { const u = w.byId.get(id); if (u.order.t === 'idle') this.march(u, t); }
        continue;
      }
      g.target = t.id;
      for (const id of g.units) this.march(w.byId.get(id), t);
    }
    if (this.n >= this.total && w.tick % 200 === 0) {
      
    }
    for (const g of this.groups) if (!g.king && g.units.some(id => w.byId.get(id)?.type === 'rat_king')) g.king = true;
    if (this.groups.some(g => g.king) && !w.units.some(e => e.alive && e.type === 'rat_king')) this.kingSlain = true;
  }

  march(u, t) {
    if (!u || !u.alive) return;
    const w = this.w;
    if (u.order.t === 'amove' && u.order.target) return;  // busy fighting
    const p = w.grid.nearestFree(t.x, t.y - t.h / 2 - 1.5, 10) || [t.x, t.y];
    u.orders = [];
    w.setOrder(u, { t: 'amove', x: p[0], y: p[1], fx: p[0], fy: p[1], gid: 0 });
  }
}
