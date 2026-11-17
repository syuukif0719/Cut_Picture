# Propeller Tablet — procedural build script (Blender 5.x, bpy)
# Usage: python build.py <out.blend>
# Units: meters (display mm). Front = -Y, Up = +Z. Body center at origin.
# All dimensions below are written in millimeters and converted with MM.
import bpy, bmesh, math, sys, os
from math import pi, sin, cos, tan, acos, atan2, radians
from mathutils import Vector

MM = 0.001
OUT = sys.argv[-1] if sys.argv[-1].endswith(".blend") else "/tmp/propeller_tablet.blend"
SKILL_SCRIPTS = os.environ.get("BPL_SCRIPTS", "")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.length_unit = 'MILLIMETERS'
scene.unit_settings.scale_length = 1.0

# ---------------------------------------------------------------- parameters
P = dict(
    W=320.0, H=230.0, D=65.0,           # body overall
    step_x=133.0, mod_top=53.0,         # right control module: main body right edge / module top
    seam_y=10.0, seam_gap=0.6,          # front/rear shell split
    r_front=8.0, r_back=8.0, r_seam=0.8,
    scr_cx=-15.0, scr_w=250.0, scr_h=185.0, scr_r=12.0,
    ctrl_x=137.5,
    prop_z=158.0, prop_span=400.0,
    pipe_r=8.5,
)
X0, X1 = -P['W'] / 2, P['W'] / 2
Z0, Z1 = -P['H'] / 2, P['H'] / 2
YF, YB = -P['D'] / 2, P['D'] / 2     # front face y, back face y
EMB = 0.5                            # embed depth for parts sitting on a surface (avoids coplanar faces)

# ---------------------------------------------------------------- collections
def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or scene.collection).children.link(c)
    return c

C_ROOT = coll("PropellerTablet")
C_BODY = coll("TAB_Body", C_ROOT)
C_SCREEN = coll("TAB_Screen", C_ROOT)
C_PROP = coll("TAB_Propeller", C_ROOT)
C_PIPES = coll("TAB_Pipes", C_ROOT)
C_CTRL = coll("TAB_Controls", C_ROOT)
C_LAMP = coll("TAB_Lamp", C_ROOT)
C_DET = coll("TAB_Details", C_ROOT)
C_CUT = coll("_Cutters")
C_STUDIO = coll("Studio")
C_CAMS = coll("Cameras")

# ---------------------------------------------------------------- materials
def _bsdf(m):
    try:
        m.use_nodes = True
    except Exception:
        pass
    return m.node_tree.nodes.get("Principled BSDF")

