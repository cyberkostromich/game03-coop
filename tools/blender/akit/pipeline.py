"""Unit build pipeline: parts -> mesh -> AO bake -> rig -> clips -> GLB."""
import json
import math
import os

import bpy
import numpy as np

from . import anim, beast, build, clips, palette, render, rig, texture, units


def assemble(uid, team=None, textured=True):
    """Build a unit into the current scene. Returns (spec, mesh_ob, arm_ob)."""
    spec = units.build(uid)
    s = spec.body.scale
    tint = team or palette.FACTIONS[spec.faction]["team"]
    parts = spec.parts
    for p in parts:
        p.V = p.V * s
    ob = build.parts_to_object(parts, uid, team=tint)
    budget = 16000 if spec.hero else (9000 if spec.worker else 12500)
    build.decimate_to(ob, budget)
    build.bake_ao(ob, strength=0.55, distance=0.22 * s, samples=32)
    if textured:
        size = 2048 if spec.hero else 1024
        texture.bake_textures(ob, size=size, scale=s, team=palette.rgb(tint).tolist())
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
    for o in bpy.context.scene.objects:
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
        export_all_vertex_colors=False, export_extras=False, export_image_format="WEBP",
        export_image_quality=88,
    )
    from . import glb
    glb.patch_materials(path, {"team": team_rgb, "roof": team_rgb})


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
    """Review sheet: idle + attack beauty shots (Reforged framing) and an RTS-camera view."""
    shots = shots or [("Idle", 1, "beauty"), ("Attack", 14, "beauty"), ("Walk", 6, "rts")]
    if spec.worker:
        shots[1] = ("Work", 14, "beauty")
    h = max(v.co.z for v in ob.data.vertices)
    render.setup_render((600, 720), 32)
    render.setup_world(0.9, top="#3a68c0", bottom="#16264a")
    render.lights(sun_rot=(48, 0, 28), sun_strength=3.8)
    render.ground("#16264a")
    cam = render.camera((0, 0, h * 0.5), h * 2.3, 10, 22, lens=50)
    frames = []
    base, ext = os.path.splitext(path)
    for i, (clip, f, kind) in enumerate(shots):
        if kind == "rts":
            render.aim(cam, (0, 0, h * 0.4), max(h, 1.2) * 3.6, 52, 30)
        else:
            render.aim(cam, (0, 0, h * 0.5), h * 2.3, 10, 22)
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


# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------

def assemble_building(bid, textured=True, tex_size=None):
    from . import buildings
    spec = buildings.build(bid)
    # halls are the hero pieces; the rest read fine at 1024 and bake 4x faster
    tex_size = tex_size or (1536 if spec.role in ("town_hall", "shrine") else 1024)
    tint = spec.team
    ob = build.parts_to_object(spec.parts, bid, team=tint)
    build.decimate_to(ob, 60000)   # buildings: few on screen, keep thin details intact
    build.bake_ao(ob, strength=0.6, distance=0.9, samples=20)
    if textured:
        texture.bake_textures(ob, size=tex_size, scale=2.4, team=palette.rgb(tint).tolist())
    bones = [("root", (0, 0, 0), (0, 0, 0.5), None, True)] + [
        (n, np.asarray(h), np.asarray(t), par, True) for n, h, t, par in spec.bones]
    arm = rig.create_armature(bid, bones)
    rig.bind(ob, arm)
    return spec, ob, arm


def building_clips(spec, arm):
    names = [b.name for b in arm.data.bones]
    banners = sorted({n.split(".")[0] for n in names if n.startswith("banner")})

    def idle(t):
        p = anim.Pose()
        for i, bn in enumerate(banners):
            ph = i * 0.37
            p.rot(bn + ".1", 4 * math.sin(2 * math.pi * (t * 2 + ph)), 6 * math.sin(2 * math.pi * (t + ph)), 0)
            p.rot(bn + ".2", 8 * math.sin(2 * math.pi * (t * 2 + ph - 0.2)), 10 * math.sin(2 * math.pi * (t + ph - 0.25)), 0)
        if "wheel" in names:
            p.rot("wheel", -360 * t)
        return p
    anim.bake_clip(arm, "Idle", 90, idle, loop=True)
    return {"Idle": {"frames": 90, "seconds": 3.0, "loop": True}}


def preview_building(ob, arm, path):
    render.setup_render((900, 700), 32)
    render.setup_world(0.9, top="#9cc4ef", bottom="#e8dcc0")
    render.lights(sun_rot=(50, 0, 35), sun_strength=3.8)
    render.ground("#6f9a4a")
    h = max(v.co.z for v in ob.data.vertices)
    cam = render.camera((0, 0, h * 0.4), h * 2.3, 28, 30, lens=50)
    base, ext = os.path.splitext(path)
    f1 = f"{base}_0{ext}"
    render.render(f1)
    render.aim(cam, (0, 0, h * 0.25), h * 3.2, 55, 25)
    f2 = f"{base}_1{ext}"
    render.render(f2)
    _stitch([f1, f2], path)
    os.remove(f1)
    os.remove(f2)


def build_building(bid, out_dir, preview_dir=None):
    build.reset_scene()
    spec, ob, arm = assemble_building(bid)
    info = building_clips(spec, arm)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{bid}.glb")
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    meta = {"id": bid, "faction": spec.faction, "name": spec.name, "role": spec.role,
            "footprint": spec.footprint, "tris": tris, "clips": info, "team_default": spec.team,
            "height": round(float(max(v.co.z for v in ob.data.vertices)), 3), "file": f"{bid}.glb"}
    if preview_dir:
        preview_building(ob, arm, os.path.join(preview_dir, f"{bid}.png"))
    export_glb(path, ob, arm, palette.rgb(spec.team).tolist())
    return meta


# ---------------------------------------------------------------------------
# Static props (trees, rocks, bridges...)
# ---------------------------------------------------------------------------

def export_static(path, ob):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_yup=True, export_animations=False,
        export_skins=False, export_materials="EXPORT", export_vertex_color="MATERIAL",
        export_image_format="WEBP", export_image_quality=85, export_lights=False, export_cameras=False)


def build_prop(pid, out_dir, preview_dir=None):
    from . import props
    build.reset_scene()
    parts = props.PROPS[pid]()
    ob = build.parts_to_object(parts, pid)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    h = max(v.co.z for v in ob.data.vertices)
    build.bake_ao(ob, strength=0.5, distance=0.6, samples=24)
    texture.bake_textures(ob, size=512, scale=1.6, normal=False)
    os.makedirs(out_dir, exist_ok=True)
    if preview_dir:
        render.setup_render((420, 420), 24)
        render.setup_world(0.9)
        render.lights()
        render.ground("#6f9a4a")
        render.camera((0, 0, h * 0.45), max(h, 1.0) * 2.4, 25, 30, lens=50)
        render.render(os.path.join(preview_dir, f"{pid}.png"))
    export_static(os.path.join(out_dir, f"{pid}.glb"), ob)
    return {"id": pid, "tris": tris, "height": round(float(h), 2), "file": f"{pid}.glb"}
