"""Turns frames from capture_frames.mjs into a GIF that fits a size limit (GitHub: 10 MB for images).

Frames advance every --step-ms and hold at the zoom levels in --holds and at both ends; --zoom-step keeps only the
frames at multiples of that zoom step, besides the holds and both ends. The GIF is made with one
palette for all frames (ffmpeg palettegen/paletteuse) and scaled down through --widths until it fits --max-mb.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frames", type=Path, help="folder with frames.json from capture_frames.mjs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--step-ms", type=int, default=80)
    parser.add_argument("--holds", default="11.99:900,12:1200,12.01:900", help="zoom:ms,...")
    parser.add_argument("--zoom-step", type=float, default=0, help="keep only frames at multiples of this zoom step")
    parser.add_argument("--start-ms", type=int, default=800)
    parser.add_argument("--end-ms", type=int, default=1500)
    parser.add_argument("--widths", default="1100,1000,900,800,700")
    parser.add_argument("--max-mb", type=float, default=9.5)
    args = parser.parse_args()

    frames = json.loads((args.frames / "frames.json").read_text())["frames"]
    holds = {round(float(zoom), 2): int(ms) for zoom, ms in (hold.split(":") for hold in args.holds.split(",") if hold)}
    if args.zoom_step:
        step = round(args.zoom_step * 100)
        frames = [frame for index, frame in enumerate(frames)
                  if round(frame["zoom"] * 100) % step == 0 or round(frame["zoom"], 2) in holds
                  or index in (0, len(frames) - 1)]
    lines = []
    for index, frame in enumerate(frames):
        ms = holds.get(round(frame["zoom"], 2), args.step_ms)
        if index == 0:
            ms = max(ms, args.start_ms)
        if index == len(frames) - 1:
            ms = max(ms, args.end_ms)
        lines += [f"file '{(args.frames / frame['file']).resolve()}'", f"duration {ms / 1000:.3f}"]
    # The concat demuxer takes the duration of the last file only when the file is listed once more
    lines.append(f"file '{(args.frames / frames[-1]['file']).resolve()}'")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory() as folder:
        listing = Path(folder, "frames.txt")
        listing.write_text("\n".join(lines))
        for width in map(int, args.widths.split(",")):
            filters = (f"scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];"
                       "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                            "-lavfi", filters, "-fps_mode", "passthrough", "-loop", "0", str(args.out)], check=True)
            megabytes = args.out.stat().st_size / 1e6
            print(f"{args.out.name}: {len(frames)} frames, {width} px wide, {megabytes:.1f} MB")
            if megabytes <= args.max_mb:
                return
    raise SystemExit(f"{args.out} is larger than {args.max_mb} MB at every width")


if __name__ == "__main__":
    main()
