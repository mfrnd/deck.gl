// Runs campath.spec.ts in Node against the deck.gl sources of the checked out version
import {defineConfig} from 'vitest/config';
import {resolve} from 'path';

const rootDir = resolve(import.meta.dirname, '../..');

export default defineConfig({
  root: rootDir,
  resolve: {
    alias: {
      '@deck.gl/core': resolve(rootDir, 'modules/core/src')
    }
  },
  test: {
    environment: 'node',
    include: ['scripts/globe-camera-path/campath.spec.ts'],
    globals: false
  }
});
