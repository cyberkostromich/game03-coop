// Звериные королевства — client entry: boot, menu, game loop.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { loadData, ASSETS } from './data.js';
import { World, HZ, DT } from './sim/world.js';
import { Fog } from './view/fog.js';
import { buildTerrain } from './view/terrain.js';
import { EntityViews } from './view/entities.js';
import { RtsCamera } from './view/camera.js';
import { Fx } from './view/fx.js';
import { Hud } from './ui/hud.js';
import { Input } from './ui/input.js';
import { Minimap } from './ui/minimap.js';
import { Overlay } from './ui/overlay.js';
import { UnitIcons } from './ui/icons.js';
import { Audio } from './audio.js';
import { AllyAI } from './sim/ally.js';
import { Net } from './net.js';
import { showMenu, showEnd, showPause } from './ui/screens.js';

const COLORS = ['#2f5fd0', '#d23a2a', '#27a35a', '#e0a020'];
const DIFF = { easy: 'Лёгкий', normal: 'Нормальный', ruthless: 'Безжалостный' };

class App {
  async boot() {
    this.root = document.getElementById('app');
    const bar = document.querySelector('#loading .bar i'), msg = document.querySelector('#loading .msg');
    const prog = (f, t) => { bar.style.width = (f * 100).toFixed(0) + '%'; if (t) msg.textContent = t; };
    prog(0.02, 'Читаем летописи…');
    this.D = await loadData(f => prog(f));
    const img = new Image();
    img.src = ASSETS + 'maps/mill_pond_splat.png';
    await img.decode();
    this.splatImg = img;
    this.audio = new Audio();
    this.renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('view'), antialias: true, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
    this.renderer.setSize(innerWidth, innerHeight, false);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.autoClear = false;
    addEventListener('resize', () => this.resize());
    prog(0.15, 'Готово');
    document.getElementById('loading').style.opacity = 0;
    setTimeout(() => document.getElementById('loading').remove(), 800);
    this.net = new Net(this);
    showMenu(this, cfg => this.start(cfg));
  }

  resize() {
    this.renderer.setSize(innerWidth, innerHeight, false);
    if (this.camera) { this.camera.aspect = innerWidth / innerHeight; this.camera.updateProjectionMatrix(); }
  }

  // cfg: { players: [{name, faction, ai}], me, difficulty, seed, net: 'host'|'client'|null }
  async start(cfg) {
    const loading = document.createElement('div');
    loading.id = 'loading';
    loading.innerHTML = `<div class="crest"></div><div class="title">Мельничный пруд</div><div class="bar frame"><i></i></div><div class="msg">Собираем войска…</div>`;
    document.body.appendChild(loading);
    const bar = loading.querySelector('.bar i');
    this.cfg = cfg;
    this.me = cfg.me;
    this.diffName = DIFF[cfg.difficulty] || '';
    const players = cfg.players.map((p, i) => ({ ...p, color: p.color || COLORS[i] }));
    this.world = new World(this.D, { players, difficulty: cfg.difficulty, seed: cfg.seed });
    this.world.sharedControl = !!cfg.sharedControl;
    this.allies = players.map((p, i) => p.ai ? new AllyAI(this.world, i) : null);
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#0a0d12');
    this.camera = new THREE.PerspectiveCamera(36, innerWidth / innerHeight, 0.5, 260);
    const pm = new THREE.PMREMGenerator(this.renderer);
    this.scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    this.scene.environmentIntensity = 0.45;
    this.lights();
    this.fog = new Fog(this.world);
    const T = buildTerrain(this.D, this.world, this.renderer, this.fog, this.splatImg);
    this.terrain = T;
    this.scene.add(T.mesh, T.water.mesh);
    this.addSkirt();
    this.views = new EntityViews(this);
    await this.views.preload(f => { bar.style.width = (f * 90).toFixed(0) + '%'; });
    this.icons = new UnitIcons(this.renderer, this.views.models);
    this.cam = new RtsCamera(this.camera, this.renderer.domElement, this.world.grid);
    const home = this.world.players[this.me].home;
    this.cam.lookAt(home.x, home.y - 4);
    this.fx = new Fx(this);
    this.sel = []; this.subType = null; this.menu = null; this.hover = null; this.alerts = [];
    const ov = document.createElement('canvas'); ov.id = 'overlay'; this.root.insertBefore(ov, document.getElementById('hud'));
    this.hud = new Hud(this);
    this.input = new Input(this);
    this.minimap = new Minimap(this, this.splatImg);
    this.overlay = new Overlay(this);
    this.portrait = this.makePortrait();
    this.indicator = this.makeIndicators();
    if (cfg.net) this.net.attach(cfg);
    loading.style.opacity = 0; setTimeout(() => loading.remove(), 800);
    this.hud.banner('Оборона Королевства', 'Крысиная Чума поднимается из подземелий. Продержитесь и засыпьте провалы!', 5000);
    this.hud.msg('Подсказка: ПКМ — приказ, рамка — выделение, A — атака, B — строить (у рабочих), Ctrl+1..9 — отряды', 'info');
    this.audio.unlock();
    this.last = performance.now();
    this.acc = 0;
    this.running = true;
    // a few warm-up frames compile shaders before the player sees anything
    this.renderer.compile(this.scene, this.camera);
    requestAnimationFrame(t => this.frame(t));
  }

