"""Animation library for the shared beast rig.

Each clip is built from a *stance* (how the unit holds its weapon) plus
layered motion: breathing, blinks, ear twitches, tail sway, cape flutter.
Secondary motion uses phase-delayed waves so ears, tails and capes overlap
the main action instead of moving in lockstep with it.
"""
import math

from .anim import Pose, back_out, ease_in, ease_out, keys, seg, smooth, wave
from .beast import tail_bones
import numpy as np
from mathutils import Quaternion, Vector

TAU = 2 * math.pi


class Ctx:
    """Everything a clip needs to know about the unit."""

    def __init__(self, body, style="sword", shield=False, walk="walk", special="groom",
                 posture=0.0, bones=()):
        self.b = body
        self.style = style
        self.shield = shield
        self.walk = walk
        self.special = special
        self.posture = posture          # forward hunch in degrees (rats)
        self.bones = set(bones)
        self.tail = tail_bones(body)
        self.leg = body.hip_h - body.foot_r * 0.9
        self.has_ear_tip = "ear_tip.L" in self.bones


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def crouch(p, c, a):
    """Bend knees by angle a (deg) keeping feet planted under the hips."""
    p.rot("thigh.L", -a).rot("thigh.R", -a)
    p.rot("shin.L", 2 * a).rot("shin.R", 2 * a)
    p.rot("foot.L", -a).rot("foot.R", -a)
    drop = c.leg * (1 - math.cos(math.radians(a)))
    p.move("hips", z=-drop)
    return p


def stance(c, p=None, k=1.0):
    """Ready pose for the unit's weapon style (k scales intensity)."""
    p = p or Pose()
    s = c.style
    p.rot("chest", c.posture * 0.8).rot("neck", -c.posture * 0.5).rot("head", -c.posture * 0.3)
    # relaxed defaults
    arm = {"upper_arm.L": (-8, 0, 16), "forearm.L": (-22, 0, 0),
           "upper_arm.R": (-8, 0, -16), "forearm.R": (-22, 0, 0)}
    if s in ("sword", "mace", "sabre"):
        arm["upper_arm.R"] = (-18, -8, -14)
        arm["forearm.R"] = (-62, 0, 0)
        arm["hand.R"] = (10, 0, 0)
    elif s == "thrust":
        arm["upper_arm.R"] = (-22, -6, -12)
        arm["forearm.R"] = (-58, 0, 0)
        arm["upper_arm.L"] = (-48, -26, 4)
        arm["forearm.L"] = (-40, -10, 0)
        arm["hand.R"] = (8, 0, 0)
    elif s == "bow":
        arm["upper_arm.L"] = (-28, 6, 10)
        arm["forearm.L"] = (-52, 0, 0)
        arm["hand.L"] = (0, 0, 0)
    elif s == "crossbow":
        arm["upper_arm.R"] = (-14, -10, -8)
        arm["forearm.R"] = (-72, 0, 0)
        arm["upper_arm.L"] = (-34, -28, 4)
        arm["forearm.L"] = (-58, -14, 0)
    elif s == "dagger2":
        arm["upper_arm.R"] = (-18, -10, -16)
        arm["forearm.R"] = (-70, 0, 0)
        arm["upper_arm.L"] = (-18, 10, 16)
        arm["forearm.L"] = (-70, 0, 0)
    elif s == "sling":
        arm["upper_arm.R"] = (-6, 0, -10)
        arm["forearm.R"] = (-30, 0, 0)
    elif s in ("tool", "staff"):
        arm["upper_arm.R"] = (-14, -6, -10)
        arm["forearm.R"] = (-66, 0, 0)
    elif s == "lantern":
        arm["upper_arm.R"] = (-14, -6, -10)
        arm["forearm.R"] = (-66, 0, 0)
        arm["upper_arm.L"] = (-20, 0, 8)
        arm["forearm.L"] = (-60, 0, 0)
    if c.shield:
        # shield carried at the side, face out: keeps the body readable
        arm["upper_arm.L"] = (-8, 0, 20)
        arm["forearm.L"] = (-30, 0, 0)
    for bone, (pp, yy, rr) in arm.items():
        p.rot(bone, pp * k, yy * k, rr * k)
    if s in ("sword", "thrust", "dagger2", "mace", "sabre"):
        # battle-ready: knees bent, wide stance, chest forward, glare from under the brows
        crouch(p, c, 13 * k)
        p.rot("thigh.L", 0, 4 * k, 6 * k).rot("thigh.R", 0, -4 * k, -6 * k)
        p.rot("foot.L", 0, 4 * k, -6 * k).rot("foot.R", 0, -4 * k, 6 * k)
        p.rot("chest", 7 * k).rot("head", -8 * k)
    elif s in ("bow", "crossbow", "sling", "lantern", "staff"):
        crouch(p, c, 6 * k)
        p.rot("thigh.L", 0, 3 * k, 4 * k).rot("thigh.R", 0, -3 * k, -4 * k)
        p.rot("chest", 3 * k).rot("head", -4 * k)
    return p


def _qrot(a, b):
    """Minimal rotation taking direction a to direction b."""
    a, b = Vector(a).normalized(), Vector(b).normalized()
    return a.rotation_difference(b)


