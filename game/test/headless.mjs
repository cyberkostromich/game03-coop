// Headless soak test: runs the simulation without a browser and checks
// invariants (no exceptions, economy flows, waves spawn, units don't get
// stuck inside blockers).
import fs from 'node:fs';
import { World, HZ } from '../src/sim/world.js';

const ROOT = new URL('../../', import.meta.url).pathname;
const J = p => JSON.parse(fs.readFileSync(ROOT + p, 'utf8'));
export function loadD() {
  const D = {};
  for (const n of ['units', 'buildings', 'heroes', 'factions', 'damage_matrix', 'economy', 'waves', 'creeps']) D[n] = J(`data/${n}.json`);
  D.map = J('data/maps/mill_pond.json');
  const h = fs.readFileSync(ROOT + 'assets/animal_kingdoms/maps/mill_pond_height.bin');
  const p = fs.readFileSync(ROOT + 'assets/animal_kingdoms/maps/mill_pond_path.bin');
  D.mapBin = { height: new Uint16Array(h.buffer, h.byteOffset, h.length / 2), path: new Uint8Array(p.buffer, p.byteOffset, p.length) };
  return D;
}

if (process.argv[1].endsWith('headless.mjs')) {
  const D = loadD();
  const factions = (process.argv[2] || 'cats,dogs').split(',');
  const minutes = +(process.argv[3] || 6);
  const w = new World(D, { players: factions.map((f, i) => ({ name: 'P' + i, faction: f, color: '#c33' })), seed: 7, difficulty: 'normal' });
  const t0 = performance.now();
  const P = w.players;
  // script: all workers gather gold; train workers, build farm + barracks, train army
  const my = (p, f) => w.ents.filter(e => e.alive && e.owner === p && f(e));
  for (const p of P) {
    const ws = my(p.id, e => e.kind === 'unit');
    const mine = w.nearest(p.home.x, p.home.y, e => e.type === 'gold_mine');
    w.issue({ p: p.id, t: 'smart', ids: ws.slice(0, 4).map(e => e.id), target: mine.id, x: mine.x, y: mine.y });
    const tree = w.nearest(p.home.x, p.home.y, e => e.kind === 'tree');
    w.issue({ p: p.id, t: 'smart', ids: [ws[4].id], target: tree.id, x: tree.x, y: tree.y });
  }
  let maxTick = 0, slow = 0; const seen = new Set();
  const N = minutes * 60 * HZ;
  for (let i = 0; i < N; i++) {
    if (i % 100 === 50) for (const p of P) {
      const F = D.factions[p.faction];
      const hall = my(p.id, e => e.type === F.hall)[0];
      if (hall && hall.queue.length < 2 && my(p.id, e => e.def?.gatherer).length < 12) w.issue({ p: p.id, t: 'train', building: hall.id, unit: F.worker });
      const idle = my(p.id, e => e.kind === 'unit' && e.def.gatherer && e.order.t === 'idle');
      for (const u of idle) {
        const tree = w.nearest(u.x, u.y, e => e.kind === 'tree');
        w.issue({ p: p.id, t: 'gather', ids: [u.id], target: tree.id });
      }
      const pre = p.faction.slice(0, 3) === 'ham' ? 'ham' : p.faction.slice(0, -1) === 'hare' ? 'hare' : p.faction.slice(0, 3);
      const tryBuild = (type) => {
        const d = w.defs.buildings[type];
        const builder = my(p.id, e => e.def?.gatherer && e.order.t === 'gather' && !e.hidden)[0];
        if (!builder) return;
        for (let k = 0; k < 40; k++) {
          const a = k * 0.9, r = 9 + k * 0.4;
          const x = Math.round(p.home.x + Math.cos(a) * r), y = Math.round(p.home.y + Math.sin(a) * r);
          if (w.grid.canPlace(x, y, d.w, d.h)) { w.issue({ p: p.id, t: 'build', ids: [builder.id], type, x, y, queue: false }); return; }
        }
      };
      const prefix = F.hall.split('_')[0];
      if (p.popCap - p.popUsed < 4 && !my(p.id, e => e.type === prefix + '_farm' && e.built < 1).length && !my(p.id, e => e.order?.t === 'build').length) tryBuild(prefix + '_farm');
      if (i > 1200 && !my(p.id, e => e.type === prefix + '_barracks').length && !my(p.id, e => e.order?.t === 'build').length) tryBuild(prefix + '_barracks');
      const bar = my(p.id, e => e.type === prefix + '_barracks' && e.built >= 1)[0];
      if (bar && bar.queue.length < 2) w.issue({ p: p.id, t: 'train', building: bar.id, unit: bar.def.produces[i / 100 % 2 | 0] });
      if (hall && i === 2400) w.issue({ p: p.id, t: 'train', building: hall.id, unit: 'hero:' + F.heroes[0] });
      const heroes = my(p.id, e => e.def?.hero);
      for (const h of heroes) for (const k of ['Q', 'W', 'E', 'R']) w.issue({ p: p.id, t: 'learn', id: h.id, key: k });
    }
    const a = performance.now();
    w.step();
    const dt = performance.now() - a;
    if (dt > maxTick) { maxTick = dt; var worstAt = i; } if (dt > 25) slow++;
    for (const ev of w.events) if (ev.k === 'msg' && (ev.kind === 'alert' || ev.kind === 'error' && !seen.has(ev.text) && seen.add(ev.text))) console.log(`[${(w.tick / HZ).toFixed(0)}s] ${ev.text}`);
    w.events.length = 0;
  }
  const el = performance.now() - t0;
  console.log(`ran ${N} ticks in ${el.toFixed(0)} ms (${(el / N).toFixed(2)} ms/tick, worst ${maxTick.toFixed(1)} ms, ${slow} ticks > 25ms) worst at ${worstAt}`);
  for (const p of P) {
    const units = my(p.id, e => e.kind === 'unit');
    const bs = my(p.id, e => e.kind === 'building');
    console.log(p.name, p.faction, `gold ${p.gold | 0} wood ${p.wood | 0} food ${p.food | 0} pop ${p.popUsed}/${p.popCap} mined ${p.mined}`,
      'units', units.length, Object.entries(units.reduce((m, u) => (m[u.type] = (m[u.type] || 0) + 1, m), {})).map(x => x.join(':')).join(' '),
      '| bld', bs.map(b => b.type + (b.built < 1 ? '(' + (b.built * 100 | 0) + '%)' : '')).join(' '));
    const orders = units.reduce((m, u) => (m[u.order.t + (u.order.phase ? '/' + u.order.phase : '')] = (m[u.order.t + (u.order.phase ? '/' + u.order.phase : '')] || 0) + 1, m), {});
    console.log('   orders', JSON.stringify(orders));
    for (const h of units.filter(u => u.def.hero)) console.log('   hero', h.type, 'lvl', h.level, 'xp', h.xp | 0, JSON.stringify(h.skill));
  }
  const rats = w.ents.filter(e => e.alive && e.owner === 4 && e.kind === 'unit');
  console.log('rats alive', rats.length, 'waves sent', w.director.n, 'result', w.result);
  const stuck = w.ents.filter(e => e.alive && e.kind === 'unit' && !e.hidden && !w.grid.freeAt(e.x, e.y));
  console.log('units on blocked cells', stuck.length, stuck.slice(0, 5).map(e => [e.type, e.x.toFixed(1), e.y.toFixed(1)]));
}
