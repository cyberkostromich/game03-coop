// Procedural sound: small WebAudio synth for clashes, bows, UI clicks and
// horns. No assets needed; volumes are kept low and rate-limited.
export class Audio {
  constructor() {
    this.ctx = null;
    this.vol = 0.5;
    this.last = {};
  }

  unlock() {
    if (this.ctx) { if (this.ctx.state === 'suspended') this.ctx.resume(); return; }
    try {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      this.master = this.ctx.createGain(); this.master.gain.value = this.vol;
      this.comp = this.ctx.createDynamicsCompressor();
      this.master.connect(this.comp); this.comp.connect(this.ctx.destination);
      const n = this.ctx.sampleRate;
      this.noise = this.ctx.createBuffer(1, n, n);
      const d = this.noise.getChannelData(0);
      for (let i = 0; i < n; i++) d[i] = Math.random() * 2 - 1;
    } catch { this.ctx = null; }
  }

  gate(name, ms) {
    const now = performance.now();
    if (now - (this.last[name] || 0) < ms) return false;
    this.last[name] = now; return true;
  }

  tone(f0, f1, dur, type = 'sine', vol = 0.2, delay = 0) {
    const c = this.ctx; if (!c) return;
    const t = c.currentTime + delay;
    const o = c.createOscillator(), g = c.createGain();
    o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vol, t + 0.01); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(g); g.connect(this.master); o.start(t); o.stop(t + dur + 0.05);
  }

  hiss(dur, freq, q, vol = 0.2, delay = 0, type = 'bandpass') {
    const c = this.ctx; if (!c) return;
    const t = c.currentTime + delay;
    const s = c.createBufferSource(); s.buffer = this.noise; s.playbackRate.value = 0.8 + Math.random() * 0.4;
    const f = c.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
    const g = c.createGain(); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    s.connect(f); f.connect(g); g.connect(this.master); s.start(t, Math.random() * 0.5); s.stop(t + dur + 0.05);
  }

  play(name, k = 1) {
    if (!this.ctx) return;
    const v = Math.max(0.05, Math.min(1, k));
    switch (name) {
      case 'clash': if (this.gate('clash', 60)) { this.hiss(0.12, 3200 + Math.random() * 1500, 6, 0.16 * v); this.tone(1800 + Math.random() * 600, 900, 0.18, 'triangle', 0.05 * v); } break;
      case 'hit': if (this.gate('hit', 50)) this.hiss(0.09, 700, 1.2, 0.14 * v, 0, 'lowpass'); break;
      case 'bow': if (this.gate('bow', 70)) { this.hiss(0.18, 1500, 3, 0.07 * v); this.tone(320, 120, 0.12, 'triangle', 0.05 * v); } break;
      case 'chop': if (this.gate('chop', 120)) { this.tone(260, 120, 0.08, 'square', 0.04 * v); this.hiss(0.06, 1200, 2, 0.08 * v); } break;
      case 'coin': if (this.gate('coin', 90)) { this.tone(1900, 1900, 0.08, 'square', 0.025); this.tone(2500, 2500, 0.12, 'square', 0.025, 0.06); } break;
      case 'click': this.tone(900, 600, 0.04, 'triangle', 0.06); break;
      case 'error': if (this.gate('error', 300)) { this.tone(220, 180, 0.12, 'square', 0.05); this.tone(180, 140, 0.16, 'square', 0.05, 0.1); } break;
      case 'build': this.tone(392, 392, 0.15, 'triangle', 0.08); this.tone(523, 523, 0.25, 'triangle', 0.08, 0.14); break;
      case 'trained': this.tone(523, 523, 0.12, 'triangle', 0.07); this.tone(659, 659, 0.12, 'triangle', 0.07, 0.1); this.tone(784, 784, 0.25, 'triangle', 0.07, 0.2); break;
      case 'level': [523, 659, 784, 1046].forEach((f, i) => this.tone(f, f, 0.3, 'triangle', 0.08, i * 0.08)); break;
      case 'horn': if (this.gate('horn', 3000)) { this.tone(146, 150, 1.6, 'sawtooth', 0.06); this.tone(220, 224, 1.6, 'sawtooth', 0.04, 0.05); this.hiss(1.4, 300, 0.7, 0.05, 0, 'lowpass'); } break;
      case 'alert': if (this.gate('alert', 2500)) { this.tone(660, 660, 0.18, 'square', 0.05); this.tone(520, 520, 0.3, 'square', 0.05, 0.2); } break;
      case 'cast': if (this.gate('cast', 120)) { this.tone(400, 1200, 0.35, 'sine', 0.08); this.hiss(0.4, 2400, 1.5, 0.05); } break;
      case 'death': if (this.gate('death', 120)) this.tone(300, 90, 0.35, 'sawtooth', 0.04 * v); break;
      case 'crumble': this.hiss(1.4, 300, 0.6, 0.25, 0, 'lowpass'); this.tone(80, 40, 1.2, 'sine', 0.2); break;
      case 'victory': [392, 523, 659, 784, 1046].forEach((f, i) => this.tone(f, f, 0.6, 'triangle', 0.09, i * 0.15)); break;
      case 'defeat': [392, 349, 311, 262].forEach((f, i) => this.tone(f, f * 0.98, 0.7, 'sawtooth', 0.05, i * 0.3)); break;
    }
  }

  // unit acknowledgement "barks" as short pitched chirps per species
  ack(e, kind) {
    if (!this.ctx || !e || !this.gate('ack', 250)) return;
    const base = { cats: 620, dogs: 330, hamsters: 880, hares: 740, rats: 500 }[e.def?.faction] || 500;
    const f = kind === 'attack' ? base * 1.25 : base;
    this.tone(f, f * 1.35, 0.09, 'triangle', 0.05);
    this.tone(f * 1.2, f * 0.9, 0.12, 'triangle', 0.04, 0.08);
  }

  select(e) { if (e?.kind === 'unit') this.ack(e, 'select'); else this.play('click'); }
}