def _set(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val

def principled(name, color, rough, metallic=0.0, **kw):
    m = bpy.data.materials.new(name)
    b = _bsdf(m)
    _set(b, "Base Color", (*color, 1.0))
    _set(b, "Roughness", rough)
    _set(b, "Metallic", metallic)
    for k, v in kw.items():
        _set(b, k, v)
    m.diffuse_color = (*color, 1.0)
    m.roughness = rough
    return m

def micro_surface(m, rough, var=0.04, scale=3500.0, strength=0.12, dist=0.00003):
    """Very small bump (sub-mm noise) + gentle roughness variation."""
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N.get("Principled BSDF")
    tc = N.new("ShaderNodeTexCoord"); tc.location = (-1100, 0)
    n1 = N.new("ShaderNodeTexNoise"); n1.location = (-850, -250)
    n1.inputs["Scale"].default_value = scale
    n1.inputs["Detail"].default_value = 4.0
    bump = N.new("ShaderNodeBump"); bump.location = (-500, -250)
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = dist
    L.new(tc.outputs["Object"], n1.inputs["Vector"])
    L.new(n1.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    n2 = N.new("ShaderNodeTexNoise"); n2.location = (-850, 150)
    n2.inputs["Scale"].default_value = 45.0
    n2.inputs["Detail"].default_value = 2.0
    mr = N.new("ShaderNodeMapRange"); mr.location = (-500, 150)
    mr.inputs["To Min"].default_value = rough - var
    mr.inputs["To Max"].default_value = rough + var
    L.new(tc.outputs["Object"], n2.inputs["Vector"])
    L.new(n2.outputs["Fac"], mr.inputs["Value"])
    L.new(mr.outputs["Result"], b.inputs["Roughness"])
    return m

M = {}
M['ivory'] = micro_surface(principled("M_ABS_Ivory", (0.60, 0.52, 0.40), 0.44), 0.44)
M['ivory2'] = micro_surface(principled("M_ABS_Ivory_Sleeve", (0.56, 0.51, 0.43), 0.47), 0.47)
M['blue'] = micro_surface(principled("M_Resin_Blue", (0.012, 0.095, 0.70), 0.36), 0.36, var=0.03)
M['purple'] = micro_surface(principled("M_Resin_Purple", (0.25, 0.075, 0.62), 0.40), 0.40, var=0.03)
M['sil_lblue'] = micro_surface(principled("M_Silicone_LightBlue", (0.22, 0.42, 0.82), 0.58,
                                          **{"Subsurface Weight": 0.08}), 0.58, var=0.04, strength=0.2)
M['sil_blue'] = micro_surface(principled("M_Silicone_Blue", (0.015, 0.12, 0.72), 0.55,
                                         **{"Subsurface Weight": 0.05}), 0.55, var=0.04, strength=0.2)
M['red'] = micro_surface(principled("M_Silicone_Red", (0.62, 0.04, 0.03), 0.55), 0.55)
M['screen'] = principled("M_Screen_Glass", (0.004, 0.004, 0.0045), 0.10, **{"IOR": 1.52})
M['screen_bez'] = principled("M_Screen_Border_Black", (0.006, 0.006, 0.007), 0.35)
M['metal'] = principled("M_Metal_Screw", (0.78, 0.78, 0.80), 0.24, 1.0)
M['metal_dark'] = principled("M_Metal_Steel", (0.55, 0.56, 0.58), 0.32, 1.0)
M['glass'] = principled("M_Lamp_Glass", (1.0, 1.0, 1.0), 0.02,
                        **{"Transmission Weight": 1.0, "IOR": 1.5})
M['filament'] = principled("M_Filament_Emit", (0.9, 0.5, 0.2), 0.4,
                           **{"Emission Color": (1.0, 0.42, 0.10, 1.0), "Emission Strength": 40.0})
M['led'] = principled("M_LED_Pink", (0.9, 0.6, 0.95), 0.3,
                      **{"Emission Color": (1.0, 0.30, 0.85, 1.0), "Emission Strength": 7.0,
                         "Subsurface Weight": 0.3})
M['rubber'] = principled("M_Rubber_Foot", (0.03, 0.03, 0.03), 0.8)
M['floor'] = micro_surface(principled("M_Floor", (0.035, 0.037, 0.042), 0.62), 0.62, var=0.08,
                           scale=900.0, strength=0.25, dist=0.0002)

def blade_material():
    m = principled("M_Blade_Blue_Stripe", (0.012, 0.095, 0.70), 0.36)
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N.get("Principled BSDF")
    tc = N.new("ShaderNodeTexCoord"); tc.location = (-1300, 300)
    sep = N.new("ShaderNodeSeparateXYZ"); sep.location = (-1100, 300)
    L.new(tc.outputs["Object"], sep.inputs[0])
    # v = X + 0.9*Y  (diagonal stripes in blade local space, meters)
    mul = N.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 0.9
    add = N.new("ShaderNodeMath"); add.operation = 'ADD'
    L.new(sep.outputs["Y"], mul.inputs[0]); L.new(sep.outputs["X"], add.inputs[0]); L.new(mul.outputs[0], add.inputs[1])
    def band(a, bb, loc):
        g = N.new("ShaderNodeMath"); g.operation = 'GREATER_THAN'; g.inputs[1].default_value = a
        l = N.new("ShaderNodeMath"); l.operation = 'LESS_THAN'; l.inputs[1].default_value = bb
        mm = N.new("ShaderNodeMath"); mm.operation = 'MULTIPLY'
        L.new(add.outputs[0], g.inputs[0]); L.new(add.outputs[0], l.inputs[0])
        L.new(g.outputs[0], mm.inputs[0]); L.new(l.outputs[0], mm.inputs[1])
        return mm
    b1 = band(0.142, 0.151, 0); b2 = band(0.160, 0.169, 1)
    mx = N.new("ShaderNodeMath"); mx.operation = 'MAXIMUM'
    L.new(b1.outputs[0], mx.inputs[0]); L.new(b2.outputs[0], mx.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = 'RGBA'; mix.location = (-300, 300)
    ins = {s.identifier: s for s in mix.inputs}
    ins["A_Color"].default_value = (0.012, 0.095, 0.70, 1)
    ins["B_Color"].default_value = (0.30, 0.09, 0.66, 1)
    L.new(mx.outputs[0], ins["Factor_Float"])
    outs = {s.identifier: s for s in mix.outputs}
    L.new(outs["Result_Color"], b.inputs["Base Color"])
    micro_surface(m, 0.36, var=0.03)
    return m
M['blade'] = blade_material()

# ---------------------------------------------------------------- geometry helpers
def finish_mesh(name, verts_mm, faces, collection, mat=None, sharp_deg=38.0, wnormal=True, uv_fn=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(v) * MM for v in verts_mm], [], faces)
    me.validate(clean_customdata=False)
    me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    lim = radians(sharp_deg)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False
    if uv_fn:
        uvl = bm.loops.layers.uv.new("UVMap")
        for f in bm.faces:
            for lp in f.loops:
                lp[uvl].uv = uv_fn(lp.vert.co / MM)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    if wnormal:
        wn = ob.modifiers.new("WeightedNormal", 'WEIGHTED_NORMAL')
        wn.keep_sharp = True
    return ob

def _isect(a, e1, b, e2):
    cr = e1.x * e2.y - e1.y * e2.x
    if abs(cr) < 1e-12:
        return a.copy()
    w = b - a
    s = (w.x * e2.y - w.y * e2.x) / cr
    return a + e1 * s

def outline(poly, d, seg=10):
    """poly: CCW list of (u, v, radius) in mm. Returns rounded outline offset inward by d."""
    n = len(poly); pts = []
    Pv = [Vector((p[0], p[1])) for p in poly]
    for i in range(n):
        p0, p1, p2 = Pv[i - 1], Pv[i], Pv[(i + 1) % n]
        e1 = (p1 - p0).normalized(); e2 = (p2 - p1).normalized()
        n1 = Vector((-e1.y, e1.x)); n2 = Vector((-e2.y, e2.x))
        C = _isect(p0 + n1 * d, e1, p2 + n2 * d, e2)
        cross = e1.x * e2.y - e1.y * e2.x
        r = poly[i][2]
        reff = max((r - d) if cross > 0 else (r + d), 1e-4)
        phi = acos(max(-1.0, min(1.0, e1.dot(e2))))
        t = reff * tan(phi / 2)
        T1 = C - e1 * t; T2 = C + e2 * t
        O = T1 + n1 * reff if cross > 0 else T1 - n1 * reff
        a1 = atan2((T1 - O).y, (T1 - O).x); a2 = atan2((T2 - O).y, (T2 - O).x)
        da = a2 - a1
        while da > pi: da -= 2 * pi
        while da <= -pi: da += 2 * pi
        for k in range(seg + 1):
            a = a1 + da * k / seg
            pts.append((O.x + reff * cos(a), O.y + reff * sin(a)))
    return pts

def loft(loops, closed=False, cap_start=True, cap_end=True):
    verts = []; faces = []
    L = len(loops[0]); ns = len(loops)
    for lp in loops:
        assert len(lp) == L
        verts += lp
    rng = range(ns) if closed else range(ns - 1)
    for k in rng:
        k2 = (k + 1) % ns
        for i in range(L):
            j = (i + 1) % L
            faces.append((k * L + i, k * L + j, k2 * L + j, k2 * L + i))
    if not closed:
        if cap_start: faces.append(tuple(reversed(range(0, L))))
        if cap_end: faces.append(tuple(range((ns - 1) * L, ns * L)))
    return verts, faces

def _dedupe(prof):
    out = []
    for p in prof:
        if not out or abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6:
            out.append(p)
    return out

def slab_profile(y_back, y_front, r_back, r_front, steps=6):
    """(inset d, y) stations from back cap to front cap, quarter-round fillets on both ends."""
    sg = 1.0 if y_back > y_front else -1.0
    prof = []
    for k in range(steps + 1):
        th = (pi / 2) * k / steps
        prof.append((r_back * (1 - sin(th)), y_back - sg * r_back * (1 - cos(th))))
    for k in range(steps + 1):
        th = (pi / 2) * k / steps
        prof.append((r_front * (1 - cos(th)), y_front + sg * r_front * (1 - sin(th))))
    return _dedupe(prof)

def slab_xz(name, poly, y_back, y_front, r_back, r_front, coll_, mat, seg=10, steps=6, uv_fn=None, sharp=38):
    """Rounded slab: outline in XZ plane, thickness along Y."""
    loops = []
    for d, y in slab_profile(y_back, y_front, r_back, r_front, steps):
        loops.append([(u, y, v) for (u, v) in outline(poly, d, seg)])
    v, f = loft(loops)
    return finish_mesh(name, v, f, coll_, mat, uv_fn=uv_fn, sharp_deg=sharp)

def rect_poly(cx, cz, w, h, r):
    return [(cx - w / 2, cz - h / 2, r), (cx + w / 2, cz - h / 2, r), (cx + w / 2, cz + h / 2, r), (cx - w / 2, cz + h / 2, r)]

def lathe(profile, seg=48, closed=False):
    verts = []; rings = []
    for r, z in profile:
        if r < 1e-9:
            rings.append([len(verts)]); verts.append((0.0, 0.0, z))
        else:
            idx = []
            for i in range(seg):
                a = 2 * pi * i / seg
                idx.append(len(verts)); verts.append((r * cos(a), r * sin(a), z))
            rings.append(idx)
    faces = []
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for A, B in pairs:
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            faces += [(A[0], B[(i + 1) % seg], B[i]) for i in range(seg)]
        elif len(B) == 1:
            faces += [(A[i], A[(i + 1) % seg], B[0]) for i in range(seg)]
        else:
            faces += [(A[i], A[(i + 1) % seg], B[(i + 1) % seg], B[i]) for i in range(seg)]
    return verts, faces

def arc_pts(cr, cz, r, a0, a1, n):
    return [(cr + r * cos(radians(a0 + (a1 - a0) * k / n)), cz + r * sin(radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]

def rounded_cyl_profile(r, h, rf_bot=0.0, rf_top=1.0, z0=0.0, n=5):
    """Solid cylinder r x h starting at z0 with fillets."""
    pr = [(0.0, z0)]
    if rf_bot > 0:
        pr += arc_pts(r - rf_bot, z0 + rf_bot, rf_bot, -90, 0, n)
    else:
        pr += [(r, z0)]
    if rf_top > 0:
        pr += arc_pts(r - rf_top, z0 + h - rf_top, rf_top, 0, 90, n)
    else:
        pr += [(r, z0 + h)]
    pr += [(0.0, z0 + h)]
    return _dedupe(pr)

AXIS_ROT = {'+Z': (0, 0, 0), '-Y': (radians(90), 0, 0), '+Y': (radians(-90), 0, 0),
            '-X': (0, radians(-90), 0), '+X': (0, radians(90), 0), '-Z': (radians(180), 0, 0)}

def lathe_obj(name, profile, coll_, mat, loc_mm, axis='+Z', seg=48, closed=False, mesh=None, sharp=38):
    if mesh is None:
        v, f = lathe(profile, seg, closed)
        ob = finish_mesh(name, v, f, coll_, mat, sharp_deg=sharp)
    else:
        ob = bpy.data.objects.new(name, mesh); coll_.objects.link(ob)
        wn = ob.modifiers.new("WeightedNormal", 'WEIGHTED_NORMAL'); wn.keep_sharp = True
    ob.location = Vector(loc_mm) * MM
    ob.rotation_euler = AXIS_ROT[axis]
    return ob

def pipe_curve(name, pts_mm, radii_mm, coll_, mat, r_pipe):
    P = [Vector(p) for p in pts_mm]
    bez = []
    d0 = (P[1] - P[0]).normalized()
    bez.append((P[0], P[0] - d0, P[0] + d0))
    for i in range(1, len(P) - 1):
        din = (P[i] - P[i - 1]).normalized(); dout = (P[i + 1] - P[i]).normalized()
        R = radii_mm[i - 1]
        phi = acos(max(-1.0, min(1.0, din.dot(dout))))
        t = R * tan(phi / 2)
        hl = (4.0 / 3.0) * tan(phi / 4) * R
        T1 = P[i] - din * t; T2 = P[i] + dout * t
        bez.append((T1, T1 - din * hl, T1 + din * hl))
        bez.append((T2, T2 - dout * hl, T2 + dout * hl))
    dn = (P[-1] - P[-2]).normalized()
    bez.append((P[-1], P[-1] - dn, P[-1] + dn))
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 20
    cu.bevel_mode = 'ROUND'
    cu.bevel_depth = r_pipe * MM
    cu.bevel_resolution = 6
    cu.use_fill_caps = True
    cu.twist_mode = 'MINIMUM'
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(bez) - 1)
    for bp, (co, hl_, hr_) in zip(sp.bezier_points, bez):
        bp.handle_left_type = 'FREE'; bp.handle_right_type = 'FREE'
        bp.co = co * MM; bp.handle_left = hl_ * MM; bp.handle_right = hr_ * MM
    ob = bpy.data.objects.new(name, cu)
    coll_.objects.link(ob)
    cu.materials.append(mat)
    return ob

def poly_curve(name, pts_mm, coll_, mat, r_wire, cyclic=False):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'; cu.bevel_mode = 'ROUND'; cu.bevel_depth = r_wire * MM
    cu.bevel_resolution = 3; cu.use_fill_caps = True
    sp = cu.splines.new('POLY'); sp.points.add(len(pts_mm) - 1)
    for p, c in zip(sp.points, pts_mm):
        p.co = (c[0] * MM, c[1] * MM, c[2] * MM, 1.0)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu); coll_.objects.link(ob)
    cu.materials.append(mat)
    return ob

# ================================================================ 1. BODY
# Front-view outline (XZ, CCW). Right side: control module, narrower top step where the lamp sits.
BODY_POLY = [
    (X0, Z0, 22.0),
    (X1, Z0, 45.0),                 # big round lower-right (smiley button area)
    (X1, P['mod_top'], 13.0),       # module top-right
    (P['step_x'], P['mod_top'], 10.0),  # concave step
    (P['step_x'], Z1, 22.0),        # main body top-right
    (X0, Z1, 22.0),
]
sy, sg = P['seam_y'], P['seam_gap']
body = slab_xz("Body_Main", BODY_POLY, sy, YF, P['r_seam'], P['r_front'], C_BODY, M['ivory'], seg=12)
rear = slab_xz("Body_RearShell", BODY_POLY, YB, sy + sg, P['r_back'], P['r_seam'], C_BODY, M['ivory'], seg=12)

# Raised screen frame (ring) on the front face
scr_l, scr_r = P['scr_cx'] - P['scr_w'] / 2, P['scr_cx'] + P['scr_w'] / 2
scr_b, scr_t = -P['scr_h'] / 2, P['scr_h'] / 2
FR_OUT = [(scr_l - 9, scr_b - 12, 21.0), (scr_r + 9, scr_b - 12, 21.0), (scr_r + 9, scr_t + 9, 21.0), (scr_l - 9, scr_t + 9, 21.0)]
FR_IN = rect_poly(P['scr_cx'], 0.0, P['scr_w'], P['scr_h'], P['scr_r'])
y_fb, y_ftop = YF + EMB, YF - 3.5      # frame back (embedded) / frame top
loops = []
loops.append([(u, y_fb, v) for u, v in outline(FR_OUT, 0.0)])
for k in range(7):                      # outer fillet r=2.2
    th = (pi / 2) * k / 6; r = 2.2
    d = r * (1 - cos(th)); y = (y_ftop + r) - r * sin(th)
    loops.append([(u, y, v) for u, v in outline(FR_OUT, d)])
for k in range(5):                      # inner lip fillet r=1.0, going down into the recess
    th = (pi / 2) * k / 4; r = 1.0
    d = -r * (1 - sin(th)); y = y_ftop + r * (1 - cos(th))
    loops.append([(u, y, v) for u, v in outline(FR_IN, d)])
loops.append([(u, y_fb, v) for u, v in outline(FR_IN, 0.0)])
v, f = loft(loops, closed=True)
frame = finish_mesh("Body_ScreenFrame", v, f, C_BODY, M['ivory'])

# ================================================================ 2. SCREEN
gl_front = YF - 2.0
def scr_uv(co):
    return ((co.x - scr_l) / P['scr_w'], (co.z - scr_b) / P['scr_h'])
glass = slab_xz("Screen_Glass", rect_poly(P['scr_cx'], 0, P['scr_w'] - 0.6, P['scr_h'] - 0.6, P['scr_r'] - 0.3),
                YF + EMB, gl_front, 0.0, 0.6, C_SCREEN, M['screen'], seg=10, steps=3, uv_fn=scr_uv)

# ================================================================ 3. PROPELLER
mount = lathe_obj("Propeller_Mount", [(0, -EMB), (13.0, -EMB)] + arc_pts(11.0, 6.0, 2.0, 0, 90, 5) + [(0, 8.0)],
                  C_PROP, M['purple'], (0, 0, Z1))
collar = lathe_obj("Propeller_Collar", rounded_cyl_profile(8.5, 19.0, 0, 1.5, z0=7.5), C_PROP, M['ivory'], (0, 0, Z1))
shaft = lathe_obj("Propeller_Shaft", rounded_cyl_profile(3.6, 26.0, 0, 0.6, z0=25.0), C_PROP, M['metal_dark'], (0, 0, Z1))

rotor = bpy.data.objects.new("Propeller_Rotor", None)
rotor.empty_display_type = 'CIRCLE'; rotor.empty_display_size = 0.21
rotor.location = (0, 0, P['prop_z'] * MM)
C_PROP.objects.link(rotor)

def child(ob, parent):
    ob.parent = parent
    return ob

hub = child(lathe_obj("Propeller_Hub", rounded_cyl_profile(11.0, 15.0, 1.2, 1.2, z0=-7.5), C_PROP, M['purple'], (0, 0, 0)), rotor)
cap = child(lathe_obj("Propeller_Cap", rounded_cyl_profile(8.8, 6.0, 0, 1.0, z0=7.0), C_PROP, M['ivory'], (0, 0, 0)), rotor)
dome_prof = [(0, 12.5), (7.2, 12.5)] + arc_pts(0, 12.5, 7.2, 0, 90, 10)[1:]
dome = child(lathe_obj("Propeller_Dome_Glass", dome_prof, C_PROP, M['glass'], (0, 0, 0)), rotor)
bead_prof = [(0, 12.4)] + arc_pts(0, 15.0, 3.0, -60, 90, 8)
bead = child(lathe_obj("Propeller_Dome_Bead", bead_prof, C_PROP, M['metal'], (0, 0, 0)), rotor)

def blade_mesh():
    R0, R1 = 8.0, P['prop_span'] / 2
    NA, NS = 28, 44
    loops = []
    for s in range(NS):
        t = (s / (NS - 1))
        t = 1 - (1 - t) ** 1.35            # denser toward the tip
        t = min(t, 0.996)
        x = R0 + (R1 - R0) * t
        ss = min(t / 0.55, 1.0); ss = ss * ss * (3 - 2 * ss)
        chord = 11.0 + 31.0 * ss
        if t > 0.78:
            q = (t - 0.78) / 0.22
            chord *= math.sqrt(max(1 - q * q, 0.0)) * 0.97 + 0.03
        th = min(6.0 + (2.4 - 6.0) * t, 0.22 * chord + 0.4)
        tw = radians(15.0 + (5.0 - 15.0) * t)
        lp = []
        for i in range(NA):
            a = 2 * pi * i / NA
            yc = 0.5 * chord * cos(a)
            zc = 0.5 * th * sin(a) * (1.0 - 0.15 * (yc / (0.5 * chord + 1e-6)))  # slightly fuller leading edge
            zc += 0.06 * chord * (1 - (2 * yc / (chord + 1e-6)) ** 2) * 0.25      # mild camber
            y = yc * cos(tw) - zc * sin(tw)
            z = yc * sin(tw) + zc * cos(tw)
            lp.append((x, y, z))
        loops.append(lp)
    return loft(loops)
bv, bf = blade_mesh()
blade_R = finish_mesh("Propeller_Blade_R", bv, bf, C_PROP, M['blade'], sharp_deg=70)
blade_R.parent = rotor
sub = blade_R.modifiers.new("Subdivision", 'SUBSURF'); sub.levels = 1; sub.render_levels = 1
blade_R.modifiers.move(1, 0)
blade_L = bpy.data.objects.new("Propeller_Blade_L", blade_R.data)   # linked duplicate
C_PROP.objects.link(blade_L)
blade_L.parent = rotor; blade_L.rotation_euler = (0, 0, pi)
for m_ in blade_R.modifiers:
    nm = blade_L.modifiers.new(m_.name, m_.type)
    if m_.type == 'SUBSURF': nm.levels = 1; nm.render_levels = 1
    if m_.type == 'WEIGHTED_NORMAL': nm.keep_sharp = True

# spin animation (linear), rotor only
try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
except Exception:
    pass
scene.frame_start, scene.frame_end = 1, 48
rotor.rotation_euler = (0, 0, 0); rotor.keyframe_insert("rotation_euler", index=2, frame=1)
rotor.rotation_euler = (0, 0, 4 * pi); rotor.keyframe_insert("rotation_euler", index=2, frame=49)
rotor.rotation_euler = (0, 0, 0)
scene.frame_set(1)

# ================================================================ 4. PIPES
pr = P['pipe_r']
pipe_L = pipe_curve("Pipe_Handle_L", [(X0 + 3, 0, 55), (X0 - 25, 0, 55), (X0 - 25, 0, -65), (X0 + 3, 0, -65)], [15, 15], C_PIPES, M['blue'], pr)
pipe_R = pipe_curve("Pipe_Bend_R", [(X1 - 3, 0, 38), (X1 + 21, 0, 38), (X1 + 21, 0, -36), (X1 - 3, 0, -36)], [13, 13], C_PIPES, M['blue'], pr)
pipe_T = pipe_curve("Pipe_Top", [(48, 0, Z1 - 3), (48, 0, Z1 + 22), (116, 0, Z1 + 22), (116, 0, Z1 - 3)], [13, 13], C_PIPES, M['blue'], pr)

conn_prof = [(0, -EMB), (13.5, -EMB), (13.5, 1.6), (12.6, 2.4), (11.0, 2.6), (11.0, 11.0)] + arc_pts(10.0, 11.0, 1.0, 0, 90, 4)[1:] + [(0, 12.0)]
v, f = lathe(conn_prof, 40)
conn_me = finish_mesh("Pipe_Connector_mesh", v, f, C_PIPES, M['blue']).data
bpy.data.objects.remove(bpy.data.objects["Pipe_Connector_mesh"])
conn_me.name = "Pipe_Connector_Mesh"
for nm, loc, ax in [("Pipe_Conn_L_Top", (X0, 0, 55), '-X'), ("Pipe_Conn_L_Bot", (X0, 0, -65), '-X'),
                    ("Pipe_Conn_R_Top", (X1, 0, 38), '+X'), ("Pipe_Conn_R_Bot", (X1, 0, -36), '+X'),
                    ("Pipe_Conn_T_L", (48, 0, Z1), '+Z'), ("Pipe_Conn_T_R", (116, 0, Z1), '+Z')]:
    lathe_obj(nm, None, C_PIPES, None, loc, ax, mesh=conn_me)
sleeve_prof = arc_pts(9.8, -14.0 + 1.2, 1.2, -90, 0, 4) + arc_pts(9.8, 14.0 - 1.2, 1.2, 0, 90, 4) + [(pr + 0.15, 14.0), (pr + 0.15, -14.0)]
lathe_obj("Pipe_Sleeve_R", _dedupe(sleeve_prof), C_PIPES, M['ivory2'], (X1 + 21, 0, 1), '+Z', closed=True)

# ================================================================ 5. CONTROLS
cx = P['ctrl_x']
# speaker slits (boolean cutters, hidden)
for i, dx in enumerate((-6.5, 0.0, 6.5)):
    c = slab_xz(f"CUT_Speaker_{i}", rect_poly(cx + dx, 30.0, 3.6, 22.0, 1.75), YF + 3.0, YF - 1.5, 0, 0, C_CUT, None, seg=6)
    c.modifiers.clear()
bo = body.modifiers.new("Speaker_Slits", 'BOOLEAN'); bo.operation = 'DIFFERENCE'
bo.operand_type = 'COLLECTION'; bo.collection = None
C_SPK = bpy.data.collections.new("CUT_Speaker"); C_CUT.children.link(C_SPK)
for o in list(C_CUT.objects):
    if o.name.startswith("CUT_Speaker"):
        C_CUT.objects.unlink(o); C_SPK.objects.link(o)
bo.collection = C_SPK
try: bo.solver = 'EXACT'
except Exception: pass
bev = body.modifiers.new("Bevel_SlitEdges", 'BEVEL'); bev.limit_method = 'ANGLE'
bev.angle_limit = radians(50); bev.width = 0.45 * MM; bev.segments = 2; bev.harden_normals = False
body.modifiers.move(body.modifiers.find("WeightedNormal"), len(body.modifiers) - 1)

# X button (silicone)
a, Lx = 4.8, 15.0
plus = [(-a, -Lx, 3.6), (a, -Lx, 3.6), (a, -a, 1.6), (Lx, -a, 3.6), (Lx, a, 3.6), (a, a, 1.6),
        (a, Lx, 3.6), (-a, Lx, 3.6), (-a, a, 1.6), (-Lx, a, 3.6), (-Lx, -a, 3.6), (-a, -a, 1.6)]
c45, s45 = cos(pi / 4), sin(pi / 4)
plus = [(cx + u * c45 - v * s45, -10.0 + u * s45 + v * c45, r) for u, v, r in plus]
slab_xz("Button_X", plus, YF + EMB, YF - 5.0, 0.0, 2.4, C_CTRL, M['sil_lblue'], seg=8)

# Smile button: ring bezel + domed silicone disc + raised smile mark
sz = -58.0
ring_prof = [(12.6, -EMB), (17.5, -EMB)] + arc_pts(16.5, 2.0, 1.0, 0, 90, 4) + arc_pts(13.6, 2.0, 1.0, 90, 180, 4) + [(12.6, -EMB)]
lathe_obj("Button_Smile_Ring", _dedupe(ring_prof[:-1]), C_CTRL, M['blue'], (cx, YF, sz), '-Y', closed=True, seg=64)
btn_prof = [(0, -EMB), (12.4, -EMB)] + arc_pts(10.6, 4.8, 1.8, 0, 90, 6)[:-1] + [(5.0, 6.75), (0, 6.85)]
lathe_obj("Button_Smile", btn_prof, C_CTRL, M['sil_blue'], (cx, YF, sz), '-Y', seg=64, sharp=60)
ym = YF - 6.75
eye_prof = [(0, -0.3)] + [(1.0 * cos(t), 0.55 * sin(t)) for t in [radians(x) for x in (0, 30, 60, 90)]][0:3] + [(0, 0.55)]
for nm, dx in (("Button_Smile_EyeL", -3.9), ("Button_Smile_EyeR", 3.9)):
    e = lathe_obj(nm, [(0, -0.3), (1.0, -0.3), (0.95, 0.25), (0.6, 0.5), (0, 0.6)], C_CTRL, M['sil_lblue'], (cx + dx, ym, sz + 2.2), '-Y', seg=24, sharp=70)
    e.scale = (1.0, 1.6, 1.0)
mouth = [(cx + 6.2 * cos(radians(t)), ym + 0.05, sz + 0.4 + 6.2 * sin(radians(t))) for t in range(205, 336, 8)]
mo = poly_curve("Button_Smile_Mouth", mouth, C_CTRL, M['sil_lblue'], 0.75)
mo.data.splines[0].type = 'NURBS'; mo.data.splines[0].use_endpoint_u = True; mo.data.splines[0].order_u = 3

# Power button on the left side
pw_ring = [(3.6, -EMB), (6.8, -EMB)] + arc_pts(6.0, 1.6, 0.8, 0, 90, 4) + arc_pts(4.4, 1.6, 0.8, 90, 180, 4)
lathe_obj("Button_Power_Ring", _dedupe(pw_ring), C_CTRL, M['red'], (X0, 0, 82), '-X', closed=True, seg=48)
lathe_obj("Button_Power", [(0, -EMB), (3.7, -EMB)] + arc_pts(2.9, 2.0, 0.8, 0, 90, 4) + [(0, 2.9)], C_CTRL, M['ivory'], (X0, 0, 82), '-X', seg=48)

# ================================================================ 6. LAMP
lx, lz = (P['step_x'] + X1) / 2, P['mod_top']
sock = [(0, -EMB), (12.6, -EMB), (12.6, 2.8), (12.1, 3.5), (11.2, 3.5), (11.2, 5.0), (12.0, 5.7), (12.0, 8.8),
        (11.2, 9.5), (11.2, 11.0), (12.0, 11.7), (12.0, 14.4), (11.3, 15.5), (0, 15.5)]
lathe_obj("Lamp_Socket", sock, C_LAMP, M['purple'], (lx, 0, lz), seg=56, sharp=30)
ro, ri, zb, zc = 10.0, 9.0, 13.5, 49.0
gprof = [(ro, zb)] + arc_pts(0, zc, ro, 0, 90, 14) + arc_pts(0, zc - 0.3, ri, 90, 0, 14) + [(ri, zb)]
lathe_obj("Lamp_Glass", _dedupe(gprof), C_LAMP, M['glass'], (lx, 0, lz), seg=56, closed=True, sharp=80)
lathe_obj("Lamp_Stem", [(0, 14.0), (2.6, 14.0), (1.2, 21.0), (0, 21.5)], C_LAMP, M['glass'], (lx, 0, lz), seg=24)
fil = []
xs = (-3.0, -1.0, 1.0, 3.0)
for i, x in enumerate(xs):
    zs = (24.0, 46.0) if i % 2 == 0 else (46.0, 24.0)
    fil += [(lx + x, 0, lz + zs[0]), (lx + x, 0, lz + zs[1])]
poly_curve("Lamp_Filament", fil, C_LAMP, M['filament'], 0.33)
poly_curve("Lamp_Support_L", [(lx - 3, 0, lz + 15.5), (lx - 3, 0, lz + 24.2)], C_LAMP, M['metal_dark'], 0.25)
poly_curve("Lamp_Support_R", [(lx + 3, 0, lz + 15.5), (lx + 3, 0, lz + 24.2)], C_LAMP, M['metal_dark'], 0.25)
poly_curve("Lamp_Support_Top", [(lx, 0, lz + 21.0), (lx, 0, lz + 47.5), (lx - 3, 0, lz + 46.6), (lx + 3, 0, lz + 46.6)], C_LAMP, M['metal_dark'], 0.18)

# ================================================================ 7. DETAILS
# LED strip on the lower frame border
slab_xz("LED_Strip", rect_poly(P['scr_cx'], scr_b - 6.0, 34.0, 4.0, 1.99), y_ftop + EMB, y_ftop - 0.8, 0.0, 0.6, C_DET, M['led'], seg=8, steps=3)

# Screw head (shared mesh, Phillips recess cut once at build time)
sh = [(0, 0), (4.4, 0), (4.4, 0.5)] + [(4.4 * cos(t), 0.5 + 1.8 * sin(t)) for t in [radians(x) for x in range(10, 91, 10)]]
v, f = lathe(_dedupe(sh), 40)
tmp = finish_mesh("_screw_tmp", v, f, C_DET, M['metal'], wnormal=False)
for i, (w, l) in enumerate(((1.1, 5.6), (5.6, 1.1))):
    # cutter: box spanning z 1.25..3 mm (head local space)
    cme = bpy.data.meshes.new(f"_screw_cut{i}")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vv in bm.verts:
        vv.co.x *= w * MM; vv.co.y *= l * MM; vv.co.z = (1.25 if vv.co.z < 0 else 3.0) * MM
    bm.to_mesh(cme); bm.free()
    c = bpy.data.objects.new(f"_screw_cut{i}", cme); C_CUT.objects.link(c)
    b_ = tmp.modifiers.new(f"cross{i}", 'BOOLEAN'); b_.object = c; b_.operation = 'DIFFERENCE'
    try: b_.solver = 'EXACT'
    except Exception: pass
dg = bpy.context.evaluated_depsgraph_get()
screw_me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
screw_me.name = "Screw_Head_Mesh"
screw_me.materials.clear(); screw_me.materials.append(M['metal'])
for o in [tmp] + [bpy.data.objects[n] for n in ("_screw_cut0", "_screw_cut1")]:
    bpy.data.objects.remove(o)
SCREWS = [(-148.0, 103.0), (121.0, 104.0), (-148.0, -103.0), (134.0, -102.0)]
for i, (x, z) in enumerate(SCREWS):
    lathe_obj(f"Screw_F_{i}", None, C_DET, None, (x, YF + 0.3, z), '-Y', mesh=screw_me)
    lathe_obj(f"Screw_B_{i}", None, C_DET, None, (x, YB - 0.3, z), '+Y', mesh=screw_me)

# Back panel (label plate) and vent slits on the rear shell
slab_xz("Body_BackPanel", rect_poly(-14.0, -39.0, 112.0, 60.0, 5.0), YB - EMB, YB + 0.8, 0.0, 0.5, C_DET, M['ivory'], seg=6, steps=3)
C_VENT = bpy.data.collections.new("CUT_Vents"); C_CUT.children.link(C_VENT)
for i in range(5):
    c = slab_xz(f"CUT_Vent_{i}", rect_poly(84.0, -62.0 + (i - 2) * 6.2, 28.0, 3.0, 1.45), YB - 2.5, YB + 1.5, 0, 0, C_VENT, None, seg=6)
    c.modifiers.clear()
bo = rear.modifiers.new("Vent_Slits", 'BOOLEAN'); bo.operation = 'DIFFERENCE'
bo.operand_type = 'COLLECTION'; bo.collection = C_VENT
try: bo.solver = 'EXACT'
except Exception: pass
bev = rear.modifiers.new("Bevel_SlitEdges", 'BEVEL'); bev.limit_method = 'ANGLE'
bev.angle_limit = radians(50); bev.width = 0.4 * MM; bev.segments = 2
rear.modifiers.move(rear.modifiers.find("WeightedNormal"), len(rear.modifiers) - 1)

# Rubber feet
for i, (x, y) in enumerate(((-120, -18), (-120, 18), (110, -18), (110, 18))):
    lathe_obj(f"Foot_{i}", rounded_cyl_profile(5.5, 2.0, 0.0, 0.8, z0=0.0), C_DET, M['rubber'], (x, y, Z0 + EMB), '-Z', seg=32)

for o in C_CUT.all_objects:
    o.hide_render = True; o.hide_viewport = True; o.display_type = 'WIRE'
C_CUT.hide_render = True

# ================================================================ 8. STUDIO
floor_z = Z0 - 2.0 + EMB
bpy.ops.mesh.primitive_plane_add(size=60.0, location=(0, 0, floor_z * MM))
floor = bpy.context.active_object; floor.name = "Studio_Floor"
for c_ in floor.users_collection: c_.objects.unlink(floor)
C_STUDIO.objects.link(floor); floor.data.materials.append(M['floor'])

target = bpy.data.objects.new("Target_Center", None); target.location = (0, 0, 0.025)
C_STUDIO.objects.link(target)

def area(name, loc, size, power, shape='SQUARE', size_y=None, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = power; ld.shape = shape; ld.size = size
    if size_y: ld.size_y = size_y
    ld.color = color
    ob = bpy.data.objects.new(name, ld); ob.location = loc; C_STUDIO.objects.link(ob)
    tc = ob.constraints.new('TRACK_TO'); tc.target = target; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    return ob
area("Light_Key", (-0.85, -1.05, 0.95), 0.55, 75.0, color=(1.0, 0.97, 0.93))
area("Light_Rim", (1.05, 0.75, 0.35), 0.12, 70.0, shape='RECTANGLE', size_y=0.9, color=(0.92, 0.96, 1.0))
area("Light_Fill", (1.3, -1.0, 0.15), 1.4, 5.0, color=(0.95, 0.97, 1.0))

world = bpy.data.worlds.new("World_Studio"); scene.world = world
try: world.use_nodes = True
except Exception: pass
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.012, 0.013, 0.016, 1); bg.inputs["Strength"].default_value = 1.0

# ================================================================ 9. CAMERAS (ARRI ALEXA 35 + Signature Prime 75mm, T5.6)
scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
D = 1.6; D3 = 1.75; zc = 0.02
CAMS = {
    "CAM_Front": (0, -D, zc),
    "CAM_Back": (0, D, zc),
    "CAM_Left": (-D, 0, zc),
    "CAM_Right": (D, 0, zc),
    "CAM_3Q_FrontRight": (D3 * sin(radians(45)) * cos(radians(14)), -D3 * cos(radians(45)) * cos(radians(14)), zc + D3 * sin(radians(14))),
    "CAM_3Q_BackLeft": (-D3 * sin(radians(45)) * cos(radians(14)), D3 * cos(radians(45)) * cos(radians(14)), zc + D3 * sin(radians(14))),
}
for nm, loc in CAMS.items():
    cd = bpy.data.cameras.new(nm)
    co = bpy.data.objects.new(nm, cd); co.location = loc; C_CAMS.objects.link(co)
    tc = co.constraints.new('TRACK_TO'); tc.target = target; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
    cd.dof.use_dof = True; cd.dof.focus_object = target
    scene.camera = co
    bpy.context.view_layer.update()
    if SKILL_SCRIPTS:
        g = {"CAM": dict(camera=nm, series="signature", focal=75, tstop=5.6, mode="4.6K_16:9", use_dof=True), "bpy": bpy}
        exec(open(os.path.join(SKILL_SCRIPTS, "camera_preset.py")).read(), g)
        print(nm, g.get("result"))
    else:
        cd.sensor_fit = 'HORIZONTAL'; cd.sensor_width = 27.99; cd.lens = 75; cd.dof.aperture_fstop = 5.6
scene.camera = bpy.data.objects["CAM_3Q_FrontRight"]

# ================================================================ 10. RENDER SETTINGS (check level)
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 128
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 12
scene.cycles.transmission_bounces = 12
scene.cycles.glossy_bounces = 6
try:
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception as e:
    print("look:", e)
scene.render.film_transparent = False

os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("SAVED", OUT, "objects:", len(bpy.data.objects))
