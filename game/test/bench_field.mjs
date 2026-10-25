import { loadD } from './headless.mjs';
import { World } from '../src/sim/world.js';
const w = new World(loadD(), { players: [{ name: 'P0', faction: 'cats' }], seed: 7 });
const g = w.grid;
let t = performance.now();
for (let k = 0; k < 20; k++) { g.version++; g.field('x' + k, [g.idx(-60 + k, -50)]); }
console.log('field ms', ((performance.now() - t) / 20).toFixed(2));
