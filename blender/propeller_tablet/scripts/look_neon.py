# Look test: pure black background, "NIGHT HIKE" neon sign (placeholder lettering, single-stroke tubes)
# behind/above the tablet; the neon light is what lights the subject.
# Usage: python look_neon.py <in.blend (studio version)> <out.blend>
# env: NEON_W (emission strength, default 30), FILL_W (neutral front fill, default 1.5)
import bpy, bmesh, sys, os, math
from mathutils import Vector
from math import radians, sin, cos, pi

src, dst = sys.argv[-2], sys.argv[-1]
SKILL_SCRIPTS = os.environ.get("BPL_SCRIPTS", "")
bpy.ops.wm.open_mainfile(filepath=src)
s = bpy.context.scene
for nm in ("Studio_Cyclorama", "Light_Path", "Light_Softbox_Reflect", "Light_Key", "Light_Rim"):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True; o.hide_viewport = True
fill = bpy.data.objects.get("Light_Fill")
if fill: fill.data.energy = float(os.environ.get("FILL_W", 1.5))
w = bpy.data.worlds.new("World_Black"); s.world = w
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0

C = bpy.data.collections.new("ENV_Neon"); s.collection.children.link(C)

# ---- neon materials: saturated emissive tube (the glass core reads almost white when it clips, like real neon)
NEON_W = float(os.environ.get("NEON_W", 1.0))
def neon_mat(name, col):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = 0.15
    b.inputs["Emission Color"].default_value = (*col, 1); b.inputs["Emission Strength"].default_value = NEON_W
    return m
M_PINK = neon_mat("ENV_Neon_Pink", (1.0, 0.12, 0.45))
M_BLUE = neon_mat("ENV_Neon_Cyan", (0.08, 0.55, 1.0))
M_CAP = bpy.data.materials.new("ENV_Neon_Electrode")
M_CAP.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1)

