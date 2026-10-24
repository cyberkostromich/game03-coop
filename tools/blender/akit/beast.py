"""Shared anthropomorphic beast body: proportions, skeleton and fur parts.

One humanoid rig for every species (GDD: "one shared humanoid skeleton and
swappable parts: head, ears, tail, armour"). Species differ by the numbers in
their Body plan and by their head/ear/tail builders.

Coordinates: meters, z up, character faces -Y, left = +X.
"""
import math
from dataclasses import dataclass, field, replace

import numpy as np

from . import geo, palette
from .geo import Part
from .rig import blend_weights, chain_weights


@dataclass
class Body:
    species: str
    hip_h: float = 0.34          # hip joint height
    hip_w: float = 0.095         # hip joint x offset (heroic stance)
    torso_h: float = 0.36
    torso_w: float = 0.34
    torso_d: float = 0.25
    belly: float = 1.0           # >1 = rounder lower torso
    chest: float = 1.0           # >1 = broader shoulders
    waist: float = 0.74          # waist width relative to chest
    neck_h: float = 0.035
    head_r: tuple = (0.165, 0.15, 0.158)   # rx, ry(depth), rz
    head_drop: float = 0.03      # how far head sinks onto the torso
    arm_r: float = 0.05
    arm_len: float = 0.36        # shoulder -> wrist
    paw_r: float = 0.06
    leg_r: float = 0.062
    foot_len: float = 0.17
    foot_r: float = 0.056
    eye_size: float = 1.0
    eye_yaw: float = 30.0
    eye_pitch: float = -2.0
    eye_spacing: float = 1.0
    tail_len: float = 0.55
    tail_r: float = 0.03
    scale: float = 1.0
    fur: str = "ginger"
    extras: dict = field(default_factory=dict)

    # derived joints ------------------------------------------------------
    @property
    def pelvis_z(self):
        return self.hip_h

    @property
    def shoulder_z(self):
        return self.hip_h + self.torso_h * 0.86

    @property
    def neck_z(self):
        return self.hip_h + self.torso_h

    @property
    def head_c(self):
        rz = self.head_r[2]
        return np.array([0.0, 0.0, self.neck_z + self.neck_h + rz - self.head_drop])

    @property
    def shoulder_x(self):
        return self.torso_w / 2 * 0.97 * self.chest

    def joints(self):
        """World positions of every joint (rest pose, A-pose arms)."""
        j = {}
        hz = self.hip_h
        j["hips"] = np.array([0, 0, hz])
        j["spine"] = np.array([0, 0, hz + self.torso_h * 0.45])
        j["chest_top"] = np.array([0, 0, self.neck_z])
        hc = self.head_c
        j["neck"] = np.array([0, 0, self.neck_z - 0.01])
        j["head"] = hc - np.array([0, 0, self.head_r[2] * 0.75])
        j["head_top"] = hc + np.array([0, 0, self.head_r[2]])
        sx, sz = self.shoulder_x, self.shoulder_z
        L = self.arm_len
        j["shoulder.L"] = np.array([sx, 0.0, sz])
        # heroic A-pose: arms hang outside the belt and armour bulk
        bulk = max(0.0, self.torso_w * self.belly - 0.31)
        j["elbow.L"] = np.array([sx + 0.075 + bulk * 0.45, 0.018, sz - L * 0.52])
        j["wrist.L"] = np.array([sx + 0.115 + bulk * 0.7, -0.01, sz - L])
        j["hand_tip.L"] = j["wrist.L"] + np.array([0.008, -0.012, -self.paw_r * 1.5])
        j["hip.L"] = np.array([self.hip_w, 0.0, hz])
        j["knee.L"] = np.array([self.hip_w + 0.006, -0.012, (hz + self.foot_r) * 0.5 + 0.01])
        j["ankle.L"] = np.array([self.hip_w + 0.006, 0.0, self.foot_r * 0.9])
        j["toe.L"] = np.array([self.hip_w + 0.008, -self.foot_len * 0.85, self.foot_r * 0.5])
        for k in list(j):
            if k.endswith(".L"):
                p = j[k].copy()
                p[0] *= -1
                j[k[:-2] + ".R"] = p
        # tail root at the back of the pelvis
        # tail root low at the back of the pelvis: it leaves from under the belt/plates
        j["tail_root"] = np.array([0.0, self.torso_d * 0.4, hz - 0.035])
        return j


SPECIES = {
    "cat": Body("cat", fur="ginger", hip_h=0.56, hip_w=0.095, torso_h=0.42, torso_w=0.31,
                head_r=(0.142, 0.128, 0.132), waist=0.64, tail_len=0.75, arm_len=0.45,
                tail_r=0.028, eye_yaw=29, eye_size=1.0, foot_len=0.18),
    "dog": Body("dog", fur="shepherd", hip_h=0.54, torso_h=0.43, torso_w=0.36, torso_d=0.26,
                chest=1.06, waist=0.72, head_r=(0.146, 0.14, 0.146), tail_len=0.36, tail_r=0.04,
                eye_yaw=31, eye_size=0.95, leg_r=0.068, arm_r=0.056, arm_len=0.45, foot_len=0.19),
    "hamster": Body("hamster", fur="golden_ham", hip_h=0.34, hip_w=0.095, torso_h=0.4,
                    torso_w=0.45, torso_d=0.36, belly=1.18, waist=0.92,
                    head_r=(0.17, 0.152, 0.148), head_drop=0.05, arm_len=0.35, arm_r=0.056,
                    leg_r=0.072, foot_len=0.17, tail_len=0.05, tail_r=0.035, eye_yaw=31,
                    eye_size=1.0, neck_h=0.0, paw_r=0.064),
    "hare": Body("hare", fur="brown_hare", hip_h=0.6, torso_h=0.42, torso_w=0.31,
                 torso_d=0.23, waist=0.68, head_r=(0.138, 0.142, 0.148), foot_len=0.26,
                 foot_r=0.052, leg_r=0.062, tail_len=0.06, tail_r=0.065, eye_yaw=36,
                 eye_size=1.0, eye_pitch=0.0, arm_len=0.44),
    "rat": Body("rat", fur="rat", hip_h=0.5, torso_h=0.42, torso_w=0.32, torso_d=0.28,
                belly=1.05, waist=0.76, head_r=(0.13, 0.15, 0.124), head_drop=0.02,
                tail_len=0.85, tail_r=0.03, eye_yaw=33, eye_size=0.85, eye_pitch=4.0,
                arm_len=0.44, foot_len=0.19),
}

