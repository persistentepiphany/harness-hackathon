// Record the live web UI at human pace through a CDP screencast (1280x627 CSS px at 1.5x = 1920x940).
// Usage: node record3.js <out_dir> <input|report|ensemble|evidence|document|agent>
// Start run is never pressed in any take.
// Writes <out>/frames/*.jpg, <out>/frames.txt (ffconcat with durations) and <out>/events.json
// (clicks, typing, page changes and captions in seconds from the first frame).
const { chromium } = require('/home/user/harness-hackathon/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const OUT = process.argv[2];
const MODE = process.argv[3];
const BASE = 'https://persistentepiphany--pah-web.us-east.modal.run';
const PACE = { cursorMs: 850, typeMsPerChar: 90, afterClickMs: 800, readMsPerWord: 300, minHoldMs: 1500, settleMs: 1500 };

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
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
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


  // eased scroll of an element (or the window) over ms, driven by requestAnimationFrame
  const easeScroll = async (sel, to, ms) => {
    await page.evaluate(([s, y, d]) => new Promise(res => {
      const el = s ? document.querySelector(s) : document.scrollingElement;
      const y0 = el.scrollTop, t0 = performance.now();
      const step = now => {
        const k = Math.min(1, (now - t0) / d), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        el.scrollTop = y0 + (y - y0) * e;
        if (k < 1) requestAnimationFrame(step); else res();
      };
      requestAnimationFrame(step);
    }), [sel, to, ms]);
  };
  const begin = async () => {
    await page.mouse.move(cx, cy);
    await pause(1200);
    recording = true;
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1920, maxHeight: 941, everyNthFrame: 1 });
    await pause(300);
    t0 = now();
    mark('start');
  };
  const RID = 'ligand_pose-249098d10007';
  try {
    if (MODE === 'input') {
      await page.goto(BASE + '/runs/new', { waitUntil: 'networkidle', timeout: 60000 });
      await begin();
      cap('New run: pick from the menus.');
      await pause(1000);
      const item = name => page.getByTestId('menu-item').filter({ hasText: name }).first();
      await clickEl(page.getByTestId('menu-target'), 700);
      await clickEl(item('Trypsin'), 700);
      cap('Each pick is looked up live.');
      await clickEl(page.getByTestId('menu-ligand'), 700);
      await clickEl(item('benzamidine'), 1500);
      cap('Four tools, five seeds.');
      await clickEl(page.getByTestId('menu-tools'), 700);
      const want = { 'Boltz-2': true, 'Boltz-1': false, 'Protenix': false, 'Chai-1': true, 'ColabFold': false,
        'AutoDock Vina': true, 'Gnina': false, 'DiffDock-L': true };
      for (const name of ['Protenix', 'Chai-1', 'AutoDock Vina', 'DiffDock-L', 'Boltz-2', 'Boltz-1', 'Gnina', 'ColabFold']) {
        const it = item(name);
        if (!(await it.count())) continue;
        const sel = (await it.getAttribute('aria-selected')) === 'true';
        if (sel !== want[name]) await clickEl(it, 650);
      }
      await pause(400);
      await page.keyboard.press('Escape');
      const five = page.getByTestId('seed-choice').getByText('5', { exact: true });
      if ((await five.getAttribute('aria-pressed').catch(() => null)) === 'false') await clickEl(five, 700);
      await pause(500);
      cap('Start run is not pressed here.');
      const rl = await page.getByTestId('run-line').boundingBox();
      if (rl) await moveTo(rl.x + rl.width * 0.45, rl.y + rl.height + 48);
      mark('runline', await page.getByTestId('run-line').innerText().catch(() => ''));
      await pause(3400);
    } else if (MODE === 'evidence') {
      await page.goto(BASE + '/reports/' + RID, { waitUntil: 'networkidle', timeout: 60000 });
      await pause(3000);
      await page.evaluate(() => window.scrollTo(0, 0));
      const col = '[data-testid=report-stage-column]';
      const off = async tid => page.evaluate(([c, t]) => {
        const C = document.querySelector(c), E = C.querySelector(`[data-testid=${t}]`);
        return E.getBoundingClientRect().top - C.getBoundingClientRect().top + C.scrollTop - 12;
      }, [col, tid]);
      await page.evaluate(() => window.scrollTo(0, document.scrollingElement.scrollHeight));
      await page.evaluate(([c, y]) => { document.querySelector(c).scrollTop = y; }, [col, await off('check-table')]);
      await begin();
      cap('Every verdict carries its evidence.');
      await pause(400);
      const row = page.getByTestId('check-row').nth(1);
      await clickEl(row, 300);
      await moveTo(560, 590);
      await easeScroll(col, await off('outputs') - 60, 1700);
      await pause(1300);
      await easeScroll(col, await off('thresholds'), 1300);
      await pause(1100);
      await easeScroll(col, await off('thresholds') + 330, 1100);
      await pause(1500);
    } else if (MODE === 'report') {
      await page.goto(BASE + '/reports/' + RID, { waitUntil: 'networkidle', timeout: 60000 });
      await pause(3500);
      cx = 700; cy = 330;
      await begin();
      cap('Finished run: seven tools, 164 structures.');
      await pause(2600);
      cap('Verdict and issues, each with its value.');
      const iss = page.getByTestId('issue').first();
      const bi = await iss.boundingBox();
      if (bi) await moveTo(bi.x + 420, bi.y + bi.height / 2);
      await pause(2600);
      cap('The Boltz-2 medoid, rendered with PyMOL.');
      const pk = page.getByRole('button', { name: 'pocket' }).first();
      if (await pk.count()) await clickEl(pk, 1800); else await pause(1800);
      const ov = page.getByRole('button', { name: 'overview' }).first();
      if (await ov.count()) await clickEl(ov, 1200);
      cap('GPU time per seed on Modal A100.');
      const col = '[data-testid=report-stage-column]';
      await easeScroll(null, 400, 900);
      const ex = await page.evaluate(c => {
        const C = document.querySelector(c), E = C.querySelector('[data-testid=execution]');
        return E.getBoundingClientRect().top - C.getBoundingClientRect().top + C.scrollTop - 8;
      }, col);
      await easeScroll(col, ex, 1400);
      await moveTo(1000, 560);
      await pause(3200);
      await easeScroll(col, ex + 230, 1200);
      await pause(2400);
    } else if (MODE === 'ensemble') {
      await page.goto(BASE + '/reports/' + RID + '/ensemble', { waitUntil: 'networkidle', timeout: 60000 });
      await pause(4000);
      cx = 640; cy = 300;
      await begin();
      cap('Ensemble: 164 structures, each with its values.');
      await pause(2600);
      await easeScroll(null, 520, 2200);
      await pause(1800);
      await easeScroll(null, 1500, 2600);
      await pause(1800);
      // the film uses the take up to 12.9 s (build.py shot end); the flagged-colour step was cut
    } else if (MODE === 'document') {
      await page.goto(BASE + '/documents/' + RID, { waitUntil: 'networkidle', timeout: 60000 });
      await pause(3500);
      cx = 900; cy = 300;
      await begin();
      cap('The document: one printable report per run.');
      await pause(2800);
      cap('Downloads: run record, report and provenance graph.');
      for (const t of ['doc-download-record', 'doc-file-markdown', 'doc-file-graph']) {
        const l = page.getByTestId(t);
        const bb = await l.boundingBox().catch(() => null);
        if (bb) { await moveTo(bb.x + Math.min(bb.width / 2, 80), bb.y + bb.height / 2); await pause(700); }
      }
      await pause(900);
      await moveTo(760, 520);
      cap('Key numbers, then the structure.');
      await easeScroll(null, 300, 1800);
      await pause(2600);
      cap('Figures: seed spread, check outcomes, PoseBusters.');
      await easeScroll(null, 1100, 2400);
      await pause(2600);
      await easeScroll(null, 1640, 1800);
      await pause(2600);
      cap('Error map, provenance graph, interactions.');
      await easeScroll(null, 1960, 1600);
      await pause(2600);
      await easeScroll(null, 2280, 1400);
      await pause(2400);
    } else if (MODE === 'agent') {
      await page.goto(BASE + '/agent', { waitUntil: 'networkidle', timeout: 60000 });
      await pause(1500);
      cx = 900; cy = 520;
      await begin();
      cap('Agents call the same API.');
      await pause(600);
      const steps = page.locator('text=POST /ui/runs').first();
      const b = await steps.boundingBox().catch(() => null);
      if (b) await moveTo(b.x + 120, b.y + b.height / 2);
      await pause(1200);
      const r = page.locator('text=run finished').first();
      const b2 = await r.boundingBox().catch(() => null);
      if (b2) await moveTo(b2.x + 90, b2.y + b2.height / 2);
      await pause(1600);
    }
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
