"""blender -b -P tools/blender/build_props.py -- [ids...]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from akit import pipeline, props  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "animal_kingdoms", "props")
PREV = os.path.join(ROOT, "docs", "renders", "props")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ids = [a for a in args if not a.startswith("--")] or list(props.PROPS)
os.makedirs(PREV, exist_ok=True)
man_path = os.path.join(OUT, "props.json")
manifest = json.load(open(man_path)) if os.path.exists(man_path) else {}
for pid in ids:
    manifest[pid] = pipeline.build_prop(pid, OUT, PREV)
    print("BUILT", pid, manifest[pid]["tris"], flush=True)
os.makedirs(OUT, exist_ok=True)
json.dump(manifest, open(man_path, "w"), indent=1)
