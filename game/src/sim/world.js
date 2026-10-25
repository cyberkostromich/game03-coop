// Deterministic RTS simulation, fixed 20 Hz tick.
//
// The world knows nothing about rendering: it consumes serialisable
// commands, advances entities and emits events that the view turns into
// animation and effects. Every random roll goes through the seeded Rng.
import { Grid } from './grid.js';
import { Rng } from './rng.js';
import { buildDefs, armorFactor, lvl, RATS, NEUTRAL } from './defs.js';
import { Abilities } from './abilities.js';
import { RatDirector } from './ai.js';

export const HZ = 20, DT = 1 / HZ;
export { RATS, NEUTRAL };

const TEAM_OF = o => (o === RATS ? 1 : o === NEUTRAL ? 2 : 0);
const hostile = (a, b) => a !== b && !(a === 1 && b === 2) && !(a === 2 && b === 1);
const HASH = 4;                                    // spatial hash bucket, metres
const DAY = 480;                                   // full day/night cycle, seconds

export class World {
  constructor(D, setup) {
    this.D = D;
    this.defs = buildDefs(D);
    this.rng = new Rng(setup.seed || 12345);
    this.tick = 0;
    this.ents = [];
    this.units = [];                               // views into ents, kept in sync by add/cleanup
    this.blds = [];
    this.byId = new Map();
    this.nextId = 1;
    this.events = [];
    this.cmds = [];
    this.diff = setup.difficulty || 'normal';
    this.result = null;                            // 'victory' | 'defeat'
    const M = D.map;
    this.grid = new Grid(M.size, M.resolution, D.mapBin.path, D.mapBin.height, M.height_min, M.height_max);
    this.grid.openUnderTrees(M.trees, D.economy.trees.block_radius);
    this.hashN = Math.ceil(M.size / HASH);
    this.hash = Array.from({ length: this.hashN * this.hashN }, () => []);
    this.players = setup.players.map((p, i) => ({
      id: i, name: p.name, faction: p.faction, color: p.color, ai: !!p.ai,
      gold: D.economy.start.gold, wood: D.economy.start.wood, food: D.economy.start.food,
      popUsed: 0, popCap: 0, tier: 1, mined: 0, heroes: [], deadHeroes: [], alive: true, stats: { kills: 0, lost: 0, gathered: 0 },
    }));
    this.vis = new Uint8Array(this.grid.n * this.grid.n);
    this.explored = new Uint8Array(this.grid.n * this.grid.n);
    this.visVersion = 0;
    this.abilities = new Abilities(this);
    this.zones = [];                               // ground effects (rain, roots, heal circles)
    this.projectiles = [];
    this.crusade = { ready: false, used: false, until: 0 };
    this.setupMap(setup);
    this.director = new RatDirector(this, setup);
    this.updatePop();
    this.updateVision();
  }

  // ------------------------------------------------------------------ setup
  setupMap(setup) {
    const M = this.D.map, E = this.D.economy;
    for (const t of M.trees) {
      const e = this.add({ kind: 'tree', type: t.type, owner: NEUTRAL, x: t.x, y: t.y, r: 0.6, hp: 1, maxHp: 1,
                           wood: E.trees.wood, scale: t.s, rot: t.r });
      e.cells = [];
      this.grid.forCells(t.x, t.y, E.trees.block_radius, i => e.cells.push(i));
      this.grid.stamp(e.cells, 1, e.id);
    }
    for (const g of M.gold_mines) {
      const m = this.placeBuilding('gold_mine', NEUTRAL, g.x, g.y, true);
      m.gold = Math.round(E.gold_mine_amount * (g.rich ? 1.6 : 1));
      m.inside = 0; m.invuln = true;
    }
    const mill = M.shrines.find(s => s.id === 'mill');
    if (mill) { const s = this.placeBuilding('mill', NEUTRAL, mill.x, mill.y + 1, true); s.invuln = true; }
    for (const [i, s] of M.fishing_shoals.entries())
      this.add({ kind: 'shoal', type: 'shoal', owner: NEUTRAL, x: s.x, y: s.y, r: 1.5, hp: 1, maxHp: 1, food: 1600, idx: i });
    for (const p of M.rat_pits) {
      const b = this.placeBuilding('rat_pit', RATS, p.x, p.y, true);
      b.opensAfter = p.opens_after_wave;
    }
    const C = this.D.creeps;
    for (const c of M.camps) {
      const list = C.camps[c.level] || [];
      let k = 0;
      for (const [type, cnt] of list) for (let j = 0; j < cnt; j++, k++) {
        const a = k * 2.399, rr = 1.2 + 0.5 * k;
        const pos = this.grid.nearestFree(c.x + Math.cos(a) * rr, c.y + Math.sin(a) * rr) || [c.x, c.y];
        const u = this.spawnUnit(type, NEUTRAL, pos[0], pos[1]);
        const s = C.scale[c.level] || 1;
        u.maxHp = u.hp = Math.round(u.hp * s);
        u.camp = { x: c.x, y: c.y, level: c.level };
        u.facing = Math.atan2(c.y - u.y, c.x - u.x) + Math.PI;
      }
    }
    for (const p of this.players) {
      const st = M.starts[p.id];
      const F = this.D.factions[p.faction];
      const hall = this.placeBuilding(F.hall, p.id, st.x, st.y, true);
      // workers line up between hall and nearest mine
      const mine = this.nearest(st.x, st.y, e => e.type === 'gold_mine');
      const ang = mine ? Math.atan2(mine.y - st.y, mine.x - st.x) : 0;
      for (let k = 0; k < E.start.workers; k++) {
        const a = ang + (k - 2) * 0.42, d = 4.6;
        const pos = this.grid.nearestFree(st.x + Math.cos(a) * d, st.y + Math.sin(a) * d) || [st.x, st.y - 4];
        const w = this.spawnUnit(F.worker, p.id, pos[0], pos[1]);
        w.facing = ang;
      }
      p.home = { x: st.x, y: st.y };
      hall.rally = null;
    }
  }

  add(e) {
    e.id = this.nextId++;
    e.alive = true;
    e.team = TEAM_OF(e.owner);
    e.born = this.tick;
    this.ents.push(e);
    this.byId.set(e.id, e);
    if (e.kind === 'unit') this.units.push(e);
    else if (e.kind === 'building') this.blds.push(e);
    return e;
  }

  unitDef(type) { return this.defs.units[type]; }

  spawnUnit(type, owner, x, y, opts = {}) {
    const d = this.defs.units[type];
    if (!d) throw new Error('unknown unit ' + type);
    const e = this.add({
      kind: 'unit', type, def: d, owner, x, y, r: d.r, facing: opts.facing ?? -Math.PI / 2,
      hp: d.hp, maxHp: d.hp, mana: d.mana, maxMana: d.mana, armor: d.armor, cd: 0, swing: 0,
      order: { t: 'idle' }, orders: [], vx: 0, vy: 0, anim: 'Idle', animT: this.tick, animDur: 1,
      carry: { res: null, amt: 0 }, buffs: [], mods: null, lastCombat: -1e9, hidden: false, prog: { d: Infinity, t: 0 },
    });
    if (d.hero) this.abilities.initHero(e);
    this.abilities.refreshMods(e);
    this.event({ k: 'spawn', id: e.id });
    return e;
  }

  placeBuilding(type, owner, x, y, done = false) {
    const d = this.defs.buildings[type];
    const e = this.add({
      kind: 'building', type, def: d, owner, x, y, w: d.w, h: d.h, r: Math.max(d.w, d.h) / 2,
      hp: done ? d.hp : Math.max(1, Math.round(d.hp * 0.1)), maxHp: d.hp, armor: d.armor,
      built: done ? 1 : 0, queue: [], rally: null, cd: 0, buffs: [], facing: -Math.PI / 2, tier: 1,
    });
    e.cells = this.grid.rectCells(x, y, d.w, d.h);
    this.grid.stamp(e.cells, 1, e.id);
    // shove units out of the new footprint
    for (const u of this.units) if (u.alive && !u.hidden && this.inRect(u.x, u.y, e, u.r)) this.unstick(u);
    this.event({ k: 'spawn', id: e.id });
    return e;
  }

