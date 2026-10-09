// Builds the fixture: one deck.gl bundle per build plus the pages.
// Usage, from the deck.gl repo root: node <this dir>/build.mjs --out <dir> --build master=<commit> --build fix=worktree
// A commit (optionally `<commit>+<patch file>`) is extracted with `git archive`; `worktree` bundles the working
// tree's modules/.
import {execFileSync} from 'child_process';
import {cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync} from 'fs';
import {tmpdir} from 'os';
import {dirname, join, resolve} from 'path';
import {createRequire} from 'module';
import {fileURLToPath} from 'url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = process.cwd();
// esbuild from the repo's node_modules
const {build} = createRequire(join(ROOT, 'package.json'))('esbuild');
const PACKAGES = ['core', 'layers', 'geo-layers', 'mesh-layers', 'extensions'];
const PAGES = ['index.html', 'panel.html'];

const args = {out: null, builds: {}};
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === '--out') args.out = resolve(argv[++i]);
  else if (argv[i] === '--build') {
    const [name, commit] = argv[++i].split('=');
    args.builds[name] = commit;
  } else throw new Error(`Unknown argument ${argv[i]}`);
}
if (!args.out || !Object.keys(args.builds).length) throw new Error('--out and --build are required');

const git = (...a) => execFileSync('git', a, {cwd: ROOT, encoding: 'utf8'}).trim();

async function bundle(name, spec) {
  const [commit, patch] = spec.split('+');
  let source = ROOT;
  let label;
  if (commit === 'worktree') {
    label = `${git('rev-parse', '--short=8', 'HEAD')}+worktree`;
  } else {
    const sha = git('rev-parse', `${commit}^{commit}`);
    label = sha.slice(0, 8);
    source = mkdtempSync(join(tmpdir(), `terrain-picking-${name}-`));
    const archive = execFileSync('git', ['archive', sha, 'modules'], {cwd: ROOT, maxBuffer: 1 << 30});
    execFileSync('tar', ['-x', '-C', source], {input: archive});
    if (patch) {
      execFileSync('git', ['apply', resolve(patch)], {cwd: source});
      label += '+patch';
    }
  }
  try {
    await build({
      entryPoints: [join(HERE, 'entry.ts')],
      bundle: true,
      format: 'iife',
      minify: true,
      outfile: join(args.out, 'bundles', `deck-${name}.js`),
      alias: Object.fromEntries(PACKAGES.map(p => [`@deck.gl/${p}`, join(source, 'modules', p, 'src')])),
      nodePaths: [join(ROOT, 'node_modules')],
      // lerc (loaders.gl) imports Node's module only when it runs in Node, as in deck.gl's .ocularrc.js
      external: ['module'],
      logLevel: 'error'
    });
  } finally {
    if (source !== ROOT) rmSync(source, {recursive: true, force: true});
  }
  return label;
}

mkdirSync(join(args.out, 'bundles'), {recursive: true});
const info = {builds: {}, generated: new Date().toISOString()};
for (const [name, commit] of Object.entries(args.builds)) {
  info.builds[name] = await bundle(name, commit);
  console.log(`built ${name}: ${info.builds[name]}`);
}
for (const page of PAGES) cpSync(join(HERE, page), join(args.out, page));
writeFileSync(join(args.out, 'build.json'), JSON.stringify(info, null, 2));
console.log(`fixture written to ${args.out}`);
