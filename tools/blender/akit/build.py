"""bpy side: scene setup, materials, turning Parts into Blender meshes."""
import bpy
import numpy as np

from . import palette

MATS = {
    # name: (roughness, metallic, emission)
    "body": (0.78, 0.0, 0.0),
    "cloth": (0.9, 0.0, 0.0),
    "metal": (0.42, 0.75, 0.0),
    "team": (0.62, 0.0, 0.0),
    "gloss": (0.12, 0.0, 0.0),
    "glow": (0.5, 0.0, 3.0),
}
MAT_ORDER = list(MATS)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures,
                 bpy.data.actions, bpy.data.objects):
        for block in list(coll):
            coll.remove(block)


def material(name, team=None):
    """Vertex-color driven material. 'team' parts get tinted by team color."""
    key = name if team is None or name != "team" else "team"
    m = bpy.data.materials.get(key)
    if m is None:
        m = bpy.data.materials.new(key)
    rough, metal, emit = MATS[name]
    tree = m.node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
    col = tree.nodes.new("ShaderNodeVertexColor")
    col.layer_name = "Col"
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    src = col.outputs["Color"]
    if name == "team" and team is not None:
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        tree.links.new(src, mix.inputs["A"])
        mix.inputs["B"].default_value = (*palette.rgb(team), 1)
        src = mix.outputs["Result"]
    tree.links.new(src, bsdf.inputs["Base Color"])
    if emit > 0:
        tree.links.new(col.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emit
    tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


def strip_team_tint():
    """Before glTF export: link vertex colors straight to base color.

    The team tint is re-applied as baseColorFactor by export.patch_glb.
    """
    m = bpy.data.materials.get("team")
    if m:
        material("team", team=None)


def parts_to_object(parts, name, team=None, collection=None, paint_pass=True):
    """Merge Parts into a single mesh object with material slots + groups."""
    verts, faces, cols, mat_idx, smooth = [], [], [], [], []
    groups = {}
    used = sorted({p.mat for p in parts}, key=MAT_ORDER.index)
    off = 0
    for p in parts:
        n = len(p.V)
        verts.append(p.V)
        cols.append(p.C)
        mi = used.index(p.mat)
        for f in p.F:
            faces.append([i + off for i in f])
            mat_idx.append(mi)
            smooth.append(p.smooth)
        if p.weights:
            for b, w in p.weights.items():
                groups.setdefault(b, []).append((off, w))
        elif p.bone:
            groups.setdefault(p.bone, []).append((off, np.ones(n)))
        off += n
    V = np.vstack(verts)
    C = np.vstack(cols)
    if paint_pass:
        # hand-painted value ramp: darker toward the feet, a touch of grain
        z0, z1 = V[:, 2].min(), V[:, 2].max()
        t = np.clip((V[:, 2] - z0) / max(z1 - z0, 1e-6), 0, 1)[:, None]
        rng = np.random.default_rng(len(V))
        grain = 1 + 0.035 * (rng.random((len(V), 1)) - 0.5)
        C = C * (0.8 + 0.28 * t) * grain
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], faces)
    me.validate(clean_customdata=False)
    me.polygons.foreach_set("material_index", mat_idx)
    me.polygons.foreach_set("use_smooth", smooth)
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    rgba = np.hstack([np.clip(C, 0, 1), np.ones((len(C), 1))]).astype(np.float32)
    attr.data.foreach_set("color", rgba.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = 0
    for m in used:
        me.materials.append(material(m, team))
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    for b, chunks in groups.items():
        vg = ob.vertex_groups.new(name=b)
        for start, w in chunks:
            for i, wi in enumerate(w):
                if wi > 1e-4:
                    vg.add([start + i], float(wi), "REPLACE")
    ob["ao_mask"] = np.concatenate([np.full(len(p.V), 1.0 if p.ao else 0.0) for p in parts]).tolist()
    return ob


def bake_ao(ob, strength=0.75, distance=0.25, samples=48, ground=True):
    """Bake ambient occlusion into the 'Col' vertex colors (hand-painted look)."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.world = scene.world or bpy.data.worlds.new("World")
    me = ob.data
    ao = me.color_attributes.new("AO", "FLOAT_COLOR", "POINT")
    me.color_attributes.active_color = ao
    plane = None
    if ground:
        bpy.ops.mesh.primitive_plane_add(size=50, location=(0, 0, ob.bound_box[0][2] - 0.001))
        plane = bpy.context.active_object
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    scene.world.light_settings.distance = distance
    bpy.ops.object.bake(type="AO", target="VERTEX_COLORS")
    a = np.empty(len(me.vertices) * 4, np.float32)
    ao.data.foreach_get("color", a)
    a = a.reshape(-1, 4)[:, 0:1]
    col = me.color_attributes["Col"]
    c = np.empty(len(me.vertices) * 4, np.float32)
    col.data.foreach_get("color", c)
    c = c.reshape(-1, 4)
    mask = np.asarray(ob.get("ao_mask", [1.0] * len(me.vertices)), np.float32)[:, None]
    k = 1 - strength * mask * (1 - a)
    c[:, :3] *= k
    col.data.foreach_set("color", c.ravel())
    me.color_attributes.remove(ao)
    me.color_attributes.active_color = me.color_attributes["Col"]
    if plane:
        bpy.data.objects.remove(plane, do_unlink=True)
    if "ao_mask" in ob:
        del ob["ao_mask"]
