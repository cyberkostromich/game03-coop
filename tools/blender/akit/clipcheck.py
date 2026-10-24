"""Gear interpenetration checker.

Every gear group (shield.L, pauldron.R, helm, breastplate, weapon.R, fur.torso
...) becomes its own skinned object on the unit's rig. For sampled frames of
every animation clip we build BVH trees of the posed meshes and count
intersecting triangle pairs between groups. Designed contacts (a fist around
a grip, ears through helmet holes) are whitelisted; everything else should
read as zero so armour pieces never cut through each other.
"""
import fnmatch
import itertools

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

from . import anim, beast, build, clips, rig, units

WHITELIST = [
    ("fur.head", "helm"), ("fur.ears", "helm"), ("fur.head", "hat"), ("fur.ears", "hat"),
    ("fur.arms", "weapon.*"), ("gauntlet.*", "weapon.*"), ("fur.arms", "gauntlet.*"),
    ("fur.arms", "vambrace.*"), ("fur.arms", "couter.*"), ("fur.arms", "pauldron.*"),
    ("fur.legs", "greave.*"), ("fur.legs", "poleyn.*"), ("fur.legs", "sabaton.*"),
    ("fur.legs", "cuisse.*"), ("fur.head", "fur.ears"), ("fur.torso", "fur.head"),
    ("fur.torso", "fur.arms"), ("fur.torso", "fur.legs"), ("fur.torso", "fur.tail"),
    ("medal", "belt"), ("emblem", "panel"), ("hat", "helm"), ("fur.torso", "gorget"),
    ("fur.head", "gorget"), ("fur.head", "scarf"), ("fur.torso", "scarf"),
    ("fur.torso", "collar"), ("fur.head", "collar"), ("fur.torso", "cape"),
    # arm- and tail-holes: limbs leave clothing through openings
    ("brigandine", "fur.arms"), ("garment", "fur.arms"), ("garment", "fur.tail"),
    ("fur.torso", "garment"),   # waistband seam, hidden under belt and brigandine
]


def _allowed(a, b):
    for x, y in WHITELIST:
        if (fnmatch.fnmatch(a, x) and fnmatch.fnmatch(b, y)) or (fnmatch.fnmatch(a, y) and fnmatch.fnmatch(b, x)):
            return True
    return False


def check(uid, samples=6, clip_names=None, verbose=True):
    build.reset_scene()
    spec = units.build(uid)
    s = spec.body.scale
    groups = {}
    for p in spec.parts:
        p.V = p.V * s
        groups.setdefault(p.group or "misc", []).append(p)
    bones = []
    for bspec in beast.skeleton(spec.body):
        name, head, tail, parent = bspec[:4]
        deform = bspec[4] if len(bspec) > 4 else True
        bones.append((name, np.asarray(head) * s, np.asarray(tail) * s, parent, deform))
    arm = rig.create_armature(uid, bones)
    objs = {}
    for g, ps in groups.items():
        ob = build.parts_to_object(ps, "g_" + g, paint_pass=False)
        rig.bind(ob, arm)
        objs[g] = ob
    c = clips.Ctx(spec.body, spec.style, spec.shield, spec.walk, spec.special, spec.posture,
                  [b.name for b in arm.data.bones])
    clip_list = clips.clips_for(c, spec.worker, spec.hero)
    for name, frames, loop, fn in clip_list:
        anim.bake_clip(arm, name, frames, fn, loop=loop, loc_scale=s)
    from .pipeline import pose_at
    worst = {}
    names = sorted(objs)
    pairs = [(a, b) for a, b in itertools.combinations(names, 2) if not _allowed(a, b)]
    for name, frames, loop, fn in clip_list:
        if clip_names and name not in clip_names:
            continue
        for f in np.linspace(1, frames, samples).astype(int):
            pose_at(arm, name, int(f))
            dg = bpy.context.evaluated_depsgraph_get()
            trees = {g: BVHTree.FromObject(ob, dg, deform=True) for g, ob in objs.items()}
            for a, b in pairs:
                n = len(trees[a].overlap(trees[b]))
                if n and n > worst.get((a, b), (0,))[0]:
                    worst[(a, b)] = (n, name, int(f))
    report = sorted(((v[0], a, b, v[1], v[2]) for (a, b), v in worst.items()), reverse=True)
    if verbose:
        print(f"CLIP {uid}: {len(report)} intersecting pairs")
        for n, a, b, clip, f in report:
            print(f"CLIP   {n:5d}  {a:16s} x {b:16s}  worst in {clip}@{f}")
    return report
