// Map validation: every start can walk to every mine, camp, pit and ally.
import { loadD } from './headless.mjs';
import { World } from '../src/sim/world.js';
const D = loadD();
const w = new World(D, { players: [0, 1, 2, 3].map(i => ({ name: 'P' + i, faction: ['cats', 'dogs', 'hamsters', 'hares'][i] })), seed: 1 });
const g = w.grid;
let bad = 0;
for (const p of w.players) {
  const f = g.field('reach' + p.id, [g.idx(...g.nearestFree(p.home.x, p.home.y - 5))]);
  const check = (name, x, y, r) => {
    let ok = false;
    g.forCells(x, y, r, i => { if (isFinite(f.cost[i])) ok = true; });
    if (!ok) { bad++; console.log('UNREACHABLE from', p.faction, name, x, y); }
  };
  for (const m of D.map.gold_mines) check('mine', m.x, m.y, 4);
  for (const c of D.map.camps) check('camp ' + c.level, c.x, c.y, 3);
  for (const pit of D.map.rat_pits) check('pit', pit.x, pit.y, 4);
  for (const s of D.map.starts) check('start', s.x, s.y, 5);
  // rat spawn ring around each pit must reach this player too
  for (const pit of D.map.rat_pits) for (let k = 0; k < 8; k++) {
    const a = k * Math.PI / 4, q = g.nearestFree(pit.x + Math.cos(a) * 3.5, pit.y + Math.sin(a) * 3.5, 10);
    if (q && !isFinite(f.cost[g.idx(q[0], q[1])])) { bad++; console.log('pit spawn cut off', pit.x, pit.y, q); }
  }
}
console.log(bad ? `FAIL ${bad}` : 'map OK: everything reachable');
