// Dumps GlobeView's camera for the animation in plot_campath.py, see README.md
import {test} from 'vitest';
import {writeFileSync} from 'fs';
import {_GlobeView as GlobeView} from '@deck.gl/core';
import {getMapLibreViewState} from '../../modules/maplibre/src/deck-utils';

const OUT = process.env.CAMPATH_OUT!;
const [longitude, latitude, elevation] = [-122.19, 46.2, 2143];
const [width, height, pitch] = [800, 600, 60];

function mockMap(zoom: number) {
  return {
    getCenter: () => ({lng: longitude, lat: latitude}),
    getZoom: () => zoom,
    getBearing: () => 0,
    getPitch: () => pitch,
    getPadding: () => ({left: 0, right: 0, top: 0, bottom: 0}),
    getRenderWorldCopies: () => true,
    getCenterElevation: () => elevation,
    getProjection: () => ({type: 'globe'})
  } as any;
}

test('dump camera path', () => {
  const view = new GlobeView({id: 'globe'});
  const frames = [];
  for (let i = 0; i <= 300; i++) {
    const zoom = 10 + i / 100;
    const scenarios = {
      plain: {longitude, latitude, zoom, pitch, bearing: 0},
      maplibre: getMapLibreViewState(mockMap(zoom))
    };
    const frame: any = {zoom};
    for (const [name, viewState] of Object.entries(scenarios)) {
      const viewport: any = view.makeViewport({width, height, viewState});
      frame[name] = {
        viewport: viewport.constructor.name,
        position: (viewState as any).position || null,
        fovy: viewport.fovy,
        camera: viewport.unprojectPosition(viewport.cameraPosition),
        target: viewport.unprojectPosition(viewport.center)
      };
    }
    frames.push(frame);
  }
  writeFileSync(OUT, JSON.stringify({longitude, latitude, elevation, width, height, pitch, frames}));
});