  inRect(x, y, b, pad = 0) {
    return Math.abs(x - b.x) < b.w / 2 + pad && Math.abs(y - b.y) < b.h / 2 + pad;
  }

  unstick(u) {
    const p = this.grid.nearestFree(u.x, u.y, 16);
    if (p) { u.x = p[0]; u.y = p[1]; }
  }

  event(ev) { ev.tick = this.tick; this.events.push(ev); }
  msg(p, text, kind = 'info') { this.event({ k: 'msg', p, text, kind }); }

  // --------------------------------------------------------------- queries
  get time() { return this.tick * DT; }
  get dayPhase() { return (this.time % DAY) / DAY; }      // 0 dawn .. 0.5 dusk .. 1
  get isNight() { const p = this.dayPhase; return p > 0.55 && p < 0.95; }

  rebuildHash() {
    for (const b of this.hash) if (b.length) b.length = 0;
    const N = this.hashN, half = this.grid.half;
    for (const e of this.units) {
      if (!e.alive || e.hidden) continue;
      const cx = Math.min(N - 1, Math.max(0, Math.floor((e.x + half) / HASH)));
      const cy = Math.min(N - 1, Math.max(0, Math.floor((e.y + half) / HASH)));
      this.hash[cy * N + cx].push(e);
    }
  }

  query(x, y, r, fn) {
    const N = this.hashN, half = this.grid.half;
    const x0 = Math.max(0, Math.floor((x - r + half) / HASH)), x1 = Math.min(N - 1, Math.floor((x + r + half) / HASH));
    const y0 = Math.max(0, Math.floor((y - r + half) / HASH)), y1 = Math.min(N - 1, Math.floor((y + r + half) / HASH));
    const r2 = r * r;
    for (let cy = y0; cy <= y1; cy++) for (let cx = x0; cx <= x1; cx++)
      for (const e of this.hash[cy * N + cx]) if ((e.x - x) ** 2 + (e.y - y) ** 2 <= r2) fn(e);
  }

  nearest(x, y, pred, maxD = Infinity) {
    let best = null, bd = maxD * maxD;
    for (const e of this.ents) {
      if (!e.alive || !pred(e)) continue;
      const d = (e.x - x) ** 2 + (e.y - y) ** 2;
      if (d < bd) { bd = d; best = e; }
    }
    return best;
  }

  // edge-to-edge distance
  gap(a, b) {
    if (b.kind === 'building') {
      const dx = Math.max(0, Math.abs(a.x - b.x) - b.w / 2), dy = Math.max(0, Math.abs(a.y - b.y) - b.h / 2);
      return Math.hypot(dx, dy) - a.r;
    }
    return Math.hypot(a.x - b.x, a.y - b.y) - a.r - b.r;
  }

  isHostile(a, b) { return hostile(a.team, b.team); }

  visibleTo(team, e) {
    if (team !== 0) return !e.mods?.invisible;
    if (e.team === 0) return true;
    const i = this.grid.idx(e.x, e.y);
    if (i < 0 || !this.vis[i]) return false;
    if (e.mods?.invisible && !this.detected(e)) return false;
    return true;
  }

  detected(e) {
    // dog trackers and revealed areas expose invisible units
    for (const z of this.zones) if (z.kind === 'reveal' && Math.hypot(e.x - z.x, e.y - z.y) < z.r) return true;
    let found = false;
    this.query(e.x, e.y, 10, u => { if (!found && u.def.detects && this.isHostile(u, e)) found = true; });
    return found;
  }

  canTarget(a, t) {
    if (!t || !t.alive || t.hidden || t.invuln) return false;
    if (t.kind !== 'unit' && t.kind !== 'building') return false;
    if (!this.isHostile(a, t)) return false;
    if (t.kind === 'building' && t.built === 0 && t.owner === NEUTRAL) return false;
    if (t.mods?.invisible) {
      if (a.team !== 0) return false;
      if (!this.detected(t)) return false;
    }
    if (a.team === 0 && t.team !== 0 && !this.visibleTo(0, t) && t.kind === 'unit') return false;
    return true;
  }

  // --------------------------------------------------------------- commands
  issue(cmd) { this.cmds.push(cmd); }

  owns(p, e) { return e && e.alive && (e.owner === p || (this.sharedControl && e.team === 0 && this.players[e.owner])); }

  applyCommand(c) {
    const P = this.players[c.p];
    if (!P || !P.alive) return;
    const units = (c.ids || []).map(id => this.byId.get(id)).filter(e => this.owns(c.p, e) && e.kind === 'unit');
    switch (c.t) {
      case 'smart': return this.cmdSmart(units, c);
      case 'move': case 'amove': case 'patrol': return this.groupMove(units, c.t, c.x, c.y, c.queue);
      case 'attack': {
        const t = this.byId.get(c.target);
        for (const u of units) this.order(u, { t: 'attack', target: c.target, forced: true }, c.queue);
        if (t) this.event({ k: 'ack', p: c.p, id: t.id, kind: 'attack' });
        return;
      }
      case 'stop': for (const u of units) { u.orders = []; this.setOrder(u, { t: 'idle' }); } return;
      case 'hold': for (const u of units) { u.orders = []; this.setOrder(u, { t: 'hold' }); } return;
      case 'gather': for (const u of units) if (u.def.gatherer) this.order(u, this.gatherOrder(u, this.byId.get(c.target)), c.queue); return;
      case 'return': for (const u of units) if (u.carry.amt > 0) this.order(u, { t: 'gather', target: u.lastRes || 0, phase: 'return' }, c.queue); return;
      case 'build': return this.cmdBuild(P, units, c);
      case 'train': return this.cmdTrain(P, c);
      case 'upgrade': return this.cmdUpgrade(P, c);
      case 'cancel': return this.cmdCancel(P, c);
      case 'rally': {
        const b = this.byId.get(c.building);
        if (this.owns(c.p, b) && b.kind === 'building') b.rally = { x: c.x, y: c.y, target: c.target || 0 };
        return;
      }
      case 'cast': {
        const u = this.byId.get(c.id);
        if (this.owns(c.p, u)) this.abilities.order(u, c.key, c, c.queue);
        return;
      }
      case 'learn': {
        const u = this.byId.get(c.id);
        if (this.owns(c.p, u)) this.abilities.learn(u, c.key);
        return;
      }
      case 'revive': return this.cmdRevive(P, c);
      case 'transfer': return this.cmdTransfer(P, c);
      case 'crusade': return this.cmdCrusade(P);
      case 'cheat': if (c.gold) { P.gold += c.gold; P.wood += c.wood || 0; P.food += c.food || 0; } return;
    }
  }

  cmdSmart(units, c) {
    const t = c.target ? this.byId.get(c.target) : null;
    if (t && t.alive) {
      const groupTarget = [];
      for (const u of units) {
        if (u.def.gatherer && (t.type === 'gold_mine' || t.kind === 'tree' || t.kind === 'shoal')) this.order(u, this.gatherOrder(u, t), c.queue);
        else if (u.def.gatherer && t.kind === 'building' && t.owner === u.owner && t.built < 1) this.order(u, { t: 'construct', target: t.id }, c.queue);
        else if (u.def.gatherer && t.kind === 'building' && t.owner === u.owner && t.def.dropoff.length && u.carry.amt > 0)
          this.order(u, { t: 'gather', target: u.lastRes || 0, phase: 'return', drop: t.id }, c.queue);
        else if (this.isHostile(u, t) && (t.kind === 'unit' || t.kind === 'building')) this.order(u, { t: 'attack', target: t.id, forced: true }, c.queue);
        else if (t.kind === 'unit' && t !== u) this.order(u, { t: 'follow', target: t.id }, c.queue);
        else groupTarget.push(u);
      }
      if (groupTarget.length) this.groupMove(groupTarget, 'move', c.x, c.y, c.queue);
      this.event({ k: 'ack', p: c.p, id: t.id, kind: this.isHostile({ team: 0 }, t) ? 'attack' : 'move' });
      return;
    }
    this.groupMove(units, 'move', c.x, c.y, c.queue);
  }

