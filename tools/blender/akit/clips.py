"""Animation library for the shared beast rig.

Each clip is built from a *stance* (how the unit holds its weapon) plus
layered motion: breathing, blinks, ear twitches, tail sway, cape flutter.
Secondary motion uses phase-delayed waves so ears, tails and capes overlap
the main action instead of moving in lockstep with it.
"""
import math

from .anim import Pose, back_out, ease_in, ease_out, keys, seg, smooth, wave
from .beast import tail_bones

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
    arm = {"upper_arm.L": (-8, 0, 6), "forearm.L": (-22, 0, 0),
           "upper_arm.R": (-8, 0, -6), "forearm.R": (-22, 0, 0)}
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
        arm["upper_arm.L"] = (-22, -14, 12)
        arm["forearm.L"] = (-68, -10, 0)
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


def secondary(p, c, t, cycles=1, energy=1.0, ear_lag=0.12):
    """Tails, ears, cape: phase-delayed overlapping motion."""
    for i, tb in enumerate(c.tail):
        amp = (7 + 4 * i) * energy
        p.rot(tb, 3 * energy * wave(t, cycles, -0.1 * i), amp * wave(t, cycles, 0.25 - 0.13 * i), 0)
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
            p.rot("upper_arm.L", -62 * e, -28 * e, -6 * e).rot("forearm.L", -82 * e, -20 * e, 0)
            p.rot("hand.L", -30 * e, 0, 0)
            p.rot("head", 14 * e + 6 * e * lick, -14 * e, 8 * e).rot("neck", 6 * e)
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
            p.rot("upper_arm.L", -50 * e, -30 * e, 0).rot("forearm.L", -95 * e, -25 * e, 0)
            p.rot("upper_arm.R", -50 * e, 30 * e, 0).rot("forearm.R", -95 * e, 25 * e, 0)
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
            p.rot("upper_arm.L", -45 * e, -25 * e, 0).rot("forearm.L", -70 * e, -35 * e + 8 * rub * e, 0)
            p.rot("upper_arm.R", -45 * e, 25 * e, 0).rot("forearm.R", -70 * e, 35 * e + 8 * rub * e, 0)
            p.rot("head", 0, 20 * math.sin(TAU * 1.5 * t) * e)
            p.rot("chest", 8 * e)
        elif sp == "proud":     # hero: chin up, chest out, cape sways
            p.rot("chest", -6 * e).rot("head", -10 * e, 12 * math.sin(TAU * t) * e)
            p.rot("upper_arm.L", 0, 0, 20 * e).rot("forearm.L", -100 * e, -40 * e, 0)
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
        p.rot("shin.L", 52 * swingL ** 1.2 + 6).rot("shin.R", 52 * swingR ** 1.2 + 6)
        p.rot("foot.L", -0.5 * (-A * cp) - 22 * swingL + 8 * max(cp, 0) * 0)
        p.rot("foot.R", -0.5 * (A * cp) - 22 * swingR)
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
        return _attack_staff(c)
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


