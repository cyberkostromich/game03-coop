"""Generate the 'Mill Pond' (Мельничный пруд) map: heightmap, splat, pathing, layout.

python3 tools/map/mill_pond.py
Outputs:
  assets/animal_kingdoms/maps/mill_pond_height.png  16-bit heights (see json for range)
  assets/animal_kingdoms/maps/mill_pond_splat.png   RGBA = grass, dirt, sand, rock weights
  assets/animal_kingdoms/maps/mill_pond_path.png    walkable (255) / blocked (0)
  data/maps/mill_pond.json                          entities, starts, trees, doodads
World units are metres; x = east, y = north; the map spans [-SIZE/2, SIZE/2].
"""
import json
import math
import os

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIZE = 192.0
RES = 385                       # 0.5 m per sample
WATER = 0.0                     # water plane height
rng = np.random.default_rng(1977)

xs = np.linspace(-SIZE / 2, SIZE / 2, RES)
X, Y = np.meshgrid(xs, xs)      # Y[i, j] = north coordinate of row i


def fbm(x, y, octaves=4, scale=40.0, seed=0):
    r = np.random.default_rng(seed)
    out = np.zeros_like(x)
    amp, freq = 1.0, 1.0 / scale
    for _ in range(octaves):
        ph = r.uniform(0, 100, 4)
        out += amp * (np.sin(x * freq + ph[0]) * np.cos(y * freq * 1.3 + ph[1])
                      + 0.5 * np.sin((x + y) * freq * 0.7 + ph[2]) * np.sin((x - y) * freq * 1.1 + ph[3]))
        amp *= 0.5
        freq *= 2.1
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def seg_dist(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    t = np.clip(((px - ax) * abx + (py - ay) * aby) / (abx * abx + aby * aby), 0, 1)
    return np.hypot(px - (ax + t * abx), py - (ay + t * aby)), t


def poly_dist(px, py, pts):
    d = np.full(px.shape, 1e9)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        dd, _ = seg_dist(px, py, ax, ay, bx, by)
        d = np.minimum(d, dd)
    return d


# --- layout --------------------------------------------------------------
POND_C, POND_R = (0.0, 8.0), (30.0, 22.0)
ISLAND_C, ISLAND_R = (0.0, 9.0), 8.5
RIVERS = {
    "west": [(-28, 6), (-50, 2), (-72, 10), (-97, 6)],
    "east": [(28, 12), (52, 16), (74, 8), (97, 14)],
    "north": [(4, 29), (8, 46), (-2, 64), (6, 97)],
}
RIVER_W = 5.0
CROSSINGS = [  # (kind, x, y, angle_deg)  bridges are walkable decks, fords are shallow
    ("bridge", -60.5, 5.0, 85), ("ford", -84.0, 8.0, 90),
    ("bridge", 62.0, 12.5, 95), ("ford", 85.0, 11.0, 90),
    ("bridge", 2.0, 55.0, 5), ("ford", 7.0, 80.0, 0),
    ("ford", 0.0, -11.0, 0),            # south ford to the island
]
STARTS = [(-62, -58), (-21, -66), (21, -66), (62, -58)]
MINES = [(-70, -44), (-30, -48), (30, -48), (70, -44), (-72, 30), (72, 34), (0, 12)]   # last = island (rich)
SHRINES = [("old_oak", -44, 32), ("moon_stone", 44, 38), ("mill", 0, 7)]
CAMPS = [  # (difficulty, x, y)
    ("green", -45, -34), ("green", 45, -34), ("green", 0, -40),
    ("yellow", -82, -12), ("yellow", 82, -10), ("yellow", -28, 28), ("yellow", 30, 30),
    ("red", -60, 58), ("red", 60, 60),
]
PITS = [(0, 84, 0), (-40, 76, 1), (42, 78, 1), (-74, 62, 2), (76, 64, 2)]   # (x, y, opens_after_wave)
SHOALS = [(-14, -6), (14, -6), (-24, 14), (24, 18)]

# --- heights ---------------------------------------------------------------
H = 1.3 + 0.45 * fbm(X, Y, 4, 30, 1) + 0.18 * fbm(X, Y, 3, 7, 2)
H = np.maximum(H, 0.55)
# raised rim of hills around the border
edge = np.maximum(np.abs(X), np.abs(Y)) / (SIZE / 2)
H += 7.0 * smoothstep(0.8, 1.0, edge) * (0.7 + 0.3 * fbm(X, Y, 3, 12, 3))
# base plateaus flattened
for sx, sy in STARTS:
    d = np.hypot(X - sx, Y - sy)
    w = 1 - smoothstep(14, 22, d)
    H = H * (1 - w) + (1.4 + 0.08 * fbm(X, Y, 2, 9, 4)) * w
# pond basin
pd = np.hypot((X - POND_C[0]) / POND_R[0], (Y - POND_C[1]) / POND_R[1])
H = np.where(pd < 1.15, H * smoothstep(0.85, 1.15, pd) - 2.6 * (1 - smoothstep(0.55, 1.0, pd)), H)
# rivers
river_mask = np.zeros_like(H)
for pts in RIVERS.values():
    d = poly_dist(X, Y, pts)
    w = 1 - smoothstep(RIVER_W * 0.5, RIVER_W * 1.1, d)
    river_mask = np.maximum(river_mask, w)
    H = H * (1 - w) + (-1.7) * w
# island
idist = np.hypot(X - ISLAND_C[0], Y - ISLAND_C[1])
iw = 1 - smoothstep(ISLAND_R * 0.75, ISLAND_R * 1.15, idist)
H = H * (1 - iw) + 1.1 * iw
# crossings
for kind, cx, cy, ang in CROSSINGS:
    a = math.radians(ang)
    dx, dy = math.cos(a), math.sin(a)
    along = (X - cx) * dx + (Y - cy) * dy
    across = -(X - cx) * dy + (Y - cy) * dx
    L = 9.0 if kind == "ford" else 8.0
    w = (1 - smoothstep(L * 0.5, L * 0.7, np.abs(along))) * (1 - smoothstep(2.6, 3.4, np.abs(across)))
    if kind == "ford":
        H = np.where(w > 0, H * (1 - w) + (-0.25) * w, H)
# --- walkability -------------------------------------------------------------
walk = H > -0.45
for kind, cx, cy, ang in CROSSINGS:
    if kind == "bridge":
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        along = (X - cx) * dx + (Y - cy) * dy
        across = -(X - cx) * dy + (Y - cy) * dx
        walk |= (np.abs(along) < 6.5) & (np.abs(across) < 1.8)
slope = np.hypot(*np.gradient(H, SIZE / (RES - 1)))
walk &= slope < 0.9
walk &= edge < 0.94

# --- splat -----------------------------------------------------------------
grass = np.ones_like(H)
sand = 1 - smoothstep(0.25, 0.75, H)                     # shores only
rock = smoothstep(0.45, 0.9, slope) + smoothstep(4.0, 6.5, H)
dirt = np.zeros_like(H)
paths = [STARTS[0], (-40, -40), (0, -40), (40, -40), STARTS[3]]
dirt = np.maximum(dirt, 1 - smoothstep(1.2, 3.0, poly_dist(X, Y, paths)))
for s in STARTS:
    dirt = np.maximum(dirt, (1 - smoothstep(6, 12, np.hypot(X - s[0], Y - s[1]))) * 0.85)
    dirt = np.maximum(dirt, 1 - smoothstep(1.2, 3.0, poly_dist(X, Y, [s, (0, -14)])))
lanes = [(0, 84), (2, 55), (0, 34), (-14, 30), (-60, 6), (-62, -58)]
dirt = np.maximum(dirt, 1 - smoothstep(1.4, 3.2, poly_dist(X, Y, lanes)))
lanes2 = [(0, 34), (16, 32), (62, 12), (62, -58)]
dirt = np.maximum(dirt, 1 - smoothstep(1.4, 3.2, poly_dist(X, Y, lanes2)))
for m in MINES:
    dirt = np.maximum(dirt, 1 - smoothstep(3, 6, np.hypot(X - m[0], Y - m[1])))
dirt *= 0.6 + 0.4 * (fbm(X, Y, 3, 5, 9) * 0.5 + 0.5)
dirt = np.clip(dirt, 0, 1)
w = np.stack([grass, dirt * 1.6, sand * 1.4, rock * 1.8], -1)
w = np.clip(w, 0, None)
w[..., 0] = np.clip(1 - w[..., 1:].max(-1), 0, 1) + 0.02
w /= w.sum(-1, keepdims=True)

# --- forests & doodads -----------------------------------------------------------
keep_clear = [(s, 16) for s in STARTS] + [(m, 6) for m in MINES] + [((c[1], c[2]), 7) for c in CAMPS] + \
             [((s[1], s[2]), 7) for s in SHRINES] + [((p[0], p[1]), 7) for p in PITS]


def clear_at(x, y, extra=0.0):
    for (cx, cy), r in keep_clear:
        if math.hypot(x - cx, y - cy) < r + extra:
            return False
    return True


def sample(ix, iy):
    return float(H[iy, ix]), bool(walk[iy, ix]), float(w[iy, ix, 1]), float(river_mask[iy, ix])


def to_idx(x, y):
    return (int(round((x + SIZE / 2) / SIZE * (RES - 1))), int(round((y + SIZE / 2) / SIZE * (RES - 1))))


trees = []
forest_density = 0.5 + 0.5 * fbm(X, Y, 3, 18, 21)
for _ in range(9000):
    x, y = rng.uniform(-SIZE / 2 + 2, SIZE / 2 - 2, 2)
    ix, iy = to_idx(x, y)
    h, wk, dr, rv = sample(ix, iy)
    if h < 0.6 or dr > 0.3 or rv > 0.05 or not clear_at(x, y):
        continue
    near_edge = max(abs(x), abs(y)) > SIZE / 2 - 22
    behind_base = any(math.hypot(x - s[0], y - (s[1] - 12)) < 20 and y < s[1] - 6 for s in STARTS)
    dens = forest_density[iy, ix]
    clump = dens > 0.62
    p = 0.85 if near_edge else (0.7 if behind_base else (0.75 if clump else 0.03))
    if rng.random() > p:
        continue
    if any((x - t["x"]) ** 2 + (y - t["y"]) ** 2 < 3.2 ** 2 for t in trees[-60:]):
        continue
    kind = rng.choice(["oak", "pine", "pine", "birch"]) if y > -30 else rng.choice(["oak", "oak", "pine", "birch"])
    trees.append({"type": str(kind), "x": round(float(x), 2), "y": round(float(y), 2),
                  "s": round(float(rng.uniform(0.85, 1.25)), 2), "r": round(float(rng.uniform(0, 360)), 1)})
    if len(trees) > 1400:
        break
doodads = []
for _ in range(2500):
    x, y = rng.uniform(-SIZE / 2 + 4, SIZE / 2 - 4, 2)
    ix, iy = to_idx(x, y)
    h, wk, dr, rv = sample(ix, iy)
    if not clear_at(x, y, -3):
        continue
    if -0.6 < h < 0.25 and rng.random() < 0.6:
        doodads.append({"type": "reeds", "x": round(float(x), 2), "y": round(float(y), 2), "s": round(float(rng.uniform(0.8, 1.3)), 2)})
    elif h < -1.0 and rng.random() < 0.12:
        doodads.append({"type": "lily", "x": round(float(x), 2), "y": round(float(y), 2), "s": round(float(rng.uniform(0.7, 1.2)), 2)})
    elif h > 0.4 and rng.random() < 0.08:
        doodads.append({"type": str(rng.choice(["rock", "bush", "bush", "flowers", "mushrooms"])),
                        "x": round(float(x), 2), "y": round(float(y), 2), "s": round(float(rng.uniform(0.7, 1.4)), 2),
                        "r": round(float(rng.uniform(0, 360)), 1)})
    if len(doodads) > 900:
        break

# --- write --------------------------------------------------------------------------
hmin, hmax = float(H.min()), float(H.max())
h16 = ((H - hmin) / (hmax - hmin) * 65535).astype(np.uint16)
out_dir = os.path.join(ROOT, "assets", "animal_kingdoms", "maps")
Image.fromarray(h16[::-1]).save(os.path.join(out_dir, "mill_pond_height.png"))
Image.fromarray((w[::-1] * 255).astype(np.uint8), "RGBA").save(os.path.join(out_dir, "mill_pond_splat.png"))
Image.fromarray((walk[::-1] * 255).astype(np.uint8)).save(os.path.join(out_dir, "mill_pond_path.png"))
layout = {
    "name": "Мельничный пруд", "id": "mill_pond", "size": SIZE, "resolution": RES,
    "height_min": hmin, "height_max": hmax, "water_level": WATER,
    "images": {"height": "mill_pond_height.png", "splat": "mill_pond_splat.png", "path": "mill_pond_path.png"},
    "_note": "Images are stored north-up (row 0 = north edge).",
    "starts": [{"x": x, "y": y} for x, y in STARTS],
    "gold_mines": [{"x": x, "y": y, "rich": i == len(MINES) - 1} for i, (x, y) in enumerate(MINES)],
    "shrines": [{"id": n, "x": x, "y": y} for n, x, y in SHRINES],
    "camps": [{"level": l, "x": x, "y": y} for l, x, y in CAMPS],
    "rat_pits": [{"x": x, "y": y, "opens_after_wave": o} for x, y, o in PITS],
    "crossings": [{"kind": k, "x": x, "y": y, "angle": a} for k, x, y, a in CROSSINGS],
    "fishing_shoals": [{"x": x, "y": y} for x, y in SHOALS],
    "rivers": RIVERS, "pond": {"x": POND_C[0], "y": POND_C[1], "rx": POND_R[0], "ry": POND_R[1]},
    "island": {"x": ISLAND_C[0], "y": ISLAND_C[1], "r": ISLAND_R},
    "trees": trees, "doodads": doodads,
}
json.dump(layout, open(os.path.join(ROOT, "data", "maps", "mill_pond.json"), "w"), ensure_ascii=False)
print("height", round(hmin, 2), round(hmax, 2), "trees", len(trees), "doodads", len(doodads),
      "walkable %.1f%%" % (100 * walk.mean()))

# overview preview
col = np.zeros((RES, RES, 3))
pal = np.array([[0.36, 0.55, 0.25], [0.55, 0.42, 0.28], [0.83, 0.76, 0.55], [0.5, 0.5, 0.5]])
col = (w[..., :, None] * pal[None, None]).sum(2)
col = np.where((H < WATER)[..., None], np.array([0.2, 0.45, 0.6]) * (0.6 + 0.4 * smoothstep(-3, 0, H))[..., None], col)
shade = np.clip(1 + (np.gradient(H, axis=1) - np.gradient(H, axis=0)) * 2.5, 0.6, 1.4)
col = np.clip(col * shade[..., None], 0, 1)
img = Image.fromarray((col[::-1] * 255).astype(np.uint8)).resize((768, 768))
from PIL import ImageDraw
d = ImageDraw.Draw(img)
def px(x, y):
    return ((x + SIZE / 2) / SIZE * 768, (SIZE / 2 - y) / SIZE * 768)
for t in trees:
    cx, cy = px(t["x"], t["y"]); d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(30, 70, 25))
for i, (x, y) in enumerate(STARTS):
    cx, cy = px(x, y); d.rectangle([cx - 8, cy - 8, cx + 8, cy + 8], outline=(255, 255, 255), width=3); d.text((cx - 3, cy - 6), str(i + 1), fill=(255, 255, 255))
for x, y in MINES:
    cx, cy = px(x, y); d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 210, 60))
for l, x, y in CAMPS:
    cx, cy = px(x, y); d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill={"green": (60, 220, 60), "yellow": (240, 220, 40), "red": (230, 60, 50)}[l])
for x, y, o in PITS:
    cx, cy = px(x, y); d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(120, 220, 40), outline=(20, 30, 10), width=2)
for k, x, y, a in CROSSINGS:
    cx, cy = px(x, y); d.rectangle([cx - 4, cy - 4, cx + 4, cy + 4], fill=(140, 90, 40) if k == "bridge" else (200, 200, 200))
for n, x, y in SHRINES:
    cx, cy = px(x, y); d.polygon([(cx, cy - 8), (cx + 7, cy + 5), (cx - 7, cy + 5)], fill=(150, 120, 255))
img.save(os.path.join(ROOT, "docs", "renders", "mill_pond_overview.png"))
