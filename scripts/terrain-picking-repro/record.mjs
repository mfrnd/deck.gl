// Records index.html?recorder=1 in a headless Chromium (Edge or Chrome) that this script starts and closes again.
// It serves the built fixture itself, sends real mouse input through the DevTools protocol to both panels and saves
// the screencast frames with their timestamps; make_video.py turns them into an MP4.
// Usage: node record.mjs --browser <path> --site <built fixture> --out <dir> [--probe 1] [--size 1600x880]
//   [--clicks x,y;x,y] (fractions of a panel) [--pan 1]
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {mkdirSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {extname, join, normalize} from 'node:path';

const args = {size: '1600x880', clicks: '', probe: '', pan: ''};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
for (const name of ['browser', 'site', 'out']) {
  if (!args[name]) throw new Error(`--${name} is required`);
}
const [width, height] = args.size.split('x').map(Number);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const PANELS = ['master', 'fix'];

const TYPES = {'.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css'};
const server = createServer((request, response) => {
  const path = normalize(decodeURIComponent(new URL(request.url, 'http://x').pathname)).replace(/^[\\/]+/, '');
  try {
    const body = readFileSync(join(args.site, path || 'index.html'));
    response.writeHead(200, {'Content-Type': TYPES[extname(path)] || 'application/octet-stream', 'Cache-Control': 'no-store'});
    response.end(body);
  } catch {
    response.writeHead(404);
    response.end();
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;

const port = 9300 + Math.floor(Math.random() * 600);
const profile = join(tmpdir(), `terrain-picking-${port}`);
const browser = spawn(args.browser, ['--headless', '--no-first-run', '--disable-extensions', '--hide-scrollbars',
  `--user-data-dir=${profile}`, `--remote-debugging-port=${port}`, `--window-size=${width},${height}`, 'about:blank'],
  {stdio: 'ignore'});

let socket = null;
let messageId = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++messageId;
  pending.set(id, {resolve, reject});
  socket.send(JSON.stringify({id, method, params}));
});
const evaluate = async expression => {
  const result = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
};
const waitFor = async (expression, ms) => {
  const start = Date.now();
  while (Date.now() - start < ms) {
    if (await evaluate(expression)) return true;
    await sleep(50);
  }
  return false;
};

const frames = [];
const captions = [];
let recording = false;
const caption = async (step, text, detail = '') => {
  captions.push({at: Date.now() / 1000, step, text, detail});
  await evaluate(`setCaption(${JSON.stringify(step)}, ${JSON.stringify(text)}, ${JSON.stringify(detail)})`);
};

// Input: every action goes to both panels at the same place within the panel
let rects = null;
const toPage = (name, [fx, fy]) => {
  const r = rects[name];
  return {x: r.x + fx * r.width, y: r.y + fy * r.height};
};
const mouse = (type, {x, y}, extra = {}) => send('Input.dispatchMouseEvent', {type, x, y, ...extra});
let pointer = [0.5, 0.2];
async function move(to, ms) {
  const from = pointer;
  const steps = Math.max(1, Math.round(ms / 16));
  for (let i = 1; i <= steps; i++) {
    const s = i / steps;
    const e = s < 0.5 ? 2 * s * s : 1 - (-2 * s + 2) ** 2 / 2;
    const at = [from[0] + (to[0] - from[0]) * e, from[1] + (to[1] - from[1]) * e];
    for (const name of PANELS) await mouse('mouseMoved', toPage(name, at));
    await sleep(16);
  }
  pointer = to;
}
async function click(at) {
  for (const name of PANELS) {
    const p = toPage(name, at);
    await mouse('mouseMoved', p);
    await mouse('mousePressed', p, {button: 'left', buttons: 1, clickCount: 1});
    await sleep(40);
    await mouse('mouseReleased', p, {button: 'left', buttons: 0, clickCount: 1});
  }
}
async function wheel(at, deltaY) {
  for (const name of PANELS) await mouse('mouseWheel', toPage(name, at), {deltaX: 0, deltaY});
}
async function drag(from, to, ms) {
  for (const name of PANELS) {
    const steps = Math.max(1, Math.round(ms / 16));
    await mouse('mousePressed', toPage(name, from), {button: 'left', buttons: 1, clickCount: 1});
    for (let i = 1; i <= steps; i++) {
      const s = i / steps;
      await mouse('mouseMoved', toPage(name, [from[0] + (to[0] - from[0]) * s, from[1] + (to[1] - from[1]) * s]), {button: 'left', buttons: 1});
      await sleep(16);
    }
    await mouse('mouseReleased', toPage(name, to), {button: 'left', buttons: 0, clickCount: 1});
  }
  pointer = to;
}
const status = () => evaluate(`({${PANELS.map(name => `${name}: panel('${name}').status()`).join(', ')}})`);
const settled = async (quietMs, timeout) => {
  const start = Date.now();
  let last = null;
  let since = Date.now();
  while (Date.now() - start < timeout) {
    const s = await status();
    const key = JSON.stringify(PANELS.map(name => [s[name].isLoaded, s[name].events, s[name].tileZRange]));
    if (key !== last) {
      last = key;
      since = Date.now();
    } else if (PANELS.every(name => s[name].isLoaded) && Date.now() - since > quietMs) {
      return s;
    }
    await sleep(100);
  }
  return null;
};

try {
  let target = null;
  for (let i = 0; i < 100 && !target; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      target = list.find(t => t.type === 'page');
    } catch {
      // the browser is still starting
    }
    if (!target) await sleep(200);
  }
  if (!target) throw new Error('browser did not start');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  mkdirSync(args.out, {recursive: true});
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Page.screencastFrame') {
      const {data, metadata, sessionId} = message.params;
      send('Page.screencastFrameAck', {sessionId});
      if (recording) {
        const file = `${String(frames.length).padStart(5, '0')}.jpg`;
        writeFileSync(join(args.out, file), Buffer.from(data, 'base64'));
        frames.push({file, t: metadata.timestamp});
      }
      return;
    }
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  };

  await send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
  await send('Network.enable');
  await send('Network.setCacheDisabled', {cacheDisabled: true});
  await send('Page.enable');
  await send('Page.startScreencast', {format: 'jpeg', quality: 93, maxWidth: width, maxHeight: height, everyNthFrame: 1});
  recording = true;
  await send('Page.navigate', {url: `${origin}/index.html?recorder=1`});
  if (!(await waitFor(`document.readyState === 'complete' && ${PANELS.map(n => `panel('${n}')?.ready`).join(' && ')}`, 60000))) {
    throw new Error('panels did not load');
  }
  rects = await evaluate(`Object.fromEntries(${JSON.stringify(PANELS)}.map(name => {
    const frame = document.getElementById(name);
    const r = frame.getBoundingClientRect();
    return [name, {x: r.left + frame.clientLeft, y: r.top + frame.clientTop, width: frame.clientWidth, height: frame.clientHeight}];
  }))`);
  const deckStart = await evaluate(`Math.max(...${JSON.stringify(PANELS)}.map(n => panel(n).start + document.getElementById(n).contentWindow.performance.timeOrigin))`);

  await caption(1, 'Zoom in with the mouse wheel while the first tiles load');
  await move([0.5, 0.5], 300);
  // The zoom lands about half a second after the Deck was created
  const wait = deckStart + 500 - (await evaluate('performance.timeOrigin + performance.now()'));
  if (wait > 0) await sleep(wait);
  const atWheel = await status();
  console.log('at the wheel:', JSON.stringify(atWheel));
  for (let i = 0; i < 3; i++) {
    await wheel([0.5, 0.5], -100);
    await sleep(70);
  }
  for (const name of PANELS) await evaluate(`panel('${name}').log('mouse wheel ×3 → zoom ' + panel('${name}').status().zoom.toFixed(2) + ', tiles loaded ${atWheel[name].loaded} of ${atWheel[name].selected}')`);
  await caption(1, 'Zoom in with the mouse wheel while the first tiles load', 'then wait until every tile has loaded');
  const loaded = await settled(1500, 40000);
  console.log('settled:', JSON.stringify(loaded));
  if (!loaded) throw new Error('tiles did not settle');

  if (args.probe) {
    const {data} = await send('Page.captureScreenshot', {format: 'png'});
    writeFileSync(join(args.out, 'probe.png'), Buffer.from(data, 'base64'));
  } else {
    const clicks = args.clicks.split(';').filter(Boolean).map(c => c.split(',').map(Number));
    await caption(2, 'Click the mountain', 'deck.gl onClick picks at the pointer');
    for (const at of clicks) {
      await move(at, 550);
      await sleep(150);
      await click(at);
      await sleep(750);
    }
    await move([0.97, 0.12], 400);
    await caption(3, 'Pick a 40 × 26 grid with deck.pickObject', 'green: TerrainLayer picked · red: nothing');
    const grid = {cols: 40, rows: 26, top: 0.04, bottom: 0.98};
    await evaluate(`Promise.all(${JSON.stringify(PANELS)}.map(n => panel(n).pickGrid(${JSON.stringify(grid)}))).then(() => true)`);
    await sleep(800);
    const final = await evaluate(`Object.fromEntries(${JSON.stringify(PANELS)}.map(n => [n, {clicks: panel(n).clicks, grid: panel(n).grid, status: panel(n).status()}]))`);
    console.log('result:', JSON.stringify(final));
    const summary = name => {
      const {clicks: c, grid: g} = final[name];
      return `${c.filter(x => x.hit).length} of ${c.length} clicks, ${Math.round((100 * g.hits) / g.total)}% of the grid`;
    };
    await caption('', `Before: ${summary('master')} · After: ${summary('fix')}`);
    await sleep(3500);
    if (args.pan) {
      await caption(4, 'Any later layer update hides it: drag the map a little', 'TerrainLayer then renders its TileLayer with the range');
      await evaluate(`${JSON.stringify(PANELS)}.forEach(n => panel(n).clearGrid()), true`);
      await move([0.3, 0.5], 400);
      await drag([0.3, 0.5], [0.3, 0.53], 250);
      await settled(800, 20000);
      await move([0.97, 0.12], 300);
      await evaluate(`Promise.all(${JSON.stringify(PANELS)}.map(n => panel(n).pickGrid(${JSON.stringify(grid)}))).then(() => true)`);
      await sleep(3000);
    }
    writeFileSync(join(args.out, 'result.json'), JSON.stringify({atWheel, loaded, final}, null, 1));
  }
  recording = false;
  await send('Page.stopScreencast');
  writeFileSync(join(args.out, 'frames.json'), JSON.stringify({width, height, frames, captions}, null, 1));
  console.log(`${frames.length} frames in ${args.out}`);
} finally {
  try {
    if (socket) await Promise.race([send('Browser.close'), sleep(3000)]);
  } catch {
    // already closed
  }
  browser.kill();
  server.close();
  await sleep(1000);
  rmSync(profile, {recursive: true, force: true, maxRetries: 5, retryDelay: 500});
}
