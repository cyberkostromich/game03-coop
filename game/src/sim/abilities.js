// Hero progression, buffs, auras and the data-driven ability interpreter.
//
// Abilities come from data/heroes.json: a cast type (target_unit, point,
// no_target, aura, passive, channel, target_building) and a list of effect
// records. Each effect kind has one handler below; ground effects become
// zones that tick on their own.
import { lvl, RATS, NEUTRAL } from './defs.js';

const HZ = 20, DT = 1 / HZ;
const MAX_SKILL = { Q: 3, W: 3, E: 3, R: 1 };

export class Abilities {
  constructor(w) { this.w = w; }

  // ------------------------------------------------------------ progression
  initHero(e) {
    e.level = 1; e.xp = 0; e.points = 1;
    e.skill = { Q: 0, W: 0, E: 0, R: 0 };
    e.cds = { Q: 0, W: 0, E: 0, R: 0 };
    e.items = [];
    e.dmgBonus = 0;
    e.manaRegen = e.def.primary === 'int' ? 1.1 : 0.75;
  }

  restoreHero(e, h) {
    while (e.level < h.level) this.levelUp(e, true);
    e.xp = h.xp; e.skill = { ...h.skill }; e.points = h.points; e.items = h.items || [];
    e.hp = e.maxHp; e.mana = e.maxMana;
  }

  xpFor(level) { return this.w.D.economy.heroes.xp_levels[level] ?? Infinity; }

  levelUp(e, silent = false) {
    const d = e.def, pl = d.perLevel;
    e.level++; e.points++;
    e.maxHp += pl.hp; e.hp += pl.hp;
    e.maxMana += pl.mana; e.mana += pl.mana;
    e.dmgBonus += pl.damage; e.armor += pl.armor;
    if (!silent) this.w.event({ k: 'level', id: e.id, level: e.level });
  }

  grantXp(dead, killer) {
    const w = this.w, H = w.D.economy.heroes;
    let xp;
    if (dead.kind === 'building') xp = 40;
    else if (dead.def.hero) xp = H.hero_kill_xp * (dead.level || 1);
    else xp = H.kill_xp_per_pop * Math.max(1, dead.def.pop) * (dead.camp ? H.creep_xp_mult : 1) * (dead.def.boss ? 10 : 1);
    const heroes = [];
    w.query(dead.x, dead.y, H.xp_radius, u => { if (u.def.hero && u.team === killer.team && u.alive && !u.summoned) heroes.push(u); });
    if (!heroes.length) return;
    const share = xp / heroes.length;
    for (const h of heroes) {
      if (h.level >= h.def.maxLevel) continue;
      h.xp += share;
      while (h.level < h.def.maxLevel && h.xp >= this.xpFor(h.level)) this.levelUp(h);
    }
  }

  learn(e, key) {
    if (!e.def.hero || e.points <= 0) return;
    const cur = e.skill[key];
    if (cur >= MAX_SKILL[key]) return;
    if (key === 'R' && e.level < e.def.ultLevel) return;
    if (key !== 'R' && e.level < cur * 2 + 1) return;
    e.skill[key]++; e.points--;
    this.w.event({ k: 'learn', id: e.id, key });
  }

  ability(e, key) { return e.def.abilities?.find(a => a.key === key); }

  canLearn(e, key) {
    if (!e.def.hero || e.points <= 0) return false;
    const cur = e.skill[key];
    if (cur >= MAX_SKILL[key]) return false;
    if (key === 'R') return e.level >= e.def.ultLevel;
    return e.level >= cur * 2 + 1;
  }

  // ------------------------------------------------------------------ orders
  order(u, key, c, queue) {
    const a = this.ability(u, key);
    if (!a || !u.skill || u.skill[key] <= 0) return;
    if (a.type === 'aura' || a.type === 'passive') return;
    const why = this.blocked(u, key, a);
    if (why) { this.w.msg(u.owner, why, 'error'); return; }
    const o = { t: 'cast', key, target: c.target || 0, x: c.x, y: c.y };
    if (a.type === 'target_unit' || a.type === 'target_building') {
      const t = this.w.byId.get(c.target);
      if (!t || !t.alive) return;
      if (!this.validTarget(u, a, t)) { this.w.msg(u.owner, 'Неверная цель', 'error'); return; }
    }
    this.w.order(u, o, queue);
  }

  blocked(u, key, a) {
    if (u.cds[key] > 0) return 'Способность ещё не готова';
    if (u.mana < a.mana) return 'Недостаточно маны';
    return null;
  }

