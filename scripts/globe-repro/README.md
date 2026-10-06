# Globe reproductions

Side-by-side comparisons of deck.gl builds around zoom 12, where `GlobeView` switches from
`GlobeViewport` to `WebMercatorViewport` and the flat projection switches from `WEB_MERCATOR` to
`WEB_MERCATOR_AUTO_OFFSET`. Not meant for upstream: everything lives in this folder.

## Comparisons

| Page | Builds | What to look for |
|---|---|---|
| GlobeView with `viewState.position`, no base map | master vs camera fix | The red dot (2,000 m above the map center, where `position` puts the camera target) belongs on the crosshair. On master it is off below zoom 12 and jumps at 12. |
| `MapLibreOverlay` on MapLibre's globe with terrain | master vs camera fix | Pink deck.gl points belong inside MapLibre's cyan circles. |
| `TerrainLayer` on a `MapView` | master vs cartesian z fix | Pink markers at their DEM elevation belong on the terrain. On master the terrain is too flat below zoom 12 and pops up at 12. |
| GlobeView alone near Zurich | master live on the GPU vs master and master + `patches/globe-sincos.patch` recorded with SwiftShader | The red dot belongs on the crosshair. Software rendering's inaccurate `sin`/`cos` move it on master, up to 46 px at zoom 12. |

Below each view, a side view shows that build's camera in the north-south plane through the map center,
seen from the east, at the same scale on both sides: the camera and its line of sight to the target
(`unprojectPosition` of the viewport's `cameraPosition` and `center`), the camera's trace over the zoom range
with a dot every 0.1 zoom, and red dashes where it jumps. For the MapLibre scene the overlay's camera depends on
MapLibre's state, so its trace fills in as the map is zoomed. In the `TerrainLayer` and sin/cos comparisons the
camera is the same in both builds; their differences are in how positions are drawn.

In the `TerrainLayer` comparison, "Measured terrain" adds the surface each build draws: `pickObject` with
`unproject3D` along the center column of its view, which lies in the side view's plane, drawn in orange over the
elevation data, with the median ratio of drawn to actual height (master: 69% below zoom 12, the cosine of the
latitude; the fix: 100%).

A page cannot choose its renderer, so the software rendering panels of the sin/cos comparison are frames recorded
with SwiftShader, one per 0.01 zoom step with the measured offset and camera, under `recorded/` in the site. All
its panels render at 640×480 and are scaled to fit, so the live and recorded panels match.

Builds are fixed commits, listed in `build.mjs` and in the site's `build.json`:

- master: `d1b0ae43`
- cartesian z fix: `0e141bb1` (branch `fix/7064-cartesian-z-scale`)
- camera fix: `074e492c` (branch `fix/7064-maplibre-globe-camera-elevation`)
- sin/cos: master + `patches/globe-sincos.patch` (`project_globe_` computes sin/cos with a polynomial)

Judge the first three on a GPU. Under software rendering (SwiftShader, as in headless browsers and
deck.gl's CI) the globe projection is off by up to about a kilometer on its own, which hides them.

## Build and run

From the repo root, after `yarn`:

```sh
node scripts/globe-repro/build.mjs --out /tmp/globe-repro-site
python3 -m http.server --directory /tmp/globe-repro-site 8080
# open http://localhost:8080/
```

`build.mjs` extracts `modules/` of each commit with `git archive`, applies the patch if any and
bundles `site/entry.ts` with esbuild against the repo's `node_modules`; the working tree is not
touched. It also copies MapLibre GL JS 6 (its worker must be served from the same origin).

To see the sin/cos difference in Chrome, start it with
`--use-angle=swiftshader --enable-unsafe-swiftshader`; the pages show which renderer is in use.

`compare.html?scene=<id>&zoom=<zoom>` opens a comparison at a zoom level, `&measure=1` with measured terrain.

To record the software rendering panels into a built site (`out/` in the served folder receives the posts):

```sh
mkdir -p /tmp/globe-repro && node scripts/globe-repro/build.mjs --out /tmp/globe-repro/site
cp scripts/globe-repro/tools/record.html /tmp/globe-repro/
python3 scripts/globe-repro/tools/server.py --dir /tmp/globe-repro &
# in Chrome started with --use-angle=swiftshader --enable-unsafe-swiftshader (or tools/run_sw.sh):
#   http://127.0.0.1:8791/record.html?site=site/&scene=globe-sincos&builds=master,sincos&v=rec
python3 scripts/globe-repro/tools/save_recording.py --site /tmp/globe-repro/site \
  /tmp/globe-repro/out/result-rec-master.json /tmp/globe-repro/out/result-rec-sincos.json
```
`compare.html?scene=<id>&autotest=<name>&zooms=11.9,12,12.01` steps through the zoom levels and posts
both readouts to `/result?v=<name>` (see `tools/server.py`).

## Tools

`tools/` holds the harness used for the measurements and videos:

- `page.html`: frames mode (`m=frames`, with `lng`, `lat`, `h`, `pitch`, `z0`, `z1`, `step`, `seg`),
  drawn vs projected positions (`m=check`) and the `TerrainLayer` scene (`m=terrain`)
- `ml.html`: MapLibre globe with terrain; `perf.html`: projection and frame-time benchmarks;
  `trig.html`: GLSL `sin`/`cos` accuracy via transform feedback
- `server.py`: serves the pages and stores posted results in `out/`
- `record.html` and `save_recording.py`: record frames of a scene in the browser's renderer into the site
- `run_edge.sh`: headless Windows Edge on the GPU from WSL; `run_sw.sh`: SwiftShader in Playwright's
  headless shell
- `make_gif.py`, `make_demo.py`, `make_demo_2x2.py`: side-by-side GIFs and videos with measured readouts

The tool pages load `deck-<name>.js` from their own folder, built from `tools/entry*.ts`:

```sh
npx esbuild scripts/globe-repro/tools/entry.ts --bundle --format=iife --minify \
  --outfile=scripts/globe-repro/tools/deck-<name>.js \
  --alias:@deck.gl/core=./modules/core/src --alias:@deck.gl/layers=./modules/layers/src
```

## Pitfalls found on the way

- Long straight path segments on the globe are chords below the ground (a 0.6° segment dips about
  90 m) and pop up at zoom 12. Split lines into short segments (`seg` in `page.html`).
- Markers on the ground get half covered by ground lines in Mercator mode. Draw them with
  `parameters: {depthCompare: 'always'}`.
- Headless browsers render with SwiftShader unless told otherwise; check the renderer string.
- Headless Edge does not run `requestAnimationFrame` while the load event is held back; let pages load
  and poll for results instead.
- `TerrainLayer` passes the elevation range of its tiles (`zRange`) to its `TileLayer` only when it renders its
  sublayers again. When the view changes while the first tiles load, that may not happen, and picking then culls
  the tiles as if they were at sea level and misses the high ones. `view.html` makes it render them before measuring.
- An overlaid `MapLibreOverlay` keeps its WebGL context after removal; tests in one page can run out of
  contexts. Use `interleaved: true` in tests.

Terrain: Terrarium tiles from the AWS Open Data terrain tiles (Mapzen; USGS 3DEP, GMTED2010, SRTM).