# design-space head width per species: head builders are authored at this
# size and scaled onto the real head (keeps every feature in proportion)
HEAD_REF = {"cat": 0.215, "dog": 0.2, "hamster": 0.22, "hare": 0.185, "rat": 0.18}


def body_for(species, **kw):
    b = replace(SPECIES[species])
    for k, v in kw.items():
        setattr(b, k, v)
    return b


# ---------------------------------------------------------------------------
# Skeleton
# ---------------------------------------------------------------------------

def skeleton(b: Body):
    j = b.joints()
    hc = b.head_c
    bones = [
        ("root", (0, 0, 0), (0, -0.12, 0), None, False),
        ("hips", j["hips"], j["spine"], "root"),
        ("chest", j["spine"], j["chest_top"], "hips"),
        ("neck", j["neck"], j["head"], "chest"),
        ("head", j["head"], j["head_top"], "neck"),
    ]
    for s in ("L", "R"):
        bones += [
            (f"upper_arm.{s}", j[f"shoulder.{s}"], j[f"elbow.{s}"], "chest"),
            (f"forearm.{s}", j[f"elbow.{s}"], j[f"wrist.{s}"], f"upper_arm.{s}"),
            (f"hand.{s}", j[f"wrist.{s}"], j[f"hand_tip.{s}"], f"forearm.{s}"),
            (f"thigh.{s}", j[f"hip.{s}"], j[f"knee.{s}"], "hips"),
            (f"shin.{s}", j[f"knee.{s}"], j[f"ankle.{s}"], f"thigh.{s}"),
            (f"foot.{s}", j[f"ankle.{s}"], j[f"toe.{s}"], f"shin.{s}"),
        ]
    # eyes (scaled for blinks), ears (1-2 bones), cheeks (hamster stuffing)
    for s, sign in (("L", 1), ("R", -1)):
        ep = eye_pos(b, sign)
        bones.append((f"eye.{s}", ep, ep + np.array([0, -0.05, 0]), "head"))
        e0, e1, e2 = ear_chain(b, sign)
        bones.append((f"ear.{s}", e0, e1, "head"))
        if e2 is not None:
            bones.append((f"ear_tip.{s}", e1, e2, f"ear.{s}"))
    bones.append(("jaw", hc + np.array([0, -b.head_r[1] * 0.3, -b.head_r[2] * 0.35]),
                  hc + np.array([0, -b.head_r[1] * 1.0, -b.head_r[2] * 0.45]), "head"))
    if b.species == "hamster":
        bones.append(("cheeks", hc + np.array([0, -0.05, -0.08]),
                      hc + np.array([0, -0.12, -0.08]), "head"))
    # tail chain
    pts = tail_points(b)
    names = tail_bones(b)
    parent = "hips"
    for i, n in enumerate(names):
        bones.append((n, pts[i], pts[i + 1], parent))
        parent = n
    # cape bones (used by gear that has capes; harmless otherwise)
    cz = b.shoulder_z
    bones.append(("cape", (0, b.torso_d * 0.5, cz), (0, b.torso_d * 0.62, cz - 0.16), "chest"))
    bones.append(("cape_tip", (0, b.torso_d * 0.62, cz - 0.16),
                  (0, b.torso_d * 0.7, cz - 0.34), "cape"))
    # tabard cloth chain (front of the hips); animated to ride over the leading thigh
    tz = b.hip_h + 0.02
    ty = -(b.torso_d * 0.5 * 1.3 + 0.05)
    bones.append(("tabard", (0, ty, tz), (0, ty - 0.01, tz - 0.12), "hips"))
    bones.append(("tabard_tip", (0, ty - 0.01, tz - 0.12), (0, ty - 0.02, tz - 0.26), "tabard"))
    # attachment helpers (non-deforming) for engines: weapon & head sockets
    bones.append(("socket_weapon", j["wrist.R"] + np.array([0, -0.02, -0.04]),
                  j["wrist.R"] + np.array([0, -0.1, -0.04]), "hand.R", False))
    return bones


def tail_bones(b):
    n = {"cat": 4, "rat": 4, "dog": 3, "hamster": 1, "hare": 1}[b.species]
    return [f"tail.{i + 1}" for i in range(n)]


def tail_points(b):
    """Rest curve of the tail (joint positions)."""
    j = b.joints()
    r0 = j["tail_root"]
    n = len(tail_bones(b))
    L = b.tail_len
    pts = []
    for i in range(n + 1):
        t = i / n
        if b.species == "cat":
            # sweeps back and up, tip hooks over - stays well behind the back
            p = r0 + np.array([0, L * (0.62 * t + 0.12 * math.sin(math.pi * t)), L * 0.62 * t ** 1.25])
            p[1] -= L * 0.12 * t ** 4
        elif b.species == "rat":
            p = r0 + np.array([0, L * t, L * 0.1 * math.sin(t * math.pi) - 0.17 * t])
            p[0] = 0.08 * math.sin(t * math.pi * 1.2)
            p[2] = max(p[2], 0.03)
        elif b.species == "dog":
            p = r0 + np.array([0, L * (0.8 * t + 0.05 * t * t), L * (0.25 * t + 0.55 * t * t)])
        else:
            p = r0 + np.array([0, L * t + 0.0, L * 0.25 * t])
        pts.append(p)
    return np.array(pts)


def _design(b):
    """Design-space body whose head matches the size head builders were authored at."""
    hs = b.head_r[0] / HEAD_REF[b.species]
    return replace(b, head_r=tuple(r / hs for r in b.head_r)), hs


def to_head_world(b, P):
    bd, hs = _design(b)
    return (np.asarray(P, float) - bd.head_c) * hs + b.head_c


def eye_pos(b, sign):
    bd, _ = _design(b)
    return to_head_world(b, _eye_pos_d(bd, sign))


def ear_chain(b, sign):
    bd, _ = _design(b)
    e = _ear_chain_d(bd, sign)
    return tuple(None if p is None else to_head_world(b, p) for p in e)


