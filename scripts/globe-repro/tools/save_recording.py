"""Writes recordings posted by record.html into the built site.

For each recording: recorded/<scene>/<name>-<build>/<zoom * 100>.webp, and recorded/<scene>/<name>-<build>.json with
the renderer, the build, the readout and camera of every frame and the camera trace, which compare.html reads.
"""
import argparse
import base64
import json
from pathlib import Path

PREFIX = "data:image/webp;base64,"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, required=True, help="folder of the built site")
    parser.add_argument("results", type=Path, nargs="+", help="result-<v>-<build>.json files from tools/server.py")
    args = parser.parse_args()
    for path in args.results:
        recording = json.loads(path.read_text())
        name = f"{recording['name']}-{recording['build']}"
        folder = args.site / "recorded" / recording["scene"] / name
        folder.mkdir(parents=True, exist_ok=True)
        frames = {}
        for frame in recording.pop("frames"):
            image = frame.pop("image")
            if not image.startswith(PREFIX):
                raise ValueError(f"{path}: zoom {frame['zoom']} is not a WebP data URL")
            (folder / f"{round(frame['zoom'] * 100)}.webp").write_bytes(base64.b64decode(image[len(PREFIX):]))
            frames[f"{frame['zoom']:.2f}"] = frame
        recording["frames"] = frames
        (folder.parent / f"{name}.json").write_text(json.dumps(recording))
        size = sum(file.stat().st_size for file in folder.iterdir())
        offsets = [f["offset"] for f in frames.values() if isinstance(f["offset"], (int, float))]
        print(f"{name}: {len(frames)} frames, {size / 1e6:.1f} MB, {recording['renderer']}, "
              f"offset up to {max(offsets, default=float('nan')):.1f} px")


if __name__ == "__main__":
    main()
