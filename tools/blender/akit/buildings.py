"""Faction buildings in the Warcraft III idiom.

Formula (Reforged/WC3): a heavy battered stone plinth with oversized corner
stones, short thick walls framed by dark timber beams (the buildings'
'trim'), and a huge overhanging roof that takes about half the height and
carries the team colour. Banners, lanterns and clutter sell the scale.
Each faction gets its own shape language: cat spires shaped like ears,
dog kennel-keeps with arched gates, hamster burrow-mounds with round doors,
hare terems with onion domes.

Units are ~1.2 m tall; a town hall is ~6-7 m. Coordinates: z up, the
building's front (gate) faces -Y.
"""
import math

import numpy as np

from . import geo, palette
from .armor import band_trim, plate, stud
from .rig import chain_weights

TW = "#f4f4f4"


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _st(p, mat, bone="root"):
    p.mat = mat
    p.bone = bone
    p.weights = None
    return p


def battered_block(w, d, h, batter=0.12, color="#9da2b0", mat="stone", z0=0.0, n=(4, 4, 3), r=0.06):
    """Rounded block whose sides lean in toward the top (castle plinth)."""
    p = geo.rbox(w, d, h, r=r, k=2, mid=max(n), color=color)
    p.tf((0, 0, z0 + h / 2))

    def lean(V):
        t = np.clip((V[:, 2] - z0) / h, 0, 1)
        k = 1 + batter * (1 - t)
        V[:, 0] *= k
        V[:, 1] *= k
        return V
    p.deform(lean)
    return _st(p, mat)


def round_block(r, h, batter=0.1, color="#8d8f99", mat="stone", z0=0.0, segs=16, top_r=None):
    rt = r if top_r is None else top_r
    p = geo.lathe([(r * (1 + batter), z0), (r * (1 + batter * 0.4), z0 + h * 0.5), (rt, z0 + h)], segs,
                  color=color)
    return _st(p, mat)


