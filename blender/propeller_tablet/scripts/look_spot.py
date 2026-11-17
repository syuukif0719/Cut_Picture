# Look test: black void, one spotlight from above at frame centre; the tablet flies into its pool of light.
# Motion is unchanged (uses the fly-in animation file). Haze only inside the beam, so the rest stays black.
# Usage: python look_spot.py <in.blend (fly-in, studio version)> <out.blend>
# env: SPOT_W (default 900), BEAM_DENSITY (default 0.05), LENS (default 47)
import bpy, bmesh, sys, os, math
from mathutils import Vector
from math import radians

src, dst = sys.argv[-2], sys.argv[-1]
SKILL_SCRIPTS = os.environ.get("BPL_SCRIPTS", "")
bpy.ops.wm.open_mainfile(filepath=src)
s = bpy.context.scene
for nm in ("Studio_Cyclorama", "Light_Path", "Light_Softbox_Reflect", "Light_Key", "Light_Rim"):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True; o.hide_viewport = True
fill = bpy.data.objects.get("Light_Fill")
if fill: fill.data.energy = 0.8
w = bpy.data.worlds.new("World_Black"); s.world = w
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0

C = bpy.data.collections.new("ENV_Spot"); s.collection.children.link(C)
FLOOR_Z = -0.20
SPOT_Z = 2.6
CONE = radians(13)

# black stage floor (slightly glossy so the pool and a soft reflection read)
me = bpy.data.meshes.new("ENV_Stage_Floor"); bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=15.0)
for v in bm.verts: v.co.z = FLOOR_Z
bm.to_mesh(me); bm.free()
fl = bpy.data.objects.new("ENV_Stage_Floor", me); C.objects.link(fl)
mf = bpy.data.materials.new("ENV_Stage_Black")
b = mf.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1); b.inputs["Roughness"].default_value = 0.42
me.materials.append(mf)

# the spotlight
sd = bpy.data.lights.new("Light_Spot_Center", 'SPOT')
sd.energy = float(os.environ.get("SPOT_W", 900)); sd.spot_size = CONE; sd.spot_blend = 0.35
sd.shadow_soft_size = 0.04; sd.color = (1.0, 0.96, 0.9)
so = bpy.data.objects.new("Light_Spot_Center", sd); so.location = (0, 0.0, SPOT_Z); C.objects.link(so)
so.rotation_euler = (0, 0, 0)          # spot points down (-Z)

# haze only inside (a bit wider than) the beam cone
r_bot = (SPOT_Z - FLOOR_Z) * math.tan(CONE / 2) * 1.25
me = bpy.data.meshes.new("ENV_Beam_Haze"); bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=r_bot, radius2=0.03, depth=SPOT_Z - FLOOR_Z - 0.01)
for v in bm.verts: v.co.z += (SPOT_Z + FLOOR_Z) / 2
bm.to_mesh(me); bm.free()
hz = bpy.data.objects.new("ENV_Beam_Haze", me); C.objects.link(hz); hz.visible_shadow = False
mv = bpy.data.materials.new("ENV_Beam_Haze"); N, L = mv.node_tree.nodes, mv.node_tree.links
for n in list(N):
    if n.bl_idname != "ShaderNodeOutputMaterial": N.remove(n)
tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 2.5; nz.inputs["Detail"].default_value = 6
L.new(tc.outputs["Object"], nz.inputs["Vector"])
mr = N.new("ShaderNodeMapRange"); mr.inputs["From Min"].default_value = 0.35; mr.inputs["From Max"].default_value = 0.7
mr.inputs["To Min"].default_value = 0.4; mr.inputs["To Max"].default_value = 1.3
L.new(nz.outputs["Fac"], mr.inputs["Value"])
mul = N.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = float(os.environ.get("BEAM_DENSITY", 0.14))
L.new(mr.outputs["Result"], mul.inputs[0])
pv = N.new("ShaderNodeVolumePrincipled"); pv.inputs["Anisotropy"].default_value = 0.3
L.new(mul.outputs[0], pv.inputs["Density"]); L.new(pv.outputs[0], N["Material Output"].inputs["Volume"])
me.materials.append(mv)

# camera: same move, wider lens so the beam and the pool read
cam = bpy.data.objects["CAM_FlyIn"]; s.camera = cam
bpy.context.view_layer.update()
lens = int(os.environ.get("LENS", 47))
if SKILL_SCRIPTS:
    g = {"CAM": dict(camera="CAM_FlyIn", series="signature", focal=lens, tstop=4.0, mode="4.6K_16:9", use_dof=True), "bpy": bpy}
    exec(open(os.path.join(SKILL_SCRIPTS, "camera_preset.py")).read(), g)
    print(g.get("result", {}).get("warnings"))
else:
    cam.data.lens = lens; cam.data.dof.aperture_fstop = 4.0
s.cycles.volume_bounces = 1
s.view_settings.exposure = 0.0
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst)