  validTarget(u, a, t) {
    const kinds = a.effects.map(e => e.kind);
    if (a.type === 'target_building') return t.kind === 'building' && t.owner === u.owner;
    if (kinds.includes('redirect_damage') || kinds.includes('invulnerable_heal')) return t.kind === 'unit' && t.team === u.team;
    if (kinds.includes('convert_neutral')) return t.kind === 'unit' && t.owner === NEUTRAL && !t.def.boss;
    if (kinds.includes('damage') && a.effects.find(e => e.vs_buildings)) return this.w.isHostile(u, t);
    return t.kind === 'unit' && this.w.isHostile(u, t);
  }

  castRange(u, a) {
    if (a.type === 'no_target' || a.type === 'channel') return Infinity;
    return Math.max(a.range || 0, 1.2);
  }

  castTick(e, o) {
    const w = this.w, a = this.ability(e, o.key);
    if (!a) { w.nextOrder(e); return; }
    let tx = o.x, ty = o.y, t = null;
    if (o.target) {
      t = w.byId.get(o.target);
      if (!t || !t.alive) { w.nextOrder(e); return; }
      tx = t.x; ty = t.y;
    }
    const range = this.castRange(e, a);
    if (isFinite(range)) {
      const d = t ? w.gap(e, t) : Math.hypot(tx - e.x, ty - e.y);
      if (d > range) {
        if (t) w.moveToEnt(e, t, range * 0.9); else w.moveTo(e, tx, ty, range * 0.9, null);
        w.anim(e, 'Walk');
        return;
      }
      w.face(e, tx, ty, true);
    }
    const why = this.blocked(e, o.key, a);
    if (why) { w.msg(e.owner, why, 'error'); w.nextOrder(e); return; }
    e.castT = 0.3;
    e.pending = { key: o.key, target: o.target, x: tx, y: ty };
    w.anim(e, e.def.hero ? 'Cast' : 'Attack', 0.6);
    w.nextOrder(e);
  }

  release(e) {
    const p = e.pending; e.pending = null;
    if (!p || !e.alive) return;
    const w = this.w, a = this.ability(e, p.key);
    if (!a || e.mana < a.mana || e.cds[p.key] > 0) return;
    const L = e.skill[p.key] || 1;
    e.mana -= a.mana;
    e.cds[p.key] = a.cooldown;
    const t = p.target ? w.byId.get(p.target) : null;
    if (p.target && (!t || !t.alive)) return;
    const ctx = { e, a, L, t, x: t ? t.x : p.x ?? e.x, y: t ? t.y : p.y ?? e.y, targets: null };
    ctx.targets = this.areaTargets(ctx);
    w.event({ k: 'cast', id: e.id, key: p.key, vfx: a.vfx, x: ctx.x, y: ctx.y, target: p.target || 0, r: a.radius });
    for (const fx of a.effects) {
      const h = EFFECTS[fx.kind];
      if (h) h(this, ctx, fx);
    }
    this.breakInvis(e);
  }

  areaTargets({ e, a, t, x, y }) {
    const w = this.w;
    if (t) return [t];
    if (!a.radius) return [];
    const out = [];
    const cone = a.effects.some(f => f.kind === 'stun_cone');
    const cx = cone ? e.x : x, cy = cone ? e.y : y;
    const dir = Math.atan2(y - e.y, x - e.x);
    w.query(cx, cy, a.radius + (cone ? a.range : 0) + 0.5, u => {
      if (!w.canTarget(e, u)) return;
      if (cone) {
        const d = Math.hypot(u.x - e.x, u.y - e.y);
        let da = Math.atan2(u.y - e.y, u.x - e.x) - dir;
        while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
        if (d > a.range + 0.5 || Math.abs(da) > 0.75) return;
      }
      out.push(u);
    });
    return out;
  }

  // ------------------------------------------------------------------ buffs
  buff(u, b) {
    if (!u || !u.alive) return;
    if (u.mods?.ccImmune && (b.kind === 'stun' || b.kind === 'root' || b.kind === 'taunt')) return;
    b.until = this.w.tick + Math.round((b.dur ?? 1) * HZ);
    if (b.tag) {                                 // same tag refreshes instead of stacking
      const old = u.buffs.find(x => x.tag === b.tag);
      if (old) { Object.assign(old, b); return; }
    }
    u.buffs.push(b);
  }

  breakInvis(e) {
    if (!e.buffs.some(b => b.kind === 'invis')) return;
    e.buffs = e.buffs.filter(b => b.kind !== 'invis');
  }