  // formation slots around the click point, keeping the group compact
  groupMove(units, kind, x, y, queue) {
    if (!units.length) return;
    const snap = this.grid.nearestFree(x, y, 20) || [x, y];
    [x, y] = snap;
    const gid = this.nextId++;
    const n = units.length;
    let cx = 0, cy = 0;
    for (const u of units) { cx += u.x; cy += u.y; }
    cx /= n; cy /= n;
    const spread = Math.max(...units.map(u => Math.hypot(u.x - cx, u.y - cy)));
    const keepShape = spread < 6 && n > 1;
    const ang = Math.atan2(y - cy, x - cx);
    const slots = [];
    if (keepShape) {
      for (const u of units) slots.push([x + u.x - cx, y + u.y - cy]);
    } else {
      const cols = Math.ceil(Math.sqrt(n * 1.6)), sp = 1.25;
      const fx = Math.cos(ang), fy = Math.sin(ang), rx = -fy, ry = fx;
      for (let k = 0; k < n; k++) {
        const row = Math.floor(k / cols), col = k % cols, rowN = Math.min(cols, n - row * cols);
        const a = (col - (rowN - 1) / 2) * sp, b = -row * sp;
        slots.push([x + rx * a + fx * b, y + ry * a + fy * b]);
      }
    }
    // greedy assignment: furthest-forward units take the front slots
    const order = units.map((u, i) => i);
    const used = new Array(n).fill(false);
    for (const i of order) {
      const u = units[i];
      let best = -1, bd = Infinity;
      for (let s = 0; s < n; s++) if (!used[s]) {
        const d = (slots[s][0] - u.x) ** 2 + (slots[s][1] - u.y) ** 2;
        if (d < bd) { bd = d; best = s; }
      }
      used[best] = true;
      let [sx, sy] = slots[best];
      if (!this.grid.freeAt(sx, sy)) [sx, sy] = this.grid.nearestFree(sx, sy, 6) || [x, y];
      const o = { t: kind, x: sx, y: sy, fx: x, fy: y, gid };
      if (kind === 'patrol') { o.ax = u.x; o.ay = u.y; }
      this.order(u, o, queue);
    }
    this.event({ k: 'ackpt', x, y, kind });
  }

  order(u, o, queue) {
    if (!o) return;
    if (queue && u.order.t !== 'idle' && u.order.t !== 'hold') { if (u.orders.length < 16) u.orders.push(o); return; }
    u.orders = [];
    this.setOrder(u, o);
  }

  setOrder(u, o) {
    if (u.swing > 0 && o.t !== 'attack') { u.swing = 0; }
    if (u.hidden && u.inMine) this.finishMining(u);   // ordered out of the mine: leave with the load
    if (u.order.t === 'construct') this.anim(u, 'Idle');
    u.order = o;
    u.wp = null; u.wpT = 0;
    u.prog = { d: Infinity, t: this.tick };
    if (o.t === 'idle' || o.t === 'hold') { u.home = { x: u.x, y: u.y }; }
  }

  nextOrder(u) {
    const o = u.orders.shift();
    this.setOrder(u, o || { t: 'idle' });
    if (!o) { u.vx = u.vy = 0; }
  }

  // ------------------------------------------------------------- economy cmds
  canAfford(P, cost, n = 1) {
    return P.gold >= (cost.gold || 0) * n && P.wood >= (cost.wood || 0) * n && P.food >= (cost.food || 0) * n;
  }
  pay(P, cost, s = 1) { P.gold -= (cost.gold || 0) * s; P.wood -= (cost.wood || 0) * s; P.food -= (cost.food || 0) * s; }

  missing(P, cost) {
    if (P.gold < (cost.gold || 0)) return 'Недостаточно золота';
    if (P.wood < (cost.wood || 0)) return 'Недостаточно дерева';
    if (P.food < (cost.food || 0)) return 'Недостаточно еды';
    return null;
  }

  cmdBuild(P, units, c) {
    const d = this.defs.buildings[c.type];
    const u = units.find(w => w.def.gatherer);
    if (!d || !u) return;
    if (d.faction !== P.faction) return;
    if (!this.grid.canPlace(c.x, c.y, d.w, d.h)) { this.msg(P.id, 'Здесь нельзя строить', 'error'); return; }
    const miss = this.missing(P, d.cost);
    if (miss) { this.msg(P.id, miss, 'error'); return; }
    this.pay(P, d.cost);
    this.order(u, { t: 'build', type: c.type, x: c.x, y: c.y, paid: true }, c.queue);
  }

  queuedPop(P) {
    let n = 0;
    for (const e of this.blds) if (e.owner === P.id && e.alive)
      for (const q of e.queue) if (q.unit) n += this.defs.units[q.unit].pop;
    return n;
  }

  cmdTrain(P, c) {
    const b = this.byId.get(c.building);
    if (!this.owns(P.id, b) || b.kind !== 'building' || b.built < 1) return;
    if (!b.def.produces.includes(c.unit)) return;
    if (b.queue.length >= 5) { this.msg(P.id, 'Очередь заполнена', 'error'); return; }
    const d = this.defs.units[c.unit];
    if (d.tier > P.tier) { this.msg(P.id, 'Нужна ратуша уровня ' + d.tier, 'error'); return; }
    if (d.hero) {
      const have = P.heroes.length + P.deadHeroes.length + this.blds.filter(e => e.alive && e.owner === P.id && e.queue.some(q => q.unit && this.defs.units[q.unit].hero)).length;
      if (P.heroes.some(id => this.byId.get(id)?.type === c.unit) || P.deadHeroes.some(h => h.type === c.unit)) { this.msg(P.id, 'Этот герой уже на службе', 'error'); return; }
      if (b.queue.some(q => q.unit === c.unit)) return;
      if (have >= this.D.economy.heroes.max_heroes) { this.msg(P.id, 'Не больше трёх героев', 'error'); return; }
    }
    if (P.popUsed + this.queuedPop(P) + d.pop > Math.min(P.popCap, this.D.economy.pop_cap)) {
      this.msg(P.id, P.popCap >= this.D.economy.pop_cap ? 'Достигнут предел населения' : 'Нужно больше ферм', 'error'); return;
    }
    const miss = this.missing(P, d.cost);
    if (miss) { this.msg(P.id, miss, 'error'); return; }
    this.pay(P, d.cost);
    b.queue.push({ unit: c.unit, t: 0, time: d.buildTime });
  }

  cmdUpgrade(P, c) {
    const b = this.byId.get(c.building);
    if (!this.owns(P.id, b) || b.built < 1) return;
    const up = b.def.upgrades.find(u => u.tier === b.tier + 1);
    if (!up || b.queue.some(q => q.up)) return;
    if (b.queue.length >= 5) return;
    const miss = this.missing(P, up.cost);
    if (miss) { this.msg(P.id, miss, 'error'); return; }
    this.pay(P, up.cost);
    b.queue.push({ up: up.tier, t: 0, time: up.time, cost: up.cost });
  }

  cmdCancel(P, c) {
    const b = this.byId.get(c.building);
    if (!this.owns(P.id, b)) return;
    if (b.built < 1) {                             // cancel a foundation: 75% refund
      this.pay(P, b.def.cost, -0.75);
      this.kill(b, null, true);
      return;
    }
    const i = c.slot ?? b.queue.length - 1;
    const q = b.queue[i];
    if (!q) return;
    b.queue.splice(i, 1);
    if (q.unit) this.pay(P, this.defs.units[q.unit].cost, -1);
    else if (q.up) this.pay(P, q.cost, -1);
    else if (q.revive) this.pay(P, q.cost, -1);
  }

  cmdRevive(P, c) {
    const b = this.byId.get(c.building);
    const h = P.deadHeroes.find(x => x.type === c.unit);
    if (!this.owns(P.id, b) || !h || b.queue.some(q => q.revive === c.unit) || b.def.role !== 'town_hall') return;
    const d = this.defs.units[h.type];
    const k = this.D.economy.heroes.revive_cost_mult;
    const cost = { gold: Math.round(d.cost.gold * k), wood: Math.round(d.cost.wood * k), food: 0 };
    const miss = this.missing(P, cost);
    if (miss) { this.msg(P.id, miss, 'error'); return; }
    this.pay(P, cost);
    b.queue.push({ revive: h.type, t: 0, time: this.D.economy.heroes.revive_time, cost });
  }

