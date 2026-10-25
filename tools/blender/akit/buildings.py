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
    return BuildingSpec(bid, faction, name, role, parts, bones, fp, palette.FACTIONS.get(faction, {"team": "#8a7a5a"})["team"])


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


# ---------------------------------------------------------------------------
# More primitives (logs, mounds, round doors, silos, plants)
# ---------------------------------------------------------------------------

def log_wall(w, d, z0, h, color="#efe9dc", spots="#3a3530", r=0.11, ends=True):
    """Stacked log cabin walls with crossing log ends (birch for hares)."""
    out = []
    n = max(2, int(h / (2 * r * 0.92)))
    for i in range(n):
        z = z0 + r + i * 2 * r * 0.92
        alt = i % 2
        for axis in (0, 1):
            L = (w if axis == 0 else d) + (0.5 if ends else 0.0)
            off = (d if axis == 0 else w) / 2
            for sgn in (-1, 1):
                lg = geo.cyl(r, L, 8, color=color, z0=-L / 2).tf(rot=(0, 90, 0) if axis == 0 else (90, 0, 0))
                if axis == 0:
                    lg.tf((0, sgn * off, z + (r * 0.92 if alt else 0)))
                else:
                    lg.tf((sgn * off, 0, z + (0 if alt else r * 0.92)))
                lg.paint(geo.stripes(spots, axis=axis ^ 1 if False else (0 if axis == 0 else 1), freq=9.0,
                                     width=0.08, phase=i * 1.7))
                out.append(_st(lg, "wood"))
    return out


def mound(r, h, z0=0.0, color="#7da04a", earth="#8a6a48", mat="foliage", segs=20):
    """Grassy burrow mound: earth sides, grass cap."""
    prof = [(r * 1.08, z0), (r * 1.02, z0 + h * 0.25), (r * 0.85, z0 + h * 0.6), (r * 0.5, z0 + h * 0.9),
            (0.0, z0 + h)]
    m = geo.lathe(prof, segs, color=color)
    m.paint(geo.grad_z(earth, color, z0, z0 + h * 0.45))
    m.deform(lambda V: V + np.column_stack([np.zeros(len(V)), np.zeros(len(V)),
                                            0.04 * np.sin(V[:, 0] * 7) * np.sin(V[:, 1] * 5)]))
    return [_st(m, mat)]


def round_door(r, z_c, y, wood="#6b4a2e", frame="#9a8a70", iron="#3a3a40", frame_mat="stone"):
    out = []
    d = geo.disc(r, 0.1, 20, wood, bevel=0.05).tf((0, y, z_c))
    d.paint(geo.stripes(palette.mul(wood, 0.72), axis=0, freq=2 * math.pi / (r / 2.5), width=0.12))
    out.append(_st(d, "wood"))
    ring = np.array([(math.cos(a) * r * 1.08, y - 0.02, z_c + math.sin(a) * r * 1.08)
                     for a in np.linspace(0, 2 * math.pi, 33)])
    out.append(_st(geo.tube(ring, 0.07, 6, color=frame), frame_mat))
    knob = geo.qsphere(0.05, 2, "#e3a227").tf((0, y - 0.07, z_c))
    out.append(_st(knob, "gold"))
    return out


def silo(x, y, r, h, wall="#d9c7a0", roof=TW, band="#8a5a32"):
    out = [_st(geo.cyl(r, h, 14, color=wall).tf((x, y, 0)), "plaster")]
    for z in (h * 0.3, h * 0.65):
        b = geo.lathe([(r * 1.02, z - 0.04), (r * 1.06, z), (r * 1.02, z + 0.04)], 14, cap_bottom=False,
                      cap_top=False, color=band).tf((x, y, 0))
        out.append(_st(b, "wood"))
    out += [q.tf((x, y, 0)) for q in cone_roof(r, h, r * 1.3, roof, overhang=0.18, sag=0.1, segs=14,
                                                 finial=None, thick=0.08)]
    return out


def sunflower(pos, h=1.2, s=1.0):
    pos = np.asarray(pos, float)
    out = []
    st = geo.tube([pos, pos + np.array([0.02, 0, h * 0.5]), pos + np.array([0, 0.03, h])], 0.03 * s, 5,
                  color="#5a8a2e")
    out.append(_st(st, "foliage"))
    head = geo.disc(0.13 * s, 0.05, 12, "#5a3a1e").tf(rot=(-30, 0, 0)).tf(pos + np.array([0, -0.03, h]))
    out.append(_st(head, "foliage"))
    for a in np.linspace(0, 2 * math.pi, 10, endpoint=False):
        pt = geo.ellipsoid(0.07 * s, 0.015, 0.03 * s, 2, "#f2c12e").tf(
            (math.cos(a) * 0.17 * s, 0, math.sin(a) * 0.17 * s), rot=(0, -math.degrees(a), 0))
        pt.tf(rot=(-30, 0, 0)).tf(pos + np.array([0, -0.025, h]))
        out.append(_st(pt, "foliage"))
    lf = geo.ellipsoid(0.12 * s, 0.02, 0.06 * s, 3, "#4f8a2a").tf(rot=(0, 30, 20)).tf(pos + np.array([0.1, 0, h * 0.5]))
    out.append(_st(lf, "foliage"))
    return out


