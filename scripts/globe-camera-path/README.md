# GlobeView camera path, before and after the globe camera fix

`campath.mp4` animates deck.gl's `GlobeView` camera from zoom 10 to 13 at pitch 60 over
Mount St. Helens, in a side view facing north: distance north of the map center against altitude,
at equal scale. It shows the camera, its target and the vertical field of view for deck.gl master
(left) and with the fix (right):

- Top: `GlobeView` alone, without a base map or terrain. Nothing sets `position`, so both versions
  are identical and nothing jumps at zoom 12.
- Bottom: `MapLibreOverlay` on MapLibre's globe with terrain at 2,143 m at the map center, through
  `getMapLibreViewState` with a mocked map. Before the fix the target sits 1.5 km north and 596 m
  below the terrain up to zoom 12 and jumps when `GlobeView` switches from `GlobeViewport` to
  `WebMercatorViewport`. With the fix it rises straight up from sea level at zoom 11, where
  MapLibre's globe camera aims, to the terrain at zoom 12, and does not jump.

Between zoom 11 and 12 MapLibre blends its globe into Web Mercator; no single base map target is
drawn there.

## Regenerate

The camera data comes from the deck.gl sources, dumped once per version:

```sh
# from the repo root, with this folder copied next to the checked out sources
git checkout <master or the fix branch> -- modules
CAMPATH_OUT=$PWD/scripts/globe-camera-path/campath-<master|fixed>.json \
  npx vitest run --config scripts/globe-camera-path/vitest.config.ts
```

Then render the video and stills (Python 3.12, `pip install -r requirements.txt`):

```sh
python scripts/globe-camera-path/plot_campath.py \
  --master scripts/globe-camera-path/campath-master.json \
  --fixed scripts/globe-camera-path/campath-fixed.json \
  --out scripts/globe-camera-path/campath.mp4 --still 12.02
```
