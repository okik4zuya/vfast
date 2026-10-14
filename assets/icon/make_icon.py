"""Generate app-icon PNGs (all sizes) and app-icon.ico from the locked app-icon.svg design.

Re-implements the SVG geometry directly in Pillow (no SVG rasterizer dependency):
skewed rounded-square box with a diagonal blue gradient, white play triangle sharing
the skew, and a fan of rounded solid speed bars (with a soft glow pass) behind it.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
PNG_DIR = HERE / "png"
PNG_DIR.mkdir(exist_ok=True)

MASTER = 1024          # render master, 2x the 512 viewBox used when designing the SVG
SCALE = MASTER / 512
SKEW_DEG = -18
BOX_CENTER_Y = 256 * SCALE   # skew is centered on the box's own vertical center

GRAD_START = (0x3E, 0x6B, 0xFF)
GRAD_END = (0x17, 0x30, 0xB0)
GLOW_COLOR = (0xBF, 0xE0, 0xFF)


def s(v):
    return v * SCALE


def skew_matrix(k, cy):
    """PIL AFFINE (inverse) coefficients for x_out = x + k*(y-cy), y_out = y."""
    return (1, -k, k * cy, 0, 1, 0)


def draw_gradient_rounded_rect(box, radius, c0, c1):
    x0, y0, x1, y1 = box
    w, h = int(round(x1 - x0)), int(round(y1 - y0))
    grad = Image.new("RGB", (w, h))
    px = grad.load()
    denom = max(w + h - 2, 1)
    for j in range(h):
        for i in range(w):
            t = (i + j) / denom
            px[i, j] = (
                round(c0[0] + (c1[0] - c0[0]) * t),
                round(c0[1] + (c1[1] - c0[1]) * t),
                round(c0[2] + (c1[2] - c0[2]) * t),
            )
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return grad, mask, (int(round(x0)), int(round(y0)))


def make_box_layer(size):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    box = (s(106), s(86), s(446), s(426))
    grad, mask, origin = draw_gradient_rounded_rect(box, radius=s(76), c0=GRAD_START, c1=GRAD_END)
    layer.paste(grad, origin, mask)

    draw = ImageDraw.Draw(layer)
    triangle = [(s(238), s(181)), (s(238), s(331)), (s(368), s(256))]
    draw.polygon(triangle, fill=(255, 255, 255, 255))

    k = math.tan(math.radians(SKEW_DEG))
    coeffs = skew_matrix(k, s(256))
    return layer.transform((size, size), Image.AFFINE, coeffs, resample=Image.BICUBIC)


SPEED_BARS = [
    # (x1, x2, y, stroke_width)
    (70, 180, 266, 24),
    (40, 190, 290, 28),
    (55, 185, 312, 28),
    (20, 195, 334, 34),
    (50, 180, 356, 28),
    (80, 170, 378, 24),
]


def draw_speed_bars(draw, color, alpha):
    for x1, x2, y, w in SPEED_BARS:
        r = s(w) / 2
        draw.rounded_rectangle(
            [s(x1), s(y) - r, s(x2), s(y) + r], radius=r, fill=color + (alpha,)
        )


def make_speed_layer(size, blurred):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if blurred:
        draw_speed_bars(draw, GLOW_COLOR, round(255 * 0.6))
        layer = layer.filter(ImageFilter.GaussianBlur(s(8)))
    else:
        draw_speed_bars(draw, (255, 255, 255), 255)
    return layer


def make_icon(size):
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(make_speed_layer(size, blurred=True))
    canvas.alpha_composite(make_speed_layer(size, blurred=False))
    canvas.alpha_composite(make_box_layer(size))
    return canvas


MASTER_IMG = make_icon(MASTER)

PNG_SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

for sz in PNG_SIZES:
    img = MASTER_IMG if sz == MASTER else MASTER_IMG.resize((sz, sz), Image.LANCZOS)
    img.save(PNG_DIR / f"icon-{sz}.png")

def write_ico(path, sizes):
    """Write a multi-resolution ICO by hand, one PNG-compressed image per size.

    Pillow's ICO writer is not usable here: it only emits sizes <= the first frame's size and
    ignores append_images, so saving from the 16px frame produced a one-image, 16x16 icon that
    Windows upscaled (blurry desktop shortcut). Each size is downscaled separately from the
    1024 master with LANCZOS instead of letting a writer resample from one frame."""
    import io
    import struct

    blobs = []
    for sz in sizes:
        buf = io.BytesIO()
        MASTER_IMG.resize((sz, sz), Image.LANCZOS).save(buf, format="PNG")
        blobs.append(buf.getvalue())
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for sz, blob in zip(sizes, blobs):
        dim = 0 if sz >= 256 else sz  # 0 means 256 in the ICO directory
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    Path(path).write_bytes(header + entries + b"".join(blobs))


write_ico(HERE / "app-icon.ico", ICO_SIZES)

print(f"Wrote {len(PNG_SIZES)} PNGs to {PNG_DIR} and app-icon.ico ({ICO_SIZES})")
