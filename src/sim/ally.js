// Allied computer player: runs an economy, builds farms, barracks and a
// tower, trains a hero and an army, defends the base and later pushes the
// rat pits. Issues ordinary commands, so it also works as the stand-in for
// a disconnected co-op player.
const HZ = 20;

export class AllyAI {
  constructor(w, p) {
    this.w = w; this.p = p;
    this.t = (p * 37) % 40;
    this.phase = 'eco';
    this.army = new Set();
  }

  get P() { return this.w.players[this.p]; }
  my(f) { return this.w.units.filter(e => e.alive && e.owner === this.p && f(e)); }
  myB(f) { return this.w.blds.filter(e => e.alive && e.owner === this.p && f(e)); }
  cmd(c) { c.p = this.p; if (this.sink) this.sink(c); else this.w.issue(c); }

  tick() {
    if (!this.P.alive || this.w.result) return;
    if (++this.t % 20) return;                       // think once per second
    const w = this.w, P = this.P, F = w.D.factions[P.faction];
    const pre = F.hall.split('_')[0];
    const hall = this.myB(b => b.def.role === 'town_hall' && b.built >= 1)[0];
    const workers = this.my(u => u.def.gatherer);
    // economy: idle workers back to work, 2/3 on gold, rest on wood
    const mine = hall && w.nearest(hall.x, hall.y, e => e.type === 'gold_mine' && e.alive && e.gold > 0, 40);
    const onGold = workers.filter(u => u.order.t === 'gather' && u.order.res === 'gold').length;
    for (const u of workers) {
      if (u.order.t !== 'idle') continue;
      if (mine && onGold < 5) { this.cmd({ t: 'gather', ids: [u.id], target: mine.id }); continue; }
      const tree = w.nearest(u.x, u.y, e => e.kind === 'tree' && e.alive, 30);
      if (tree) this.cmd({ t: 'gather', ids: [u.id], target: tree.id });
    }
    if (!hall) return;
    const queued = q => this.myB(b => b.queue.some(x => x.unit === q)).length;
    if (workers.length + queued(F.worker) < 13 && hall.queue.length < 2) this.cmd({ t: 'train', building: hall.id, unit: F.worker });
    const building = this.my(u => u.order.t === 'build' || u.order.t === 'construct').length;
    const farms = this.myB(b => b.def.role === 'farm');
    const bar = this.myB(b => b.def.role === 'barracks');
    const towers = this.myB(b => b.def.role === 'tower');
    if (!building) {
      if (P.popCap - P.popUsed < 6 && P.popCap < 100) this.build(pre + '_farm', hall);
      else if (!bar.length && w.time > 40) this.build(pre + '_barracks', hall);
      else if (towers.length < 2 && w.time > 180 && P.wood > 150) this.build(pre + '_tower', hall, 6);
      else if (bar.length < 2 && w.time > 420 && P.gold > 400) this.build(pre + '_barracks', hall);
    }
    // hero first, then army
    if (!P.heroes.length && !P.deadHeroes.length && !hall.queue.some(q => q.unit?.startsWith('hero:')) && P.gold >= 425 && w.time > 90)
      this.cmd({ t: 'train', building: hall.id, unit: 'hero:' + F.heroes[0] });
    for (const d of P.deadHeroes) this.cmd({ t: 'revive', building: hall.id, unit: d.type });
    if (P.tier < 2 && w.time > 360 && P.gold > 500 && P.wood > 250) this.cmd({ t: 'upgrade', building: hall.id });
    for (const b of bar) if (b.built >= 1 && b.queue.length < 2) {
      const opts = b.def.produces.filter(u => w.defs.units[u].tier <= P.tier);
      const u = opts[(this.t / 20 | 0) % opts.length];
      if (u) this.cmd({ t: 'train', building: b.id, unit: u });
      if (!b.rally) this.cmd({ t: 'rally', building: b.id, x: hall.x + (hall.x > 0 ? -6 : 6), y: hall.y + 8 });
    }
    for (const h of this.my(u => u.def.hero)) for (const k of ['R', 'Q', 'W', 'E']) if (w.abilities.canLearn(h, k)) this.cmd({ t: 'learn', id: h.id, key: k });
    this.fight(hall);
  }

  fight(hall) {
    const w = this.w;
    const army = this.my(u => !u.def.gatherer && !u.summoned);
    // defend anything of ours under attack
    let threat = null;
    for (const b of this.myB(() => true)) {
      w.query(b.x, b.y, 14, e => { if (!threat && e.team === 1 && e.alive) threat = e; });
      if (threat) break;
    }
    const idle = army.filter(u => u.order.t === 'idle' || u.order.t === 'guard');
    if (threat) {
      const ids = army.filter(u => u.order.t !== 'attack' && u.order.t !== 'amove').map(u => u.id);
      if (ids.length) this.cmd({ t: 'amove', ids, x: threat.x, y: threat.y });
    } else if (army.length >= 14 && w.director.n >= 2 && idle.length >= 10) {
      // push the nearest pit
      const pit = w.blds.filter(b => b.alive && b.type === 'rat_pit').sort((a, b) => Math.hypot(a.x - hall.x, a.y - hall.y) - Math.hypot(b.x - hall.x, b.y - hall.y))[0];
      if (pit) this.cmd({ t: 'amove', ids: idle.map(u => u.id), x: pit.x, y: pit.y - pit.h / 2 - 2 });
    }
    // heroes cast what they can on the nearest enemy
    for (const h of this.my(u => u.def.hero)) {
      if (w.tick - h.lastCombat > 2 * HZ) continue;
      for (const k of ['R', 'Q', 'W', 'E']) {
        const a = w.abilities.ability(h, k);
        if (!a || h.skill[k] === 0 || h.cds[k] > 0 || h.mana < a.mana || a.type === 'aura' || a.type === 'passive') continue;
        const foe = w.byId.get(h.engaged);
        if (a.type === 'no_target' || a.type === 'channel') { this.cmd({ t: 'cast', id: h.id, key: k }); break; }
        if (!foe || !foe.alive) continue;
        if (a.type === 'target_unit' && w.abilities.validTarget(h, a, foe)) { this.cmd({ t: 'cast', id: h.id, key: k, target: foe.id }); break; }
        if (a.type === 'point') { this.cmd({ t: 'cast', id: h.id, key: k, x: foe.x, y: foe.y }); break; }
      }
    }
  }

  build(type, hall, minR = 9) {
    const w = this.w, d = w.defs.buildings[type];
    if (!d || !w.canAfford(this.P, d.cost)) return;
    const builder = this.my(u => u.def.gatherer && !u.hidden && u.order.t === 'gather' && u.order.res === 'wood')[0] || this.my(u => u.def.gatherer && !u.hidden)[0];
    if (!builder) return;
    const away = hall.y < 0 ? -1 : 1;                 // build on the side away from the rats
    for (let k = 0; k < 80; k++) {
      const a = k * 2.399, r = minR + k * 0.35;
      const x = Math.round(hall.x + Math.cos(a) * r) + 0.5 * (Math.round(d.w) % 2), y = Math.round(hall.y + Math.sin(a) * r * 0.8 + away * 2) + 0.5 * (Math.round(d.h) % 2);
      if (w.grid.canPlace(x, y, d.w + 2, d.h + 2)) { this.cmd({ t: 'build', ids: [builder.id], type, x, y }); return; }
    }
  }
}
