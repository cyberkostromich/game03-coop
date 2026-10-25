// Game data loader: every number lives in data/*.json (GDD rule).
// <meta name="ak-base"> points at the folder holding data/ and assets/:
// "../" when served from the repo, "./" inside the published bundle.
const base = document.querySelector('meta[name="ak-base"]')?.content ?? '../';
export const BASE = new URL(base, document.baseURI).href;
export const DATA = BASE + 'data/';
export const ASSETS = BASE + 'assets/animal_kingdoms/';

async function json(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`load failed: ${url}`);
  return r.json();
}

async function bin(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`load failed: ${url}`);
  return r.arrayBuffer();
}

export async function loadData(progress = () => {}) {
  const names = ['units', 'buildings', 'heroes', 'factions', 'damage_matrix', 'economy', 'waves', 'creeps'];
  const D = {};
  await Promise.all(names.map(async n => { D[n] = await json(DATA + n + '.json'); }));
  progress(0.05);
  D.map = await json(DATA + 'maps/mill_pond.json');
  const [h, p] = await Promise.all([bin(ASSETS + 'maps/mill_pond_height.bin'), bin(ASSETS + 'maps/mill_pond_path.bin')]);
  D.mapBin = { height: new Uint16Array(h), path: new Uint8Array(p) };
  const [ua, ba, pa] = await Promise.all([
    json(ASSETS + 'units/units.json').catch(() => ({})),
    json(ASSETS + 'buildings/buildings.json').catch(() => ({})),
    json(ASSETS + 'props/props.json').catch(() => ({})),
  ]);
  D.unitAssets = ua; D.buildingAssets = ba; D.propAssets = pa;
  progress(0.1);
  return D;
}