def _attack_swing(c, overhead=False):
    if overhead:
        wind = {"upper_arm.R": (-30, 0, -115), "forearm.R": (-20, 0, -45), "hand.R": (60, 0, 0),
                "chest": (-14, -10, 0), "head": (-8, 0, 0), "hips": (0, -6, 0),
                "upper_arm.L": (-30, 0, 10)}
        hit = {"upper_arm.R": (-70, -10, -6), "forearm.R": (0, 0, 0), "hand.R": (40, 0, 0),
               "chest": (26, 8, 0), "head": (8, 0, 0), "hips": (6, 6, 0),
               "upper_arm.L": (10, 0, 6), "thigh.L": (-26, 0, 0), "shin.L": (26, 0, 0),
               "thigh.R": (16, 0, 0), "shin.R": (12, 0, 0), "jaw": (18, 0, 0)}
        follow = dict(hit, chest=(30, 10, 0), **{"upper_arm.R": (-50, -12, 0), "hand.R": (55, 0, 0)})
        hit_loc = {"hips": (0, -0.05, -0.03)}
    else:
        wind = {"upper_arm.R": (-25, 0, -108), "forearm.R": (-30, 0, -42), "hand.R": (45, 0, 0),
                "chest": (-8, -28, -4), "head": (-6, 14, 0), "hips": (0, -12, 0),
                "upper_arm.L": (-20, -10, 8), "thigh.R": (6, 0, 0)}
        hit = {"upper_arm.R": (-72, -38, -8), "forearm.R": (-6, 0, 0), "hand.R": (52, 0, 10),
               "chest": (16, 34, 4), "head": (6, -12, 0), "hips": (4, 14, 0),
               "upper_arm.L": (12, 10, 4), "thigh.L": (-28, 0, 0), "shin.L": (26, 0, 0),
               "thigh.R": (18, 0, 0), "shin.R": (14, 0, 0), "jaw": (18, 0, 0)}
        follow = dict(hit, chest=(18, 42, 6), **{"upper_arm.R": (-60, -55, 4), "hand.R": (62, 0, 14)})
        hit_loc = {"hips": (0, -0.06, -0.025)}
    kf = [
        (0.0, {}, {}),
        (0.30, wind, {"hips": (0, 0.015, -0.01)}),
        (0.36, wind, {"hips": (0, 0.015, -0.012)}),     # hold - readable anticipation
        (0.45, hit, hit_loc),                             # fast strike (3 frames)
        (0.56, follow, hit_loc),                          # follow-through
        (1.0, {}, {}),
    ]

    def fn(t):
        p = stance(c)
        key_poses(p, t, kf)
        b = math.sin(math.pi * seg(t, 0.4, 0.75))
        secondary(p, c, t, 1, 0.8 + 1.4 * b)
        p.rot("cape", 14 * b).rot("cape_tip", 18 * b)
        return p
    return ("Attack", 30, False, fn)


def _attack_thrust(c):
    def fn(t):
        p = stance(c)
        pull = smooth(seg(t, 0.0, 0.32))
        jab = ease_out(seg(t, 0.34, 0.46))
        rec = smooth(seg(t, 0.6, 1.0))
        a = pull * (1 - jab)
        b = jab * (1 - rec)
        p.rot("upper_arm.R", 20 * a - 35 * b, 0, 0).rot("forearm.R", -25 * a + 30 * b)
        p.rot("upper_arm.L", 15 * a - 35 * b).rot("forearm.L", -10 * a + 25 * b)
        p.rot("chest", -6 * a + 14 * b, 12 * a - 10 * b)
        p.rot("head", -4 * a + 4 * b)
        st = math.sin(math.pi * seg(t, 0.28, 0.9))
        p.rot("thigh.L", -30 * st).rot("shin.L", 28 * st).rot("foot.L", 2 * st)
        p.rot("thigh.R", 18 * st).rot("shin.R", 8 * st)
        p.move("hips", y=-0.05 * st, z=-0.018 * st)
        secondary(p, c, t, 1, 0.8 + b)
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
    def fn(t):
        p = stance(c)
        up = smooth(seg(t, 0.0, 0.3)) * (1 - smooth(seg(t, 0.75, 1.0)))
        point = ease_out(seg(t, 0.45, 0.6)) * (1 - smooth(seg(t, 0.75, 1.0)))
        p.rot("upper_arm.R", -20 * up - 60 * point, 0, -120 * up + 110 * point)
        p.rot("forearm.R", 0, 0, -30 * up + 30 * point).rot("hand.R", 40 * up)
        p.rot("forearm.R", -20 * up)
        p.rot("upper_arm.L", -60 * up - 30 * point, 20 * up, 25 * up)
        p.rot("forearm.L", -10 * up)
        p.rot("chest", -12 * up + 16 * point).rot("head", -14 * up + 10 * point)
        p.move("hips", z=0.02 * up * (1 - point))
        secondary(p, c, t, 1, 1.2)
        p.rot("cape", 18 * up).rot("cape_tip", 20 * up)
        return p
    return ("Cast", 40, False, fn)


def work(c):
    """Gathering loop: chop / mine / dig in front of the unit."""
    def fn(t):
        p = stance(c)
        lift = smooth(seg(t, 0.0, 0.45))
        hit = ease_in(seg(t, 0.45, 0.58))
        a = lift * (1 - hit)
        p.rot("upper_arm.R", -50 + 30 * a - 20 * hit, -10, -10 - 85 * a)
        p.rot("hand.R", 40 * a)
        p.rot("forearm.R", -20 - 30 * a + 40 * hit * (1 - smooth(seg(t, 0.6, 1.0))))
        p.rot("upper_arm.L", -50 - 70 * a + 20 * hit, -30, 10).rot("forearm.L", -40 - 20 * a)
        p.rot("chest", -8 * a + 20 * hit * (1 - smooth(seg(t, 0.6, 1.0))))
        crouch(p, c, 10 + 8 * hit * (1 - smooth(seg(t, 0.6, 1.0))))
        p.rot("head", 12 - 10 * a)
        secondary(p, c, t, 1, 0.8)
        jolt = math.sin(math.pi * seg(t, 0.56, 0.7))
        p.rot("ear.L", 12 * jolt).rot("ear.R", 12 * jolt)
        return p
    return ("Work", 30, True, fn)


