// One bundle per deck.gl build, exposed as window.deckBuild for panel.html
import {Deck, MapView} from '@deck.gl/core';
import {TerrainLayer} from '@deck.gl/geo-layers';

(window as any).deckBuild = {Deck, MapView, TerrainLayer};
