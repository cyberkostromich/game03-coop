"""Clothing, armour, headwear, weapons, shields and heraldry.

Everything is fitted to a beast.Body, so the same garment works on a cat,
a dog or a hamster. Weapons are modelled along +Z with the grip at the
origin and their 'front' (blade edge, bow belly) toward -Y, then mounted in
the hand with weapon_in_hand().
"""
import math

import numpy as np

from .geo import tagged
from . import geo, palette
from .beast import torso_r, fur_colors
from .rig import blend_weights, chain_weights


# ---------------------------------------------------------------------------
# Body garments
# ---------------------------------------------------------------------------

def _ratio(b):
    return b.torso_d / b.torso_w


def garment_r(b, z, z_bot, flare=0.25, layer="cloth"):
    """Outer radius (rx, ry) of a garment at height z (for trims that sit on it)."""
    from .armor import layer_r
    hip = b.hip_h + 0.02
    k = max(hip - z, 0.0) / max(hip - z_bot, 1e-6)
    lrx, lry = layer_r(b, z, layer)
    return lrx * (1 + flare * k), lry * (1 + flare * k)


def garment(b, z_bot, z_top, color, mat="cloth", inflate=1.07, flare=0.25, segs=18,
            thick=0.015, rings=10, hips_only=False, layer="cloth"):
    """Closed shell around the torso; below the hips it becomes a bell skirt that
    always clears the thighs (legs come out of the hem, never through the side)."""
    hip = b.hip_h + 0.02
    z_top = min(z_top, b.neck_z - 0.05, b.head_c[2] - b.head_r[2] - 0.035)
    outer = []
    depth = []
    for i in range(rings + 1):
        z = z_bot + (z_top - z_bot) * i / rings
        r, ry = garment_r(b, z, z_bot, flare, layer)
        outer.append((r, z))
        depth.append((z, ry / r))
    r_in = outer[0][0] - thick
    prof = [(max(r_in * 0.9, 0.01), min(hip, z_top)), (r_in, z_bot + thick)] + outer
    prof.append((outer[-1][0] * 0.55, z_top + 0.01))
    p = geo.lathe(prof, segs, cap_bottom=True, cap_top=True, phase=math.pi / segs, color=color)
    zs = np.array([z for z, _ in depth])
    ds = np.array([d for _, d in depth])
    p.V[:, 1] *= np.interp(p.V[:, 2], zs, ds)
    p.mat = mat
    if hips_only:
        p.bone = "hips"
    elif z_top <= b.hip_h + 0.1:
        from .armor import thigh_follow
        thigh_follow([p], b, 0.65)      # skirt: hem follows the thighs like cloth
    else:
        blend_weights(p, "hips", "chest", b.hip_h + 0.1, b.hip_h + b.torso_h * 0.7)
        # long robes: the part below the hips still drifts with the legs
        if z_bot < b.hip_h - 0.05:
            w = p.weights
            low = np.clip((b.hip_h - p.V[:, 2]) / max(b.hip_h - z_bot, 1e-6), 0, 1)
            side = np.clip(p.V[:, 0] / (b.hip_w * 1.5), -1, 1)
            wl = 0.8 * low * np.clip(side, 0, 1)
            wr = 0.8 * low * np.clip(-side, 0, 1)
            p.weights = {"hips": w["hips"] * (1 - wl - wr), "chest": w["chest"] * (1 - wl - wr),
                         "thigh.L": wl, "thigh.R": wr}
    p.group = "garment"
    return p


def band(b, z, color, mat="cloth", thick=0.018, inflate=1.1, segs=18, bone=None, add=0.006, radius=None):
    """Torus-like band hugging the torso at height z (belts, trims)."""
    rx = radius[0] if radius else torso_r(b, max(z, b.hip_h + 0.02))[0] * inflate + add
    prof = []
    for a in np.linspace(-math.pi / 2, math.pi * 1.5, 9):
        prof.append((rx + thick * 0.55 * math.cos(a), z + thick * math.sin(a)))
    p = geo.lathe(prof, segs, cap_bottom=False, cap_top=False, color=color)
    ryt = torso_r(b, max(z, b.hip_h + 0.02))
    ry_ = radius[1] if radius else ryt[1] * inflate + add
    p.V[:, 1] *= ry_ / max(rx, 1e-6)
    p.mat = mat
    if bone:
        p.bone = bone
    else:
        blend_weights(p, "hips", "chest", b.hip_h + 0.02, b.hip_h + b.torso_h * 0.6)
    return p


_NOT_TORSO = ("weapon", "shield", "fur.arms", "gauntlet", "vambrace", "couter", "fur.legs", "fur.tail",
              "cape", "sabaton", "greave", "poleyn", "cuisse", "fur.head", "fur.ears", "hat", "helm", "pauldron")


def fit_r(b, parts, z, floor="cloth", band=0.02):
    """Snug radius at height z over whatever is already worn there: a belt
    sits on the outermost torso layer instead of a fixed armour layer."""
    from .armor import layer_r
    rx, ry = layer_r(b, z, floor)
    for p in parts or ():
        g = p.group or ""
        if g.startswith(_NOT_TORSO):
            continue
        m = np.abs(p.V[:, 2] - z) < band
        if not m.any():
            continue
        rx = max(rx, float(np.abs(p.V[m, 0]).max()))
        ry = max(ry, float(np.abs(p.V[m, 1]).max()))
    return rx, ry


@tagged("belt")
def belt(b, leather, buckle=palette.GOLD, z=None, pouch=None, fit=None):
    """Belt hugging the outermost layer at its height (or the 'belt' layer)."""
    z = b.hip_h + 0.065 if z is None else z
    from .armor import layer_r
    if fit is not None:
        lrx, lry = fit_r(b, fit, z)
        lrx, lry = lrx + 0.013, lry + 0.013
    else:
        lrx, lry = layer_r(b, z, "belt")
    out = [band(b, z, leather, "body", thick=0.03, inflate=1.0, add=0.0, radius=(lrx, lry))]
    out[0].fit = (lrx, lry)
    ry = lry + 0.016
    bk = geo.rbox(0.05, 0.02, 0.042, 0.006, color=buckle).tf((0, -ry, z))
    out.append(bk.on("hips", "metal"))
    if pouch:
        rx = lrx
        pc = geo.rbox(0.06, 0.04, 0.07, 0.015, color=pouch).tf((rx * 0.78, -ry * 0.68, z - 0.05),
                                                                 rot=(0, 0, 30))
        out.append(pc.on("hips"))
    return out


def front_panel(b, z_top, z_bot, half_w, color, mat="team", depth=0.012, tip="point",
                side=-1, inflate=None, bone_blend=True, n=10, m=7, layer="over"):
    """A tabard / apron panel curved over the front (side=-1) or back (+1) on a torso layer."""
    from .armor import layer_r, thigh_follow
    z_top = min(z_top, b.neck_z - 0.06)
    secs = []
    for i in range(n + 1):
        t = i / n
        z = z_top + (z_bot - z_top) * t
        rx, ry = layer_r(b, z, layer)
        rx, ry = rx + 0.004, ry + 0.004
        w = half_w
        if tip == "point" and t > 0.7:
            w = half_w * (1 - (t - 0.7) / 0.3 * 0.85)
        elif tip == "round" and t > 0.75:
            w = half_w * math.sqrt(max(1 - ((t - 0.75) / 0.25) ** 2, 0.04))
        w = min(w, rx * 0.97)
        front, back = [], []
        for x in np.linspace(-w, w, m):
            ys = ry * math.sqrt(max(1 - (x / rx) ** 2, 0.0))
            if z < b.hip_h:
                ys += (b.hip_h - z) * 0.35
            front.append((x, side * (ys + depth), z))
            back.append((x, side * ys, z))
        secs.append(front + back[::-1])
    p = geo.loft(secs, color=color)
    p.mat = mat
    if bone_blend:
        blend_weights(p, "hips", "chest", b.hip_h + 0.1, b.hip_h + b.torso_h * 0.7)
        if z_bot < b.hip_h - 0.03:
            w = p.weights
            low = np.clip((b.hip_h - p.V[:, 2]) / max(b.hip_h - z_bot, 1e-6), 0, 1)
            side_ = np.clip(p.V[:, 0] / (b.hip_w * 1.5), -1, 1)
            wl = 0.6 * low * np.clip(side_, 0, 1) + 0.3 * low * (1 - abs(side_))
            wr = 0.6 * low * np.clip(-side_, 0, 1) + 0.3 * low * (1 - abs(side_))
            p.weights = {"hips": w["hips"] * (1 - wl - wr), "chest": w["chest"] * (1 - wl - wr),
                         "thigh.L": wl, "thigh.R": wr}
    p.group = "panel"
    return p