def carrot_row(x0, x1, y, n=6):
    out = []
    bed = geo.rbox(abs(x1 - x0) + 0.3, 0.45, 0.16, r=0.06, k=1, color="#6e4e30").tf(((x0 + x1) / 2, y, 0.08))
    out.append(_st(bed, "foliage"))
    for x in np.linspace(x0, x1, n):
        for k in range(3):
            lf = geo.cone(0.05, 0.3 + 0.05 * k, 5, "#5aa13a").tf(rot=(15 * (k - 1), 10 * (k - 1), 0)).tf((x, y, 0.15))
            out.append(_st(lf, "foliage"))
        top = geo.cone(0.045, 0.05, 6, palette.CARROT).tf((x, y, 0.13), rot=(180, 0, 0))
        out.append(_st(top, "foliage"))
    return out


def bone_finial(pos, s=1.0, color="#efe6d2"):
    pos = np.asarray(pos, float)
    out = [_st(geo.cyl(0.05 * s, 0.4 * s, 8, color=color, z0=0).tf(pos), "plaster")]
    for z in (0.0, 0.4 * s):
        for x in (-0.05 * s, 0.05 * s):
            out.append(_st(geo.qsphere(0.07 * s, 3, color).tf(pos + np.array([x, 0, z])), "plaster"))
    return out


def fence(points, h=0.7, color="#7a5232"):
    out = []
    pts = [np.asarray(p, float) for p in points]
    for a, b in zip(pts[:-1], pts[1:]):
        L = np.linalg.norm(b - a)
        n = max(2, int(L / 0.5))
        for t in np.linspace(0, 1, n):
            p = a + (b - a) * t
            out.append(beam(p, p + np.array([0, 0, h]), 0.07, color))
        for z in (h * 0.4, h * 0.85):
            out.append(beam(a + np.array([0, 0, z]), b + np.array([0, 0, z]), 0.05, color))
    return out


def rock(pos, s=1.0, color="#8a8478", seed=0):
    rng = np.random.default_rng(seed)
    p = geo.qsphere(1.0, 3, color).tf(scale=(0.6 * s, 0.5 * s, 0.4 * s))
    p.V += rng.normal(0, 0.08 * s, p.V.shape)
    p.V[:, 2] = np.maximum(p.V[:, 2], -0.05 * s)
    p.tf(np.asarray(pos, float) + np.array([0, 0, 0.12 * s]))
    p.smooth = False
    return [_st(p, "stone")]


def kokoshnik_gable(w, h, z0, y, color=TW, trim="#e7b53c"):
    """Rounded 'kokoshnik' gable over a hare doorway/porch."""
    pts = [(math.cos(a) * w / 2, math.sin(a) * h) for a in np.linspace(0, math.pi, 13)]
    g = geo.extrude(pts, 0.1, color, bevel=0.06).tf((0, y, z0))
    out = [_st(g, "roof")]
    edge = np.array([(math.cos(a) * w / 2 * 1.02, y - 0.06, z0 + math.sin(a) * h * 1.02)
                     for a in np.linspace(0, math.pi, 17)])
    out.append(_st(geo.tube(edge, 0.04, 6, color=trim), "gold"))
    return out


def stone_ground(w, d, color="#9a978e"):
    """Flagstone apron in front of / around a building."""
    p = geo.rbox(w, d, 0.08, r=0.03, k=1, color=color).tf((0, 0, 0.0))
    return [_st(p, "stone")]


def _banners(points, height=2.2, width=0.45, length=0.8):
    parts, bones = [], []
    for i, pt in enumerate(points):
        ps, bb = banner(pt, height, TW, bone=f"banner_{i}", width=width, length=length)
        parts += ps
        bones += bb
    return parts, bones


# ---------------------------------------------------------------------------
# CATS
# ---------------------------------------------------------------------------

