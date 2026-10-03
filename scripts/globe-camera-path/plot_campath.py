"""Animate deck.gl's GlobeView camera path, before and after the fix, from dumped viewports.

Side view of the vertical plane through the map center facing north (bearing 0):
x is the distance north of the map center, y the altitude, both in km at equal scale.
"""

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

EARTH_RADIUS = 6371008.8
SWITCH_ZOOM = 12
BLEND = (11, 12)

COLOR_CAMERA = "#1f4e9c"
COLOR_TARGET = "#c2185b"
COLOR_FOV = "#5b9bd5"
COLOR_REFERENCE = "#222222"
COLOR_BROKEN = "#c62828"
COLOR_FIXED = "#2e7d32"
COLOR_GROUND = "#d9cbb3"
COLOR_TERRAIN = "#9e8a6a"
COLOR_SKY = "#f7fbff"

ROWS = [
    ("plain", "No base map: GlobeView alone, no terrain"),
    ("maplibre", "MapLibreOverlay on MapLibre's globe with terrain (2,143 m at the map center)"),
]
COLUMNS = [
    ("master", "Before: deck.gl master", COLOR_BROKEN),
    ("fixed", "After: with the fix", COLOR_FIXED),
]


def to_local(lng_lat_alt, lng0, lat0):
    """Meters north of the map center and altitude in meters."""
    lng, lat, alt = lng_lat_alt
    north = math.radians(lat - lat0) * EARTH_RADIUS
    return north, alt


def reference_target(row, zoom, elevation):
    """Where the base map's camera aims, or None inside MapLibre's globe to Mercator blend."""
    if row == "plain":
        return (0.0, 0.0)
    if zoom <= BLEND[0]:
        return (0.0, 0.0)
    if zoom >= BLEND[1]:
        return (0.0, float(elevation))
    return None


def frame_schedule(frames, fps):
    """Indexes into frames: every second zoom step, with holds at the start, at the switch and at the end.

    switch_index is the first frame above zoom 12, where GlobeView uses WebMercatorViewport.
    """
    switch_index = next(i for i, f in enumerate(frames) if f["zoom"] > SWITCH_ZOOM + 1e-9)
    order = [0] * int(0.8 * fps)
    for index in list(range(0, switch_index, 2)) + list(range(switch_index, len(frames), 2)):
        order.append(index)
        if index == switch_index:
            order.extend([index] * int(2.0 * fps))
    order.extend([order[-1]] * int(2.0 * fps))
    return order, switch_index


def row_extent(distance, elevation_top, aspect):
    """Smooth view extent from the camera distance, so the frame zooms in with the map."""
    y_min = -0.08 * distance
    y_max = 0.62 * distance + elevation_top
    y_span = y_max - y_min
    x_span = aspect * y_span
    x_center = -0.27 * distance
    return (x_center - x_span / 2, x_center + x_span / 2), (y_min, y_max)


def fov_wedge(camera, target, fovy, length):
    """Two rays from the camera at +-fovy/2 around the line of sight, in the vertical plane."""
    dx, dy = target[0] - camera[0], target[1] - camera[1]
    angle = math.atan2(dy, dx)
    half = math.radians(fovy) / 2
    rays = []
    for sign in (1, -1):
        a = angle + sign * half
        rays.append((camera[0] + length * math.cos(a), camera[1] + length * math.sin(a)))
    return rays


