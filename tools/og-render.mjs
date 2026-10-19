// Рендерит HTML-карточки превью ссылок в JPG 1200×630 через локальный Chrome.
// node tools/og-render.mjs <список.json>   (список: [{url, out}])
import { spawn } from 'node:child_process'; import { readFileSync, writeFileSync } from 'node:fs';
const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const chrome = spawn(CHROME, ['--no-sandbox', '--headless=new', '--remote-debugging-port=9341', '--user-data-dir=/tmp/og-' + Date.now(), '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
const sleep = t => new Promise(r => setTimeout(r, t));
let list;
for (let i = 0; i < 40 && !list; i++) { await sleep(500); try { list = await (await fetch('http://127.0.0.1:9341/json')).json(); } catch (e) {} }
const ws = new WebSocket(list.find(t => t.type === 'page').webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pend = {}; ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend[m.id]) { pend[m.id](m.result); delete pend[m.id]; } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
for (const j of jobs) {
  await send('Page.navigate', { url: j.url }); await sleep(900);
  await send('Runtime.evaluate', { expression: 'document.fonts.ready.then(()=>Promise.all([...document.images].map(i=>i.complete?1:new Promise(r=>{i.onload=i.onerror=r}))))', awaitPromise: true });
  const s = await send('Page.captureScreenshot', { format: 'jpeg', quality: 84 });
  writeFileSync(j.out, Buffer.from(s.data, 'base64'));
}
console.log('карточек:', jobs.length); ws.close(); chrome.kill();