@building("cat_barracks", "cats", "Кошачья казарма", "barracks", (4.5, 3.5))
def cat_barracks():
    stone, plaster, wood = "#a3a8b6", "#e3dccb", "#4b3426"
    out = [battered_block(4.4, 3.2, 0.7, 0.06, stone)]
    out += quoins(4.4, 3.2, 0, 0.7, stone, size=0.3, rows=1)
    out.append(walls(3.8, 2.7, 0.7, 1.6, plaster))
    out += timber_frame(3.8, 2.7, 0.7, 2.3, wood, size=0.14)
    out += gable_roof(3.8, 2.7, 2.3, 1.6, TW, overhang=0.4, ridge_axis="x")
    for sx in (-1, 1):   # cat-ear finials on the gable ends
        out += cone_roof(0.25, 3.6, 0.8, TW, overhang=0.08, sag=0.1, segs=4, phase=math.pi / 4,
                         finial="#e3a227", thick=0.06, center=(sx * 2.0, 0), tilt=(0, sx * 20, 0))
    out += arched_door(0.9, 1.4, z0=0.7, y=-1.42, frame=stone)
    for x in (-1.2, 1.2):
        out += window(0.32, 0.5, x, 1.7, -1.4, frame=wood)
    out += medallion_on_wall("cats", (0, -1.48, 2.45), r=0.24)
    # weapon rack + training dummy
    out.append(beam((1.9, -2.0, 0), (1.9, -2.0, 1.2), 0.1, wood))
    out.append(beam((2.5, -2.0, 0), (2.5, -2.0, 1.2), 0.1, wood))
    out.append(beam((1.85, -2.0, 1.1), (2.55, -2.0, 1.1), 0.08, wood))
    dummy = geo.cyl(0.18, 0.7, 8, color="#d9c08a").tf((-2.2, -2.0, 0.5))
    out.append(_st(dummy, "cloth"))
    out.append(beam((-2.2, -2.0, 0), (-2.2, -2.0, 1.5), 0.08, wood))
    out.append(_st(geo.qsphere(0.16, 3, "#d9c08a").tf((-2.2, -2.0, 1.38)), "cloth"))
    ps, bones = _banners([(-1.9, -1.5, 0.7)], 2.0)
    return out + ps, bones


@building("cat_farm", "cats", "Рыбацкая хижина", "farm", (3.0, 3.0))
def cat_farm():
    wood, stone = "#6b4a33", "#a3a8b6"
    out = [battered_block(2.4, 2.2, 0.4, 0.05, stone)]
    out.append(walls(2.0, 1.8, 0.4, 1.2, "#cbb894"))
    out += timber_frame(2.0, 1.8, 0.4, 1.6, "#4b3426", size=0.12, braces=False)
    out += cone_roof(1.25, 1.6, 1.5, TW, overhang=0.35, sag=0.2, segs=4, phase=math.pi / 4)
    out += arched_door(0.7, 1.0, z0=0.4, y=-0.95, frame=stone)
    # fish drying rack
    for x in (1.4, 2.2):
        out.append(beam((x, -1.2, 0), (x, -1.2, 1.2), 0.07, wood))
    out.append(beam((1.35, -1.2, 1.15), (2.25, -1.2, 1.15), 0.05, wood))
    for i, x in enumerate(np.linspace(1.5, 2.1, 4)):
        f = geo.ellipsoid(0.05, 0.03, 0.14, 3, "#9aa7b0").tf((x, -1.2, 0.98))
        out.append(_st(f, "gloss"))
        tail = geo.cone(0.05, 0.08, 4, "#7d8a94").tf((x, -1.2, 0.8), rot=(180, 0, 0))
        out.append(_st(tail, "gloss"))
    out += barrel((-1.4, -1.2, 0), s=0.9)
    out += barrel((-1.7, -0.7, 0), s=0.8)
    return out, []


@building("cat_tower", "cats", "Кошачий насест", "tower", (2.0, 2.0))
def cat_tower():
    stone, wood = "#a3a8b6", "#4b3426"
    out = [round_block(0.8, 3.4, 0.12, stone, segs=14)]
    for z in (1.1, 2.2):
        out.append(_st(geo.lathe([(0.82, z - 0.05), (0.88, z), (0.82, z + 0.05)], 14, cap_bottom=False,
                                 cap_top=False, color="#6a7080"), "stone"))
    deck = geo.lathe([(0.8, 3.35), (1.15, 3.4), (1.15, 3.52), (0.8, 3.54)], 16, color=wood)
    out.append(_st(deck, "wood"))
    for a in np.linspace(0, 2 * math.pi, 10, endpoint=False):
        out.append(beam((math.cos(a) * 1.1, math.sin(a) * 1.1, 3.52), (math.cos(a) * 1.1, math.sin(a) * 1.1, 4.4),
                        0.08, wood))
    cushion = geo.rbox(0.9, 0.9, 0.18, r=0.08, k=2, color=TW).tf((0, 0, 3.62))
    out.append(_st(cushion, "team"))
    out += cone_roof(1.1, 4.4, 1.5, TW, overhang=0.25, sag=0.2, segs=12)
    out += window(0.28, 0.45, 0, 1.6, -0.82, frame=wood)
    out += window(0.28, 0.45, 0, 2.6, -0.8, frame=wood)
    return out, []


# ---------------------------------------------------------------------------
# DOGS
# ---------------------------------------------------------------------------