  lights() {
    const sun = new THREE.DirectionalLight(0xfff1d6, 3.0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const S = 36;
    Object.assign(sun.shadow.camera, { left: -S, right: S, top: S, bottom: -S, near: 1, far: 140 });
    sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.04;
    this.scene.add(sun, sun.target);
    const hemi = new THREE.HemisphereLight(0xbfd8ff, 0x5a4630, 1.15);
    this.scene.add(hemi);
    this.sun = sun; this.hemi = hemi;
    this.sunDir = new THREE.Vector3(-0.45, 0.82, 0.38).normalize();
  }

  addSkirt() {
    // dark forest floor beyond the map edge so the void never shows
    const g = new THREE.PlaneGeometry(600, 600).rotateX(-Math.PI / 2);
    const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: '#0b120a' }));
    m.position.y = -0.6;
    this.scene.add(m);
  }

  makePortrait() {
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(24, 0.8, 0.05, 60);
    const key = new THREE.DirectionalLight(0xfff0dd, 3.2); key.position.set(1.4, 2.4, 3);
    const rim = new THREE.DirectionalLight(0x88aaff, 2.6); rim.position.set(-2.5, 1.5, -2);
    scene.add(key, rim, new THREE.HemisphereLight(0xcfdcff, 0x302018, 1.0));
    scene.environment = this.scene.environment;
    return { scene, cam, id: 0, inst: null };
  }

  updatePortrait(dt) {
    const P = this.portrait, lead = this.leader();
    const id = lead ? lead.id : 0;
    if (P.id !== id) {
      if (P.inst) P.scene.remove(P.inst.root);
      P.inst = null; P.id = id;
      if (lead) {
        const kind = lead.kind === 'unit' ? 'units' : 'buildings';
        P.inst = this.views.models.instance(kind, lead.def.model, this.views.colorOf(lead));
        if (P.inst) {
          P.scene.add(P.inst.root);
          const a = P.inst.actions.Idle; if (a) a.play();
          P.inst.root.updateMatrixWorld(true);
          const box = new THREE.Box3().setFromObject(P.inst.root);
          const h = box.max.y - box.min.y;
          if (kind === 'units') {
            const head = box.min.y + h * 0.8;
            P.cam.position.set(h * 0.18, head + h * 0.02, h * 1.1);
            P.cam.lookAt(0, head - h * 0.06, 0);
          } else {
            const c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() * 0.5;
            P.cam.position.set(c.x + r * 0.8, c.y + r * 0.5, c.z + r * 2.0);
            P.cam.lookAt(c);
          }
        }
      }
    }
    if (P.inst) P.inst.mixer.update(dt);
  }

  renderPortrait() {
    const P = this.portrait;
    if (!P.inst) return;
    const r = this.hud.$.portrait.getBoundingClientRect();
    const R = this.renderer, H = innerHeight;
    P.cam.aspect = r.width / r.height; P.cam.updateProjectionMatrix();
    R.setScissorTest(true);
    R.setScissor(r.left + 3, H - r.bottom + 3, r.width - 6, r.height - 6);
    R.setViewport(r.left + 3, H - r.bottom + 3, r.width - 6, r.height - 6);
    R.clearDepth();
    R.render(P.scene, P.cam);
    R.setScissorTest(false);
    R.setViewport(0, 0, innerWidth, innerHeight);
  }

  makeIndicators() {
    const ringMat = c => new THREE.MeshBasicMaterial({ map: this.views.ringTex, color: c, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    const geo = new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
    const aoe = new THREE.Mesh(geo, ringMat('#ffd060')), range = new THREE.Mesh(geo, ringMat('#60a0ff'));
    aoe.visible = range.visible = false; aoe.renderOrder = range.renderOrder = 4;
    this.scene.add(aoe, range);
    return { aoe, range };
  }

  updateIndicators() {
    const m = this.input.mode, I = this.indicator;
    I.aoe.visible = I.range.visible = false;
    if (m?.kind !== 'target' || m.cmd !== 'cast') return;
    const u = this.world.byId.get(m.ids[0]); if (!u) return;
    const a = m.ability;
    if (a.range && a.range < 40) { I.range.visible = true; const r = a.range * 2 + u.r * 2; I.range.scale.set(r, 1, r); I.range.position.set(u.x, this.world.grid.heightAt(u.x, u.y) + 0.1, -u.y); }
    const rad = a.radius || a.effects.find(e => e.radius)?.radius;
    if (rad) {
      const g = this.input.ground(this.input.mouse.x, this.input.mouse.y);
      if (g) { I.aoe.visible = true; I.aoe.scale.set(rad * 2, 1, rad * 2); I.aoe.position.set(g.x, this.world.grid.heightAt(g.x, g.y) + 0.12, -g.y); }
    }
  }

  // ------------------------------------------------------------- selection
  selected() { return this.sel.map(id => this.world.byId.get(id)).filter(e => e && e.alive); }

  select(ids) {
    const w = this.world;
    const prio = e => (e.def.hero ? 0 : e.kind === 'unit' ? (e.def.gatherer ? 2 : 1) : 3);
    const list = [...new Set(ids)].map(id => w.byId.get(id)).filter(e => e && e.alive && !e.hidden);
    // never mix own and foreign entities
    const own = list.filter(e => e.owner === this.me);
    const use = own.length ? own : list.slice(0, 1);
    use.sort((a, b) => prio(a) - prio(b) || a.type.localeCompare(b.type));
    for (const id of this.sel) { const e = w.byId.get(id); if (e) this.views.setSelected(e, null); }
    this.sel = use.map(e => e.id);
    this.subType = use[0]?.type || null;
    for (const e of use) this.views.setSelected(e, e.owner === this.me ? '#5cff6a' : e.team === 0 ? '#ffe060' : e.owner === 5 ? '#ffd060' : '#ff4030');
    this.menu = null;
    if (this.input?.mode?.kind === 'target') this.input.setMode(null);
    if (this.hud) this.hud.sig = '';
  }

  leader() {
    const s = this.selected();
    return s.find(e => e.type === this.subType) || s[0] || null;
  }

  cycleSub() {
    const types = [...new Set(this.selected().map(e => e.type))];
    if (types.length < 2) return;
    this.subType = types[(types.indexOf(this.subType) + 1) % types.length];
    this.menu = null; this.hud.sig = '';
  }

  focusSelection() {
    const s = this.selected(); if (!s.length) return;
    const x = s.reduce((a, e) => a + e.x, 0) / s.length, y = s.reduce((a, e) => a + e.y, 0) / s.length;
    this.cam.lookAt(x, y - 3);
  }

  jumpToAlert() {
    const a = this.alerts.pop();
    if (a) this.cam.lookAt(a.x, a.y - 3); else this.focusSelection();
  }

  jumpHome() { const h = this.world.players[this.me].home; this.cam.lookAt(h.x, h.y - 4); }

  send(cmd) {
    cmd.p = this.me;
    if (this.net.role === 'client') this.net.sendCmd(cmd);
    else this.world.issue(cmd);
  }

  ping(x, y) {
    this.minimap.ping(x, y, this.world.players[this.me].color);
    this.fx.ring(x, y, [1, 0.85, 0.3], 4, 2);
    this.audio.play('alert');
    this.net.sendPing?.(x, y);
  }

  flash(col, a) { this._flash = { col, a, t: 0 }; }

  togglePause() {
    if (this.world?.result) return;
    if (this.net.role) { showPause(this, false); return; }
    this.paused = !this.paused;
    showPause(this, this.paused);
  }

  // ---------------------------------------------------------------- events
  handleEvents() {
    const w = this.world;
    for (const ev of w.events) {
      this.fx.onEvent(ev);
      switch (ev.k) {
        case 'msg': if (ev.p === this.me || ev.p === -1) { this.hud.msg(ev.text, ev.kind); if (ev.kind === 'error') this.audio.play('error'); } break;
        case 'remove': this.views.remove(ev.id); if (this.sel.includes(ev.id)) this.select(this.sel.filter(x => x !== ev.id)); break;
        case 'death': {
          if (this.sel.includes(ev.id)) this.select(this.sel.filter(x => x !== ev.id));
          const e = w.byId.get(ev.id);
          if (e?.kind === 'building') this.audio.play('crumble');
          else if (e?.kind === 'unit' && this.onScreen(e)) this.audio.play('death');
          break;
        }
        case 'hit': { const t = w.byId.get(ev.id); if (t && this.onScreen(t)) this.audio.play(ev.atk === 'pierce' ? 'hit' : 'clash', 0.6); break; }
        case 'proj': { const s = w.byId.get(ev.src); if (s && this.onScreen(s)) this.audio.play('bow', 0.6); break; }
        case 'chop': { const t = w.byId.get(ev.id); if (t && this.onScreen(t)) this.audio.play('chop', 0.5); break; }
        case 'bounty': if (ev.p === this.me) { this.overlay.float(ev.x, this.world.grid.heightAt(ev.x, ev.y) + 2, -ev.y, '+' + ev.amt, '#ffd84a', 20); this.audio.play('coin'); } break;
        case 'deposit': if (ev.p === this.me && ev.res === 'gold') { const e = w.byId.get(ev.id); if (e && this.onScreen(e)) this.overlay.float(e.x, w.grid.heightAt(e.x, e.y) + 1.8, -e.y, '+' + ev.amt, '#ffd84a', 15); } break;
        case 'miss': { const t = w.byId.get(ev.id); if (t && this.onScreen(t)) this.overlay.float(t.x, w.grid.heightAt(t.x, t.y) + 2, -t.y, 'промах', '#ffffff', 14); break; }
        case 'built': if (ev.p === this.me) this.audio.play('build'); break;
        case 'trained': if (ev.p === this.me) this.audio.play('trained'); break;
        case 'level': { const e = w.byId.get(ev.id); if (e?.owner === this.me) { this.audio.play('level'); this.hud.msg(`${e.def.name} достигает уровня ${ev.level}!`, 'ally'); } break; }
        case 'cast': this.audio.play('cast'); break;
        case 'wave': this.audio.play('horn'); this.hud.banner(`Волна ${ev.n}`, `Крысы лезут из провалов: ${ev.count}`); break;
        case 'alert': if (ev.p === this.me) { this.alerts.push({ x: ev.x, y: ev.y }); if (this.alerts.length > 5) this.alerts.shift(); this.minimap.ping(ev.x, ev.y, '#ff4a3a'); this.audio.play('alert'); this.hud.msg('Нас атакуют! (Пробел — к месту боя)', 'alert'); } break;
        case 'crusade': this.audio.play('horn'); this.hud.banner('Крестовый поход!', '+30% к урону и скорости на 60 секунд'); break;
        case 'boss_dead': this.hud.banner('Крыса-Король повержен!', ''); break;
        case 'end': this.end(ev.result); break;
      }
    }
    if (this.net.role === 'host') this.net.collect(w.events);
    w.events.length = 0;
  }

  onScreen(e) {
    const v = this.views.views.get(e.id);
    const p = v ? v.root.position : new THREE.Vector3(e.x, 0, -e.y);
    return Math.abs(p.x - this.cam.target.x) < this.cam.dist * 1.2 && Math.abs(p.z - this.cam.target.z) < this.cam.dist * 1.1;
  }

  end(result) {
    this.audio.play(result === 'victory' ? 'victory' : 'defeat');
    setTimeout(() => showEnd(this, result), 1800);
  }

  // ------------------------------------------------------------------ frame
  frame(now) {
    if (!this.running) return;
    requestAnimationFrame(t => this.frame(t));
    now = performance.now();
    let dt = Math.max(0, Math.min(0.1, (now - this.last) / 1000));
    this.last = now;
    const w = this.world;
    if (!this.paused) {
      if (this.net.role !== 'client') {
        this.acc += dt * (this.speed || 1);
        let n = 0;
        while (this.acc >= DT && n < 5) {
          this.views.snapshot();
          for (const a of this.allies) a?.tick();
          w.step();
          this.handleEvents();
          this.acc -= DT; n++;
        }
        if (n === 5) this.acc = 0;
        this.net.tick?.();
      } else {
        this.acc = this.net.update(dt);
        this.handleEvents();
      }
    } else dt = 0;
    const alpha = Math.min(1, this.acc / DT);
    this.cam.update(dt);
    this.updateLighting(dt);
    this.fog.update(dt);
    this.views.update(dt, alpha);
    this.fx.update(dt);
    this.input.updateGhost();
    this.updateIndicators();
    this.hover = this.input.box || this.input.mode ? null : this.input.pick(this.input.mouse.x, this.input.mouse.y);
    this.terrain.water.uniforms.time.value += dt;
    this.updatePortrait(dt);
    const R = this.renderer;
    R.setViewport(0, 0, innerWidth, innerHeight);
    R.clear();
    R.render(this.scene, this.camera);
    this.renderPortrait();
    this.overlay.draw(dt);
    this.hud.update(dt);
    this.minimap.update(dt);
  }

  updateLighting(dt) {
    const w = this.world;
    const ph = w.dayPhase;
    // day 0..0.55, dusk to 0.6, night .6-.92, dawn .92-1
    let day;
    if (ph < 0.5) day = 1; else if (ph < 0.6) day = 1 - (ph - 0.5) / 0.1; else if (ph < 0.9) day = 0; else day = (ph - 0.9) / 0.1;
    day = day * day * (3 - 2 * day);
    const t = this.cam.target;
    const sunCol = new THREE.Color(0xfff1d6).lerp(new THREE.Color(0xffb070), (1 - day) * 0.6 * (ph > 0.45 && ph < 0.62 ? 1 : 0.3));
    const moon = new THREE.Color(0x8aa0ff);
    this.sun.color.copy(sunCol.lerp(moon, 1 - day));
    this.sun.intensity = 0.9 + 2.3 * day;
    this.hemi.intensity = 0.55 + 0.6 * day;
    this.hemi.color.set(day > 0.5 ? 0xbfd8ff : 0x6d7fc8);
    this.renderer.toneMappingExposure = 0.85 + 0.2 * day;
    const d = this.sunDir;
    this.sun.position.set(t.x + d.x * 60, t.y + d.y * 60, t.z + d.z * 60);
    this.sun.target.position.copy(t);
    // snap the shadow frustum to texels so shadows don't shimmer while panning
    const texel = 72 / 2048;
    this.sun.target.position.x = Math.round(t.x / texel) * texel;
    this.sun.target.position.z = Math.round(t.z / texel) * texel;
    this.sun.position.x = this.sun.target.position.x + d.x * 60;
    this.sun.position.z = this.sun.target.position.z + d.z * 60;
    const W = this.terrain.water.uniforms;
    W.dayLight.value = 0.45 + 0.55 * day;
    W.sunDir.value.copy(d);
    if (this._flash) {
      this._flash.t += dt;
      if (this._flash.t > 1.2) this._flash = null;
    }
    void dt;
  }
}

const app = new App();
window.__app = app;
app.boot().catch(err => {
  console.error(err);
  const m = document.querySelector('#loading .msg');
  if (m) m.textContent = 'Ошибка загрузки: ' + err.message;
});
export { HZ };