def _eye_pos_d(b, sign):
    hc = b.head_c
    rx, ry, rz = b.head_r
    yaw = math.radians(b.eye_yaw * b.eye_spacing)
    pit = math.radians(b.eye_pitch)
    d = np.array([sign * math.sin(yaw) * math.cos(pit), -math.cos(yaw) * math.cos(pit),
                  math.sin(pit)])
    return hc + d * np.array([rx, ry, rz]) * 0.93 + np.array([0, 0, -rz * 0.08])


def _ear_chain_d(b, sign):
    """(base, mid, tip-or-None) for the ear bones."""
    hc = b.head_c
    rx, ry, rz = b.head_r
    sp = b.species
    ear = b.extras.get("ears", {"cat": "cat", "dog": "pointy", "hamster": "round",
                                "hare": "long", "rat": "round_big"}[sp])
    if ear == "long":
        base = hc + np.array([sign * rx * 0.42, ry * 0.12, rz * 0.82])
        mid = base + np.array([sign * 0.035, 0.03, 0.2])
        tip = mid + np.array([sign * 0.03, 0.04, 0.2])
        return base, mid, tip
    if ear == "floppy":
        base = hc + np.array([sign * rx * 0.86, 0.0, rz * 0.45])
        mid = base + np.array([sign * 0.05, 0.0, -0.08])
        tip = mid + np.array([sign * 0.015, -0.01, -0.12])
        return base, mid, tip
    if ear == "rose":
        base = hc + np.array([sign * rx * 0.72, 0.01, rz * 0.7])
        return base, base + np.array([sign * 0.07, 0.0, 0.03]), None
    if ear in ("round", "round_big"):
        k = 0.75 if ear == "round" else 0.72
        base = hc + np.array([sign * rx * k, ry * 0.1, rz * 0.7])
        return base, base + np.array([sign * 0.05, 0.01, 0.06]), None
    # cat / pointy
    base = hc + np.array([sign * rx * 0.55, ry * 0.05, rz * 0.72])
    return base, base + np.array([sign * 0.05, 0.015, 0.14]), None


# ---------------------------------------------------------------------------
# Fur body parts
# ---------------------------------------------------------------------------

def fur_colors(b):
    base, light, dark = palette.FUR[b.fur]
    return base, light, dark


_TORSO_T = np.array([0.0, 0.07, 0.22, 0.44, 0.66, 0.84, 0.94, 1.0])
_TORSO_R = np.array([0.0, 0.74, 0.86, 0.78, 0.98, 1.0, 0.82, 0.42])


def torso_r(b, z):
    """(rx, ry) of the fur torso at height z: pelvis, waist, chest, shoulders."""
    z0, h = b.hip_h - 0.07, b.torso_h + 0.09
    t = min(max((z - z0) / h, 0.0), 1.0)
    prof = _TORSO_R.copy()
    prof[3] = prof[4] * b.waist + (b.belly - 1) * 0.9
    prof[2] = max(prof[2], prof[3] * 1.04) + (b.belly - 1) * 0.5
    prof[4:6] *= b.chest
    r = float(np.interp(t, _TORSO_T, prof))
    # smooth the polyline a little
    r = 0.5 * r + 0.25 * float(np.interp(t - 0.04, _TORSO_T, prof)) + \
        0.25 * float(np.interp(t + 0.04, _TORSO_T, prof))
    rx = r * b.torso_w / 2
    depth = b.torso_d / b.torso_w * (1 + 0.1 * math.sin(math.pi * min(max((t - 0.5) / 0.45, 0), 1)))
    return rx, rx * depth


def torso(b):
    base, light, dark = fur_colors(b)
    z0, h = b.hip_h - 0.07, b.torso_h + 0.09
    prof = []
    n = 14
    for i in range(n + 1):
        z = z0 + h * i / n
        prof.append((torso_r(b, z)[0], z))
    prof[0] = (0, z0 - 0.005)
    prof[-1] = (0, z0 + h)
    p = geo.lathe(prof, 18, color=base)
    zs = p.V[:, 2]
    k = np.array([torso_r(b, z)[1] / max(torso_r(b, z)[0], 1e-6) for z in zs])
    p.V[:, 1] *= k
    p.paint(geo.patch((0, -b.torso_d * 0.5, z0 + h * 0.5), 0.17, light, 0.5,
                      axis_scale=(0.7, 0.6, 1.4)))
    blend_weights(p, "hips", "chest", b.hip_h + 0.03, b.hip_h + b.torso_h * 0.6)
    return [p]


def neck(b):
    base, light, _ = fur_colors(b)
    if b.neck_h <= 0:
        return []
    z = b.neck_z - 0.04
    p = geo.cyl(b.torso_w * 0.2, b.neck_h + 0.08, 12, color=base).tf((0, 0.0, z))
    return [p.on("neck")]


def limb(path, r0, r1, color, bone_a, bone_b, j_mid):
    pts = geo.bezier(path[0], path[1], path[2], n=7)
    p = geo.tube(pts, np.linspace(r0, r1, len(pts)), 10, color=color)
    return blend_weights_dist(p, bone_a, bone_b, j_mid)


def blend_weights_dist(p, bone_a, bone_b, mid, soft=0.03):
    """Blend across a joint: vertices above the joint plane -> bone_a."""
    a = np.asarray(mid, float)
    d = p.V[:, 2] - a[2]
    t = np.clip(0.5 - d / (2 * soft), 0, 1)
    t = t * t * (3 - 2 * t)
    p.weights = {bone_a: 1 - t, bone_b: t}
    p.bone = None
    return p


def _limb_tube(pts3, r0, r1, color, bones, bulge=0.0):
    """One continuous tube through 3 joints, skinned across the middle joint."""
    a, m, c = (np.asarray(p, float) for p in pts3)
    path = np.vstack([geo.bezier(a, a + (m - a) * 0.75, m, n=5)[:-1],
                      geo.bezier(m, m + (c - m) * 0.25, c, n=5)])
    t = np.linspace(0, 1, len(path))
    radii = r0 + (r1 - r0) * t + bulge * np.sin(np.pi * t * 2) ** 2 * (t < 0.5)
    p = geo.tube(path, radii, 10, color=color)
    from .rig import chain_weights
    chain_weights(p, bones, [a, m, c])
    return p