def kennel_arch(w, h, z0, y, color=TW, wood="#5a3a22"):
    """A big gable 'kennel' hood over a gate - the dogs' signature shape."""
    out = []
    pts = [(-w / 2 - 0.2, 0), (0, h), (w / 2 + 0.2, 0)]
    for k, dz in ((0, 0), (1, -0.18)):
        for side in (-1, 1):
            a = np.array([side * (w / 2 + 0.25), y, z0])
            b = np.array([0, y, z0 + h])
            out.append(beam(a + np.array([0, -0.05 * k, dz]), b + np.array([0, -0.05 * k, dz]), 0.22, wood))
    g = geo.extrude([(-w / 2, 0), (w / 2, 0), (0, h * 0.85)], 0.12, color).tf((0, y + 0.06, z0))
    out.append(_st(g, "roof"))
    return out


@building("dog_hall", "dogs", "Псарный замок", "town_hall", (5.5, 5.0))
def dog_hall():
    stone, dark = "#b0a68e", "#7d745f"
    out = [battered_block(5.4, 4.6, 0.8, 0.08, palette.mul(stone, 0.85))]
    out += quoins(5.4, 4.6, 0.0, 0.8, palette.mul(stone, 0.8), size=0.34, rows=2)
    out.append(battered_block(3.6, 3.0, 2.6, 0.06, stone, z0=0.8))
    out += quoins(3.6, 3.0, 0.8, 2.6, dark, size=0.3)
    # crenellations
    for x in np.linspace(-1.55, 1.55, 6):
        for y in (-1.5, 1.5):
            out.append(_st(geo.rbox(0.36, 0.36, 0.4, r=0.04, k=1, color=stone).tf((x, y, 3.6)), "stone"))
    out += gable_roof(3.0, 2.4, 3.4, 1.4, TW, overhang=0.35, ridge_axis="y")
    for sx in (-1, 1):
        cx = sx * 2.0
        out += tower_square(cx, 0.6, 1.3, 0.8, 3.2, stone)
        out += cone_roof(0.65, 4.0, 1.7, TW, overhang=0.3, sag=0.12, segs=4, phase=math.pi / 4, finial=None,
                         center=(cx, 0.6))
        out += bone_finial((cx, 0.6, 5.6), s=0.9)
    out += arched_door(1.3, 1.9, z0=0.8, y=-1.62, frame=dark)
    out += kennel_arch(1.6, 1.3, 2.8, -1.7)
    out += medallion_on_wall("dogs", (0, -1.68, 3.35), r=0.26, gold="#ecc35e")
    for x in (-1.1, 1.1):
        out += window(0.32, 0.55, x, 2.4, -1.58, frame="#5a3a22")
    for i in range(3):
        st = geo.rbox(1.8 - i * 0.2, 0.4, 0.27, r=0.03, k=1, color=palette.mul(stone, 0.9)).tf(
            (0, -2.55 + i * 0.25, 0.135 + i * 0.27))
        out.append(_st(st, "stone"))
    out += bone_finial((-1.4, -2.6, 0), s=1.2)
    out += barrel((2.3, -2.4, 0))
    out += crate((-2.4, -2.4, 0), rot=15)
    ps, bones = _banners([(-2.75, -0.2, 0.8), (2.75, -0.2, 0.8)], 2.6)
    return out + ps, bones


@building("dog_barracks", "dogs", "Казарма стаи", "barracks", (4.5, 3.5))
def dog_barracks():
    wood, stone = "#7a5232", "#b0a68e"
    out = [battered_block(4.2, 3.2, 0.5, 0.05, stone)]
    out.append(walls(3.6, 2.6, 0.5, 1.5, "#c9a77c"))
    out += timber_frame(3.6, 2.6, 0.5, 2.0, "#5a3a22", size=0.15)
    out += gable_roof(3.6, 2.6, 2.0, 2.0, TW, overhang=0.45, sag=0.06, ridge_axis="y")
    door = geo.extrude([(math.cos(a) * 0.65, 0.6 + math.sin(a) * 0.65) for a in np.linspace(0, math.pi, 12)]
                       + [(-0.65, 0.0), (0.65, 0.0)], 0.1, "#2a1e16").tf((0, -1.36, 0.5))
    out.append(_st(door, "wood"))
    out += kennel_arch(1.4, 1.0, 1.8, -1.42)
    out += bone_finial((0, -1.4, 3.95), s=0.7)
    out += medallion_on_wall("dogs", (0, -1.45, 2.25), r=0.2, gold="#ecc35e")
    bowl = geo.lathe([(0.25, 0), (0.3, 0.12), (0.26, 0.14), (0.2, 0.05)], 12, color="#b33a2a").tf((1.6, -2.0, 0))
    out.append(_st(bowl, "metal"))
    out += bone_finial((1.6, -2.0, 0.14), s=0.4)
    ps, bones = _banners([(-2.0, -1.6, 0.5)], 2.0)
    return out + ps, bones


