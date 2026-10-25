// Co-op networking: turn-based lockstep over WebRTC (PeerJS) with the host
// as relay and authority. Every peer runs the same deterministic World;
// only commands travel. The host stamps each 100 ms turn with the commands
// to run DELAY turns later, peers stall if a turn hasn't arrived, and a
// periodic state hash catches drift, which the host repairs with a full
// snapshot. ?local in the URL swaps WebRTC for BroadcastChannel (tabs).
import { AllyAI } from './sim/ally.js';

export const TURN = 2;            // ticks per turn (100 ms)
const DELAY = 3;                  // turns between issue and execution
const HASH_EVERY = 25;            // turns
const MAX_AHEAD = 10;             // host waits for clients beyond this
const PEERJS = 'https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js';
const COLORS = ['#2f5fd0', '#d23a2a', '#27a35a', '#e0a020'];
const FACTIONS = ['cats', 'dogs', 'hamsters', 'hares'];

function loadScript(src) {
  return new Promise((res, rej) => { if (window.Peer) return res(); const s = document.createElement('script'); s.src = src; s.onload = res; s.onerror = () => rej(new Error('PeerJS не загрузился')); document.head.appendChild(s); });
}

// --- transports: { send(peerId|null, msg), onmsg(fn), onjoin(fn), onleave(fn), id }
class LocalBus {
  constructor(id, room) {
    this.id = id; this.ch = new BroadcastChannel('ak-' + room);
    this.ch.onmessage = e => { const m = e.data; if (m.to && m.to !== this.id) return; if (m.from === this.id) return; if (m.hello) this._join?.(m.from); else this._msg?.(m.from, m.msg); };
  }
  send(to, msg) { this.ch.postMessage({ from: this.id, to, msg }); }
  hello() { this.ch.postMessage({ from: this.id, hello: true }); }
  onmsg(f) { this._msg = f; } onjoin(f) { this._join = f; } onleave(f) { this._leave = f; }
}

class PeerBus {
  static async host() {
    await loadScript(PEERJS);
    const code = 'ak-' + Math.random().toString(36).slice(2, 7);
    const b = new PeerBus();
    b.peer = new window.Peer(code);
    await new Promise((res, rej) => { b.peer.on('open', res); b.peer.on('error', rej); });
    b.id = code; b.conns = new Map();
    b.peer.on('connection', c => {
      c.on('open', () => { b.conns.set(c.peer, c); b._join?.(c.peer); });
      c.on('data', m => b._msg?.(c.peer, m));
      c.on('close', () => { b.conns.delete(c.peer); b._leave?.(c.peer); });
    });
    return b;
  }
  static async join(code) {
    await loadScript(PEERJS);
    const b = new PeerBus();
    b.peer = new window.Peer();
    await new Promise((res, rej) => { b.peer.on('open', res); b.peer.on('error', rej); });
    b.id = b.peer.id; b.conns = new Map();
    const c = b.peer.connect(code, { reliable: true, serialization: 'json' });
    await new Promise((res, rej) => { c.on('open', res); c.on('error', rej); setTimeout(() => rej(new Error('Хост не отвечает')), 15000); });
    b.conns.set(code, c);
    c.on('data', m => b._msg?.(code, m));
    c.on('close', () => b._leave?.(code));
    return b;
  }
  send(to, msg) {
    if (to) this.conns.get(to)?.send(msg);
    else for (const c of this.conns.values()) c.send(msg);
  }
  onmsg(f) { this._msg = f; } onjoin(f) { this._join = f; } onleave(f) { this._leave = f; }
}

export class Net {
  constructor(app) {
    this.app = app;
    this.role = null;
    this.turns = new Map();       // turn -> cmds
    this.pending = [];
    this.acks = new Map();        // peer -> last turn reached
    this.hashes = new Map();
    this.local = new URLSearchParams(location.search).has('local');
  }