  cmdTransfer(P, c) {
    const T = this.players[c.to];
    if (!T || T === P) return;
    const tax = this.D.economy.transfer_tax;
    const g = Math.max(0, Math.min(P.gold, c.gold || 0)), w = Math.max(0, Math.min(P.wood, c.wood || 0));
    P.gold -= g; P.wood -= w;
    T.gold += Math.floor(g * (1 - tax)); T.wood += Math.floor(w * (1 - tax));
    this.msg(T.id, `${P.name} передаёт вам ${Math.floor(g * (1 - tax))} зол. и ${Math.floor(w * (1 - tax))} дер.`, 'ally');
  }

  cmdCrusade(P) {
    if (!this.crusade.ready || this.crusade.used) return;
    this.crusade.used = true;
    this.crusade.until = this.tick + 60 * HZ;
    this.event({ k: 'crusade' });
    this.msg(-1, `${P.name} объявляет Крестовый поход! Армии +30% к урону и скорости на 60 с`, 'ally');
  }

  gatherOrder(u, t) {
    if (!t || !t.alive) return null;
    const res = t.type === 'gold_mine' ? 'gold' : t.kind === 'tree' ? 'wood' : t.kind === 'shoal' ? 'food' : null;
    if (!res) return null;
    return { t: 'gather', target: t.id, res, phase: u.carry.amt > 0 && u.carry.res !== res ? 'return' : 'go' };
  }

  // ------------------------------------------------------------------ tick
  step() {
    if (this.result) { this.tick++; return; }
    this.fieldBudget = 5;
    this.grid.tick = this.tick;
    for (const c of this.cmds) { try { this.applyCommand(c); } catch (err) { console.error('cmd', c, err); } }
    this.cmds.length = 0;
    this.rebuildHash();
    this.blist = this.blds.filter(e => e.alive);
    this.abilities.tick();
    this.director.tick();
    const units = [];
    for (const e of this.units) if (e.alive) { this.unitTick(e); units.push(e); }
    for (const b of this.blist) if (b.alive) this.buildingTick(b);
    this.physics(units);
    this.projTick();
    if (this.tick % 4 === 0) this.updateVision();
    if (this.tick % 10 === 0) { this.updatePop(); this.economyTick(); }
    this.cleanup();
    this.checkEnd();
    this.tick++;
  }

  economyTick() {
    for (const P of this.players) {
      if (!P.alive) continue;
      let trickle = 0;
      for (const e of this.blds) if (e.alive && e.owner === P.id && e.built >= 1) trickle += e.def.foodTrickle;
      P.food += trickle * 0.5;                      // every 10 ticks = 0.5 s
    }
    const team = this.players.reduce((s, p) => s + p.mined, 0);
    const allT3 = this.players.every(p => !p.alive || p.tier >= 3);
    if (!this.crusade.ready && team >= this.D.economy.royal_treasury_goal && allT3) {
      this.crusade.ready = true;
      this.msg(-1, 'Королевская казна полна! Доступен Крестовый поход', 'ally');
    }
  }

  upkeep(P) {
    for (const t of this.D.economy.upkeep) if (P.popUsed <= t.max_pop) return t.gold_rate;
    return 0.4;
  }

  updatePop() {
    for (const P of this.players) { P.popUsed = 0; P.popCap = 0; P.tier = 1; P.halls = 0; }
    for (const e of this.units.concat(this.blds)) {
      if (!e.alive) continue;
      const P = this.players[e.owner];
      if (!P) continue;
      if (e.kind === 'unit') { if (!e.summoned) P.popUsed += e.def.pop; }
      else if (e.kind === 'building' && e.built >= 1) {
        P.popCap += e.def.pop;
        if (e.def.role === 'town_hall') { P.tier = Math.max(P.tier, e.tier); P.halls++; }
      }
    }
    for (const P of this.players) P.popCap = Math.min(P.popCap, this.D.economy.pop_cap);
  }

  updateVision() {
    const g = this.grid, n = g.n, V = this.vis;
    V.fill(0);
    for (const e of this.units.concat(this.blds)) {
      if (!e.alive || e.team !== 0) continue;
      const r = e.kind === 'unit' ? e.def.sight * (this.isNight && !e.def.hero ? 0.8 : 1) : (e.built >= 1 ? e.def.sight : 4);
      const cx = g.cx(e.x), cy = g.cy(e.y), R = Math.ceil(r), r2 = r * r;
      for (let dy = -R; dy <= R; dy++) {
        const y = cy + dy; if (y < 0 || y >= n) continue;
        const span = Math.floor(Math.sqrt(Math.max(0, r2 - dy * dy)));
        const x0 = Math.max(0, cx - span), x1 = Math.min(n - 1, cx + span);
        V.fill(1, y * n + x0, y * n + x1 + 1);
      }
    }
    for (const z of this.zones) if (z.kind === 'reveal' || z.kind === 'ward') {
      g.forCells(z.x, z.y, z.r, i => { V[i] = 1; });
    }
    const X = this.explored;
    for (let i = 0; i < V.length; i++) if (V[i]) X[i] = 1;
    this.visVersion++;
  }

  // ------------------------------------------------------------------ units
  anim(e, name, dur = 1) {
    if (e.anim === name && name !== 'Attack' && name !== 'Cast') return;
    e.anim = name; e.animT = this.tick; e.animDur = dur;
  }

  unitTick(e) {
    if (e.cd > 0) e.cd -= DT;
    e.vx = 0; e.vy = 0;
    const m = e.mods;
    if (e.hidden) { if (e.order.t === 'gather') this.gatherTick(e, e.order); return; }
    if (m.stunned) { e.swing = 0; this.anim(e, 'Idle'); return; }
    if (e.swing > 0) {
      e.swing -= DT;
      if (e.swing <= 0) this.strike(e);
      return;
    }
    if (e.castT > 0) {
      e.castT -= DT;
      if (e.castT <= 0) this.abilities.release(e);
      return;
    }
    if (m.taunted) {
      const t = this.byId.get(m.taunted);
      if (this.canTarget(e, t)) { this.engage(e, t); return; }
    }
    const o = e.order;
    switch (o.t) {
      case 'idle': this.idleTick(e, false); break;
      case 'hold': this.idleTick(e, true); break;
      case 'move':
        if (this.moveTo(e, o.x, o.y, 0.25, o)) this.nextOrder(e);
        else this.anim(e, 'Walk');
        break;
      case 'amove': case 'patrol': this.amoveTick(e, o); break;
      case 'attack': {
        const t = this.byId.get(o.target);
        if (!this.canTarget(e, t) && !(t && t.alive && o.forced && t.kind === 'building' && this.isHostile(e, t))) { this.nextOrder(e); break; }
        this.engage(e, t);
        break;
      }
      case 'follow': {
        const t = this.byId.get(o.target);
        if (!t || !t.alive) { this.nextOrder(e); break; }
        if (this.gap(e, t) > 1.6) { this.moveToEnt(e, t, 1.2); this.anim(e, 'Walk'); }
        else { this.anim(e, 'Idle'); }
        break;
      }
      case 'gather': this.gatherTick(e, o); break;
      case 'build': this.buildTick(e, o); break;
      case 'construct': this.constructTick(e, o); break;
      case 'cast': this.abilities.castTick(e, o); break;
      case 'leap': this.abilities.leapTick(e, o); break;
      case 'guard': this.guardTick(e, o); break;
      case 'creep': {
        const t = this.byId.get(o.target), c = e.camp;
        if (!c || !this.canTarget(e, t) || Math.hypot(e.x - c.x, e.y - c.y) > this.D.creeps.leash) { this.setOrder(e, { t: 'idle' }); break; }
        this.engage(e, t);
        break;
      }
      default: this.nextOrder(e);
    }
  }

  acquireRange(e) { return e.def.range > 2 ? Math.max(e.def.range + 1.5, 8) : 7.5; }

  findTarget(e, r) {
    let best = null, bs = Infinity;
    this.query(e.x, e.y, r + 1.5, t => {
      if (!this.canTarget(e, t)) return;
      // prefer things that fight back, then the closest
      const s = Math.hypot(t.x - e.x, t.y - e.y) - t.r + (t.def.gatherer ? 3 : 0) + (t.order?.t === 'attack' ? -1 : 0);
      if (s < bs) { bs = s; best = t; }
    });
    if (!best && e.team !== 0) {
      // structures in range (rats chew on buildings)
      for (const b of this.blist) {
        if (!b.alive || !this.canTarget(e, b)) continue;
        const d = this.gap(e, b);
        if (d < r && d < bs) { bs = d; best = b; }
      }
    }
    return best;
  }