@tagged("cape")
def cape(b, color, length=None, width=1.0, mat="team", lining=None, collar=None):
    """Cape hanging from the shoulders, skinned on chest -> cape -> cape_tip."""
    zt = b.shoulder_z - 0.03
    zb = 0.08 if length is None else zt - length
    n, m = 12, 9
    secs = []
    for i in range(n + 1):
        t = i / n
        z = zt + (zb - zt) * t
        zz = min(max(z, b.hip_h + 0.05), b.neck_z - 0.04)
        from .armor import layer_r
        rx, ry = layer_r(b, zz, "over")
        flare = 1 + 0.45 * t
        rx = (rx + 0.02) * flare * width
        ry = ry + 0.045 + 0.09 * t ** 1.3
        front, back = [], []
        span = math.radians(56 + 36 * t)
        for a in np.linspace(-span, span, m):
            x = rx * math.sin(a)
            y = ry * math.cos(a)
            wob = 0.008 * math.sin(a * 5 + t * 3) * t
            front.append((x, y + wob, z))
            back.append((x, y + wob + 0.014, z))
        secs.append(back + front[::-1])
    p = geo.loft(secs, color=color)
    p.mat = mat
    pts = [(0, b.torso_d * 0.5, zt + 0.05), (0, b.torso_d * 0.5, b.shoulder_z - 0.02),
           (0, b.torso_d * 0.62, b.shoulder_z - 0.16), (0, b.torso_d * 0.7, zb)]
    chain_weights(p, ["chest", "cape", "cape_tip"], pts)
    out = [p]
    if collar:
        rx, ry = torso_r(b, b.neck_z - 0.02)
        cl = geo.lathe([(rx * 0.95, b.neck_z - 0.06), (rx * 1.15, b.neck_z - 0.02),
                        (rx * 1.0, b.neck_z + 0.02), (rx * 0.7, b.neck_z + 0.03)], 16, color=collar)
        cl.V[:, 1] *= _ratio(b) * 1.05
        cl.V[:, 1] += 0.01
        out.append(cl.on("chest", "body"))
    return out


def cuirass(b, metal, z_bot=None, z_top=None, inflate=1.12, ridge=True, mat="metal"):
    z_bot = b.hip_h + 0.03 if z_bot is None else z_bot
    z_top = b.neck_z - 0.02 if z_top is None else z_top
    p = garment(b, z_bot, z_top, metal, mat, inflate=inflate, flare=0.0, segs=18, rings=8)
    out = [p]
    if ridge:
        zs = np.linspace(z_bot + 0.03, z_top - 0.04, 6)
        pts = []
        for z in zs:
            ry = torso_r(b, z)[1] * inflate * 1.02 + 0.006
            pts.append((0, -ry, z))
        r = geo.tube(pts, 0.008, 6, color=palette.mul(metal, 1.1))
        r.mat = mat
        blend_weights(r, "hips", "chest", b.hip_h + 0.02, b.hip_h + b.torso_h * 0.6)
        out.append(r)
    return out


def faulds(b, metal, rows=2, mat="metal", trim=None):
    out = []
    for i in range(rows):
        z = b.hip_h + 0.02 - i * 0.045
        p = garment(b, z - 0.05, z, metal, mat, inflate=1.16 + 0.04 * i, flare=0.25,
                    segs=18, rings=2, hips_only=True)
        out.append(p)
    if trim:
        out.append(band(b, b.hip_h - 0.07 - 0.045 * (rows - 1), trim, "metal", 0.012, 1.3,
                        bone="hips"))
    return out


def pauldrons(b, metal, size=1.0, mat="metal", trim=None, spikes=False, layers=2, rivets=True):
    """Oversized layered shoulder plates - the main Blizzard-style silhouette cue."""
    j = b.joints()
    out = []
    trim = trim or palette.mul(metal, 0.7)
    for s, sign in (("L", 1), ("R", -1)):
        sh = j[f"shoulder.{s}"]
        bone = f"upper_arm.{s}"
        r = 0.088 * size
        centre = sh + np.array([sign * 0.03 * size, 0.004, 0.012 * size])
        for li in range(layers):
            rr = r * (1 - 0.14 * li)
            dome = geo.lathe([(rr * math.cos(a), rr * math.sin(a) * 0.72) for a in
                              np.linspace(-0.35, math.pi / 2, 7)], 14, color=metal)
            dome.V[:, 1] *= 1.12
            dome.V[:, 0] *= 1.08
            off = np.array([sign * 0.022 * li * size, 0, -0.045 * li * size])
            dome.tf(rot=(0, sign * (32 + 14 * li), 0)).tf(centre + off)
            out.append(dome.on(bone, mat))
            rim = geo.lathe([(rr * 0.98, -0.026 * size), (rr * 1.07, -0.018 * size),
                             (rr * 1.07, -0.005 * size), (rr * 0.98, 0.0)], 14,
                            cap_bottom=False, cap_top=False, color=trim)
            rim.V[:, 1] *= 1.12
            rim.V[:, 0] *= 1.08
            rim.tf(rot=(0, sign * (32 + 14 * li), 0)).tf(centre + off)
            out.append(rim.on(bone, mat))
        if rivets:
            for a in np.linspace(-1.0, 1.0, 4):
                rv = geo.qsphere(0.009 * size, 2, trim)
                d = np.array([0, math.sin(a) * r * 0.85 * 1.12, r * 0.5])
                rv.tf(d).tf(rot=(0, sign * 32, 0)).tf(centre)
                out.append(rv.on(bone, mat))
        if spikes:
            for k, (dz, dy) in enumerate(((0.0, 0.0), (-0.01, -0.045), (-0.01, 0.045))):
                sp = geo.cone(0.02 * size, 0.075 * size * (1 if k == 0 else 0.7), 6,
                              palette.mul(metal, 1.15))
                sp.tf(rot=(0, sign * 40, 0)).tf(centre + np.array([sign * 0.045 * size, dy * size,
                                                                     0.05 * size + dz]))
                out.append(sp.on(bone, mat))
    return out


def bracers(b, color, mat="body"):
    j = b.joints()
    out = []
    for s in ("L", "R"):
        el, wr = j[f"elbow.{s}"], j[f"wrist.{s}"]
        a = el + (wr - el) * 0.3
        c = wr + (wr - el) * 0.02
        t = geo.tube([a, (a + c) / 2, c], [b.arm_r * 1.12, b.arm_r * 1.18, b.arm_r * 1.22], 10,
                     color=color)
        t.mat = mat
        out.append(t.on(f"forearm.{s}"))
    return out


def boots(b, color, mat="body", cuff=None):
    j = b.joints()
    out = []
    for s in ("L", "R"):
        kn, an = j[f"knee.{s}"], j[f"ankle.{s}"]
        a = kn + (an - kn) * 0.25
        t = geo.tube([a, (a + an) / 2, an + np.array([0, 0, -0.01])],
                     [b.leg_r * 1.12, b.leg_r * 1.02, b.leg_r * 1.0], 10, color=color)
        t.mat = mat
        out.append(t.on(f"shin.{s}"))
        if cuff:
            c = geo.lathe([(b.leg_r * 1.15, -0.012), (b.leg_r * 1.28, 0.0), (b.leg_r * 1.15, 0.014)],
                          10, cap_bottom=False, cap_top=False, color=cuff).tf(a)
            out.append(c.on(f"shin.{s}", mat))
    return out


