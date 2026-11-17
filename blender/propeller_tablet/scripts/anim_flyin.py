# Propeller Tablet — fly-in animation: comes from far back, brakes (flare), settles into a hover in front of camera.
# Usage: python anim_flyin.py <in.blend> <out.blend>
# Rig: FLY_Root (flight path) -> FLY_Hover (bob / wobble) -> every top-level tablet object (and boolean cutters).
import bpy, sys, os, math
from math import radians, sin, pi

src, dst = sys.argv[-2], sys.argv[-1]
SKILL_SCRIPTS = os.environ.get("BPL_SCRIPTS", "")
bpy.ops.wm.open_mainfile(filepath=src)
scene = bpy.context.scene
scene.render.fps = 24
scene.frame_start, scene.frame_end = 1, 120
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
except Exception:
    pass

C_ROOT = bpy.data.collections["PropellerTablet"]
C_CUT = bpy.data.collections["_Cutters"]
C_STUDIO = bpy.data.collections["Studio"]
C_CAMS = bpy.data.collections["Cameras"]

# ---------------------------------------------------------------- rig
root = bpy.data.objects.new("FLY_Root", None); root.empty_display_type = 'ARROWS'; root.empty_display_size = 0.25
hover = bpy.data.objects.new("FLY_Hover", None); hover.empty_display_type = 'SPHERE'; hover.empty_display_size = 0.05
C_ROOT.objects.link(root); C_ROOT.objects.link(hover)
hover.parent = root
for o in list(C_ROOT.all_objects) + list(C_CUT.all_objects):
    if o.parent is None and o not in (root, hover):
        o.parent = hover            # rig sits at the origin with identity transform -> no inverse needed

# flight path keys: frame, location (m), rotation deg (pitch X: + leans top toward camera, roll Y, yaw Z)
PATH = [
    (-12, (0.45, 10.5, 0.95), (17, -3, -14)),
    (1,   (0.38, 8.6, 0.84),  (17, -4, -12)),
    (36,  (0.16, 3.6, 0.46),  (15, 3, -5)),
    (64,  (0.02, 0.55, 0.17), (-9, 1, 1)),      # flare: tilts back to brake
    (78,  (0.0, -0.06, 0.105), (-11, -0.5, 0)), # small overshoot toward camera
    (92,  (0.0, 0.025, 0.128), (4, 0.3, 0)),
    (106, (0.0, -0.004, 0.117), (-1.2, 0, 0)),
    (120, (0.0, 0.0, 0.12),   (0, 0, 0)),
]
for f, loc, rot in PATH:
    root.location = loc
    root.rotation_euler = tuple(radians(a) for a in rot)
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)

# hover bob + flight wobble on FLY_Hover (amplitude shrinks once it has arrived)
def env(f):  # 1 during flight -> 0.3 while hovering
    t = min(max((f - 60) / 40.0, 0.0), 1.0)
    return 1.0 - 0.7 * (t * t * (3 - 2 * t))
for f in range(-12, 131, 4):
    a = env(f)
    hover.location = (0.004 * a * sin(f * 0.21 + 1.0), 0.0, 0.007 * a * sin(f * 0.26) + 0.002 * sin(f * 0.61))
    hover.rotation_euler = (radians(1.8 * a * sin(f * 0.23 + 0.5)), radians(2.4 * a * sin(f * 0.17 + 2.0)),
                            radians(1.5 * a * sin(f * 0.11 + 1.3)))
    hover.keyframe_insert("location", frame=f)
    hover.keyframe_insert("rotation_euler", frame=f)

# propeller spin: constant 112.5 deg/frame (7.5 rev/s @24fps) -> reads as fast forward spin with motion blur
rotor = bpy.data.objects["Propeller_Rotor"]
rotor.animation_data_clear()
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
except Exception:
    pass
for f in (-12, 132):
    rotor.rotation_euler = (0, 0, radians(112.5) * (f + 12))
    rotor.keyframe_insert("rotation_euler", index=2, frame=f)
def all_fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action: return []
    act = ad.action
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(act, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:
        return list(getattr(act, "fcurves", []))
for fc in all_fcurves(rotor):
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
# path keys: auto-clamped bezier, but the first keys keep momentum (already flying at frame 1)
for fc in all_fcurves(root):
    for kp in fc.keyframe_points:
        kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    fc.update()

# ---------------------------------------------------------------- studio: bigger cove so the approach has a floor
cyc = bpy.data.objects["Studio_Cyclorama"]
cyc.scale = (7.0, 7.0, 4.0)
fm = bpy.data.materials["M_Floor"]
for n in fm.node_tree.nodes:   # keep texture size constant despite the object scale
    if n.bl_idname == "ShaderNodeTexNoise":
        n.inputs["Scale"].default_value *= 7.0
ld = bpy.data.lights.new("Light_Path", 'AREA'); ld.shape = 'RECTANGLE'; ld.size = 3.0; ld.size_y = 9.0
ld.energy = 260.0; ld.color = (0.9, 0.94, 1.0)
lp = bpy.data.objects.new("Light_Path", ld); lp.location = (0.2, 5.0, 3.2); C_STUDIO.objects.link(lp)

# ---------------------------------------------------------------- camera
tgt = bpy.data.objects.new("Target_Fly", None); tgt.location = (0, 0, 0.15); C_STUDIO.objects.link(tgt)
cd = bpy.data.cameras.new("CAM_FlyIn"); cam = bpy.data.objects.new("CAM_FlyIn", cd); C_CAMS.objects.link(cam)
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
cd.dof.use_dof = True; cd.dof.focus_object = hover
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
except Exception:
    pass
for f, loc in ((1, (0.06, -2.35, 0.06)), (120, (0.0, -2.08, 0.10))):   # slow, straight push-in (never fully static)
    cam.location = loc; cam.keyframe_insert("location", frame=f)
scene.camera = cam
bpy.context.view_layer.update()
if SKILL_SCRIPTS:
    g = {"CAM": dict(camera="CAM_FlyIn", series="signature", focal=75, tstop=5.6, mode="4.6K_16:9",
                     use_dof=True, shutter_angle=180), "bpy": bpy}
    exec(open(os.path.join(SKILL_SCRIPTS, "camera_preset.py")).read(), g)
    print(g.get("result"))
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst)
