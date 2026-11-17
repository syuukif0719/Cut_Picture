# Look test: daylight sky background (physical sky + sun), studio floor/lights disabled (not deleted).
# Usage: python look_sky.py <in.blend> <out.blend>   (env SKY_EXPOSURE, SUN_ELEV, SUN_ROT in degrees optional)
import bpy, sys, os, math
src, dst = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=src)
s = bpy.context.scene

# studio off (kept in file, just not rendered)
for nm in ("Studio_Cyclorama", "Light_Key", "Light_Rim", "Light_Fill", "Light_Softbox_Reflect", "Light_Path"):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True; o.hide_viewport = True

w = bpy.data.worlds.new("World_Sky"); s.world = w
nt = w.node_tree; N = nt.nodes; L = nt.links
for n in list(N):
    if n.bl_idname not in ("ShaderNodeBackground", "ShaderNodeOutputWorld"): N.remove(n)
bg = N["Background"]; out = N["World Output"]
sky = N.new("ShaderNodeTexSky")
types = [i.identifier for i in sky.bl_rna.properties["sky_type"].enum_items]
print("sky types:", types)
for t in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING", "HOSEK_WILKIE"):
    if t in types: sky.sky_type = t; break
def setp(name, val):
    if hasattr(sky, name):
        try: setattr(sky, name, val)
        except Exception as e: print("sky", name, e)
setp("sun_disc", True)
setp("sun_size", math.radians(0.545))
setp("sun_intensity", 1.0)
setp("sun_elevation", math.radians(float(os.environ.get("SUN_ELEV", 30))))
setp("sun_rotation", math.radians(float(os.environ.get("SUN_ROT", 110))))   # sun from the front-right
setp("altitude", 300.0)
setp("air_density", 1.0); setp("dust_density", 1.2); setp("ozone_density", 1.0)
L.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0
s.view_settings.exposure = float(os.environ.get("SKY_EXPOSURE", -4.3))

# camera a little lower, looking slightly up so the frame is mostly sky
cam = bpy.data.objects.get("CAM_FlyIn")
for fr, z in ((s.frame_start, -0.12), (s.frame_end, -0.08)):
    s.frame_set(fr); cam.location.z = z; cam.keyframe_insert("location", index=2, frame=fr)
s.frame_set(s.frame_start)
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst, "sky:", sky.sky_type)