def quoins(w, d, z0, h, color, size=0.32, rows=None, mat="stone"):
    """Big alternating corner stones - the chunky Blizzard corner read."""
    out = []
    rows = rows or max(2, int(h / (size * 0.75)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            for i in range(rows):
                long_x = i % 2 == 0
                sw = size * (1.5 if long_x else 0.95)
                sd = size * (0.95 if long_x else 1.5)
                sh = h / rows * 0.92
                z = z0 + h / rows * (i + 0.5)
                c = (sx * (w / 2 - sw / 2 + 0.04), sy * (d / 2 - sd / 2 + 0.04), z)
                q = geo.rbox(sw, sd, sh, r=0.04, k=1, color=palette.mul(color, 0.92 + 0.12 * ((i + sx) % 2)))
                q.tf(c, rot=(0, 0, 0))
                out.append(_st(q, mat))
    return out


def beam(a, b, size, color="#4e3320", mat="wood"):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    L = np.linalg.norm(d)
    p = geo.rbox(size, size, L, r=size * 0.15, k=1, color=color).tf((0, 0, L / 2))
    z = np.array([0, 0, 1.0])
    dn = d / L
    v = np.cross(z, dn)
    s = np.linalg.norm(v)
    c = float(np.dot(z, dn))
    if s > 1e-9:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * ((1 - c) / s ** 2)
        p.V = p.V @ R.T
    elif c < 0:
        p.V[:, 2] *= -1
    p.V += a
    p.smooth = False
    return _st(p, mat)


def timber_frame(w, d, z0, z1, color="#4e3320", size=0.16, braces=True, out=0.02):
    """Corner posts, sill + plate beams and diagonal braces on all four walls."""
    parts = []
    hw, hd = w / 2 + out, d / 2 + out
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    for x, y in corners:
        parts.append(beam((x, y, z0), (x, y, z1), size * 1.15, color))
    for i in range(4):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 4]
        for z in (z0 + size / 2, z1 - size / 2):
            parts.append(beam((x0, y0, z), (x1, y1, z), size, color))
        if braces:
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            parts.append(beam((x0 + (mx - x0) * 0.15, y0 + (my - y0) * 0.15, z0 + size),
                              (mx, my, z1 - size), size * 0.7, color))
            parts.append(beam((x1 + (mx - x1) * 0.15, y1 + (my - y1) * 0.15, z0 + size),
                              (mx, my, z1 - size), size * 0.7, color))
            parts.append(beam((mx, my, z0), (mx, my, z1), size * 0.8, color))
    return parts


def walls(w, d, z0, h, color="#e8dcc4", mat="plaster"):
    p = geo.rbox(w, d, h, r=0.04, k=1, mid=3, color=color).tf((0, 0, z0 + h / 2))
    p.paint(geo.shade(1.04, 0.86, z0, z0 + h))
    return _st(p, mat)


def gable_roof(w, d, z0, h, color=TW, overhang=0.45, sag=0.12, thick=0.14, fascia="#4e3320",
               mat="roof", ridge_axis="x", flare=0.25):
    """Two sagging roof slabs with thick fascia boards and a ridge beam."""
    out = []
    W = (w if ridge_axis == "x" else d) / 2 + overhang      # half-length along ridge
    D = (d if ridge_axis == "x" else w) / 2 + overhang      # half-span to eave
    nu, nv = 10, 7
    for side in (-1, 1):
        P = np.zeros((nu, nv, 3))
        for i, u in enumerate(np.linspace(-W, W, nu)):
            for j, t in enumerate(np.linspace(0, 1, nv)):
                span = D * t
                z = z0 + h * (1 - t) - sag * math.sin(math.pi * t) * h * 0.6
                z += flare * h * max(0, t - 0.75) ** 2 * 3   # upturned eaves
                ends = 1 + 0.05 * (abs(u) / W) ** 4           # ridge droops toward the ends
                P[i, j] = (u, side * span, z / ends if False else z)
        if ridge_axis == "y":
            P = P[..., [1, 0, 2]]
        parts = plate(P, thick, color, mat=mat, ref=(0, 0, z0 - 2.0), trim=fascia, trim_r=thick * 0.6,
                      edges=("v1", "u0", "u1"), trim_mat="wood")
        out += [_st(q, q.mat) for q in parts]
    # ridge beam
    a = (-W - 0.1, 0, z0 + h + thick * 0.8)
    b = (W + 0.1, 0, z0 + h + thick * 0.8)
    if ridge_axis == "y":
        a, b = (a[1], a[0], a[2]), (b[1], b[0], b[2])
    out.append(beam(a, b, thick * 1.6, fascia))
    # gable walls (triangles) under the roof
    for s in (-1, 1):
        half = (d if ridge_axis == "x" else w) / 2
        pts = [(-half, 0.0), (half, 0.0), (0.0, h * 0.92)]
        g = geo.extrude(pts, 0.12, "#e8dcc4")
        g.tf(rot=(0, 0, 90 if ridge_axis == "x" else 0))
        if ridge_axis == "x":
            g.tf((s * (w / 2 - 0.06), 0, z0))
        else:
            g.tf((0, s * (d / 2 - 0.06), z0))
        out.append(_st(g, "plaster"))
    return out


def cone_roof(r, z0, h, color=TW, overhang=0.35, sag=0.18, thick=0.12, fascia="#4e3320", mat="roof",
              segs=16, finial="#e3a227", flare=0.25, phase=0.0, tilt=(0, 0, 0), center=(0, 0)):
    nu, nv = segs + 1, 8
    P = np.zeros((nu, nv, 3))
    R = (r + overhang) / (math.cos(math.pi / segs) if segs <= 6 else 1.0)
    for i, u in enumerate(np.linspace(-math.pi + phase, math.pi + phase, nu)):
        for j, t in enumerate(np.linspace(0, 1, nv)):
            rr = R * t
            z = z0 + h * (1 - t) - sag * h * math.sin(math.pi * t) * 0.6 + flare * h * max(0, t - 0.75) ** 2 * 3
            P[i, j] = (math.cos(u) * rr, math.sin(u) * rr, z)
    parts = plate(P, thick, color, mat=mat, ref=(0, 0, z0 - 2.0), trim=fascia, trim_r=thick * 0.6,
                  edges=("v1",), trim_mat="wood", wrap_u=False)
    out = [_st(q, q.mat) for q in parts]
    if segs <= 6:   # hip ridges follow the sagging roof surface
        for i in range(segs):
            line = P[i, :, :] + np.array([0, 0, thick * 1.2])
            rd = geo.tube(line[::-1], thick * 0.75, 6, color=fascia)
            out.append(_st(rd, "wood"))
    if finial:
        f = geo.lathe([(0.09, 0), (0.05, 0.15), (0.11, 0.25), (0.02, 0.5), (0, 0.62)], 8, color=finial)
        f.tf((0, 0, z0 + h - 0.05))
        out.append(_st(f, "gold"))
    if any(tilt) or any(center):
        for q in out:
            q.V -= np.array([0, 0, z0])
            q.tf(rot=tilt)
            q.V += np.array([center[0], center[1], z0])
    return out


def onion_dome(r, z0, color=TW, mat="roof", finial="#e7b53c", h=None):
    h = h or r * 2.4
    prof = [(r * 0.75, 0), (r * 1.0, h * 0.22), (r * 1.05, h * 0.38), (r * 0.8, h * 0.6),
            (r * 0.35, h * 0.8), (r * 0.08, h * 0.95), (0, h)]
    d = geo.lathe(prof, 16, color=color).tf((0, 0, z0))
    d.paint(geo.stripes(palette.mul(color, 0.8), axis=2, freq=40 / r, width=0.18))
    out = [_st(d, mat)]
    c = geo.lathe([(0.04, 0), (0.025, 0.2), (0.07, 0.24), (0.0, 0.42)], 8, color=finial).tf((0, 0, z0 + h - 0.03))
    out.append(_st(c, "gold"))
    cr = geo.box(0.22, 0.03, 0.03, finial).tf((0, 0, z0 + h + 0.3))
    out.append(_st(cr, "gold"))
    return out


def arched_door(w, h, depth=0.12, wood="#6b4a2e", frame="#9a9690", iron="#3a3a40", z0=0.0, y=0.0,
                frame_mat="stone"):
    """Plank door with iron bands under a stone arch (faces -Y)."""
    out = []
    pts = [(-w / 2, 0)] + [(math.cos(a) * w / 2, h - w / 2 + math.sin(a) * w / 2)
                           for a in np.linspace(0, math.pi, 10)][::-1] + [(w / 2, 0)]
    pts = [(-w / 2, 0), (w / 2, 0)] + [(math.cos(a) * w / 2, h - w / 2 + math.sin(a) * w / 2)
                                       for a in np.linspace(0, math.pi, 10)]
    door = geo.extrude(pts, depth, wood).tf((0, y, z0))
    door.paint(geo.stripes(palette.mul(wood, 0.7), axis=0, freq=2 * math.pi / (w / 4), width=0.1))
    out.append(_st(door, "wood"))
    for k in (0.25, 0.6):
        bd = geo.box(w * 0.95, 0.03, 0.06, iron).tf((0, y - depth / 2 - 0.01, z0 + h * k))
        out.append(_st(bd, "metal"))
    ring = geo.lathe([(0.06, -0.012), (0.075, 0.0), (0.06, 0.012)], 8, cap_bottom=False, cap_top=False,
                     color=iron).tf(rot=(90, 0, 0)).tf((w * 0.25, y - depth / 2 - 0.03, z0 + h * 0.45))
    out.append(_st(ring, "metal"))
    # voussoir arch (chunky stones)
    n = 7
    for i in range(n):
        a0 = math.pi * i / n
        a1 = math.pi * (i + 1) / n
        am = (a0 + a1) / 2
        rr = w / 2 + 0.14
        c = (math.cos(am) * rr, y - 0.02, z0 + h - w / 2 + math.sin(am) * rr)
        st = geo.rbox(0.3, depth + 0.16, 0.24, r=0.04, k=1, color=palette.mul(frame, 0.9 + 0.1 * (i % 2)))
        st.tf(rot=(0, -math.degrees(am) + 90, 0)).tf(c)
        out.append(_st(st, frame_mat))
    for sx in (-1, 1):
        jamb = geo.rbox(0.26, depth + 0.16, h - w / 2, r=0.04, k=1, color=frame).tf(
            (sx * (w / 2 + 0.13), y - 0.02, z0 + (h - w / 2) / 2))
        out.append(_st(jamb, frame_mat))
    return out


def window(w, h, x, z, y, frame="#4e3320", glass="#2a2430", shutters=None, round_top=True, facing="y"):
    out = []
    pts = [(-w / 2, 0), (w / 2, 0)] + ([(math.cos(a) * w / 2, h - w / 2 + math.sin(a) * w / 2)
                                        for a in np.linspace(0, math.pi, 7)] if round_top else
                                       [(w / 2, h), (-w / 2, h)])
    g = geo.extrude(pts, 0.06, glass).tf((0, 0, -h / 2))
    g.paint(geo.patch((0, -0.05, h * 0.2), w, "#ffcf6a", 0.9))   # warm interior glow
    fr = geo.extrude([(x_ * 1.25, z_ * 1.12) for x_, z_ in pts], 0.05, frame).tf((0, 0.02, -h / 2 - 0.03))
    parts = [_st(g, "glow"), _st(fr, "wood")]
    cross = geo.box(0.04, 0.04, h * 0.9, frame).tf((0, -0.04, 0))
    parts.append(_st(cross, "wood"))
    if shutters:
        for s in (-1, 1):
            sh = geo.box(w * 0.55, 0.04, h * 0.95, shutters).tf((s * w * 0.85, 0.0, 0), rot=(0, 0, s * 25))
            parts.append(_st(sh, "wood"))
    rot = {"y": 0, "-y": 180, "x": 90, "-x": -90}[facing]
    for p in parts:
        p.tf(rot=(0, 0, rot)).tf((x, y, z))
        out.append(p)
    return out


def banner(pole_base, height, color=TW, emblem=None, bone="banner", width=0.55, length=0.8,
           pole="#4e3320", tip="#e3a227"):
    """Pole with a hanging team banner, skinned to a 2-bone chain for wind."""
    base = np.asarray(pole_base, float)
    out = []
    pl = geo.cyl(0.05, height, 8, color=pole).tf(base)
    out.append(_st(pl, "wood"))
    t = geo.lathe([(0.07, 0), (0.0, 0.22)], 8, color=tip).tf(base + np.array([0, 0, height]))
    out.append(_st(t, "gold"))
    bar = geo.cyl(0.03, width + 0.15, 6, color=pole, z0=-(width + 0.15) / 2).tf(
        rot=(0, 90, 0)).tf(base + np.array([0, -0.06, height - 0.12]))
    out.append(_st(bar, "wood"))
    top = height - 0.15
    n = 6
    secs = []
    for i in range(n + 1):
        tt = i / n
        z = top - length * tt
        ww = width / 2 * (1 - 0.1 * tt)
        if tt > 0.8:
            pass
        secs.append([(base[0] - ww, base[1] - 0.06, base[2] + z), (base[0] + ww, base[1] - 0.06, base[2] + z),
                     (base[0] + ww, base[1] - 0.09, base[2] + z), (base[0] - ww, base[1] - 0.09, base[2] + z)])
    # swallow-tail bottom
    last = secs[-1]
    secs[-1] = [last[0], (base[0], base[1] - 0.06, base[2] + top - length * 0.82),
                (base[0], base[1] - 0.09, base[2] + top - length * 0.82), last[3]]
    secs[-1] = [last[0], last[1], last[2], last[3]]
    cl = geo.loft(secs, color=color)
    cl.mat = "team"
    pts = [base + np.array([0, -0.07, top + 0.02]), base + np.array([0, -0.07, top - length * 0.5]),
           base + np.array([0, -0.07, top - length * 1.02])]
    chain_weights(cl, [bone + ".1", bone + ".2"], pts)
    out.append(cl)
    if emblem:
        for e in emblem:
            e.V *= width / 0.25
            e.tf(base + np.array([0, -0.1, top - length * 0.4]))
            e.weights = None
            e.bone = bone + ".1"
            out.append(e)
    bones = [(bone + ".1", pts[0], pts[1], "root"), (bone + ".2", pts[1], pts[2], bone + ".1")]
    return out, bones


def barrel(pos, color="#7a5232", band="#3a3a40", s=1.0):
    p = geo.lathe([(0.2 * s, 0), (0.25 * s, 0.25 * s), (0.2 * s, 0.5 * s)], 12, color=color).tf(pos)
    out = [_st(p, "wood")]
    for z in (0.08, 0.42):
        b = geo.lathe([(0.215 * s, z * s - 0.02), (0.235 * s, z * s), (0.215 * s, z * s + 0.02)], 12,
                      cap_bottom=False, cap_top=False, color=band).tf(pos)
        out.append(_st(b, "metal"))
    return out


def crate(pos, s=0.45, color="#8a6a42", rot=0):
    c = geo.rbox(s, s, s, r=0.03, k=1, color=color).tf((0, 0, s / 2), rot=(0, 0, rot)).tf(pos)
    out = [_st(c, "wood")]
    for z in (0.05, s - 0.05):
        bd = geo.box(s * 1.02, s * 1.02, 0.05, palette.mul(color, 0.6)).tf((0, 0, z), rot=(0, 0, rot)).tf(pos)
        out.append(_st(bd, "wood"))
    return out


def sack(pos, s=1.0, color="#d8c08a"):
    p = geo.qsphere(1.0, 4, color).tf(scale=(0.22 * s, 0.2 * s, 0.26 * s)).tf((0, 0, 0.22 * s)).tf(pos)
    p.deform(lambda V: V + 0.01 * np.sin(V * 40))
    return [_st(p, "cloth")]


def chimney(x, y, z0, h, color="#7d7a78"):
    p = geo.rbox(0.45, 0.45, h, r=0.04, k=1, color=color).tf((x, y, z0 + h / 2))
    cap = geo.rbox(0.6, 0.6, 0.12, r=0.03, k=1, color=palette.mul(color, 0.8)).tf((x, y, z0 + h))
    return [_st(p, "stone"), _st(cap, "stone")]


def lantern_post(pos, glow="#ffcf6a", metal="#3a3a40"):
    pos = np.asarray(pos, float)
    out = [_st(geo.cyl(0.05, 1.3, 6, color="#4e3320").tf(pos), "wood")]
    arm = beam(pos + np.array([0, 0, 1.25]), pos + np.array([0, -0.35, 1.25]), 0.05, "#4e3320")
    out.append(arm)
    l = geo.cyl(0.09, 0.2, 6, color=glow).tf(pos + np.array([0, -0.35, 1.0]))
    out.append(_st(l, "glow"))
    r = geo.cone(0.13, 0.12, 6, metal).tf(pos + np.array([0, -0.35, 1.2]))
    out.append(_st(r, "metal"))
    return out



# ---------------------------------------------------------------------------
# Faction buildings
# ---------------------------------------------------------------------------

class BuildingSpec:
    def __init__(self, bid, faction, name, role, parts, bones, footprint, team):
        self.id, self.faction, self.name, self.role = bid, faction, name, role
        self.parts, self.bones, self.footprint, self.team = parts, bones, footprint, team


REGISTRY = {}


def building(bid, faction, name, role, footprint):
    def deco(fn):
        REGISTRY[bid] = (fn, faction, name, role, footprint)
        return fn
    return deco


def build(bid):
    fn, faction, name, role, fp = REGISTRY[bid]
    parts, bones = fn()
    return BuildingSpec(bid, faction, name, role, parts, bones, fp, palette.FACTIONS[faction]["team"])


def medallion_on_wall(faction, pos, r=0.35, gold="#e3a227"):
    from . import armor
    out = []
    for q in armor.medallion(faction, gold, r=r):
        q.tf(pos)
        out.append(_st(q, q.mat))
    return out


def tower_square(cx, cy, w, z0, h, stone, plaster=None, frame=None):
    out = []
    if plaster:
        out.append(_st(walls(w, w, z0, h, plaster), "plaster").tf((cx, cy, 0)))
        if frame:
            for q in timber_frame(w, w, z0, z0 + h, frame, size=0.14):
                out.append(q.tf((cx, cy, 0)))
    else:
        out.append(battered_block(w, w, h, 0.05, stone, z0=z0).tf((cx, cy, 0)))
        out += [q.tf((cx, cy, 0)) for q in quoins(w, w, z0, h, stone, size=0.26)]
    return out


@building("cat_hall", "cats", "Кошачий замок", "town_hall", (5.5, 5.0))
def cat_hall():
    stone, dark = "#a3a8b6", "#6a7080"
    team, wood, gold = TW, "#4b3426", "#e3a227"
    out, bones = [], []
    # plinth
    out.append(battered_block(5.4, 4.6, 0.9, 0.08, palette.mul(stone, 0.85)))
    out += quoins(5.4, 4.6, 0.0, 0.9, palette.mul(stone, 0.8), size=0.34, rows=2)
    # keep: round tower in the middle-back
    out.append(round_block(1.55, 3.0, 0.06, stone, z0=0.9, segs=18))
    for k in range(3):
        z = 1.2 + k * 0.9
        ring = geo.lathe([(1.6, z - 0.06), (1.66, z), (1.6, z + 0.06)], 18, cap_bottom=False, cap_top=False,
                         color=dark)
        out.append(_st(ring, "stone"))
    # perch balcony ring
    bal = geo.lathe([(1.6, 3.55), (2.0, 3.6), (2.0, 3.72), (1.6, 3.74)], 20, color=wood)
    out.append(_st(bal, "wood"))
    for a in np.linspace(0, 2 * math.pi, 16, endpoint=False):
        out.append(beam((math.cos(a) * 1.95, math.sin(a) * 1.95, 3.72), (math.cos(a) * 1.95, math.sin(a) * 1.95, 4.0),
                        0.07, wood))
    rail = geo.lathe([(1.93, 3.98), (1.99, 4.02), (1.93, 4.06)], 20, cap_bottom=False, cap_top=False, color=wood)
    out.append(_st(rail, "wood"))
    out.append(round_block(1.45, 0.8, 0.0, stone, z0=3.72, segs=18))
    out += cone_roof(1.45, 4.5, 2.6, team, overhang=0.55, sag=0.22, segs=18, finial=gold)
    # ear towers flanking the gate
    for sx in (-1, 1):
        cx, cy = sx * 1.75, -1.45
        out += tower_square(cx, cy, 1.2, 0.9, 2.7, stone)
        out += cone_roof(0.6, 3.6, 2.9, team, overhang=0.3, sag=0.16, segs=4, phase=math.pi / 4,
                         finial=gold, tilt=(-10, sx * 22, 0), center=(cx, cy))
        for z in (1.6, 2.6):
            out += window(0.32, 0.55, cx, z, cy - 0.62, frame=wood, facing="y")
    # gatehouse wall between the ears
    out.append(battered_block(2.3, 1.0, 2.0, 0.04, stone, z0=0.9).tf((0, -1.6, 0)))
    crenel = []
    for i in range(5):
        crenel.append(geo.rbox(0.32, 1.0, 0.35, r=0.04, k=1, color=stone).tf((-0.9 + i * 0.45, -1.6, 3.07)))
    out += [_st(q, "stone") for q in crenel]
    out += arched_door(1.1, 1.75, z0=0.9, y=-2.12, frame=palette.mul(stone, 0.9))
    out += medallion_on_wall("cats", (0, -2.16, 2.55), r=0.3, gold=gold)
    # keep windows (warm glow)
    for a in (-50, -20, 20, 50):
        x, y = math.sin(math.radians(a)) * 1.62, -math.cos(math.radians(a)) * 1.62
        w = window(0.3, 0.55, 0, 0, 0, frame=wood, facing="y")
        for q in w:
            q.tf(rot=(0, 0, a)).tf((x, y, 2.6))
        out += w
    # steps
    for i in range(3):
        st = geo.rbox(1.6 - i * 0.2, 0.4, 0.3, r=0.03, k=1, color=palette.mul(stone, 0.9)).tf(
            (0, -2.55 + i * 0.25, 0.15 + i * 0.3 - 0.3 * 0))
        st.V[:, 2] = np.minimum(st.V[:, 2], 0.3 * (i + 1))
        out.append(_st(st, "stone"))
    # banners on the ears
    for sx, name in ((-1, "banner_l"), (1, "banner_r")):
        parts, bb = banner((sx * 2.42, -1.45, 0.9), 2.4, TW, bone=name, width=0.5, length=0.9)
        out += parts
        bones += bb
    # clutter: fish drying rack + barrels
    out += barrel((2.4, -2.5, 0.0))
    out += barrel((2.0, -2.75, 0.0), s=0.85)
    out += crate((-2.4, -2.6, 0.0), rot=20)
    out += lantern_post((-1.0, -2.6, 0.0))
    out += lantern_post((1.0, -2.6, 0.0))
    return out, bones
