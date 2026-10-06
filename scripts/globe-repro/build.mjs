// Builds the comparison site: one deck.gl bundle per build, plus the pages and MapLibre.
// Usage, from the repo root after `yarn`: node scripts/globe-repro/build.mjs --out /tmp/globe-repro-site
// Each build is a commit (and optionally a patch from patches/), extracted with `git archive`, so the
// working tree is never touched. Override a build with --build name=commit[+patch-file].

import {execFileSync} from 'child_process';
import {cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync} from 'fs';
import {tmpdir} from 'os';
import {dirname, join, resolve} from 'path';
import {fileURLToPath} from 'url';
import {build} from 'esbuild';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '../..');

const BUILDS = {
  master: {commit: 'd1b0ae43f982a0a7ec214bd7542f812e5d49744a'},
  pr1: {commit: '0e141bb1'},
  pr2: {commit: '074e492c'},
  sincos: {commit: 'd1b0ae43f982a0a7ec214bd7542f812e5d49744a', patch: 'globe-sincos.patch'}
};
const PACKAGES = ['core', 'layers', 'geo-layers', 'mesh-layers', 'extensions', 'maplibre'];
const SITE_FILES = ['index.html', 'compare.html', 'view.html', 'scenes.js', 'style.css'];
const MAPLIBRE_FILES = ['maplibre-gl.mjs', 'maplibre-gl-shared.mjs', 'maplibre-gl-worker.mjs', 'maplibre-gl.css'];

function parseArgs(argv) {
  const args = {out: null, builds: {...BUILDS}};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--out') args.out = resolve(argv[++i]);
    else if (argv[i] === '--build') {
      const [name, spec] = argv[++i].split('=');
      const [commit, patch] = spec.split('+');
      args.builds[name] = {commit, patch};
    } else throw new Error(`Unknown argument ${argv[i]}`);
  }
  if (!args.out) throw new Error('--out is required');
  return args;
}

function git(...args) {
  return execFileSync('git', args, {cwd: ROOT, encoding: 'utf8'}).trim();
}

async function buildBundle(name, {commit, patch}, out) {
  const sha = git('rev-parse', `${commit}^{commit}`);
  const source = mkdtempSync(join(tmpdir(), `globe-repro-${name}-`));
  try {
    const archive = execFileSync('git', ['archive', sha, 'modules'], {cwd: ROOT, maxBuffer: 1 << 30});
    execFileSync('tar', ['-x', '-C', source], {input: archive});
    if (patch) {
      execFileSync('git', ['apply', join(HERE, 'patches', patch)], {cwd: source});
    }
    const alias = Object.fromEntries(PACKAGES.map(p => [`@deck.gl/${p}`, join(source, 'modules', p, 'src')]));
    await build({
      entryPoints: [join(HERE, 'site', 'entry.ts')],
      bundle: true,
      format: 'iife',
      minify: true,
      outfile: join(out, 'bundles', `deck-${name}.js`),
      alias,
      nodePaths: [join(ROOT, 'node_modules')],
      logLevel: 'error'
    });
    return {commit: sha.slice(0, 8), patch: patch || null};
  } finally {
    rmSync(source, {recursive: true, force: true});
  }
}

const args = parseArgs(process.argv.slice(2));
mkdirSync(join(args.out, 'bundles'), {recursive: true});
const info = {builds: {}, generated: new Date().toISOString()};
for (const [name, spec] of Object.entries(args.builds)) {
  info.builds[name] = await buildBundle(name, spec, args.out);
  console.log(`built ${name}: ${info.builds[name].commit}${spec.patch ? ` + ${spec.patch}` : ''}`);
}
for (const file of SITE_FILES) cpSync(join(HERE, 'site', file), join(args.out, file));
mkdirSync(join(args.out, 'maplibre'), {recursive: true});
for (const file of [...MAPLIBRE_FILES, '../LICENSE.txt']) {
  cpSync(join(ROOT, 'node_modules', 'maplibre-gl-v6', 'dist', file), join(args.out, 'maplibre', file.replace('../', '')));
}
writeFileSync(join(args.out, 'build.json'), JSON.stringify(info, null, 2));
// GitHub Pages: serve files as they are
writeFileSync(join(args.out, '.nojekyll'), '');
console.log(`site written to ${args.out}`);
