// Mouse and keyboard: box select, smart right-click, targeting modes,
// building placement ghost, control groups and WC3 hotkeys.
import * as THREE from 'three';

const DRAG = 6;

export class Input {
  constructor(app) {
    this.app = app;
    this.w = app.world;
    this.dom = app.renderer.domElement;
    this.mode = null;
    this.box = null;
    this.mouse = { x: 0, y: 0 };
    this.groups = {};
    this.lastGroup = { n: -1, t: 0 };
    this.lastClick = { id: 0, t: 0 };
    this.alt = false;
    this.ghost = null;
    this.dom.addEventListener('contextmenu', e => e.preventDefault());
    this.dom.addEventListener('pointerdown', e => this.down(e));
    addEventListener('pointermove', e => this.move(e));
    addEventListener('pointerup', e => this.up(e));
    addEventListener('keydown', e => this.key(e));
    addEventListener('keyup', e => { if (e.key === 'Alt') this.alt = false; });
    addEventListener('blur', () => { this.alt = false; this.box = null; });
  }

  ndc(x, y) { return { x: x / innerWidth * 2 - 1, y: -(y / innerHeight) * 2 + 1 }; }

  ground(x, y) {
    const n = this.ndc(x, y);
    const p = this.app.cam.groundAt(n.x, n.y);
    return p ? { x: p.x, y: -p.z } : null;
  }

  // entity under the cursor: screen-space test on projected silhouettes
  pick(sx, sy, filter = () => true) {
    const w = this.w, cam = this.app.camera, views = this.app.views.views;
    const v3 = new THREE.Vector3();
    let best = null, bd = Infinity;
    for (const e of w.units.concat(w.blds)) {
      if (!e.alive || e.hidden || !filter(e)) continue;
      const v = views.get(e.id);
      if (!v || !v.root.visible) continue;
      const h = v.height || 1.3;
      const base = v.root.position;
      v3.set(base.x, base.y + h * 0.5, base.z).project(cam);
      if (v3.z > 1) continue;
      const px = (v3.x + 1) / 2 * innerWidth, py = (1 - v3.y) / 2 * innerHeight;
      // projected radius from the entity's size
      v3.set(base.x, base.y + h, base.z).project(cam);
      const top = (1 - v3.y) / 2 * innerHeight;
      const halfH = Math.max(14, Math.abs(py - top));
      const halfW = e.kind === 'building' ? halfH * 1.2 : Math.max(14, halfH * 0.55);
      const dx = (sx - px) / halfW, dy = (sy - py) / halfH;
      const d = dx * dx + dy * dy;
      if (d < 1 && d < bd + (e.kind === 'building' ? 0.3 : 0)) { bd = d; best = e; }
    }
    return best;
  }

  pickTree(g) {
    if (!g) return null;
    return this.w.nearest(g.x, g.y, e => e.kind === 'tree' && e.alive, 1.6);
  }

  pickItem(g) { return g ? this.w.nearest(g.x, g.y, e => e.kind === 'item' && e.alive, 1.4) : null; }

  pickShoal(g) { return g ? this.w.nearest(g.x, g.y, e => e.kind === 'shoal' && e.alive, 3) : null; }

  setMode(m) {
    this.mode = m;
    this.app.root.classList.toggle('target', !!m && (m.kind === 'target' || m.kind === 'ping'));
    if (m?.kind !== 'build') this.clearGhost();
    if (m?.kind === 'build') this.makeGhost(m.type);
    this.app.hud.sig = '';
    if (!m) this.modeButton = null;
  }

  // ------------------------------------------------------------------ mouse
  inUi(e) { return e.target !== this.dom; }

  down(e) {
    this.app.audio?.unlock();
    if (e.button === 0) {
      if (this.mode) { this.applyMode(e); return; }
      this.box = { x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY };
    } else if (e.button === 2) {
      if (this.mode) { this.setMode(null); this.app.menu = null; return; }
      this.smart(e.clientX, e.clientY, e.shiftKey);
    }
  }

