"""Build unit GLBs + previews.  blender -b -P tools/blender/build_units.py -- [ids...]"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from akit import pipeline, units  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "animal_kingdoms", "units")
PREV = os.path.join(ROOT, "docs", "renders", "units")

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
no_preview = "--no-preview" in args
ids = [a for a in args if not a.startswith("--")] or list(units.REGISTRY)
os.makedirs(PREV, exist_ok=True)
META = os.path.join(OUT, "meta")
os.makedirs(META, exist_ok=True)
for uid in ids:
    t0 = time.time()
    meta = pipeline.build_unit(uid, OUT, None if no_preview else PREV)
    json.dump(meta, open(os.path.join(META, uid + ".json"), "w"), ensure_ascii=False, indent=1)
    print(f"BUILT {uid}: {meta['tris']} tris, {meta['bones']} bones, {time.time() - t0:.1f}s", flush=True)

# merge per-unit metadata (safe with parallel builders)
manifest = {}
for fn in sorted(os.listdir(META)):
    if fn.endswith(".json"):
        m = json.load(open(os.path.join(META, fn)))
        manifest[m["id"]] = m
json.dump(manifest, open(os.path.join(OUT, "units.json"), "w"), ensure_ascii=False, indent=1)