  preventDeath(t) {
    if (!t.def.hero || !t.skill) return false;
    const a = this.ability(t, 'E');
    if (!a || t.skill.E <= 0 || t.cds.E > 0 || !a.effects.some(f => f.kind === 'revive')) return false;
    const f = a.effects.find(f => f.kind === 'revive');
    t.hp = Math.round(t.maxHp * f.hp);
    t.cds.E = a.cooldown;
    this.w.event({ k: 'fx', fx: 'revive', id: t.id, x: t.x, y: t.y });
    this.w.msg(t.owner, `${t.def.name}: одна из девяти жизней`, 'info');
    return true;
  }

  incomeBonus(owner) {
    const mill = this.w.millHolder;
    return mill === 0 ? (this.w.D.buildings.mill?.aura?.income || 0) : 0;
  }

  trainBonus(b) {
    let s = 0;
    for (const x of b.buffs) if (x.kind === 'train' && x.until > this.w.tick) s += x.value;
    return s;
  }

  refreshMods(u) {
    const w = this.w;
    const m = { speed: 1, atkSpeed: 1, dmg: 1, armor: 0, evasion: 0, miss: 0, dmgTaken: 1, invisible: false,
                stunned: false, rooted: false, taunted: 0, reflect: false, redirect: null, ccImmune: false, gather: 0, keepInvis: false };
    let packMult = 1, firstStrike = 0;
    for (const b of u.buffs) {
      switch (b.kind) {
        case 'stat':
          if (b.stat === 'attack_speed') m.atkSpeed += b.value;
          else if (b.stat === 'move_speed') m.speed += b.value;
          else if (b.stat === 'damage') m.dmg += b.value;
          else if (b.stat === 'armor') m.armor += b.value;
          else if (b.stat === 'gather_rate') m.gather += b.value;
          else if (b.stat === 'pack_mult') packMult = Math.max(packMult, b.value);
          else if (b.stat === 'miss') m.miss = Math.max(m.miss, b.value);
          break;
        case 'stun': case 'fear': m.stunned = true; break;
        case 'root': m.rooted = true; break;
        case 'invis': m.invisible = true; firstStrike = Math.max(firstStrike, b.firstStrike || 0); break;
        case 'evade': m.evasion = Math.max(m.evasion, b.value); break;
        case 'taunt': m.taunted = b.target; break;
        case 'reflect': m.reflect = true; break;
        case 'redirect': m.redirect = { src: b.src, share: b.share }; break;
        case 'ccimmune': m.ccImmune = true; break;
        case 'invuln': m.invuln = true; m.stunned = true; break;
        case 'illusion': m.dmg *= 0.3; m.dmgTaken *= 2; break;
      }
    }
    const d = u.def;
    // passive: thick hide
    if (d.hero && u.skill) {
      const pw = this.ability(u, 'W');
      if (pw?.type === 'passive' && u.skill.W > 0) {
        const f = pw.effects.find(f => f.kind === 'damage_reduction');
        if (f) m.dmgTaken *= 1 - lvl(f.value, u.skill.W);
      }
      const pe = this.ability(u, 'E');
      if (pe?.type === 'passive' && u.skill.E > 0 && pe.effects.some(f => f.kind === 'invisible_when') && w.isNight && w.tick - u.lastCombat > 3 * HZ) m.invisible = true;
    }
    // faction mechanics: cats hunt at night, dogs fight as a pack
    if (d.nightInvisible && w.isNight && w.tick - u.lastCombat > 3 * HZ) { m.invisible = true; firstStrike = Math.max(firstStrike, 2); }
    if (d.pack && (w.tick + u.id) % 10 === 0) {
      let n = 0;
      w.query(u.x, u.y, 6, o => { if (o !== u && o.owner === u.owner && o.def.faction === 'dogs' && !o.def.gatherer) n++; });
      u.packN = n;
    }
    if (d.pack) m.dmg += Math.min(0.3 * packMult, (u.packN || 0) * d.pack * packMult);
    if (w.crusade.until > w.tick && u.team === 0) { m.dmg += 0.3; m.speed += 0.3; }
    if (m.invuln) u.invuln = true; else if (u.invuln && u.kind === 'unit') u.invuln = false;
    m.speed = Math.max(0.25, m.speed);
    m.atkSpeed = Math.max(0.3, m.atkSpeed);
    u.firstStrike = m.invisible ? firstStrike : 0;
    u.mods = m;
  }