def draw_panel(ax, state, history, row, column, zoom, elevation, extent, jump):
    (x_min, x_max), (y_min, y_max) = extent
    km = 1000.0
    ax.clear()
    ax.set_xlim(x_min / km, x_max / km)
    ax.set_ylim(y_min / km, y_max / km)
    ax.set_aspect("equal", adjustable="box")
    ax.set_facecolor(COLOR_SKY)
    ax.tick_params(labelsize=8)

    # Ground below sea level, terrain at the map center elevation
    ax.add_patch(Rectangle((x_min / km, y_min / km), (x_max - x_min) / km, -y_min / km, color=COLOR_GROUND, zorder=0))
    ax.axhline(0, color="#7a6a50", lw=0.8, zorder=1)
    if row == "maplibre":
        ax.add_patch(Rectangle((x_min / km, 0), (x_max - x_min) / km, elevation / km, color=COLOR_TERRAIN, alpha=0.55, zorder=0.5))
        ax.text(x_max / km, elevation / km, f"terrain {elevation:,} m ", ha="right", va="bottom", fontsize=8, color="#5d4e36")
    ax.text(x_max / km, 0, "sea level ", ha="right", va="bottom", fontsize=8, color="#5d4e36")

    camera = to_local(state["camera"], *history["origin"])
    target = to_local(state["target"], *history["origin"])
    distance = math.dist(camera, target)

    # Field of view and line of sight
    rays = fov_wedge(camera, target, state["fovy"], 2.2 * distance)
    wedge = Polygon([(camera[0] / km, camera[1] / km), (rays[0][0] / km, rays[0][1] / km), (rays[1][0] / km, rays[1][1] / km)],
                    closed=True, color=COLOR_FOV, alpha=0.18, zorder=2, lw=0)
    ax.add_patch(wedge)
    for ray in rays:
        ax.plot([camera[0] / km, ray[0] / km], [camera[1] / km, ray[1] / km], color=COLOR_FOV, lw=0.8, zorder=2)
    ax.plot([camera[0] / km, target[0] / km], [camera[1] / km, target[1] / km], color=COLOR_CAMERA, lw=1.0, ls="--", zorder=3)

    # Trails of the camera and the target
    for segment in history["targets"]:
        if segment:
            tx, ty = zip(*segment)
            ax.plot([x / km for x in tx], [y / km for y in ty], color=COLOR_TARGET, lw=1.2, alpha=0.5, zorder=3)
    for segment in history["cameras"]:
        if segment:
            cx, cy = zip(*segment)
            ax.plot([x / km for x in cx], [y / km for y in cy], color=COLOR_CAMERA, lw=1.2, alpha=0.4, zorder=3)

    # Where the base map aims
    reference = reference_target(row, zoom, elevation)
    if reference is not None:
        ax.plot(reference[0] / km, reference[1] / km, "o", ms=13, mfc="none", mec=COLOR_REFERENCE, mew=1.4, zorder=4)
    else:
        ax.plot([0, 0], [0, elevation / km], color=COLOR_REFERENCE, lw=1.2, ls=":", zorder=4)
        ax.text(-0.01 * (x_max - x_min) / km, elevation / 2 / km, "MapLibre blends from\nsea level to terrain", fontsize=7.5, ha="right", va="center", color=COLOR_REFERENCE)

    ax.plot(camera[0] / km, camera[1] / km, marker="s", ms=8, color=COLOR_CAMERA, zorder=5)
    ax.plot(target[0] / km, target[1] / km, marker="X", ms=10, color=COLOR_TARGET, mec="white", mew=0.8, zorder=6)

    # Jump marker: arrow from the target just below zoom 12 to the target just above
    if jump is not None:
        (bx, by), (ax_, ay) = jump["target"]
        if math.dist((bx, by), (ax_, ay)) > 1.0:
            (cbx, cby), _ = jump["camera"]
            ax.plot(cbx / km, cby / km, marker="s", ms=8, mfc="none", mec=COLOR_CAMERA, mew=1.2, alpha=0.6, zorder=5)
            ax.plot(bx / km, by / km, marker="X", ms=10, mfc="none", mec=COLOR_TARGET, mew=1.2, alpha=0.7, zorder=6)
            ax.annotate("", xy=(ax_ / km, ay / km), xytext=(bx / km, by / km),
                        arrowprops=dict(arrowstyle="->", color=COLOR_BROKEN, lw=2.0), zorder=7)
            (cbx, cby), (cax, cay) = jump["camera"]
            ax.annotate("", xy=(cax / km, cay / km), xytext=(cbx / km, cby / km),
                        arrowprops=dict(arrowstyle="->", color=COLOR_BROKEN, lw=2.0), zorder=7)
            ax.text(0.02, 0.03, f"JUMP at zoom 12: target {abs(ax_ - bx) / km:.1f} km south, {abs(ay - by):,.0f} m up",
                    transform=ax.transAxes, fontsize=9, fontweight="bold", color="white", va="bottom",
                    bbox=dict(boxstyle="round,pad=0.3", fc=COLOR_BROKEN, ec="none"), zorder=9)
        else:
            ax.text(0.02, 0.03, "no jump at zoom 12", transform=ax.transAxes, fontsize=9, fontweight="bold",
                    color="white", va="bottom", bbox=dict(boxstyle="round,pad=0.3", fc=COLOR_FIXED, ec="none"), zorder=9)

    # Status: viewport class and target offset from the base map's aim
    if reference is not None:
        offset_north = target[0] - reference[0]
        offset_up = target[1] - reference[1]
        if abs(offset_north) < 1 and abs(offset_up) < 1:
            offset = "target on the map center" if row == "plain" else "target on the base map's target"
        else:
            offset = f"target {abs(offset_north):,.0f} m {'north' if offset_north > 0 else 'south'}, {abs(offset_up):,.0f} m {'below' if offset_up < 0 else 'above'}"
            if row == "plain":
                offset = f"target {abs(offset_north):,.0f} m off the map center"
    else:
        offset = f"target {target[1]:,.0f} m above sea level"
        if abs(target[0]) >= 1:
            offset += f", {abs(target[0]):,.0f} m {'north' if target[0] > 0 else 'south'}"
    ax.text(0.98, 0.96, f"{state['viewport']}, field of view {state['fovy']:.1f}°\n{offset}", transform=ax.transAxes, ha="right", va="top", fontsize=8.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#bbbbbb", alpha=0.9), zorder=8)


def draw_timeline(ax, zoom, zoom_range):
    ax.clear()
    ax.set_xlim(*zoom_range)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.tick_params(labelsize=8)
    ax.set_xlabel("zoom", fontsize=9)
    ax.axvspan(*BLEND, color="#cccccc", alpha=0.6)
    ax.text(sum(BLEND) / 2, 0.75, "MapLibre globe blends to Mercator", ha="center", va="center", fontsize=8)
    ax.axvline(SWITCH_ZOOM, color=COLOR_BROKEN, lw=1.5)
    ax.text(SWITCH_ZOOM + 0.02, 0.25, "GlobeView: GlobeViewport -> WebMercatorViewport", ha="left", va="center", fontsize=8, color=COLOR_BROKEN)
    ax.axvspan(zoom_range[0], zoom, ymin=0, ymax=0.12, color=COLOR_CAMERA)
    ax.plot([zoom], [0.06], marker="v", color=COLOR_CAMERA, ms=9, clip_on=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", type=Path, required=True, help="camera path dumped with deck.gl master")
    parser.add_argument("--fixed", type=Path, required=True, help="camera path dumped with the fix")
    parser.add_argument("--out", type=Path, required=True, help="output video (.mp4)")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--still", type=float, action="append", default=[], help="also write a PNG at this zoom")
    parser.add_argument("--stills-only", action="store_true", help="write the PNGs, no video")
    args = parser.parse_args()

    data = {"master": json.loads(args.master.read_text()), "fixed": json.loads(args.fixed.read_text())}
    meta = data["master"]
    origin = (meta["longitude"], meta["latitude"])
    elevation = meta["elevation"]
    frames = {name: d["frames"] for name, d in data.items()}
    zooms = [f["zoom"] for f in frames["master"]]
    assert zooms == [f["zoom"] for f in frames["fixed"]]

    order, switch_index = frame_schedule(frames["master"], args.fps)

    fig = plt.figure(figsize=(12.8, 8.0), dpi=100)
    grid = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.16], hspace=0.32, wspace=0.08, left=0.05, right=0.99, top=0.84, bottom=0.07)
    axes = [[fig.add_subplot(grid[r, c]) for c in range(2)] for r in range(2)]
    timeline = fig.add_subplot(grid[2, :])
    aspect = 2.15

    def jump_for(name, row, index):
        if switch_index is None or index < switch_index:
            return None
        before = frames[name][switch_index - 1][row]
        after = frames[name][switch_index][row]
        return {
            "target": (to_local(before["target"], *origin), to_local(after["target"], *origin)),
            "camera": (to_local(before["camera"], *origin), to_local(after["camera"], *origin)),
        }

    def render(index):
        zoom = zooms[index]
        fig.suptitle(f"deck.gl GlobeView camera, side view facing north (pitch {meta['pitch']}, Mount St. Helens)   zoom {zoom:.2f}",
                     fontsize=13, y=0.975)
        for r, (row, row_title) in enumerate(ROWS):
            distance = math.dist(*(to_local(frames["fixed"][index]["plain"][k], *origin) for k in ("camera", "target")))
            extent = row_extent(distance, elevation if row == "maplibre" else 0, aspect)
            for c, (name, column_title, color) in enumerate(COLUMNS):
                ax = axes[r][c]
                # Trails, split at the switch so that a jump shows as a gap, not as a path
                split = switch_index if switch_index is not None and switch_index <= index else index + 1
                segments = [range(0, split), range(split, index + 1)]
                history = {
                    "origin": origin,
                    "targets": [[to_local(frames[name][i][row]["target"], *origin) for i in seg] for seg in segments],
                    "cameras": [[to_local(frames[name][i][row]["camera"], *origin) for i in seg] for seg in segments],
                }
                draw_panel(ax, frames[name][index][row], history, row, name, zoom, elevation, extent, jump_for(name, row, index))
                ax.set_title(row_title, fontsize=10, loc="left")
                if c == 0:
                    ax.set_ylabel("altitude (km)", fontsize=9)
                if r == 1:
                    ax.set_xlabel("north of the map center (km)", fontsize=9)
        draw_timeline(timeline, zoom, (zooms[0], zooms[-1]))

    legend_items = [
        plt.Line2D([], [], marker="s", ls="", color=COLOR_CAMERA, label="deck.gl camera"),
        plt.Line2D([], [], marker="X", ls="", color=COLOR_TARGET, label="deck.gl camera target"),
        plt.Line2D([], [], marker="o", ls="", mfc="none", mec=COLOR_REFERENCE, label="base map's camera target, or the map center"),
        matplotlib.patches.Patch(color=COLOR_FOV, alpha=0.35, label="vertical field of view"),
    ]
    fig.legend(handles=legend_items, loc="upper center", ncol=4, fontsize=9, frameon=False, bbox_to_anchor=(0.5, 0.95))
    for c, (name, column_title, color) in enumerate(COLUMNS):
        fig.text(0.05 + c * 0.475 + 0.235, 0.875, column_title, ha="center", fontsize=13, fontweight="bold", color=color)

    for still in args.still:
        index = min(range(len(zooms)), key=lambda i: abs(zooms[i] - still))
        render(index)
        fig.savefig(args.out.with_name(f"{args.out.stem}-z{zooms[index]:.2f}.png"))

    if args.stills_only:
        return

    import imageio_ffmpeg

    plt.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    writer = FFMpegWriter(fps=args.fps, codec="libx264", extra_args=["-pix_fmt", "yuv420p", "-crf", "20"])
    with writer.saving(fig, str(args.out), dpi=100):
        for count, index in enumerate(order):
            render(index)
            writer.grab_frame()
            if count % 50 == 0:
                print(f"frame {count}/{len(order)} zoom {zooms[index]:.2f}", flush=True)
    print(f"wrote {args.out} ({len(order)} frames, {len(order) / args.fps:.1f} s)")


if __name__ == "__main__":
    main()
