import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import importlib
import numpy as np
from akit import build, beast, rig, render, geo

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "/tmp/lineup.png"
build.reset_scene()
xs = {"cat": -1.8, "dog": -0.9, "hamster": 0.0, "hare": 0.9, "rat": 1.8}
for sp, x in xs.items():
    b = beast.body_for(sp)
    parts = beast.fur_body(b)
    ob = build.parts_to_object(parts, sp)
    arm = rig.create_armature(sp, beast.skeleton(b))
    rig.bind(ob, arm)
    arm.location.x = x
    print(sp, "verts", len(ob.data.vertices), "tris", sum(len(p.vertices) - 2 for p in ob.data.polygons))
render.setup_render((1600, 700), 32)
render.setup_world()
render.lights()
render.ground()
render.camera((0, 0, 0.55), 6.2, 16, 22, lens=55)
render.render(out)