@building("dog_farm", "dogs", "Псарня и кухня", "farm", (3.0, 3.0))
def dog_farm():
    wood, stone = "#7a5232", "#b0a68e"
    out = [battered_block(2.4, 2.2, 0.35, 0.05, stone)]
    out.append(walls(2.0, 1.8, 0.35, 1.2, "#c9a77c"))
    out += timber_frame(2.0, 1.8, 0.35, 1.55, "#5a3a22", size=0.12, braces=False)
    out += gable_roof(2.0, 1.8, 1.55, 1.2, TW, overhang=0.35, ridge_axis="x")
    out += chimney(0.6, 0.4, 2.0, 1.2)
    out += arched_door(0.7, 1.0, z0=0.35, y=-0.95, frame=stone)
    # hanging sausages
    out.append(beam((-1.6, -1.1, 1.3), (-0.9, -1.1, 1.3), 0.05, wood))
    for x in np.linspace(-1.5, -1.0, 4):
        s_ = geo.capsule(0.04, 0.22, 6, 2, "#a8452e").tf((x, -1.1, 1.05))
        out.append(_st(s_, "gloss"))
    out += barrel((1.4, -1.1, 0), s=0.8)
    out += bone_finial((1.1, -1.5, 0), s=0.5)
    return out, []


@building("dog_tower", "dogs", "Сторожевая будка", "tower", (2.0, 2.0))
def dog_tower():
    stone, wood = "#b0a68e", "#5a3a22"
    out = [battered_block(1.5, 1.5, 3.0, 0.1, stone)]
    out += quoins(1.5, 1.5, 0, 3.0, "#8d846f", size=0.26)
    out.append(walls(1.5, 1.5, 3.0, 0.9, "#c9a77c"))
    out += timber_frame(1.5, 1.5, 3.0, 3.9, wood, size=0.12, braces=False)
    out += gable_roof(1.5, 1.5, 3.9, 1.0, TW, overhang=0.3, ridge_axis="y")
    door = geo.extrude([(math.cos(a) * 0.35, 0.3 + math.sin(a) * 0.35) for a in np.linspace(0, math.pi, 10)]
                       + [(-0.35, 0), (0.35, 0)], 0.08, "#1e1612").tf((0, -0.77, 3.05))
    out.append(_st(door, "wood"))
    out += bone_finial((0, 0, 4.95), s=0.5)
    return out, []


# ---------------------------------------------------------------------------
# HAMSTERS
# ---------------------------------------------------------------------------

@building("ham_hall", "hamsters", "Кладовая", "town_hall", (5.5, 5.0))
def ham_hall():
    out = mound(2.4, 2.6)
    out += round_door(0.75, 1.0, -2.25)
    stoneframe = geo.extrude([(math.cos(a) * 1.15, math.sin(a) * 1.15 + 1.0) for a in np.linspace(0, math.pi, 12)]
                             + [(-1.15, 0.0), (1.15, 0.0)], 0.5, "#b5a58a").tf((0, -2.05, 0))
    out.append(_st(stoneframe, "stone"))
    # terracotta roof cap on the mound
    out += cone_roof(1.2, 2.3, 1.1, TW, overhang=0.35, sag=0.1, segs=14, finial="#e9c46a")
    for a in (-55, 55):
        x, y = math.sin(math.radians(a)) * 2.15, -math.cos(math.radians(a)) * 2.15
        rw = round_door(0.28, 1.2, 0)
        for q in rw:
            q.V[:, 1] -= 0
            q.tf(rot=(0, 0, a)).tf((x, y, 0))
        out += rw
    out += silo(-2.3, 1.0, 0.65, 2.4)
    out += silo(2.2, 1.2, 0.55, 2.0)
    out += chimney(0.8, 0.9, 2.0, 1.1)
    wheel = geo.lathe([(0.55, -0.06), (0.62, 0), (0.55, 0.06), (0.5, 0)], 18, cap_bottom=False, cap_top=False,
                      color="#e9c46a").tf(rot=(90, 0, 0)).tf((0, -2.3, 2.25))
    out.append(_st(wheel, "gold"))
    for a in range(0, 180, 45):
        sp = geo.cyl(0.03, 1.0, 5, color="#e9c46a", z0=-0.5).tf(rot=(0, a, 0)).tf((0, -2.3, 2.25))
        out.append(_st(sp, "gold"))
    out += sack((1.4, -2.6, 0))
    out += sack((1.75, -2.4, 0), s=0.8)
    out += sack((-1.5, -2.6, 0), s=0.9)
    ps, bones = _banners([(-1.2, -2.5, 0), (1.2, -2.5, 0)], 2.4)
    return out + ps, bones