  idleTick(e, hold) {
    this.anim(e, 'Idle');
    if (e.def.gatherer && !hold) return;          // workers don't pick fights
    if (e.camp) { this.creepTick(e); return; }
    if ((this.tick + e.id) % 5) return;
    const t = this.findTarget(e, hold ? e.def.range + 0.6 : this.acquireRange(e));
    if (!t) return;
    if (hold) { if (this.gap(e, t) <= e.def.range + 0.1) this.engage(e, t); return; }
    e.orders.unshift({ t: 'move', x: e.x, y: e.y, fx: e.x, fy: e.y, gid: 0 });
    this.setOrder(e, { t: 'guard', target: t.id, hx: e.x, hy: e.y });
  }

  // chase an acquired target, then walk back home (WC3 "return to guard")
  guardTick(e, o) {
    const t = this.byId.get(o.target);
    const far = Math.hypot(e.x - o.hx, e.y - o.hy) > 14;
    if (!this.canTarget(e, t) || far) {
      const nt = far ? null : this.findTarget(e, this.acquireRange(e));
      if (nt) { o.target = nt.id; return; }
      this.nextOrder(e); return;
    }
    this.engage(e, t);
  }

  creepTick(e) {
    const C = this.D.creeps, c = e.camp;
    const home = Math.hypot(e.x - c.x, e.y - c.y);
    if (e.order.t === 'idle') {
      if (e.hp < e.maxHp && (this.tick % 20) === 0 && this.tick - e.lastCombat > 100) e.hp = Math.min(e.maxHp, e.hp + e.maxHp * 0.05);
      if (home > 3) { this.moveTo(e, c.x, c.y, 2.5, { fx: c.x, fy: c.y }); this.anim(e, 'Walk'); return; }
      if ((this.tick + e.id) % 6) return;
      let t = null, bd = C.aggro;
      this.query(c.x, c.y, C.aggro, u => {
        const d = Math.hypot(u.x - c.x, u.y - c.y);
        if (this.canTarget(e, u) && d < bd) { bd = d; t = u; }
      });
      if (t) this.campAggro(c, t);
    }
  }

  campAggro(c, t) {
    this.query(c.x, c.y, 9, u => {
      if (u.camp === c || (u.camp && u.camp.x === c.x && u.camp.y === c.y)) {
        if (u.order.t === 'idle') this.setOrder(u, { t: 'creep', target: t.id });
      }
    });
  }

  amoveTick(e, o) {
    if (o.target) {
      const t = this.byId.get(o.target);
      if (this.canTarget(e, t) && Math.hypot(t.x - e.x, t.y - e.y) < this.acquireRange(e) + 6) { this.engage(e, t); return; }
      o.target = 0; e.wp = null;
    }
    if ((this.tick + e.id) % 4 === 0) {
      const t = this.findTarget(e, this.acquireRange(e));
      if (t) { o.target = t.id; this.engage(e, t); return; }
    }
    if (this.moveTo(e, o.x, o.y, 0.4, o)) {
      if (o.t === 'patrol') { const { ax, ay } = o; o.ax = o.x; o.ay = o.y; o.x = ax; o.y = ay; o.fx = ax; o.fy = ay; e.wp = null; e.prog = { d: Infinity, t: this.tick }; }
      else this.nextOrder(e);
    } else this.anim(e, 'Walk');
  }

  engage(e, t) {
    e.lastCombat = this.tick;
    const g = this.gap(e, t);
    const rng = e.def.range;
    if (g <= rng + 0.05) {
      this.face(e, t.x, t.y, true);
      if (e.cd <= 0) this.startSwing(e, t);
      else if (e.anim !== 'Attack' || this.tick - e.animT > e.animDur * HZ) this.anim(e, 'Idle');
      e.engaged = t.id;
      return true;
    }
    if (e.mods.rooted) { this.anim(e, 'Idle'); return false; }
    this.moveToEnt(e, t, rng * 0.9);
    this.anim(e, 'Walk');
    return false;
  }

  startSwing(e, t) {
    const m = e.mods;
    const cd = e.def.cooldown / m.atkSpeed;
    const dur = Math.min(1.0, cd * 0.85);
    e.cd = cd;
    e.swing = dur * (e.def.range > 2 ? 0.5 : 0.42);
    e.swingT = t.id;
    this.anim(e, 'Attack', dur);
    if (m.invisible && !m.keepInvis) this.abilities.breakInvis(e);
  }

  strike(e) {
    const t = this.byId.get(e.swingT);
    if (!t || !t.alive) return;
    const d = this.def(e);
    if (this.gap(e, t) > d.range + 1.0) return;
    let amt = (this.rng.int(d.dmg[0], d.dmg[1]) + (e.dmgBonus || 0)) * e.mods.dmg;
    if (e.firstStrike) { amt *= e.firstStrike; e.firstStrike = 0; }
    if (d.projectile) {
      this.projectiles.push({ id: this.nextId++, src: e.id, owner: e.owner, team: e.team, target: t.id, x: e.x, y: e.y,
        z: 0.9, speed: this.defs.PROJECTILE_SPEED[d.projectile] || 20, kind: d.projectile, dmg: amt, atk: d.atkType });
      this.event({ k: 'proj', id: this.projectiles.at(-1).id, src: e.id, target: t.id, kind: d.projectile });
    } else {
      this.damage(e, t, amt, d.atkType, { attack: true });
    }
  }

  def(e) { return e.def; }

  projTick() {
    const keep = [];
    for (const p of this.projectiles) {
      const t = this.byId.get(p.target);
      if (!t || !t.alive) { this.event({ k: 'projend', id: p.id }); continue; }
      const dx = t.x - p.x, dy = t.y - p.y, d = Math.hypot(dx, dy);
      const step = p.speed * DT;
      if (d <= step + t.r * 0.5) {
        const src = this.byId.get(p.src) || { team: p.team, owner: p.owner, id: p.src, mods: { dmg: 1 } };
        this.damage(src, t, p.dmg, p.atk, { attack: true, ranged: true });
        if (p.bounce) this.abilities.bounce(p, t);
        if (p.splash) this.splash(src, t.x, t.y, p.splash, p.dmg * 0.5, p.atk, t);
        this.event({ k: 'projend', id: p.id, hit: true });
        continue;
      }
      p.x += dx / d * step; p.y += dy / d * step;
      keep.push(p);
    }
    this.projectiles = keep;
  }

  splash(src, x, y, r, amt, atk, skip) {
    this.query(x, y, r, u => { if (u !== skip && this.isHostile(src, u)) this.damage(src, u, amt, atk, {}); });
  }

  damage(src, t, amt, atk, opts = {}) {
    if (!t.alive || t.invuln || amt <= 0) return 0;
    const m = t.mods || {};
    if (opts.attack) {
      if (m.evasion && this.rng.next() < m.evasion) { this.event({ k: 'miss', id: t.id }); return 0; }
      if (src.mods?.miss && this.rng.next() < src.mods.miss) { this.event({ k: 'miss', id: t.id }); return 0; }
      if (m.reflect && !opts.ranged && src.kind === 'unit') { this.damage(t, src, amt, 'hero', {}); this.event({ k: 'fx', fx: 'parry', x: t.x, y: t.y }); return 0; }
    }
    const D = this.D.damage_matrix;
    const ai = D.armor.indexOf(t.kind === 'building' ? (t.def.armorType || 'fortified') : t.def.armorType);
    let mult = (D.attack[atk] || D.attack.hero)[ai < 0 ? 1 : ai];
    if (opts.vsBuildings && t.kind === 'building') mult *= opts.vsBuildings;
    const armor = (t.armor || 0) + (m.armor || 0);
    let dmg = amt * mult * armorFactor(armor, D.armor_reduction_per_point) * (m.dmgTaken || 1);
    if (m.redirect) {                              // Rex's Loyalty: share damage onto the protector
      const pr = this.byId.get(m.redirect.src);
      if (pr && pr.alive && pr !== t) { const s = dmg * m.redirect.share; dmg -= s; pr.hp -= s; this.event({ k: 'hit', id: pr.id, amt: Math.round(s) }); if (pr.hp <= 0) this.kill(pr, src); }
    }
    t.hp -= dmg;
    t.lastCombat = this.tick;
    if (src && src.kind === 'unit') src.lastCombat = this.tick;
    this.event({ k: 'hit', id: t.id, src: src?.id, amt: Math.round(dmg), atk });
    if (t.kind === 'unit' && t.team === 0 && this.players[t.owner] && this.tick - (this.players[t.owner].alertT || -999) > 200 && src?.team !== 0) {
      this.players[t.owner].alertT = this.tick;
      this.event({ k: 'alert', p: t.owner, x: t.x, y: t.y });
    }
    if (t.hp <= 0) {
      if (!this.abilities.preventDeath(t)) this.kill(t, src);
      return dmg;
    }
    // retaliation and calls for help
    if (t.kind === 'unit' && src && src.kind === 'unit' && src.alive) {
      if (t.camp) this.campAggro(t.camp, src);
      else if ((t.order.t === 'idle') && !t.def.gatherer && this.canTarget(t, src)) {
        e_guard(this, t, src);
      }
    }
    return dmg;
  }

