import { loadD } from './headless.mjs';
import { World } from '../src/sim/world.js';
const w = new World(loadD(), { players: [{ name: 'P', faction: 'cats' }], seed: 11 });
const camp = w.D.map.camps.find(c => c.level === 'yellow');
const h = w.spawnUnit('hero:murena', 0, camp.x, camp.y - 6);
w.players[0].heroes.push(h.id);
const creeps = w.units.filter(u => u.camp && u.camp.x === camp.x && u.camp.y === camp.y);
let it = null;
for (let tries = 0; tries < 20 && !it; tries++) {
  for (const c of creeps) if (c.alive) w.kill(c, h);
  it = w.ents.find(e => e.kind === 'item' && e.alive);
  if (!it) { w.dropLoot(camp, camp.x, camp.y); it = w.ents.find(e => e.kind === 'item' && e.alive); }
}
console.log('dropped', it?.type);
const pot = w.dropItem('heal_potion', camp.x + 1, camp.y);
w.issue({ p: 0, t: 'smart', ids: [h.id], target: it.id, x: it.x, y: it.y });
for (let i = 0; i < 200; i++) w.step();
w.issue({ p: 0, t: 'smart', ids: [h.id], target: pot.id, x: pot.x, y: pot.y, queue: false });
for (let i = 0; i < 100; i++) w.step();
console.log('inventory', JSON.stringify(h.items), 'xp', h.xp, 'lvl', h.level, 'mods dmgFlat', h.mods.dmgFlat, 'armor+', h.mods.armor);
h.hp = 100;
const slot = h.items.findIndex(s => s?.type === 'heal_potion');
w.issue({ p: 0, t: 'useitem', id: h.id, slot });
w.step();
console.log('hp after potion', Math.round(h.hp), 'items', JSON.stringify(h.items));
