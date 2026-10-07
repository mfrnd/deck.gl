"""Turns frames from capture_frames.mjs into a GIF that fits a size limit (GitHub: 10 MB for images).

Frames advance every --step-ms and hold at the zoom levels in --holds and at both ends. --zoom-step keeps only the
frames at multiples of that zoom step outside the --fine zoom range, besides the holds and both ends, and shows them
for twice as long. All frames share one palette: the most
frequent saturated colors (captions, markers, lines) exactly, the rest by median cut, without dithering. Pixels that
did not change since the previous frame are transparent. The GIF is decoded again and compared with the frames, and
scaled down through --widths until it fits --max-mb.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageChops

TRANSPARENT = 255
ACCENTS = 48
# Colors of the pages (style.css, scenes): captions, text, camera, target, measured terrain, markers, circles, dot
PAGE_COLORS = ['#c62828', '#2e7d32', '#1e1e1e', '#5a5a5a', '#1f4e9c', '#c2185b', '#e65100', '#ff00aa', '#00c8e6',
               '#dc143c', '#c82828']


def make_palette(frames):
    """A palette image: the page colors and frequent saturated colors exactly, then a median cut of a sample."""
    sample = frames[:: max(1, len(frames) // 12)]
    counts = Counter()
    for frame in sample:
        for count, color in frame.getcolors(maxcolors=frame.width * frame.height):
            counts[color] += count
    page = [tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5)) for hex_color in PAGE_COLORS]
    accents = page + [color for color, _ in counts.most_common()
                      if max(color) - min(color) > 40 and color not in page][:ACCENTS - len(page)]
    mosaic = Image.new("RGB", (sample[0].width, sample[0].height * len(sample)))
    for index, frame in enumerate(sample):
        mosaic.paste(frame, (0, index * frame.height))
    rest = mosaic.quantize(colors=TRANSPARENT - len(accents), method=Image.Quantize.MEDIANCUT).getpalette()
    colors = accents + [tuple(rest[i:i + 3]) for i in range(0, 3 * (TRANSPARENT - len(accents)), 3)]
    # The transparent index repeats the first color, so that no pixel is mapped to it
    colors += [colors[0]] * (256 - len(colors))
    palette = Image.new("P", (1, 1))
    palette.putpalette([value for color in colors for value in color])
    return palette


def write_gif(frames, durations, out):
    """Writes the frames with one palette; returns the quantized frames as shown."""
    palette = make_palette(frames)
    shown = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    if any(image.histogram()[TRANSPARENT] for image in shown):
        raise RuntimeError("a pixel was mapped to the transparent index")
    images = [shown[0]]
    for previous, current in zip(shown, shown[1:]):
        indices = Image.frombytes("L", current.size, current.tobytes())
        unchanged = ImageChops.difference(indices, Image.frombytes("L", previous.size, previous.tobytes()))
        unchanged = unchanged.point(lambda value: 255 if value == 0 else 0)
        image = current.copy()
        image.paste(TRANSPARENT, mask=unchanged)
        images.append(image)
    images[0].save(out, save_all=True, append_images=images[1:], duration=durations, loop=0, disposal=1,
                   transparency=TRANSPARENT, optimize=False)
    return [image.convert("RGB") for image in shown]


def check_gif(path, expected):
    """Number of pixels that differ from the quantized frames when the GIF is played."""
    gif = Image.open(path)
    worst = 0
    for index, frame in enumerate(expected):
        gif.seek(index)
        difference = ImageChops.difference(gif.convert("RGB"), frame).convert("L").point(lambda v: 255 if v else 0)
        worst = max(worst, difference.histogram()[255])
    return worst


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path, help="folder with frames.json from capture_frames.mjs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--step-ms", type=int, default=80)
    parser.add_argument("--holds", default="11.99:900,12:1200,12.01:900", help="zoom:ms,...")
    parser.add_argument("--zoom-step", type=float, default=0, help="keep only frames at multiples of this zoom step")
    parser.add_argument("--fine", default="", help="from:to, zoom range in which all frames are kept")
    parser.add_argument("--start-ms", type=int, default=800)
    parser.add_argument("--end-ms", type=int, default=1500)
    parser.add_argument("--widths", default="1100,1000,900,800,700")
    parser.add_argument("--max-mb", type=float, default=9.5)
    args = parser.parse_args()

    frames = json.loads((args.frames / "frames.json").read_text())["frames"]
    holds = {round(float(zoom), 2): int(ms) for zoom, ms in (hold.split(":") for hold in args.holds.split(",") if hold)}
    fine = [float(zoom) for zoom in args.fine.split(":")] if args.fine else [0, 0]
    in_fine = lambda zoom: fine[0] <= zoom <= fine[1]
    if args.zoom_step:
        step = round(args.zoom_step * 100)
        frames = [frame for index, frame in enumerate(frames)
                  if round(frame["zoom"] * 100) % step == 0 or round(frame["zoom"], 2) in holds
                  or in_fine(frame["zoom"]) or index in (0, len(frames) - 1)]
    durations = []
    for index, frame in enumerate(frames):
        coarse = args.zoom_step and not in_fine(frame["zoom"])
        ms = holds.get(round(frame["zoom"], 2), args.step_ms * (2 if coarse else 1))
        if index == 0:
            ms = max(ms, args.start_ms)
        if index == len(frames) - 1:
            ms = max(ms, args.end_ms)
        durations.append(ms)
    images = [Image.open(args.frames / frame["file"]).convert("RGB") for frame in frames]
    sizes = {image.size for image in images}
    if len(sizes) > 1:
        raise SystemExit(f"frames differ in size, {sorted(sizes)}: the page layout changed during the capture")

    for width in map(int, args.widths.split(",")):
        scaled = [image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)
                  for image in images]
        shown = write_gif(scaled, durations, args.out)
        megabytes = args.out.stat().st_size / 1e6
        mismatched = check_gif(args.out, shown)
        print(f"{args.out.name}: {len(frames)} frames, {width}x{scaled[0].height}, {sum(durations) / 1000:.1f} s, "
              f"{megabytes:.1f} MB, pixels off when played: {mismatched}")
        if megabytes <= args.max_mb:
            return
    raise SystemExit(f"{args.out} is larger than {args.max_mb} MB at every width")


if __name__ == "__main__":
    main()