  kill(e, src, silent = false) {
    if (!e.alive) return;
    e.alive = false;
    e.hp = 0;
    e.deadT = this.tick;
    e.swing = 0;
    if (e.kind === 'unit') {
      this.anim(e, 'Death');
      e.order = { t: 'dead' }; e.orders = [];
      if (e.hidden) e.hidden = false;
      const P = this.players[e.owner];
      if (P) P.stats.lost++;
      if (e.def.hero && P) {
        P.heroes = P.heroes.filter(id => id !== e.id);
        if (!e.summoned) P.deadHeroes.push({ type: e.type, level: e.level, xp: e.xp, skill: { ...e.skill }, points: e.points, items: e.items });
        this.msg(P.id, `${e.def.name} пал(а)! Воскресите героя в ратуше`, 'alert');
      }
      if (src && this.players[src.owner]) this.players[src.owner].stats.kills++;
      if (src && src.team !== e.team && !e.summoned) this.abilities.grantXp(e, src);
      if (e.camp && src && this.players[src.owner]) {
        const g = Math.round(this.D.economy.bounty.creep_gold_per_pop * (e.def.pop + 1) * (this.D.creeps.scale[e.camp.level] || 1));
        this.players[src.owner].gold += g;
        this.event({ k: 'bounty', x: e.x, y: e.y, amt: g, p: src.owner });
      }
      if (e.def.boss) this.event({ k: 'boss_dead' });
    } else if (e.kind === 'building') {
      this.grid.stamp(e.cells, -1);
      for (const q of e.queue) if (q.unit && this.players[e.owner]) this.pay(this.players[e.owner], this.defs.units[q.unit].cost, -1);
      e.queue = [];
    } else if (e.kind === 'tree') {
      this.grid.stamp(e.cells, -1);
    }
    if (!silent) this.event({ k: 'death', id: e.id, kind: e.kind });
    this.updatePop();
  }

  cleanup() {
    if (this.tick % 20) return;
    const keep = [];
    for (const e of this.ents) {
      if (!e.alive) {
        const age = this.tick - e.deadT;
        const ttl = e.kind === 'unit' ? 8 * HZ : e.kind === 'building' ? 6 * HZ : 4 * HZ;
        if (age > ttl) { this.byId.delete(e.id); this.event({ k: 'remove', id: e.id }); continue; }
      }
      keep.push(e);
    }
    this.ents = keep;
    this.units = keep.filter(e => e.kind === 'unit');
    this.blds = keep.filter(e => e.kind === 'building');
  }

  checkEnd() {
    if (this.tick % 20) return;
    for (const P of this.players) {
      if (!P.alive) continue;
      const hasHall = this.blds.some(e => e.alive && e.owner === P.id && e.def.role === 'town_hall');
      const hasUnits = this.units.some(e => e.alive && e.owner === P.id && e.def.gatherer);
      if (!hasHall && !hasUnits) { P.alive = false; this.msg(-1, `${P.name} выбывает из игры`, 'alert'); }
    }
    if (this.players.every(p => !p.alive)) { this.result = 'defeat'; this.event({ k: 'end', result: 'defeat' }); return; }
    const pits = this.blds.filter(e => e.alive && e.type === 'rat_pit');
    if (!pits.length || this.director.kingSlain) { this.result = 'victory'; this.event({ k: 'end', result: 'victory' }); }
  }