@building("ham_barracks", "hamsters", "Нора ополчения", "barracks", (4.0, 3.5))
def ham_barracks():
    out = mound(1.8, 1.9)
    out += round_door(0.6, 0.75, -1.72)
    fr = geo.extrude([(math.cos(a) * 0.9, math.sin(a) * 0.9 + 0.75) for a in np.linspace(0, math.pi, 12)]
                     + [(-0.9, 0), (0.9, 0)], 0.4, "#b5a58a").tf((0, -1.55, 0))
    out.append(_st(fr, "stone"))
    out += cone_roof(0.8, 1.7, 0.8, TW, overhang=0.25, sag=0.1, segs=12, finial="#e9c46a")
    # training wheel
    cx, cy, cz = 2.1, -0.6, 1.0
    rim = geo.lathe([(0.85, -0.25), (0.9, -0.25), (0.9, 0.25), (0.85, 0.25)], 20, color="#8b6239").tf(
        rot=(0, 90, 0)).tf((cx, cy, cz))
    out.append(_st(rim, "wood"))
    for a in range(0, 180, 30):
        sp = geo.cyl(0.03, 1.7, 5, color="#6b4a2e", z0=-0.85).tf(rot=(a, 0, 0)).tf((cx, cy, cz))
        out.append(_st(sp, "wood"))
    for sx in (-0.3, 0.3):
        out.append(beam((cx + sx, cy - 0.5, 0), (cx + sx, cy, cz), 0.09, "#6b4a2e"))
    out += crate((-2.0, -1.0, 0), rot=10)
    ps, bones = _banners([(-1.4, -1.6, 0)], 1.9)
    return out + ps, bones


@building("ham_farm", "hamsters", "Семечковое поле", "farm", (3.5, 3.0))
def ham_farm():
    out = []
    soil = geo.rbox(3.2, 2.6, 0.12, r=0.05, k=1, color="#6e4e30").tf((0, 0.2, 0.06))
    out.append(_st(soil, "foliage"))
    rng = np.random.default_rng(3)
    for x in np.linspace(-1.2, 1.2, 5):
        for y in np.linspace(-0.6, 1.0, 3):
            out += sunflower((x + rng.uniform(-0.1, 0.1), y, 0.1), h=rng.uniform(0.9, 1.3))
    shed = walls(1.0, 0.8, 0.0, 0.8, "#d9c7a0").tf((1.6, -1.2, 0))
    out.append(shed)
    out += [q.tf((1.6, -1.2, 0)) for q in gable_roof(1.0, 0.8, 0.8, 0.5, TW, overhang=0.2, ridge_axis="x",
                                                       thick=0.08)]
    out += fence([(-1.7, -1.3, 0), (1.0, -1.3, 0)], 0.6)
    out += sack((-1.4, -1.7, 0), s=0.8)
    return out, []


@building("ham_tower", "hamsters", "Нора-бункер", "tower", (2.2, 2.2))
def ham_tower():
    out = mound(1.1, 1.2)
    out.append(_st(geo.rbox(0.9, 0.12, 0.14, r=0.03, k=1, color="#1a1410").tf((0, -1.0, 0.8)), "wood"))
    for a in (-60, 60):
        sl = geo.rbox(0.5, 0.12, 0.12, r=0.03, k=1, color="#1a1410").tf((0, -0.98, 0.7))
        sl.tf(rot=(0, 0, a))
        out.append(_st(sl, "wood"))
    out.append(_st(geo.cyl(0.35, 0.9, 12, color="#b5a58a").tf((0, 0, 1.0)), "stone"))
    out += cone_roof(0.35, 1.9, 0.6, TW, overhang=0.18, sag=0.1, segs=12, finial="#e9c46a", thick=0.07)
    out += sack((0.9, -0.8, 0), s=0.8)
    out += sack((-0.9, -0.85, 0), s=0.7)
    return out, []


# ---------------------------------------------------------------------------
# HARES
# ---------------------------------------------------------------------------

@building("hare_hall", "hares", "Терем", "town_hall", (5.5, 5.0))
def hare_hall():
    birch = "#efe9dc"
    out = [battered_block(5.2, 4.4, 0.6, 0.06, "#c9c3b4")]
    out += [q.tf((0, 0.2, 0)) for q in log_wall(3.6, 2.8, 0.6, 2.0, birch)]
    out += [q.tf((0, 0.2, 0)) for q in log_wall(2.4, 2.0, 2.6, 1.2, birch, r=0.09)]
    out += [q.tf((0, 0.2, 0)) for q in gable_roof(3.6, 2.8, 2.55, 0.5, TW, overhang=0.35, ridge_axis="x",
                                                   sag=0.0)]
    out += [q.tf((0, 0.2, 0)) for q in onion_dome(0.75, 3.7, h=1.9)]
    for sx in (-1, 1):
        out += [q.tf((sx * 1.6, 1.1, 0)) for q in onion_dome(0.42, 2.6, h=1.0)]
    out += kokoshnik_gable(1.8, 1.0, 2.0, -1.3)
    out += arched_door(0.9, 1.3, z0=0.6, y=-1.32, frame="#c9a26a", frame_mat="wood")
    for x in (-1.1, 1.1):
        out += window(0.32, 0.5, x, 1.6, -1.3, frame="#a3243b", shutters="#a3243b")
    # porch posts
    for x in (-0.75, 0.75):
        out.append(beam((x, -1.9, 0.6), (x, -1.9, 2.0), 0.14, "#c9a26a"))
    out += carrot_row(1.4, 2.3, -2.0, n=4)
    ps, bones = _banners([(-2.4, -1.6, 0.6), (2.4, -1.6, 0.6)], 2.4)
    return out + ps, bones


