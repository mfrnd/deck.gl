import {Deck, _GlobeView as GlobeView, MapView} from '@deck.gl/core';
import {PathLayer, ScatterplotLayer} from '@deck.gl/layers';
(window as any).deckRepro = {Deck, GlobeView, MapView, PathLayer, ScatterplotLayer};