def arm_ik(p, c, side, target, pole=(0.0, 0.6, -0.4), blade=None):
    """Two-bone IK for an arm, in the chest's rest frame (world axes, metres).

    target: wrist position relative to the shoulder joint. pole: where the elbow
    should point. blade: desired weapon direction (weapons rest pointing -Y).
    Writes explicit quaternions for upper_arm, forearm and hand.
    """
    j = c.b.joints()
    S, E0, W0 = (Vector(j[f"{k}.{side}"]) for k in ("shoulder", "elbow", "wrist"))
    L1, L2 = (E0 - S).length, (W0 - E0).length
    T = Vector(target)
    d = min(max(T.length, abs(L1 - L2) + 1e-3), (L1 + L2) * 0.999)
    dirT = T.normalized()
    cos_a = (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)
    a = math.acos(min(max(cos_a, -1.0), 1.0))
    pole_v = Vector(pole)
    perp = (pole_v - dirT * pole_v.dot(dirT))
    if perp.length < 1e-6:
        perp = Vector((0, 0, -1)) - dirT * (-dirT.z)
    perp.normalize()
    elbow = dirT * (L1 * math.cos(a)) + perp * (L1 * math.sin(a))
    wrist = dirT * d
    u0 = (E0 - S).normalized()
    f0 = (W0 - E0).normalized()
    q1 = _qrot(u0, elbow)
    q2 = _qrot(q1 @ f0, (wrist - elbow).normalized())
    p.q[f"upper_arm.{side}"] = q1
    p.q[f"forearm.{side}"] = q1.inverted() @ q2 @ q1   # expressed in the arm's rest axes
    # combined forearm world rotation = q2 @ q1
    if blade is not None:
        qa = q2 @ q1
        w0 = Vector((0, -1, 0))
        qh = _qrot(qa @ w0, Vector(blade))
        local = qa.inverted() @ qh @ qa
        lim = math.radians(38)              # wrists don't fold into the vambrace
        if local.angle > lim:
            local = Quaternion().slerp(local, lim / local.angle)
        p.q[f"hand.{side}"] = local
    return p


def blend_fk_ik(p, side, w, bones=("upper_arm", "forearm", "hand")):
    """Slerp each arm bone between its FK stance angles and the IK quaternion."""
    from .anim import _world_quat
    for b in bones:
        name = f"{b}.{side}"
        if name not in p.q:
            continue
        fk = _world_quat(*p.get(name, (0.0, 0.0, 0.0)))
        p.q[name] = fk.slerp(p.q[name], w)
    return p


