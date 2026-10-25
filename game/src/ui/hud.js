// HUD: resource bar, allies, minimap frame, portrait/info panel, command
// card with WC3 hotkeys and tooltips. DOM updates are throttled; the
// command card is rebuilt only when its content signature changes.
import { icon, abilityIcon } from './icons.js';

const ATK = { pierce: 'колющий', slash: 'рубящий', polearm: 'древковый', siege: 'осадный', fire: 'огненный', hero: 'геройский' };
const ARM = { light: 'лёгкая', medium: 'средняя', heavy: 'тяжёлая', fortified: 'укреплённая', hero: 'геройская' };
const ROLE = { worker: 'Рабочий', infantry: 'Пехота', ranged: 'Стрелок', elite: 'Элита', hero: 'Герой', support: 'Поддержка', boss: 'Босс',
  town_hall: 'Ратуша', barracks: 'Казарма', farm: 'Ферма', tower: 'Башня', gold_mine: 'Рудник', shrine: 'Святыня', spawner: 'Провал' };
const GRID_KEYS = ['KeyQ', 'KeyW', 'KeyE', 'KeyR', 'KeyA', 'KeyS', 'KeyD', 'KeyF', 'KeyZ', 'KeyX', 'KeyC', 'KeyV'];
const keyLabel = c => c.replace('Key', '').replace('Digit', '');

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };

export class Hud {
  constructor(app) {
    this.app = app;
    this.w = app.world;
    this.root = $('#hud');
    this.build();
    this.sig = '';
    this.t = 0;
    this.buttons = [];
    this.msgList = [];
  }