def arms(b, sleeve=None, paw=None):
    base, light, dark = fur_colors(b)
    j = b.joints()
    out = []
    for s in ("L", "R"):
        sh, el, wr = j[f"shoulder.{s}"], j[f"elbow.{s}"], j[f"wrist.{s}"]
        c = sleeve or base
        sgn = 1 if s == "L" else -1
        arm = _limb_tube([sh + np.array([-sgn * 0.02, 0, 0.0]), el, wr], b.arm_r * 1.12,
                         b.arm_r * 0.9, c, [f"upper_arm.{s}", f"forearm.{s}"],
                         bulge=b.arm_r * 0.08)
        ball = geo.qsphere(b.arm_r * 1.25, 4, c).tf(sh + np.array([-sgn * 0.008, 0, -0.005]))
        out += [arm, ball.on(f"upper_arm.{s}")]
        out += paw_parts(b, s, paw or light)
    return out


def paw_parts(b, s, color):
    """Clenched fist: palm block, rolled fingers, wrapped thumb, small claws."""
    j = b.joints()
    wr, tip = j[f"wrist.{s}"], j[f"hand_tip.{s}"]
    sign = 1 if s == "L" else -1
    r = b.paw_r
    d = (tip - wr) / np.linalg.norm(tip - wr)
    c = wr + d * r * 0.85
    bone = f"hand.{s}"
    out = []
    palm = geo.rbox(r * 1.45, r * 1.3, r * 1.55, r * 0.45, k=2, color=color).tf(c)
    out.append(palm.on(bone))
    # four finger rolls across the front (grip side faces -Y)
    for i in range(4):
        t = (i - 1.5) / 1.5
        fc = c + np.array([sign * 0.0, -r * 0.62, -r * 0.1 + t * r * 0.5])
        f = geo.capsule(r * 0.27, r * 1.15, 8, 2, color=color).tf((0, 0, -r * 0.57), rot=(0, 90, 0)).tf(fc)
        out.append(f.on(bone))
        cl = geo.cone(r * 0.1, r * 0.22, 5, "#f3ece0").tf(rot=(100, 0, 0)).tf(
            fc + np.array([-sign * r * 0.42, -r * 0.22, 0]))
        cl.ao = False
        out.append(cl.on(bone, "gloss"))
    th = geo.capsule(r * 0.3, r * 1.0, 8, 2, color=color).tf((0, 0, -r * 0.5), rot=(0, 75, 0)).tf(
        c + np.array([-sign * r * 0.55, -r * 0.45, r * 0.35]))
    out.append(th.on(bone))
    return out


def legs(b, pants=None, boots=None):
    base, light, dark = fur_colors(b)
    j = b.joints()
    out = []
    for s in ("L", "R"):
        hp, kn, an = j[f"hip.{s}"], j[f"knee.{s}"], j[f"ankle.{s}"]
        c = pants or base
        leg = _limb_tube([hp + np.array([0, 0, 0.0]), kn, an + np.array([0, 0, 0.01])],
                         b.leg_r * 1.18, b.leg_r * 0.86, c, [f"thigh.{s}", f"shin.{s}"])
        if boots:
            leg.paint(geo.where(lambda V, z=kn[2] - 0.02: V[:, 2] < z, boots))
        out.append(leg)
        out += foot_parts(b, s, boots or light)
    return out


def foot_parts(b, s, color):
    j = b.joints()
    an, toe = j[f"ankle.{s}"], j[f"toe.{s}"]
    L = b.foot_len
    r = b.foot_r
    c = (an + toe) / 2 + np.array([0, 0, -0.005])
    f = geo.ellipsoid(r * 1.0, L * 0.62, r * 0.85, 4, color).tf(c)
    f.deform(lambda V: np.column_stack([V[:, 0], V[:, 1], np.maximum(V[:, 2], 0.004)]))
    return [f.on(f"foot.{s}")]


# --- heads ----------------------------------------------------------------

def head(b):
    sp = b.species
    fn = {"cat": head_cat, "dog": head_dog, "hamster": head_hamster, "hare": head_hare,
          "rat": head_rat}[sp]
    bd, hs = _design(b)
    parts = fn(bd)
    parts += eyes(bd)
    ear_parts = ears(bd)
    for p in ear_parts:
        p.group = "fur.ears"
    parts += ear_parts
    parts += head_tufts(bd)
    for p in parts:
        p.V = to_head_world(b, p.V)
    return parts


def tuft(base, direction, length, width, color, n=3, spread=25.0, curl=0.3, seed=0):
    """Cluster of flattened, curved fur spikes (WoW-style chunky fur)."""
    rng = np.random.default_rng(seed)
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    up = np.array([0, 0, 1.0]) if abs(d[2]) < 0.9 else np.array([0, -1.0, 0])
    side = np.cross(d, up)
    side /= np.linalg.norm(side)
    nrm = np.cross(side, d)
    out = []
    for i in range(n):
        a = math.radians((i - (n - 1) / 2) * spread + rng.uniform(-6, 6))
        di = d * math.cos(a) + side * math.sin(a)
        L = length * rng.uniform(0.75, 1.1)
        p0 = np.asarray(base, float) + side * (i - (n - 1) / 2) * width * 0.6
        p1 = p0 + di * L * 0.55 + nrm * L * curl * 0.3
        p2 = p0 + di * L + nrm * L * curl
        pts = geo.bezier(p0, p1, p2, n=5)
        t = geo.tube(pts, np.array([1.0, 0.85, 0.6, 0.35, 0.05]) * width, 5, color=color, squash=0.45)
        out.append(t)
    return out


def head_tufts(b):
    """Cheek ruff / brow tufts that break the head silhouette."""
    base, light, dark = fur_colors(b)
    hc = b.head_c
    rx, ry, rz = b.head_r
    out = []
    style = b.extras.get("tufts", {"cat": "cheeks", "dog": "none", "hamster": "none",
                                   "hare": "cheeks_small", "rat": "none"}[b.species])
    if style in ("cheeks", "cheeks_small"):
        k = 1.0 if style == "cheeks" else 0.7
        for sign in (1, -1):
            c = hc + np.array([sign * rx * 0.86, -ry * 0.25, -rz * 0.42])
            for p in tuft(c, (sign * 1.0, 0.15, -0.55), 0.085 * k, 0.03 * k, light if b.fur != "black" else base,
                          n=3, spread=22, curl=-0.15, seed=7 + sign):
                out.append(p.on("head"))
    return out