@tagged("scarf")
def scarf(b, color, mat="team", tails=True):
    z = b.neck_z - 0.005
    rx, ry = torso_r(b, z - 0.02)
    p = geo.lathe([(rx * 0.85, z - 0.035), (rx * 1.05, z - 0.02), (rx * 1.02, z + 0.02),
                   (rx * 0.75, z + 0.035)], 16, color=color)
    p.V[:, 1] *= _ratio(b) * 1.1
    out = [p.on("chest", mat)]
    if tails:
        s = 1
        pts = [(rx * 0.35, b.torso_d * 0.45, z - 0.01), (rx * 0.45, b.torso_d * 0.62, z - 0.08),
               (rx * 0.4, b.torso_d * 0.7, z - 0.17)]
        t = geo.tube(pts, [0.022, 0.02, 0.016], 6, color=color, squash=0.35)
        out.append(t.on("chest", mat))
    return out


@tagged("collar")
def collar(b, leather, spikes=None, tag=None):
    z = b.neck_z + 0.0
    rx, ry = torso_r(b, z - 0.03)
    p = geo.lathe([(rx * 0.8, z - 0.02), (rx * 0.92, z - 0.012), (rx * 0.92, z + 0.012),
                   (rx * 0.8, z + 0.02)], 16, cap_bottom=False, cap_top=False, color=leather)
    p.V[:, 1] *= _ratio(b)
    out = [p.on("chest")]
    if spikes:
        for a in np.linspace(0, 2 * math.pi, 9, endpoint=False):
            d = np.array([math.cos(a) * rx * 0.92, math.sin(a) * ry * 0.92, 0])
            n = d / np.linalg.norm(d)
            sp = geo.cone(0.012, 0.03, 5, spikes)
            yaw = math.degrees(math.atan2(n[1], n[0]))
            sp.tf(rot=(0, 90, 0)).tf(rot=(0, 0, yaw)).tf(d + np.array([0, 0, z]))
            out.append(sp.on("chest", "metal"))
    if tag:
        t = geo.disc(0.022, 0.006, 10, tag).tf((0, -ry * 0.95 - 0.01, z - 0.035))
        out.append(t.on("chest", "metal"))
    return out


@tagged("backpack")
def backpack(b, color, strap=palette.LEATHER, size=1.0, kind="sack"):
    from .armor import layer_r
    z = b.hip_h + b.torso_h * 0.6
    ry = max(layer_r(b, zz, "over")[1] for zz in np.linspace(z - 0.15, z + 0.15, 7)) + 0.03
    out = []
    if kind == "sack":
        s = geo.qsphere(1.0, 5, color).tf(scale=(0.16 * size, 0.12 * size, 0.17 * size))
        s.deform(lambda V: V * (1 + 0.04 * np.sin(V[:, 2:3] * 40)))
        s.tf((0, ry + 0.1 * size, z + 0.03))
        tie = geo.cone(0.05 * size, 0.07 * size, 8, color).tf((0, ry + 0.1 * size, z + 0.17 * size))
        knot = geo.lathe([(0.035 * size, -0.01), (0.045 * size, 0.0), (0.035 * size, 0.012)], 10,
                         color=palette.ROPE).tf((0, ry + 0.1 * size, z + 0.17 * size))
        out += [s.on("chest"), tie.on("chest"), knot.on("chest")]
    elif kind == "quiver":
        q = geo.cyl(0.045, 0.3, 10, r_top=0.05, color=color)
        q.tf((0, 0, -0.12), rot=(0, -18, 0)).tf((0.03, ry + 0.075, z + 0.05))
        out.append(q.on("chest"))
        for i, dx in enumerate((-0.015, 0.0, 0.017)):
            ar = geo.cyl(0.005, 0.12, 5, color=palette.WOOD).tf((dx, 0, 0.15), rot=(0, -18, 0)).tf(
                (0.03, ry + 0.075, z + 0.05))
            fl = geo.extrude([(-0.012, 0), (0.012, 0), (0.006, 0.05), (-0.006, 0.05)], 0.003,
                             "#f2efe6").tf((dx, 0, 0.23), rot=(0, -18, 0)).tf((0.03, ry + 0.075, z + 0.05))
            out += [ar.on("chest"), fl.on("chest")]
    # straps
    rx = torso_r(b, z)[0]
    for sgn in (1, -1):
        st = band(b, z, strap, "body", thick=0.01, inflate=1.15, segs=16, bone="chest")
        st.tf(rot=(0, sgn * 62, 0)).tf((0, 0, 0))
        # recentre around the torso after tilting
        c = st.V.mean(0)
        st.V += np.array([sgn * rx * 0.55, 0, z]) - c
        st.V[:, 0] *= 0.55
        st.V[:, 0] += sgn * rx * 0.25
        out.append(st)
    return out


# ---------------------------------------------------------------------------
# Headwear
# ---------------------------------------------------------------------------

def _dome(b, inflate, cut, color, peak=1.0, segs=18, n=7, front_lift=0.0):
    """Shell over the skull: elliptic profile above z=cut (relative, -1..1)."""
    rx, ry, rz = (r * inflate for r in b.head_r)
    a0 = math.asin(max(min(cut, 0.99), -0.99))
    prof = []
    for i in range(n + 1):
        a = a0 + (math.pi / 2 - a0) * i / n
        r = math.cos(a)
        z = math.sin(a) * peak
        prof.append((r, z))
    prof[-1] = (0, prof[-1][1])
    p = geo.lathe(prof, segs, cap_bottom=True, cap_top=False, color=color, phase=math.pi / segs)
    p.V *= np.array([rx, ry, rz])
    if front_lift:
        zmin = p.V[:, 2].min()
        lift = front_lift * np.clip(-p.V[:, 1] / ry, 0, 1) ** 1.5 * np.clip(
            1 - (p.V[:, 2] - zmin) / (rz * 0.8), 0, 1)
        p.V[:, 2] += lift
    p.V += b.head_c
    return p


@tagged("hat")
def helm_kettle(b, metal, brim=1.45, mat="metal", plume=None):
    hc = b.head_c
    rx, ry, rz = b.head_r
    d = _dome(b, 1.08, 0.12, metal, peak=1.05)
    zc = hc[2] + rz * 0.12 * 1.08
    br = geo.lathe([(rx * 0.95, zc + 0.012), (rx * brim, zc - 0.03), (rx * brim + 0.012, zc - 0.035),
                    (rx * brim, zc - 0.045), (rx * 0.95, zc - 0.005)], 20, color=metal)
    br.V[:, 1] = (br.V[:, 1]) * (ry / rx)
    br.V[:, 0:2] += hc[0:2]
    out = [d.on("head", mat), br.on("head", mat)]
    if plume:
        out += _plume(b, plume)
    return out


@tagged("hat")
def helm_nasal(b, metal, mat="metal", trim=None, nasal=True, aventail=None, spike=True):
    hc = b.head_c
    rx, ry, rz = b.head_r
    d = _dome(b, 1.09, 0.1, metal, peak=1.35 if spike else 1.05, front_lift=0.0)
    out = [d.on("head", mat)]
    zc = hc[2] + rz * 0.1 * 1.09
    rim = geo.lathe([(1.0, -0.014), (1.03, 0.0), (1.0, 0.016)], 20, cap_bottom=False,
                    cap_top=False, color=trim or palette.mul(metal, 0.8))
    rim.V[:, 0] *= rx * 1.09
    rim.V[:, 1] *= ry * 1.09
    rim.V += np.array([hc[0], hc[1], zc])
    out.append(rim.on("head", mat))
    if nasal:
        nz = geo.rbox(0.022, 0.012, 0.09, 0.005, color=metal).tf(
            (0, hc[1] - ry * 1.08, zc - 0.03), rot=(-12, 0, 0))
        out.append(nz.on("head", mat))
    if spike:
        sp = geo.lathe([(0.012, 0), (0.004, 0.05), (0, 0.06)], 8, color=trim or metal).tf(
            (0, 0, hc[2] + rz * 1.09 * 1.33))
        out.append(sp.on("head", mat))
    if aventail:
        av = geo.lathe([(rx * 1.05, hc[2] - rz * 0.25), (rx * 1.12, zc)], 18, cap_bottom=False,
                       cap_top=False, color=aventail)
        av.V[:, 1] *= ry / rx
        av.V[:, 0:2] += hc[0:2]
        keep = [f for f in av.F if np.mean(av.V[list(f), 1] - hc[1]) > -ry * 0.55]
        av.F = keep
        out.append(av.on("head", "metal"))
    return out


