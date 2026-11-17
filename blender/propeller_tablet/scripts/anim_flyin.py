# Propeller Tablet — fly-in animation (v2: wind-up -> fast serpentine dash -> slow, relaxed settle)
# Usage: python anim_flyin.py <in.blend> <out.blend>
# Rig: FLY_Root (flight path, baked every 2 frames from the curves below) -> FLY_Hover (bob / wobble)
#      -> every top-level tablet object (and boolean cutters).
# Beats @24fps:  1-18 hover far away | 18-30 wind-up (pull back, lean back, prop spins up)
#                30-~70 dash, weaving left/right with banking | 70-144 brake (flare) and drift in slowly, settle.
import bpy, sys, os, math
from math import radians, degrees, sin, cos, pi, exp, atan2

src, dst = sys.argv[-2], sys.argv[-1]
SKILL_SCRIPTS = os.environ.get("BPL_SCRIPTS", "")
bpy.ops.wm.open_mainfile(filepath=src)
scene = bpy.context.scene
FPS, F0, F1 = 24, 1, 144
scene.render.fps = FPS
scene.frame_start, scene.frame_end = F0, F1

def pref_interp(kind):
    try: bpy.context.preferences.edit.keyframe_new_interpolation_type = kind
    except Exception: pass

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
        o.parent = hover

def smooth(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)

# ---------------------------------------------------------------- flight curves (per frame)
Y_FAR, Z_FAR, Z_END, BACK = 9.0, 0.75, 0.12, 0.28
FR = list(range(F0 - 12, F1 + 13))
def vel(f):              # forward speed profile (normalized): burst, cruise, long exponential brake
    if f < 30: return 0.0
    if f < 38: return smooth(30, 38, f)
    if f < 60: return 1.0
    return exp(-(f - 60) / 10.0)
dist = {}; acc = 0.0
for f in FR:
    acc += vel(f); dist[f] = acc
total = dist[F1]
def y_of(f):
    back = BACK * smooth(18, 30, f)                  # wind-up: drifts back a little
    d = min(dist.get(f, total) / total, 1.0)
    ovs = 0.0
    if f > 92:                                        # gentle overshoot toward camera, then back
        ovs = -0.05 * exp(-(f - 92) / 14.0) * sin(2 * pi * (f - 92) / 38.0)
    return Y_FAR + back - (Y_FAR + BACK) * d + ovs
def x_of(f):
    y = y_of(f)
    trav = (Y_FAR + BACK) * min(dist.get(f, total) / total, 1.0)   # distance actually travelled in the dash
    amp = 0.5 * smooth(0.8, 5.0, y) * smooth(0.0, 1.0, trav)       # weave fades out near the camera
    return amp * sin(2 * pi * trav / 7.0)
def z_of(f):
    y = y_of(f)
    k = max(min(y / Y_FAR, 1.0), 0.0) ** 1.25
    z = Z_END + (Z_FAR - Z_END) * k
    z += 0.05 * smooth(18, 28, f) * (1 - smooth(30, 40, f))   # small rise during the wind-up
    return z

P = {f: (x_of(f), y_of(f), z_of(f)) for f in FR}
def d1(f, i): return (P[min(f + 1, FR[-1])][i] - P[max(f - 1, FR[0])][i]) / 2.0
def d2(f, i): return P[min(f + 1, FR[-1])][i] - 2 * P[f][i] + P[max(f - 1, FR[0])][i]
vmax = max(abs(d1(f, 1)) for f in FR[1:-1])

pref_interp('BEZIER')
for f in range(F0 - 12, F1 + 13, 2):
    vy, ay = -d1(f, 1) / vmax, -d2(f, 1) / vmax        # forward (toward camera) speed / accel, normalized
    pitch = 13 * vy + 300 * ay                          # lean into acceleration, flare when braking
    pitch -= 9 * smooth(18, 26, f) * (1 - smooth(29, 33, f))   # wind-up lean back
    pitch = max(-16.0, min(24.0, pitch))
    roll = max(-24.0, min(24.0, 520.0 * d2(f, 0)))     # bank into the weave
    yaw = 0.45 * degrees(atan2(d1(f, 0), max(-d1(f, 1), 1e-4))) if -d1(f, 1) > 0.002 else 0.0
    root.location = P[f]
    root.rotation_euler = (radians(pitch), radians(roll), radians(yaw))
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)

