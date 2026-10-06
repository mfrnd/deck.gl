// Captures frames of a comparison page while stepping its zoom, through the DevTools protocol of a Chromium browser
// (Edge or Chrome) that this script starts headless and closes again. frames_to_gif.py turns them into a GIF.
// Each frame waits until every live view has drawn the zoom and stopped posting messages (tiles loaded, terrain
// measured) and the recorded frames have loaded.
// Usage: node capture_frames.mjs --browser <path> --url <compare.html?scene=...> --out <dir>
//   [--zooms <from>:<to>:<step>] [--extra 11.99,12,12.01] [--size 1360x1500] [--settle 400] [--timeout 30000]
import {spawn} from 'node:child_process';
import {mkdirSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const args = {zooms: null, extra: '11.99,12,12.01', size: '1360x1500', settle: '400', timeout: '30000'};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
for (const name of ['browser', 'url', 'out']) {
  if (!args[name]) throw new Error(`--${name} is required`);
}
const [width, height] = args.size.split('x').map(Number);
const settle = Number(args.settle);
const timeout = Number(args.timeout);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

const port = 9300 + Math.floor(Math.random() * 600);
const profile = join(tmpdir(), `capture-frames-${port}`);
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
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  };

  await send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
  await send('Page.enable');
  await send('Page.navigate', {url: args.url});
  if (!(await waitFor(`document.readyState === 'complete' && document.querySelectorAll('.side-readout').length > 0 &&
      [...document.querySelectorAll('.side-readout')].every(e => e.textContent)`, 120000))) {
    throw new Error('page did not load');
  }
  const title = await evaluate("document.getElementById('title').textContent");
  console.log(title);
  // Only the title, the views and the controls; remember when each view last posted a message
  await evaluate(`(() => {
    const style = document.createElement('style');
    style.textContent = 'header > a, #description, .note { display: none !important; }';
    document.head.append(style);
    window.__last = {};
    window.addEventListener('message', event => {
      const data = event.data || {};
      if (data.build) window.__last[data.build] = {...(window.__last[data.build] || {}), [data.type]: data.zoom, at: performance.now()};
    });
    return true;
  })()`);

  const [from, to, step] = (args.zooms || '').split(':').map(Number);
  const steps = Math.round((to - from) / step);
  const zooms = [...new Set([
    ...Array.from({length: steps + 1}, (_, i) => Math.round((from + i * step) * 100) / 100),
    ...args.extra.split(',').filter(Boolean).map(Number)
  ])].filter(zoom => zoom >= from && zoom <= to).sort((a, b) => a - b);

  mkdirSync(args.out, {recursive: true});
  const frames = [];
  for (const [index, zoom] of zooms.entries()) {
    await evaluate(`(() => {
      const slider = document.getElementById('zoom');
      slider.value = ${zoom};
      slider.dispatchEvent(new Event('input', {bubbles: true}));
      return true;
    })()`);
    const ready = await waitFor(`(() => {
      const builds = [...document.querySelectorAll('#panels iframe')].map(f => new URL(f.src).searchParams.get('build'));
      const measuring = document.getElementById('measure').checked;
      const views = builds.every(build => {
        const last = window.__last[build] || {};
        return last.readout === ${zoom} && (!measuring || last.surface === ${zoom}) && performance.now() - last.at > ${settle};
      });
      const images = [...document.querySelectorAll('.stage img')].every(image =>
        image.getAttribute('src').endsWith('/${Math.round(zoom * 100)}.webp') && image.complete && image.naturalWidth > 0);
      return views && images;
    })()`, timeout);
    if (!ready) console.warn(`zoom ${zoom}: not settled after ${timeout} ms`);
    // Let the side views draw
    await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))');
    const clip = await evaluate(`(() => {
      const top = document.querySelector('header h1').getBoundingClientRect().top - 8;
      const panels = document.getElementById('panels').getBoundingClientRect();
      const controls = document.querySelector('.controls').getBoundingClientRect();
      const right = Math.max(panels.right, controls.right) + 8;
      return {x: Math.max(0, panels.left - 8), y: Math.max(0, top), width: right - Math.max(0, panels.left - 8),
        height: controls.bottom + 8 - Math.max(0, top), scale: 1};
    })()`);
    const {data} = await send('Page.captureScreenshot', {format: 'png', clip});
    const file = `${String(index).padStart(3, '0')}.png`;
    writeFileSync(join(args.out, file), Buffer.from(data, 'base64'));
    frames.push({file, zoom, settled: ready});
    process.stdout.write(`\r${index + 1}/${zooms.length} zoom ${zoom.toFixed(2)}   `);
  }
  writeFileSync(join(args.out, 'frames.json'), JSON.stringify({url: args.url, title, frames}, null, 1));
  console.log(`\n${frames.length} frames in ${args.out}`);
} finally {
  try {
    if (socket) await Promise.race([send('Browser.close'), sleep(3000)]);
  } catch {
    // already closed
  }
  browser.kill();
  await sleep(1000);
  rmSync(profile, {recursive: true, force: true, maxRetries: 5, retryDelay: 500});
}