  move(e) {
    this.mouse.x = e.clientX; this.mouse.y = e.clientY;
    if (this.box) { this.box.x1 = e.clientX; this.box.y1 = e.clientY; }
    if (this.mode?.kind === 'target') {
      const t = this.pick(e.clientX, e.clientY);
      this.app.root.classList.toggle('enemy', !!t && this.w.isHostile({ team: 0 }, t));
    }
  }

  up(e) {
    if (e.button !== 0 || !this.box) return;
    const b = this.box; this.box = null;
    const app = this.app;
    if (Math.abs(b.x1 - b.x0) < DRAG && Math.abs(b.y1 - b.y0) < DRAG) {
      const t = this.pick(b.x0, b.y0);
      if (!t) { if (!e.shiftKey) app.select([]); return; }
      const now = performance.now();
      if ((now - this.lastClick.t < 350 && this.lastClick.id === t.id) || e.ctrlKey) {
        // double click: all of that type on screen
        app.select(this.onScreen(x => x.owner === t.owner && x.type === t.type).map(x => x.id));
      } else if (e.shiftKey && t.owner === app.me && t.kind === 'unit') {
        app.select(app.sel.includes(t.id) ? app.sel.filter(x => x !== t.id) : [...app.sel, t.id]);
      } else app.select([t.id]);
      this.lastClick = { id: t.id, t: now };
      app.audio?.select(t);
      return;
    }
    const x0 = Math.min(b.x0, b.x1), x1 = Math.max(b.x0, b.x1), y0 = Math.min(b.y0, b.y1), y1 = Math.max(b.y0, b.y1);
    let got = this.onScreen(e2 => e2.owner === app.me && e2.kind === 'unit', [x0, y0, x1, y1]);
    if (!got.length) got = this.onScreen(e2 => e2.owner === app.me && e2.kind === 'building', [x0, y0, x1, y1]).slice(0, 1);
    const ids = got.map(x => x.id);
    app.select(e.shiftKey ? [...new Set([...app.sel, ...ids])] : ids);
    if (got[0]) app.audio?.select(got[0]);
  }

  onScreen(pred, rect = [0, 0, innerWidth, innerHeight - innerHeight * 0.2]) {
    const cam = this.app.camera, views = this.app.views.views, v3 = new THREE.Vector3(), out = [];
    for (const e of this.w.units.concat(this.w.blds)) {
      if (!e.alive || e.hidden || !pred(e)) continue;
      const v = views.get(e.id);
      if (!v || !v.root.visible) continue;
      v3.copy(v.root.position); v3.y += (v.height || 1) * 0.4; v3.project(cam);
      const px = (v3.x + 1) / 2 * innerWidth, py = (1 - v3.y) / 2 * innerHeight;
      if (px >= rect[0] && px <= rect[2] && py >= rect[1] && py <= rect[3]) out.push(e);
    }
    return out.slice(0, 48);
  }

  smart(sx, sy, queue, gOverride) {
    const app = this.app, w = this.w;
    const sel = app.selected().filter(e => e.owner === app.me);
    if (!sel.length) return;
    const g = gOverride || this.ground(sx, sy);
    if (!g) return;
    const units = sel.filter(e => e.kind === 'unit');
    if (!units.length) {                              // buildings: right click = rally point
      const t = gOverride ? null : (this.pick(sx, sy) || this.pickTree(g));
      for (const b of sel) if (b.def.produces.length) app.send({ t: 'rally', building: b.id, x: g.x, y: g.y, target: t?.id || 0 });
      app.fx.marker(g.x, g.y, [1, 0.85, 0.3]);
      return;
    }
    let t = gOverride ? null : this.pick(sx, sy);
    if (!t) t = this.pickItem(g);
    if (!t && units.some(u => u.def.gatherer)) t = this.pickTree(g) || this.pickShoal(g);
    app.send({ t: 'smart', ids: units.map(u => u.id), x: g.x, y: g.y, target: t?.id || 0, queue });
    app.audio?.ack(units[0], t && w.isHostile({ team: 0 }, t) ? 'attack' : 'move');
  }