  build() {
    const H = this.root;
    H.innerHTML = `
      <div id="top" class="frame panel">
        <div class="res gold"><i></i><span>0</span></div>
        <div class="res wood"><i></i><span>0</span></div>
        <div class="res food"><i></i><span>0</span></div>
        <div class="res pop"><i></i><span>0/0</span></div>
        <div class="upkeep">Без содержания</div>
        <div id="clock" title="День и ночь"><div class="dial"></div><div class="cover"></div></div>
        <div id="wave"><div class="t">—</div><div class="l">до волны крыс</div></div>
      </div>
      <div id="menuBtns"><button class="tbtn" data-act="allies">Союзники</button><button class="tbtn" data-act="menu">Меню (F10)</button></div>
      <div id="allies" class="frame panel"></div>
      <div id="msgs"></div>
      <div id="centerMsg"></div>
      <div id="banner"><div class="big"></div><div class="small"></div></div>
      <div id="bottom">
        <div id="mmWrap" class="frame panel"><div id="mmBtns"><button data-mm="ping" title="Сигнал союзникам (Alt+клик)">!</button><button data-mm="terrain" class="on" title="Рельеф">◐</button></div><canvas id="minimap" width="256" height="256"></canvas></div>
        <div id="center" class="frame panel">
          <div id="portrait"><div class="lvl" style="display:none"></div></div>
          <div id="info"></div>
        </div>
        <div id="cmd" class="frame panel"></div>
      </div>
      <div id="tip" class="frame"></div>`;
    this.$ = {
      gold: $('.res.gold span', H), wood: $('.res.wood span', H), food: $('.res.food span', H), pop: $('.res.pop span', H),
      upkeep: $('.upkeep', H), dial: $('#clock .dial', H), wave: $('#wave .t', H), waveL: $('#wave .l', H),
      allies: $('#allies', H), msgs: $('#msgs', H), info: $('#info', H), cmd: $('#cmd', H), tip: $('#tip', H),
      portrait: $('#portrait', H), lvl: $('#portrait .lvl', H), banner: $('#banner', H), center: $('#centerMsg', H),
    };
    $('#menuBtns', H).addEventListener('click', e => {
      const a = e.target.dataset.act;
      if (a === 'menu') this.app.togglePause();
      if (a === 'allies') this.$.allies.style.display = this.$.allies.style.display === 'none' ? '' : 'none';
    });
    $('#mmBtns', H).addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.mm === 'ping') this.app.input.setMode({ kind: 'ping' });
      if (b.dataset.mm === 'terrain') { b.classList.toggle('on'); this.app.minimap.terrain = b.classList.contains('on'); }
    });
    for (let i = 0; i < 12; i++) {
      const b = el('button', 'cb');
      b.style.visibility = 'hidden';
      b.addEventListener('pointerdown', e => { e.stopPropagation(); if (e.button === 0) this.press(i); });
      b.addEventListener('contextmenu', e => { e.preventDefault(); const c = this.buttons[i]; if (c?.alt) c.alt(); });
      b.addEventListener('pointerenter', () => this.showTip(i));
      b.addEventListener('pointerleave', () => this.hideTip());
      this.$.cmd.appendChild(b);
    }
    this.cbs = [...this.$.cmd.children];
  }

  get me() { return this.w.players[this.app.me]; }

  // --------------------------------------------------------------- per frame
  update(dt) {
    this.t += dt;
    if (this.t < 0.1) return;
    this.t = 0;
    const P = this.me, w = this.w;
    this.$.gold.textContent = Math.floor(P.gold);
    this.$.wood.textContent = Math.floor(P.wood);
    this.$.food.textContent = Math.floor(P.food);
    this.$.pop.textContent = `${P.popUsed}/${P.popCap}`;
    const up = w.upkeep(P);
    this.$.upkeep.textContent = up >= 1 ? 'Без содержания' : up >= 0.7 ? 'Малое содержание' : 'Большое содержание';
    this.$.upkeep.className = 'upkeep' + (up >= 1 ? '' : up >= 0.7 ? ' mid' : ' high');
    this.$.dial.style.transform = `rotate(${-w.dayPhase * 360 + 90}deg)`;
    const s = w.director.secondsToNext;
    if (s < 0) { this.$.wave.textContent = w.result ? '—' : 'Последняя'; this.$.waveL.textContent = 'волна вышла'; }
    else { this.$.wave.textContent = `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`; this.$.waveL.textContent = `до волны ${w.director.n + 1} из ${w.director.total}`; }
    this.updateAllies();
    this.updateInfo();
    this.updateCmd();
    this.fadeMsgs();
  }

  updateAllies() {
    const w = this.w;
    const html = w.players.map(p => {
      const heroes = p.heroes.map(id => w.byId.get(id)).filter(Boolean)
        .map(h => `<span title="${h.def.name}"><b style="width:${(h.hp / h.maxHp * 100).toFixed(0)}%"></b></span>`).join('');
      const F = this.app.D.factions[p.faction];
      return `<div class="ally ${p.alive ? '' : 'dead'}"><div class="c" style="background:${p.color}"></div>
        <div class="n">${p.name}${p.id === this.app.me ? ' (вы)' : ''}<small>${F.name}</small></div>
        ${p.id !== this.app.me && p.alive ? `<button class="tbtn click" data-tr="${p.id}" title="Передать 100 золота и 50 дерева (налог 10%)">⇄</button>` : '<span></span>'}
        <div class="heroes">${heroes}</div></div>`;
    }).join('') + (w.crusade.ready && !w.crusade.used ? `<button class="tbtn click" data-crusade="1">⚔ Крестовый поход</button>` : '');
    if (html !== this._alliesHtml) {
      this._alliesHtml = html;
      this.$.allies.innerHTML = html;
      this.$.allies.querySelectorAll('[data-tr]').forEach(b => b.onclick = () => this.app.send({ t: 'transfer', to: +b.dataset.tr, gold: 100, wood: 50 }));
      this.$.allies.querySelectorAll('[data-crusade]').forEach(b => b.onclick = () => this.app.send({ t: 'crusade' }));
    }
  }

  // ------------------------------------------------------------ info panel
  updateInfo() {
    const app = this.app, w = this.w;
    const sel = app.selected();
    const lead = app.leader();
    const box = this.$.info;
    if (!lead) { box.innerHTML = this.idleInfo(); this.$.lvl.style.display = 'none'; this._infoKey = ''; return; }
    if (sel.length > 1) {
      const key = 'g' + sel.map(e => e.id).join(',') + app.subType;
      if (key !== this._infoKey) {
        this._infoKey = key;
        box.innerHTML = `<div id="group">${sel.slice(0, 24).map(e => `<div class="g ${e.type === app.subType ? 'sub' : ''}" data-id="${e.id}" style="background-image:url(${this.iconFor(e)})"><i><b></b></i></div>`).join('')}</div>`;
        box.querySelectorAll('.g').forEach(g => g.onclick = ev => {
          const id = +g.dataset.id;
          if (ev.shiftKey) app.select(app.sel.filter(x => x !== id));
          else if (ev.ctrlKey) app.select(app.sel.filter(x => w.byId.get(x)?.type === w.byId.get(id)?.type));
          else app.select([id]);
        });
      }
      box.querySelectorAll('.g').forEach(g => { const e = w.byId.get(+g.dataset.id); if (e) g.querySelector('b').style.width = (e.hp / e.maxHp * 100) + '%'; });
      this.$.lvl.style.display = 'none';
      return;
    }
    const e = lead;
    const d = e.def;
    const key = 's' + e.id + (e.kind === 'building' ? e.built >= 1 : '') + (e.queue?.map(q => q.unit || q.up || q.revive).join() || '');
    if (key !== this._infoKey) {
      this._infoKey = key;
      const own = e.owner === app.me;
      let html = `<div class="name">${d.name}</div><div class="sub">${this.subtitle(e)}</div>
        <div class="bar hp"><b></b><span></span></div>`;
      if (e.maxMana) html += `<div class="bar mana"><b></b><span></span></div>`;
      if (d.hero) html += `<div class="bar xp" title="Опыт"><b></b></div>`;
      if (e.kind === 'building' && (e.built < 1 || e.queue?.length)) html += `<div class="bar prog"><b></b><span></span></div>`;
      if (e.kind === 'building' && own && e.queue?.length) html += `<div id="queue">${e.queue.map((q, i) => `<div class="q" data-i="${i}" style="background-image:url(${this.queueIcon(q)})" title="Отменить"></div>`).join('')}</div>`;
      else html += `<div class="stats">${this.stats(e)}</div>`;
      if (d.hero) html += `<div class="items">${'<div></div>'.repeat(6)}</div>`;
      box.innerHTML = html;
      box.querySelectorAll('#queue .q').forEach(q => q.onclick = () => app.send({ t: 'cancel', building: e.id, slot: +q.dataset.i }));
    }
    const hp = box.querySelector('.bar.hp');
    if (hp) {
      const f = Math.max(0, e.hp / e.maxHp);
      hp.querySelector('b').style.width = f * 100 + '%';
      hp.querySelector('b').style.filter = f < 0.3 ? 'hue-rotate(-100deg) saturate(1.4)' : f < 0.6 ? 'hue-rotate(-50deg)' : '';
      hp.querySelector('span').textContent = `${Math.ceil(e.hp)} / ${Math.round(e.maxHp)}`;
    }
    const mp = box.querySelector('.bar.mana');
    if (mp) { mp.querySelector('b').style.width = e.mana / e.maxMana * 100 + '%'; mp.querySelector('span').textContent = `${Math.floor(e.mana)} / ${Math.round(e.maxMana)}`; }
    const xp = box.querySelector('.bar.xp');
    if (xp) {
      const A = w.abilities, lo = A.xpFor(e.level - 1) || 0, hi = A.xpFor(e.level);
      xp.querySelector('b').style.width = (e.level >= d.maxLevel ? 100 : (e.xp - lo) / (hi - lo) * 100) + '%';
      this.$.lvl.style.display = ''; this.$.lvl.textContent = `Уровень ${e.level}`;
    } else this.$.lvl.style.display = 'none';
    const pr = box.querySelector('.bar.prog');
    if (pr) {
      let f, txt;
      if (e.built < 1) { f = e.built; txt = `Строится… ${Math.floor(f * 100)}%`; }
      else { const q = e.queue[0]; f = q ? q.t / q.time : 0; txt = q ? (e.blocked ? 'Нужно больше ферм' : (q.up ? 'Улучшение' : q.revive ? 'Воскрешение' : 'Обучение') + ` ${Math.floor(f * 100)}%`) : ''; }
      pr.querySelector('b').style.width = f * 100 + '%'; pr.querySelector('span').textContent = txt;
    }
    const st = box.querySelector('.stats');
    if (st && this.t === 0 && (w.tick % 10 === 0)) st.innerHTML = this.stats(e);
  }

  idleInfo() {
    const P = this.me, w = this.w;
    const F = this.app.D.factions[P.faction];
    return `<div class="name">${F.name}</div><div class="sub">Оборона Королевства · ${this.app.diffName}</div>
      <div class="stats"><div class="st">Добыто золота: ${Math.floor(P.mined)}</div><div class="st">Казна команды: ${Math.floor(w.players.reduce((s, p) => s + p.mined, 0))} / ${this.app.D.economy.royal_treasury_goal}</div></div>
      <div class="sub" style="margin-top:8px">Провалы крыс: ${w.blds.filter(b => b.alive && b.type === 'rat_pit').length} · Волна ${w.director.n} из ${w.director.total}</div>`;
  }

  subtitle(e) {
    const P = this.w.players[e.owner];
    const owner = P ? P.name : e.owner === 4 ? 'Крысиная Чума' : 'Нейтральные';
    if (e.kind === 'building') {
      if (e.type === 'gold_mine') return `Золото: ${Math.floor(e.gold)}`;
      const tier = e.def.role === 'town_hall' && e.tier > 1 ? ` · ${e.def.upgrades.find(u => u.tier === e.tier)?.name}` : '';
      return `${ROLE[e.def.role] || ''}${tier} · ${owner}`;
    }
    if (e.def.hero) return `${e.def.heroRole === 'leader' ? 'Лидер' : 'Герой'} · ${owner}`;
    return `${ROLE[e.def.role] || ''}${e.summoned ? ' · призван' : ''} · ${owner}`;
  }

  stats(e) {
    const d = e.def, m = e.mods || {};
    if (e.kind === 'building') {
      let s = `<div class="st"><img src="${icon('shield', 'stone')}"><div>${e.armor}<small>${ARM[d.armorType] || ''}</small></div></div>`;
      if (d.attack) s = `<div class="st"><img src="${icon('arrow', 'red')}"><div>${d.attack.damage[0]}–${d.attack.damage[1]}<small>${ATK[d.attack.attack_type]}</small></div></div>` + s;
      if (d.pop) s += `<div class="st"><img src="${icon('paw', 'blue')}"><div>+${d.pop}<small>население</small></div></div>`;
      if (e.type === 'gold_mine') s = `<div class="st"><img src="${icon('coin', 'gold', '#ffd75a')}"><div>${e.inside || 0}/5<small>рабочих внутри</small></div></div>`;
      return s;
    }
    const lo = d.dmg[0] + (e.dmgBonus || 0), hi = d.dmg[1] + (e.dmgBonus || 0);
    const bonus = (m.dmg || 1) > 1.001 ? ` <span style="color:#7aff7a">+${Math.round(((m.dmg || 1) - 1) * 100)}%</span>` : '';
    const arm = (e.armor || 0) + (m.armor || 0);
    let s = `<div class="st"><img src="${icon('sword', 'red')}"><div>${Math.round(lo)}–${Math.round(hi)}${bonus}<small>${ATK[d.atkType]}${d.range > 2 ? ', дальн. ' + d.range : ''}</small></div></div>
      <div class="st"><img src="${icon('shield', 'stone')}"><div>${arm.toFixed(arm % 1 ? 1 : 0)}<small>${ARM[d.armorType]}</small></div></div>`;
    if (e.carry?.amt) s += `<div class="st"><img src="${icon(e.carry.res === 'gold' ? 'coin' : e.carry.res === 'wood' ? 'hammer' : 'carrot', 'gold')}"><div>${e.carry.amt}<small>несёт</small></div></div>`;
    if (d.hero) s += `<div class="st"><img src="${icon('book', 'purple')}"><div>${e.points}<small>очков навыков</small></div></div>`;
    return s;
  }

  iconFor(e) {
    const ic = this.app.icons;
    const color = this.app.views.colorOf(e);
    if (e.kind === 'unit') return ic.get('units', e.def.model, color);
    return ic.get('buildings', e.def.model, color, 'stone');
  }

  queueIcon(q) {
    if (q.up) return icon('up', 'gold');
    const d = this.w.defs.units[q.unit || q.revive];
    return this.app.icons.get('units', d.model, this.me.color);
  }

  // ----------------------------------------------------------- command card
  commands() {
    const app = this.app, w = this.w, P = this.me;
    const lead = app.leader();
    const C = new Array(12).fill(null);
    if (!lead || lead.owner !== app.me || !lead.alive) return C;
    const ids = app.selected().filter(e => e.owner === app.me && e.kind === lead.kind).map(e => e.id);
    const menu = app.menu;
    const back = { icon: icon('cross', 'red'), name: 'Отмена', hk: 'Escape', run: () => { app.menu = null; app.input.setMode(null); } };
    if (lead.kind === 'unit') {
      const d = lead.def;
      if (menu === 'build') {
        const list = Object.values(w.defs.buildings).filter(b => b.faction === P.faction);
        list.forEach((b, i) => {
          C[i] = { icon: app.icons.get('buildings', b.model, P.color, 'stone'), name: b.name, hk: GRID_KEYS[i], cost: b.cost,
            desc: this.buildingDesc(b), run: () => app.input.setMode({ kind: 'build', type: b.id, ids }) };
        });
        C[11] = back;
        return C;
      }
      if (menu === 'learn') {
        for (const [i, k] of ['Q', 'W', 'E', 'R'].entries()) {
          const a = w.abilities.ability(lead, k);
          if (!a) continue;
          const can = w.abilities.canLearn(lead, k);
          C[8 + i] = { icon: abilityIcon(a), name: `Изучить: ${a.name}`, hk: 'Key' + k, off: !can, lv: [lead.skill[k], k === 'R' ? 1 : 3],
            desc: a.desc + (k === 'R' ? `<div class="req">Требуется уровень ${d.ultLevel}</div>` : ''),
            run: () => { if (can) { app.send({ t: 'learn', id: lead.id, key: k }); if (lead.points <= 1) app.menu = null; } } };
        }
        C[11] = back;
        return C;
      }
      if (app.input.mode?.kind === 'target' || app.input.mode?.kind === 'build') { C[11] = back; return C; }
      C[0] = { icon: icon('boot', 'green'), name: 'Идти', hk: 'KeyM', desc: 'Идти к цели, не отвлекаясь на врагов.', run: () => app.input.setMode({ kind: 'target', cmd: 'move', ids }) };
      C[1] = { icon: icon('hand', 'red'), name: 'Стоп', hk: 'KeyS', desc: 'Прервать все приказы.', run: () => app.send({ t: 'stop', ids }) };
      C[2] = { icon: icon('shield', 'blue'), name: 'Стоять на месте', hk: 'KeyH', desc: 'Не сходить с места, атаковать только тех, кто в досягаемости.', run: () => app.send({ t: 'hold', ids }) };
      C[3] = { icon: icon('sword', 'red'), name: 'Атаковать', hk: 'KeyA', desc: 'Атаковать цель или идти в атаку на точку, сражаясь со всеми по пути.', run: () => app.input.setMode({ kind: 'target', cmd: 'attack', ids }) };
      C[4] = { icon: icon('patrol', 'blue'), name: 'Патруль', hk: 'KeyP', desc: 'Ходить между точками, атакуя врагов.', run: () => app.input.setMode({ kind: 'target', cmd: 'patrol', ids }) };
      if (d.gatherer) {
        C[8] = { icon: icon('hammer', 'stone'), name: 'Строить', hk: 'KeyB', desc: 'Открыть список построек.', run: () => { app.menu = 'build'; } };
        C[9] = { icon: icon('pick', 'gold'), name: 'Добывать', hk: 'KeyG', desc: 'Золото из рудника, дерево из леса, рыба на отмелях.', run: () => app.input.setMode({ kind: 'target', cmd: 'gather', ids }) };
        if (lead.carry.amt > 0) C[10] = { icon: icon('sack', 'gold'), name: 'Отнести груз', hk: 'KeyC', desc: 'Отнести ресурсы в ратушу.', run: () => app.send({ t: 'return', ids }) };
      }
      if (d.hero && lead.skill) {
        if (lead.points > 0) C[7] = { icon: icon('book', 'purple'), name: 'Изучить навык', hk: 'KeyO', badge: lead.points, desc: 'Потратить очки навыков.', run: () => { app.menu = 'learn'; } };
        for (const [i, k] of ['Q', 'W', 'E', 'R'].entries()) {
          const a = w.abilities.ability(lead, k);
          if (!a) continue;
          const L = lead.skill[k];
          const passive = a.type === 'aura' || a.type === 'passive';
          C[8 + i] = {
            icon: abilityIcon(a), name: a.name + (passive ? ' (пассивно)' : ''), hk: 'Key' + k, off: L === 0 || (!passive && lead.mana < a.mana),
            lv: [L, k === 'R' ? 1 : 3], cd: lead.cds[k] > 0 ? [lead.cds[k], a.cooldown] : null, mana: a.mana,
            desc: a.desc + `<div class="d" style="color:#9ac0ff;margin-top:4px">${a.mana ? 'Мана: ' + a.mana + ' · ' : ''}${a.cooldown ? 'Перезарядка: ' + a.cooldown + ' с' : ''}</div>` + (L === 0 ? '<div class="req">Навык не изучен</div>' : ''),
            run: () => this.castAbility(lead, k, a),
          };
        }
      }
      return C;
    }
    // buildings
    const b = lead;
    if (b.built < 1) { C[11] = { icon: icon('cross', 'red'), name: 'Отменить стройку', hk: 'Escape', desc: 'Вернуть 75% стоимости.', run: () => app.send({ t: 'cancel', building: b.id }) }; return C; }
    if (b.owner !== app.me) return C;
    const list = b.def.produces;
    list.forEach((u, i) => {
      const d = w.defs.units[u];
      if (!d) return;
      const taken = d.hero && (P.heroes.some(id => w.byId.get(id)?.type === u) || P.deadHeroes.some(h => h.type === u));
      const lock = d.tier > P.tier;
      C[i] = { icon: app.icons.get('units', d.model, P.color), name: (d.hero ? 'Призвать: ' : 'Обучить: ') + d.name, hk: GRID_KEYS[i], cost: d.cost, pop: d.pop,
        off: taken || lock, desc: this.unitDesc(d) + (lock ? `<div class="req">Нужна ратуша уровня ${d.tier}</div>` : '') + (taken ? '<div class="req">Уже на службе</div>' : ''),
        cnt: b.queue.filter(q => q.unit === u).length || null,
        run: () => app.send({ t: 'train', building: b.id, unit: u }) };
    });
    if (b.def.role === 'town_hall') {
      P.deadHeroes.forEach((h, i) => {
        const d = w.defs.units[h.type];
        const k = this.app.D.economy.heroes.revive_cost_mult;
        C[4 + i] = { icon: app.icons.get('units', d.model, P.color), name: `Воскресить: ${d.name} (ур. ${h.level})`, hk: GRID_KEYS[4 + i],
          cost: { gold: Math.round(d.cost.gold * k), wood: Math.round(d.cost.wood * k) }, desc: 'Герой вернётся со всем опытом.',
          run: () => app.send({ t: 'revive', building: b.id, unit: h.type }) };
      });
      const up = b.def.upgrades.find(u => u.tier === b.tier + 1);
      if (up && !b.queue.some(q => q.up)) C[8] = { icon: icon('crown', 'gold', '#ffd75a'), name: `Улучшить: ${up.name}`, hk: 'KeyZ', cost: up.cost,
        desc: `Открывает войска ${up.tier}-го уровня и укрепляет ратушу (${up.hp} прочности).`, run: () => app.send({ t: 'upgrade', building: b.id }) };
    }
    if (list.length) C[11] = { icon: icon('flag', 'blue'), name: 'Точка сбора', hk: 'KeyV', desc: 'Новые воины пойдут сюда. Рабочие — сразу на добычу, если указать рудник или дерево.', run: () => app.input.setMode({ kind: 'target', cmd: 'rally', ids: [b.id] }) };
    return C;
  }

  castAbility(u, k, a) {
    const app = this.app;
    if (a.type === 'aura' || a.type === 'passive' || u.skill[k] === 0) return;
    if (a.type === 'no_target' || a.type === 'channel') { app.send({ t: 'cast', id: u.id, key: k }); return; }
    app.input.setMode({ kind: 'target', cmd: 'cast', key: k, ids: [u.id], ability: a, unitTarget: a.type === 'target_unit' || a.type === 'target_building' });
  }

  unitDesc(d) {
    if (d.hero) {
      const h = this.app.D.heroes[d.key];
      return `${h.abilities.map(a => `<b>${a.key}</b> ${a.name}`).join('<br>')}`;
    }
    return `${ROLE[d.role]} · ${d.range > 2 ? 'дальний бой' : 'ближний бой'}<br>Урон ${d.dmg[0]}–${d.dmg[1]} (${ATK[d.atkType]}) · Броня ${d.armor} (${ARM[d.armorType]})<br>Здоровье ${d.hp} · Скорость ${d.speed}`;
  }

  buildingDesc(b) {
    const parts = [ROLE[b.role] || ''];
    if (b.pop) parts.push(`+${b.pop} к населению`);
    if (b.foodTrickle) parts.push(`+${b.foodTrickle} еды в секунду`);
    if (b.attack) parts.push(`Стреляет: ${b.attack.damage[0]}–${b.attack.damage[1]}, дальность ${b.attack.range}`);
    if (b.produces.length) parts.push('Обучает: ' + b.produces.map(u => this.w.defs.units[u]?.name).filter(Boolean).join(', '));
    return parts.join('<br>');
  }

  updateCmd() {
    const C = this.commands();
    this.buttons = C;
    const sig = C.map(c => c ? c.name + c.off + (c.lv || '') + (c.badge || '') + (c.cnt || '') + (c.cd ? Math.ceil(c.cd[0]) : '') : '-').join('|') + this.app.menu;
    if (sig === this.sig) return;
    this.sig = sig;
    C.forEach((c, i) => {
      const b = this.cbs[i];
      if (!c) { b.style.visibility = 'hidden'; b.innerHTML = ''; return; }
      b.style.visibility = '';
      b.style.backgroundImage = `url(${c.icon})`;
      b.className = 'cb' + (c.off ? ' off' : '') + (this.app.input.mode?.cmd && c.name && this.app.input.modeButton === i ? ' active' : '');
      let h = `<span class="hk">${keyLabel(c.hk === 'Escape' ? 'Esc' : c.hk)}</span>`;
      if (c.lv) h += `<span class="lv">${Array.from({ length: c.lv[1] }, (_, k) => `<i class="${k < c.lv[0] ? 'on' : ''}"></i>`).join('')}</span>`;
      if (c.cd) { const p = c.cd[0] / c.cd[1]; h += `<span class="cd" style="--p:${(p * 100).toFixed(1)}%"></span><span class="cdn">${Math.ceil(c.cd[0])}</span>`; }
      if (c.badge) h += `<span class="badge">${c.badge}</span>`;
      if (c.cnt) h += `<span class="cnt">${c.cnt}</span>`;
      b.innerHTML = h;
    });
    if (this.tipIdx != null) this.showTip(this.tipIdx);
  }

  press(i) {
    const c = this.buttons[i];
    if (!c || !c.run) return;
    const b = this.cbs[i];
    b.classList.add('pressed'); setTimeout(() => b.classList.remove('pressed'), 90);
    if (c.off && !c.lv) { this.flash(c.desc?.includes('req') ? c.desc.match(/class="req">([^<]*)/)?.[1] : 'Сейчас недоступно'); return; }
    if (c.off && c.lv && c.lv[0] === 0) { this.flash('Навык не изучен'); return; }
    if (c.cd) { this.flash('Способность ещё не готова'); return; }
    if (c.mana && this.app.leader()?.mana < c.mana) { this.flash('Недостаточно маны'); return; }
    if (c.cost) { const miss = this.w.missing(this.me, c.cost); if (miss) { this.flash(miss); this.app.audio?.play('error'); return; } }
    this.app.input.modeButton = i;
    c.run();
    this.sig = '';
  }

  hotkey(code) {
    for (let i = 0; i < 12; i++) if (this.buttons[i]?.hk === code) { this.press(i); return true; }
    return false;
  }

  showTip(i) {
    const c = this.buttons[i];
    this.tipIdx = i;
    if (!c) { this.hideTip(); return; }
    const P = this.me;
    let cost = '';
    if (c.cost) {
      const item = (k, cls, v) => v ? `<span class="${P[k] < v ? 'bad' : ''}"><span style="color:${cls}">●</span> ${v}</span>` : '';
      cost = `<div class="cost">${item('gold', '#ffd75a', c.cost.gold)}${item('wood', '#c8945a', c.cost.wood)}${item('food', '#ff9a4a', c.cost.food)}${c.pop ? `<span><span style="color:#9ab8ff">●</span> ${c.pop}</span>` : ''}</div>`;
    }
    this.$.tip.innerHTML = `<div class="t">${c.name} <em>[${keyLabel(c.hk === 'Escape' ? 'Esc' : c.hk)}]</em></div>${cost}<div class="d">${c.desc || ''}</div>`;
    this.$.tip.style.display = 'block';
  }

  hideTip() { this.tipIdx = null; this.$.tip.style.display = 'none'; }

  // ---------------------------------------------------------------- messages
  msg(text, kind = 'info') {
    const d = el('div', kind, text);
    this.$.msgs.appendChild(d);
    this.msgList.push({ d, t: performance.now() });
    while (this.msgList.length > 7) this.msgList.shift().d.remove();
  }

  fadeMsgs() {
    const now = performance.now();
    for (const m of this.msgList) if (now - m.t > 7000) m.d.style.opacity = 0;
    while (this.msgList.length && now - this.msgList[0].t > 8200) this.msgList.shift().d.remove();
  }

  flash(text) {
    const c = this.$.center;
    c.textContent = text; c.style.opacity = 1;
    clearTimeout(this._fl); this._fl = setTimeout(() => { c.style.opacity = 0; }, 1600);
  }

  banner(big, small = '', ms = 3200) {
    const b = this.$.banner;
    b.querySelector('.big').textContent = big; b.querySelector('.small').textContent = small;
    b.style.opacity = 1;
    clearTimeout(this._bn); this._bn = setTimeout(() => { b.style.opacity = 0; }, ms);
  }
}
