"""Package the web client as a self-contained folder (build/web/) that can be
served from any static host or published as an Artifact.

  python3 tools/web/bundle.py            -> build/web/ (index.html with doctype)
  python3 tools/web/bundle.py --artifact -> build/web/ with an artifact page
                                            (no document skeleton, base './')
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "build", "web")
artifact = "--artifact" in sys.argv

shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
shutil.copytree(os.path.join(ROOT, "game", "src"), os.path.join(OUT, "src"))
shutil.copytree(os.path.join(ROOT, "data"), os.path.join(OUT, "data"))
A = os.path.join(ROOT, "assets", "animal_kingdoms")
for sub in ("units", "buildings", "props"):
    src = os.path.join(A, sub)
    if not os.path.isdir(src):
        continue
    dst = os.path.join(OUT, "assets", "animal_kingdoms", sub)
    os.makedirs(dst)
    for fn in os.listdir(src):
        if fn.endswith((".glb", ".json")):
            shutil.copy(os.path.join(src, fn), dst)
maps = os.path.join(OUT, "assets", "animal_kingdoms", "maps")
os.makedirs(maps)
for fn in os.listdir(os.path.join(A, "maps")):
    if fn.endswith(".bin") or fn.endswith("_splat.png"):
        shutil.copy(os.path.join(A, "maps", fn), maps)
rend = os.path.join(OUT, "docs", "renders", "units")
os.makedirs(rend)
for h in ("cat_hero_murena", "dog_hero_rex", "ham_hero_puhloshek", "hare_hero_belyana"):
    p = os.path.join(ROOT, "docs", "renders", "units", h + ".png")
    if os.path.exists(p):
        shutil.copy(p, rend)

html = open(os.path.join(ROOT, "game", "index.html"), encoding="utf-8").read()
html = html.replace('<meta name="ak-base" content="../">', '<meta name="ak-base" content="./">')
if artifact:
    # the host wraps the page in its own document skeleton
    head = re.search(r"<head>(.*)</head>", html, re.S).group(1)
    body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
    head = re.sub(r'<meta charset="utf-8">\s*|<meta name="viewport"[^>]*>\s*', "", head)
    css = open(os.path.join(ROOT, "game", "src", "ui", "style.css"), encoding="utf-8").read()
    head = head.replace('<link rel="stylesheet" href="src/ui/style.css">', "<style>\n" + css + "\n</style>")
    # artifact frames forbid WebRTC: the menu offers computer allies instead of network play
    head = '<meta name="ak-net" content="off">\n<meta name="ak-pack" content="json">\n' + head
    page = head.strip() + "\n<style>html,body{height:100%;background:#0b0906;color-scheme:dark}</style>\n" + body.strip() + "\n"
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
else:
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)

if artifact:
    # artifact hosting serves text and image types only: GLB -> glTF JSON +
    # .webp textures, map binaries -> base64 inside a JSON file
    sys.path.insert(0, os.path.dirname(__file__))
    from glb2gltf import convert
    import base64
    for sub in ("units", "buildings", "props"):
        d = os.path.join(OUT, "assets", "animal_kingdoms", sub)
        if not os.path.isdir(d):
            continue
        manifest = os.path.join(d, sub + ".json")
        meta = json.load(open(manifest)) if os.path.exists(manifest) else {}
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".glb"):
                continue
            mid = fn[:-4]
            convert(os.path.join(d, fn), os.path.join(d, mid + ".gltf.json"), mid + "_tex")
            os.remove(os.path.join(d, fn))
            if mid in meta:
                meta[mid]["file"] = mid + ".gltf.json"
        if meta:
            json.dump(meta, open(manifest, "w"), ensure_ascii=False)
    md = os.path.join(OUT, "assets", "animal_kingdoms", "maps")
    for fn in sorted(os.listdir(md)):
        if fn.endswith("_height.bin"):
            name = fn[:-len("_height.bin")]
            pack = {k: base64.b64encode(open(os.path.join(md, f"{name}_{k}.bin"), "rb").read()).decode() for k in ("height", "path")}
            json.dump(pack, open(os.path.join(md, name + "_bins.json"), "w"))
    for fn in os.listdir(md):
        if fn.endswith(".bin"):
            os.remove(os.path.join(md, fn))

files = []
for d, _, fs in os.walk(OUT):
    for f in fs:
        rel = os.path.relpath(os.path.join(d, f), OUT)
        if rel != "index.html":
            files.append((rel, os.path.getsize(os.path.join(d, f))))
json.dump(sorted(files), open(os.path.join(ROOT, "build", "web_files.json"), "w"))
print(len(files), "files", round(sum(s for _, s in files) / 1e6, 1), "MB")
