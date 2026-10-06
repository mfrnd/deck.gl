// One bundle per deck.gl version, exposed as window.deck for view.html
import {Deck, _GlobeView as GlobeView, MapView} from '@deck.gl/core';
import {PathLayer, ScatterplotLayer} from '@deck.gl/layers';
import {TerrainLayer} from '@deck.gl/geo-layers';
import {MapLibreOverlay} from '@deck.gl/maplibre';

(window as any).deck = {Deck, GlobeView, MapView, PathLayer, ScatterplotLayer, TerrainLayer, MapLibreOverlay};
