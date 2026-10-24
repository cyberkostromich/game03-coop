"""blender -b -P clipcheck.py -- uid [uid...]"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from akit import clipcheck, units
ids = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else list(units.REGISTRY)
for uid in ids or list(units.REGISTRY):
    clipcheck.check(uid)
