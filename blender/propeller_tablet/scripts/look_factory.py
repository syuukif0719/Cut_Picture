# Look test: factory interior (procedural). Big room, concrete floor, steel columns/beams,
# tall back windows with sun shafts through light haze, hanging lamps, crates/shelves.
# Usage: python look_factory.py <in.blend (studio version)> <out.blend>
import bpy, bmesh, sys, os, math
from mathutils import Vector
from math import radians

src, dst = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=src)
s = bpy.context.scene
for nm in ("Studio_Cyclorama", "Light_Path", "Light_Softbox_Reflect"):
    o = bpy.data.objects.get(nm)
    if o: o.hide_render = True; o.hide_viewport = True

C = bpy.data.collections.new("ENV_Factory"); s.collection.children.link(C)
FLOOR, CEIL = -0.75, 8.0
YB, YF, XW = 13.0, -7.0, 14.0       # back wall y, front wall y, half width

def mat(name, col, rough, metal=0.0, emit=None, strength=0.0, noise=None):
    m = bpy.data.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1); b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = strength
    if noise:   # (scale, dark factor, bump) : grime/variation for concrete etc.
        N, L = m.node_tree.nodes, m.node_tree.links
        tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = noise[0]; nz.inputs["Detail"].default_value = 10
        cr = N.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].color = (col[0] * noise[1], col[1] * noise[1], col[2] * noise[1], 1)
        cr.color_ramp.elements[1].color = (*col, 1)
        L.new(tc.outputs["Object"], nz.inputs["Vector"]); L.new(nz.outputs["Fac"], cr.inputs["Fac"])
        L.new(cr.outputs["Color"], b.inputs["Base Color"])
        rr = N.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = rough - 0.12; rr.inputs["To Max"].default_value = rough + 0.08
        L.new(nz.outputs["Fac"], rr.inputs["Value"]); L.new(rr.outputs["Result"], b.inputs["Roughness"])
        bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = noise[2]
        nz2 = N.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = noise[0] * 30
        L.new(tc.outputs["Object"], nz2.inputs["Vector"]); L.new(nz2.outputs["Fac"], bp.inputs["Height"])
        L.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m

M_CONC = mat("ENV_Concrete_Floor", (0.16, 0.155, 0.145), 0.62, noise=(1.2, 0.55, 0.25))
M_WALL = mat("ENV_Wall_Concrete", (0.15, 0.145, 0.135), 0.85, noise=(0.8, 0.6, 0.3))
M_STEEL = mat("ENV_Steel_Painted", (0.045, 0.06, 0.075), 0.45)
M_STEEL_Y = mat("ENV_Steel_Yellow", (0.55, 0.36, 0.03), 0.5)
M_FRAME = mat("ENV_Window_Frame", (0.02, 0.022, 0.025), 0.4, metal=1.0)
M_WOOD = mat("ENV_Crate_Wood", (0.17, 0.11, 0.055), 0.75, noise=(4.0, 0.6, 0.2))
M_SHADE = mat("ENV_Lamp_Shade", (0.03, 0.035, 0.03), 0.35, metal=1.0)
M_BULB = mat("ENV_Lamp_Bulb", (1, 0.9, 0.7), 0.3, emit=(1.0, 0.72, 0.42), strength=40.0)

def box(name, cx, cy, cz, sx, sy, sz, m):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts: v.co = Vector((v.co.x * sx + cx, v.co.y * sy + cy, v.co.z * sz + cz))
    bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); C.objects.link(o); return o

def cyl(name, cx, cy, cz, r, h, m, seg=32):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    for v in bm.verts: v.co += Vector((cx, cy, cz))
    for f in bm.faces: f.smooth = True
    bm.to_mesh(me); bm.free(); me.materials.append(m)
    o = bpy.data.objects.new(name, me); C.objects.link(o); return o

