// Record the live web UI at human pace through a CDP screencast (1280x627 CSS px at 1.5x = 1920x940).
// Usage: node record.js <out_dir>
// Writes <out>/frames/*.jpg, <out>/frames.txt (ffconcat with durations) and <out>/events.json
// (clicks, typing, page changes and captions in seconds from the first frame).
const { chromium } = require('/home/user/harness-hackathon/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const OUT = process.argv[2];
const BASE = 'https://persistentepiphany--pah-web.us-east.modal.run';
const PACE = { cursorMs: 850, typeMsPerChar: 90, afterClickMs: 800, readMsPerWord: 300, minHoldMs: 1500, settleMs: 1500 };
const PROMPT = 'Dock imatinib into ABL1 with Boltz-2 and Gnina, 5 seeds';

const CURSOR = `
(() => {
  if (window.__cur) return;
  const add = () => {
    const c = document.createElement('div');
    c.id = '__cur';
    c.innerHTML = '<svg width="22" height="30" viewBox="0 0 22 30"><path d="M2 2 L2 24 L8 18.5 L12 28 L16 26.3 L12 17 L20 17 Z" fill="#1A1A18" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, { position: 'fixed', left: '0px', top: '0px', zIndex: 2147483647, pointerEvents: 'none', transform: 'translate(640px, 400px)' });
    document.documentElement.appendChild(c);
    window.__cur = c;
    const last = JSON.parse(sessionStorage.getItem('__curpos') || '[640,400]');
    c.style.transform = 'translate(' + last[0] + 'px,' + last[1] + 'px)';
    window.addEventListener('mousemove', e => {
      c.style.transform = 'translate(' + (e.clientX - 2) + 'px,' + (e.clientY - 2) + 'px)';
      sessionStorage.setItem('__curpos', JSON.stringify([e.clientX - 2, e.clientY - 2]));
    }, true);
  };
  if (document.documentElement) add(); else document.addEventListener('DOMContentLoaded', add);
})();`;

(async () => {
  fs.mkdirSync(path.join(OUT, 'frames'), { recursive: true });
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 627 }, deviceScaleFactor: 1.5 });
  await ctx.addInitScript(CURSOR);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  let n = 0;
  let recording = false;
  cdp.on('Page.screencastFrame', async f => {
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
    if (!recording) return;
    const file = `f${String(n++).padStart(6, '0')}.jpg`;
    fs.writeFileSync(path.join(OUT, 'frames', file), Buffer.from(f.data, 'base64'));
    frames.push([f.metadata.timestamp, file]);
  });
  const ev = [];
  let t0 = null;
  const now = () => Date.now() / 1000;
  const mark = (k, v) => ev.push([now(), k, v ?? null]);
  const pause = ms => page.waitForTimeout(Math.max(0, ms));
  const hold = text => pause(Math.max(PACE.minHoldMs, text.trim().split(/\s+/).length * PACE.readMsPerWord));
  let cx = 640, cy = 400;
  const moveTo = async (x, y) => {
    const steps = 26;
    const x0 = cx, y0 = cy;
    const bend = 0.12 * Math.hypot(x - x0, y - y0);
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      const off = Math.sin(Math.PI * e) * bend;
      await page.mouse.move(x0 + (x - x0) * e + off * 0.3, y0 + (y - y0) * e - off * 0.2);
      await pause(PACE.cursorMs / steps);
    }
    cx = x; cy = y;
  };
  const clickEl = async (loc, after = PACE.afterClickMs) => {
    await loc.scrollIntoViewIfNeeded().catch(() => {});
    const b = await loc.boundingBox();
    if (!b) throw new Error('no box');
    await moveTo(b.x + Math.min(b.width / 2, 60), b.y + b.height / 2);
    mark('click');
    await page.mouse.down(); await page.mouse.up();
    await pause(after);
  };
  const smoothScroll = async (y) => {
    await page.evaluate(yy => window.scrollTo({ top: yy, behavior: 'smooth' }), y);
    await pause(1300);
  };
  const cap = text => mark('cap', text);

  try {
    // Second take: the Jobs list, then the finished all-tools run. Start run is never pressed.
    const RID = 'ligand_pose-249098d10007';
    await page.goto(BASE + '/jobs', { waitUntil: 'networkidle', timeout: 60000 });
    await page.mouse.move(cx, cy);
    await pause(1500);
    recording = true;
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1920, maxHeight: 941, everyNthFrame: 1 });
    await pause(300);
    t0 = now();
    mark('start');
    cap('Jobs lists every run with its six layer bars and verdict.');
    await pause(700);
    const card = page.locator(`a[href="/jobs/${RID}"]`).first();
    await card.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => {});
    await pause(1500);
    await clickEl(card, 300);
    mark('route');
    await page.getByText('Open report').first().waitFor({ timeout: 20000 }).catch(() => {});
    await pause(1200);
    cap('Its report opens on the verdict and the issues that limit the claim.');
    await clickEl(page.getByText('Open report').first(), 300);
    mark('route');
    await page.getByTestId('issues').waitFor({ timeout: 20000 }).catch(() => {});
    await page.waitForLoadState('networkidle').catch(() => {});
    await pause(3000);
    cap('Seven tools ran on Modal A100 and the CPU; 164 structures, each checked.');
    await page.getByTestId('execution').evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'start' })).catch(() => {});
    await pause(1800);
    await page.getByTestId('execution-row').nth(4).evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' })).catch(() => {});
    await pause(2400);
    await smoothScroll(0);
    cap('Ensemble shows every structure with its pLDDT, confidence and PoseBusters result.');
    await clickEl(page.getByTestId('open-ensemble'), 300);
    mark('route');
    await page.getByTestId('structure-grid').waitFor({ timeout: 20000 }).catch(() => {});
    await pause(2200);
    await smoothScroll(300);
    await pause(1600);
  } catch (e) {
    mark('error', String(e).slice(0, 300));
  }
  const tEnd = now();
  recording = false;
  await cdp.send('Page.stopScreencast').catch(() => {});
  // ffconcat with per-frame durations
  const lines = ['ffconcat version 1.0'];
  for (let i = 0; i < frames.length; i++) {
    const d = (i + 1 < frames.length ? frames[i + 1][0] : tEnd) - frames[i][0];
    lines.push(`file 'frames/${frames[i][1]}'`, `duration ${Math.max(d, 0.001).toFixed(4)}`);
  }
  if (frames.length) lines.push(`file 'frames/${frames[frames.length - 1][1]}'`);
  fs.writeFileSync(path.join(OUT, 'frames.txt'), lines.join('\n') + '\n');
  const first = frames.length ? frames[0][0] : t0;
  fs.writeFileSync(path.join(OUT, 'events.json'), JSON.stringify({
    first, tEnd, duration: tEnd - first, frames: frames.length,
    ev: ev.map(([t, k, v]) => [+(t - first).toFixed(3), k, v]),
  }, null, 1));
  console.log('frames', frames.length, 'duration', (tEnd - first).toFixed(1), 'errors', ev.filter(e => e[1] === 'error').map(e => e[2]));
  await browser.close();
})();