  // ------------------------------------------------------------------- tick
  tick() {
    const w = this.w, now = w.tick;
    const aura = now % 10 === 0;
    for (const b of w.blds) if (b.alive && b.buffs.length) b.buffs = b.buffs.filter(x => x.until > now);
    for (const u of w.units) {
      if (!u.alive) continue;
      if (u.buffs.length) {
        let changed = false;
        for (const b of u.buffs) {
          if (b.kind === 'dot') { const s = w.byId.get(b.src) || { team: b.team, owner: -1, mods: {} }; w.damage(s, u, b.dps * DT, 'hero'); }
          else if (b.kind === 'hot' || b.kind === 'invuln') u.hp = Math.min(u.maxHp, u.hp + (b.hps || 0) * DT);
          if (b.until <= now) { changed = true; if (b.then) this.buff(u, b.then); }
        }
        if (changed) u.buffs = u.buffs.filter(b => b.until > now);
        if (!u.alive) continue;
      }
      if (u.def.hero) {
        for (const k in u.cds) if (u.cds[k] > 0) u.cds[k] = Math.max(0, u.cds[k] - DT);
        u.mana = Math.min(u.maxMana, u.mana + u.manaRegen * DT);
        if (aura) this.heroAuras(u);
      }
      if (u.hp < u.maxHp && now - u.lastCombat > 5 * HZ) u.hp = Math.min(u.maxHp, u.hp + (u.def.hero ? 1.2 : 0.35) * DT);
      if (aura && u.def.heals) this.doctorHeal(u);
      if (u.expires && now >= u.expires) { w.event({ k: 'fx', fx: 'vanish', x: u.x, y: u.y }); w.kill(u, null, true); w.event({ k: 'remove', id: u.id }); continue; }
      this.refreshMods(u);
    }
    if (aura) this.millTick();
    this.zonesTick();
  }

  heroAuras(h) {
    const w = this.w;
    for (const key of ['W']) {
      const a = this.ability(h, key);
      if (!a || a.type !== 'aura' || h.skill[key] <= 0) continue;
      const f = a.effects[0], L = h.skill[key];
      const tag = 'aura:' + h.type + key;
      w.query(h.x, h.y, a.radius, u => {
        const enemy = w.isHostile(h, u);
        if (f.target === 'enemies' ? !enemy : enemy) return;
        if (f.target === 'workers' && (!u.def.gatherer || u.owner !== h.owner)) return;
        this.buff(u, { kind: 'stat', stat: f.stat, value: lvl(f.value, L), dur: 0.7, tag });
      });
    }
  }

  doctorHeal(u) {
    const w = this.w;
    let best = null, bf = 0.95;
    w.query(u.x, u.y, 6, o => { if (o.team === u.team && o.alive && o.hp / o.maxHp < bf) { bf = o.hp / o.maxHp; best = o; } });
    if (best) { best.hp = Math.min(best.maxHp, best.hp + u.def.heals * 4); w.event({ k: 'fx', fx: 'heal', id: best.id, x: best.x, y: best.y }); }
  }

  // the Old Mill on the island: whoever holds it gets income and regen
  millTick() {
    const w = this.w;
    const mill = w.blds.find(e => e.type === 'mill');
    if (!mill) return;
    let ours = 0, theirs = 0;
    w.query(mill.x, mill.y, 7, u => { if (u.team === 0) ours++; else if (u.team === 1) theirs++; });
    const prev = w.millHolder;
    if (ours && !theirs) w.millHolder = 0; else if (theirs && !ours) w.millHolder = 1;
    if (prev !== w.millHolder && w.millHolder === 0) w.msg(-1, 'Старая мельница под нашим контролем: +10% золота', 'ally');
    const regen = mill.def.aura?.regen || 0;
    if (regen) w.query(mill.x, mill.y, 7, u => { if (u.team === w.millHolder) u.hp = Math.min(u.maxHp, u.hp + regen * 0.5); });
  }

