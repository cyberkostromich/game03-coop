// Normalised definitions built once from data/*.json.

export const RATS = 4, NEUTRAL = 5;

const RADIUS = { worker: 0.38, infantry: 0.46, ranged: 0.42, support: 0.44, elite: 0.56, boss: 1.1 };
const PROJECTILE_SPEED = { bolt: 26, arrow: 22, seed: 17, magic: 15, flask: 13 };

export function buildDefs(D) {
  const units = {}, buildings = {};
  for (const [id, u] of Object.entries(D.units)) {
    units[id] = {
      id, kind: 'unit', name: u.name || D.unitAssets?.[u.model || id]?.name || id, faction: u.faction, role: u.role,
      hp: u.hp, mana: 0, armor: u.armor, armorType: u.armor_type,
      dmg: u.damage, atkType: u.attack_type, cooldown: u.cooldown, range: u.range,
      speed: u.speed, sight: Math.max(10, u.sight || 10), pop: u.pop || 0, cost: u.cost, buildTime: u.build_time || 20,
      tier: u.tier || 1, model: u.model || id, gatherer: !!u.gatherer, carryMult: u.carry_mult || 1,
      projectile: u.range > 2 ? (u.projectile || (u.attack_type === 'fire' ? 'flask' : 'arrow')) : null,
      r: id === 'ham_barrel' ? 0.66 : (RADIUS[u.role] || 0.45),
      pack: u.pack || 0, detects: !!u.detects, nightInvisible: !!u.night_invisible,
      heals: u.heals || 0, boss: !!u.boss, leap: !!u.leap,
    };
  }
  for (const [key, h] of Object.entries(D.heroes)) {
    const id = 'hero:' + key;
    units[id] = {
      id, kind: 'unit', hero: true, key, name: h.name, faction: h.faction, role: 'hero', heroRole: h.role,
      hp: h.hp, mana: h.mana, armor: h.armor, armorType: 'hero', dmg: h.damage, atkType: 'hero',
      cooldown: h.cooldown, range: h.range, speed: h.speed, sight: 12, pop: h.pop || 5, cost: h.cost,
      buildTime: 45, tier: 1, model: h.model, perLevel: h.per_level, maxLevel: h.max_level || 10,
      ultLevel: h.ult_level || 6, abilities: h.abilities, primary: h.primary,
      projectile: h.range > 2 ? 'magic' : null, r: 0.55,
    };
  }
  for (const [id, b] of Object.entries(D.buildings)) {
    buildings[id] = {
      id, kind: 'building', name: b.name || D.buildingAssets?.[id]?.name || id, faction: b.faction, role: b.role,
      hp: b.hp, armor: b.armor ?? 5, armorType: b.armor_type || 'fortified', cost: b.cost || { gold: 0, wood: 0, food: 0 },
      buildTime: b.build_time || 30, w: b.footprint[0], h: b.footprint[1], produces: b.produces || [],
      pop: b.pop || 0, tier: b.tier || 1, model: b.model || id, dropoff: b.dropoff || [],
      attack: b.attack || null, foodTrickle: b.food_trickle || 0, upgrades: b.upgrades || [],
      gold: b.gold || 0, aura: b.aura || null, sight: b.role === 'town_hall' ? 15 : b.role === 'tower' ? 12 : 9,
    };
  }
  return { units, buildings, PROJECTILE_SPEED };
}

// armour reduction, WC3 formula: negative armour amplifies damage
export function armorFactor(a, per) {
  if (a >= 0) return 1 - (a * per) / (1 + a * per);
  return 2 - Math.pow(1 - per, -a);
}

export function lvl(v, level) {
  if (!Array.isArray(v)) return v;
  return v[Math.max(0, Math.min(v.length - 1, level - 1))];
}
