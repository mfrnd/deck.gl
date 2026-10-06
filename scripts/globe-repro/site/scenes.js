// Scenes for compare.html (left vs right build) and view.html (one build)

export const BUILDS = {
  master: 'deck.gl master',
  pr1: 'cartesian z fix (fix/7064-cartesian-z-scale)',
  pr2: 'globe camera fix (fix/7064-maplibre-globe-camera-elevation)',
  sincos: 'master + globe sin/cos patch'
};

const TERRARIUM = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const ST_HELENS = [-122.19, 46.2];

export const SCENES = {
  'globe-position': {
    title: 'GlobeView with viewState.position, no base map',
    description:
      'position = [0, 0, 2000] puts the camera target 2,000 m above the map center (red dot). ' +
      'It belongs on the crosshair. GlobeView switches from GlobeViewport to WebMercatorViewport above zoom 12.',
    builds: ['master', 'pr2'],
    zoom: [11.5, 12.5, 11.95],
    kind: 'deck',
    viewState: zoom => ({longitude: ST_HELENS[0], latitude: ST_HELENS[1], zoom, pitch: 60, bearing: 0, position: [0, 0, 2000]}),
    marker: {position: [ST_HELENS[0], ST_HELENS[1], 2000], mast: true},
    globe: true
  },
  'maplibre-globe-terrain': {
    title: "MapLibreOverlay on MapLibre's globe with terrain",
    description:
      'Cyan: MapLibre circles. Pink: deck.gl points at the same places and terrain heights. ' +
      'They belong inside the cyan circles. MapLibre blends its globe into Mercator between zoom 11 and 12.',
    builds: ['master', 'pr2'],
    zoom: [10, 12.5, 11.5],
    kind: 'maplibre',
    terrarium: TERRARIUM,
    center: ST_HELENS,
    points: [-0.03, 0, 0.03].flatMap(dx => [-0.02, 0, 0.02].map(dy => [ST_HELENS[0] + dx, ST_HELENS[1] + dy]))
  },
  'terrain-layer': {
    title: 'TerrainLayer on a MapView (no globe)',
    description:
      'Pink: markers at their DEM elevation. They belong on the terrain surface. ' +
      'Below zoom 12, master draws cartesian z at the scale of the equator, so the terrain is too flat and pops up at zoom 12. ' +
      'The camera aims 2,000 m above the view center (viewState.position, which MapView handles correctly in both builds).',
    builds: ['master', 'pr1'],
    zoom: [11.5, 12.5, 11.9],
    kind: 'terrain',
    terrarium: TERRARIUM,
    viewState: zoom => ({longitude: -122.19, latitude: 46.18, zoom, pitch: 60, bearing: 0, position: [0, 0, 2000]}),
    markers: [
      [-122.1944, 46.1914],
      [-122.21, 46.2],
      [-122.17, 46.205],
      [-122.2, 46.18]
    ]
  },
  'globe-sincos': {
    title: 'GlobeView alone, looking straight down near Zurich',
    description:
      'Red dot: the map center on the ground. It belongs on the crosshair. ' +
      'The two sides only differ under software rendering (SwiftShader), whose sin/cos are inaccurate: ' +
      'on a GPU both are correct.',
    builds: ['master', 'sincos'],
    zoom: [10, 12.5, 11.95],
    kind: 'deck',
    viewState: zoom => ({longitude: 8.5, latitude: 47.3, zoom, pitch: 0, bearing: 0}),
    marker: {position: [8.5, 47.3, 0], mast: false},
    globe: true
  }
};

// Grid lines split into short segments: on the globe a long straight segment is a chord below the ground
export function grid(longitude, latitude) {
  const paths = [];
  const line = (from, to, steps = 60) =>
    Array.from({length: steps + 1}, (_, k) => [from[0] + ((to[0] - from[0]) * k) / steps, from[1] + ((to[1] - from[1]) * k) / steps]);
  for (let i = -30; i <= 30; i++) {
    const major = i % 5 === 0;
    paths.push({path: line([longitude + i * 0.01, latitude - 0.3], [longitude + i * 0.01, latitude + 0.3]), major});
    paths.push({path: line([longitude - 0.3, latitude + i * 0.01], [longitude + 0.3, latitude + i * 0.01]), major});
  }
  return paths;
}
