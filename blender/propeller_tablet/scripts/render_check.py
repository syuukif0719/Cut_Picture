# Usage: python render_check.py <file.blend> <outdir> <width> <samples> [cam1,cam2,...]
import bpy, sys, os, time
blend, outdir, width, samples = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
cams = sys.argv[5].split(",") if len(sys.argv) > 5 else None
bpy.ops.wm.open_mainfile(filepath=blend)
s = bpy.context.scene
s.render.resolution_x = width; s.render.resolution_y = int(width * 9 / 16); s.render.resolution_percentage = 100
s.cycles.samples = samples; s.cycles.device = 'CPU'
s.render.threads_mode = 'FIXED'; s.render.threads = os.cpu_count()
s.render.image_settings.file_format = 'PNG'
os.makedirs(outdir, exist_ok=True)
for o in [o for o in bpy.data.objects if o.type == 'CAMERA']:
    if cams and o.name not in cams: continue
    s.camera = o
    s.render.filepath = os.path.join(outdir, o.name + ".png")
    t = time.time(); bpy.ops.render.render(write_still=True)
    print("RENDERED", o.name, round(time.time() - t, 1), "s", flush=True)
