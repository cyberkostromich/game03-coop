import { loadD } from './headless.mjs';
import { World, HZ } from '../src/sim/world.js';
import { AllyAI } from '../src/sim/ally.js';
const D = loadD();
const w = new World(D, { players: [{ name: 'AI', faction: 'cats', ai: true }], seed: 3 });
const ai = new AllyAI(w, 0);
for (let i = 0; i < 7 * 60 * HZ; i++) { ai.tick(); w.step(); w.events.length = 0; }
for (const u of w.units.filter(u => u.alive && u.owner === 4)) {
  const t = w.byId.get(u.order.target);
  console.log(u.id, u.type, u.x.toFixed(1), u.y.toFixed(1), 'order', u.order.t, 'tgt', t ? `${t.type} ${t.owner} ${t.x.toFixed(0)},${t.y.toFixed(0)} alive=${t.alive}` : '-', 'goal', u.order.x?.toFixed(0), u.order.y?.toFixed(0), 'free', w.grid.freeAt(u.x, u.y), 'wave', u.wave, 'anim', u.anim);
}