  // ------------------------------------------------------------- lobby: host
  async host(st, dlg, onStart) {
    const box = dlg.querySelector('#lobby');
    box.innerHTML = '<div class="hint">Создаём комнату…</div>';
    try {
      this.bus = this.local ? new LocalBus('host', 'room') : await PeerBus.host();
    } catch (e) { box.innerHTML = `<div class="hint" style="color:#ff8a6a">Сеть недоступна: ${e.message}</div>`; return; }
    this.role = 'host';
    const code = this.local ? 'local' : this.bus.id;
    this.slots = [{ peer: null, name: st.name, faction: st.faction }];
    const render = () => {
      box.innerHTML = `<h2>Комната: <span style="color:#fff0b8;user-select:all">${code}</span></h2>
        <div class="hint" style="text-align:left">Передайте код друзьям — они вводят его и жмут «Подключиться». До 4 игроков.</div>
        <div class="lobby-slots">${this.slots.map((s, i) => `<div class="slot"><div class="c" style="background:${COLORS[i]}"></div><div>${s.name}${i === 0 ? ' (хост)' : ''}${s.ai ? ' (ИИ)' : ''}</div><div>${this.app.D.factions[s.faction].name}</div><div></div></div>`).join('')}</div>`;
      this.bus.send(null, { k: 'lobby', slots: this.slots.map(s => ({ name: s.name, faction: s.faction, ai: !!s.ai })) });
    };
    this.bus.onjoin(p => { if (this.local) return; });
    this.bus.onmsg((p, m) => {
      if (m.k === 'hello' && this.slots.length < 4 && !this.started) {
        const used = new Set(this.slots.map(s => s.faction));
        const faction = used.has(m.faction) ? FACTIONS.find(f => !used.has(f)) : m.faction;
        this.slots.push({ peer: p, name: m.name.slice(0, 16), faction });
        render();
      } else this.onMessage(p, m);
    });
    this.bus.onleave(p => {
      if (!this.started) { this.slots = this.slots.filter(s => s.peer !== p); render(); return; }
      this.dropPeer(p);
    });
    render();
    const btn = dlg.querySelector('#startBtn');
    btn.textContent = 'Начать для всех';
    btn.onclick = () => {
      this.started = true;
      // fill with computer allies if requested
      const ms0 = this.app.menuState || {};
      const want = ms0.mode === 'teams' ? 4 : ms0.mode === 'ffa' ? this.slots.length + (ms0.foes || 0) : this.slots.length + (+ms0.allies || 0);
      const extra = Math.max(0, Math.min(4, want) - this.slots.length);
      for (let i = 0; i < extra; i++) { const used = new Set(this.slots.map(s => s.faction)); this.slots.push({ peer: null, name: 'Союзник (ИИ)', faction: FACTIONS.find(f => !used.has(f)), ai: true }); }
      const ms = this.app.menuState || {};
      const team = i => ms.mode === 'ffa' ? i : ms.mode === 'teams' ? (i < 2 ? 0 : 1) : 0;
      const players = this.slots.map((s, i) => ({ name: s.name, faction: s.faction, ai: !!s.ai, team: team(i) }));
      const cfg = { players, difficulty: ms.diff || 'normal', seed: (Math.random() * 1e9) | 0, net: 'host',
                    mode: ms.mode && ms.mode !== 'coop' ? 'melee' : 'coop', rats: !!ms.rats };
      this.slots.forEach((s, i) => { if (s.peer) { this.bus.send(s.peer, { k: 'start', cfg: { ...cfg, me: i, net: 'client' } }); this.acks.set(s.peer, 0); } });
      onStart({ ...cfg, me: 0 });
    };
  }

  // ------------------------------------------------------------ lobby: client
  async join(code, st, dlg, onStart) {
    const box = dlg.querySelector('#lobby');
    if (!code && !this.local) { box.innerHTML = '<div class="hint" style="color:#ff8a6a">Введите код комнаты</div>'; return; }
    box.innerHTML = '<div class="hint">Подключаемся…</div>';
    try {
      if (this.local) { this.bus = new LocalBus('c' + Math.random().toString(36).slice(2, 7), 'room'); this.hostId = 'host'; }
      else { this.bus = await PeerBus.join(code); this.hostId = code; }
    } catch (e) { box.innerHTML = `<div class="hint" style="color:#ff8a6a">Не удалось подключиться: ${e.message}</div>`; return; }
    this.role = 'client';
    dlg.querySelector('#startBtn').style.display = 'none';
    this.bus.onmsg((p, m) => {
      if (m.k === 'lobby') box.innerHTML = `<h2>Ожидаем хоста…</h2><div class="lobby-slots">${m.slots.map((s, i) => `<div class="slot"><div class="c" style="background:${COLORS[i]}"></div><div>${s.name}${s.ai ? ' (ИИ)' : ''}</div><div>${this.app.D.factions[s.faction].name}</div><div></div></div>`).join('')}</div>`;
      else if (m.k === 'start') onStart(m.cfg);
      else this.onMessage(p, m);
    });
    this.bus.onleave(() => { this.app.hud?.msg('Связь с хостом потеряна', 'alert'); this.lost = true; });
    this.bus.send(this.hostId, { k: 'hello', name: st.name, faction: st.faction });
  }

