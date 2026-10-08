// SPDX-License-Identifier: GPL-3.0-only
// Independent installed-browser receiving of actual external QC review files.
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const args = new Map();
for (let index = 2; index < process.argv.length; index += 2) {
  assert.ok(process.argv[index].startsWith('--') && process.argv[index + 1]);
  args.set(process.argv[index].slice(2), process.argv[index + 1]);
}
for (const name of ['browser', 'review', 'expectations', 'output', 'profile'])
  assert.ok(args.has(name), 'Missing explicit owned path: ' + name);
const executable = resolve(args.get('browser'));
const review = resolve(args.get('review'));
const output = resolve(args.get('output'));
const profile = resolve(args.get('profile'));
const expected = JSON.parse(await readFile(args.get('expectations'), 'utf8'));
const indexUrl = pathToFileURL(join(review, 'index.html')).href;
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const report = {
  schema: 'capture.qc-review.index-browser/1', status: 'running',
  node: process.version, executable, indexUrl, checks: [], artifacts: [],
  pageRequests: [], externalPageRequests: [], pageErrors: [], viewports: [],
  visualBoundary: 'Actual file-open, DOM and PNG output. Direct pixel inspection is separate.',
};
let child, socket, sessionId, serial = 0, browserStderr = '', failed, ownedProfile = false;
const pending = new Map();
async function waitFor(test, label, timeout = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const result = await test();
    if (result) return result;
    await new Promise(resolve_ => setTimeout(resolve_, 50));
  }
  throw new Error('Timed out waiting for ' + label);
}
function command(method, params = {}, useSession = true) {
  return new Promise((resolve_, reject) => {
    const id = ++serial;
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error('CDP timeout: ' + method));
    }, 20000);
    pending.set(id, { resolve: resolve_, reject, timer });
    socket.send(JSON.stringify({
      id, method, params, ...(useSession && sessionId ? { sessionId } : {}),
    }));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', {
    expression, returnByValue: true, awaitPromise: true,
  });
  if (result.exceptionDetails)
    throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
  return result.result.value;
}
const inPage = (fn, ...values) => evaluate('(' + fn.toString() + ')(...' + JSON.stringify(values) + ')');
async function open(url, width, height) {
  await command('Page.bringToFront');
  await command('Emulation.setDeviceMetricsOverride', {
    width, height, deviceScaleFactor: 1, mobile: false,
  });
  await command('Page.navigate', { url });
  await waitFor(() => inPage(
    expectedUrl => location.href === expectedUrl && document.readyState === 'complete',
    url,
  ), 'actual file document: ' + url);
  await evaluate('document.fonts.ready.then(() => true)');
  report.viewports.push({ url, width, height });
}
async function screenshot(name, ordinal = null) {
  await command('Page.bringToFront');
  await inPage(value => {
    if (value === null) window.scrollTo(0, 0);
    else {
      const node = document.querySelector('[data-qc-review-ordinal="' + value + '"]');
      if (!node) throw new Error('Missing visible package block ' + value);
      node.scrollIntoView({ block: 'start' });
    }
  }, ordinal);
  await evaluate(
    'new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))',
  );
  const { data } = await command('Page.captureScreenshot', {
    format: 'png', captureBeyondViewport: false,
  });
  const bytes = Buffer.from(data, 'base64');
  assert.ok(bytes.length <= 2 * 1024 * 1024, 'Bounded actual viewport image');
  await writeFile(join(output, name), bytes, { flag: 'wx' });
  report.artifacts.push({ path: name, bytes: bytes.length, sha256: hash(bytes) });
}
async function receiveIndex(width, height) {
  await open(indexUrl, width, height);
  const actual = await inPage(() => {
    const normalize = value => value.replace(/\s+/g, ' ').trim();
    return {
      url: location.href,
      overflow: document.documentElement.scrollWidth > innerWidth + 1,
      forbidden: document.querySelectorAll('script,img,iframe,object,embed').length,
      events: [...document.querySelectorAll('*')].flatMap(node =>
        [...node.attributes].filter(attr => /^on/i.test(attr.name)).map(attr => attr.name)),
      links: [...document.querySelectorAll('a[href]')].map(node => node.getAttribute('href'))
        .filter(href => !href.startsWith('#')),
      rows: [...document.querySelectorAll('[data-qc-review-ordinal]')].map(node => ({
        ordinal: Number(node.dataset.qcReviewOrdinal),
        raw: node.textContent, visibleText: normalize(node.innerText),
        visible: node.getClientRects().length > 0,
        box: node.getBoundingClientRect().toJSON(),
      })),
    };
  });
  assert.equal(actual.url, indexUrl);
  assert.equal(actual.overflow, false, 'New review index has no document horizontal overflow');
  assert.equal(actual.forbidden, 0, 'Authored markup stays literal');
  assert.deepEqual(actual.events, []);
  assert.deepEqual([...new Set(actual.links)].sort(), [...new Set(expected.links)].sort());
  assert.deepEqual(actual.rows.map(row => row.ordinal), expected.rows.map(row => row.ordinal));
  const normalize = value => value.replace(/\s+/g, ' ').trim();
  for (let index = 0; index < expected.rows.length; index++) {
    const want = expected.rows[index], got = actual.rows[index];
    assert.ok(got.visible, 'No hidden substitute for package ordinal ' + want.ordinal);
    assert.ok(got.box.x >= 0 && got.box.right <= width + 1, 'Package block fits viewport');
    const wantedText = [want.inputPath, want.packagePath, ...want.warnings];
    if (want.sessionId) wantedText.push(want.sessionId);
    if (want.error) wantedText.push(want.error.message);
    for (const value of wantedText) {
      assert.ok(got.raw.includes(value), 'Exact DOM text for ordinal ' + want.ordinal + ': ' + value);
      assert.ok(got.visibleText.includes(normalize(value)), 'Visible identity/warning/error text');
    }
    assert.ok(got.visibleText.toLowerCase().includes(want.status), 'Collection disposition visible');
    for (const [source, light] of Object.entries(want.lights)) {
      assert.ok(got.visibleText.includes(source), 'Native light source stays visible');
      assert.ok(got.visibleText.toLowerCase().includes(light), 'Native light stays visible');
    }
  }
  report.checks.push('actual index at ' + width + 'x' + height + ': ordered literal rows and links');
  report.indexReceipts ??= [];
  report.indexReceipts.push(actual);
}
try {
  assert.equal(typeof WebSocket, 'function', 'Use the installed Node native WebSocket');
  await mkdir(profile, { recursive: false });
  ownedProfile = true;
  child = spawn(executable, [
    '--headless=new', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
    '--user-data-dir=' + profile, '--no-first-run', '--no-default-browser-check',
    '--disable-background-networking', '--disable-sync', '--disable-extensions',
    '--disable-component-update', '--password-store=basic', 'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  child.stderr.on('data', data => { browserStderr += data.toString(); });
  child.stdout.on('data', () => {});
  child.on('error', error => { failed = error; });
  const endpoint = await waitFor(async () => {
    if (failed) throw failed;
    if (child.exitCode !== null) throw new Error('Installed browser exited: ' + child.exitCode);
    try {
      const parts = (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).trim().split(/\r?\n/);
      if (/^\d+$/.test(parts[0]) && parts[1]?.startsWith('/devtools/browser/'))
        return 'ws://127.0.0.1:' + parts[0] + parts[1];
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    return null;
  }, 'the owned installed-browser DevTools endpoint');
  socket = new WebSocket(endpoint);
  await new Promise((resolve_, reject) => {
    socket.addEventListener('open', resolve_, { once: true });
    socket.addEventListener('error', reject, { once: true });
  });
  socket.addEventListener('message', event => {
    const message = JSON.parse(String(event.data));
    if (message.id) {
      const item = pending.get(message.id);
      if (!item) return;
      pending.delete(message.id); clearTimeout(item.timer);
      if (message.error) item.reject(new Error(JSON.stringify(message.error)));
      else item.resolve(message.result);
      return;
    }
    if (message.method === 'Runtime.exceptionThrown') report.pageErrors.push(message.params);
    if (message.method === 'Network.requestWillBeSent') {
      const item = { url: message.params.request.url, method: message.params.request.method };
      report.pageRequests.push(item);
      if (/^https?:/i.test(item.url)) report.externalPageRequests.push(item);
    }
    if (message.method === 'Fetch.requestPaused')
      command('Fetch.failRequest', { requestId: message.params.requestId, errorReason: 'BlockedByClient' })
        .catch(error => report.pageErrors.push({ receiving: String(error) }));
  });
  report.browser = await command('Browser.getVersion', {}, false);
  const { targetId } = await command('Target.createTarget', { url: 'about:blank' }, false);
  ({ sessionId } = await command('Target.attachToTarget', { targetId, flatten: true }, false));
  await command('Page.enable'); await command('Runtime.enable'); await command('Network.enable');
  await command('Fetch.enable', { patterns: [{ urlPattern: 'http*' }] });
  await receiveIndex(1280, 1000);
  await screenshot('index-desktop.png');
  await receiveIndex(390, 844);
  await screenshot('index-phone.png');
  await screenshot('index-phone-failure.png', expected.rows.find(row => row.status === 'failed').ordinal);
  const nativeUrl = new URL(expected.nativeReport.path, indexUrl).href;
  await open(nativeUrl, 1280, 1000);
  const native = await inPage(() => ({
    url: location.href, text: document.body.textContent,
    forbidden: document.querySelectorAll('script,img,iframe,object,embed').length,
  }));
  assert.equal(native.url, nativeUrl);
  assert.equal(native.forbidden, 0);
  for (const value of expected.nativeReport.text)
    assert.ok(native.text.includes(value), 'Native file report text: ' + value);
  report.nativeReport = native;
  report.checks.push('actual native QC report file opens with exact literal identity and gap evidence');
  await screenshot('native-report-desktop.png');
  assert.deepEqual(report.pageErrors, []);
  assert.deepEqual(report.externalPageRequests, []);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed';
  report.error = error.stack ?? String(error);
  report.browserStderr = browserStderr;
  process.exitCode = 1;
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    await command('Browser.close', {}, false).catch(() => {});
    socket.close();
  }
  for (const item of pending.values()) clearTimeout(item.timer);
  pending.clear();
  if (child?.pid && child.exitCode === null) {
    if (process.platform === 'win32')
      spawnSync('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true });
    else child.kill('SIGTERM');
  }
  if (ownedProfile) {
    try {
      await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
      report.profileCleanup = 'Owned profile removed';
    } catch (error) {
      report.profileCleanup = String(error);
    }
  } else report.profileCleanup = 'No profile created; existing paths untouched';
  const raw = Buffer.from(JSON.stringify(report, null, 2) + '\n', 'utf8');
  await writeFile(join(output, 'browser-report.json'), raw, { flag: 'wx' });
  console.log('CAPTURE_QC_INDEX_BROWSER_RESULT ' + JSON.stringify({
    status: report.status, browser: report.browser, checks: report.checks.length,
    images: report.artifacts.length, reportBytes: raw.length, reportSha256: hash(raw),
  }));
}