@tagged("hat")
def helm_shishak(b, metal, ear_guards=True, mat="metal", trim=palette.GOLD, plume=None):
    """Rus' pointed helm; hares get ear sleeves going up their ears."""
    out = helm_nasal(b, metal, mat, trim=trim, nasal=True, spike=True)
    if ear_guards and b.species == "hare":
        from .beast import ear_chain
        for s, sign in (("L", 1), ("R", -1)):
            e0, e1, e2 = ear_chain(b, sign)
            sl = geo.tube([e0 + (e1 - e0) * 0.05, e0 + (e1 - e0) * 0.5, e0 + (e1 - e0) * 0.95],
                          [0.05, 0.047, 0.042], 10, color=metal, squash=0.55)
            sl.mat = mat
            out.append(sl.on(f"ear.{s}"))
            rg = geo.tube([e0 + (e1 - e0) * 0.9, e1 + (e1 - e0) * 0.02],
                          [0.045, 0.045], 10, color=trim, squash=0.6)
            rg.mat = mat
            out.append(rg.on(f"ear.{s}"))
    if plume:
        out += _plume(b, plume)
    return out


@tagged("hat")
def helm_sallet(b, metal, mat="metal", trim=None, plume=None):
    """Light open helm sitting high on the skull with a flared tail at the back."""
    hc = b.head_c
    rx, ry, rz = b.head_r
    d = _dome(b, 1.06, 0.38, metal, peak=1.02)
    zc = hc[2] + rz * 0.38 * 1.06

    def tail(V):
        back = np.clip((V[:, 1] - hc[1]) / ry, 0, 1)
        low = np.clip(1 - (V[:, 2] - zc) / (rz * 0.5), 0, 1)
        V[:, 1] += 0.05 * back ** 2 * low
        V[:, 2] -= 0.06 * back ** 2 * low
        return V
    d.deform(tail)
    out = [d.on("head", mat)]
    k = math.cos(math.asin(0.38)) * 1.06
    rim = geo.lathe([(1.0, -0.012), (1.05, 0.0), (1.0, 0.012)], 18, cap_bottom=False,
                    cap_top=False, color=trim or palette.mul(metal, 0.8), phase=math.pi / 18)
    rim.V[:, 0] *= rx * k
    rim.V[:, 1] *= ry * k
    rim.V += np.array([hc[0], hc[1], zc])
    rim.deform(tail)
    out.append(rim.on("head", mat))
    if plume:
        out += _plume(b, plume)
    return out


@tagged("hat")
def helm_great(b, metal, mat="metal", visor_up=True, trim=palette.GOLD, crest=None):
    """Bascinet with raised visor: face visible (bulldog guard)."""
    hc = b.head_c
    rx, ry, rz = b.head_r
    d = _dome(b, 1.1, -0.35, metal, peak=1.1)
    keep = []
    for f in d.F:
        c = d.V[list(f)].mean(0) - hc
        face = c[1] < -ry * 0.55 and c[2] < rz * 0.35 and abs(c[0]) < rx * 0.75
        if not face:
            keep.append(f)
    d.F = keep
    out = [d.on("head", mat)]
    if visor_up:
        vz = hc[2] + rz * 0.62
        v = geo.ellipsoid(rx * 0.8, 0.07, 0.07, 5, palette.mul(metal, 0.9)).tf(
            (0, hc[1] - ry * 0.75, vz + 0.02), rot=(-35, 0, 0))
        out.append(v.on("head", mat))
        sl = geo.box(rx * 0.9, 0.01, 0.008, "#202020").tf((0, hc[1] - ry * 0.82 - 0.05, vz - 0.0),
                                                           rot=(-35, 0, 0))
        out.append(sl.on("head", "body"))
    rim = geo.lathe([(1.0, -0.012), (1.03, 0.0), (1.0, 0.012)], 20, cap_bottom=False,
                    cap_top=False, color=trim)
    rim.V *= np.array([rx * 1.1, ry * 1.1, 1])
    rim.V += np.array([hc[0], hc[1], hc[2] + rz * 0.45])
    out.append(rim.on("head", mat))
    if crest:
        out += _plume(b, crest, big=True)
    return out


def _plume(b, color, big=False):
    hc = b.head_c
    rz = b.head_r[2]
    top = hc + np.array([0, 0.0, rz * 1.12])
    pts = geo.bezier(top, top + np.array([0, 0.06, 0.12]), top + np.array([0, 0.22, 0.06]), n=7)
    r = np.array([0.03, 0.045, 0.05, 0.048, 0.04, 0.028, 0.008]) * (1.4 if big else 1.0)
    p = geo.tube(pts, r, 8, color=color, squash=0.45)
    p.mat = "team"
    return [p.on("head")]


@tagged("hat")
def hood(b, color, mat="team", mantle=False, open_face=0.78, point=0.0):
    hc = b.head_c
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, 8, color)
    p.V *= np.array([rx * 1.13, ry * 1.13, rz * 1.12])
    if point:
        p.V[:, 1] += point * np.clip(p.V[:, 2] / rz, 0, 1) ** 2 * np.clip(p.V[:, 1] / ry + 0.3, 0, 1)
    V = p.V
    zl = rz * 0.62 * open_face / 0.78
    fx = np.clip(1 - np.abs(V[:, 0]) / (rx * open_face * 1.1), 0, 1)
    fz = np.clip((zl - V[:, 2]) / (rz * 0.25), 0, 1)
    fy = np.clip((-V[:, 1] - ry * 0.2) / (ry * 0.3), 0, 1)
    w = np.clip(fx * 3, 0, 1) * fz * fy
    p.V = V * (1 - 0.3 * w[:, None])
    p.V += hc
    out = [p.on("head", mat)]
    if mantle:
        z = b.neck_z
        rxt, ryt = torso_r(b, z - 0.03)
        m = geo.lathe([(rxt * 0.75, z + 0.05), (rxt * 1.1, z - 0.0), (rxt * 1.35, z - 0.07),
                       (rxt * 1.38, z - 0.085)], 18, cap_bottom=True, cap_top=True, color=color)
        m.V[:, 1] *= _ratio(b) * 1.1
        out.append(m.on("chest", mat))
    return out


@tagged("hat")
def straw_hat(b, color=palette.STRAW, band_c="#a33a2a", brim=1.7):
    hc = b.head_c
    rx, ry, rz = b.head_r
    z = hc[2] + rz * 0.55
    p = geo.lathe([(rx * brim, z - 0.025), (rx * brim + 0.01, z - 0.018), (rx * 0.9, z + 0.005),
                   (rx * 0.85, z + 0.11), (rx * 0.6, z + 0.15), (0, z + 0.155)], 20, color=color)
    p.paint(geo.stripes(palette.mul(color, 0.82), axis=2, freq=160, width=0.25))
    bd = geo.lathe([(rx * 0.9, z + 0.012), (rx * 0.89, z + 0.045)], 20, cap_bottom=False,
                   cap_top=False, color=band_c)
    bd.V *= np.array([1.02, 1.02, 1])
    out = []
    for q in (p, bd):
        q.V[:, 0:2] += hc[0:2]
        out.append(q.on("head", "body"))
    return out


@tagged("hat")
def cap(b, color, feather=None, mat="team", tilt=-12):
    """Soft beret / kolpak with optional feather."""
    hc = b.head_c
    rx, ry, rz = b.head_r
    d = _dome(b, 1.1, 0.3, color, peak=1.15)
    d.V -= hc
    d.tf(rot=(tilt * 0.3, tilt, 0))
    d.V += hc
    out = [d.on("head", mat)]
    rim = geo.lathe([(1.0, -0.016), (1.06, 0.0), (1.0, 0.018)], 20, cap_bottom=False, cap_top=False,
                    color=palette.mul(color, 0.75))
    rim.V *= np.array([rx * 1.12, ry * 1.12, 1])
    rim.tf(rot=(tilt * 0.3, tilt, 0))
    rim.V += np.array([hc[0], hc[1], hc[2] + rz * 0.33])
    out.append(rim.on("head", "cloth"))
    if feather:
        base = hc + np.array([rx * 0.7, ry * 0.2, rz * 0.6])
        pts = geo.bezier(base, base + np.array([0.04, 0.05, 0.12]), base + np.array([0.02, 0.15, 0.2]), n=7)
        f = geo.tube(pts, [0.006, 0.022, 0.028, 0.026, 0.02, 0.012, 0.002], 6, color=feather, squash=0.25)
        out.append(f.on("head", "cloth"))
    return out


