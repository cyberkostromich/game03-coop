// Determinism: two worlds fed the same commands stay identical; a world
// restored from a snapshot continues identically.
import { loadD } from './headless.mjs';
import { World } from '../src/sim/world.js';
import { AllyAI } from '../src/sim/ally.js';
const D = loadD();
const mk = () => new World(D, { players: [{ name: 'a', faction: 'cats' }, { name: 'b', faction: 'dogs', ai: true }], seed: 5 });
const a = mk(), b = mk();
const ai = [new AllyAI(a, 1)];
const run = (ws, n) => { for (let i = 0; i < n; i++) { for (const x of ai) x.tick(); const cmds = a.cmds.slice(); for (const w of ws) { if (w !== a) w.cmds.push(...cmds.map(c => ({ ...c }))); w.step(); w.events.length = 0; } } };
run([a, b], 4000);
console.log('lockstep same', a.stateHash() === b.stateHash(), 'tick', a.tick, 'units', a.units.filter(u => u.alive).length);
const c = mk(); c.restore(a.serialize());
run([a, c], 3000);
console.log('restored same', a.stateHash() === c.stateHash(), a.stateHash(), c.stateHash());