  // --------------------------------------------------------------- in game
  attach(cfg) {
    this.cfg = cfg;
    for (let t = 0; t < DELAY; t++) this.turns.set(t, []);
    // computer allies think on the host only; their orders travel like a player's
    if (this.role === 'client') this.app.allies = this.app.allies.map(() => null);
  }

  get turn() { return Math.floor(this.app.world.tick / TURN); }

  // called before every world step; false = stall (turn data missing)
  beforeStep() {
    const w = this.app.world;
    if (!this.role) return true;
    if (w.tick % TURN !== 0) return true;
    const n = this.turn;
    if (this.role === 'host') {
      for (const t of this.acks.values()) if (t < n - MAX_AHEAD) return false;
      const out = { k: 'turn', n: n + DELAY, cmds: this.pending };
      if (n % HASH_EVERY === 0) { out.hash = w.stateHash(); out.hn = n; }
      this.pending = [];
      this.turns.set(n + DELAY, out.cmds);
      this.bus.send(null, out);
    } else {
      if (!this.turns.has(n)) return false;
      const h = this.hashes.get(n);
      if (h != null) {
        this.hashes.delete(n);
        if (h !== w.stateHash() && !this.resyncing) { this.resyncing = true; this.bus.send(this.hostId, { k: 'resync' }); this.app.hud?.msg('Рассинхронизация — получаем состояние от хоста…', 'alert'); }
      }
      if (n % 5 === 0) this.bus.send(this.hostId, { k: 'ack', n });
    }
    for (const c of this.turns.get(n)) w.issue(c);
    this.turns.delete(n - 1);
    return true;
  }

  sendCmd(c) {
    if (this.role === 'host') this.pending.push(c);
    else if (this.role === 'client') this.bus.send(this.hostId, { k: 'cmd', c });
  }

  sendPing(x, y) {
    const m = { k: 'ping', x, y, p: this.app.me };
    if (this.role === 'host') this.bus.send(null, m); else if (this.role === 'client') this.bus.send(this.hostId, m);
  }

  onMessage(from, m) {
    const app = this.app;
    switch (m.k) {
      case 'cmd': if (this.role === 'host') { const slot = this.slots.findIndex(s => s.peer === from); if (slot >= 0) { m.c.p = slot; this.pending.push(m.c); } } break;
      case 'turn': this.turns.set(m.n, m.cmds); if (m.hash != null) this.hashes.set(m.hn, m.hash); break;
      case 'ack': this.acks.set(from, m.n); break;
      case 'ping':
        if (this.role === 'host') this.bus.send(null, m);
        if (m.p !== app.me) { app.minimap?.ping(m.x, m.y, app.world.players[m.p]?.color); app.fx?.ring(m.x, m.y, [1, 0.85, 0.3], 4, 2); app.audio.play('alert'); app.hud?.msg(`${app.world.players[m.p]?.name}: сигнал на карте`, 'ally'); }
        break;
      case 'resync':
        if (this.role === 'host') this.wantSnap = from;
        break;
      case 'snap': {
        const w = app.world;
        w.restore(m.data);
        this.turns = new Map(m.turns.map(([n, c]) => [n, c]));
        this.hashes.clear();
        this.resyncing = false;
        app.views.rebind();
        app.hud?.msg('Состояние восстановлено', 'ally');
        break;
      }
      case 'drop': app.hud?.msg(m.text, 'alert'); break;
    }
  }

  // host: answer resync requests at a turn boundary (after beforeStep)
  afterStep() {
    if (this.role !== 'host' || !this.wantSnap) return;
    const w = this.app.world;
    if (w.tick % TURN !== 0) return;
    const turns = [...this.turns.entries()].filter(([n]) => n >= this.turn);
    this.bus.send(this.wantSnap, { k: 'snap', data: w.serialize(), turns });
    this.wantSnap = null;
  }

  dropPeer(p) {
    const i = this.slots.findIndex(s => s.peer === p);
    if (i < 0) return;
    this.slots[i].peer = null;
    this.acks.delete(p);
    const app = this.app;
    // a computer ally takes over the abandoned kingdom (on every peer, via the command stream)
    app.allies[i] = new AllyAI(app.world, i);
    app.allies[i].sink = c => this.sendCmd(c);
    const text = `${app.world.players[i].name} отключился — его королевством управляет компьютер`;
    app.hud?.msg(text, 'alert');
    this.bus.send(null, { k: 'drop', text });
  }
}
