// Networking placeholder: single-player runs with role = null. The co-op
// transport (host-authoritative over WebRTC) plugs in here.
export class Net {
  constructor(app) { this.app = app; this.role = null; }
  attach() {}
  collect() {}
  update() { return 0; }
  tick() {}
  sendCmd() {}
  sendPing() {}
}