@building("hare_barracks", "hares", "Дружинная изба", "barracks", (4.0, 3.5))
def hare_barracks():
    out = [battered_block(4.0, 3.0, 0.4, 0.05, "#c9c3b4")]
    out += log_wall(3.2, 2.4, 0.4, 1.5, "#d8c9a8")
    out += gable_roof(3.2, 2.4, 1.95, 1.7, TW, overhang=0.35, ridge_axis="y", sag=0.08)
    out += kokoshnik_gable(1.4, 0.8, 1.9, -1.3)
    out += arched_door(0.8, 1.2, z0=0.4, y=-1.25, frame="#c9a26a", frame_mat="wood")
    out += [q.tf((0, -1.3, 0)) for q in onion_dome(0.22, 3.6, h=0.6)]
    ps, bones = _banners([(-1.9, -1.5, 0.4)], 2.0)
    return out + ps, bones


@building("hare_farm", "hares", "Огород с морковью", "farm", (3.5, 3.0))
def hare_farm():
    out = []
    for y in (-0.9, -0.3, 0.3, 0.9):
        out += carrot_row(-1.2, 0.8, y, n=6)
    shed = walls(0.9, 0.9, 0.0, 0.9, "#d8c9a8").tf((1.6, 0.6, 0))
    out.append(shed)
    out += [q.tf((1.6, 0.6, 0)) for q in gable_roof(0.9, 0.9, 0.9, 0.6, TW, overhang=0.2, ridge_axis="y",
                                                      thick=0.08)]
    out += fence([(-1.6, -1.4, 0), (1.2, -1.4, 0), (1.2, -0.2, 0)], 0.55, "#c9a26a")
    return out, []


@building("hare_tower", "hares", "Смотровая кочка", "tower", (2.0, 2.0))
def hare_tower():
    out = mound(1.0, 0.6, color="#6f9a4a")
    wood = "#c9a26a"
    for x in (-0.5, 0.5):
        for y in (-0.5, 0.5):
            out.append(beam((x, y, 0.3), (x * 0.7, y * 0.7, 3.6), 0.12, wood))
    for z in (1.4, 2.5):
        for a, b_ in (((-0.45, -0.45), (0.45, -0.45)), ((0.45, -0.45), (0.45, 0.45)),
                      ((0.45, 0.45), (-0.45, 0.45)), ((-0.45, 0.45), (-0.45, -0.45))):
            out.append(beam((a[0], a[1], z), (b_[0], b_[1], z), 0.07, wood))
    deck = geo.rbox(1.3, 1.3, 0.12, r=0.03, k=1, color=wood).tf((0, 0, 3.6))
    out.append(_st(deck, "wood"))
    out += onion_dome(0.5, 3.66, h=1.2)
    drum = geo.cyl(0.25, 0.35, 12, color="#a3243b").tf(rot=(90, 0, 0)).tf((0.4, -0.5, 3.8))
    out.append(_st(drum, "team"))
    return out, []


# ---------------------------------------------------------------------------
# NEUTRAL
# ---------------------------------------------------------------------------

@building("gold_mine", "neutral", "Золотой рудник", "gold_mine", (4.5, 4.0))
def gold_mine():
    out = []
    rng = np.random.default_rng(11)
    for i in range(9):
        a = math.pi * (0.1 + 0.8 * i / 8)
        r = 2.0 + rng.uniform(-0.2, 0.2)
        out += rock((math.cos(a) * r * 1.1, math.sin(a) * r * 0.8 + 0.2, 0), s=2.2 + rng.uniform(-0.3, 0.6),
                    color="#7d776c", seed=i)
    out += rock((0, 1.2, 0.6), s=3.4, color="#8a8478", seed=99)
    # timber mine entrance
    for x in (-0.7, 0.7):
        out.append(beam((x, -0.6, 0), (x, -0.6, 1.8), 0.22, "#5a3a22"))
    out.append(beam((-0.95, -0.6, 1.8), (0.95, -0.6, 1.8), 0.24, "#5a3a22"))
    hole = geo.box(1.25, 0.4, 1.7, "#120e0a").tf((0, -0.45, 0.85))
    out.append(_st(hole, "stone"))
    for k in range(7):   # glowing gold veins / nuggets
        g = geo.qsphere(0.12 + 0.06 * rng.random(), 2, "#ffd24a").tf(
            (rng.uniform(-1.6, 1.6), rng.uniform(-0.3, 0.6), rng.uniform(0.4, 1.8)))
        out.append(_st(g, "glow"))
    rail = [beam((x, -0.6, 0.03), (x, -2.4, 0.03), 0.05, "#3a3a40") for x in (-0.3, 0.3)]
    out += rail
    for y in np.linspace(-0.8, -2.3, 6):
        out.append(beam((-0.45, y, 0.0), (0.45, y, 0.0), 0.08, "#5a3a22"))
    cart = geo.rbox(0.7, 0.9, 0.45, r=0.05, k=1, color="#6b4a2e").tf((0, -1.9, 0.38))
    out.append(_st(cart, "wood"))
    for x in (-0.35, 0.35):
        for y in (-2.2, -1.6):
            out.append(_st(geo.cyl(0.12, 0.06, 10, color="#3a3a40", z0=-0.03).tf(rot=(0, 90, 0)).tf((x, y, 0.13)), "metal"))
    for k in range(5):
        out.append(_st(geo.qsphere(0.1, 2, "#ffd24a").tf((rng.uniform(-0.25, 0.25), -1.9 + rng.uniform(-0.3, 0.3), 0.66)),
                       "glow"))
    return out, []