  zonesTick() {
    const w = this.w, now = w.tick;
    const keep = [];
    for (const z of w.zones) {
      if (z.until <= now) { if (z.cells) w.grid.stamp(z.cells, -1); w.event({ k: 'zoneend', id: z.id }); continue; }
      keep.push(z);
      const src = w.byId.get(z.src) || { team: z.team, owner: z.owner, mods: {}, kind: 'zone' };
      if (z.follow) { const f = w.byId.get(z.follow); if (f && f.alive) { z.x = f.x; z.y = f.y; } }
      switch (z.kind) {
        case 'rain':
          w.query(z.x, z.y, z.r, u => { if (w.isHostile(src, u)) w.damage(src, u, z.dps * DT, 'pierce'); });
          break;
        case 'heal':
          w.query(z.x, z.y, z.r, u => { if (u.team === z.team) u.hp = Math.min(u.maxHp, u.hp + z.hps * DT); });
          break;
        case 'miss':
          if (now % 10 === 0) w.query(z.x, z.y, z.r, u => { if (w.isHostile(src, u)) this.buff(u, { kind: 'stat', stat: 'miss', value: z.value, dur: 0.7, tag: 'misszone' }); });
          break;
        case 'roller': {
          const step = z.speed * DT;
          z.x += z.dx * step; z.y += z.dy * step; z.travel += step;
          w.query(z.x, z.y, z.r + 0.6, u => {
            if (!w.isHostile(src, u) || z.hit.has(u.id)) return;
            z.hit.add(u.id); w.damage(src, u, z.dmg, 'siege');
          });
          if (z.travel >= z.length) z.until = now;
          break;
        }
        case 'waves':
          if (now >= z.nextT && z.left > 0) {
            z.left--; z.nextT = now + 2 * HZ;
            for (let k = 0; k < z.count; k++) {
              const a = k / z.count * Math.PI * 2, p = w.grid.nearestFree(z.x + Math.cos(a) * 1.6, z.y + Math.sin(a) * 1.6) || [z.x, z.y];
              const s = w.spawnUnit(z.unit, z.owner, p[0], p[1]);
              s.summoned = true; s.expires = now + 30 * HZ;
              w.event({ k: 'fx', fx: 'burrow', x: p[0], y: p[1] });
              w.setOrder(s, { t: 'amove', x: z.x, y: z.y, fx: z.x, fy: z.y, gid: z.id });
            }
          }
          break;
      }
    }
    w.zones = keep;
  }

  addZone(z) {
    z.id = this.w.nextId++;
    z.until = this.w.tick + Math.round(z.dur * HZ);
    this.w.zones.push(z);
    this.w.event({ k: 'zone', id: z.id, kind: z.kind, x: z.x, y: z.y, r: z.r, dur: z.dur, follow: z.follow || 0, dx: z.dx, dy: z.dy, speed: z.speed, length: z.length });
    return z;
  }

  summon(e, type, n, dur, x = e.x, y = e.y, extra = {}) {
    const w = this.w, out = [];
    for (let k = 0; k < n; k++) {
      const a = k * 2.399 + e.facing, r = 1.4 + Math.sqrt(k) * 0.9;
      const p = w.grid.nearestFree(x + Math.cos(a) * r, y + Math.sin(a) * r, 8) || [x, y];
      const s = w.spawnUnit(type, e.owner, p[0], p[1], { facing: e.facing });
      s.summoned = true; s.expires = w.tick + Math.round(dur * HZ);
      Object.assign(s, extra);
      w.event({ k: 'fx', fx: 'summon', x: p[0], y: p[1] });
      out.push(s);
    }
    return out;
  }

  // smooth hop used by dash, leap and army leap
  startLeap(u, x, y, dur, onLand) {
    const w = this.w;
    const p = w.grid.nearestFree(x, y, 10) || [u.x, u.y];
    u.orders = [];
    w.setOrder(u, { t: 'leap', x0: u.x, y0: u.y, x1: p[0], y1: p[1], t0: w.tick, dur: Math.max(1, Math.round(dur * HZ)), onLand });
    u.facing = Math.atan2(p[1] - u.y, p[0] - u.x);
    w.anim(u, 'Walk');
    w.event({ k: 'leap', id: u.id, x0: u.x, y0: u.y, x1: p[0], y1: p[1], dur });
  }

  leapTick(u, o) {
    const w = this.w;
    const k = Math.min(1, (w.tick - o.t0) / o.dur);
    u.x = o.x0 + (o.x1 - o.x0) * k; u.y = o.y0 + (o.y1 - o.y0) * k;
    u.hop = Math.sin(k * Math.PI) * Math.min(3, Math.hypot(o.x1 - o.x0, o.y1 - o.y0) * 0.25);
    if (k >= 1) {
      u.hop = 0;
      const f = o.onLand;
      w.nextOrder(u);
      if (f) f();
    }
  }

