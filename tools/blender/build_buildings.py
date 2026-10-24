"""blender -b -P tools/blender/build_buildings.py -- [ids...]"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from akit import buildings, pipeline  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "animal_kingdoms", "buildings")
PREV = os.path.join(ROOT, "docs", "renders", "buildings")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ids = [a for a in args if not a.startswith("--")] or list(buildings.REGISTRY)
os.makedirs(os.path.join(OUT, "meta"), exist_ok=True)
os.makedirs(PREV, exist_ok=True)
for bid in ids:
    meta = pipeline.build_building(bid, OUT, None if "--no-preview" in args else PREV)
    json.dump(meta, open(os.path.join(OUT, "meta", bid + ".json"), "w"), ensure_ascii=False, indent=1)
    print("BUILT", bid, meta["tris"], flush=True)
manifest = {}
for fn in sorted(os.listdir(os.path.join(OUT, "meta"))):
    m = json.load(open(os.path.join(OUT, "meta", fn)))
    manifest[m["id"]] = m
json.dump(manifest, open(os.path.join(OUT, "buildings.json"), "w"), ensure_ascii=False, indent=1)
