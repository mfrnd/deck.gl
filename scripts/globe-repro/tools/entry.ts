import {Deck, _GlobeView as GlobeView, MapView} from '@deck.gl/core';
import {LineLayer, PathLayer, ScatterplotLayer} from '@deck.gl/layers';
(window as any).deckRepro = {Deck, GlobeView, MapView, LineLayer, PathLayer, ScatterplotLayer};
