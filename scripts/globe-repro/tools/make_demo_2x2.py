"""2x2 demo video: deck.gl master vs master + the globe sin/cos fix, each on the GPU and in software."""

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from make_demo import BLUE, GRAY, GREEN, INK, RED, decode, load_font, measure

W, H = 480, 360
MARGIN, GAP, HEADER, ROW_TITLE, FOOTER = 14, 16, 96, 24, 66
SWITCH_ZOOM = 12.0

SCENES = [
    {"id": "a", "title": "1. GlobeView alone, looking straight down near Zurich (8.5° E, 47.3° N)"},
    {"id": "b", "title": "2. GlobeView alone, pitch 60, Mount St. Helens (122.19° W, 46.2° N)"},
]
ROWS = [("base", "Before: deck.gl master d1b0ae43", RED), ("trig", "After: master + globe sin/cos fix ccdbd7f8", GREEN)]
COLUMNS = [("gpu", "GPU: NVIDIA GTX 970 (Direct3D 11)"), ("sw", "Software: SwiftShader (no GPU)")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="folder with result-<scene>-<row>-<column>.json")
    parser.add_argument("--out", type=Path, required=True, help="output .mp4")
    parser.add_argument("--font", default="/mnt/c/Windows/Fonts/arial.ttf")
    parser.add_argument("--bold-font", default="/mnt/c/Windows/Fonts/arialbd.ttf")
    parser.add_argument("--fps", type=int, default=25)
    args = parser.parse_args()

    f_title, f_head = load_font(args.bold_font, 17), load_font(args.bold_font, 15)
    f_text, f_small, f_bold = load_font(args.font, 13), load_font(args.font, 12), load_font(args.bold_font, 14)
    width = 2 * W + GAP + 2 * MARGIN
    height = HEADER + 2 * (ROW_TITLE + H) + GAP + FOOTER
    images, durations, summary = [], [], {}

    for scene in SCENES:
        frames, readouts = {}, {}
        for row, _, _ in ROWS:
            for col, _ in COLUMNS:
                data = json.loads((args.results / f"result-{scene['id']}-{row}-{col}.json").read_text())["frames"]
                frames[row, col] = [decode(f["png"]) for f in data]
                readouts[row, col] = [measure(im, "dot") for im in frames[row, col]]
                zooms = [f["zoom"] for f in data]
        last_before = max(i for i, z in enumerate(zooms) if z <= SWITCH_ZOOM)
        jumps = {}
        for key, values in readouts.items():
            a, b = values[last_before], values[last_before + 1]
            jumps[key] = math.dist(a, b) if a and b else None
        summary[scene["id"]] = {f"{r}/{c}": {"max_offset": round(max((math.hypot(*v) for v in readouts[r, c] if v), default=-1), 2),
                                            "jump_at_12": round(jumps[r, c], 2) if jumps[r, c] is not None else None}
                                for r, _, _ in ROWS for c, _ in COLUMNS}

        for i, zoom in enumerate(zooms):
            canvas = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(canvas)
            draw.text((MARGIN, 8), "deck.gl globe sin/cos fix, before and after, on the GPU and in software. No base map, no terrain, no position.",
                      font=f_small, fill=GRAY)
            draw.text((MARGIN, 26), scene["title"], font=f_title, fill=INK)
            draw.text((MARGIN, 49), "Red dot: the map center on the ground, where the camera aims. It belongs on the crosshair.", font=f_small, fill=INK)
            for c, (col, col_title) in enumerate(COLUMNS):
                draw.text((MARGIN + c * (W + GAP), 72), col_title, font=f_head, fill=INK)
            for r, (row, row_title, row_color) in enumerate(ROWS):
                y0 = HEADER + r * (ROW_TITLE + H + GAP)
                draw.text((MARGIN, y0 + 3), row_title, font=f_bold, fill=row_color)
                for c, (col, _) in enumerate(COLUMNS):
                    x = MARGIN + c * (W + GAP)
                    y = y0 + ROW_TITLE
                    panel = frames[row, col][i].copy()
                    pd = ImageDraw.Draw(panel)
                    pd.line([(W / 2 - 16, H / 2), (W / 2 + 16, H / 2)], fill=(0, 0, 0), width=1)
                    pd.line([(W / 2, H / 2 - 16), (W / 2, H / 2 + 16)], fill=(0, 0, 0), width=1)
                    canvas.paste(panel, (x, y))
                    draw.rectangle([x, y, x + W - 1, y + H - 1], outline=(200, 200, 200))
                    v = readouts[row, col][i]
                    lines = ["GlobeViewport" if zoom <= SWITCH_ZOOM else "WebMercatorViewport",
                             f"dot off the crosshair: {math.hypot(*v):.1f} px" if v else "dot off the crosshair: -"]
                    for li, text in enumerate(lines):
                        tw = draw.textlength(text, font=f_small)
                        draw.rectangle([x + 4, y + 4 + li * 19, x + tw + 14, y + 21 + li * 19], fill=(255, 255, 255))
                        draw.text((x + 9, y + 6 + li * 19), text, font=f_small, fill=INK)
                    j = jumps[row, col]
                    if zoom > SWITCH_ZOOM and j is not None:
                        text, fill = (f"jumped {j:.0f} px at zoom 12", RED) if j > 2 else ("no jump at zoom 12", GREEN)
                        tw = draw.textlength(text, font=f_bold)
                        draw.rectangle([x + 4, y + H - 26, x + tw + 18, y + H - 4], fill=fill)
                        draw.text((x + 11, y + H - 24), text, font=f_bold, fill="white")
            # Zoom bar
            yb = height - FOOTER + 26
            x0, x1 = MARGIN + 74, width - MARGIN - 20
            to_x = lambda z: x0 + (z - zooms[0]) / (zooms[-1] - zooms[0]) * (x1 - x0)
            draw.text((MARGIN, yb - 8), f"zoom {zoom:.2f}", font=f_text, fill=INK)
            draw.line([(x0, yb), (x1, yb)], fill=(185, 185, 185), width=4)
            draw.line([(x0, yb), (to_x(zoom), yb)], fill=BLUE, width=4)
            sx = (to_x(zooms[last_before]) + to_x(zooms[last_before + 1])) / 2
            draw.line([(sx, yb - 9), (sx, yb + 9)], fill=RED, width=2)
            label = "zoom 12: GlobeView switches to WebMercatorViewport"
            lw = draw.textlength(label, font=f_small)
            draw.text((sx + 6 if sx + 6 + lw <= width - MARGIN else sx - 6 - lw, yb + 7), label, font=f_small, fill=RED)
            images.append(canvas)
            durations.append(1500 if i in (last_before, last_before + 1) else (1000 if i in (0, len(zooms) - 1) else 80))

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
