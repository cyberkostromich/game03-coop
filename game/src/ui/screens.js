// Full-screen panels: main menu / lobby, pause, end of match.
import { BASE } from '../data.js';

const FAC = {
  cats: { hero: 'cat_hero_murena', tag: 'Скрытность и элита. Ночью невидимы, первый удар ×2.' },
  dogs: { hero: 'dog_hero_rex', tag: 'Стая и оборона. +5% урона за пса рядом, чуют невидимых.' },
  hamsters: { hero: 'ham_hero_puhloshek', tag: 'Экономика и масса. Рабочие несут ×2 ресурса.' },
  hares: { hero: 'hare_hero_belyana', tag: 'Скорость и прыжки. Самые быстрые войска.' },
};

function screen(id, html) {
  document.getElementById(id)?.remove();
  const d = document.createElement('div');
  d.id = id; d.className = 'screen';
  d.innerHTML = html;
  document.body.appendChild(d);
  return d;
}

export function showMenu(app, onStart) {
  const D = app.D;
  const st = { faction: localStorage.getItem('ak.faction') || 'cats', allies: +(localStorage.getItem('ak.allies') ?? 1), diff: localStorage.getItem('ak.diff') || 'normal', name: localStorage.getItem('ak.name') || 'Игрок' };
  try { void 0; } catch { /* storage may be blocked */ }
  const d = screen('menuScreen', `
    <div class="card frame">
      <div class="gem" style="left:-9px;top:-9px"></div><div class="gem" style="right:-9px;top:-9px"></div>
      <h1>Звериные королевства</h1>
      <p class="sub">Оборона Королевства · карта «${D.map.name}» · до 4 игроков против Крысиной Чумы</p>
      <h2>Ваше королевство</h2>
      <div class="facs">${Object.entries(FAC).map(([k, f]) => `
        <div class="fac ${k === st.faction ? 'on' : ''}" data-f="${k}">
          <img src="${BASE}docs/renders/units/${f.hero}.png" alt="">
          <b>${D.factions[k].name}</b><small>${f.tag}</small></div>`).join('')}</div>
      <h2>Союзники под управлением компьютера</h2>
      <div class="row" id="allyRow">${[0, 1, 2, 3].map(n => `<div class="opt ${n === st.allies ? 'on' : ''}" data-a="${n}">${n === 0 ? 'Один' : '+' + n}</div>`).join('')}</div>
      <h2>Сложность Чумы</h2>
      <div class="row" id="diffRow">${[['easy', 'Лёгкая'], ['normal', 'Нормальная'], ['ruthless', 'Безжалостная']].map(([k, n]) => `<div class="opt ${k === st.diff ? 'on' : ''}" data-d="${k}">${n}</div>`).join('')}</div>
      <h2>Кооператив по сети</h2>
      <div class="row"><input type="text" id="pname" value="${st.name}" maxlength="16" placeholder="Имя">
        <div class="opt" id="hostBtn">Создать игру</div>
        <input type="text" id="joinCode" placeholder="Код хоста" maxlength="40"><div class="opt" id="joinBtn">Подключиться</div></div>
      <div id="lobby"></div>
      <button class="big-btn" id="startBtn">В бой!</button>
      <div class="hint">ПКМ — приказ · рамка — выделить · A атака · B строить · Q W E R способности героя · Ctrl+1..9 отряды · F10 меню</div>
    </div>`);
  const sync = () => {
    d.querySelectorAll('.fac').forEach(e => e.classList.toggle('on', e.dataset.f === st.faction));
    d.querySelectorAll('[data-a]').forEach(e => e.classList.toggle('on', +e.dataset.a === st.allies));
    d.querySelectorAll('[data-d]').forEach(e => e.classList.toggle('on', e.dataset.d === st.diff));
    try { localStorage.setItem('ak.faction', st.faction); localStorage.setItem('ak.allies', st.allies); localStorage.setItem('ak.diff', st.diff); } catch { /* private mode */ }
  };
  d.addEventListener('click', e => {
    const f = e.target.closest('[data-f]'), a = e.target.closest('[data-a]'), df = e.target.closest('[data-d]');
    if (f) st.faction = f.dataset.f; if (a) st.allies = +a.dataset.a; if (df) st.diff = df.dataset.d;
    sync();
  });
  d.querySelector('#pname').addEventListener('input', e => { st.name = e.target.value || 'Игрок'; try { localStorage.setItem('ak.name', st.name); } catch { /* */ } });
  const build = () => {
    const others = Object.keys(FAC).filter(k => k !== st.faction);
    const names = { cats: 'Сэр Мурлыка', dogs: 'Барон Гав', hamsters: 'Пан Хомяк', hares: 'Боярин Косой' };
    const players = [{ name: st.name, faction: st.faction }];
    for (let i = 0; i < st.allies; i++) players.push({ name: names[others[i]] + ' (ИИ)', faction: others[i], ai: true });
    return { players, me: 0, difficulty: st.diff, seed: (Math.random() * 1e9) | 0 };
  };
  d.querySelector('#startBtn').onclick = () => { d.remove(); onStart(build()); };
  d.querySelector('#hostBtn').onclick = () => app.net.host?.(st, d, cfg => { d.remove(); onStart(cfg); });
  d.querySelector('#joinBtn').onclick = () => app.net.join?.(d.querySelector('#joinCode').value.trim(), st, d, cfg => { d.remove(); onStart(cfg); });
}

export function showPause(app, on) {
  if (!on) { document.getElementById('pauseScreen')?.remove(); if (app.net.role) return; }
  if (!on) return;
  const d = screen('pauseScreen', `<div class="card frame"><h1>Пауза</h1>
    <button class="big-btn" id="resume">Продолжить</button>
    <button class="big-btn" id="speed">Скорость: ${app.speed === 1.5 ? 'быстро' : 'обычно'}</button>
    <button class="big-btn" id="quit">Сдаться</button></div>`);
  d.querySelector('#resume').onclick = () => app.togglePause();
  d.querySelector('#speed').onclick = e => { app.speed = app.speed === 1.5 ? 1 : 1.5; e.target.textContent = 'Скорость: ' + (app.speed === 1.5 ? 'быстро' : 'обычно'); };
  d.querySelector('#quit').onclick = () => location.reload();
}

export function showEnd(app, result) {
  const w = app.world;
  const t = Math.floor(w.time);
  const rows = w.players.map(p => `<tr><td style="color:${p.color}">■</td><td>${p.name}</td><td>${p.stats.kills}</td><td>${p.stats.lost}</td><td>${Math.floor(p.mined)}</td><td>${p.stats.gathered}</td></tr>`).join('');
  const d = screen('endScreen', `<div class="card frame">
    <div class="res ${result}">${result === 'victory' ? 'Победа!' : 'Поражение'}</div>
    <p class="sub">${result === 'victory' ? 'Крысиная Чума отброшена в подземелья. Королевство спасено!' : 'Ратуши пали. Крысы празднуют в наших амбарах…'}</p>
    <p class="sub">Время: ${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')} · Волн отбито: ${w.director.n}</p>
    <table><tr><th></th><th>Игрок</th><th>Убито</th><th>Потеряно</th><th>Золото</th><th>Ресурсы</th></tr>${rows}</table>
    <button class="big-btn" id="again">Ещё раз</button></div>`);
  d.querySelector('#again').onclick = () => location.reload();
}
