"""Turns the screencast frames written by record.mjs into an MP4 at a constant frame rate.

Each frame is shown from its own timestamp until the next one, so the video runs in real time.
Usage: python make_video.py <frames dir> --out video.mp4 [--fps 30] [--hold 1.5]
"""
import argparse
import json
import os
import subprocess
import tempfile

import imageio_ffmpeg


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('frames')
    parser.add_argument('--out', required=True)
    parser.add_argument('--fps', type=int, default=30)
    parser.add_argument('--hold', type=float, default=1.5, help='seconds to show the last frame')
    parser.add_argument('--crf', type=int, default=20)
    args = parser.parse_args()

    with open(os.path.join(args.frames, 'frames.json')) as f:
        info = json.load(f)
    frames = info['frames']
    if not frames:
        raise SystemExit('no frames')
    times = [frame['t'] for frame in frames]
    lines = []
    for i, frame in enumerate(frames):
        duration = times[i + 1] - times[i] if i + 1 < len(frames) else args.hold
        path = os.path.abspath(os.path.join(args.frames, frame['file']))
        lines.append(f"file '{path}'\nduration {max(duration, 0.001):.4f}\n")
    # The concat demuxer needs the last file again for its duration to count
    lines.append(f"file '{os.path.abspath(os.path.join(args.frames, frames[-1]['file']))}'\n")

    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as listing:
        listing.writelines(lines)
    try:
        subprocess.run([
            imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error',
            '-f', 'concat', '-safe', '0', '-i', listing.name,
            '-fps_mode', 'cfr', '-r', str(args.fps),
            '-c:v', 'libx264', '-preset', 'slow', '-crf', str(args.crf), '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart', args.out
        ], check=True)
    finally:
        os.unlink(listing.name)
    total = times[-1] - times[0] + args.hold
    print(f'{args.out}: {len(frames)} frames, {total:.1f} s, {os.path.getsize(args.out) / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
