"""Reference-matched beauty shot (Reforged 'Tales from the Smithy' framing).
blender -b -P refshot.py -- uid out.png [clip frame] [--flat]"""
import os, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bpy
from akit import build, pipeline, render

a = sys.argv[sys.argv.index("--") + 1:]
flat = "--flat" in a
a = [x for x in a if not x.startswith("--")]
uid, out = a[0], a[1]
clip = a[2] if len(a) > 2 else "Idle"
frame = int(a[3]) if len(a) > 3 else 1
build.reset_scene()
spec, ob, arm = pipeline.assemble(uid, textured=not flat)
pipeline.bake_clips(spec, arm)
pipeline.pose_at(arm, clip, frame)
h = max(v.co.z for v in ob.data.vertices)
render.setup_render((720, 820), 48)
render.setup_world(0.9, top="#3a68c0", bottom="#16264a")
render.lights(sun_rot=(48, 0, 28), sun_strength=3.8)
g = render.ground("#16264a")
yaw = float(os.environ.get("YAW", 22))
cam = render.camera((0, 0, h * 0.5), h * 2.25, 10, yaw, lens=50)
render.render(out)
if "--rts" in sys.argv:
    render.aim(cam, (0, 0, h * 0.4), h * 4.2, 52, 30)
    render.render(out.replace(".png", "_rts.png"))