def _skull(b, color, n=8):
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, n, color)
    return p, (rx, ry, rz)


def head_cat(b):
    base, light, dark = fur_colors(b)
    hc = b.head_c
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, 8, base)

    def shape(V):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        cheek = 1 + 0.12 * np.clip(-z + 0.1, 0, 1) * np.clip(-y + 0.2, 0, 1.2)
        V[:, 0] = x * rx * cheek
        V[:, 1] = y * ry * (1 - 0.12 * np.clip(-y, 0, 1) * np.clip(z + 0.3, 0, 1))
        V[:, 2] = z * rz
        return V
    p.deform(shape).tf(hc)
    face = (0, -ry * 0.95, -rz * 0.38)
    p.paint(geo.patch(hc + np.array(face), 0.5 * rx, light, 0.6, axis_scale=(1.3, 0.8, 0.9)))
    if b.fur in ("ginger", "grey_tabby"):
        # tabby forehead stripes
        region = lambda V: np.clip((V[:, 2] - hc[2] - rz * 0.35) / 0.03, 0, 1) * \
            np.clip((-(V[:, 1] - hc[1]) + 0.02) / 0.05, 0, 1)
        p.paint(geo.stripes(dark, axis=0, freq=55, width=0.3, phase=1.57, region=region))
        # cheek stripes sweeping back from the eyes
        cheek = lambda V: np.clip((np.abs(V[:, 0] - hc[0]) - rx * 0.55) / 0.03, 0, 1) * \
            np.clip((hc[2] + rz * 0.15 - V[:, 2]) / 0.03, 0, 1) * np.clip((V[:, 1] - hc[1] + ry * 0.7) / 0.05, 0, 1)
        p.paint(geo.stripes(dark, axis=2, freq=70, width=0.32, phase=0.4, region=cheek))
        # darker crown fading into the face
        p.paint(geo.patch(hc + np.array([0, ry * 0.3, rz * 0.9]), rx * 0.9, palette.mix(base, dark, 0.35),
                          0.9, axis_scale=(1.2, 1.4, 0.7)))
    if b.fur == "siamese":
        p.paint(geo.patch(hc + np.array([0, -ry * 0.9, -rz * 0.3]), 0.55 * rx, dark, 0.7,
                          axis_scale=(1.0, 0.7, 0.9)))
    parts = [p.on("head")]
    parts += muzzle_cat(b, light)
    return parts


def muzzle_cat(b, light):
    hc = b.head_c
    rx, ry, rz = b.head_r
    out = []
    mz = hc + np.array([0, -ry * 0.86, -rz * 0.36])
    for s in (1, -1):
        pad = geo.ellipsoid(0.045, 0.035, 0.034, 4, light).tf(mz + np.array([s * 0.034, 0, 0]))
        out.append(pad.on("head"))
    chin = geo.ellipsoid(0.03, 0.025, 0.022, 3, light).tf(mz + np.array([0, 0.012, -0.035]))
    out.append(chin.on("jaw"))
    nose = geo.ellipsoid(0.022, 0.014, 0.014, 3, palette.NOSE_PINK).tf(
        mz + np.array([0, -0.03, 0.03]))
    nose.deform(lambda V: V * np.column_stack([1 + 0.6 * np.clip(V[:, 2] - mz[2] - 0.03, 0, 1) * 30,
                                               np.ones(len(V)), np.ones(len(V))]))
    out.append(nose.on("head", "gloss"))
    if b.extras.get("fangs"):
        out += fangs(b, mz + np.array([0, -0.03, -0.022]), spread=0.018)
    out += whiskers(b, mz)
    return out


def whiskers(b, mz, color="#f4f1ea", n=2, length=0.12):
    out = []
    for s in (1, -1):
        for i in range(n):
            a = 8 - i * 14
            start = mz + np.array([s * 0.05, -0.01, 0.005 - i * 0.012])
            d = np.array([s * math.cos(math.radians(a)), -0.25, math.sin(math.radians(a)) * 0.6])
            d /= np.linalg.norm(d)
            pts = [start, start + d * length * 0.5 + np.array([0, 0, 0.005]), start + d * length]
            w = geo.tube(pts, [0.0035, 0.0028, 0.0012], 4, color=color)
            w.ao = False
            out.append(w.on("head"))
    return out


