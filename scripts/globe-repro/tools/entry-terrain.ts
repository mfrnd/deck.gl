import {Deck, MapView} from '@deck.gl/core';
import {ScatterplotLayer} from '@deck.gl/layers';
import {TerrainLayer} from '@deck.gl/geo-layers';
(window as any).deckRepro = {Deck, MapView, ScatterplotLayer, TerrainLayer};
