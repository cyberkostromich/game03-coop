"""Preview renders: studio lighting, RTS-angle and portrait cameras."""
import math

import bpy
from mathutils import Vector


def setup_world(strength=0.9, top="#9cc4ef", bottom="#e8dcc0"):
    from .palette import rgb
    scene = bpy.context.scene
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = w
    t = w.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputWorld")
    bg = t.nodes.new("ShaderNodeBackground")
    tc = t.nodes.new("ShaderNodeTexCoord")
    sep = t.nodes.new("ShaderNodeSeparateXYZ")
    ramp = t.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (*rgb(bottom), 1)
    ramp.color_ramp.elements[1].position = 0.75
    ramp.color_ramp.elements[1].color = (*rgb(top), 1)
    mp = t.nodes.new("ShaderNodeMapRange")
    mp.inputs["From Min"].default_value = -1
    mp.inputs["From Max"].default_value = 1
    t.links.new(tc.outputs["Generated"], sep.inputs[0])
    # generated coords on world = view direction
    t.links.new(sep.outputs["Z"], mp.inputs["Value"])
    t.links.new(mp.outputs["Result"], ramp.inputs["Fac"])
    t.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    t.links.new(bg.outputs["Background"], out.inputs["Surface"])


def setup_render(res=(1280, 720), samples=64, engine="CYCLES", transparent=False):
    scene = bpy.context.scene
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.device = "CPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = True
        scene.cycles.max_bounces = 6
        try:
            scene.cycles.denoiser = "OPENIMAGEDENOISE"
        except TypeError:
            pass
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    vs = scene.view_settings
    try:
        vs.view_transform = "AgX"
        vs.look = "AgX - Punchy"
    except TypeError:
        pass
    vs.exposure = 0.0


def lights(sun_rot=(52, 0, 38), sun_strength=3.6, rim=True):
    scene = bpy.context.scene
    sd = bpy.data.lights.new("Sun", "SUN")
    sd.energy = sun_strength
    sd.angle = math.radians(6)
    sd.color = (1.0, 0.93, 0.82)
    so = bpy.data.objects.new("Sun", sd)
    so.rotation_euler = [math.radians(a) for a in sun_rot]
    scene.collection.objects.link(so)
    if rim:
        rd = bpy.data.lights.new("Rim", "SUN")
        rd.energy = 1.6
        rd.angle = math.radians(10)
        rd.color = (0.75, 0.85, 1.0)
        ro = bpy.data.objects.new("Rim", rd)
        ro.rotation_euler = [math.radians(a) for a in (-60, 0, 200)]
        scene.collection.objects.link(ro)


def ground(color="#7fa35a", size=400, z=0.0):
    from .palette import rgb
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    g = bpy.context.active_object
    g.name = "Ground"
    m = bpy.data.materials.new("GroundMat")
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb(color), 1)
    bsdf.inputs["Roughness"].default_value = 0.95
    g.data.materials.append(m)
    return g


def camera(target=(0, 0, 0.5), dist=3.0, pitch=25.0, yaw=0.0, lens=50, ortho=None):
    scene = bpy.context.scene
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    co = bpy.data.objects.new("Cam", cd)
    scene.collection.objects.link(co)
    scene.camera = co
    aim(co, target, dist, pitch, yaw)
    return co


def aim(co, target, dist, pitch, yaw):
    t = Vector(target)
    p, y = math.radians(pitch), math.radians(yaw)
    # camera in front of the character (-Y), raised by pitch, orbit by yaw
    off = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p))) * dist
    co.location = t + off
    d = t - co.location
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render(path):
    scene = bpy.context.scene
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
