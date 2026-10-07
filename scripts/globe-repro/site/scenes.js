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
    title: 'GlobeView with viewState.position, no base map, looking straight down',
    description:
      'position = [0, 0, 2000] puts the camera target 2,000 m above the map center (red dot, on a mast from the ground). ' +
      'It belongs on the crosshair. GlobeView switches from GlobeViewport to WebMercatorViewport above zoom 12. ' +
      'How far off master is depends on where the map is: near the North Pole it is almost right.',
    builds: ['master', 'pr2'],
    zoom: [11.5, 12.5, 11.95],
    kind: 'deck',
    // ?at= picks one, the first is the default
    locations: {
      'st-helens': {name: 'Mount St. Helens, 46.2° N', center: ST_HELENS},
      equator: {name: 'the equator', center: [ST_HELENS[0], 0]},
      south: {name: '46.2° S', center: [ST_HELENS[0], -46.2]},
      'north-pole': {name: '89.5° N, near the North Pole', center: [0, 89.5]}
    },
    viewState: (zoom, [longitude, latitude] = ST_HELENS) =>
      ({longitude, latitude, zoom, pitch: 0, bearing: 0, position: [0, 0, 2000]}),
    marker: {position: [ST_HELENS[0], ST_HELENS[1], 2000], mast: true},
    squareGrid: true,
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
    pitch: 60,
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
    // Checkbox for the terrain as each build draws it, picked along the center column, in the side views
    measure: true,
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
      'Red dot: the map center on the ground. It belongs on the crosshair. A GPU draws it there. ' +
      'Software rendering (SwiftShader, as in headless browsers and CI) has inaccurate sin/cos, which moves the globe ' +
      'below zoom 12; the sin/cos patch computes them in the shader. A page cannot choose its renderer, so the ' +
      'software panels are frames recorded with SwiftShader, with their measured offsets.',
    builds: ['master', 'sincos'],
    // Software rendering cannot be chosen from a page: its panels are frames recorded with tools/record.html
    panels: [
      {build: 'master', label: 'GPU, live in this browser: master'},
      {build: 'master', recording: 'swiftshader', tone: 'before', label: 'SwiftShader, recorded: master'},
      {build: 'sincos', recording: 'swiftshader', tone: 'after', label: 'SwiftShader, recorded: master + sin/cos patch'}
    ],
    // Render size of every panel, scaled to fit, so live and recorded frames match
    size: [640, 480],
    zoom: [10, 12.5, 11.95],
    kind: 'deck',
    viewState: zoom => ({longitude: 8.5, latitude: 47.3, zoom, pitch: 0, bearing: 0}),
    marker: {position: [8.5, 47.3, 0], mast: false},
    globe: true
  }
};

// The scene at one of its locations (?at=, else the first one), or the scene itself
export function sceneAt(scene, at) {
  if (!scene.locations) return scene;
  const key = at in scene.locations ? at : Object.keys(scene.locations)[0];
  const {name, center} = scene.locations[key];
  return {
    ...scene,
    at: key,
    title: `${scene.title}, at ${name}`,
    viewState: zoom => scene.viewState(zoom, center),
    marker: {...scene.marker, position: [...center, scene.marker.position[2]]}
  };
}

// Grid lines split into short segments: on the globe a long straight segment is a chord below the ground.
// With square, the cells are about as wide as they are high, also near the poles.
export function grid(longitude, latitude, square = false) {
  const paths = [];
  const lngStep = square ? 0.01 / Math.max(Math.cos((latitude * Math.PI) / 180), 0.01) : 0.01;
  const clamp = lat => Math.max(-89.99, Math.min(89.99, lat));
  const line = (from, to, steps = 60) =>
    Array.from({length: steps + 1}, (_, k) => [from[0] + ((to[0] - from[0]) * k) / steps, from[1] + ((to[1] - from[1]) * k) / steps]);
  for (let i = -30; i <= 30; i++) {
    const major = i % 5 === 0;
    paths.push({path: line([longitude + i * lngStep, clamp(latitude - 0.3)], [longitude + i * lngStep, clamp(latitude + 0.3)]), major});
    paths.push({path: line([longitude - 30 * lngStep, clamp(latitude + i * 0.01)], [longitude + 30 * lngStep, clamp(latitude + i * 0.01)]), major});
  }
  return paths;
}
