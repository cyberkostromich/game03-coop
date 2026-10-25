// Melee: four computer kingdoms fight until one team is left.
import { loadD } from './headless.mjs';
import { World, HZ } from '../src/sim/world.js';
import { AllyAI } from '../src/sim/ally.js';
const D = loadD();
const teams = (process.argv[2] || '0,1,2,3').split(',').map(Number);
const facs = ['cats', 'dogs', 'hamsters', 'hares'].slice(0, teams.length);
const w = new World(D, { mode: 'melee', rats: process.argv[3] === 'rats', players: facs.map((f, i) => ({ name: f, faction: f, ai: true, team: teams[i] })), seed: 4 });
const ais = facs.map((f, i) => new AllyAI(w, i));
for (let i = 0; i < 45 * 60 * HZ && !w.result; i++) {
  for (const a of ais) a.tick();
  w.step();
  for (const e of w.events) if (e.k === 'msg' && e.text.includes('выбывает')) console.log(`[${(w.time / 60).toFixed(1)}m] ${e.text}`);
  w.events.length = 0;
  if (i % (5 * 60 * HZ) === 0 && i) console.log(`  ${i / HZ / 60}m`, w.players.map(p => `${p.faction}: army ${w.units.filter(u => u.alive && u.owner === p.id && !u.def.gatherer).length} bld ${w.blds.filter(b => b.alive && b.owner === p.id).length}`).join(' | '));
}
console.log('RESULT', w.result, 'winner team', w.winner, 'at', (w.time / 60).toFixed(1), 'min');