  bounce(p, t) {
    const w = this.w;
    if (t.alive) this.buff(t, { kind: 'stun', dur: p.stun || 1 });
    if (--p.bounce <= 0) return;
    let next = null, bd = 25;
    w.query(t.x, t.y, 5, u => {
      if (u === t || !w.isHostile({ team: p.team }, u) || !u.alive) return;
      const d = (u.x - t.x) ** 2 + (u.y - t.y) ** 2;
      if (d < bd) { bd = d; next = u; }
    });
    if (!next) return;
    const q = { ...p, id: w.nextId++, x: t.x, y: t.y, target: next.id };
    w.projectiles.push(q);
    w.event({ k: 'proj', id: q.id, src: t.id, target: next.id, kind: p.kind });
  }
}

// ---------------------------------------------------------------- effects
const ownArmy = (w, e, r, x = e.x, y = e.y) => {
  const out = [];
  w.query(x, y, r, u => { if (u.owner === e.owner && u.alive) out.push(u); });
  return out;
};
const allies = (w, e, r, x, y) => {
  const out = [];
  w.query(x, y, r, u => { if (u.team === e.team && u.alive) out.push(u); });
  return out;
};

const EFFECTS = {
  damage(A, c, f) {
    const w = A.w;
    for (const t of c.targets) w.damage(c.e, t, lvl(f.amount, c.L), 'hero', { vsBuildings: f.vs_buildings });
    if (f.vs_buildings) w.event({ k: 'fx', fx: 'burrow', x: c.x, y: c.y });
  },
  dot(A, c, f) {
    for (const t of c.targets) A.buff(t, { kind: 'dot', dps: lvl(f.dps, c.L), dur: f.duration, src: c.e.id, team: c.e.team, tag: 'dot' + c.e.id });
  },
  invisible(A, c, f) {
    const w = A.w;
    for (const u of w.units) if (u.alive && u.owner === c.e.owner)
      A.buff(u, { kind: 'invis', dur: f.duration, firstStrike: f.first_strike, tag: 'night' });
    w.msg(c.e.owner, 'Ночь длинных когтей: армия скрылась во тьме', 'info');
  },
  dash(A, c) {
    const t = c.t, e = c.e;
    const a = Math.atan2(e.y - t.y, e.x - t.x);
    A.startLeap(e, t.x + Math.cos(a) * (t.r + e.r + 0.3), t.y + Math.sin(a) * (t.r + e.r + 0.3), 0.22);
  },
  reflect_melee(A, c, f) { A.buff(c.e, { kind: 'reflect', dur: f.duration, tag: 'reflect' }); },
  leap(A, c, f) {
    const { e, a, L } = c;
    const rest = a.effects.filter(x => x.kind === 'stun_area' || x.kind === 'damage');
    A.startLeap(e, c.x, c.y, 0.6, rest.length ? () => {
      const ctx = { ...c, x: e.x, y: e.y, t: null };
      ctx.targets = A.areaTargets(ctx);
      A.w.event({ k: 'fx', fx: 'slam', x: e.x, y: e.y, r: a.radius });
      for (const r of rest) EFFECTS[r.kind](A, ctx, r);
    } : null);
    c.targets = [];                                // landing effects apply on touchdown
  },
  duel(A, c, f) {
    const { e, t } = c;
    A.buff(t, { kind: 'taunt', target: e.id, dur: f.duration, tag: 'duel' });
    A.buff(t, { kind: 'root', dur: f.duration, tag: 'duelroot' });
    A.buff(e, { kind: 'root', dur: f.duration, tag: 'duelroot' });
    A.addZone({ kind: 'duel', x: (e.x + t.x) / 2, y: (e.y + t.y) / 2, r: 3, dur: f.duration, team: e.team, owner: e.owner, src: e.id });
  },
  heal_area(A, c, f) {
    A.addZone({ kind: 'heal', x: c.e.x, y: c.e.y, r: c.a.radius, hps: lvl(f.hps, c.L), dur: f.duration, team: c.e.team, owner: c.e.owner, src: c.e.id, follow: c.e.id });
  },
  buff(A, c, f) {
    const w = A.w, { e, a, L } = c;
    let list;
    if (f.night_only) {
      list = w.units.filter(u => u.alive && u.owner === e.owner);
      if (!w.isNight) w.msg(e.owner, 'Вой слабее при свете дня', 'info');
    } else if (a.radius) list = allies(w, e, a.radius, a.type === 'point' ? c.x : e.x, a.type === 'point' ? c.y : e.y);
    else list = [e];
    const v = lvl(f.value, L) * (f.night_only && !w.isNight ? 0.5 : 1);
    for (const u of list) {
      const b = { kind: 'stat', stat: f.stat, value: v, dur: f.duration || 15, tag: 'b' + e.type + a.key };
      if (a.key === 'W' && f.stat === 'attack_speed') b.then = { kind: 'stat', stat: 'move_speed', value: -0.35, dur: 3, tag: 'drowsy' };
      A.buff(u, b);
      if (f.slow) A.buff(u, { kind: 'stat', stat: 'move_speed', value: -f.slow, dur: f.duration, tag: 'slow' + a.key });
      if (f.cc_immune) A.buff(u, { kind: 'ccimmune', dur: f.duration, tag: 'ccimm' });
    }
    if (f.fear) w.query(e.x, e.y, 10, u => { if (w.canTarget(e, u) && !u.def.boss) A.buff(u, { kind: 'fear', dur: f.fear, tag: 'fear' }); });
  },
  miss_zone(A, c, f) { A.addZone({ kind: 'miss', x: c.x, y: c.y, r: c.a.radius, value: f.value, dur: f.duration, team: c.e.team, owner: c.e.owner, src: c.e.id }); },
  root_area(A, c, f) {
    for (const t of c.targets) A.buff(t, { kind: 'root', dur: f.duration, tag: 'root' });
    A.addZone({ kind: 'yarn', x: c.x, y: c.y, r: c.a.radius, dur: f.duration, team: c.e.team, owner: c.e.owner, src: c.e.id });
  },
  stun_cone(A, c, f) { for (const t of c.targets) A.buff(t, { kind: 'stun', dur: lvl(f.duration, c.L), tag: 'stun' }); },
  stun_area(A, c, f) { for (const t of c.targets) A.buff(t, { kind: 'stun', dur: lvl(f.duration, c.L), tag: 'stun' }); },
  redirect_damage(A, c, f) { A.buff(c.t, { kind: 'redirect', share: lvl(f.share, c.L), src: c.e.id, dur: f.duration, tag: 'redirect' }); },
  summon(A, c, f) { A.summon(c.e, f.unit, f.count, f.duration); },
  hold(A, c, f) {
    A.buff(c.t, { kind: 'stun', dur: f.duration, tag: 'hold' });
    A.buff(c.e, { kind: 'root', dur: f.duration, tag: 'holdroot' });
  },
  taunt(A, c, f) {
    const w = A.w;
    w.query(c.e.x, c.e.y, c.a.radius, u => { if (w.canTarget(c.e, u) && u.kind === 'unit') A.buff(u, { kind: 'taunt', target: c.e.id, dur: f.duration, tag: 'taunt' }); });
  },
  reveal(A, c, f) { A.addZone({ kind: 'reveal', x: c.e.x, y: c.e.y, r: c.a.radius, dur: f.duration, team: c.e.team, owner: c.e.owner, src: c.e.id, follow: c.e.id }); },
  projectile_bounce(A, c, f) {
    const w = A.w, { e, t } = c;
    const p = { id: w.nextId++, src: e.id, owner: e.owner, team: e.team, target: t.id, x: e.x, y: e.y, z: 1, speed: 16, kind: 'stick', dmg: 40 + 30 * c.L, atk: 'hero', bounce: f.targets, stun: f.stun };
    w.projectiles.push(p);
    w.event({ k: 'proj', id: p.id, src: e.id, target: t.id, kind: 'stick' });
  },
  ward(A, c, f) { A.addZone({ kind: 'ward', x: c.x, y: c.y, r: 9, dur: f.duration, team: c.e.team, owner: c.e.owner, src: c.e.id }); },
  grant_gold(A, c, f) {
    const P = A.w.players[c.e.owner]; if (!P) return;
    const g = lvl(f.amount, c.L); P.gold += g;
    A.w.event({ k: 'bounty', x: c.e.x, y: c.e.y, amt: g, p: P.id });
  },
  convert_neutral(A, c) {
    const t = c.t;
    t.owner = c.e.owner; t.team = 0; t.camp = null;
    t.orders = []; A.w.setOrder(t, { t: 'idle' });
    A.w.event({ k: 'convert', id: t.id });
  },
  team_resources(A, c, f) {
    for (const P of A.w.players) if (P.alive) { P.gold += f.gold; P.wood += f.wood; }
    A.w.msg(-1, `Великая заначка: всем +${f.gold} золота и +${f.wood} дерева`, 'ally');
  },
  line_damage(A, c, f) {
    const e = c.e, len = f.length || c.a.range || 10;
    const a = Math.atan2(c.y - e.y, c.x - e.x);
    const fast = c.a.vfx !== 'q' || e.def.key === 'kosoy';
    A.addZone({ kind: 'roller', x: e.x, y: e.y, dx: Math.cos(a), dy: Math.sin(a), speed: e.def.key === 'kosoy' ? 40 : len > 20 ? 14 : 16,
                travel: 0, length: len, r: len > 20 ? 2.2 : 1.1, dmg: lvl(f.amount, c.L), hit: new Set(), dur: 8,
                team: e.team, owner: e.owner, src: e.id, style: e.def.key === 'kosoy' ? 'arrow' : 'wheel', big: len > 20 });
    void fast;
  },
  turret(A, c, f) {
    const [s] = A.summon(c.e, 'ham_slinger', 1, f.duration, c.x, c.y, { turret: true });
    A.buff(s, { kind: 'root', dur: f.duration, tag: 'turret' });
  },
  invulnerable_heal(A, c, f) { A.buff(c.t, { kind: 'invuln', hps: f.hps, dur: f.duration, tag: 'sleep' }); },
  army_leap(A, c, f) {
    const e = c.e, w = A.w;
    for (const u of ownArmy(w, e, f.radius)) {
      if (u.kind !== 'unit' || u.hidden) continue;
      A.startLeap(u, c.x + (u.x - e.x), c.y + (u.y - e.y), 1.1);
    }
  },
  evasion(A, c, f) { A.buff(c.e, { kind: 'evade', value: f.value, dur: f.duration, tag: 'evade' }); },
  illusions(A, c, f) {
    const s = A.summon(c.e, c.e.type, f.count, f.duration, c.e.x, c.e.y, { illusion: true });
    for (const u of s) {
      u.level = c.e.level; u.skill = { Q: 0, W: 0, E: 0, R: 0 }; u.hp = u.maxHp = c.e.maxHp; u.mana = 0;
      A.buff(u, { kind: 'illusion', dur: f.duration });
      const P = A.w.players[u.owner]; if (P) P.heroes = P.heroes.filter(id => id !== u.id);
    }
  },
  rain(A, c, f) { A.addZone({ kind: 'rain', x: c.x, y: c.y, r: c.a.radius, dps: f.dps, dur: f.duration, team: c.e.team, owner: c.e.owner, src: c.e.id }); },
  barrier(A, c, f) {
    const w = A.w, e = c.e;
    const a = Math.atan2(c.y - e.y, c.x - e.x) + Math.PI / 2;
    const cells = new Set();
    for (let k = -2; k <= 2; k++) w.grid.forCells(c.x + Math.cos(a) * k * 0.9, c.y + Math.sin(a) * k * 0.9, 0.6, i => { if (w.grid.free(i)) cells.add(i); });
    const z = A.addZone({ kind: 'barrier', x: c.x, y: c.y, r: 2.4, rot: a, dur: f.duration, team: e.team, owner: e.owner, src: e.id });
    z.cells = [...cells];
    w.grid.stamp(z.cells, 1);
    w.query(c.x, c.y, 3, u => { if (!w.grid.freeAt(u.x, u.y)) w.unstick(u); });
  },
  grant_food(A, c, f) { const P = A.w.players[c.e.owner]; if (P) P.food += f.amount; },
  teleport_squad(A, c, f) {
    const e = c.e, w = A.w;
    for (const u of ownArmy(w, e, f.radius)) {
      if (u.kind !== 'unit' || u.hidden) continue;
      const p = w.grid.nearestFree(c.x + (u.x - e.x), c.y + (u.y - e.y), 8);
      if (!p) continue;
      w.event({ k: 'fx', fx: 'burrow', x: u.x, y: u.y });
      u.x = p[0]; u.y = p[1]; u.orders = []; w.setOrder(u, { t: 'idle' });
      w.event({ k: 'fx', fx: 'burrow', x: u.x, y: u.y });
      w.event({ k: 'teleport', id: u.id });
    }
  },
  train_speed(A, c, f) { A.buff(c.t, { kind: 'train', value: f.value, dur: f.duration, tag: 'harvest' }); },
  summon_waves(A, c, f) {
    A.addZone({ kind: 'waves', x: c.x, y: c.y, r: 2.5, unit: f.unit, count: f.count, left: f.waves, nextT: A.w.tick, dur: f.waves * 2 + 1, team: c.e.team, owner: c.e.owner, src: c.e.id });
  },
  aura() {}, revive() {}, damage_reduction() {}, invisible_when() {},
};

export { RATS };
