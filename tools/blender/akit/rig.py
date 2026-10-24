"""Armature creation and skinning.

All bones are rolled so their local X axis is world +X (character's left),
which keeps pitch rotations consistent across species. Animation code works
in world-axis terms anyway (see anim.py) and converts to bone space.
"""
import bpy
import numpy as np
from mathutils import Vector


def create_armature(name, bones, collection=None):
    """bones: list of (name, head, tail, parent_name_or_None, deform=True)."""
    arm = bpy.data.armatures.new(name + "_rig")
    ob = bpy.data.objects.new(name + "_rig", arm)
    (collection or bpy.context.scene.collection).objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    for spec in bones:
        bname, head, tail, parent = spec[:4]
        deform = spec[4] if len(spec) > 4 else True
        b = eb.new(bname)
        b.head = Vector(head)
        b.tail = Vector(tail)
        d = (b.tail - b.head).normalized()
        x = Vector((1, 0, 0))
        if abs(d.dot(x)) > 0.95:
            x = Vector((0, -1, 0))
        b.align_roll(x.cross(d))
        b.use_deform = deform
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return ob


def bind(mesh_ob, arm_ob):
    mesh_ob.parent = arm_ob
    mod = mesh_ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_ob
    return mod


def blend_weights(part, bone_a, bone_b, z0, z1, axis=2):
    """Smoothly blend a part's skin between two bones along an axis."""
    t = np.clip((part.V[:, axis] - z0) / max(z1 - z0, 1e-6), 0, 1)
    t = t * t * (3 - 2 * t)
    part.weights = {bone_a: 1 - t, bone_b: t}
    part.bone = None
    return part


def chain_weights(part, bones, points):
    """Skin a part (e.g. a tail tube) along a chain of bones.

    points: joint positions (len(bones)+1); each vertex is weighted to the
    nearest segments with a soft falloff.
    """
    P = np.asarray(points, float)
    V = part.V
    W = np.zeros((len(V), len(bones)))
    for i in range(len(bones)):
        a, b = P[i], P[i + 1]
        ab = b - a
        t = np.clip(((V - a) @ ab) / max(ab @ ab, 1e-9), 0, 1)
        d = np.linalg.norm(V - (a + t[:, None] * ab), axis=1)
        W[:, i] = 1.0 / (d + 0.02) ** 4
    W /= W.sum(1, keepdims=True)
    part.weights = {b: W[:, i] for i, b in enumerate(bones)}
    part.bone = None
    return part