# ---- single-stroke letters on a unit grid (x 0..width, y 0..1). Each letter = list of strokes (polylines).
def arc(cx, cy, rx, ry, a0, a1, n=14):
    return [(cx + rx * cos(radians(a0 + (a1 - a0) * k / n)), cy + ry * sin(radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
GLYPHS = {
    "N": (0.62, [[(0, 0), (0, 1), (0.62, 0), (0.62, 1)]]),
    "I": (0.0, [[(0, 0), (0, 1)]]),
    "G": (0.66, [arc(0.33, 0.5, 0.33, 0.5, 42, 360) + [(0.66, 0.42), (0.36, 0.42)]]),
    "H": (0.6, [[(0, 0), (0, 1)], [(0.6, 0), (0.6, 1)], [(0, 0.52), (0.6, 0.52)]]),
    "T": (0.62, [[(0, 1), (0.62, 1)], [(0.31, 1), (0.31, 0)]]),
    "K": (0.56, [[(0, 0), (0, 1)], [(0.56, 1), (0.02, 0.42)], [(0.2, 0.61), (0.58, 0)]]),
    "E": (0.52, [[(0.52, 1), (0, 1), (0, 0), (0.52, 0)], [(0, 0.52), (0.42, 0.52)]]),
}
def rounded(pts, r):
    """Round sharp corners of a polyline with radius r (unit grid), like bent glass tube."""
    if len(pts) < 3: return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[i + 1])
        a, b = (p0 - p1), (p2 - p1)
        if a.length < 1e-6 or b.length < 1e-6: continue
        ang = a.angle(b)
        if ang > radians(160):                       # nearly straight (arc samples): keep as is
            out.append(pts[i]); continue
        t = min(r / math.tan(ang / 2), a.length * 0.45, b.length * 0.45)
        q0, q2 = p1 + a.normalized() * t, p1 + b.normalized() * t
        for k in range(7):                           # quadratic bezier corner
            u = k / 6
            q = (1 - u) ** 2 * q0 + 2 * (1 - u) * u * p1 + u * u * q2
            out.append((q.x, q.y))
    out.append(pts[-1])
    return out

H_LET, TRACK, SPACE = 0.13, 0.30, 0.45        # letter height (m), gap between letters / word space (in letter-heights)
TUBE_R = 0.0055
SIGN_Y, SIGN_Z = 0.55, 0.44                   # sign plane: behind the subject, above it
def build_word(word, mat, x_start):
    x = x_start
    for ch in word:
        wdt, strokes = GLYPHS[ch]
        for si, st in enumerate(strokes):
            pts = rounded(st, 0.10)
            cu = bpy.data.curves.new(f"NEON_{ch}", 'CURVE'); cu.dimensions = '3D'
            cu.bevel_mode = 'ROUND'; cu.bevel_depth = TUBE_R; cu.bevel_resolution = 4; cu.use_fill_caps = True
            sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
            for p, (u, v) in zip(sp.points, pts):
                p.co = (x + u * H_LET, SIGN_Y, SIGN_Z + v * H_LET, 1.0)
            cu.materials.append(mat)
            ob = bpy.data.objects.new(f"ENV_Neon_{word}_{ch}_{si}", cu); C.objects.link(ob)
            for (u, v) in (pts[0], pts[-1]):          # dark electrode sleeves at the tube ends, bent back to the wall
                me = bpy.data.meshes.new("cap"); bm = bmesh.new()
                bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=TUBE_R * 1.25, radius2=TUBE_R * 1.25, depth=0.035)
                for vv in bm.verts: vv.co = Vector((vv.co.x, vv.co.z, vv.co.y)) + Vector((x + u * H_LET, SIGN_Y + 0.0175, SIGN_Z + v * H_LET))
                bm.to_mesh(me); bm.free(); me.materials.append(M_CAP)
                co = bpy.data.objects.new("ENV_Neon_Electrode", me); C.objects.link(co)
        x += (wdt + TRACK) * H_LET
    return x
def word_w(word):
    return sum((GLYPHS[c][0] + TRACK) * H_LET for c in word) - TRACK * H_LET
total = word_w("NIGHT") + SPACE * H_LET + word_w("HIKE")
x0 = -total / 2
x1 = build_word("NIGHT", M_PINK, x0)
build_word("HIKE", M_BLUE, x1 - TRACK * H_LET + SPACE * H_LET)

# ---- the sign's light on the subject: one soft panel per word, same colour, invisible to camera and reflections
def word_light(name, cx, width, col, watts):
    ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'; ld.size = width; ld.size_y = H_LET
    ld.energy = watts; ld.color = col
    ob = bpy.data.objects.new(name, ld); C.objects.link(ob)
    ob.location = (cx, SIGN_Y - 0.01, SIGN_Z + H_LET / 2)
    ob.rotation_euler = (radians(-90), 0, 0)         # light emits along local -Z -> -Y (toward the tablet)
    ob.visible_camera = False; ob.visible_glossy = False
    return ob
wN, wH = word_w("NIGHT"), word_w("HIKE")
NEON_L = float(os.environ.get("NEON_LIGHT_W", 120))
word_light("Light_Neon_NIGHT", x0 + wN / 2, wN, (1.0, 0.12, 0.45), NEON_L)
word_light("Light_Neon_HIKE", x0 + total - wH / 2, wH, (0.08, 0.55, 1.0), NEON_L)

# ---- very light glow on the tubes (compositor fog glow, kept weak). Off by default: the 5.x compositor needs a GPU
#      context, which headless renders here don't have -> the glow is added in post instead (see neon_glow step).
try:
    if os.environ.get("NEON_GLARE") != "1": raise RuntimeError("disabled (NEON_GLARE!=1)")
    ng = bpy.data.node_groups.new("Comp_NeonGlow", "CompositorNodeTree")
    s.compositing_node_group = ng
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    out = ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    go = ng.nodes.new("NodeGroupOutput")
    def setin(node, names, val):
        for nm_ in names:
            if nm_ in node.inputs: node.inputs[nm_].default_value = val; return True
        return False
    try: gl.glare_type = 'FOG_GLOW'
    except Exception: setin(gl, ["Type"], 'Fog Glow')
    setin(gl, ["Threshold"], 1.0); setin(gl, ["Strength"], 0.35); setin(gl, ["Size"], 0.55)
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"]); ng.links.new(gl.outputs["Image"], go.inputs[0])
    print("glare ok", [i.name for i in gl.inputs])
except Exception as e:
    print("glare skipped:", e)

# ---- still camera for this look: 47 mm, a bit further back so the sign reads above the tablet
cd = bpy.data.cameras.new("CAM_Neon"); cam = bpy.data.objects.new("CAM_Neon", cd)
bpy.data.collections["Cameras"].objects.link(cam)
cam.location = (0.0, -2.15, 0.22)
aim = bpy.data.objects.new("Target_Neon", None); aim.location = (0.0, 0.3, 0.30); C.objects.link(aim)
tc = cam.constraints.new('TRACK_TO'); tc.target = aim; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
cd.dof.use_dof = True; cd.dof.focus_object = bpy.data.objects.get("FLY_Hover")
s.camera = cam
bpy.context.view_layer.update()
if SKILL_SCRIPTS:
    g = {"CAM": dict(camera="CAM_Neon", series="signature", focal=47, tstop=4.0, mode="4.6K_16:9", use_dof=True), "bpy": bpy}
    exec(open(os.path.join(SKILL_SCRIPTS, "camera_preset.py")).read(), g)
    print(g.get("result", {}).get("warnings"))
else:
    cd.sensor_width = 27.99; cd.lens = 47; cd.dof.aperture_fstop = 4.0
s.view_settings.exposure = 0.0
s.frame_set(s.frame_end)
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst, "sign width %.2f m" % total)