  // a targeting command aimed at the minimap: ground point only
  applyModeAt(p) {
    const m = this.mode;
    if (!m || m.kind !== 'target' || (m.cmd === 'cast' && m.unitTarget)) return;
    this.applyMode({ clientX: -1, clientY: -1, shiftKey: false }, p);
  }

  applyMode(e, at) {
    const app = this.app, m = this.mode;
    const g = at || this.ground(e.clientX, e.clientY);
    const queue = e.shiftKey;
    if (m.kind === 'ping') { if (g) app.ping(g.x, g.y); this.setMode(null); return; }
    if (m.kind === 'build') {
      const pos = this.ghostPos;
      if (!pos || !pos.ok) { app.hud.flash('Здесь нельзя строить'); app.audio?.play('error'); return; }
      app.send({ t: 'build', ids: m.ids, type: m.type, x: pos.x, y: pos.y, queue });
      app.audio?.ack(app.leader(), 'build');
      if (!queue) { this.setMode(null); app.menu = null; }
      return;
    }
    if (!g) return;
    const t = at ? null : this.pick(e.clientX, e.clientY);
    switch (m.cmd) {
      case 'move': app.send({ t: 'smart', ids: m.ids, x: g.x, y: g.y, target: t && !this.w.isHostile({ team: 0 }, t) ? t.id : 0, queue }); break;
      case 'attack':
        if (t && t.id) app.send({ t: 'attack', ids: m.ids, target: t.id, queue });
        else app.send({ t: 'amove', ids: m.ids, x: g.x, y: g.y, queue });
        break;
      case 'patrol': app.send({ t: 'patrol', ids: m.ids, x: g.x, y: g.y, queue }); break;
      case 'gather': {
        const tt = t || this.pickTree(g) || this.pickShoal(g);
        if (tt) app.send({ t: 'gather', ids: m.ids, target: tt.id, queue });
        break;
      }
      case 'rally': app.send({ t: 'rally', building: m.ids[0], x: g.x, y: g.y, target: (t || this.pickTree(g))?.id || 0 }); break;
      case 'cast': {
        const u = this.w.byId.get(m.ids[0]);
        if (m.unitTarget) {
          if (!t) { app.hud.flash('Выберите цель'); return; }
          if (!this.w.abilities.validTarget(u, m.ability, t)) { app.hud.flash('Неверная цель'); return; }
          app.send({ t: 'cast', id: u.id, key: m.key, target: t.id, queue });
        } else app.send({ t: 'cast', id: u.id, key: m.key, x: g.x, y: g.y, queue });
        break;
      }
    }
    if (m.cmd !== 'cast') app.fx.marker(g.x, g.y, m.cmd === 'attack' ? [1, 0.25, 0.15] : [0.3, 1, 0.35]);
    app.audio?.ack(app.leader(), m.cmd === 'attack' ? 'attack' : 'move');
    if (!queue) this.setMode(null);
  }

  // ------------------------------------------------------------- build ghost
  makeGhost(type) {
    this.clearGhost();
    const d = this.w.defs.buildings[type];
    const g = new THREE.Group();
    const inst = this.app.views.models.instance('buildings', d.model, this.app.hud.me.color);
    if (inst) {
      inst.root.traverse(o => { if (o.isMesh) { o.material = this.app.views.models.ghostOf(o.material, 0.55); o.castShadow = false; } });
      g.add(inst.root);
    }
    const cells = new THREE.Group();
    g.add(cells);
    this.ghost = { g, cells, d };
    this.app.scene.add(g);
  }

  clearGhost() {
    if (!this.ghost) return;
    this.app.scene.remove(this.ghost.g);
    this.ghost = null; this.ghostPos = null;
  }

