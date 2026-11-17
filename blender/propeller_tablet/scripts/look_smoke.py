# Look test: black background, soft back light through stage smoke.
# Usage: python look_smoke.py <in.blend (studio version)> <out.blend>
# env: SMOKE_DENSITY (default 0.025), BACK_W (back light watts, default 120), EXPO (exposure, default 0)
import bpy, bmesh, sys, os
from mathutils import Vector
from math import radians

src, dst = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=src)
s = bpy.context.scene
for nm in ("Studio_Cyclorama", "Light_Path", "Light_Softbox_Reflect", "Light_Key", "Light_Rim"):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True; o.hide_viewport = True

C = bpy.data.collections.new("ENV_Smoke"); s.collection.children.link(C)
w = bpy.data.worlds.new("World_Black"); s.world = w
bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0, 0, 0, 1); bg.inputs["Strength"].default_value = 0.0

target = bpy.data.objects.get("Target_Fly") or bpy.data.objects["Target_Center"]
def area(name, loc, size, size_y, power, color, aim=None, cam_visible=False):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = size; ld.size_y = size_y
    ld.energy = power; ld.color = color
    ob = bpy.data.objects.new(name, ld); ob.location = loc; C.objects.link(ob)
    tc = ob.constraints.new('TRACK_TO'); tc.target = aim or target; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    ob.visible_camera = cam_visible
    return ob
BACK_W = float(os.environ.get("BACK_W", 120))
# main: large soft panel behind and above, slightly to the right -> glow in the smoke + rim on top/right edges
bl = area("Light_Back_Soft", (0.35, 1.9, 0.75), 1.6, 1.0, BACK_W, (0.92, 0.95, 1.0))
bl.data.spread = radians(55)          # narrower beam: glow stays behind the subject, edges fall to black
# second, smaller and warmer from behind-left for a rim on the left edge
area("Light_Back_RimL", (-1.2, 1.2, 0.25), 0.4, 1.2, BACK_W * 0.25, (1.0, 0.9, 0.8))
# barely-there front fill so the face keeps some information (dark, not black)
fill = bpy.data.objects.get("Light_Fill")
if fill: fill.data.energy = 2.5

# stage smoke: big volume box, density broken up by layered noise
me = bpy.data.meshes.new("ENV_Smoke_Volume"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts: v.co = Vector((v.co.x * 6.0, v.co.y * 6.0 + 2.6, v.co.z * 4.0 + 0.3))   # y -0.4..5.6: mostly behind the subject
bm.to_mesh(me); bm.free()
vol = bpy.data.objects.new("ENV_Smoke_Volume", me); C.objects.link(vol)
vol.visible_shadow = False
m = bpy.data.materials.new("ENV_Smoke"); me.materials.append(m)
N, L = m.node_tree.nodes, m.node_tree.links
for n in list(N):
    if n.bl_idname != "ShaderNodeOutputMaterial": N.remove(n)
tc = N.new("ShaderNodeTexCoord")
mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 1.0, 1.6)   # smoke drifts in horizontal layers
L.new(tc.outputs["Object"], mp.inputs["Vector"])
nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.1; nz.inputs["Detail"].default_value = 8
nz.inputs["Roughness"].default_value = 0.6
if "Distortion" in nz.inputs: nz.inputs["Distortion"].default_value = 0.8
L.new(mp.outputs["Vector"], nz.inputs["Vector"])
cr = N.new("ShaderNodeMapRange"); cr.inputs["From Min"].default_value = 0.42; cr.inputs["From Max"].default_value = 0.68
cr.inputs["To Min"].default_value = 0.05; cr.inputs["To Max"].default_value = 1.6
L.new(nz.outputs["Fac"], cr.inputs["Value"])
mul = N.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'
mul.inputs[1].default_value = float(os.environ.get("SMOKE_DENSITY", 0.025))
L.new(cr.outputs["Result"], mul.inputs[0])
pv = N.new("ShaderNodeVolumePrincipled")
pv.inputs["Color"].default_value = (0.85, 0.87, 0.9, 1)
pv.inputs["Anisotropy"].default_value = 0.55          # forward scattering: glows when lit from behind
L.new(mul.outputs[0], pv.inputs["Density"])
L.new(pv.outputs[0], N["Material Output"].inputs["Volume"])

s.cycles.volume_bounces = 1
s.cycles.volume_step_rate = 2.0 if hasattr(s.cycles, "volume_step_rate") else 1.0
s.view_settings.exposure = float(os.environ.get("EXPO", 0.0))
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst)
