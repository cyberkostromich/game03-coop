import { loadD } from './headless.mjs';
import { World } from '../src/sim/world.js';
const D = loadD();
const w = new World(D, { players: [{ name: 'P0', faction: 'cats' }], seed: 7 });
const ws = w.ents.filter(e => e.owner === 0 && e.kind === 'unit');
const mine = w.nearest(-62, -58, e => e.type === 'gold_mine');
const hall = w.ents.find(e => e.type === 'cat_hall');
console.log('hall', hall.x, hall.y, 'mine', mine.x, mine.y, mine.w, mine.h, 'goals', w.ringCells(mine).length);
w.issue({ p: 0, t: 'smart', ids: [ws[0].id], target: mine.id, x: mine.x, y: mine.y });
for (let i = 0; i < 400; i++) {
  w.step();
  const u = ws[0];
  if (i % 20 === 0) console.log(i, u.x.toFixed(2), u.y.toFixed(2), u.order.t, u.order.phase, 'gap', w.gap(u, mine).toFixed(2), 'wp', u.wp && u.wp.map(v => v.toFixed(1)).join(','), 'v', u.vx.toFixed(2), u.vy.toFixed(2), u.hidden, u.carry.amt);
}