H = CEIL - FLOOR
# shell: floor, ceiling, side + front walls
box("ENV_Floor", 0, (YB + YF) / 2, FLOOR - 0.1, 2 * XW + 2, YB - YF + 2, 0.2, M_CONC)
box("ENV_Ceiling", 0, (YB + YF) / 2, CEIL + 0.1, 2 * XW + 2, YB - YF + 2, 0.2, M_WALL)
box("ENV_Wall_L", -XW - 0.15, (YB + YF) / 2, (FLOOR + CEIL) / 2, 0.3, YB - YF, H, M_WALL)
box("ENV_Wall_R", XW + 0.15, (YB + YF) / 2, (FLOOR + CEIL) / 2, 0.3, YB - YF, H, M_WALL)
box("ENV_Wall_Front", 0, YF - 0.15, (FLOOR + CEIL) / 2, 2 * XW, 0.3, H, M_WALL)
# back wall with a band of tall windows (real openings, so the sun can come through)
WZ0, WZ1 = 0.9, 5.6
box("ENV_BackWall_Low", 0, YB + 0.2, (FLOOR + WZ0) / 2, 2 * XW, 0.4, WZ0 - FLOOR, M_WALL)
box("ENV_BackWall_High", 0, YB + 0.2, (WZ1 + CEIL) / 2, 2 * XW, 0.4, CEIL - WZ1, M_WALL)
WIN_W, PIER = 3.2, 1.2
xs = []
x = -XW
while x < XW - 0.01:
    xs.append(x); x += WIN_W + PIER
for i, x0 in enumerate(xs):
    box(f"ENV_BackWall_Pier_{i}", x0 + PIER / 2, YB + 0.2, (WZ0 + WZ1) / 2, PIER, 0.4, WZ1 - WZ0, M_WALL)
    wx0, wx1 = x0 + PIER, min(x0 + PIER + WIN_W, XW)
    if wx1 - wx0 < 0.5: continue
    for k in range(1, 4):                                   # vertical mullions
        mx = wx0 + (wx1 - wx0) * k / 4
        box(f"ENV_Mullion_V_{i}_{k}", mx, YB + 0.05, (WZ0 + WZ1) / 2, 0.06, 0.08, WZ1 - WZ0, M_FRAME)
    for k in range(1, 6):                                   # horizontal mullions
        mz = WZ0 + (WZ1 - WZ0) * k / 6
        box(f"ENV_Mullion_H_{i}_{k}", (wx0 + wx1) / 2, YB + 0.05, mz, wx1 - wx0, 0.08, 0.05, M_FRAME)
# steel columns (H-section) and roof beams
def h_column(name, cx, cy, m):
    hgt = CEIL - FLOOR
    box(name + "_Web", cx, cy, FLOOR + hgt / 2, 0.02, 0.30, hgt, m)
    box(name + "_FlA", cx - 0.15, cy, FLOOR + hgt / 2, 0.02, 0.30, hgt, m).scale = (1, 1, 1)
    box(name + "_FlB", cx + 0.15, cy, FLOOR + hgt / 2, 0.02, 0.30, hgt, m)
for j, (cy, cxx) in enumerate(((5.0, 1.75), (9.5, 2.6), (1.0, 3.4))):
    for side in (-1, 1):
        h_column(f"ENV_Column_{j}_{'L' if side < 0 else 'R'}", side * cxx, cy, M_STEEL)
    box(f"ENV_Beam_{j}", 0, cy, CEIL - 1.6, 2 * XW, 0.25, 0.5, M_STEEL)
box("ENV_Crane_Rail", 0, 8.0, CEIL - 2.6, 2 * XW, 0.35, 0.35, M_STEEL_Y)
# hanging lamps
for j, cy in enumerate((4.0, 7.5, 11.5)):
    for i, cx in enumerate((-1.1, 1.1)):
        cz = 1.25 + 0.3 * j
        cyl(f"ENV_Lamp_Cord_{j}_{i}", cx, cy, (cz + CEIL) / 2, 0.006, CEIL - cz, M_SHADE, seg=8)
        sh = bpy.data.meshes.new("shade"); bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=False, segments=32, radius1=0.30, radius2=0.08, depth=0.28)
        for v in bm.verts: v.co += Vector((cx, cy, cz - 0.1))
        for f in bm.faces: f.smooth = True
        bm.to_mesh(sh); bm.free(); sh.materials.append(M_SHADE)
        so = bpy.data.objects.new(f"ENV_Lamp_Shade_{j}_{i}", sh); C.objects.link(so)
        so.modifiers.new("Solidify", 'SOLIDIFY').thickness = 0.004
        b = cyl(f"ENV_Lamp_Bulb_{j}_{i}", cx, cy, cz - 0.2, 0.05, 0.08, M_BULB, seg=16)
        pl = bpy.data.lights.new(f"ENV_LampLight_{j}_{i}", 'POINT'); pl.energy = 60.0; pl.shadow_soft_size = 0.05
        pl.color = (1.0, 0.78, 0.55)
        po = bpy.data.objects.new(pl.name, pl); po.location = (cx, cy, cz - 0.3); C.objects.link(po)
