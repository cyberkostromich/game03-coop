"""Hand-painted texture baking.

Reforged/WoW models get their look from painted textures: light edges on
metal and leather, dark creases, top-down light, fur strands, scuffs.
We generate that procedurally: every material gets a 'paint' shader built
from the vertex colours plus edge/cavity/noise masks, and Cycles bakes it
into one UV atlas per asset. A second bake turns rounded bevels and
surface noise into a tangent-space normal map so low-poly edges catch light.
"""
import math

import bpy

# per material: (edge_highlight, cavity, strand_noise, scratch, weave, roughness, metallic)
PAINT = {
    "body":  dict(edge=0.12, cavity=0.6, strands=0.22, scratch=0.0, weave=0.0, rough=0.82, metal=0.0),
    "cloth": dict(edge=0.06, cavity=0.6, strands=0.0, scratch=0.0, weave=0.10, rough=0.92, metal=0.0),
    "team":  dict(edge=0.08, cavity=0.55, strands=0.0, scratch=0.0, weave=0.08, rough=0.7, metal=0.0),
    "metal": dict(edge=0.9, cavity=0.9, strands=0.0, scratch=0.28, weave=0.0, rough=0.4, metal=0.32,
                  grime=0.35),
    "mail":  dict(edge=0.2, cavity=0.8, strands=0.0, scratch=0.0, weave=0.45, rough=0.5, metal=0.35),
    "gold":  dict(edge=0.75, cavity=0.85, strands=0.0, scratch=0.1, weave=0.0, rough=0.3, metal=0.55,
                  grime=0.15, edge_col=(1.0, 0.93, 0.6, 1)),
    "stone": dict(edge=0.35, cavity=0.85, strands=0.0, scratch=0.0, weave=0.0, rough=0.9, metal=0.0,
                  grime=0.3, blocks=0.65),
    "wood":  dict(edge=0.25, cavity=0.8, strands=0.0, scratch=0.0, weave=0.0, rough=0.85, metal=0.0,
                  grime=0.2, grain=0.3),
    "plaster": dict(edge=0.15, cavity=0.7, strands=0.0, scratch=0.0, weave=0.0, rough=0.95, metal=0.0,
                    grime=0.25),
    "roof":  dict(edge=0.25, cavity=0.8, strands=0.0, scratch=0.0, weave=0.0, rough=0.75, metal=0.0,
                  grime=0.15, shingles=0.5),
    "foliage": dict(edge=0.15, cavity=0.75, strands=0.28, scratch=0.0, weave=0.0, rough=0.9, metal=0.0,
                    grime=0.2),
    "gloss": dict(edge=0.0, cavity=0.2, strands=0.0, scratch=0.0, weave=0.0, rough=0.12, metal=0.0),
    "glow":  dict(edge=0.0, cavity=0.0, strands=0.0, scratch=0.0, weave=0.0, rough=0.5, metal=0.0),
}


def unwrap(ob, margin=0.004):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    try:
        bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    except TypeError:
        bpy.ops.uv.pack_islands(margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def _n(tree, kind, **props):
    node = tree.nodes.new(kind)
    for k, v in props.items():
        setattr(node, k, v)
    return node


def _math(tree, op, a, b=None, clamp=False):
    m = tree.nodes.new("ShaderNodeMath")
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            tree.links.new(v, m.inputs[i])
    return m.outputs[0]


def _mix(tree, mode, fac, a, b):
    m = tree.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    m.blend_type = mode
    for sock, v in ((m.inputs["Factor"], fac), (m.inputs[6], a), (m.inputs[7], b)):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, tuple):
            sock.default_value = v
        else:
            tree.links.new(v, sock)
    return m.outputs[2]


