"""Environment props in the WoW / Warcraft idiom.

Chunky silhouettes, oversized canopies made of a few smooth leaf 'clouds'
painted light on top and dark underneath, thick trunks with root flares.
Each prop is a static mesh (one material set, baked painted texture) meant
for GPU instancing in the client.
"""
import math

import numpy as np

from . import geo, palette
from .buildings import beam, rock as _rock, _st


def _blob(c, r, color_top, color_bot, seed, squash=0.8, n=3):
    rng = np.random.default_rng(seed)
    p = geo.qsphere(1.0, n, color_top).tf(scale=(r, r, r * squash))
    p.V += rng.normal(0, r * 0.06, p.V.shape)
    z0, z1 = -r * squash, r * squash
    p.paint(geo.grad_z(color_bot, color_top, z0 * 0.6, z1))
    p.tf(c)
    return _st(p, "foliage")


def trunk(base_r, h, color="#6b4a33", lean=(0.0, 0.0), roots=4, seed=0):
    rng = np.random.default_rng(seed)
    pts = geo.bezier((0, 0, -0.2), (lean[0] * 0.3, lean[1] * 0.3, h * 0.5), (lean[0], lean[1], h), n=7)
    radii = base_r * np.array([1.5, 1.1, 0.95, 0.85, 0.75, 0.65, 0.55])
    t = geo.tube(pts, radii, 9, color=color)
    t.paint(geo.stripes(palette.mul(color, 0.75), axis=2, freq=9, width=0.2))
    out = [_st(t, "wood")]
    for i in range(roots):
        a = 2 * math.pi * i / roots + rng.uniform(-0.3, 0.3)
        d = np.array([math.cos(a), math.sin(a), 0])
        rt = geo.tube([d * base_r * 0.6 + np.array([0, 0, 0.5]), d * base_r * 1.6 + np.array([0, 0, 0.12]),
                       d * base_r * 2.4 + np.array([0, 0, -0.05])], [base_r * 0.55, base_r * 0.35, base_r * 0.15], 6,
                      color=color)
        out.append(_st(rt, "wood"))
    return out


def oak(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = trunk(0.32, 3.2, "#6b4a33", lean=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)), seed=seed)
    top, bot = "#7fbf3a", "#2f6a2a"
    blobs = [((0, 0, 4.4), 1.9)]
    for i in range(6):
        a = 2 * math.pi * i / 6 + rng.uniform(-0.3, 0.3)
        r = rng.uniform(1.1, 1.5)
        blobs.append(((math.cos(a) * 1.6, math.sin(a) * 1.6, 3.7 + rng.uniform(-0.3, 0.5)), r))
    for i in range(3):
        a = rng.uniform(0, 2 * math.pi)
        blobs.append(((math.cos(a) * 0.8, math.sin(a) * 0.8, 5.4 + rng.uniform(0, 0.4)), rng.uniform(0.9, 1.2)))
    for k, (c, r) in enumerate(blobs):
        out.append(_blob(c, r, top, bot, seed * 10 + k))
    for i in range(3):   # visible branches into the canopy
        a = 2 * math.pi * i / 3 + 0.4
        out.append(beam((0, 0, 2.6), (math.cos(a) * 1.2, math.sin(a) * 1.2, 3.6), 0.16, "#5a3d2a"))
    return _scaled(out, scale)