@tagged("hat")
def fur_hat(b, color, fur="#f2ece0", mat="team"):
    """Kolpak with fur trim (hare archers, princes)."""
    hc = b.head_c
    rx, ry, rz = b.head_r
    out = []
    d = _dome(b, 1.08, 0.25, color, peak=1.35)
    out.append(d.on("head", mat))
    tr = geo.lathe([(1.0, -0.03), (1.1, -0.01), (1.1, 0.02), (1.0, 0.035)], 20, cap_bottom=False,
                   cap_top=False, color=fur)
    tr.V *= np.array([rx * 1.1, ry * 1.1, 1])
    tr.V += np.array([hc[0], hc[1], hc[2] + rz * 0.3])
    tr.deform(lambda V: V + 0.004 * np.sin(V * 90))
    out.append(tr.on("head", "cloth"))
    return out


@tagged("hat")
def crown(b, gold=palette.GOLD, gem="#c0283c", points=6, h=0.07, r_scale=0.72, tilt=0.0):
    hc = b.head_c
    rx, ry, rz = b.head_r
    z = hc[2] + rz * 0.78
    r = rx * r_scale
    segs = points * 4
    V, F = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        top = h if i % 4 == 0 else (h * 0.45 if i % 2 == 0 else h * 0.35)
        V += [(r * math.cos(a), r * math.sin(a), 0), (r * math.cos(a), r * math.sin(a), top)]
    for i in range(segs):
        k = (i + 1) % segs
        F.append((2 * i, 2 * k, 2 * k + 1, 2 * i + 1))
    outer = geo.Part(V, F, gold)
    inner = outer.copy()
    inner.V[:, 0:2] *= 0.9
    inner.F = [tuple(reversed(f)) for f in inner.F]
    p = geo.merge([outer, inner])
    p.V[:, 1] *= ry / rx
    p.tf(rot=(tilt, 0, 0)).tf((hc[0], hc[1], z))
    out = [p.on("head", "metal")]
    for i in range(points):
        a = 2 * math.pi * i / points
        g = geo.qsphere(0.014, 2, gem).tf((r * math.cos(a) * 1.02, r * math.sin(a) * ry / rx * 1.02,
                                          h * 0.25)).tf(rot=(tilt, 0, 0)).tf((hc[0], hc[1], z))
        out.append(g.on("head", "gloss"))
    return out


@tagged("hat")
def kokoshnik(b, color, gold=palette.GOLD, pearl="#fbf6ea"):
    hc = b.head_c
    rx, ry, rz = b.head_r
    pts = []
    for i in range(17):
        a = math.pi * i / 16
        pts.append((math.cos(a) * rx * 1.05, math.sin(a) * rz * 0.75))
    poly = pts
    k = geo.extrude(poly, 0.025, color, bevel=0.06)
    k.paint(geo.patch((0, 0, rz * 0.35), 0.11, gold, 0.6, axis_scale=(1, 3, 1)))
    k.tf(rot=(-12, 0, 0)).tf(hc + np.array([0, -ry * 0.25, rz * 0.68]))
    out = [k.on("head", "team")]
    for i in range(1, 16, 2):
        a = math.pi * i / 16
        p = geo.qsphere(0.011, 2, pearl).tf((math.cos(a) * rx * 0.98, -0.016, math.sin(a) * rz * 0.68))
        p.tf(rot=(-12, 0, 0)).tf(hc + np.array([0, -ry * 0.25, rz * 0.68]))
        out.append(p.on("head", "gloss"))
    return out


@tagged("hat")
def bandana(b, color, mat="team"):
    hc = b.head_c
    rx, ry, rz = b.head_r
    d = _dome(b, 1.04, 0.5, color, peak=1.02)
    out = [d.on("head", mat)]
    k = geo.ellipsoid(0.03, 0.025, 0.025, 3, color).tf(hc + np.array([0, ry * 1.0, rz * 0.4]))
    for s in (1, -1):
        t = geo.tube([hc + np.array([s * 0.01, ry * 1.0, rz * 0.4]),
                      hc + np.array([s * 0.04, ry * 1.12, rz * 0.25]),
                      hc + np.array([s * 0.05, ry * 1.18, rz * 0.1])], [0.02, 0.018, 0.01], 6,
                     color=color, squash=0.3)
        out.append(t.on("head", mat))
    out.append(k.on("head", mat))
    return out


@tagged("hat")
def merchant_hat(b, color, trim=palette.GOLD):
    hc = b.head_c
    rx, ry, rz = b.head_r
    z = hc[2] + rz * 0.45
    p = geo.lathe([(rx * 1.05, z - 0.02), (rx * 1.12, z + 0.02), (rx * 1.15, z + 0.1),
                   (rx * 1.0, z + 0.2), (rx * 0.5, z + 0.25), (0, z + 0.255)], 18, color=color)
    p.V[:, 1] *= ry / rx
    p.V[:, 0:2] += hc[0:2]
    p.deform(lambda V: V + np.column_stack([np.zeros(len(V)),
                                            0.04 * np.clip((V[:, 2] - z) / 0.25, 0, 1) ** 2,
                                            np.zeros(len(V))]))
    rim = geo.lathe([(rx * 1.08, z - 0.03), (rx * 1.13, z - 0.005), (rx * 1.08, z + 0.02)], 18,
                    cap_bottom=False, cap_top=False, color=trim)
    rim.V[:, 1] *= ry / rx
    rim.V[:, 0:2] += hc[0:2]
    return [p.on("head", "team"), rim.on("head", "metal")]


@tagged("hat")
def wide_hat(b, color, brim=1.9):
    hc = b.head_c
    rx, ry, rz = b.head_r
    z = hc[2] + rz * 0.5
    p = geo.lathe([(rx * brim, z - 0.03), (rx * brim + 0.01, z - 0.02), (rx * 0.85, z + 0.01),
                   (rx * 0.8, z + 0.17), (rx * 0.75, z + 0.18), (0, z + 0.182)], 20, color=color)
    p.V[:, 0:2] += hc[0:2]
    return [p.on("head", "cloth")]


@tagged("hat")
def beak_mask(b, color="#e8dcc0", lens="#9fe04a"):
    hc = b.head_c
    rx, ry, rz = b.head_r
    out = []
    pts = geo.bezier(hc + np.array([0, -ry * 0.75, -rz * 0.1]), hc + np.array([0, -ry * 1.6, -rz * 0.25]),
                     hc + np.array([0, -ry * 2.3, -rz * 0.7]), n=8)
    bk = geo.tube(pts, np.linspace(0.075, 0.006, 8), 10, color=color)
    out.append(bk.on("head", "body"))
    for s in (1, -1):
        g = geo.cyl(0.032, 0.02, 12, color=palette.DARK_IRON).tf((0, 0, 0), rot=(90, 0, 0)).tf(
            hc + np.array([s * rx * 0.42, -ry * 0.88, rz * 0.12]))
        gl = geo.cyl(0.024, 0.006, 12, color=lens).tf((0, 0, 0), rot=(90, 0, 0)).tf(
            hc + np.array([s * rx * 0.42, -ry * 0.88 - 0.016, rz * 0.12]))
        out += [g.on("head", "metal"), gl.on("head", "glow")]
    return out


# ---------------------------------------------------------------------------
# Weapons & tools (local: +Z = pointing direction, grip at origin)
# ---------------------------------------------------------------------------

def _grip(length=0.11, r=0.015, color=palette.LEATHER, z0=-0.03):
    g = geo.cyl(r, length, 8, color=color, z0=z0)
    g.paint(geo.stripes(palette.mul(color, 0.7), axis=2, freq=170, width=0.3))
    return g