def lerp3(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def secondary(p, c, t, cycles=1, energy=1.0, ear_lag=0.12):
    """Tails, ears, cape: phase-delayed overlapping motion."""
    te = min(energy, 1.0)          # tails never whip into gear
    for i, tb in enumerate(c.tail):
        amp = (6 + 3 * i) * te
        p.rot(tb, 3 * te * wave(t, cycles, -0.1 * i), amp * wave(t, cycles, 0.25 - 0.13 * i), 0)
    for s in ("L", "R"):
        sgn = 1 if s == "L" else -1
        p.rot(f"ear.{s}", 2.5 * energy * wave(t, cycles * 2, -ear_lag), 0, -sgn * 1.5 * energy * wave(t, cycles, 0.3))
        if c.has_ear_tip:
            p.rot(f"ear_tip.{s}", 6 * energy * wave(t, cycles * 2, -ear_lag - 0.15), 0, 0)
    p.rot("cape", 4 + 3 * energy * wave(t, cycles * 2, -0.15))
    p.rot("cape_tip", 4 + 4 * energy * wave(t, cycles * 2, -0.3))
    return p


def blink(p, t, at, dur=0.07):
    """Close both eyes around time 'at' (fraction of the clip)."""
    d = abs(t - at)
    if d < dur:
        k = 1 - d / dur
        s = 1 - 0.92 * smooth(k * 1.4)
        p.size("eye.L", 1, 1, s).size("eye.R", 1, 1, s)
    return p


def eyes_closed(p, amount=1.0):
    s = 1 - 0.9 * amount
    return p.size("eye.L", 1, 1, s).size("eye.R", 1, 1, s)


# ---------------------------------------------------------------------------
# Clips
# ---------------------------------------------------------------------------

def idle(c):
    def fn(t):
        p = stance(c)
        br = wave(t, 1)
        p.rot("chest", 1.6 * br).rot("neck", -0.6 * br).rot("head", 1.2 * wave(t, 1, 0.15))
        p.move("hips", z=0.003 * wave(t, 1, -0.1))
        p.rot("upper_arm.L", -1.5 * br, 0, 1.2 * br).rot("upper_arm.R", -1.5 * br, 0, -1.2 * br)
        p.rot("head", 0, 6 * math.sin(TAU * t) * smooth(seg(t, 0.1, 0.4)) * (1 - smooth(seg(t, 0.6, 0.9))))
        secondary(p, c, t, 1, 0.8)
        # ear twitch
        tw = seg(t, 0.45, 0.53)
        if 0 < tw < 1:
            p.rot("ear.L", 14 * math.sin(math.pi * tw) * math.sin(TAU * 2 * tw), 0, -8 * math.sin(math.pi * tw))
        blink(p, t, 0.78)
        return p
    return ("Idle", 72, True, fn)


def idle_special(c):
    sp = c.special

    def fn(t):
        p = stance(c)
        e = smooth(seg(t, 0.0, 0.18)) * (1 - smooth(seg(t, 0.8, 1.0)))
        if sp == "groom":       # cat licks its paw then wipes its ear
            lick = math.sin(TAU * 4 * t) * 0.5 + 0.5
            p.rot("upper_arm.L", -46 * e, -16 * e, 2 * e).rot("forearm.L", -62 * e, -12 * e, 0)
            p.rot("hand.L", -20 * e, 0, 0)
            p.rot("head", 8 * e + 4 * e * lick, -18 * e, 8 * e).rot("neck", 4 * e)
            eyes_closed(p, e * 0.9)
            p.rot("jaw", 8 * e * lick)
        elif sp == "sniff":     # dog sniffs the ground and wags hard
            sn = math.sin(TAU * 6 * t)
            p.rot("chest", 16 * e).rot("neck", 14 * e).rot("head", 10 * e + 3 * e * sn)
            crouch(p, c, 10 * e)
            for i, tb in enumerate(c.tail):
                p.rot(tb, 10 * e, 30 * e * math.sin(TAU * 8 * t - i * 0.7), 0)
        elif sp == "stuff":     # hamster stuffs its cheeks
            chew = math.sin(TAU * 5 * t)
            p.rot("upper_arm.L", -34 * e, -12 * e, 12 * e).rot("forearm.L", -58 * e, -14 * e, 0)
            p.rot("upper_arm.R", -34 * e, 12 * e, -12 * e).rot("forearm.R", -58 * e, 14 * e, 0)
            p.rot("head", -6 * e)
            puff = 1 + 0.35 * smooth(seg(t, 0.25, 0.55)) * (1 - smooth(seg(t, 0.8, 1.0))) + 0.04 * chew * e
            p.size("cheeks", puff, puff, puff)
            p.rot("jaw", 6 * e * (chew * 0.5 + 0.5))
            eyes_closed(p, 0.6 * smooth(seg(t, 0.4, 0.5)) * (1 - smooth(seg(t, 0.7, 0.8))))
        elif sp == "thump":     # hare ears swivel, foot thumps twice
            for s, ph in (("L", 0.0), ("R", 0.2)):
                p.rot(f"ear.{s}", 0, 25 * e * math.sin(TAU * 1.5 * t + ph), 0)
            for at in (0.45, 0.6):
                k = seg(t, at - 0.06, at)
                if 0 < k < 1:
                    up = math.sin(math.pi * k)
                    p.rot("thigh.R", -20 * up).rot("shin.R", 30 * up).rot("foot.R", -10 * up)
            p.rot("head", 0, 15 * math.sin(TAU * t) * e)
        elif sp == "scheme":    # rat rubs its paws together
            rub = math.sin(TAU * 6 * t)
            p.rot("upper_arm.L", -24 * e, -10 * e, 12 * e).rot("forearm.L", -46 * e, -24 * e + 6 * rub * e, 0)
            p.rot("upper_arm.R", -24 * e, 10 * e, -12 * e).rot("forearm.R", -46 * e, 24 * e + 6 * rub * e, 0)
            p.rot("head", 0, 20 * math.sin(TAU * 1.5 * t) * e)
            p.rot("chest", 8 * e)
        elif sp == "flourish":  # armoured: wrist circles with the weapon, shoulder roll, glare
            spin = TAU * 2 * smooth(seg(t, 0.15, 0.75))
            p.rot("forearm.R", -8 * e)
            p.rot("hand.R", 18 * e * math.sin(spin), 0, 24 * e * math.cos(spin))
            p.rot("chest", 0, 10 * e * math.sin(TAU * t), 0).rot("head", -4 * e, -14 * e * math.sin(TAU * t))
            roll = math.sin(math.pi * seg(t, 0.75, 0.95))
            p.rot("upper_arm.L", 0, 0, 6 * roll).rot("upper_arm.R", 0, 0, -6 * roll)
        elif sp == "proud":     # hero: chin up, chest out, slow look across the field
            p.rot("chest", -6 * e).rot("head", -8 * e, 14 * math.sin(TAU * t) * e)
            p.rot("upper_arm.L", 0, 0, 6 * e).rot("upper_arm.R", 0, 0, -6 * e)
        secondary(p, c, t, 1, 0.9)
        if sp not in ("groom",):
            blink(p, t, 0.3)
        return p
    return ("IdleSpecial", 120, True, fn)


def walk(c):
    kind = c.walk
    if kind == "hop":
        return hop(c)
    A = {"walk": 26, "waddle": 18, "skitter": 22, "prowl": 24, "march": 28}[kind]
    frames = {"walk": 26, "waddle": 18, "skitter": 18, "prowl": 30, "march": 26}[kind]

    def fn(t):
        p = stance(c, k=0.75)
        ph = TAU * t
        cp, sp = math.cos(ph), math.sin(ph)
        # legs: left forward at t=0
        p.rot("thigh.L", -A * cp).rot("thigh.R", A * cp)
        swingL = max(0.0, -sp)
        swingR = max(0.0, sp)
        p.rot("shin.L", 44 * swingL ** 1.2 + 6).rot("shin.R", 44 * swingR ** 1.2 + 6)
        p.rot("foot.L", -0.3 * (-A * cp) - 12 * swingL)
        p.rot("foot.R", -0.3 * (A * cp) - 12 * swingR)
        bob = 0.5 - 0.5 * math.cos(2 * ph)
        p.move("hips", z=0.016 * bob - 0.006)
        sway = {"waddle": 9, "skitter": 3}.get(kind, 4)
        p.rot("hips", 0, 7 * cp, sway * sp)
        p.rot("chest", 4 + (8 if kind == "skitter" else 0), -10 * cp, -sway * 0.7 * sp)
        p.rot("head", -2 * math.cos(2 * ph), 4 * cp, sway * 0.4 * sp)
        # arms swing opposite to legs (weapon arm less)
        free_l = c.style not in ("thrust", "crossbow", "dagger2") and not c.shield and c.style != "bow"
        free_r = c.style in ("sling",) or c.style == "bow"
        if c.style not in ("thrust", "crossbow", "dagger2", "lantern"):
            free_l = True if not c.shield else False
        aw = 26 if kind != "prowl" else 14
        p.rot("upper_arm.L", (aw if free_l else 6) * cp)
        p.rot("upper_arm.R", -(aw if free_r else 8) * cp)
        p.rot("forearm.L", -10 * max(-cp, 0) * (1 if free_l else 0.3))
        p.rot("forearm.R", -10 * max(cp, 0))
        secondary(p, c, t, 2, 1.2)
        if c.walk == "prowl":
            p.rot("chest", 6)
            for i, tb in enumerate(c.tail):
                p.rot(tb, 6, 12 * wave(t, 1, -0.15 * i), 0)
        blink(p, t, 0.62, 0.05)
        return p
    return ("Walk", frames, True, fn)


def hop(c):
    def fn(t):
        p = stance(c, k=0.7)
        # 0-0.25 crouch/push, 0.25-0.7 airborne, 0.7-1 land/absorb
        push = smooth(seg(t, 0.0, 0.18)) * (1 - smooth(seg(t, 0.18, 0.3)))
        air = math.sin(math.pi * seg(t, 0.22, 0.72))
        land = math.sin(math.pi * seg(t, 0.68, 1.0))
        p.move("hips", z=0.085 * air)
        crouch(p, c, 22 * push + 18 * land)
        tuck = air
        p.rot("thigh.L", -18 * tuck).rot("thigh.R", -18 * tuck)
        p.rot("shin.L", 30 * tuck).rot("shin.R", 30 * tuck)
        p.rot("foot.L", 25 * tuck - 10).rot("foot.R", 25 * tuck - 10)
        p.rot("chest", 10 * push - 6 * air + 8 * land)
        p.rot("head", -6 * push + 6 * air - 6 * land)
        p.rot("upper_arm.L", 20 * air - 15 * push).rot("upper_arm.R", 20 * air - 15 * push)
        for s in ("L", "R"):
            lag = math.sin(math.pi * seg(t, 0.3, 0.85))
            p.rot(f"ear.{s}", 18 * lag - 6 * push)
            if c.has_ear_tip:
                p.rot(f"ear_tip.{s}", 30 * math.sin(math.pi * seg(t, 0.38, 0.95)))
        p.rot("cape", 10 + 20 * air)
        p.rot("cape_tip", 8 + 20 * math.sin(math.pi * seg(t, 0.3, 0.9)))
        for i, tb in enumerate(c.tail):
            p.rot(tb, 15 * air)
        return p
    return ("Walk", 20, True, fn)


def attack(c):
    s = c.style
    if s in ("sword", "mace", "sabre"):
        return _attack_swing(c, overhead=(s == "mace"))
    if s == "thrust":
        return _attack_thrust(c)
    if s == "bow":
        return _attack_bow(c)
    if s == "crossbow":
        return _attack_crossbow(c)
    if s == "sling":
        return _attack_sling(c)
    if s == "dagger2":
        return _attack_daggers(c)
    if s in ("tool",):
        return _attack_swing(c, overhead=True)
    if s in ("staff", "lantern"):
        return _attack_swing(c, overhead=True)
    return _attack_swing(c)


def key_poses(p, t, kf, ease=smooth):
    """Additive keyframed deltas: kf = [(t, {bone: (pitch, yaw, roll)}, {bone: (x,y,z)}), ...]."""
    if t <= kf[0][0]:
        i0 = i1 = 0
        u = 0.0
    else:
        i0 = len(kf) - 1
        i1 = i0
        u = 0.0
        for i in range(len(kf) - 1):
            if kf[i][0] <= t <= kf[i + 1][0]:
                i0, i1 = i, i + 1
                u = ease((t - kf[i][0]) / max(kf[i + 1][0] - kf[i][0], 1e-9))
                break
    r0, r1 = kf[i0][1], kf[i1][1]
    for bone in set(r0) | set(r1):
        a = r0.get(bone, (0, 0, 0))
        b = r1.get(bone, (0, 0, 0))
        p.rot(bone, *(x + (y - x) * u for x, y in zip(a, b)))
    l0 = kf[i0][2] if len(kf[i0]) > 2 else {}
    l1 = kf[i1][2] if len(kf[i1]) > 2 else {}
    for bone in set(l0) | set(l1):
        a = l0.get(bone, (0, 0, 0))
        b = l1.get(bone, (0, 0, 0))
        p.move(bone, *(x + (y - x) * u for x, y in zip(a, b)))
    return p


def ik_track(t, keys, ease=smooth, bulge=None):
    """Interpolate IK targets [(t, wrist, blade, pole), ...]; optional outward arc."""
    if t <= keys[0][0]:
        k0 = k1 = keys[0]
        u = 0.0
    elif t >= keys[-1][0]:
        k0 = k1 = keys[-1]
        u = 0.0
    else:
        for k0, k1 in zip(keys[:-1], keys[1:]):
            if k0[0] <= t <= k1[0]:
                break
        u = ease((t - k0[0]) / max(k1[0] - k0[0], 1e-9))
    w = lerp3(k0[1], k1[1], u)
    if bulge is not None and k0 is not k1:
        arc = math.sin(math.pi * u)
        w = tuple(x + bx * arc for x, bx in zip(w, bulge))
    bl = lerp3(k0[2], k1[2], u)
    po = lerp3(k0[3], k1[3], u)
    return w, bl, po


def _attack_swing(c, overhead=False):
    """Weapon swing driven by IK targets for the right arm (clean, readable arcs)."""
    if overhead:
        ready = ((-0.05, -0.22, -0.26), (-0.05, -0.45, 0.9), (-0.7, 0.4, -0.5))
        wind = ((-0.1, 0.02, 0.22), (-0.15, 0.4, 0.9), (-0.9, 0.2, -0.1))
        hit = ((-0.02, -0.37, -0.18), (0.05, -0.75, -0.55), (-0.7, 0.3, -0.6))
        follow = ((0.0, -0.32, -0.26), (0.1, -0.6, -0.7), (-0.7, 0.3, -0.6))
        body = {"wind": {"chest": (-14, -8, 0), "head": (-6, 0, 0), "hips": (0, -6, 0)},
                "hit": {"chest": (24, 6, 0), "head": (8, 0, 0), "hips": (6, 6, 0)}}
    else:
        ready = ((-0.06, -0.24, -0.28), (-0.1, -0.45, 0.9), (-0.6, 0.4, -0.4))
        wind = ((-0.37, 0.05, 0.17), (-0.35, 0.4, 0.85), (-0.85, 0.25, -0.35))
        hit = ((-0.02, -0.42, -0.12), (0.25, -0.88, -0.38), (-0.8, 0.2, -0.4))
        follow = ((-0.1, -0.4, -0.12), (0.3, -0.8, -0.45), (-0.8, 0.2, -0.4))
        body = {"wind": {"chest": (-8, -16, -4), "head": (-6, 10, 0), "hips": (0, -10, 0)},
                "hit": {"chest": (16, 14, 4), "head": (6, -8, 0), "hips": (4, 10, 0)}}
    legs_hit = {"thigh.L": (-22, 0, 0), "shin.L": (22, 0, 0), "thigh.R": (14, 0, 0), "shin.R": (12, 0, 0),
                "jaw": (18, 0, 0), "upper_arm.L": (10, 0, 0)}
    kf = [
        (0.0, {}, {}),
        (0.30, body["wind"], {"hips": (0, 0.015, -0.01)}),
        (0.36, body["wind"], {"hips": (0, 0.015, -0.012)}),
        (0.45, dict(body["hit"], **legs_hit), {"hips": (0, -0.05, -0.025)}),
        (0.56, dict(body["hit"], **legs_hit), {"hips": (0, -0.05, -0.025)}),
        (1.0, {}, {}),
    ]
    track = [(0.0, *ready), (0.30, *wind), (0.36, *wind), (0.45, *hit), (0.56, *follow), (1.0, *ready)]

    def fn(t):
        p = stance(c)
        key_poses(p, t, kf)
        if t < 0.30:
            bul = (-0.22, -0.06, 0.0)          # rise out to the side, clear of the pauldron
        elif 0.36 <= t <= 0.45:
            bul = (-0.14, -0.1, 0.0)           # strike arcs outward, away from the face
        elif t > 0.56:
            bul = (-0.12, -0.04, 0.0)          # recover outside the belt line
        else:
            bul = None
        w, bl, po = ik_track(t, track, bulge=bul)
        arm_ik(p, c, "R", w, po, bl)
        blend_fk_ik(p, "R", smooth(seg(t, 0.0, 0.18)) * (1 - smooth(seg(t, 0.8, 1.0))))
        b = math.sin(math.pi * seg(t, 0.4, 0.75))
        secondary(p, c, t, 1, 0.8 + 0.6 * b)
        p.rot("cape", 14 * b).rot("cape_tip", 18 * b)
        return p
    return ("Attack", 30, False, fn)


def _attack_thrust(c):
    """Two-handed polearm jab via IK: rear hand on the butt, front hand on the shaft."""
    ready = ((-0.2, -0.12, -0.32), (0.0, -0.95, 0.3))
    pull = ((-0.24, 0.06, -0.3), (0.0, -0.97, 0.22))
    jab = ((-0.16, -0.36, -0.22), (0.0, -0.99, 0.1))

    def fn(t):
        p = stance(c)
        a = smooth(seg(t, 0.0, 0.32))
        j = ease_out(seg(t, 0.34, 0.46))
        r = smooth(seg(t, 0.6, 1.0))
        if t < 0.34:
            w, bl = lerp3(ready[0], pull[0], a), lerp3(ready[1], pull[1], a)
        elif t < 0.6:
            w, bl = lerp3(pull[0], jab[0], j), lerp3(pull[1], jab[1], j)
        else:
            w, bl = lerp3(jab[0], ready[0], r), lerp3(jab[1], ready[1], r)
        arm_ik(p, c, "R", w, (-0.8, 0.3, -0.5), bl)
        k = smooth(seg(t, 0.0, 0.15)) * (1 - smooth(seg(t, 0.85, 1.0)))
        blend_fk_ik(p, "R", k)
        if not c.shield:
            # front hand grips the shaft ~0.26 m ahead of the rear hand (mirror shoulder frame)
            j_ = c.b.joints()
            off = np.array(j_["shoulder.R"]) - np.array(j_["shoulder.L"])
            front = np.array(w) + np.array(bl) / np.linalg.norm(bl) * 0.26 + off
            arm_ik(p, c, "L", tuple(front), (0.8, 0.3, -0.5), None)
            blend_fk_ik(p, "L", k)
        b_ = j * (1 - r)
        p.rot("chest", -6 * a * (1 - j) + 12 * b_, 10 * a * (1 - j) - 8 * b_)
        st = math.sin(math.pi * seg(t, 0.28, 0.9))
        p.rot("thigh.L", -22 * st).rot("shin.L", 20 * st).rot("thigh.R", 14 * st).rot("shin.R", 8 * st)
        p.move("hips", y=-0.04 * st, z=-0.015 * st)
        secondary(p, c, t, 1, 0.8 + 0.5 * b_)
        if 0.34 < t < 0.6:
            p.rot("jaw", 14 * math.sin(math.pi * seg(t, 0.34, 0.6)))
        return p
    return ("Attack", 30, False, fn)


def _attack_bow(c):
    def fn(t):
        p = stance(c)
        aim = smooth(seg(t, 0.0, 0.2)) * (1 - smooth(seg(t, 0.85, 1.0)))
        draw = smooth(seg(t, 0.15, 0.5))
        release = ease_out(seg(t, 0.6, 0.66))
        p.rot("chest", 0, 18 * aim)
        p.rot("head", 0, -14 * aim)
        p.rot("upper_arm.L", -58 * aim, -20 * aim, 0).rot("forearm.L", 40 * aim)
        d = draw * (1 - release)
        p.rot("upper_arm.R", -70 * aim + 10 * d, -40 * aim - 10 * d, 0)
        p.rot("forearm.R", -60 * aim - 50 * d + 30 * release * aim)
        p.rot("hand.R", 0, 0, 0)
        kick = math.sin(math.pi * seg(t, 0.6, 0.78))
        p.rot("chest", -4 * kick)
        p.rot("upper_arm.R", 0, 0, -20 * kick)
        secondary(p, c, t, 1, 0.8)
        return p
    return ("Attack", 36, False, fn)


def _attack_crossbow(c):
    def fn(t):
        p = stance(c)
        raise_ = smooth(seg(t, 0.0, 0.25)) * (1 - smooth(seg(t, 0.75, 1.0)))
        fire = math.sin(math.pi * seg(t, 0.45, 0.62))
        p.rot("upper_arm.R", -55 * raise_, 0, 0).rot("forearm.R", -10 * raise_)
        p.rot("upper_arm.L", -40 * raise_).rot("forearm.L", 5 * raise_)
        p.rot("head", 8 * raise_, 0, 6 * raise_)
        p.rot("chest", -8 * fire).rot("upper_arm.R", 12 * fire).rot("upper_arm.L", 12 * fire)
        p.move("hips", y=0.02 * fire)
        secondary(p, c, t, 1, 0.8 + fire)
        return p
    return ("Attack", 36, False, fn)


def _attack_sling(c):
    def fn(t):
        p = stance(c)
        spin = seg(t, 0.05, 0.55)
        ang = TAU * 1.5 * ease_in(spin) * 1.0
        up = smooth(seg(t, 0.0, 0.15)) * (1 - smooth(seg(t, 0.55, 0.65)))
        p.rot("upper_arm.R", -15 * up, 0, -125 * up)
        p.rot("forearm.R", 30 * math.sin(ang) * up, 0, -20 * up + 30 * math.cos(ang) * up)
        throw = ease_out(seg(t, 0.55, 0.68)) * (1 - smooth(seg(t, 0.75, 1.0)))
        p.rot("upper_arm.R", -60 * throw, 0, 0).rot("forearm.R", 20 * throw)
        p.rot("chest", -6 * up + 14 * throw, 14 * up - 18 * throw)
        st = math.sin(math.pi * seg(t, 0.45, 0.95))
        p.rot("thigh.L", -18 * st).rot("shin.L", 14 * st)
        secondary(p, c, t, 1, 1.0)
        return p
    return ("Attack", 36, False, fn)


def _attack_daggers(c):
    def fn(t):
        p = stance(c)
        for side, t0 in (("R", 0.12), ("L", 0.45)):
            sgn = 1 if side == "L" else -1
            w = smooth(seg(t, t0 - 0.12, t0)) * (1 - ease_out(seg(t, t0 + 0.02, t0 + 0.1)))
            s = ease_out(seg(t, t0 + 0.02, t0 + 0.1)) * (1 - smooth(seg(t, t0 + 0.18, t0 + 0.4)))
            p.rot(f"upper_arm.{side}", 25 * w - 70 * s, sgn * (-20 * s), 0)
            p.rot(f"forearm.{side}", -40 * w + 55 * s)
            p.rot("chest", 0, sgn * (10 * w - 16 * s))
        lunge = math.sin(math.pi * seg(t, 0.0, 0.85))
        crouch(p, c, 14 * lunge)
        p.rot("thigh.L", -14 * lunge).rot("chest", 14 * lunge)
        p.move("hips", y=-0.05 * lunge)
        secondary(p, c, t, 1, 1.2)
        return p
    return ("Attack", 30, False, fn)


def _attack_staff(c):
    def fn(t):
        p = stance(c)
        lift = smooth(seg(t, 0.0, 0.35)) * (1 - ease_out(seg(t, 0.4, 0.55)))
        slam = ease_out(seg(t, 0.4, 0.55)) * (1 - smooth(seg(t, 0.7, 1.0)))
        p.rot("upper_arm.R", -20 * lift - 60 * slam, 0, -110 * lift)
        p.rot("hand.R", 40 * lift)
        p.rot("forearm.R", -30 * lift + 10 * slam)
        p.rot("chest", -12 * lift + 16 * slam)
        p.rot("head", -12 * lift + 8 * slam)
        p.rot("upper_arm.L", -40 * lift, 0, 30 * lift)
        secondary(p, c, t, 1, 1.0)
        return p
    return ("Attack", 34, False, fn)


def cast(c):
    """Hero cast: weapon raised to the side, then thrust forward (IK, clear of the head)."""
    def fn(t):
        p = stance(c)
        up = smooth(seg(t, 0.0, 0.3)) * (1 - smooth(seg(t, 0.75, 1.0)))
        point = ease_out(seg(t, 0.45, 0.6)) * (1 - smooth(seg(t, 0.75, 1.0)))
        raise_ = ((-0.36, -0.08, 0.12), (-0.2, -0.2, 1.0), (-0.8, 0.3, -0.3))
        thrust = ((-0.12, -0.42, -0.02), (0.05, -1.0, 0.1), (-0.8, 0.3, -0.4))
        w = lerp3(raise_[0], thrust[0], point)
        bl = lerp3(raise_[1], thrust[1], point)
        po = lerp3(raise_[2], thrust[2], point)
        arm_ik(p, c, "R", w, po, bl)
        blend_fk_ik(p, "R", up)
        if not c.shield:
            arm_ik(p, c, "L", (0.3, -0.25, -0.05), (0.8, 0.3, -0.4), (0.2, -0.6, 0.6))
            blend_fk_ik(p, "L", up * 0.8)
        p.rot("chest", -10 * up + 14 * point).rot("head", -8 * up + 8 * point)
        p.move("hips", z=0.02 * up * (1 - point))
        secondary(p, c, t, 1, 1.0)
        p.rot("cape", 10 * up).rot("cape_tip", 12 * up)
        return p
    return ("Cast", 40, False, fn)


def work(c):
    """Gathering loop: chop / mine / dig in front (IK keeps the tool clear of head and ears)."""
    up_t = ((-0.3, -0.05, 0.1), (-0.2, 0.2, 1.0), (-0.85, 0.2, -0.2))
    down_t = ((-0.08, -0.4, -0.3), (0.0, -0.6, -0.8), (-0.8, 0.2, -0.5))

    def fn(t):
        p = stance(c)
        lift = smooth(seg(t, 0.0, 0.45))
        hit = ease_in(seg(t, 0.45, 0.58))
        back = smooth(seg(t, 0.62, 1.0))
        u = lift * (1 - hit)
        u = u if t < 0.62 else back * 0.0
        k = (1 - hit) * lift if t < 0.6 else 0.0
        w = lerp3(down_t[0], up_t[0], k)
        bl = lerp3(down_t[1], up_t[1], k)
        po = lerp3(down_t[2], up_t[2], k)
        bul = (-0.15, -0.05, 0) if t < 0.45 else None
        if bul:
            w = tuple(x + bx * math.sin(math.pi * lift) for x, bx in zip(w, bul))
        arm_ik(p, c, "R", w, po, bl)
        arm_ik(p, c, "L", (0.18, -0.36, -0.2 + 0.25 * k), (0.8, 0.3, -0.4), None)
        p.rot("chest", -6 * k + 16 * hit * (1 - back)).rot("head", 10 - 6 * k)
        crouch(p, c, 10 + 8 * hit * (1 - back))
        secondary(p, c, t, 1, 0.8)
        jolt = math.sin(math.pi * seg(t, 0.56, 0.7))
        p.rot("ear.L", 10 * jolt).rot("ear.R", 10 * jolt)
        return p
    return ("Work", 30, True, fn)


def hit(c):
    def fn(t):
        p = stance(c)
        k = ease_out(seg(t, 0.0, 0.25)) * (1 - smooth(seg(t, 0.3, 1.0)))
        p.rot("chest", -16 * k, 0, 6 * k).rot("head", -14 * k, 0, -6 * k)
        p.move("hips", y=0.03 * k)
        p.rot("upper_arm.L", -6 * k, 0, 9 * k).rot("upper_arm.R", -6 * k, 0, -9 * k)
        eyes_closed(p, 0.8 * k)
        for s in ("L", "R"):
            p.rot(f"ear.{s}", 25 * k)
        secondary(p, c, t, 1, 0.5 + 2 * k)
        return p
    return ("Hit", 14, False, fn)


def death(c):
    def fn(t):
        p = stance(c, k=1 - smooth(seg(t, 0.0, 0.2)))
        stag = math.sin(math.pi * seg(t, 0.0, 0.3))
        fall = ease_in(seg(t, 0.25, 0.62))
        settle = math.sin(math.pi * seg(t, 0.62, 0.78))
        p.rot("chest", -12 * stag - 10 * fall).rot("head", -18 * stag + 10 * fall, 0, 18 * fall)
        p.rot("hips", -84 * fall - 5 * settle)
        lie = c.b.torso_d * 0.5 + 0.02
        p.move("hips", y=0.06 * stag + (c.b.hip_h * 0.9) * fall, z=-(c.b.hip_h - lie) * fall + 0.02 * settle)
        # fall back, arms flung wide, legs straight and apart (nothing folds into armour)
        wide = smooth(seg(t, 0.0, 0.3))          # arms swing out at once, clear of belt and skirt
        legs = max(fall, 0.5 * stag)
        p.rot("thigh.L", -24 * fall, 0, 16 * legs).rot("thigh.R", -18 * fall, 0, -16 * legs)
        p.rot("shin.L", 3 * fall).rot("shin.R", 5 * fall)
        p.rot("upper_arm.L", -14 * wide, 0, 38 * wide).rot("upper_arm.R", -14 * wide, 0, -40 * wide)
        p.rot("forearm.L", -6 * wide).rot("forearm.R", -8 * wide)
        for i, tb in enumerate(c.tail):
            p.rot(tb, -10 * fall, 10 * fall * (1 if i % 2 else -1))
        for s in ("L", "R"):
            p.rot(f"ear.{s}", 25 * fall, 0, 0)
        p.rot("cape", -12 * fall)
        eyes_closed(p, smooth(seg(t, 0.5, 0.6)))
        p.rot("jaw", 12 * smooth(seg(t, 0.55, 0.7)))
        return p
    return ("Death", 42, False, fn)


def victory(c):
    """Weapon thrust to the sky at shoulder height (IK keeps arms clear of the collar)."""
    def fn(t):
        p = stance(c)
        up = smooth(seg(t, 0.0, 0.2)) * (1 - smooth(seg(t, 0.85, 1.0)))
        jump = math.sin(math.pi * seg(t, 0.15, 0.45)) + 0.6 * math.sin(math.pi * seg(t, 0.5, 0.75))
        shake = 0.03 * math.sin(TAU * 3 * t) * up
        arm_ik(p, c, "R", (-0.32, -0.14, 0.08 + shake), (-0.8, 0.3, -0.3), (-0.25, -0.15, 1.0))
        blend_fk_ik(p, "R", up)
        if not c.shield:
            arm_ik(p, c, "L", (0.3, -0.16, 0.04 - shake), (0.8, 0.3, -0.3), (0.2, -0.3, 1.0))
            blend_fk_ik(p, "L", up)
        p.move("hips", z=0.07 * jump)
        p.rot("thigh.L", -15 * jump).rot("thigh.R", -15 * jump).rot("shin.L", 25 * jump).rot("shin.R", 25 * jump)
        p.rot("chest", -8 * up).rot("head", -7 * up)
        p.rot("jaw", 18 * up)
        secondary(p, c, t, 2, 1.2)
        for i, tb in enumerate(c.tail):
            p.rot(tb, -4 * up, 14 * up * math.sin(TAU * 4 * t - i))
        return p
    return ("Victory", 48, True, fn)


def cloth_follow(p):
    """Tabard rides over whichever thigh is forward (no leg poking through)."""
    lead = min(p.get("thigh.L", (0, 0, 0))[0], p.get("thigh.R", (0, 0, 0))[0], 0.0)
    hips = p.get("hips", (0, 0, 0))[0]
    p.rot("tabard", lead * 1.05 - hips * 0.2)
    p.rot("tabard_tip", lead * 0.25)
    back = max(p.get("thigh.L", (0, 0, 0))[0], p.get("thigh.R", (0, 0, 0))[0], 0.0)
    p.rot("cape", back * 0.8).rot("cape_tip", back * 0.3)
    return p


def _wrap(clip):
    name, frames, loop, fn = clip
    return (name, frames, loop, lambda t: cloth_follow(fn(t)))


def clips_for(c, worker=False, hero=False):
    out = [idle(c), idle_special(c), walk(c), attack(c), hit(c), death(c), victory(c)]
    out = [_wrap(cl) for cl in out]
    if worker:
        out.append(_wrap(work(c)))
    if hero:
        out.append(_wrap(cast(c)))
    return out