@building("mill", "neutral", "Старая мельница", "shrine", (4.0, 4.0))
def mill():
    stone = "#a8a296"
    out = [battered_block(2.6, 2.6, 1.0, 0.1, stone)]
    out += quoins(2.6, 2.6, 0, 1.0, "#8a8478", size=0.3, rows=2)
    out.append(walls(2.2, 2.2, 1.0, 1.6, "#e3dccb"))
    out += timber_frame(2.2, 2.2, 1.0, 2.6, "#4b3426", size=0.14)
    out += cone_roof(1.3, 2.6, 1.8, "#8a5a3a", overhang=0.35, segs=4, phase=math.pi / 4, mat="wood",
                     finial="#d8b04a")
    out += arched_door(0.7, 1.1, z0=1.0, y=-1.15, frame=stone)
    # water wheel on the side, skinned to its own bone
    wheel_parts = []
    cx, cy, cz = 1.75, 0.0, 1.05
    rim = geo.lathe([(1.05, -0.2), (1.12, -0.2), (1.12, 0.2), (1.05, 0.2)], 20, color="#6b4a2e")
    rim.tf(rot=(0, 90, 0))
    wheel_parts.append(rim)
    for a in range(0, 180, 30):
        wheel_parts.append(geo.cyl(0.05, 2.1, 5, color="#5a3a22", z0=-1.05).tf(rot=(a, 0, 0)))
    for a in np.linspace(0, 2 * math.pi, 12, endpoint=False):
        pd = geo.box(0.38, 0.06, 0.25, "#7a5232").tf((0, math.cos(a) * 1.15, math.sin(a) * 1.15),
                                                     rot=(math.degrees(a), 0, 0))
        wheel_parts.append(pd)
    hub = geo.cyl(0.18, 0.5, 10, color="#3a3a40", z0=-0.25).tf(rot=(0, 90, 0))
    wheel_parts.append(hub)
    for q in wheel_parts:
        q.tf((cx, cy, cz))
        _st(q, q.mat if q.mat != "body" else "wood")
        q.bone = "wheel"
    out += wheel_parts
    out.append(beam((1.3, 0, cz), (cx + 0.3, 0, cz), 0.12, "#3a3a40"))
    bones = [("wheel", (cx, cy, cz), (cx + 0.5, cy, cz), "root")]
    out += sack((-1.6, -1.2, 0))
    out += sack((-1.9, -0.9, 0), s=0.8)
    return out, bones


@building("rat_pit", "rats", "Провал Крысиной Чумы", "spawner", (4.0, 4.0))
def rat_pit():
    out = []
    rng = np.random.default_rng(5)
    ring = geo.lathe([(1.4, -0.4), (1.6, 0.05), (2.1, 0.12), (2.4, 0.0)], 20, color="#5e5a4c")
    ring.deform(lambda V: V + rng.normal(0, 0.05, V.shape))
    out.append(_st(ring, "stone"))
    pit = geo.cyl(1.45, 0.05, 20, color="#0c0f06").tf((0, 0, -0.38))
    out.append(_st(pit, "stone"))
    glow = geo.cyl(1.0, 0.04, 16, color="#9adf2a").tf((0, 0, -0.3))
    out.append(_st(glow, "glow"))
    for i in range(10):
        a = 2 * math.pi * i / 10 + rng.uniform(-0.2, 0.2)
        out += rock((math.cos(a) * 1.9, math.sin(a) * 1.9, 0), s=0.5 + rng.uniform(0, 0.5), color="#6e6a5e", seed=i)
    for i in range(6):   # junk planks and spikes
        a = rng.uniform(0, 2 * math.pi)
        p0 = np.array([math.cos(a) * 1.5, math.sin(a) * 1.5, 0.05])
        out.append(beam(p0, p0 + np.array([rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0.4, 1.0)]),
                        0.1, "#4a3a2a"))
    return out, []