def head_dog(b):
    base, light, dark = fur_colors(b)
    hc = b.head_c
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, 8, base).tf(scale=(rx, ry, rz)).tf(hc)
    style = b.extras.get("dog", "shepherd")
    snout_len = {"shepherd": 0.17, "beagle": 0.15, "bulldog": 0.06, "mastiff": 0.09,
                 "hound": 0.16}.get(style, 0.14)
    snout_w = {"bulldog": 0.135, "mastiff": 0.125}.get(style, 0.1)
    sc = hc + np.array([0, -ry * 0.75, -rz * 0.3])
    y0, y1 = hc[1] - ry * 0.4, hc[1] - ry - snout_len
    secs = []
    for i in range(9):
        t = i / 8
        y = y0 + (y1 - y0) * t
        w = snout_w * (1 - 0.22 * t)
        h = snout_w * 0.78 * (1 - 0.25 * t)
        if t > 0.7:
            k = math.sqrt(max(1 - ((t - 0.7) / 0.3) ** 2, 0.02))
            w *= k
            h *= k
        zc = hc[2] - rz * 0.3 - 0.012 * t
        ring = []
        for a in np.linspace(0, 2 * math.pi, 14, endpoint=False):
            sa = math.sin(a)
            ring.append((w * math.cos(a), y, zc + h * sa * (0.8 if sa > 0 else 1.0)))
        secs.append(ring)
    sn = geo.loft(secs, color=light)
    if style == "shepherd":
        p.paint(geo.patch(hc + np.array([0, ry * 0.3, rz * 0.55]), 0.2, dark, 0.9,
                          axis_scale=(1.6, 1.2, 0.8)))
        sn.paint(geo.patch(np.array([0, y1, hc[2] - rz * 0.2]), 0.09, dark, 0.8,
                           axis_scale=(1.0, 1.4, 0.8)))
    if style in ("beagle", "hound"):
        p.paint(geo.patch(hc + np.array([0, -ry * 0.95, 0.0]), 0.045, "#f6f0e6", 0.7,
                          axis_scale=(0.5, 1, 2.0)))
        p.paint(geo.patch(hc + np.array([0, ry * 0.2, rz * 0.6]), 0.2, dark, 0.9,
                          axis_scale=(1.4, 1.4, 0.7)))
    nose_c = np.array([0, y1 + 0.012, hc[2] - rz * 0.3 + snout_w * 0.42])
    nose = geo.ellipsoid(0.034 if style != "bulldog" else 0.04, 0.026, 0.024, 4,
                         palette.NOSE_DARK).tf(nose_c)
    parts = [p.on("head"), sn.on("head"), nose.on("head", "gloss")]
    jaw = geo.ellipsoid(snout_w * 0.62, snout_len * 0.5 + 0.03, 0.028, 4, light).tf(
        np.array([0, (y0 + y1) / 2 - 0.01, hc[2] - rz * 0.3 - snout_w * 0.62]))
    parts.append(jaw.on("jaw"))
    if style in ("bulldog", "mastiff"):
        for s in (1, -1):  # jowls
            jw = geo.ellipsoid(0.05, 0.05, 0.045, 4, light).tf(
                sc + np.array([s * 0.05, -snout_len * 0.3, -0.035]))
            parts.append(jw.on("head"))
        brow = geo.ellipsoid(rx * 0.75, 0.05, 0.03, 4, base).tf(hc + np.array([0, -ry * 0.82, rz * 0.2]))
        parts.append(brow.on("head"))
    if b.extras.get("fangs"):
        parts += fangs(b, np.array([0, y1 + 0.045, hc[2] - rz * 0.3 - snout_w * 0.42]),
                       size=1.3, spread=snout_w * 0.45)
    if b.extras.get("tongue"):
        tongue = geo.ellipsoid(0.02, 0.025, 0.006, 3, "#e0607a").tf(
            np.array([0.012, y1 + 0.03, hc[2] - rz * 0.3 - snout_w * 0.7]), rot=(20, 0, 0))
        parts.append(tongue.on("jaw"))
    # darker nose bridge reads as "dog" from above
    sn.paint(geo.patch(np.array([0, (y0 + y1) / 2, hc[2] - rz * 0.3 + snout_w * 0.75]), snout_w * 0.9,
                       palette.mul(base, 0.85), 0.8, axis_scale=(0.7, 2.2, 0.5)))
    return parts


def head_hamster(b):
    base, light, dark = fur_colors(b)
    hc = b.head_c
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, 8, base).tf(scale=(rx, ry, rz)).tf(hc)
    p.paint(geo.patch(hc + np.array([0, -ry * 0.9, -rz * 0.5]), 0.16, light, 0.7,
                      axis_scale=(1.5, 0.9, 1.0)))
    parts = [p.on("head")]
    for s in (1, -1):
        ck = geo.ellipsoid(0.085, 0.08, 0.072, 5, light).tf(
            hc + np.array([s * rx * 0.62, -ry * 0.48, -rz * 0.45]))
        ck.paint(geo.patch(hc + np.array([s * rx * 0.95, -ry * 0.2, -rz * 0.2]), 0.07, base, 0.9))
        parts.append(ck.on("cheeks"))
    mz = hc + np.array([0, -ry * 0.94, -rz * 0.3])
    nose = geo.ellipsoid(0.017, 0.012, 0.012, 3, palette.NOSE_PINK).tf(mz + np.array([0, -0.01, 0.0]))
    parts.append(nose.on("head", "gloss"))
    for s in (1, -1):
        m = geo.ellipsoid(0.028, 0.02, 0.02, 3, light).tf(mz + np.array([s * 0.02, 0.0, -0.025]))
        parts.append(m.on("head"))
    teeth = geo.rbox(0.022, 0.008, 0.02, 0.003, color="#fffdf5").tf(mz + np.array([0, -0.006, -0.05]))
    parts.append(teeth.on("jaw", "gloss"))
    parts += whiskers(b, mz + np.array([0, 0.01, -0.01]), length=0.08)
    return parts


def head_hare(b):
    base, light, dark = fur_colors(b)
    hc = b.head_c
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, 8, base)

    def shape(V):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        V[:, 0] = x * rx * (1 + 0.08 * np.clip(-z, 0, 1))
        V[:, 1] = y * ry * (1 + 0.1 * np.clip(-y, 0, 1) * np.clip(-z + 0.2, 0, 1))
        V[:, 2] = z * rz
        return V
    p.deform(shape).tf(hc)
    p.paint(geo.patch(hc + np.array([0, -ry * 0.95, -rz * 0.42]), 0.12, light, 0.7,
                      axis_scale=(1.4, 0.9, 1.0)))
    parts = [p.on("head")]
    mz = hc + np.array([0, -ry * 0.95, -rz * 0.38])
    for s in (1, -1):
        pad = geo.ellipsoid(0.034, 0.028, 0.03, 4, light).tf(mz + np.array([s * 0.026, 0, 0]))
        parts.append(pad.on("head"))
    nose = geo.ellipsoid(0.018, 0.012, 0.012, 3, palette.NOSE_PINK).tf(mz + np.array([0, -0.025, 0.028]))
    parts.append(nose.on("head", "gloss"))
    for s in (1, -1):
        t = geo.rbox(0.014, 0.008, 0.026, 0.003, color="#fffdf5").tf(
            mz + np.array([s * 0.0075, -0.02, -0.04]))
        parts.append(t.on("jaw", "gloss"))
    parts += whiskers(b, mz, length=0.1)
    return parts


def head_rat(b):
    base, light, dark = fur_colors(b)
    hc = b.head_c
    rx, ry, rz = b.head_r
    p = geo.qsphere(1.0, 8, base)

    def shape(V):
        x, y, z = V[:, 0], V[:, 1], V[:, 2]
        front = np.clip(-y, 0, 1)
        V[:, 0] = x * rx * (1 - 0.55 * front ** 1.5)
        V[:, 1] = y * ry * (1 + 0.85 * front ** 1.3)
        V[:, 2] = z * rz * (1 - 0.45 * front ** 1.5) - 0.04 * front ** 2
        return V
    p.deform(shape).tf(hc)
    p.paint(geo.patch(hc + np.array([0, -ry * 1.4, -rz * 0.45]), 0.15, light, 0.8))
    tip = hc + np.array([0, -ry * 1.83, -rz * 0.3])
    nose = geo.ellipsoid(0.022, 0.018, 0.018, 3, palette.NOSE_PINK).tf(tip)
    parts = [p.on("head"), nose.on("head", "gloss")]
    for s in (1, -1):
        t = geo.rbox(0.012, 0.008, 0.03, 0.003, color="#efe2a6").tf(
            tip + np.array([s * 0.007, 0.03, -0.05]))
        parts.append(t.on("jaw", "gloss"))
    parts += whiskers(b, tip + np.array([0, 0.03, 0.0]), color="#d9d2c6", length=0.11)
    return parts