  // ---------------------------------------------------------------- movement
  face(e, x, y, instant = false) {
    const a = Math.atan2(y - e.y, x - e.x);
    let d = a - e.facing;
    while (d > Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    const turn = instant ? 0.45 : 0.3;
    e.facing += Math.max(-turn, Math.min(turn, d));
  }

  fieldFor(key, goals) {
    const f = this.grid.fields.get(key);
    if (f && this.grid.fresh(f)) return this.grid.field(key, goals);
    if (this.fieldBudget <= 0) return null;
    this.fieldBudget--;
    return this.grid.field(key, goals);
  }

  // returns true on arrival (or when giving up on an unreachable goal)
  moveTo(e, gx, gy, arriveR, o) {
    const dx = gx - e.x, dy = gy - e.y, dist = Math.hypot(dx, dy);
    if (dist <= arriveR) { e.arrivedGid = o?.gid || 0; return true; }
    if (e.mods.rooted) return false;
    // arrival contagion: stop when touching a group-mate that already arrived
    if (o && o.gid && dist < 2.2 + Math.sqrt(e.orders.length + 1)) {
      let touching = false;
      this.query(e.x, e.y, e.r + 0.7, u => { if (u !== e && u.arrivedGid === o.gid) touching = true; });
      if (touching) { e.arrivedGid = o.gid; return true; }
    }
    if (dist < e.prog.d - 0.25) { e.prog.d = dist; e.prog.t = this.tick; }
    else if (this.tick - e.prog.t > 3 * HZ) { e.prog = { d: dist, t: this.tick }; e.wp = null; return true; }   // stuck: give up (callers may retry)
    if (!e.wp || this.tick >= e.wpT || Math.hypot(e.wp[0] - e.x, e.wp[1] - e.y) < 0.3) {
      let wp = null;
      if (dist < 40 && this.grid.los(e.x, e.y, gx, gy, e.r * 0.8)) wp = [gx, gy];
      else {
        const fx = o?.fx ?? gx, fy = o?.fy ?? gy;
        const gi = o?.goalKey ? null : this.grid.idx(fx, fy);
        const key = o?.goalKey || 'p' + gi;
        const f = this.fieldFor(key, o?.goals || [gi]);
        if (f) {
          const here = this.grid.idx(e.x, e.y);
          if (here >= 0 && f.cost[here] === 0) wp = [gx, gy];
          else wp = this.grid.steer(f, e.x, e.y, e.r * 0.8);
          if (!wp) { e.prog = { d: dist, t: this.tick }; return true; }   // unreachable
        } else wp = [gx, gy];
      }
      e.wp = wp; e.wpT = this.tick + 5 + (e.id % 4);
    }
    const sx = e.wp[0] - e.x, sy = e.wp[1] - e.y, sd = Math.hypot(sx, sy) || 1;
    const sp = e.def.speed * e.mods.speed;
    e.vx = sx / sd * sp; e.vy = sy / sd * sp;
    this.face(e, e.x + e.vx, e.y + e.vy);
    e.arrivedGid = 0;
    return false;
  }

  // move to within `range` of an entity's edge
  moveToEnt(e, t, range) {
    if (this.gap(e, t) <= range) return true;
    const static_ = t.kind !== 'unit';
    if (static_) {
      // final approach: straight at the closest point of the footprint
      const hw = t.w ? t.w / 2 : 0, hh = t.h ? t.h / 2 : 0;
      let px = Math.max(t.x - hw, Math.min(t.x + hw, e.x)), py = Math.max(t.y - hh, Math.min(t.y + hh, e.y));
      let nx = e.x - px, ny = e.y - py, nl = Math.hypot(nx, ny) || 1;
      const pad = (t.w ? 0 : t.r) + e.r + 0.1;
      px += nx / nl * pad; py += ny / nl * pad;
      if (Math.hypot(e.x - px, e.y - py) < 3.5 && this.grid.los(e.x, e.y, px, py, 0.15)) {
        this.moveTo(e, px, py, 0.05, null);
        return false;
      }
      if (!t.goals || t.goalsV !== this.grid.version) { t.goals = this.ringCells(t); t.goalsV = this.grid.version; }
      const key = 'e' + t.id;
      this.moveTo(e, t.x, t.y, 0, { fx: t.x, fy: t.y, goalKey: key, goals: t.goals });
      return false;
    }
    this.moveTo(e, t.x, t.y, 0, { fx: t.x, fy: t.y });
    return false;
  }

  ringCells(t) {
    const g = this.grid, out = [];
    const w = (t.w || t.r * 2) / 2 + 0.9, h = (t.h || t.r * 2) / 2 + 0.9;
    const extra = t.kind === 'shoal' ? 6.5 : 0;
    for (const i of g.rectCells(t.x, t.y, w * 2 + extra * 2, h * 2 + extra * 2)) if (g.terrain[i] && !g.block[i]) out.push(i);
    if (!out.length) { const p = g.nearestFree(t.x, t.y, 12); if (p) out.push(g.idx(p[0], p[1])); }
    return out;
  }

  physics(units) {
    const g = this.grid;
    for (const e of units) {
      if (!e.alive || e.hidden || (!e.vx && !e.vy)) continue;
      const nx = e.x + e.vx * DT, ny = e.y + e.vy * DT;
      if (g.freeAt(nx, ny)) { e.x = nx; e.y = ny; }
      else if (g.freeAt(nx, e.y)) e.x = nx;
      else if (g.freeAt(e.x, ny)) e.y = ny;
      else e.wp = null;
    }
    this.rebuildHash();
    // pairwise separation, two relaxation passes
    for (let pass = 0; pass < 2; pass++) {
      for (const a of units) {
        if (!a.alive || a.hidden) continue;
        this.query(a.x, a.y, a.r + 1.2, b => {
          if (b.id <= a.id || !b.alive) return;
          const dx = b.x - a.x, dy = b.y - a.y, R = a.r + b.r;
          const d2 = dx * dx + dy * dy;
          if (d2 >= R * R) return;
          const d = Math.sqrt(d2) || 0.01, ov = (R - d) * 0.5;
          const ma = mass(a), mb = mass(b), s = ma + mb;
          const ux = d2 ? dx / d : Math.cos(a.id), uy = d2 ? dy / d : Math.sin(a.id);
          const ka = ov * (mb / s) * 2, kb = ov * (ma / s) * 2;
          const ax = a.x - ux * ka, ay = a.y - uy * ka, bx = b.x + ux * kb, by = b.y + uy * kb;
          if (g.freeAt(ax, ay)) { a.x = ax; a.y = ay; }
          if (g.freeAt(bx, by)) { b.x = bx; b.y = by; }
        });
      }
    }
    for (const e of units) if (e.alive && !e.hidden && !g.freeAt(e.x, e.y)) {
      const p = g.nearestFree(e.x, e.y, 4);
      if (p) { const dx = p[0] - e.x, dy = p[1] - e.y, d = Math.hypot(dx, dy); const s = Math.min(d, 0.25); e.x += dx / d * s; e.y += dy / d * s; }
    }
  }

  // ---------------------------------------------------------------- gathering
  dropoff(e) {
    let best = null, bd = Infinity;
    for (const b of this.blds) {
      if (!b.alive || b.owner !== e.owner || b.built < 1 || !b.def.dropoff.includes(e.carry.res)) continue;
      const d = (b.x - e.x) ** 2 + (b.y - e.y) ** 2;
      if (d < bd) { bd = d; best = b; }
    }
    return best;
  }

  leaveMine(e) {
    if (!e.hidden && !e.inMine) return;
    const m = this.byId.get(e.inMine);
    if (m) m.inside = Math.max(0, m.inside - 1);
    e.inMine = 0; e.hidden = false;
    if (m) {
      const home = this.dropoff(e) || m;
      const a = Math.atan2(home.y - m.y, home.x - m.x);
      const p = this.grid.nearestFree(m.x + Math.cos(a) * (m.w / 2 + 0.9), m.y + Math.sin(a) * (m.h / 2 + 0.9), 6);
      if (p) { e.x = p[0]; e.y = p[1]; }
      e.facing = a;
    }
  }

  gatherTick(e, o) {
    const E = this.D.economy, P = this.players[e.owner];
    if (o.phase === 'return') {
      if (!e.carry.amt) { o.phase = 'go'; return; }
      const b = (o.drop && this.byId.get(o.drop)?.alive && this.byId.get(o.drop)) || this.dropoff(e);
      if (!b) { this.anim(e, 'Idle'); return; }
      if (this.gap(e, b) <= 0.75) {
        let amt = e.carry.amt;
        if (e.carry.res === 'gold') { P.mined += amt; amt = Math.round(amt * this.upkeep(P) * (1 + this.abilities.incomeBonus(e.owner))); }
        P[e.carry.res] += amt;
        P.stats.gathered += amt;
        this.event({ k: 'deposit', id: e.id, res: e.carry.res, amt, p: e.owner });
        e.carry = { res: null, amt: 0 };
        o.phase = 'go'; o.drop = 0; e.wp = null; e.prog = { d: Infinity, t: this.tick };
        if (!o.target || !this.byId.get(o.target)?.alive) this.retarget(e, o);
        return;
      }
      this.moveToEnt(e, b, 0.6);
      this.anim(e, 'Walk');
      return;
    }
    let t = this.byId.get(o.target);
    if (e.hidden && (!t || !t.alive)) this.leaveMine(e);
    if (!t || !t.alive || (t.kind === 'tree' && t.wood <= 0)) { if (!this.retarget(e, o)) { this.setOrder(e, { t: 'idle' }); } return; }
    o.res = o.res || (t.type === 'gold_mine' ? 'gold' : t.kind === 'tree' ? 'wood' : 'food');
    const cap = E.gather[o.res].per_trip * e.def.carryMult;
    if (o.phase === 'go') {
      if (e.carry.amt >= cap || (e.carry.amt && e.carry.res !== o.res)) { o.phase = 'return'; return; }
      const reach = t.kind === 'shoal' ? 6.0 : t.kind === 'tree' ? 0.95 : 0.7;
      if (this.gap(e, t) <= reach) {
        if (o.res === 'gold') {
          if (t.inside >= E.gather.gold.max_workers) { this.anim(e, 'Idle'); return; }
          t.inside++; e.inMine = t.id; e.hidden = true;
          this.event({ k: 'enter', id: e.id, mine: t.id });
        }
        o.phase = 'work';
        e.workT = E.gather[o.res].seconds / (1 + (e.mods.gather || 0));
        this.face(e, t.x, t.y, true);
        if (o.res !== 'gold') this.anim(e, 'Work');
        return;
      }
      this.moveToEnt(e, t, reach * 0.8);
      this.anim(e, 'Walk');
      return;
    }
    if (o.phase === 'work') {
      e.workT -= DT;
      if (o.res !== 'gold') this.face(e, t.x, t.y);
      if (e.workT > 0) return;
      let amt = cap;
      if (o.res === 'food' && this.D.factions[P.faction]?.mechanics?.fish_bonus) amt = Math.round(amt * (1 + this.D.factions[P.faction].mechanics.fish_bonus));
      if (o.res === 'gold') { amt = Math.min(amt, t.gold); t.gold -= amt; }
      else if (o.res === 'wood') { amt = Math.min(amt, t.wood); t.wood -= amt; this.event({ k: 'chop', id: t.id }); }
      else { amt = Math.min(amt, t.food); t.food -= amt; }
      e.carry = { res: o.res, amt };
      e.lastRes = t.id;
      if (o.res === 'gold') {
        this.leaveMine(e);
        if (t.gold <= 0) { this.msg(e.owner, 'Рудник истощён', 'alert'); this.kill(t, null); }
      }
      if (o.res === 'wood' && t.wood <= 0) this.kill(t, e);
      if (o.res === 'food' && t.food <= 0) { this.kill(t, null, true); }
      o.phase = 'return'; e.wp = null; e.prog = { d: Infinity, t: this.tick };
    }
  }

  finishMining(e) {
    const m = this.byId.get(e.inMine);
    const cap = this.D.economy.gather.gold.per_trip * e.def.carryMult;
    if (m && m.alive) { const amt = Math.min(cap, m.gold); m.gold -= amt; e.carry = { res: 'gold', amt }; e.lastRes = m.id; }
    this.leaveMine(e);
    if (m && m.alive && m.gold <= 0) this.kill(m, null);
  }

  retarget(e, o) {
    const last = this.byId.get(o.target);
    const x = last?.x ?? e.x, y = last?.y ?? e.y;
    let t = null;
    if (o.res === 'wood') t = this.nearest(x, y, z => z.kind === 'tree' && z.wood > 0, 14);
    else if (o.res === 'gold') t = this.nearest(x, y, z => z.type === 'gold_mine' && z.gold > 0, 30);
    else if (o.res === 'food') t = this.nearest(x, y, z => z.kind === 'shoal' && z.food > 0, 40);
    if (!t) return false;
    o.target = t.id;
    return true;
  }

  // -------------------------------------------------------------- construction
  buildTick(e, o) {
    const d = this.defs.buildings[o.type];
    const P = this.players[e.owner];
    const site = { kind: 'building', x: o.x, y: o.y, w: d.w, h: d.h, r: Math.max(d.w, d.h) / 2 };
    if (this.gap(e, site) > 0.9) {
      if (!o.goals) { o.goals = this.ringCells(site); o.goalKey = 'site' + o.x + ',' + o.y; o.fx = o.x; o.fy = o.y; }
      if (this.moveTo(e, o.x, o.y, Math.min(d.w, d.h) / 2 + e.r + 0.6, o) && this.gap(e, site) > 1.6) {
        this.msg(e.owner, 'Строитель не может добраться до места', 'error');
        if (o.paid) this.pay(P, d.cost, -1);
        this.nextOrder(e);
        return;
      }
      this.anim(e, 'Walk');
      return;
    }
    // shove friendly units off the site; abort if blocked by anything solid
    if (!this.grid.canPlace(o.x, o.y, d.w, d.h)) {
      this.msg(e.owner, 'Место занято', 'error');
      if (o.paid) this.pay(P, d.cost, -1);
      this.nextOrder(e);
      return;
    }
    const b = this.placeBuilding(o.type, e.owner, o.x, o.y, false);
    this.unstick(e);
    this.setOrder(e, { t: 'construct', target: b.id });
  }

  constructTick(e, o) {
    const b = this.byId.get(o.target);
    if (!b || !b.alive || b.built >= 1) { this.anim(e, 'Idle'); this.nextOrder(e); return; }
    if (this.gap(e, b) > 0.9) { this.moveToEnt(e, b, 0.6); this.anim(e, 'Walk'); return; }
    this.face(e, b.x, b.y);
    this.anim(e, 'Work');
    if (b.lastBuildTick === this.tick) return;      // several builders: WC3 humans stack, keep it 1x + 50% each
    b.lastBuildTick = this.tick;
    const rate = DT / b.def.buildTime;
    const before = b.built;
    b.built = Math.min(1, b.built + rate);
    b.hp = Math.min(b.maxHp, b.hp + (b.built - before) * b.maxHp * 0.9);
    if (b.built >= 1) {
      b.hp = Math.max(b.hp, Math.round(b.maxHp * 0.999));
      this.event({ k: 'built', id: b.id, p: b.owner });
      this.msg(b.owner, `Построено: ${b.def.name}`, 'info');
      this.updatePop();
      this.nextOrder(e);
      // a builder next to wood or gold goes back to work
      if (e.order.t === 'idle' && e.lastRes) {
        const t = this.byId.get(e.lastRes);
        if (t && t.alive) this.setOrder(e, this.gatherOrder(e, t));
      }
    }
  }

  // ---------------------------------------------------------------- buildings
  buildingTick(b) {
    if (b.built < 1) return;
    const P = this.players[b.owner];
    if (b.def.attack && P) this.towerTick(b);
    if (!b.queue.length) return;
    const q = b.queue[0];
    if (q.unit) {
      const d = this.defs.units[q.unit];
      if (q.t === 0 && P.popUsed + d.pop > P.popCap) { b.blocked = true; return; }
      b.blocked = false;
    }
    q.t += DT * (1 + this.abilities.trainBonus(b));
    if (q.t < q.time) return;
    b.queue.shift();
    if (q.up) {
      b.tier = q.up;
      const up = b.def.upgrades.find(u => u.tier === q.up);
      if (up?.hp) { const f = b.hp / b.maxHp; b.maxHp = up.hp; b.hp = Math.round(up.hp * f); }
      this.msg(b.owner, `Ратуша улучшена: ${up?.name || 'уровень ' + q.up}`, 'info');
      this.event({ k: 'upgraded', id: b.id, tier: q.up });
      this.updatePop();
      return;
    }
    const type = q.unit || q.revive;
    const exit = this.exitPoint(b);
    const u = this.spawnUnit(type, b.owner, exit[0], exit[1]);
    u.facing = Math.atan2(exit[1] - b.y, exit[0] - b.x);
    if (q.revive) {
      const i = P.deadHeroes.findIndex(h => h.type === q.revive);
      const h = P.deadHeroes.splice(i, 1)[0];
      this.abilities.restoreHero(u, h);
    }
    if (u.def.hero) P.heroes.push(u.id);
    if (b.rally) {
      const t = b.rally.target && this.byId.get(b.rally.target);
      if (u.def.gatherer && t && t.alive) this.setOrder(u, this.gatherOrder(u, t) || { t: 'move', x: b.rally.x, y: b.rally.y });
      else { const p = this.grid.nearestFree(b.rally.x, b.rally.y) || [b.rally.x, b.rally.y]; this.setOrder(u, { t: 'move', x: p[0], y: p[1], fx: p[0], fy: p[1] }); }
    }
    this.event({ k: 'trained', id: u.id, p: b.owner });
    this.updatePop();
  }

  exitPoint(b) {
    const tx = b.rally ? b.rally.x : b.x, ty = b.rally ? b.rally.y : b.y - 10;
    const a = Math.atan2(ty - b.y, tx - b.x);
    const r = Math.max(b.w, b.h) / 2 + 0.8;
    return this.grid.nearestFree(b.x + Math.cos(a) * r, b.y + Math.sin(a) * r, 8) || [b.x, b.y - r];
  }

  towerTick(b) {
    if (b.cd > 0) { b.cd -= DT; return; }
    const A = b.def.attack;
    const t0 = this.byId.get(b.towerT);
    let t = t0 && this.canTarget(b, t0) && this.gap(t0, b) <= A.range ? t0 : null;
    if (!t && (this.tick + b.id) % 4 === 0) {
      let bd = Infinity;
      this.query(b.x, b.y, A.range + 2, u => {
        if (!this.canTarget(b, u)) return;
        const d = this.gap(u, b);
        if (d <= A.range && d < bd) { bd = d; t = u; }
      });
    }
    if (!t) return;
    b.towerT = t.id;
    b.cd = A.cooldown;
    const amt = this.rng.int(A.damage[0], A.damage[1]);
    this.projectiles.push({ id: this.nextId++, src: b.id, owner: b.owner, team: b.team, target: t.id, x: b.x, y: b.y, z: 4, speed: 24, kind: 'bolt', dmg: amt, atk: A.attack_type });
    this.event({ k: 'proj', id: this.projectiles.at(-1).id, src: b.id, target: t.id, kind: 'bolt', z0: 4.2 });
  }
}

function mass(u) {
  const o = u.order.t;
  if (u.mods?.stunned || u.mods?.rooted) return 50;
  if (o === 'hold') return 12;
  if (u.swing > 0 || u.engaged && (u.anim === 'Attack')) return 5;
  if (o === 'construct' || (o === 'gather' && u.order.phase === 'work')) return 6;
  if (u.vx || u.vy) return 1;
  return 1.6;
}

function e_guard(w, t, src) {
  w.setOrder(t, { t: 'guard', target: src.id, hx: t.x, hy: t.y });
  t.orders.unshift({ t: 'move', x: t.x, y: t.y, fx: t.x, fy: t.y, gid: 0 });
}
