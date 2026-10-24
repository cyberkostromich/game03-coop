"""Render a clip as a filmstrip.  blender -b -P filmstrip.py -- uid Clip f1,f2,... out.png [yaw]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bpy
from akit import build, pipeline, render

a = sys.argv[sys.argv.index("--") + 1:]
uid, clip, frames, out = a[0], a[1], [int(x) for x in a[2].split(",")], a[3]
yaw = float(a[4]) if len(a) > 4 else 28
build.reset_scene()
spec, ob, arm = pipeline.assemble(uid)
pipeline.bake_clips(spec, arm)
h = max(v.co.z for v in ob.data.vertices)
render.setup_render((420, 520), 12)
render.setup_world(); render.lights(); render.ground()
render.camera((0, 0, h * 0.5), h * 2.6, 18, yaw, lens=50)
files = []
for i, f in enumerate(frames):
    pipeline.pose_at(arm, clip, f)
    fp = f"/tmp/fs_{os.getpid()}_{i}.png"; render.render(fp); files.append(fp)
pipeline._stitch(files, out)