def sword(length=0.56, width=0.095, steel=palette.STEEL, guard=palette.GOLD, grip=palette.LEATHER,
          pommel=None):
    """Oversized chunky sword (Blizzard proportions: ~1.5x realistic)."""
    parts = [_grip(0.11, 0.02, grip)]
    gd = geo.rbox(0.24, 0.05, 0.045, 0.016, color=guard).tf((0, 0, 0.08))
    gd.deform(lambda V: V + np.column_stack([np.zeros(len(V)), np.zeros(len(V)),
                                             0.25 * (V[:, 0] ** 2) * 4]))
    parts.append(gd.on(None, "gold"))
    for s in (1, -1):
        parts.append(geo.cone(0.026, 0.05, 6, guard).tf(rot=(0, s * 70, 0)).tf((s * 0.11, 0, 0.1)).on(None, "gold"))
    gem = geo.qsphere(0.016, 2, "#c0283c").tf((0, -0.022, 0.08))
    parts.append(gem.on(None, "gloss"))
    pm = geo.qsphere(0.032, 3, pommel or guard).tf((0, 0, -0.05))
    parts.append(pm.on(None, "gold"))
    bl = geo.blade(length, width, 0.026, tip=0.2, color=steel).tf((0, 0, 0.095), rot=(0, 0, 90))
    bl.paint(geo.patch((0, 0, 0.095 + length * 0.4), length * 0.42, palette.mul(steel, 0.72), 0.5,
                       axis_scale=(0.15, 0.25, 1)))
    parts.append(bl.on(None, "metal"))
    # gold inlay running up the fuller on both faces
    for side in (-1, 1):
        inl = geo.tube([(0, side * 0.0135, 0.11), (0, side * 0.0135, 0.11 + length * 0.35)],
                       [0.007, 0.004], 5, color=guard, squash=0.4)
        parts.append(inl.on(None, "gold"))
    # leather wrap rings on the grip
    for zz in np.linspace(-0.015, 0.06, 4):
        parts.append(geo.lathe([(0.021, zz - 0.006), (0.024, zz), (0.021, zz + 0.006)], 8,
                               cap_bottom=False, cap_top=False, color="#3a2418").on(None, "body"))
    return parts


def sabre(length=0.58, steel=palette.STEEL, guard=palette.GOLD, grip="#3a2a4a"):
    parts = sword(length, 0.085, steel, guard, grip)
    bl = parts[-1]

    def bend(V):
        z = np.clip((V[:, 2] - 0.095) / length, 0, 1)
        V[:, 1] += 0.12 * z ** 2
        return V
    bl.deform(bend)
    return parts


def rapier(length=0.55, steel=palette.STEEL, guard=palette.STEEL):
    parts = [_grip(0.1, 0.014, "#2a2440")]
    cup = geo.lathe([(0.0, 0.05), (0.05, 0.065), (0.058, 0.09), (0.05, 0.1)], 12, cap_top=False,
                    color=guard)
    parts.append(cup.on(None, "metal"))
    parts.append(geo.qsphere(0.022, 3, palette.GOLD).tf((0, 0, -0.045)).on(None, "metal"))
    bl = geo.blade(length, 0.026, 0.012, tip=0.15, color=steel).tf((0, 0, 0.09))
    parts.append(bl.on(None, "metal"))
    return parts


def dagger(length=0.2, steel=palette.STEEL, guard=palette.DARK_IRON):
    parts = [_grip(0.08, 0.013, "#2a2226", z0=-0.02)]
    parts.append(geo.rbox(0.07, 0.022, 0.018, 0.006, color=guard).tf((0, 0, 0.065)).on(None, "metal"))
    bl = geo.blade(length, 0.05, 0.014, tip=0.35, color=steel).tf((0, 0, 0.07), rot=(0, 0, 90))
    bl.deform(lambda V: V + np.column_stack([np.zeros(len(V)),
                                             0.03 * np.clip((V[:, 2] - 0.07) / length, 0, 1) ** 2,
                                             np.zeros(len(V))]))
    parts.append(bl.on(None, "metal"))
    return parts


def cleaver(steel="#8d8a82", rust="#8b4a2a"):
    parts = [_grip(0.12, 0.016, palette.WOOD_DARK, z0=-0.04)]
    bl = geo.extrude([(-0.012, 0.08), (0.11, 0.08), (0.12, 0.3), (0.0, 0.32), (-0.012, 0.25)],
                     0.014, steel, bevel=0.05)
    bl.tf(rot=(0, 0, 90))
    bl.paint(geo.patch((0, -0.08, 0.28), 0.08, rust, 0.6))
    bl.paint(geo.patch((0, -0.02, 0.12), 0.05, rust, 0.5))
    parts.append(bl.flat().on(None, "metal"))
    return parts


def polearm(length=1.15, grip_at=0.42, wood=palette.WOOD, head=None):
    """Shaft from -grip_at to length-grip_at along +Z."""
    z0 = -grip_at
    sh = geo.cyl(0.016, length, 8, color=wood, z0=z0)
    sh.paint(geo.stripes(palette.mul(wood, 0.85), axis=2, freq=60, width=0.15))
    butt = geo.cone(0.02, 0.04, 8, palette.DARK_IRON).tf((0, 0, z0), rot=(180, 0, 0))
    return [sh, butt.on(None, "metal")], z0 + length


def halberd(steel=palette.STEEL, wood=palette.WOOD):
    parts, top = polearm(1.2, 0.45, wood)
    axe = geo.extrude([(0.0, -0.09), (0.04, -0.1), (0.16, -0.14), (0.15, 0.02), (0.09, 0.08),
                       (0.0, 0.06)], 0.016, steel, bevel=0.05).tf(rot=(0, 0, 90))
    axe.tf((0, 0, top - 0.12))
    spike = geo.blade(0.18, 0.04, 0.014, 0.4, steel).tf((0, 0, top - 0.02), rot=(0, 0, 90))
    hook = geo.cone(0.016, 0.09, 6, steel).tf(rot=(-95, 0, 0)).tf((0, 0.012, top - 0.07))
    band_ = geo.cyl(0.021, 0.04, 8, color=palette.DARK_IRON, z0=top - 0.17)
    parts += [axe.flat().on(None, "metal"), spike.on(None, "metal"), hook.on(None, "metal"),
              band_.on(None, "metal")]
    return parts


def spear(steel=palette.STEEL, wood="#c9b99a", length=1.25, tassel=None):
    parts, top = polearm(length, 0.48, wood)
    head = geo.blade(0.2, 0.065, 0.02, 0.5, steel).tf((0, 0, top - 0.01), rot=(0, 0, 90))
    sock = geo.cyl(0.02, 0.06, 8, r_top=0.014, color=palette.DARK_IRON, z0=top - 0.05)
    parts += [head.on(None, "metal"), sock.on(None, "metal")]
    if tassel:
        t = geo.cone(0.03, 0.08, 8, tassel).tf((0, 0, top - 0.05), rot=(180, 0, 0))
        parts.append(t.on(None, "team"))
    return parts


def pitchfork(steel="#a7aab0", wood=palette.WOOD):
    parts, top = polearm(1.15, 0.44, wood)
    bar = geo.rbox(0.13, 0.02, 0.025, 0.008, color=steel).tf((0, 0, top))
    parts.append(bar.on(None, "metal"))
    for x in (-0.055, 0.0, 0.055):
        t = geo.tube([(x, 0, top), (x * 1.1, -0.01, top + 0.1), (x * 1.05, -0.02, top + 0.19)],
                     [0.008, 0.007, 0.002], 6, color=steel)
        parts.append(t.on(None, "metal"))
    return parts


def mace(steel=palette.STEEL, wood=palette.WOOD_DARK, size=1.0, flanges=6):
    parts = [_grip(0.36, 0.017, wood, z0=-0.06)]
    hd = geo.qsphere(0.05 * size, 3, steel).tf((0, 0, 0.32))
    parts.append(hd.on(None, "metal"))
    for i in range(flanges):
        a = 360 * i / flanges
        f = geo.extrude([(0, -0.05), (0.045, -0.02), (0.045, 0.03), (0, 0.06)], 0.012, steel).tf(
            rot=(0, 0, a)).tf((0, 0, 0.32))
        f.V *= np.array([size, size, 1])
        parts.append(f.flat().on(None, "metal"))
    return parts