  updateGhost() {
    if (!this.ghost) return;
    const gp = this.ground(this.mouse.x, this.mouse.y);
    if (!gp) return;
    const d = this.ghost.d, grid = this.w.grid;
    // snap so the footprint covers whole cells
    const sx = Math.round(d.w) % 2 ? 0.5 : 0, sy = Math.round(d.h) % 2 ? 0.5 : 0;
    const x = Math.round(gp.x - sx) + sx, y = Math.round(gp.y - sy) + sy;
    if (this.ghostPos && this.ghostPos.x === x && this.ghostPos.y === y && this.ghostPos.v === grid.version) return;
    const ok = grid.canPlace(x, y, d.w, d.h);
    this.ghostPos = { x, y, ok, v: grid.version };
    const h = grid.heightAt(x, y);
    this.ghost.g.position.set(x, h, -y);
    this.ghost.g.rotation.y = 0;
    // per-cell green/red tiles
    const cg = this.ghost.cells;
    cg.clear();
    const geo = this.cellGeo ||= new THREE.PlaneGeometry(0.92, 0.92).rotateX(-Math.PI / 2);
    const mg = this.cellMats ||= [new THREE.MeshBasicMaterial({ color: 0x35ff55, transparent: true, opacity: 0.45, depthWrite: false }), new THREE.MeshBasicMaterial({ color: 0xff3020, transparent: true, opacity: 0.55, depthWrite: false })];
    for (const i of grid.rectCells(x, y, d.w, d.h)) {
      const [cx, cy] = grid.centre(i);
      const good = grid.free(i) && grid.heightAt(cx, cy) > 0.2;
      const m = new THREE.Mesh(geo, mg[good ? 0 : 1]);
      m.position.set(cx - x, grid.heightAt(cx, cy) - h + 0.08, -(cy - y));
      m.renderOrder = 4;
      cg.add(m);
    }
  }

  // --------------------------------------------------------------- keyboard
  key(e) {
    if (e.target.closest?.('input,textarea')) return;
    const app = this.app;
    if (e.key === 'Alt') { this.alt = true; e.preventDefault(); return; }
    if (e.code === 'F10' || (e.code === 'Escape' && !this.mode && !app.menu && !app.sel.length)) { e.preventDefault(); app.togglePause(); return; }
    if (app.paused) return;
    if (e.code === 'Escape') {
      if (this.mode) this.setMode(null); else if (app.menu) app.menu = null; else app.select([]);
      app.hud.sig = '';
      return;
    }
    const digit = /^Digit(\d)$/.exec(e.code);
    if (digit) {
      const n = +digit[1];
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) { this.groups[n] = [...app.sel]; app.hud.flash(`Отряд ${n} назначен`); return; }
      if (e.shiftKey) { this.groups[n] = [...new Set([...(this.groups[n] || []), ...app.sel])]; return; }
      const g = (this.groups[n] || []).filter(id => this.w.byId.get(id)?.alive);
      if (!g.length) return;
      const now = performance.now();
      app.select(g);
      if (this.lastGroup.n === n && now - this.lastGroup.t < 400) app.focusSelection();
      this.lastGroup = { n, t: now };
      return;
    }
    if (/^F[1-3]$/.test(e.key)) {
      e.preventDefault();
      const P = app.hud.me;
      const h = this.w.byId.get(P.heroes[+e.key[1] - 1]);
      if (h) { if (app.sel.length === 1 && app.sel[0] === h.id) app.focusSelection(); app.select([h.id]); }
      return;
    }
    if (e.code === 'Space') { e.preventDefault(); app.jumpToAlert(); return; }
    if (e.code === 'Tab') { e.preventDefault(); app.cycleSub(); return; }
    if (e.code === 'Backspace' || e.code === 'KeyH' && e.ctrlKey) { app.jumpHome(); return; }
    if (e.ctrlKey || e.metaKey) return;
    if (app.hud.hotkey(e.code)) e.preventDefault();
  }
}