def paint_shader(mat_name, scale=1.0):
    """Emission shader that outputs the 'painted' albedo for baking."""
    cfg = PAINT[mat_name]
    m = bpy.data.materials.get(mat_name)
    t = m.node_tree
    t.nodes.clear()
    out = _n(t, "ShaderNodeOutputMaterial")
    em = _n(t, "ShaderNodeEmission")
    col = _n(t, "ShaderNodeVertexColor", layer_name="Col")
    geo = _n(t, "ShaderNodeNewGeometry")
    tc = _n(t, "ShaderNodeTexCoord")
    base = col.outputs["Color"]

    # top-down painted light: normal.z -> brighter tops, darker undersides
    sep = _n(t, "ShaderNodeSeparateXYZ")
    t.links.new(geo.outputs["Normal"], sep.inputs[0])
    light = _math(t, "MULTIPLY_ADD", sep.outputs["Z"], 0.16)   # z*0.16 + b
    t.nodes[-1].inputs[2].default_value = 1.0
    c = _mix(t, "MULTIPLY", 1.0, base, (1, 1, 1, 1))
    mul = t.nodes[-1]
    t.links.new(light, mul.inputs[7])

    # cavity (small-scale AO) darkens creases
    if cfg["cavity"] > 0:
        ao = _n(t, "ShaderNodeAmbientOcclusion", samples=16, only_local=True)
        ao.inputs["Distance"].default_value = 0.05 * scale
        cav = _math(t, "POWER", ao.outputs["AO"], 1.6)
        cav = _math(t, "MULTIPLY_ADD", cav, cfg["cavity"])
        t.nodes[-1].inputs[2].default_value = 1 - cfg["cavity"]
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(cav, t.nodes[-1].inputs[7])

    # convex edge highlight: bevel normal vs true normal
    if cfg["edge"] > 0:
        bev = _n(t, "ShaderNodeBevel", samples=8)
        bev.inputs["Radius"].default_value = 0.012 * scale
        dot = _n(t, "ShaderNodeVectorMath", operation="DOT_PRODUCT")
        t.links.new(bev.outputs["Normal"], dot.inputs[0])
        t.links.new(geo.outputs["Normal"], dot.inputs[1])
        edge = _math(t, "SUBTRACT", 1.0, dot.outputs["Value"])
        edge = _math(t, "MULTIPLY", edge, 14.0, clamp=True)
        if cfg["cavity"] > 0:   # only where not occluded (keeps creases dark)
            edge = _math(t, "MULTIPLY", edge, ao.outputs["AO"])
        edge = _math(t, "MULTIPLY", edge, cfg["edge"])
        c = _mix(t, "SCREEN", edge, c, cfg.get("edge_col", (1.0, 0.97, 0.9, 1)))

    # fur strands: noise stretched along z + fine grain
    if cfg["strands"] > 0:
        mp = _n(t, "ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (90 / scale, 90 / scale, 14 / scale)
        t.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        nz = _n(t, "ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.0
        nz.inputs["Detail"].default_value = 6
        nz.inputs["Roughness"].default_value = 0.6
        t.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
        k = _math(t, "SUBTRACT", nz.outputs["Fac"], 0.5)
        k = _math(t, "MULTIPLY_ADD", k, cfg["strands"] * 2.2)
        t.nodes[-1].inputs[2].default_value = 1.0
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])

    # metal: hammered mottling + scratches
    if cfg["scratch"] > 0:
        nz = _n(t, "ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 26 / scale
        nz.inputs["Detail"].default_value = 3
        t.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        k = _math(t, "SUBTRACT", nz.outputs["Fac"], 0.5)
        k = _math(t, "MULTIPLY_ADD", k, 0.35)
        t.nodes[-1].inputs[2].default_value = 1.0
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])
        mp = _n(t, "ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (40 / scale, 4 / scale, 40 / scale)
        mp.inputs["Rotation"].default_value = (0.3, 0.7, 0.2)
        t.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        vor = _n(t, "ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        vor.inputs["Scale"].default_value = 3.0
        t.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
        sc = _math(t, "LESS_THAN", vor.outputs["Distance"], 0.025)
        sc = _math(t, "MULTIPLY", sc, cfg["scratch"])
        c = _mix(t, "SCREEN", sc, c, (1, 1, 1, 1))

    # grime / painted value variation (low-frequency blotches)
    if cfg.get("grime", 0) > 0:
        nz = _n(t, "ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 9 / scale
        nz.inputs["Detail"].default_value = 4
        t.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        k = _math(t, "MULTIPLY_ADD", nz.outputs["Fac"], cfg["grime"] * 1.6)
        t.nodes[-1].inputs[2].default_value = 1 - cfg["grime"] * 0.8
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])

    # masonry: coursed blocks (brick texture on (x+y, z)), dark mortar, per-block value shifts
    if cfg.get("blocks", 0) > 0:
        sep = _n(t, "ShaderNodeSeparateXYZ")
        t.links.new(tc.outputs["Object"], sep.inputs[0])
        hx = _math(t, "ADD", sep.outputs["X"], sep.outputs["Y"])
        comb = _n(t, "ShaderNodeCombineXYZ")
        t.links.new(hx, comb.inputs[0])
        t.links.new(sep.outputs["Z"], comb.inputs[1])
        br = _n(t, "ShaderNodeTexBrick")
        br.inputs["Scale"].default_value = 1.6 / scale
        br.inputs["Mortar Size"].default_value = 0.035
        br.inputs["Mortar Smooth"].default_value = 0.3
        br.inputs["Brick Width"].default_value = 0.9
        br.inputs["Row Height"].default_value = 0.42
        br.inputs["Color1"].default_value = (1, 1, 1, 1)
        br.inputs["Color2"].default_value = (0.78, 0.78, 0.78, 1)
        br.inputs["Mortar"].default_value = (1 - cfg["blocks"], 1 - cfg["blocks"], 1 - cfg["blocks"], 1)
        br.offset = 0.5
        t.links.new(comb.outputs[0], br.inputs["Vector"])
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(br.outputs["Color"], t.nodes[-1].inputs[7])
        hl = _math(t, "SUBTRACT", 1.0, br.outputs["Fac"])
        hl = _math(t, "MULTIPLY", hl, 0.08)
        c = _mix(t, "SCREEN", hl, c, (1, 0.97, 0.9, 1))

    # wood grain + plank seams
    if cfg.get("grain", 0) > 0:
        mp = _n(t, "ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (30 / scale, 30 / scale, 3 / scale)
        t.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        wv = _n(t, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X")
        wv.inputs["Scale"].default_value = 1.0
        wv.inputs["Distortion"].default_value = 6.0
        wv.inputs["Detail"].default_value = 3.0
        t.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
        k = _math(t, "MULTIPLY_ADD", wv.outputs["Fac"], cfg["grain"])
        t.nodes[-1].inputs[2].default_value = 1 - cfg["grain"] * 0.6
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])

    # roof shingles: rows with a dark lower lip and staggered breaks
    if cfg.get("shingles", 0) > 0:
        sepz = _n(t, "ShaderNodeSeparateXYZ")
        t.links.new(tc.outputs["Object"], sepz.inputs[0])
        rows = _math(t, "MULTIPLY", sepz.outputs["Z"], 9.0 / scale)
        frac = _math(t, "FRACT", rows)
        lip = _math(t, "LESS_THAN", frac, 0.18)
        k = _math(t, "MULTIPLY_ADD", lip, -cfg["shingles"])
        t.nodes[-1].inputs[2].default_value = 1.0
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])
        top = _math(t, "MULTIPLY", frac, 0.25)
        c = _mix(t, "SCREEN", top, c, (1, 1, 1, 1))
        mp = _n(t, "ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (7 / scale, 7 / scale, 2 / scale)
        t.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        v = _n(t, "ShaderNodeTexVoronoi", feature="DISTANCE_TO_EDGE")
        t.links.new(mp.outputs["Vector"], v.inputs["Vector"])
        brk = _math(t, "LESS_THAN", v.outputs["Distance"], 0.05)
        k = _math(t, "MULTIPLY_ADD", brk, -0.35)
        t.nodes[-1].inputs[2].default_value = 1.0
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])

    # cloth weave
    if cfg["weave"] > 0:
        w1 = _n(t, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X")
        w1.inputs["Scale"].default_value = 160 / scale
        w2 = _n(t, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
        w2.inputs["Scale"].default_value = 160 / scale
        t.links.new(tc.outputs["Object"], w1.inputs["Vector"])
        t.links.new(tc.outputs["Object"], w2.inputs["Vector"])
        k = _math(t, "MULTIPLY", w1.outputs["Fac"], w2.outputs["Fac"])
        k = _math(t, "MULTIPLY_ADD", k, -cfg["weave"])
        t.nodes[-1].inputs[2].default_value = 1.0
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])
        nz = _n(t, "ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 6 / scale
        t.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        k = _math(t, "MULTIPLY_ADD", nz.outputs["Fac"], 0.25)
        t.nodes[-1].inputs[2].default_value = 0.88
        c = _mix(t, "MULTIPLY", 1.0, c, (1, 1, 1, 1))
        t.links.new(k, t.nodes[-1].inputs[7])

    t.links.new(c, em.inputs["Color"])
    t.links.new(em.outputs[0], out.inputs["Surface"])


def normal_shader(mat_name, scale=1.0):
    """Principled with bevelled + bumped normals, for the NORMAL bake."""
    cfg = PAINT[mat_name]
    m = bpy.data.materials.get(mat_name)
    t = m.node_tree
    t.nodes.clear()
    out = _n(t, "ShaderNodeOutputMaterial")
    bsdf = _n(t, "ShaderNodeBsdfPrincipled")
    bev = _n(t, "ShaderNodeBevel", samples=8)
    bev.inputs["Radius"].default_value = (0.01 if mat_name == "metal" else 0.006) * scale
    tc = _n(t, "ShaderNodeTexCoord")
    nz = _n(t, "ShaderNodeTexNoise")
    nz.inputs["Detail"].default_value = 4
    if cfg["strands"] > 0:
        mp = _n(t, "ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (110 / scale, 110 / scale, 16 / scale)
        t.links.new(tc.outputs["Object"], mp.inputs["Vector"])
        t.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
        strength = 0.35
    elif mat_name == "metal":
        nz.inputs["Scale"].default_value = 30 / scale
        t.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        strength = 0.12
    else:
        nz.inputs["Scale"].default_value = 60 / scale
        t.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        strength = 0.15 if mat_name in ("cloth", "team") else 0.0
    bump = _n(t, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.004 * scale
    t.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    t.links.new(bev.outputs["Normal"], bump.inputs["Normal"])
    t.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    t.links.new(bsdf.outputs[0], out.inputs["Surface"])


def final_shader(mat_name, img_col, img_nrm, team=None):
    cfg = PAINT[mat_name]
    m = bpy.data.materials.get(mat_name)
    t = m.node_tree
    t.nodes.clear()
    out = _n(t, "ShaderNodeOutputMaterial")
    bsdf = _n(t, "ShaderNodeBsdfPrincipled")
    tex = _n(t, "ShaderNodeTexImage", image=img_col)
    src = tex.outputs["Color"]
    if mat_name in ("team", "roof") and team is not None:
        mix = _mix(t, "MULTIPLY", 1.0, src, (*team, 1.0))
        src = mix
    t.links.new(src, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = cfg["rough"]
    bsdf.inputs["Metallic"].default_value = cfg["metal"]
    if mat_name == "glow":
        t.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.0
    if img_nrm is not None and mat_name not in ("glow", "gloss"):
        nt = _n(t, "ShaderNodeTexImage", image=img_nrm)
        nm = _n(t, "ShaderNodeNormalMap")
        t.links.new(nt.outputs["Color"], nm.inputs["Color"])
        t.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    t.links.new(bsdf.outputs[0], out.inputs["Surface"])


def bake_textures(ob, size=1024, scale=1.0, samples=24, team=None, normal=True):
    """UV unwrap + bake painted albedo (and normals) for one object."""
    unwrap(ob)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    mats = [s.material.name for s in ob.material_slots]
    img_col = bpy.data.images.new(ob.name + "_col", size, size, alpha=False)
    img_nrm = bpy.data.images.new(ob.name + "_nrm", size, size, alpha=False) if normal else None
    if img_nrm:
        img_nrm.colorspace_settings.name = "Non-Color"

    def target(img):
        for name in mats:
            t = bpy.data.materials[name].node_tree
            node = t.nodes.new("ShaderNodeTexImage")
            node.image = img
            for n in t.nodes:
                n.select = False
            node.select = True
            t.nodes.active = node

    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bk = scene.render.bake
    bk.margin = 6
    bk.use_clear = True

    for name in mats:
        paint_shader(name, scale)
    target(img_col)
    bpy.ops.object.bake(type="EMIT")

    if img_nrm:
        for name in mats:
            normal_shader(name, scale)
        target(img_nrm)
        bk.normal_space = "TANGENT"
        bpy.ops.object.bake(type="NORMAL")

    for name in mats:
        final_shader(name, img_col, img_nrm, team)
    img_col.pack()
    if img_nrm:
        img_nrm.pack()
    return img_col, img_nrm