def hit(c):
    def fn(t):
        p = stance(c)
        k = ease_out(seg(t, 0.0, 0.25)) * (1 - smooth(seg(t, 0.3, 1.0)))
        p.rot("chest", -16 * k, 0, 6 * k).rot("head", -14 * k, 0, -6 * k)
        p.move("hips", y=0.03 * k)
        p.rot("upper_arm.L", -10 * k, 0, 20 * k).rot("upper_arm.R", -10 * k, 0, -20 * k)
        eyes_closed(p, 0.8 * k)
        for s in ("L", "R"):
            p.rot(f"ear.{s}", 25 * k)
        secondary(p, c, t, 1, 0.5 + 2 * k)
        return p
    return ("Hit", 14, False, fn)


def death(c):
    def fn(t):
        p = stance(c, k=1 - smooth(seg(t, 0.0, 0.4)))
        stag = math.sin(math.pi * seg(t, 0.0, 0.3))
        fall = ease_in(seg(t, 0.25, 0.62))
        settle = math.sin(math.pi * seg(t, 0.62, 0.78))
        p.rot("chest", -12 * stag - 10 * fall).rot("head", -18 * stag + 10 * fall, 0, 18 * fall)
        p.rot("hips", -84 * fall - 5 * settle)
        lie = c.b.torso_d * 0.5 + 0.02
        p.move("hips", y=0.06 * stag + (c.b.hip_h * 0.9) * fall, z=-(c.b.hip_h - lie) * fall + 0.02 * settle)
        p.rot("thigh.L", -70 * fall).rot("thigh.R", -55 * fall).rot("shin.L", 30 * fall).rot("shin.R", 50 * fall)
        p.rot("upper_arm.L", -40 * fall, 0, 55 * fall).rot("upper_arm.R", -50 * fall, 0, -60 * fall)
        p.rot("forearm.L", -20 * fall).rot("forearm.R", -30 * fall)
        for i, tb in enumerate(c.tail):
            p.rot(tb, -20 * fall, 15 * fall * (1 if i % 2 else -1))
        for s in ("L", "R"):
            p.rot(f"ear.{s}", 25 * fall, 0, 0)
        p.rot("cape", -40 * fall)
        eyes_closed(p, smooth(seg(t, 0.5, 0.6)))
        p.rot("jaw", 12 * smooth(seg(t, 0.55, 0.7)))
        return p
    return ("Death", 42, False, fn)


def victory(c):
    def fn(t):
        p = stance(c)
        up = smooth(seg(t, 0.0, 0.2)) * (1 - smooth(seg(t, 0.85, 1.0)))
        jump = math.sin(math.pi * seg(t, 0.15, 0.45)) + 0.6 * math.sin(math.pi * seg(t, 0.5, 0.75))
        p.rot("upper_arm.R", -20 * up, 0, -125 * up).rot("forearm.R", 0, 0, -30 * up).rot("hand.R", 50 * up)
        if not c.shield:
            p.rot("upper_arm.L", -20 * up, 0, 125 * up).rot("forearm.L", 0, 0, 30 * up)
        p.move("hips", z=0.07 * jump)
        p.rot("thigh.L", -15 * jump).rot("thigh.R", -15 * jump).rot("shin.L", 25 * jump).rot("shin.R", 25 * jump)
        p.rot("chest", -10 * up).rot("head", -16 * up)
        p.rot("jaw", 18 * up)
        secondary(p, c, t, 2, 1.5)
        for i, tb in enumerate(c.tail):
            p.rot(tb, 20 * up, 25 * up * math.sin(TAU * 4 * t - i))
        return p
    return ("Victory", 48, True, fn)


def clips_for(c, worker=False, hero=False):
    out = [idle(c), idle_special(c), walk(c), attack(c), hit(c), death(c), victory(c)]
    if worker:
        out.append(work(c))
    if hero:
        out.append(cast(c))
    return out
