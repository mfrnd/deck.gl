"""GPU vs software rendering demo video of deck.gl with both fixes, three scenes with measured readouts."""

import argparse
import base64
import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 480, 360
MARGIN, GAP, HEADER, FOOTER = 14, 16, 96, 66
RED, GREEN, BLUE, INK, GRAY = (198, 40, 40), (46, 125, 50), (31, 78, 156), (30, 30, 30), (90, 90, 90)
DOT, PINK, CYAN = (220, 20, 60), (255, 0, 170), (0, 200, 230)
SWITCH_ZOOM = 12.0

SCENES = [
    {
        "id": "s1", "crosshair": True, "kind": "dot",
        "title": "1. GlobeView alone: no base map, no position, looking straight down near Zurich",
        "subtitle": "Red dot: the map center on the ground, where the camera aims. It belongs on the crosshair.",
    },
    {
        "id": "s2", "crosshair": True, "kind": "dot",
        "title": "2. GlobeView with viewState.position = [0, 0, 2000], Mount St. Helens, pitch 60",
        "subtitle": "Red dot: 2,000 m above the map center, where position puts the camera target. It belongs on the crosshair.",
    },
    {
        "id": "s3", "crosshair": False, "kind": "pairs", "band": (11, 12, "MapLibre blends its globe into Mercator"),
        "title": "3. MapLibreOverlay on MapLibre 6's globe with terrain, Mount St. Helens, pitch 60",
        "subtitle": "Cyan: MapLibre circles. Pink: deck.gl points at the same places and terrain heights; they belong inside the cyan circles.",
    },
]
COLUMNS = [("gpu", "GPU: NVIDIA GTX 970 (Direct3D 11)"), ("sw", "Software: SwiftShader (no GPU)")]


def load_font(path, size):
    return ImageFont.truetype(path, size) if path and Path(path).exists() else ImageFont.load_default(size=size)


def decode(png):
    image = Image.open(__import__("io").BytesIO(base64.b64decode(png.split(",")[1]))).convert("RGBA")
    background = Image.new("RGBA", image.size, (248, 250, 253, 255))
    background.alpha_composite(image)
    return background.convert("RGB")


def mask(array, color, tolerance):
    return np.all(np.abs(array.astype(int) - np.array(color)) < tolerance, axis=2)


