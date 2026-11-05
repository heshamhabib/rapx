"""
Renders a procedural unit (.blend) into OpenRA facing frames: transparent background,
soft cast shadow (shadow catcher), orthographic RTS camera, light from the upper-left.

Env: PX_UNIT_PX (world px per Blender unit, i.e. unit size), PX_SUN_ELEV (sun height, degrees),
PX_NO_GROUND=1 (no ground shadow, for aircraft).

Frame i faces i * 360/N degrees counter-clockwise from north (OpenRA facing order).
The ground point under the object's origin is the centre of every frame.

  Blender -b unit.blend -P artsrc/units/render_sprites.py -- <root object> <out dir> [facings] [frame px] [samples] [zoom]

zoom > 1 renders the same framing at higher resolution (for previews, not for the game).
Writes <out dir>/frame-NN.png.

Animated units import this module from their own render script and call setup() / render_to().
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))

# Sprite pixels per world pixel (matches the HD buildings) and the RTS camera angle.
DENSITY = 3.0
ELEVATION = 50.0


def setup(frame=160, samples=64, zoom=1, unit_px=None, sun_elevation=None):
    """Prepares the current scene: Cycles, lights, shadow catcher and camera.

    unit_px: world pixels per Blender unit (a 7-unit vehicle ~ one 24px cell, like the classic sprites).
    """
    unit_px = unit_px or float(os.environ.get("PX_UNIT_PX", "3.5"))
    sun_elevation = sun_elevation or float(os.environ.get("PX_SUN_ELEV", "62"))

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = frame * zoom
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    # Standard (not AgX) keeps the team-colour green at its hue so PlayerColorShift can find it
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = -0.2

    # Even sky glow for ambient light plus one sun from the upper-left, high enough that the
    # shadow stays short and close to the unit like the classic sprites.
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.68, 0.8, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(6)
    s_el = math.radians(sun_elevation)
    travel = Vector((math.cos(s_el) * 0.707, -math.cos(s_el) * 0.707, -math.sin(s_el)))  # towards screen down-right
    sun.rotation_euler = (-travel).to_track_quat("Z", "Y").to_euler()  # a sun shines along its -Z
    scene.collection.objects.link(sun)

    # PX_LIGHT=punchy (ground vehicles, set by meshes/make.sh): little sky, a hard sun and a cool rim
    # light from behind, so hull/turret faces separate (lit top, darker sides) and edges catch light;
    # the AI-textured paint gets a little shinier for small metal highlights.
    if os.environ.get("PX_LIGHT") == "punchy":
        world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.25
        sun.data.energy = 5.6
        sun.data.angle = math.radians(3)
        rim = bpy.data.objects.new("Rim", bpy.data.lights.new("Rim", "SUN"))
        rim.data.energy = 3.0
        rim.data.color = (0.85, 0.92, 1.0)
        r_el = math.radians(28)
        rim_travel = Vector((-math.cos(r_el) * 0.5, -math.cos(r_el) * 0.866, -math.sin(r_el)))  # from behind, towards camera
        rim.rotation_euler = (-rim_travel).to_track_quat("Z", "Y").to_euler()
        rim.data.use_shadow = False  # no second ground shadow
        scene.collection.objects.link(rim)
        scene.view_settings.exposure = -0.1
        for material in bpy.data.materials:
            bsdf = material.node_tree and material.node_tree.nodes.get("Principled BSDF")
            # textured paint only; px_finish = finish already set on import (meshes/import_sketchfab.py)
            if bsdf and bsdf.inputs["Base Color"].is_linked and not material.get("px_finish"):
                bsdf.inputs["Roughness"].default_value = 0.42
                bsdf.inputs["Metallic"].default_value = 0.35

    # PX_LIGHT=hd (Sketchfab models, meshes/import_sketchfab.py): a warm, sharp key sun, a cool rim from
    # behind and a faint fill, with the HDR sky seen only in reflections (metal and glass mirror a real sky)
    # while diffuse ambient stays an even blue-grey glow, so the HDRI's own sun adds no second shadow.
    # The models keep their own PBR maps (normal, roughness, metal), so materials are left alone.
    if os.environ.get("PX_LIGHT") == "hd":
        nt = world.node_tree
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(os.path.join(HERE, "..", "hdri", "sky_2k.hdr"))
        glossy_sky = nt.nodes.new("ShaderNodeBackground")
        glossy_sky.inputs["Strength"].default_value = 0.9
        # Grey: the sky image's green horizon (grass, trees) would tint the sides of shiny models green, and
        # green is the team colour
        grey = nt.nodes.new("ShaderNodeHueSaturation")
        grey.inputs["Saturation"].default_value = 0.0
        nt.links.new(env.outputs["Color"], grey.inputs["Color"])
        nt.links.new(grey.outputs["Color"], glossy_sky.inputs["Color"])
        ambient = nt.nodes["Background"]
        ambient.inputs["Strength"].default_value = 0.32
        path = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(path.outputs["Is Glossy Ray"], mix.inputs["Fac"])
        nt.links.new(ambient.outputs["Background"], mix.inputs[1])
        nt.links.new(glossy_sky.outputs["Background"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], nt.nodes["World Output"].inputs["Surface"])

        sun.data.energy = 4.6
        sun.data.angle = math.radians(2)
        sun.data.color = (1.0, 0.95, 0.88)
        for name, energy, colour, elevation, along in (
                ("Rim", 2.4, (0.8, 0.88, 1.0), 25, (-0.5, -0.866)),  # from behind, towards the camera
                ("Fill", 0.5, (0.9, 0.93, 1.0), 35, (-0.707, 0.707))):  # opposite the key, lifts shadow sides
            light = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
            light.data.energy = energy
            light.data.color = colour
            el = math.radians(elevation)
            t = Vector((math.cos(el) * along[0], math.cos(el) * along[1], -math.sin(el)))
            light.rotation_euler = (-t).to_track_quat("Z", "Y").to_euler()
            light.data.use_shadow = False  # one ground shadow only
            scene.collection.objects.link(light)
        scene.view_settings.exposure = 0.0
        scene.view_settings.look = "Medium High Contrast"
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.005
        scene.cycles.max_bounces = 8
        scene.cycles.caustics_reflective = scene.cycles.caustics_refractive = False
        scene.render.filter_size = 1.0  # crisper edges: the sprite is drawn at 1/3 of its pixels anyway

    # Ground shadow (aircraft skip it: the engine draws their shadow on the ground itself)
    if not os.environ.get("PX_NO_GROUND"):
        bpy.ops.mesh.primitive_plane_add(size=60)
        bpy.context.object.is_shadow_catcher = True

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = frame / (unit_px * DENSITY)
    e = math.radians(ELEVATION)
    cam.location = Vector((0, -50 * math.cos(e), 50 * math.sin(e)))
    cam.rotation_euler = (math.radians(90) - e, 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene


def face(root, index, facings):
    """Turns root to OpenRA facing frame `index` of `facings` (counter-clockwise from north)."""
    root.rotation_euler = (0, 0, math.radians(index * 360.0 / facings))


def render_to(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    root_name, out = argv[0], argv[1]
    facings = int(argv[2]) if len(argv) > 2 else 32
    frame = int(argv[3]) if len(argv) > 3 else 160
    samples = int(argv[4]) if len(argv) > 4 else 64
    zoom = int(argv[5]) if len(argv) > 5 else 1

    setup(frame, samples, zoom)
    root = bpy.data.objects[root_name]
    for i in range(facings):
        face(root, i, facings)
        render_to(os.path.join(out, f"frame-{i:02d}.png"))
    print("rendered", facings, "facings to", out)


if __name__ == "__main__":
    main()
