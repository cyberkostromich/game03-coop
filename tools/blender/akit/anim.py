"""Procedural keyframe animation.

A clip is a python function pose(t) -> Pose, t in [0, 1). Rotations are
given per bone in *world axes of the rest pose* (degrees):

    pitch: about +X. Positive tips an upward bone forward (bow / nod),
           a downward bone (arm, leg) swings backward.
    yaw:   about +Z. Positive turns toward the character's left.
    roll:  about the forward axis (-Y). Positive tips an upward bone toward
           the character's right.

Offsets (loc) are world-axis translations in meters (z up, -y forward).
They are converted to bone-local quaternions/locations with the rest
matrix, so the same clip code works for every species' proportions.
"""
import math

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

FPS = 30


class Pose(dict):
    """{bone: (pitch, yaw, roll)} plus .loc {bone: (x, y, z)}, .scale."""

    def __init__(self):
        super().__init__()
        self.loc = {}
        self.scale = {}
        self.q = {}      # explicit world-axis quaternions (from IK); override angles

    def rot(self, bone, pitch=0.0, yaw=0.0, roll=0.0):
        p, y, r = self.get(bone, (0.0, 0.0, 0.0))
        self[bone] = (p + pitch, y + yaw, r + roll)
        return self

    def move(self, bone, x=0.0, y=0.0, z=0.0):
        a = self.loc.get(bone, (0.0, 0.0, 0.0))
        self.loc[bone] = (a[0] + x, a[1] + y, a[2] + z)
        return self

    def size(self, bone, sx=1.0, sy=1.0, sz=1.0):
        self.scale[bone] = (sx, sy, sz)
        return self


# --- easing ---------------------------------------------------------------

def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = min(max(x, 0.0), 1.0)
    return x ** 3


def back_out(x, s=1.7):
    x = min(max(x, 0.0), 1.0) - 1
    return x * x * ((s + 1) * x + s) + 1


def seg(t, a, b):
    """0..1 progress of t within [a, b] (clamped)."""
    return min(max((t - a) / (b - a), 0.0), 1.0)


def keys(t, pts, ease=smooth):
    """Piecewise interpolation through [(t, value), ...] with easing."""
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, v0), (t1, v1) in zip(pts[:-1], pts[1:]):
        if t <= t1:
            u = ease((t - t0) / max(t1 - t0, 1e-9))
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * u for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * u
    return pts[-1][1]


def wave(t, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (t * cycles + phase))


# --- conversion -----------------------------------------------------------

def _world_quat(p, y, r):
    q = Quaternion((1, 0, 0), math.radians(p))
    q = Quaternion((0, -1, 0), math.radians(r)) @ q
    q = Quaternion((0, 0, 1), math.radians(y)) @ q
    return q


def bake_clip(arm_ob, name, frames, pose_fn, step=1, loop=True, loc_scale=1.0):
    """Create an action from a pose function and stash it on an NLA track."""
    ad = arm_ob.animation_data or arm_ob.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    ad.action = act
    rest = {b.name: b.matrix_local.to_3x3() for b in arm_ob.data.bones}
    bones = arm_ob.pose.bones
    animated = set()
    samples = []
    for f in range(0, frames + 1, step):
        t = f / frames
        if loop and f == frames:
            t = 0.0
        samples.append((f, pose_fn(t)))
        animated |= (set(samples[-1][1].keys()) | set(samples[-1][1].loc) | set(samples[-1][1].scale)
                     | set(samples[-1][1].q))
    for f, pose in samples:
        for bname in animated:
            pb = bones.get(bname)
            if pb is None:
                continue
            m = rest[bname]
            mi = m.inverted()
            if bname in pose.q:
                qw = pose.q[bname]
            else:
                p, y, r = pose.get(bname, (0.0, 0.0, 0.0))
                qw = _world_quat(p, y, r)
            ql = (mi @ qw.to_matrix() @ m).to_quaternion()
            pb.rotation_quaternion = ql
            pb.keyframe_insert("rotation_quaternion", frame=f + 1, group=bname)
            if bname in pose.loc:
                lw = Vector(pose.loc.get(bname, (0.0, 0.0, 0.0))) * loc_scale
                pb.location = mi @ lw
                pb.keyframe_insert("location", frame=f + 1, group=bname)
            if bname in pose.scale:
                pb.scale = Vector(pose.scale[bname])
                pb.keyframe_insert("scale", frame=f + 1, group=bname)
    # make sure location/scale channels exist on every sample when used
    _fill_missing(arm_ob, act, samples)
    slot = ad.action_slot
    track = ad.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, 1, act)
    if slot is not None and hasattr(strip, "action_slot"):
        strip.action_slot = slot
    track.mute = True
    ad.action = None
    for pb in bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)
    return act


def _fill_missing(arm_ob, act, samples):
    """Bones that only have loc/scale on some frames get explicit rest keys."""
    bones = arm_ob.pose.bones
    loc_bones = set()
    scale_bones = set()
    for _, pose in samples:
        loc_bones |= set(pose.loc)
        scale_bones |= set(pose.scale)
    for f, pose in samples:
        for b in loc_bones:
            if b in pose.loc or b not in bones:
                continue
            bones[b].location = (0, 0, 0)
            bones[b].keyframe_insert("location", frame=f + 1, group=b)
        for b in scale_bones:
            if b in pose.scale or b not in bones:
                continue
            bones[b].scale = (1, 1, 1)
            bones[b].keyframe_insert("scale", frame=f + 1, group=b)
