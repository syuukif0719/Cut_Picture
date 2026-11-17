# Post: soft neon glow (stand-in for the compositor Fog Glow, which needs a GPU context here).
# Usage: python3 -I neon_glow.py in.png out.jpg [strength=0.55] [radius_frac=0.012]
import sys
from PIL import Image, ImageFilter, ImageChops, ImageEnhance
src, dst = sys.argv[1], sys.argv[2]
k = float(sys.argv[3]) if len(sys.argv) > 3 else 0.55
rf = float(sys.argv[4]) if len(sys.argv) > 4 else 0.012
im = Image.open(src).convert("RGB")
hsv_v = im.convert("L").point(lambda v: 255 if v > 150 else int(v * v / 150 / 255 * 120))   # keep only bright parts
mask = hsv_v.convert("L")
bright = Image.composite(im, Image.new("RGB", im.size), mask)
r = max(2, int(im.width * rf))
glow = bright.filter(ImageFilter.GaussianBlur(r))
glow2 = bright.filter(ImageFilter.GaussianBlur(r * 4))
glow = ImageChops.add(ImageEnhance.Brightness(glow).enhance(k), ImageEnhance.Brightness(glow2).enhance(k * 0.5))
ImageChops.add(im, glow).save(dst, quality=92)
