"""Unit build pipeline: parts -> mesh -> AO bake -> rig -> clips -> GLB."""
import json
import math
import os

import bpy
import numpy as np

from . import anim, beast, build, clips, palette, render, rig, units


def assemble(uid, team=None):
    """Build a unit into the current scene. Returns (spec, mesh_ob, arm_ob)."""
    spec = units.build(uid)
    s = spec.body.scale
    tint = team or palette.FACTIONS[spec.faction]["team"]
    parts = spec.parts
    for p in parts:
        p.V = p.V * s
    ob = build.parts_to_object(parts, uid, team=tint)
    build.bake_ao(ob, strength=0.7, distance=0.22 * s, samples=32)
    bones = []
    for bspec in beast.skeleton(spec.body):
        name, head, tail, parent = bspec[:4]
        deform = bspec[4] if len(bspec) > 4 else True
        bones.append((name, np.asarray(head) * s, np.asarray(tail) * s, parent, deform))
    arm = rig.create_armature(uid, bones)
    # remove bones no part is skinned to (keeps rigs light), except core ones
    rig.bind(ob, arm)
    return spec, ob, arm


def bake_clips(spec, arm):
    c = clips.Ctx(spec.body, spec.style, spec.shield, spec.walk, spec.special, spec.posture,
                  [b.name for b in arm.data.bones])
    out = {}
    for name, frames, loop, fn in clips.clips_for(c, spec.worker, spec.hero):
        anim.bake_clip(arm, name, frames, fn, loop=loop, loc_scale=spec.body.scale)
        out[name] = {"frames": frames, "seconds": round(frames / anim.FPS, 3), "loop": loop}
    return out


def walk_speed(spec, clip_info):
    """Ground speed (m/s) matching the walk clip so feet do not slide."""
    b = spec.body
    leg = (b.hip_h - b.foot_r * 0.9) * b.scale
    if spec.walk == "hop":
        stride = leg * 1.4
    else:
        amp = {"walk": 26, "waddle": 18, "skitter": 22, "prowl": 24, "march": 28}[spec.walk]
        stride = 4 * leg * math.sin(math.radians(amp))
    return round(stride / clip_info["Walk"]["seconds"], 3)


def export_glb(path, ob, arm, team_rgb):
    build.strip_team_tint()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_apply=False,
        export_yup=True, export_animations=True, export_animation_mode="NLA_TRACKS",
        export_force_sampling=True, export_frame_step=1, export_optimize_animation_size=True,
        export_def_bones=True, export_skins=True, export_morph=False, export_lights=False,
        export_cameras=False, export_materials="EXPORT", export_vertex_color="MATERIAL",
        export_all_vertex_colors=False, export_extras=False,
    )
    from . import glb
    glb.patch_materials(path, {"team": team_rgb})


def build_unit(uid, out_dir, preview_dir=None):
    build.reset_scene()
    spec, ob, arm = assemble(uid)
    info = bake_clips(spec, arm)
    team = palette.FACTIONS[spec.faction]["team"]
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{uid}.glb")
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    meta = {
        "id": uid, "faction": spec.faction, "name": spec.name, "role": spec.role,
        "species": spec.body.species, "scale": spec.body.scale, "tris": tris,
        "bones": len(arm.data.bones), "clips": info, "walk_speed": walk_speed(spec, info),
        "height": round(float(max(v.co.z for v in ob.data.vertices)), 3),
        "team_default": team, "file": f"{uid}.glb",
    }
    if preview_dir:
        preview(spec, ob, arm, os.path.join(preview_dir, f"{uid}.png"))
    export_glb(path, ob, arm, palette.rgb(team).tolist())
    return meta


def pose_at(arm, clip, frame):
    ad = arm.animation_data
    act = bpy.data.actions[clip]
    for tr in ad.nla_tracks:
        tr.mute = True
    ad.action = act
    for slot in act.slots:
        ad.action_slot = slot
        break
    bpy.context.scene.frame_set(frame)


def preview(spec, ob, arm, path, shots=None):
    """Contact sheet: one row of poses rendered from the RTS-ish angle."""
    shots = shots or [("Idle", 1), ("Walk", 6), ("Attack", 14), ("IdleSpecial", 50)]
    if spec.worker:
        shots[-1] = ("Work", 14)
    s = spec.body.scale
    h = max(v.co.z for v in ob.data.vertices)
    render.setup_render((600, 720), 24)
    render.setup_world()
    render.lights()
    render.ground()
    cam = render.camera((0, 0, h * 0.5), h * 2.3, 22, 28, lens=50)
    frames = []
    base, ext = os.path.splitext(path)
    for i, (clip, f) in enumerate(shots):
        pose_at(arm, clip, f)
        fp = f"{base}_{i}{ext}"
        render.render(fp)
        frames.append(fp)
    arm.animation_data.action = None
    _stitch(frames, path)
    for fp in frames:
        os.remove(fp)


def _stitch(files, out):
    imgs = [bpy.data.images.load(f) for f in files]
    w, h = imgs[0].size
    sheet = bpy.data.images.new("sheet", w * len(imgs), h, alpha=False)
    buf = np.zeros((h, w * len(imgs), 4), np.float32)
    for i, im in enumerate(imgs):
        px = np.array(im.pixels[:], np.float32).reshape(h, w, 4)
        buf[:, i * w:(i + 1) * w] = px
    sheet.pixels = buf.ravel()
    if os.path.exists(out):
        os.remove(out)
    sheet.filepath_raw = out
    sheet.file_format = "PNG"
    sheet.save(filepath=out)
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(sheet)