def hammer(steel=palette.IRON, wood=palette.WOOD, size=1.0, mallet=False):
    L = 0.32 * size
    parts = [geo.cyl(0.016 * size, L, 8, color=wood, z0=-0.08 * size)]
    if mallet:
        hd = geo.cyl(0.075 * size, 0.2 * size, 12, color=palette.WOOD, z0=-0.1 * size).tf(
            rot=(90, 0, 0)).tf((0, 0, L - 0.08 * size))
        for y in (-0.08 * size, 0.08 * size):
            bd = geo.cyl(0.08 * size, 0.022 * size, 12, color=palette.mul(palette.GOLD, 0.8),
                         z0=-0.011 * size).tf(rot=(90, 0, 0)).tf((0, y, L - 0.08 * size))
            parts.append(bd.on(None, "metal"))
        parts.append(hd)
    else:
        hd = geo.rbox(0.06 * size, 0.14 * size, 0.06 * size, 0.01, color=steel).tf(
            (0, 0, L - 0.09 * size))
        parts.append(hd.on(None, "metal"))
    return parts


def pickaxe(steel=palette.IRON, wood=palette.WOOD):
    parts = [geo.cyl(0.016, 0.38, 8, color=wood, z0=-0.08)]
    hd = geo.tube(geo.bezier((0, 0.16, 0.24), (0, 0.0, 0.33), (0, -0.16, 0.24), n=9),
                  [0.004, 0.012, 0.018, 0.022, 0.024, 0.022, 0.018, 0.012, 0.004], 6, color=steel)
    parts.append(hd.on(None, "metal"))
    return parts


def hoe(steel=palette.IRON, wood="#c9b99a"):
    parts, top = polearm(0.95, 0.35, wood)
    bl = geo.rbox(0.1, 0.12, 0.014, 0.006, color=steel).tf((0, -0.06, top - 0.01), rot=(-15, 0, 0))
    parts.append(bl.on(None, "metal"))
    return parts


def staff(wood=palette.WOOD, top=None, length=1.15, grip_at=0.5):
    parts, z = polearm(length, grip_at, wood)
    knob = geo.qsphere(0.03, 3, palette.mul(wood, 0.8)).tf((0, 0, z))
    parts.append(knob)
    if top is not None:
        parts += [p.tf((0, 0, z)) for p in top]
    return parts


def wheel_topper(metal=palette.GOLD, r=0.08):
    ring = geo.lathe([(r, -0.012), (r + 0.012, 0), (r, 0.012), (r - 0.012, 0)], 16, cap_bottom=False,
                     cap_top=False, color=metal).tf(rot=(90, 0, 0)).tf((0, 0, r + 0.02))
    out = [ring.on(None, "metal")]
    for a in range(0, 180, 45):
        sp = geo.cyl(0.006, 2 * r, 5, color=metal, z0=-r).tf(rot=(0, a, 0)).tf((0, 0, r + 0.02))
        out.append(sp.on(None, "metal"))
    out.append(geo.qsphere(0.02, 2, palette.mul(metal, 1.1)).tf((0, 0, r + 0.02)).on(None, "metal"))
    return out


def lantern(glow="#b7f04a", metal=palette.DARK_IRON):
    out = []
    body = geo.cyl(0.04, 0.08, 6, color=glow).tf((0, 0, -0.14))
    out.append(body.on(None, "glow"))
    for z in (-0.14, -0.06):
        c = geo.cyl(0.048, 0.012, 6, color=metal, z0=z - 0.006)
        out.append(c.on(None, "metal"))
    roof = geo.cone(0.05, 0.04, 6, metal).tf((0, 0, -0.054))
    hook = geo.tube([(0, 0, -0.015), (0, 0, 0.02), (0, -0.02, 0.04)], 0.005, 5, color=metal)
    out += [roof.on(None, "metal"), hook.on(None, "metal")]
    return out


def longbow(wood=palette.WOOD, length=0.95, string="#efe6cf", recurve=False):
    """Bow along Z centred on the grip; belly bulges to -Y, string on +Y."""
    h = length / 2
    n = 13
    pts, radii = [], []
    for i in range(n):
        t = i / (n - 1) * 2 - 1  # -1..1
        y = -0.09 * (1 - t * t)
        if recurve:
            y += 0.05 * max(abs(t) - 0.75, 0) / 0.25
        pts.append((0, y, t * h))
        radii.append(0.019 * (1 - 0.55 * abs(t)) + 0.004)
    limb = geo.tube(pts, radii, 6, color=wood, squash=0.8)
    grip = geo.cyl(0.021, 0.09, 8, color=palette.LEATHER, z0=-0.045).tf((0, -0.09, 0))
    tip_y = pts[0][1]
    st = geo.tube([(0, tip_y + 0.004, -h), (0, tip_y + 0.004, 0), (0, tip_y + 0.004, h)],
                  0.0025, 4, color=string)
    st.ao = False
    for p in (limb, grip, st):
        p.V[:, 1] += 0.09
    return [limb, grip, st]


def crossbow(wood=palette.WOOD, steel=palette.STEEL):
    """Stock along +Z (pointing forward when mounted), prod across X."""
    stock = geo.rbox(0.04, 0.05, 0.42, 0.012, color=wood).tf((0, 0.0, 0.13))
    butt = geo.rbox(0.045, 0.08, 0.12, 0.02, color=wood).tf((0, 0.025, -0.08), rot=(-12, 0, 0))
    prod = geo.tube([(-0.2, 0.02, 0.27), (-0.1, -0.005, 0.31), (0.0, -0.01, 0.32),
                     (0.1, -0.005, 0.31), (0.2, 0.02, 0.27)], [0.008, 0.012, 0.014, 0.012, 0.008],
                    6, color=steel)
    st = geo.tube([(-0.2, 0.02, 0.27), (0, 0.02, 0.18), (0.2, 0.02, 0.27)], 0.0025, 4, color="#efe6cf")
    bolt = geo.cyl(0.006, 0.2, 5, color=palette.WOOD_DARK, z0=0.17).tf((0, -0.03, 0))
    return [stock, butt, prod.on(None, "metal"), st, bolt]


def sling(rope=palette.ROPE, pouch=palette.LEATHER):
    pts = geo.bezier((0, 0, 0), (0.02, -0.05, -0.15), (0, 0.0, -0.28), n=7)
    r = geo.tube(pts, 0.005, 4, color=rope)
    pc = geo.ellipsoid(0.035, 0.025, 0.04, 3, pouch).tf((0, 0, -0.3))
    return [r, pc]


def shield_heater(color, rim=palette.GOLD, emblem=None, w=0.36, h=0.46):
    face = geo.heater_shield(w, h, 0.03, color)
    face.mat = "team"
    rimp = geo.heater_shield(w * 1.07, h * 1.06, 0.022, rim).tf((0, 0.006, 0))
    out = [face, rimp.on(None, "metal")]
    if emblem:
        out += [e.tf((0, -0.018, 0.02)) for e in emblem]
    return out


def shield_round(color, rim=palette.IRON, emblem=None, r=0.2, boss=True):
    face = geo.disc(r, 0.036, 20, color, bevel=0.1)
    face.mat = "team"
    rimp = geo.lathe([(r * 0.94, -0.026), (r * 1.08, -0.016), (r * 1.08, 0.016), (r * 0.94, 0.026)],
                     22, cap_bottom=False, cap_top=False, color=rim).tf(rot=(90, 0, 0))
    out = [face, rimp.on(None, "metal")]
    if boss:
        bs = geo.lathe([(r * 0.28, 0), (r * 0.22, 0.03), (0, 0.045)], 12, color=rim).tf(rot=(90, 0, 0)).tf(
            (0, -0.012, 0))
        out.append(bs.on(None, "metal"))
    for a in np.linspace(0, 2 * math.pi, 10, endpoint=False):
        st = geo.qsphere(0.011, 2, rim).tf((math.cos(a) * r * 0.86, -0.02, math.sin(a) * r * 0.86))
        out.append(st.on(None, "metal"))
    if emblem:
        out += [e.tf((0, -0.018, 0)) for e in emblem]
    return out


