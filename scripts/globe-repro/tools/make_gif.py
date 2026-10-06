"""Side-by-side GIF from GPU-rendered frames: deck.gl master on the left, the fix on the right."""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 480, 360
MARGIN, GAP, HEADER, FOOTER = 14, 16, 78, 66
RED, GREEN, BLUE, INK = (198, 40, 40), (46, 125, 50), (31, 78, 156), (30, 30, 30)


def load_font(path, size):
    if path and Path(path).exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def fitted(draw, text, path, size, max_width):
    """Font for text at size, smaller if needed so the text fits max_width."""
    font = load_font(path, size)
    while size > 8 and draw.textlength(text, font=font) > max_width:
        size -= 1
        font = load_font(path, size)
    return font


def panel(path, crosshair):
    image = Image.open(path).convert("RGBA")
    if image.size != (W, H):
        image = image.resize((W, H), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", image.size, (248, 250, 253, 255))
    background.alpha_composite(image)
    if crosshair:
        draw = ImageDraw.Draw(background)
        cx, cy = W // 2, H // 2
        draw.line([(cx - 16, cy), (cx + 16, cy)], fill=(0, 0, 0, 255), width=1)
        draw.line([(cx, cy - 16), (cx, cy + 16)], fill=(0, 0, 0, 255), width=1)
    return background.convert("RGB")


def write_mp4(images, durations, out, fps=25):
    """MP4 with the same per-frame durations, by repeating frames at a fixed rate."""
    import subprocess
    import tempfile

    import imageio_ffmpeg

    with tempfile.TemporaryDirectory() as tmp:
        index = 0
        for image, duration in zip(images, durations):
            for _ in range(max(1, round(duration / 1000 * fps))):
                image.save(Path(tmp) / f"{index:05d}.png")
                index += 1
        width, height = images[0].size
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y", "-framerate", str(fps),
                        "-i", str(Path(tmp) / "%05d.png"), "-vf", f"scale={width - width % 2}:{height - height % 2}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(out)], check=True)
    print(f"wrote {out}: {out.stat().st_size / 1e6:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True, help="folder with <prefix>-master/ and <prefix>-fixed/")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--subtitle", required=True)
    parser.add_argument("--last-before", type=float, required=True, help="last zoom before the switch, e.g. 11.99 or 12.00")
    parser.add_argument("--before-label", required=True, help="corner label before the switch")
    parser.add_argument("--after-label", required=True, help="corner label after the switch")
    parser.add_argument("--switch-label", required=True, help="text at the switch on the zoom bar")
    parser.add_argument("--crosshair", action="store_true")
    parser.add_argument("--colors", type=int, default=192)
    parser.add_argument("--every", type=int, default=1, help="use every n-th zoom step (the two at the switch are always kept)")
    parser.add_argument("--dither", action="store_true")
    parser.add_argument("--scale", type=float, default=1.0, help="panel size relative to 480x360")
    parser.add_argument("--mp4", type=Path, help="also write an MP4 with the same timing")
    parser.add_argument("--band", nargs=3, metavar=("FROM", "TO", "LABEL"), help="shaded zoom range on the zoom bar")
    parser.add_argument("--font", default="/mnt/c/Windows/Fonts/arial.ttf")
    parser.add_argument("--bold-font", default="/mnt/c/Windows/Fonts/arialbd.ttf")
    args = parser.parse_args()
    global W, H
    W, H = round(480 * args.scale), round(360 * args.scale)

    zooms = sorted(float(p.stem[1:]) for p in (args.frames / f"{args.prefix}-master").glob("z*.png"))
    first_after = min(z for z in zooms if z > args.last_before + 1e-6)
    keep = {round(args.last_before, 2), round(first_after, 2), zooms[0], zooms[-1]}
    zooms = [z for i, z in enumerate(zooms) if i % args.every == 0 or round(z, 2) in keep]
    f_title, f_text, f_small, f_bold = (load_font(args.bold_font, 17), load_font(args.font, 13),
                                        load_font(args.font, 12), load_font(args.bold_font, 14))
    width = 2 * W + GAP + 2 * MARGIN
    height = HEADER + H + FOOTER
    images, durations = [], []
    for zoom in zooms:
        after = zoom > args.last_before + 1e-6
        canvas = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((MARGIN, 8), args.title, font=fitted(draw, args.title, args.bold_font, 17, width - 2 * MARGIN), fill=INK)
        draw.text((MARGIN, 31), args.subtitle, font=fitted(draw, args.subtitle, args.font, 12, width - 2 * MARGIN), fill=INK)
        for column, (name, title, color) in enumerate((("master", "Before: deck.gl master", RED), ("fixed", "After: with the fix", GREEN))):
            x = MARGIN + column * (W + GAP)
            draw.text((x, 54), title, font=f_bold, fill=color)
            canvas.paste(panel(args.frames / f"{args.prefix}-{name}" / f"z{zoom:.2f}.png", args.crosshair), (x, HEADER))
            draw.rectangle([x, HEADER, x + W - 1, HEADER + H - 1], outline=(200, 200, 200))
            label = args.after_label if after else args.before_label
            label_width = draw.textlength(label, font=f_small)
            draw.rectangle([x + 4, HEADER + 4, x + label_width + 14, HEADER + 22], fill=(255, 255, 255))
            draw.text((x + 9, HEADER + 6), label, font=f_small, fill=INK)
            if after:
                text, fill = ("jumped at zoom 12", RED) if name == "master" else ("no jump at zoom 12", GREEN)
                text_width = draw.textlength(text, font=f_bold)
                draw.rectangle([x + 4, HEADER + H - 26, x + text_width + 18, HEADER + H - 4], fill=fill)
                draw.text((x + 11, HEADER + H - 24), text, font=f_bold, fill="white")
        # Zoom bar
        y = HEADER + H + 20
        x0, x1 = MARGIN + 74, width - MARGIN - 20
        to_x = lambda z: x0 + (z - zooms[0]) / (zooms[-1] - zooms[0]) * (x1 - x0)
        draw.text((MARGIN, y - 8), f"zoom {zoom:.2f}", font=f_text, fill=INK)
        draw.line([(x0, y), (x1, y)], fill=(185, 185, 185), width=4)
        draw.line([(x0, y), (to_x(zoom), y)], fill=BLUE, width=4)
        if args.band:
            band_from, band_to = float(args.band[0]), float(args.band[1])
            draw.rectangle([to_x(band_from), y - 7, to_x(band_to), y + 7], fill=(225, 225, 225))
            draw.text((to_x(band_from) + 4, y - 22), args.band[2], font=f_small, fill=(90, 90, 90))
            draw.line([(to_x(zooms[0]), y), (to_x(zoom), y)], fill=BLUE, width=4)
        switch_x = (to_x(args.last_before) + to_x(first_after)) / 2
        draw.line([(switch_x, y - 9), (switch_x, y + 9)], fill=RED, width=2)
        label_width = draw.textlength(args.switch_label, font=f_small)
        label_x = switch_x + 6 if switch_x + 6 + label_width <= width - MARGIN else switch_x - 6 - label_width
        draw.text((label_x, y + 7), args.switch_label, font=f_small, fill=RED)
        images.append(canvas)
        at_switch = abs(zoom - args.last_before) < 1e-6 or abs(zoom - first_after) < 1e-6
        durations.append(1500 if at_switch else (900 if zoom in (zooms[0], zooms[-1]) else 70 * args.every))
    # Palette from several frames plus swatches, so the key colors survive a small palette
    samples = [images[0], images[len(images) // 2], images[-1]]
    swatch_colors = [RED, GREEN, BLUE, INK, (255, 255, 255), (255, 0, 170), (0, 200, 230), (220, 20, 60), (0, 90, 255)]
    sheet = Image.new("RGB", (sum(im.width for im in samples), samples[0].height + 40), "white")
    x = 0
    for im in samples:
        sheet.paste(im, (x, 0))
        x += im.width
    swatch_width = sheet.width // len(swatch_colors)
    for i, color in enumerate(swatch_colors):
        sheet.paste(Image.new("RGB", (swatch_width, 40), color), (i * swatch_width, samples[0].height))
    palette = sheet.quantize(colors=args.colors, method=Image.Quantize.MEDIANCUT)
    dither = Image.Dither.FLOYDSTEINBERG if args.dither else Image.Dither.NONE
    frames = [image.quantize(palette=palette, dither=dither) for image in images]
    if args.mp4:
        write_mp4(images, durations, args.mp4)
    frames[0].save(args.out, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {args.out}: {len(frames)} frames, {sum(durations) / 1000:.1f} s, {args.out.stat().st_size / 1e6:.2f} MB, {width}x{height}")


if __name__ == "__main__":
    main()