# hover bob + wobble on FLY_Hover: livelier during the dash, calm while hovering
def env(f): return 0.3 + 0.7 * smooth(28, 36, f) * (1 - smooth(66, 96, f))
for f in range(F0 - 12, F1 + 13, 4):
    a = env(f)
    hover.location = (0.004 * a * sin(f * 0.21 + 1.0), 0.0, 0.007 * a * sin(f * 0.26) + 0.002 * sin(f * 0.61))
    hover.rotation_euler = (radians(1.8 * a * sin(f * 0.23 + 0.5)), radians(2.4 * a * sin(f * 0.17 + 2.0)),
                            radians(1.5 * a * sin(f * 0.11 + 1.3)))
    hover.keyframe_insert("location", frame=f)
    hover.keyframe_insert("rotation_euler", frame=f)

# propeller: idles while far, spins up during the wind-up, stays at full speed.
# 190 deg/frame on a 2-blade prop reads as a forward-drifting blur disc (avoids the wagon-wheel reverse look).
rotor = bpy.data.objects["Propeller_Rotor"]
rotor.animation_data_clear()
pref_interp('LINEAR')
ang = 0.0
for f in range(F0 - 12, F1 + 13):
    spd = 55.0 + (190.0 - 55.0) * smooth(16, 30, f)
    ang += spd
    if (f - F0) % 2 == 0 or f == F1 + 12:
        rotor.rotation_euler = (0, 0, radians(ang))
        rotor.keyframe_insert("rotation_euler", index=2, frame=f)

def all_fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action: return []
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return list(cb.fcurves) if cb else []
    except Exception:
        return list(getattr(ad.action, "fcurves", []))
for fc in all_fcurves(rotor):
    for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
for fc in all_fcurves(root):
    for kp in fc.keyframe_points: kp.handle_left_type = kp.handle_right_type = 'AUTO'
    fc.update()

# ---------------------------------------------------------------- studio
cyc = bpy.data.objects["Studio_Cyclorama"]
cyc.scale = (7.0, 7.0, 4.0)
fm = bpy.data.materials["M_Floor"]
for n in fm.node_tree.nodes:
    if n.bl_idname == "ShaderNodeTexNoise":
        n.inputs["Scale"].default_value *= 7.0
ld = bpy.data.lights.new("Light_Path", 'AREA'); ld.shape = 'RECTANGLE'; ld.size = 3.0; ld.size_y = 9.0
ld.energy = 260.0; ld.color = (0.9, 0.94, 1.0)
lp = bpy.data.objects.new("Light_Path", ld); lp.location = (0.2, 5.0, 3.2); C_STUDIO.objects.link(lp)
refl = bpy.data.objects.get("Light_Softbox_Reflect")
if refl: refl.data.energy = 6.0          # was whitening the screen during the flare

# ---------------------------------------------------------------- camera
tgt = bpy.data.objects.new("Target_Fly", None); tgt.location = (0, 0, 0.15); C_STUDIO.objects.link(tgt)
cd = bpy.data.cameras.new("CAM_FlyIn"); cam = bpy.data.objects.new("CAM_FlyIn", cd); C_CAMS.objects.link(cam)
tc = cam.constraints.new('TRACK_TO'); tc.target = tgt; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
cd.dof.use_dof = True; cd.dof.focus_object = hover
pref_interp('BEZIER')
for f, loc in ((F0, (0.06, -2.35, 0.06)), (F1, (0.0, -2.08, 0.10))):   # slow straight push-in
    cam.location = loc; cam.keyframe_insert("location", frame=f)
scene.camera = cam
bpy.context.view_layer.update()
if SKILL_SCRIPTS:
    g = {"CAM": dict(camera="CAM_FlyIn", series="signature", focal=75, tstop=5.6, mode="4.6K_16:9",
                     use_dof=True, shutter_angle=180), "bpy": bpy}
    exec(open(os.path.join(SKILL_SCRIPTS, "camera_preset.py")).read(), g)
    print(g.get("result", {}).get("warnings"))
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
scene.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst)