def blobs(boolean, min_size=6):
    """Centroids of 4-connected regions."""
    seen = np.zeros_like(boolean)
    centers = []
    ys, xs = np.nonzero(boolean)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack, points = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            points.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < boolean.shape[0] and 0 <= nx < boolean.shape[1] and boolean[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(points) >= min_size:
            p = np.array(points)
            centers.append((p[:, 1].mean() + 0.5, p[:, 0].mean() + 0.5, len(points)))
    return centers


def measure(image, kind):
    """Scenes 1-2: dot position (offset from the center). Scene 3: median pink-to-cyan offset vector."""
    array = np.asarray(image)
    if kind == "dot":
        # The mast (200, 40, 40) is close to the dot's color (220, 20, 60): a tight tolerance keeps it out
        found = blobs(mask(array, DOT, 14))
        if not found:
            return None
        x, y, _ = max(found, key=lambda c: c[2])
        return (x - W / 2, y - H / 2)
    pinks = blobs(mask(array, PINK, 60))
    # MapLibre circles are drawn under the pink points: fill the cyan ring with the pink inside
    cyans = blobs(mask(array, CYAN, 60) | mask(array, PINK, 60), min_size=30)
    offsets = []
    for p in pinks:
        nearest = min(cyans, key=lambda c: math.dist(c[:2], p[:2]), default=None)
        if nearest and math.dist(nearest[:2], p[:2]) < 140:
            offsets.append((p[0] - nearest[0], p[1] - nearest[1]))
    if not offsets:
        return None
    return (float(np.median([o[0] for o in offsets])), float(np.median([o[1] for o in offsets])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="folder with result-<scene>-<gpu|sw>.json")
    parser.add_argument("--out", type=Path, required=True, help="output .mp4")
    parser.add_argument("--font", default="/mnt/c/Windows/Fonts/arial.ttf")
    parser.add_argument("--bold-font", default="/mnt/c/Windows/Fonts/arialbd.ttf")
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--headline", default="deck.gl master + #10790 + #10791 (all current fixes): GPU vs software rendering")
    args = parser.parse_args()

    f_title, f_head = load_font(args.bold_font, 17), load_font(args.bold_font, 15)
    f_text, f_small, f_bold = load_font(args.font, 13), load_font(args.font, 12), load_font(args.bold_font, 14)
    width, height = 2 * W + GAP + 2 * MARGIN, HEADER + H + FOOTER
    images, durations, summary = [], [], {}

    for scene in SCENES:
        frames = {c: json.loads((args.results / f"result-{scene['id']}-{c}.json").read_text())["frames"] for c, _ in COLUMNS}
        zooms = [f["zoom"] for f in frames["gpu"]]
        assert zooms == [f["zoom"] for f in frames["sw"]]
        decoded = {c: [decode(f["png"]) for f in frames[c]] for c, _ in COLUMNS}
        readouts = {c: [measure(im, scene["kind"]) for im in decoded[c]] for c, _ in COLUMNS}
        last_before = max(i for i, z in enumerate(zooms) if z <= SWITCH_ZOOM)
        jumps = {}
        for c, _ in COLUMNS:
            a, b = readouts[c][last_before], readouts[c][last_before + 1]
            jumps[c] = math.dist(a, b) if a and b else None
        summary[scene["id"]] = {c: {"max_offset": max((math.hypot(*r) for r in readouts[c] if r), default=None),
                                    "jump_at_12": jumps[c]} for c, _ in COLUMNS}

        for i, zoom in enumerate(zooms):
            canvas = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(canvas)
            draw.text((MARGIN, 8), args.headline, font=f_small, fill=GRAY)
            draw.text((MARGIN, 26), scene["title"], font=f_title, fill=INK)
            draw.text((MARGIN, 49), scene["subtitle"], font=f_small, fill=INK)
            for col, (c, title) in enumerate(COLUMNS):
                x = MARGIN + col * (W + GAP)
                draw.text((x, 72), title, font=f_head, fill=GREEN if c == "gpu" else RED)
                panel = decoded[c][i].copy()
                pd = ImageDraw.Draw(panel)
                if scene["crosshair"]:
                    pd.line([(W / 2 - 16, H / 2), (W / 2 + 16, H / 2)], fill=(0, 0, 0), width=1)
                    pd.line([(W / 2, H / 2 - 16), (W / 2, H / 2 + 16)], fill=(0, 0, 0), width=1)
                canvas.paste(panel, (x, HEADER))
                draw.rectangle([x, HEADER, x + W - 1, HEADER + H - 1], outline=(200, 200, 200))
                viewport = "GlobeViewport" if zoom <= SWITCH_ZOOM else "WebMercatorViewport"
                r = readouts[c][i]
                what = "dot off the crosshair" if scene["kind"] == "dot" else "deck.gl off MapLibre (median)"
                value = f"{what}: {math.hypot(*r):.1f} px" if r else f"{what}: -"
                for line_index, text in enumerate((viewport, value)):
                    tw = draw.textlength(text, font=f_small)
                    yy = HEADER + 4 + line_index * 19
                    draw.rectangle([x + 4, yy, x + tw + 14, yy + 17], fill=(255, 255, 255))
                    draw.text((x + 9, yy + 2), text, font=f_small, fill=INK)
                if zoom > SWITCH_ZOOM and jumps[c] is not None:
                    text, fill = (f"jumped {jumps[c]:.0f} px at zoom 12", RED) if jumps[c] > 2 else ("no jump at zoom 12", GREEN)
                    tw = draw.textlength(text, font=f_bold)
                    draw.rectangle([x + 4, HEADER + H - 26, x + tw + 18, HEADER + H - 4], fill=fill)
                    draw.text((x + 11, HEADER + H - 24), text, font=f_bold, fill="white")
            # Zoom bar
            y = HEADER + H + 22
            x0, x1 = MARGIN + 74, width - MARGIN - 20
            to_x = lambda z: x0 + (z - zooms[0]) / (zooms[-1] - zooms[0]) * (x1 - x0)
            draw.text((MARGIN, y - 8), f"zoom {zoom:.2f}", font=f_text, fill=INK)
            draw.line([(x0, y), (x1, y)], fill=(185, 185, 185), width=4)
            if scene.get("band"):
                b0, b1, label = scene["band"]
                draw.rectangle([to_x(b0), y - 7, to_x(b1), y + 7], fill=(225, 225, 225))
                draw.text((to_x(b0) + 4, y - 23), label, font=f_small, fill=GRAY)
            draw.line([(x0, y), (to_x(zoom), y)], fill=BLUE, width=4)
            sx = (to_x(zooms[last_before]) + to_x(zooms[last_before + 1])) / 2
            draw.line([(sx, y - 9), (sx, y + 9)], fill=RED, width=2)
            label = "zoom 12: GlobeView switches to WebMercatorViewport"
            lw = draw.textlength(label, font=f_small)
            draw.text((sx + 6 if sx + 6 + lw <= width - MARGIN else sx - 6 - lw, y + 7), label, font=f_small, fill=RED)
            images.append(canvas)
            at_switch = i in (last_before, last_before + 1)
            durations.append(1500 if at_switch else (1000 if i in (0, len(zooms) - 1) else 80))

    with tempfile.TemporaryDirectory() as tmp:
        index = 0
        for image, duration in zip(images, durations):
            for _ in range(max(1, round(duration / 1000 * args.fps))):
                image.save(Path(tmp) / f"{index:05d}.png")
                index += 1
        import imageio_ffmpeg
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-framerate", str(args.fps),
                        "-i", str(Path(tmp) / "%05d.png"), "-vf", f"scale={width - width % 2}:{height - height % 2}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", "-movflags", "+faststart", str(args.out)], check=True)
    print(f"wrote {args.out}: {args.out.stat().st_size / 1e6:.2f} MB, {sum(durations) / 1000:.1f} s, {width}x{height}")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