def shield_kite(color, rim=palette.GOLD, emblem=None, w=0.3, h=0.54):
    pts = []
    for i in range(13):
        a = math.pi * i / 12
        pts.append((math.cos(a) * w / 2, h * 0.28 + math.sin(a) * w * 0.4))
    pts += [(-w / 2, h * 0.2), (-w * 0.2, -h * 0.3), (0, -h * 0.55), (w * 0.2, -h * 0.3), (w / 2, h * 0.2)]
    face = geo.extrude(pts, 0.03, color, bevel=0.1)
    face.mat = "team"
    rimp = geo.extrude([(x * 1.07, z * 1.05) for x, z in pts], 0.02, rim).tf((0, 0.006, 0))
    out = [face, rimp.on(None, "metal")]
    if emblem:
        out += [e.tf((0, -0.018, 0.04)) for e in emblem]
    return out


def pot_lid(metal="#a8a39a"):
    d = geo.lathe([(0.15, -0.006), (0.16, 0.0), (0.12, 0.03), (0.0, 0.04)], 16, color=metal).tf(
        rot=(90, 0, 0))
    hd = geo.qsphere(0.02, 2, palette.WOOD_DARK).tf((0, -0.045, 0))
    return [d.on(None, "metal"), hd]


# --- heraldry ---------------------------------------------------------------

def emblem(faction, color, scale=1.0):
    """Flat faction emblem facing -Y, ~0.12 m wide at scale 1."""
    s = scale
    out = []
    if faction == "cats":   # cat eye under a crescent moon
        eye = []
        for i in range(16):
            a = 2 * math.pi * i / 16
            eye.append((math.cos(a) * 0.06 * s, math.sin(a) * 0.032 * s * (1 - 0.3 * abs(math.cos(a)))))
        out.append(geo.extrude(eye, 0.008, color).tf((0, 0, -0.02 * s)))
        out.append(geo.extrude([(math.cos(a) * 0.01 * s, math.sin(a) * 0.028 * s)
                                for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)],
                               0.012, "#151520").tf((0, -0.003, -0.02 * s)))
        moon = []
        for i in range(12):
            a = math.pi * (0.15 + 0.7 * i / 11)
            moon.append((math.cos(a) * 0.05 * s, 0.05 * s + math.sin(a) * 0.035 * s))
        for i in range(12):
            a = math.pi * (0.85 - 0.7 * i / 11)
            moon.append((math.cos(a) * 0.035 * s, 0.06 * s + math.sin(a) * 0.022 * s))
        out.append(geo.extrude(moon, 0.008, color))
    elif faction == "dogs":  # collar ring with a crown
        out.append(geo.lathe([(0.045 * s, -0.004), (0.06 * s, -0.004), (0.06 * s, 0.004),
                              (0.045 * s, 0.004)], 20, color=color).tf(rot=(90, 0, 0)).tf((0, 0, -0.02 * s)))
        cr = [(-0.045, 0.03), (-0.045, 0.075), (-0.025, 0.055), (0.0, 0.085), (0.025, 0.055),
              (0.045, 0.075), (0.045, 0.03)]
        out.append(geo.extrude([(x * s, z * s) for x, z in cr], 0.008, color))
        out.append(geo.disc(0.016 * s, 0.01, 10, color).tf((0, 0, -0.08 * s)))
    elif faction == "hamsters":  # wheel and wheat ear
        out.append(geo.lathe([(0.05 * s, -0.004), (0.062 * s, -0.004), (0.062 * s, 0.004),
                              (0.05 * s, 0.004)], 20, color=color).tf(rot=(90, 0, 0)))
        for a in range(0, 180, 45):
            out.append(geo.box(0.1 * s, 0.006, 0.008 * s, color).tf(rot=(0, a, 0)))
        out.append(geo.disc(0.016 * s, 0.01, 10, color))
    elif faction == "hares":  # two ears and a carrot
        for sgn in (1, -1):
            ear = [(math.cos(a) * 0.016 * s, math.sin(a) * 0.055 * s)
                   for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
            out.append(geo.extrude(ear, 0.008, color).tf((sgn * 0.024 * s, 0, 0.035 * s),
                                                        rot=(0, -sgn * 12, 0)))
        car = [(-0.022 * s, -0.0), (0.022 * s, -0.0), (0.0, -0.085 * s)]
        out.append(geo.extrude(car, 0.008, palette.CARROT).tf((0, 0, -0.005 * s)))
        out.append(geo.extrude([(-0.012 * s, 0), (0.012 * s, 0), (0.0, 0.03 * s)], 0.008,
                               palette.LEAF).tf((0, 0, -0.008 * s)))
    elif faction == "rats":
        out.append(geo.disc(0.05 * s, 0.01, 10, color))
        for sgn in (1, -1):
            out.append(geo.disc(0.025 * s, 0.01, 8, color).tf((sgn * 0.045 * s, 0, 0.04 * s)))
    for p in out:
        p.mat = "metal"
    return out


@tagged("emblem")
def chest_emblem(b, faction, color, z=None, inflate=1.2, scale=0.9):
    z = b.hip_h + b.torso_h * 0.62 if z is None else z
    ry = torso_r(b, z)[1] * inflate * 1.02 + 0.026
    out = []
    for e in emblem(faction, color, scale):
        e.tf((0, -ry, z))
        e.bone = "chest"
        out.append(e)
    return out


# ---------------------------------------------------------------------------
# Mounting helpers
# ---------------------------------------------------------------------------

def _hand_center(b, s):
    j = b.joints()
    return (j[f"wrist.{s}"] + j[f"hand_tip.{s}"]) / 2


@tagged("weapon", 2, default_side="R")
def in_hand(b, parts, side="R", rot=(90, 0, 0), offset=(0, 0, 0), extra_rot=(0, 0, 0), scale=1.0):
    """Mount weapon parts (built along +Z) in a hand. Pointing forward at rest."""
    c = _hand_center(b, side)
    bone = f"hand.{side}"
    out = []
    for p in parts:
        q = p.copy()
        q.V *= scale
        q.tf(rot=extra_rot)
        q.tf(rot=rot)
        q.tf(np.asarray(offset) + c + np.array([0, -0.004, 0]))
        q.bone = bone
        q.weights = None
        out.append(q)
    return out


@tagged("shield", 2, default_side="L")
def on_forearm(b, parts, side="L", out_offset=None, along=0.78):
    """Strap a shield (built facing -Y, up +Z) flat against the outside of the forearm.

    It rides parallel to the forearm, clear of the vambrace, centred low enough
    that its top stays below the elbow cop and the pauldron.
    """
    j = b.joints()
    el, wr = j[f"elbow.{side}"], j[f"wrist.{side}"]
    sign = 1 if side == "L" else -1
    zmax = max(p.V[:, 2].max() for p in parts)
    L2 = np.linalg.norm(wr - el)
    along = max(along, (zmax + 0.03) / L2)     # shield top stays below the elbow cop
    c = el + (wr - el) * along
    if out_offset is None:
        out_offset = b.arm_r * 1.75 + 0.11
    # frame aligned with the forearm: up = toward the elbow, face = outward
    up = (el - wr) / np.linalg.norm(el - wr)
    face = np.array([sign * 1.0, 0, 0]) - up * (sign * up[0])
    face /= np.linalg.norm(face)
    xa = np.cross(up, face)          # local +X
    R = np.column_stack([xa, -face, up])   # local (x, y, z) -> world; local -Y is the face
    out = []
    for p in parts:
        q = p.copy()
        q.V = q.V @ R.T + c + face * out_offset
        if np.linalg.det(R) < 0:
            q.F = [tuple(reversed(f)) for f in q.F]
        q.bone = f"forearm.{side}"
        q.weights = None
        out.append(q)
    return out


@tagged("back")
def on_back(b, parts, rot=(0, 0, 0), offset=(0, 0, 0)):
    z = b.hip_h + b.torso_h * 0.55
    ry = torso_r(b, z)[1]
    out = []
    for p in parts:
        q = p.copy()
        q.tf(rot=rot)
        q.tf(np.array([0, ry + 0.05, z]) + np.asarray(offset))
        q.bone = "chest"
        out.append(q)
    return out


@tagged("hip")
def on_hip(b, parts, side="L", rot=(0, 0, 0)):
    z = b.hip_h + 0.02
    rx, ry = torso_r(b, z + 0.02)
    sign = 1 if side == "L" else -1
    out = []
    for p in parts:
        q = p.copy()
        q.tf(rot=rot)
        q.tf((sign * rx * 1.15, 0.02, z))
        q.bone = "hips"
        out.append(q)
    return out
