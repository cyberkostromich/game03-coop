// Full match with computer players only: balance and stability check.
import { loadD } from './headless.mjs';
import { World, HZ } from '../src/sim/world.js';
import { AllyAI } from '../src/sim/ally.js';
const D = loadD();
const facs = (process.argv[2] || 'cats').split(',');
const diff = process.argv[3] || 'normal';
const w = new World(D, { players: facs.map((f, i) => ({ name: 'AI' + i, faction: f, ai: true })), seed: +(process.argv[4] || 3), difficulty: diff });
const ais = facs.map((f, i) => new AllyAI(w, i));
const t0 = performance.now();
let worst = 0;
for (let i = 0; i < 30 * 60 * HZ && !w.result; i++) {
  for (const a of ais) a.tick();
  const s = performance.now();
  w.step();
  worst = Math.max(worst, performance.now() - s);
  for (const e of w.events) if (e.k === 'wave' || (e.k === 'msg' && e.kind === 'alert' && !e.text.includes('пал'))) console.log(`[${(w.tick / HZ / 60).toFixed(1)}m]`, e.k === 'wave' ? `wave ${e.n} (${e.count})` : e.text);
  w.events.length = 0;
  if (i % (60 * HZ) === 0 && i) {
    const s2 = w.players.map(p => `${p.faction}: army ${w.units.filter(u => u.alive && u.owner === p.id && !u.def.gatherer).length} wrk ${w.units.filter(u => u.alive && u.owner === p.id && u.def.gatherer).length} g${p.gold | 0} T${p.tier} pop ${p.popUsed}/${p.popCap}`).join(' | ');
    const rats = w.units.filter(u => u.alive && u.owner === 4).length;
    console.log(`  ${i / HZ / 60}m ${s2} | rats ${rats} pits ${w.blds.filter(b => b.alive && b.type === 'rat_pit').length}`);
  }
}
console.log('RESULT', w.result, 'at', (w.time / 60).toFixed(1), 'min; sim', ((performance.now() - t0) / 1000).toFixed(1), 's; worst tick', worst.toFixed(1), 'ms');
