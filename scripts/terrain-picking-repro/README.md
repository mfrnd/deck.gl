# TerrainLayer picking reproduction

Two deck.gl builds side by side, each with a `TerrainLayer` at Mount St. Helens. Not meant for upstream:
everything lives in this folder.

When the view changes while the first tiles load, picking misses high tiles on master. `TerrainLayer` stores the
elevation range of the loaded tiles in `onViewportLoad`, inside the `LayerManager` update pass, which drops the
update that `setState` requests. The `TileLayer` keeps `zRange: null`, so picking culls tiles as if they were at
sea level, until something else updates the layer (a drag, for example).

Builds:

- master: `b04c8f2b`
- fix: master + `layer-manager-fix.patch` (`LayerManager` keeps updates that layers request during its update
  pass; the change of branch `fix/layer-update-during-update`)

## Live page

`index.html` zooms both panels from 11 to 12.64 in three steps 70 ms apart, as soon as both have requested their
first tiles, and waits until every tile has loaded. Then a click, drag or zoom in one panel is repeated in the
other, and "Pick grid" picks a 40 × 26 grid with `deck.pickObject` in both (green: picked, red: nothing). Each
panel shows the clicks with the picked elevation, a log of the `TerrainLayer`'s `zRange` and its `TileLayer`'s, and
whether an update is pending that the `LayerManager` has not scheduled.

The tile URLs get a new query key on every page load, so the first tiles never come from the browser cache.
Without the box "Zoom while the first tiles load" (`?early=0`), the same zoom comes after the first tiles have
loaded, and master picks every point.

## Build and run

From the repo root, after `yarn`:

```sh
node scripts/terrain-picking-repro/build.mjs --out /tmp/terrain-picking-site \
  --build master=b04c8f2b --build fix=b04c8f2b+scripts/terrain-picking-repro/layer-manager-fix.patch
python3 -m http.server --directory /tmp/terrain-picking-site 8080
# open http://localhost:8080/
```

`build.mjs` extracts `modules/` of each commit with `git archive`, applies the patch if any and bundles
`entry.ts` with esbuild against the repo's `node_modules`; `--build <name>=worktree` bundles the working tree
instead. The site is static: `index.html`, `panel.html`, `build.json` and one bundle per build.

## Video

`index.html?recorder=1` leaves the input and the captions to `record.mjs`, which sends the same real mouse input
to both panels: three mouse wheel steps half a second after the `Deck` is created, four clicks, the grid and a
small drag.

```sh
node scripts/terrain-picking-repro/record.mjs --browser <path to msedge or chrome> \
  --site /tmp/terrain-picking-site --out /tmp/terrain-picking-frames \
  --clicks '0.5,0.42;0.33,0.33;0.68,0.55;0.5,0.72' --pan 1
python3 scripts/terrain-picking-repro/make_video.py /tmp/terrain-picking-frames --out terrain-picking.mp4 --hold 2.5
```

`record.mjs` serves the site itself, starts the browser headless with the cache disabled and closes it again, and
saves the screencast frames with their timestamps (`--probe 1` stops after the zoom with a screenshot). It needs
Node 22 or later for the built-in `WebSocket`, and the browser must run on the same machine. `make_video.py` needs
`imageio-ffmpeg` and writes an H.264 MP4 in real time.

The video's run (headless Edge on Windows, with the fix bundled from the branch's working tree, labeled
`b04c8f2b+worktree`, the same change as the patch): master picked 0 of 4 clicks and 367 of 1,040 grid points, with
the `TileLayer`'s `zRange` still `null`; the fix picked 4 of 4 clicks (1,646 to 2,294 m) and 1,040 of 1,040.
After the drag, master picks the whole grid too.

## Data

Elevation: AWS Terrain Tiles (Terrarium encoding, `s3.amazonaws.com/elevation-tiles-prod`; Mapzen, from USGS
3DEP, GMTED2010, SRTM and others).