def eyes(b):
    out = []
    style = b.extras.get("eyes", {"cat": "cat", "rat": "glow"}.get(b.species, "round"))
    k = b.eye_size
    for s, sign in (("L", 1), ("R", -1)):
        c = _eye_pos_d(b, sign)
        yaw = b.eye_yaw * b.eye_spacing * sign
        rot = (-(b.eye_pitch + 8), 0, yaw)
        bone = f"eye.{s}"
        if style == "cat":
            iris = b.extras.get("iris", "#c9d63a")
            e = geo.ellipsoid(0.042 * k, 0.022, 0.05 * k, 5, iris).tf(rot=rot).tf(c)
            pupil = geo.ellipsoid(0.011 * k, 0.012, 0.04 * k, 4, palette.EYE_DARK).tf(
                (0, -0.014, 0), rot=rot).tf(c)
            out += [e.on(bone, "gloss"), pupil.on(bone, "gloss")]
        elif style == "glow":
            e = geo.ellipsoid(0.034 * k, 0.02, 0.03 * k, 4, b.extras.get("glow", "#d8f05a")).tf(
                rot=rot).tf(c)
            pupil = geo.ellipsoid(0.012 * k, 0.012, 0.016 * k, 3, "#20240a").tf(
                (0, -0.012, 0), rot=rot).tf(c)
            out += [e.on(bone, "glow"), pupil.on(bone, "gloss")]
            continue
        else:
            e = geo.ellipsoid(0.036 * k, 0.022, 0.046 * k, 5, palette.EYE_DARK).tf(rot=rot).tf(c)
            out.append(e.on(bone, "gloss"))
        hl = geo.qsphere(0.011 * k, 2, "#ffffff").tf((sign * 0.012 * k, -0.02, 0.018 * k),
                                                     rot=rot).tf(c)
        hl2 = geo.qsphere(0.005 * k, 2, "#ffffff").tf((-sign * 0.01 * k, -0.02, -0.016 * k),
                                                      rot=rot).tf(c)
        for h in (hl, hl2):
            h.ao = False
            out.append(h.on(bone, "glow" if False else "gloss"))
        ang = b.extras.get("brow_angle", -14)
        lid = b.extras.get("lid", 0.0)
        if lid > 0:
            # angry upper lid: fur-coloured cap slicing the top of the eye
            lc = fur_colors(b)[0]
            eh = 0.05 * k
            ld = geo.ellipsoid(0.056 * k, 0.03, 0.036 * k, 5, lc)
            ld.tf((0, 0.002, eh * (1.45 - lid * 0.75)), rot=(0, sign * ang * 0.9, 0))
            ld.tf(rot=(-(b.eye_pitch + 8), 0, yaw)).tf(c)
            out.append(ld.on("head"))
        if b.extras.get("brows", True):
            brow_c = palette.mul(fur_colors(b)[0], 0.5)
            bc = c + np.array([sign * 0.004, -0.006, 0.062 * k - lid * 0.012])
            bw = 1.0 + 0.35 * min(lid, 1.0)
            br = geo.ellipsoid(0.04 * k * bw, 0.016, 0.012 * bw, 3, brow_c).tf(
                rot=(-(b.eye_pitch + 18), sign * ang, yaw)).tf(bc)
            out.append(br.on("head"))
    return out


def fangs(b, base, n=2, size=1.0, color="#fffaf0", spread=0.022, drop=0.0):
    """Little fangs peeking below the upper lip (warlike faces)."""
    out = []
    for s in (1, -1)[:n]:
        f = geo.cone(0.009 * size, 0.026 * size, 6, color).tf(rot=(180, 0, 0)).tf(
            base + np.array([s * spread, 0, -drop]))
        f.ao = False
        out.append(f.on("head", "gloss"))
    return out


