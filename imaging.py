"""Image sizing and overlap compositing, independent of the model runtime."""
import math
from PIL import Image, ImageChops, ImageDraw

TILE = 1024
OVERLAP = 128
MAX_PIXELS = 4_000_000


def positions(length, tile=TILE, overlap=OVERLAP):
    if length <= tile:
        return [0]
    result = [0]
    while result[-1] + tile < length:
        result.append(result[-1] + tile - overlap)
    return result


def fit_size(size, limit=MAX_PIXELS):
    w, h = size
    factor = min(1.0, math.sqrt(limit / (w * h)))
    # Model requires dimensions on a 16-pixel grid.
    return (max(16, round(w * factor / 16) * 16), max(16, round(h * factor / 16) * 16))


def merge_reconstruction(canvas, covered, generated, visible, local, core_origin, overlap=256):
    """Blend generated overlap while replacing every previously untouched pixel."""
    left, top, right, bottom = visible
    width, height = right - left, bottom - top
    fade = Image.new('L', (width, height), 255)
    x0, y0 = core_origin
    if x0 > 0:
        horizontal = Image.new('L', (width, height), 255)
        draw = ImageDraw.Draw(horizontal)
        for x in range(min(overlap, width)):
            draw.line((x, 0, x, height - 1), fill=round(255 * (x + 1) / overlap))
        fade = ImageChops.multiply(fade, horizontal)
    if y0 > 0:
        vertical = Image.new('L', (width, height), 255)
        draw = ImageDraw.Draw(vertical)
        for y in range(min(overlap, height)):
            draw.line((0, y, width - 1, y), fill=round(255 * (y + 1) / overlap))
        fade = ImageChops.multiply(fade, vertical)
    # An untouched pixel must come entirely from the model, never from the
    # original page, otherwise lettering can leak back into the output.
    previously_covered = covered.crop(visible)
    alpha = ImageChops.lighter(fade, ImageChops.invert(previously_covered))
    canvas.paste(generated.crop(local), (left, top), alpha)
    covered.paste(255, visible)


def tile_boxes(size):
    w, h = size
    return [(x, y, min(x + TILE, w), min(y + TILE, h)) for y in positions(h) for x in positions(w)]


def blend_tiles(size, tiles):
    """Blend overlapping tiles with smooth ramps; image edges remain fully covered."""
    w, h = size
    canvas = Image.new('RGB', size)
    # Sequential alpha compositing; each new tile fades in across its overlap.
    for box, image in tiles:
        x0, y0, x1, y1 = box
        tw, th = x1-x0, y1-y0
        alpha = Image.new('L', (tw, th), 255)
        draw = ImageDraw.Draw(alpha)
        if x0:
            for x in range(min(OVERLAP, tw)):
                draw.line((x, 0, x, th), fill=round(255 * (x + 1) / OVERLAP))
        if y0:
            # multiply top fade with the existing horizontal fade
            top = Image.new('L', (tw, th), 255)
            td = ImageDraw.Draw(top)
            for y in range(min(OVERLAP, th)):
                td.line((0, y, tw, y), fill=round(255 * (y + 1) / OVERLAP))
            from PIL import ImageChops
            alpha = ImageChops.multiply(alpha, top)
        canvas.paste(image.convert('RGB'), (x0, y0), alpha)
    return canvas