# crates / shelving in the mid-ground
import random
random.seed(7)
for i, (cx, cy) in enumerate(((-1.6, 4.4), (-2.2, 5.4), (1.5, 9.0), (-2.4, 8.2), (3.4, 11.6), (2.8, 4.2))):
    n = random.randint(1, 3)
    for k in range(n):
        sz = random.uniform(0.7, 1.1)
        box(f"ENV_Crate_{i}_{k}", cx + random.uniform(-0.1, 0.1), cy + random.uniform(-0.1, 0.1),
            FLOOR + sz / 2 + k * sz * 0.98, sz, sz * random.uniform(0.9, 1.2), sz * 0.98, M_WOOD).rotation_euler.z = random.uniform(-0.15, 0.15)
for i, cy in enumerate((6.6, 10.2)):         # steel shelving racks on the right
    for z in (0.0, 1.2, 2.4):
        box(f"ENV_Shelf_{i}_{z}", 2.3 + 1.5 * i, cy, FLOOR + 0.3 + z, 0.9, 3.0, 0.05, M_STEEL_Y)
    for dy in (-1.45, 1.45):
        for dx in (-0.42, 0.42):
            box(f"ENV_ShelfPost_{i}_{dy}_{dx}", 2.3 + 1.5 * i + dx, cy + dy, FLOOR + 1.6, 0.06, 0.06, 3.2, M_STEEL)

# painted safety lines on the floor (yellow walkway)
M_LINE = mat("ENV_Floor_Paint_Yellow", (0.62, 0.42, 0.02), 0.55, noise=(3.0, 0.7, 0.1))
for sx in (-1.0, 1.0):
    box(f"ENV_FloorLine_{sx}", sx, (YB + YF) / 2, FLOOR + 0.001, 0.10, YB - YF - 0.2, 0.002, M_LINE)

# light haze in the room
vol = box("ENV_Haze", 0, (YB + YF) / 2, (FLOOR + CEIL) / 2, 2 * XW - 0.1, YB - YF - 0.1, H - 0.1, M_WALL)
vm = bpy.data.materials.new("ENV_Haze_Volume")
N = vm.node_tree.nodes; Lk = vm.node_tree.links
for n in list(N):
    if n.bl_idname != "ShaderNodeOutputMaterial": N.remove(n)
pv = N.new("ShaderNodeVolumePrincipled"); pv.inputs["Density"].default_value = 0.006
pv.inputs["Anisotropy"].default_value = 0.55
Lk.new(pv.outputs[0], N["Material Output"].inputs["Volume"])
vol.data.materials.clear(); vol.data.materials.append(vm)
vol.visible_shadow = False

# sun through the windows (from behind the back wall, high, a bit from the right) + bright outside
sd = bpy.data.lights.new("ENV_Sun", 'SUN'); sd.energy = 9.0; sd.angle = radians(1.5); sd.color = (1.0, 0.93, 0.82)
so = bpy.data.objects.new("ENV_Sun", sd); C.objects.link(so)
d = Vector((-0.35, -1.0, -0.55)).normalized()       # direction the light travels
so.rotation_euler = (-d).to_track_quat('Z', 'Y').to_euler()
w = bpy.data.worlds.new("World_FactoryOutside"); s.world = w
bg = w.node_tree.nodes["Background"]; bg.inputs["Color"].default_value = (0.55, 0.65, 0.8, 1); bg.inputs["Strength"].default_value = 0.9

# object light: keep the studio key/rim/fill but softer, warm-ish practical feel
for nm, e in (("Light_Key", 45.0), ("Light_Rim", 50.0), ("Light_Fill", 4.0)):
    o = bpy.data.objects.get(nm)
    if o: o.data.energy = e
s.view_settings.exposure = -0.6
# camera level with the subject so the floor reads in the background (this look only)
cam = bpy.data.objects["CAM_FlyIn"]; tgt = bpy.data.objects["Target_Fly"]
tgt.location = (0, 0, 0.10)
for fr, z in ((s.frame_start, 0.08), (s.frame_end, 0.10)):
    s.frame_set(fr); cam.location.z = z; cam.keyframe_insert("location", index=2, frame=fr)
s.cycles.volume_bounces = 1
bpy.ops.wm.save_as_mainfile(filepath=dst)
print("SAVED", dst)