def pine(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = trunk(0.24, 1.6, "#5a3d2a", seed=seed, roots=3)
    tiers = 5
    for k in range(tiers):
        t = k / (tiers - 1)
        r = 2.0 * (1 - 0.72 * t) + 0.3
        z = 1.0 + 1.15 * k
        prof = [(0.05, z + 1.5), (r * 0.35, z + 0.9), (r * 0.8, z + 0.25), (r, z - 0.05), (r * 0.9, z - 0.2),
                (r * 0.3, z + 0.05), (0.0, z + 0.1)]
        p = geo.lathe(prof[::-1], 12, color="#3f7d3a")
        p.deform(lambda V: V + np.column_stack([np.zeros(len(V)), np.zeros(len(V)),
                                                -0.18 * np.cos(np.arctan2(V[:, 1], V[:, 0]) * 6) *
                                                np.clip(np.hypot(V[:, 0], V[:, 1]) / r, 0, 1)]))
        p.paint(geo.grad_z("#214d2a", "#6fae45", z - 0.2, z + 1.4))
        out.append(_st(p, "foliage"))
    return _scaled(out, scale)


def birch(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = trunk(0.2, 3.6, "#efebe2", lean=(rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4)), seed=seed, roots=3)
    for p in out:
        p.paint(geo.stripes("#2a2622", axis=2, freq=14, width=0.07, phase=seed))
    for k in range(6):
        a = 2 * math.pi * k / 6 + rng.uniform(-0.4, 0.4)
        c = (math.cos(a) * 0.9, math.sin(a) * 0.9, 3.9 + rng.uniform(-0.3, 0.7))
        out.append(_blob(c, rng.uniform(0.8, 1.1), "#c3dd5a", "#5f8f2c", seed * 7 + k, squash=0.9))
    out.append(_blob((0, 0, 4.8), 1.1, "#d2e66a", "#6a9a30", seed + 99))
    return _scaled(out, scale)


def bush(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(4):
        a = 2 * math.pi * k / 4 + rng.uniform(-0.4, 0.4)
        out.append(_blob((math.cos(a) * 0.35, math.sin(a) * 0.35, 0.35), rng.uniform(0.4, 0.55), "#78b43c",
                         "#2c5e2a", seed * 3 + k, squash=0.75))
    for k in range(5):
        b = geo.qsphere(0.06, 2, "#d23a4a").tf((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0.4, 0.7)))
        out.append(_st(b, "gloss"))
    return _scaled(out, scale)


def rocks(seed=0, scale=1.0):
    out = []
    rng = np.random.default_rng(seed)
    for k in range(3):
        out += _rock((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0), s=rng.uniform(0.7, 1.4), color="#8d877b",
                     seed=seed * 5 + k)
    return _scaled(out, scale)


def reeds(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(9):
        x, y = rng.uniform(-0.5, 0.5, 2)
        h = rng.uniform(0.9, 1.5)
        lean = rng.uniform(-0.15, 0.15, 2)
        bl = geo.tube([(x, y, 0), (x + lean[0] * 0.5, y + lean[1] * 0.5, h * 0.5), (x + lean[0], y + lean[1], h)],
                      [0.025, 0.018, 0.004], 4, color="#6f9a3a", squash=0.4)
        out.append(_st(bl, "foliage"))
        if k % 3 == 0:
            ct = geo.capsule(0.035, 0.18, 6, 2, "#6b3f22").tf((x + lean[0], y + lean[1], h - 0.15))
            out.append(_st(ct, "foliage"))
    return _scaled(out, scale)


def lily(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(3):
        x, y = rng.uniform(-0.5, 0.5, 2)
        r = rng.uniform(0.25, 0.4)
        pts = [(math.cos(a) * r, math.sin(a) * r) for a in np.linspace(0.3, 2 * math.pi, 14)] + [(0, 0)]
        lf = geo.extrude(pts, 0.02, "#4f8f3a").tf(rot=(90, 0, rng.uniform(0, 360))).tf((x, y, 0.02))
        out.append(_st(lf, "foliage"))
    fl = geo.lathe([(0.0, 0.0), (0.12, 0.05), (0.08, 0.12), (0.0, 0.1)], 8, color="#f2a0c0").tf((0.1, 0.1, 0.03))
    out.append(_st(fl, "gloss"))
    return _scaled(out, scale)


def flowers(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = []
    cols = ["#f2d14a", "#f07a9a", "#a87af0", "#ffffff"]
    for k in range(10):
        x, y = rng.uniform(-0.5, 0.5, 2)
        st = geo.cyl(0.012, 0.25, 4, color="#5a8a2e").tf((x, y, 0))
        out.append(_st(st, "foliage"))
        hd = geo.qsphere(0.05, 2, cols[k % 4]).tf((x, y, 0.27))
        out.append(_st(hd, "gloss"))
    return _scaled(out, scale)


def mushrooms(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(4):
        x, y = rng.uniform(-0.4, 0.4, 2)
        s = rng.uniform(0.6, 1.2)
        st = geo.cyl(0.05 * s, 0.22 * s, 8, color="#f0e6cf").tf((x, y, 0))
        cp = geo.lathe([(0.0, 0.2 * s), (0.18 * s, 0.22 * s), (0.16 * s, 0.3 * s), (0.0, 0.36 * s)], 10,
                       color="#c8323a").tf((x, y, 0))
        cp.paint(geo.stripes("#fff6e6", axis=0, freq=60, width=0.12))
        out += [_st(st, "plaster"), _st(cp, "gloss")]
    return _scaled(out, scale)


def bridge(length=13.0, width=3.4, scale=1.0):
    wood, dark = "#8a6238", "#5a3d26"
    out = []
    n = int(length / 0.45)
    for i in range(n):
        x = -length / 2 + (i + 0.5) * length / n
        arch = 0.55 * math.cos(math.pi * x / length)
        pl = geo.rbox(length / n * 0.92, width, 0.12, r=0.02, k=1, color=palette.mul(wood, 0.9 + 0.2 * (i % 2)))
        pl.tf((x, 0, 0.3 + arch))
        out.append(_st(pl, "wood"))
    for s in (-1, 1):
        rail_pts = [(x, s * width / 2, 1.2 + 0.55 * math.cos(math.pi * x / length)) for x in
                    np.linspace(-length / 2, length / 2, 9)]
        out.append(_st(geo.tube(rail_pts, 0.08, 6, color=dark), "wood"))
        for x in np.linspace(-length / 2, length / 2, 7):
            z = 0.3 + 0.55 * math.cos(math.pi * x / length)
            out.append(beam((x, s * width / 2, z - 1.4), (x, s * width / 2, z + 0.95), 0.16, dark))
    return _scaled(out, scale)


def ford_stones(seed=0, scale=1.0):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(10):
        out += _rock((rng.uniform(-4, 4), rng.uniform(-2.5, 2.5), -0.2), s=rng.uniform(0.6, 1.0), color="#9a958a",
                     seed=seed + i)
    return _scaled(out, scale)


def camp(seed=0, scale=1.0):
    """Neutral creep camp: tent, campfire, crates."""
    from .buildings import crate, barrel
    out = []
    tent = geo.lathe([(1.4, 0.0), (0.0, 1.8)], 6, color="#8a6a4a").tf((0, 1.0, 0))
    out.append(_st(tent, "cloth"))
    out.append(beam((0, 1.0, 0), (0, 1.0, 2.1), 0.08, "#4a3220"))
    fire = geo.cone(0.35, 0.7, 6, "#ff9a2a").tf((0, -0.8, 0.05))
    out.append(_st(fire, "glow"))
    for a in np.linspace(0, 2 * math.pi, 7, endpoint=False):
        out += _rock((math.cos(a) * 0.55, -0.8 + math.sin(a) * 0.55, 0), s=0.25, color="#77736a", seed=int(a * 10))
    out += crate((1.4, -0.4, 0), s=0.5, rot=20)
    out += barrel((-1.3, -0.3, 0), s=0.9)
    return _scaled(out, scale)


def _scaled(parts, s):
    if s != 1.0:
        for p in parts:
            p.V *= s
    return parts


PROPS = {
    "oak": lambda: oak(1), "oak_b": lambda: oak(2, 0.9), "pine": lambda: pine(3), "pine_b": lambda: pine(4, 1.1),
    "birch": lambda: birch(5), "bush": lambda: bush(6), "rocks": lambda: rocks(7), "reeds": lambda: reeds(8),
    "lily": lambda: lily(9), "flowers": lambda: flowers(10), "mushrooms": lambda: mushrooms(11),
    "bridge": lambda: bridge(), "ford": lambda: ford_stones(12), "camp": lambda: camp(13),
}
