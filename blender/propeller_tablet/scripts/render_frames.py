# Usage: python render_frames.py <file.blend> <outdir> <width> <samples> <start> <end> [step]
import bpy, sys, os
a = sys.argv
blend, outdir, width, samples, fs, fe = a[1], a[2], int(a[3]), int(a[4]), int(a[5]), int(a[6])
step = int(a[7]) if len(a) > 7 else 1
bpy.ops.wm.open_mainfile(filepath=blend)
s = bpy.context.scene
s.render.resolution_x = width; s.render.resolution_y = int(width * 9 / 16); s.render.resolution_percentage = 100
s.cycles.samples = samples; s.cycles.device = 'CPU'
s.render.image_settings.file_format = 'PNG'
s.frame_start, s.frame_end, s.frame_step = fs, fe, step
s.render.filepath = os.path.join(outdir, "f_")
bpy.ops.render.render(animation=True)
print("DONE")