def ears(b):
    base, light, dark = fur_colors(b)
    inner = palette.SKIN_PINK
    out = []
    ear = b.extras.get("ears", {"cat": "cat", "dog": "pointy", "hamster": "round",
                                "hare": "long", "rat": "round_big"}[b.species])
    for s, sign in (("L", 1), ("R", -1)):
        e0, e1, e2 = _ear_chain_d(b, sign)
        bone = f"ear.{s}"
        if ear in ("cat", "pointy"):
            h = np.linalg.norm(e1 - e0) * (1.25 if ear == "cat" else 1.35)
            w = 0.085 if ear == "cat" else 0.08
            secs = []
            for i in range(6):
                t = i / 5
                ww = w * (1 - t) ** 0.85 + 0.004
                dd = 0.035 * (1 - t) + 0.004
                secs.append([(ww * math.cos(a), dd * math.sin(a) + 0.01 * (1 - t), h * t)
                             for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)])
            outer = geo.loft(secs, color=base)
            inn = geo.loft([[(x * 0.62, y * 0.5 - 0.016, z * 0.82 + 0.008) for x, y, z in sec]
                            for sec in secs], color=inner)
            tipc = dark if b.fur in ("siamese", "shepherd") else base
            outer.paint(geo.grad_z(base, tipc, h * 0.3, h))
            d = (e1 - e0) / np.linalg.norm(e1 - e0)
            roll = math.degrees(math.atan2(d[0], d[2]))
            pitch = math.degrees(math.atan2(d[1], d[2]))
            for part in (outer, inn):
                part.tf(rot=(pitch, 0, 0)).tf(rot=(0, roll, 0)).tf(rot=(0, 0, sign * 12)).tf(e0)
                out.append(part.on(bone))
        elif ear == "long":
            L1 = np.linalg.norm(e1 - e0)
            L = L1 + np.linalg.norm(e2 - e1)
            secs = []
            n = 9
            for i in range(n + 1):
                t = i / n
                ww = 0.052 * math.sin(math.pi * (0.18 + 0.8 * t)) ** 0.6 + 0.006
                dd = 0.022 * (1 - 0.6 * t) + 0.004
                secs.append([(ww * math.cos(a), dd * math.sin(a), L * t)
                             for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)])
            outer = geo.loft(secs, color=base)
            inn = geo.loft([[(x * 0.6, y * 0.6 - 0.012, z * 0.9 + 0.02) for x, y, z in sec]
                            for sec in secs], color=inner)
            tipc = "#2b2420" if b.fur == "white_hare" else palette.mul(base, 0.65)
            outer.paint(geo.grad_z(base, tipc, L * 0.82, L * 1.0))
            pts = np.array([e0, e1, e2])
            for part in (outer, inn):
                _place_along(part, pts, L1, L)
                chain_weights(part, [bone, f"ear_tip.{s}"], pts)
                out.append(part)
        elif ear == "floppy":
            L = np.linalg.norm(e1 - e0) + np.linalg.norm(e2 - e1)
            secs = []
            for i in range(8):
                t = i / 7
                ww = 0.05 * math.sin(math.pi * (0.25 + 0.7 * t)) ** 0.5 + 0.01
                secs.append([(ww * math.cos(a), 0.016 * math.sin(a), L * t)
                             for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)])
            outer = geo.loft(secs, color=dark if b.extras.get("dog") == "beagle" else base)
            pts = np.array([e0, e1, e2])
            _place_along(outer, pts, np.linalg.norm(e1 - e0), L, side=sign)
            chain_weights(outer, [bone, f"ear_tip.{s}"], pts)
            out.append(outer)
        elif ear == "rose":
            f = geo.ellipsoid(0.045, 0.02, 0.035, 4, base).tf(rot=(10, 0, sign * 20)).tf((e0 + e1) / 2)
            out.append(f.on(bone))
        else:  # round ears (hamster / rat)
            big = ear == "round_big"
            r = 0.062 if big else 0.042
            disc = geo.ellipsoid(r, 0.018, r * 1.02, 5, base)
            inn = geo.ellipsoid(r * 0.72, 0.01, r * 0.74, 4, inner).tf((0, -0.011, 0))
            for part in (disc, inn):
                part.tf(rot=(-10, 0, sign * (25 if big else 18))).tf(
                    (e0 + e1) / 2 + np.array([0, 0, r * 0.3]))
                out.append(part.on(bone))
    return out


def _place_along(part, pts, L1, L, side=0):
    """Bend a part modelled along +Z (length L) onto a 3-point polyline."""
    V = part.V
    z = V[:, 2]
    out = np.zeros_like(V)
    d1 = (pts[1] - pts[0]) / L1
    d2 = (pts[2] - pts[1]) / max(L - L1, 1e-6)
    for i, (x, y, zz) in enumerate(V):
        if zz <= L1:
            base, d, t = pts[0], d1, zz
        else:
            base, d, t = pts[1], d2, zz - L1
        # local frame: d = along, side axis ~ x, depth ~ y
        up = np.array([0, -1.0, 0])
        xa = np.cross(up, d)
        nx = np.linalg.norm(xa)
        xa = xa / nx if nx > 1e-6 else np.array([1.0, 0, 0])
        ya = np.cross(d, xa)
        out[i] = base + d * t + xa * x - ya * y
    part.V = out
    return part


def tail(b):
    base, light, dark = fur_colors(b)
    names = tail_bones(b)
    pts = tail_points(b)
    sp = b.species
    if sp in ("hamster", "hare"):
        c = light if sp == "hare" else base
        r = b.tail_r
        p = geo.qsphere(r, 4, c).tf(pts[0] + np.array([0, r * 0.6, 0.0]))
        if sp == "hare":
            p.deform(lambda V: V + 0.004 * np.sin(V * 120))
        return [p.on(names[0])]
    curve = np.array([pts[0] + (pts[-1] - pts[0]) * 0] + [])
    dense = []
    for i in range(len(pts) - 1):
        for t in np.linspace(0, 1, 4, endpoint=False):
            dense.append(pts[i] * (1 - t) + pts[i + 1] * t)
    dense.append(pts[-1])
    dense = np.array(dense)
    # smooth the polyline
    for _ in range(2):
        dense[1:-1] = (dense[:-2] + dense[1:-1] * 2 + dense[2:]) / 4
    n = len(dense)
    t = np.linspace(0, 1, n)
    if sp == "rat":
        radii = b.tail_r * (1 - 0.85 * t)
        c = "#d9a3a0"
    elif sp == "dog":
        radii = b.tail_r * (0.9 + 0.5 * np.sin(np.pi * t) ** 0.8) * (1 - 0.6 * t ** 3)
        c = base
    else:
        radii = b.tail_r * (1 - 0.25 * t) * (1 - 0.8 * t ** 6)
        c = base
    radii[-1] = max(radii[-1] * 0.3, 0.004)
    p = geo.tube(dense, radii, 10, color=c)
    if sp == "cat":
        tipc = dark if b.fur != "siamese" else dark
        p.paint(geo.grad_z(c, c, 0, 1))
        if b.fur in ("ginger", "grey_tabby"):
            p.paint(geo.stripes(dark, axis=2, freq=48, width=0.3))
        if b.fur == "siamese":
            p.paint(lambda V, C: C * 0 + palette.rgb(dark))
    if sp == "dog" and b.extras.get("dog") == "beagle":
        p.paint(geo.patch(dense[-1], 0.08, "#f6f0e6", 0.5))
    chain_weights(p, names, pts)
    return [p]


def fur_body(b, sleeve=None, pants=None, paw=None, boots=None, skip=()):
    def tag(ps, g):
        for p in ps:
            if p.group is None:
                p.group = g
        return ps
    parts = []
    if "torso" not in skip:
        parts += tag(torso(b), "fur.torso")
    parts += tag(neck(b), "fur.torso")
    if "head" not in skip:
        parts += tag(head(b), "fur.head")
    if "arms" not in skip:
        parts += tag(arms(b, sleeve, paw), "fur.arms")
    if "legs" not in skip:
        parts += tag(legs(b, pants, boots), "fur.legs")
    if "tail" not in skip:
        parts += tag(tail(b), "fur.tail")
    return parts
