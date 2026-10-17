// Demo video A: human-paced walkthrough of the Harness web UI in mock mode (seed 7).
// Run through work/record.sh, which fills the __PLACEHOLDERS__ and calls
// `playwright-cli run-code --filename <copy>`. Pacing follows .claude/skills/human-pace (PACE).
// Every event the soundtrack and subtitles need is recorded in page time (performance.now) and
// returned as JSON; build.py maps it onto the video timeline.
async page => {
  const BASE = '__BASE__';
  const OUT = '__OUT__';
  const ASSETS = '__ASSETS__';
  const WARM = __WARM__;
  const W = 1440;
  const H = 800;

  const PACE = {
    cursorMs: 850,        // cursor travel and click marker per action
    typeMsPerChar: 90,    // about 11 characters a second
    afterClickMs: 800,    // let the UI react before the next move
    readMsPerWord: 300,   // hold new text long enough to read
    minHoldMs: 1500,
    chapterMs: 2500,
    scrollMs: 1200,       // smooth scroll plus a beat to look
    settleMs: 1500,       // after a page change, before the first action
    endHoldMs: 2000,
  };

  const PROMPT = 'Is the imatinib pose in ABL1 valid? Boltz-2 and Gnina, 5 seeds';
  const MY_NAME = 'ABL1 kinase · ligand pose';
  const OTHER = 'KRAS · RAF1 discovery';
  const TITLE = 'Harness: does this prediction support the claim?';
  const END = 'Every number traceable to a check, a tool and a source.';
  const C = __CAPTIONS__;
  const ROW_SELECTOR = '[data-testid="check-table"] [data-testid="check-row"][data-check="minimisation.drift"]';

  const notes = [];
  const caps = [];
  const pause = ms => page.waitForTimeout(Math.max(0, ms));
  const words = s => s.trim().split(/\s+/).length;
  const holdMs = s => Math.max(PACE.minHoldMs, words(s) * PACE.readMsPerWord);
  const tnow = () => Date.now();
  const note = async (type, data) => notes.push([tnow(), type, data ?? null]);

  // Captions: each one stays up for at least its reading hold before the next one starts.
  const capWait = async (extra = 300) => {
    if (!caps.length) return;
    const [t, text] = caps[caps.length - 1];
    await pause(t + holdMs(text) + extra - tnow());
  };
  const cap = async text => {
    await capWait();
    caps.push([tnow(), text]);
  };

  const click = async (locator, after = PACE.afterClickMs) => {
    await locator.click();
    await pause(after);
  };
  // One smooth browser scroll; wheel ticks are paced like clicks and crawl.
  const scrollTo = async (locator, block = 'center') => {
    await locator.evaluate((el, b) => el.scrollIntoView({ behavior: 'smooth', block: b }), block);
    await pause(PACE.scrollMs);
  };
  const scrollTop = async () => {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
    await pause(PACE.scrollMs);
  };
  const park = async (x, y) => {
    await page.mouse.move(x, y, { steps: 5 });
  };
  const exists = async locator => (await locator.count()) > 0;
  // Mol* builds its scene through software WebGL here, which takes 5-25 s depending on machine
  // load. The wait is cut from the video in post (build.py); the viewer keeps 0.8 s of the
  // loading state on screen so the change reads as a load.
  const cuts = [];
  const waitReady = async (fn, timeout) => {
    const t0 = tnow();
    await page.waitForFunction(fn, null, { timeout, polling: 200 }).catch(() => {});
    const t1 = tnow();
    if (t1 - t0 > 1600) cuts.push([t0 + 800, t1 - 300]);
  };
  // On a page kept busy by Mol*, a Playwright click costs many slow round trips. Move the cursor
  // there (one input event), then click through the DOM (one evaluate).
  const domClick = async (sel, rect) => {
    if (rect) await page.mouse.move(rect.x + rect.w / 2, rect.y + rect.h / 2, { steps: 3 });
    await note('click', sel);
    await page.evaluate(q => document.querySelector(q)?.click(), sel);
  };

  // Outline an element for emphasis (overlay, pointer-events none). Returns a disposable.
  const outline = async (locator, pad = 6) => {
    const b = await locator.boundingBox();
    if (!b) return { dispose: async () => {} };
    return page.screencast.showOverlay(`<div style="position:absolute;left:${b.x - pad}px;top:${b.y - pad}px;width:${b.width + 2 * pad}px;height:${b.height + 2 * pad}px;border:2px solid rgba(176,126,44,.9);border-radius:8px;box-shadow:0 0 0 4px rgba(176,126,44,.12)"></div>`);
  };

  // Type into a React-controlled field from inside the page at a fixed rate per character.
  // (Playwright key events cost a screencast round trip each, which drags under CPU load.)
  const typeInPage = (sel, text, ms) =>
    page.evaluate(
      ([s, t, perChar]) =>
        new Promise(resolve => {
          const el = document.querySelector(s);
          const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          const set = Object.getOwnPropertyDescriptor(proto, 'value').set;
          el.focus();
          const t0 = performance.now();
          let shown = 0;
          const step = () => {
            const want = Math.min(t.length, Math.floor((performance.now() - t0) / perChar) + 1);
            if (want > shown) {
              shown = want;
              set.call(el, t.slice(0, shown));
              el.dispatchEvent(new Event('input', { bubbles: true }));
            }
            if (shown < t.length) setTimeout(step, 15);
            else resolve(true);
          };
          step();
        }),
      [sel, text, ms],
    );

  const sim = {
    pause: () => page.evaluate(() => window.__harnessMock.pause()),
    resume: speed => page.evaluate(s => { window.__harnessMock.setSimSpeed(s); window.__harnessMock.resume(); }, speed),
    speed: speed => page.evaluate(s => window.__harnessMock.setSimSpeed(s), speed),
    wait: (fn, arg, timeout = 90000) => page.waitForFunction(fn, arg, { timeout, polling: 100 }),
    job: id => page.evaluate(i => { const j = window.__harnessMock.simulator.jobs.find(x => x.id === i); return j ? { status: j.status, layerIdx: j.layerIdx, progress: j.progress } : null; }, id),
    remainingMs: id => page.evaluate(i => {
      const j = window.__harnessMock.simulator.jobs.find(x => x.id === i);
      if (!j || j.status === 'done') return 0;
      let ms = 0;
      j.record.layers.forEach((l, k) => { if (k > j.layerIdx) ms += l.durationMs || 0; if (k === j.layerIdx) ms += (l.durationMs || 0) * (1 - j.progress); });
      return ms;
    }, id),
  };

  // Mock records point the crystal reference at RCSB; serve the downloaded copy instead.
  await page.route(/https:\/\/files\.rcsb\.org\/download\/\w{4}\.cif/i, async route => {
    const id = route.request().url().match(/download\/(\w{4})\.cif/i)[1].toUpperCase();
    const headers = { 'access-control-allow-origin': '*' };
    try {
      await route.fulfill({ path: `${ASSETS}${id}.cif`, contentType: 'chemical/x-mmcif', headers });
    } catch {
      await route.fulfill({ status: 404, body: 'not in the local asset folder', headers });
    }
  });

  await page.setViewportSize({ width: W, height: H });
  if (WARM) {
    // fill the HTTP and shader caches of this fresh browser: Mol* on the ensemble grid and overlay
    await page.goto(`${BASE}/reports/latest/ensemble`, { waitUntil: 'load', timeout: 90000 }).catch(() => {});
    await page.waitForFunction(() => !!document.querySelector('[data-testid="cell-viewer"][data-state="molstar-ready"]'), null, { timeout: 60000, polling: 500 }).catch(() => {});
    await page.evaluate(() => document.querySelector('[data-testid="view-mode"] [data-value="overlay"]')?.click()).catch(() => {});
    await page.waitForFunction(() => !!document.querySelector('[data-testid="overlay-viewer"][data-state="molstar-ready"]'), null, { timeout: 60000, polling: 500 }).catch(() => {});
    for (const path of ['/agent', '/documents/latest', '/jobs']) {
      await page.goto(BASE + path, { waitUntil: 'load', timeout: 60000 }).catch(() => {});
      await pause(800);
    }
  }
  await page.goto(`${BASE}/runs/new?seed=7`, { waitUntil: 'load', timeout: 90000 });
  await page.waitForFunction(() => !!window.__harnessMock && !!document.querySelector('[data-testid="prompt-input"]'), null, { timeout: 90000 });
  await pause(1000);
  await sim.pause();
  await page.evaluate(() => window.__harnessMock.advance(6500));
  await page.addStyleTag({ content: 'nextjs-portal{display:none!important}' });

  // In-page recorder: clicks, route changes, simulator log lines, job status, agent steps.
  await page.evaluate(() => {
    const va = { ev: [], path: location.pathname, rec(type, data) { va.ev.push([performance.timeOrigin + performance.now(), type, data ?? null]); } };
    window.__va = va;
    document.addEventListener('pointerdown', e => va.rec('pointerdown', { x: Math.round(e.clientX), y: Math.round(e.clientY) }), true);
    setInterval(() => {
      if (location.pathname !== va.path) {
        va.path = location.pathname;
        va.rec('route', { path: va.path });
      }
    }, 40);
    const s = window.__harnessMock.simulator;
    const seen = new Map();
    const status = new Map();
    const steps = new Map();
    for (const j of s.jobs) { seen.set(j.id, j.log.length); status.set(j.id, j.status); }
    for (const t of s.agentTasks) steps.set(t.id, s.revealedSteps(t).length);
    s.subscribe(() => {
      for (const j of s.jobs) {
        const n = seen.has(j.id) ? seen.get(j.id) : 0;
        for (let k = n; k < j.log.length; k++) {
          const l = j.log[k];
          va.rec('log', { job: j.id, name: j.name, kind: l.kind, result: l.result ?? null, layer: l.layer });
        }
        seen.set(j.id, j.log.length);
        if (status.get(j.id) !== j.status) {
          status.set(j.id, j.status);
          va.rec('status', { job: j.id, name: j.name, status: j.status, verdict: j.status === 'done' ? j.record.verdict.outcome : null });
        }
      }
      for (const t of s.agentTasks) {
        const n = s.revealedSteps(t).length;
        const had = steps.has(t.id) ? steps.get(t.id) : 0;
        for (let k = had; k < n; k++) va.rec('agentstep', { task: t.id, seq: k + 1, kind: t.steps[k].kind });
        steps.set(t.id, n);
      }
    });
  });

  const card = (title, sub) => `
    <div style="position:absolute;inset:0;background:#f7f7f4;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;font-family:var(--font-sans, Inter, system-ui, sans-serif);color:#1a1a18">
      <div style="display:flex;align-items:center;gap:12px;font-size:19px;font-weight:600">
        <span style="position:relative;display:inline-block;width:20px;height:20px;border:2px solid #1a1a18;border-radius:4px"><span style="position:absolute;inset:4px;background:#b07e2c;border-radius:1.5px"></span></span>Harness
      </div>
      <div style="font-size:40px;font-weight:600;letter-spacing:-.01em;max-width:1100px;text-align:center;line-height:1.2">${title}</div>
      <div style="font-size:16px;color:#8b8b85;font-family:var(--font-mono, ui-monospace, monospace)">${sub}</div>
    </div>`;
  const titleCard = await page.screencast.showOverlay(card(TITLE, 'mock data · seed 7'));
  await pause(300);
  // ------------------------------------------------------------------ take
  await page.screencast.start({ path: OUT, size: { width: W, height: H }, fps: 30 });
  const pageT0 = tnow();
  let myId = null;
  let error = null;
  try {
  const actions = () => page.screencast.showActions({
    duration: PACE.cursorMs,
    style: {
      title: 'display: none',
      point: 'width: 18px; height: 18px; border-radius: 50%; background: rgba(176,126,44,.18); box-shadow: 0 0 0 2px rgba(176,126,44,.55)',
    },
  });

  // 1. Title card (shown before the take starts, so the video opens on it)
  await pause(PACE.chapterMs + 300);
  await note('title-off');
  await titleCard.dispose();
  await actions();
  await pause(400);

  // 2. New run: prompt, Quick setup decisions, sources
  const prompt = page.getByTestId('prompt-input');
  await cap(C.ask);
  await click(prompt, 400);
  await note('type-start');
  await typeInPage('[data-testid="prompt-input"]', PROMPT, PACE.typeMsPerChar);
  await note('type-end');
  await pause(300);
  await capWait(0);
  await click(page.getByTestId('quick-setup'), 300);
  await cap(C.setup);
  await park(1120, 700);
  await capWait(0);
  const sources = page.getByTestId('sources-panel');
  const o1 = await outline(sources, 10);
  await cap(C.sources);
  await page.waitForFunction(() => document.querySelectorAll('[data-testid="decision-row"]').length >= 9, null, { timeout: 20000 }).catch(() => {});
  await capWait(0);
  await o1.dispose();

  // 3. Start the run, step back to the Jobs list and watch the layer bars fill
  const startBtn = (await exists(page.getByTestId('decision-stream').getByTestId('start-run')))
    ? page.getByTestId('decision-stream').getByTestId('start-run')
    : page.getByTestId('start-run').first();
  await click(startBtn, 200);
  await page.waitForURL(/\/jobs\/[^/]+$/, { timeout: 60000 });
  myId = decodeURIComponent(page.url().split('/jobs/')[1].split(/[?#]/)[0]);
  await note('job', myId);
  await pause(700);
  const back = page.getByText('All jobs').first();
  await click(back, 300);
  await page.waitForURL(/\/jobs\/?$/, { timeout: 30000 });
  await sim.resume(1.5);
  await note('resume');
  await park(1300, 470);
  const myCard = page.getByTestId('job-card').filter({ hasText: MY_NAME }).first();
  const o2 = await outline(myCard.getByTestId('layer-progress'), 6).catch(() => ({ dispose: async () => {} }));
  await cap(C.layers);
  await capWait(100);
  await o2.dispose();
  await sim.pause();   // hold the run while the page changes, so a slow navigation costs nothing

  // 4. Open the job: elapsed ticks, layer strip, streamed log, Plain/Terminal once
  await click(myCard.getByText(MY_NAME).first(), 200);
  await page.waitForURL(/\/jobs\/[^/]+$/, { timeout: 30000 });
  {
    // keep the run going while the log is shown; it is sped up after the toggle
    const left = await sim.remainingMs(myId);
    await sim.resume(Math.min(1.2, Math.max(0.25, left / 10000)));
    await note('detail-speed', left);
  }
  await park(1360, 330);
  await cap(C.stream);
  await pause(1800);
  // frame the layer strip, the whole log panel and the side column (where the verdict appears)
  const strip = page.getByTestId('layer-strip').first();
  if (await exists(strip)) {
    await strip.evaluate(el => window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 64, behavior: 'smooth' }));
    await pause(PACE.scrollMs);
  }
  await capWait(0);
  await click(page.getByTestId('log-mode-terminal'), 200);
  await cap(C.terminal);
  await capWait(0);
  await sim.pause();   // the verdict should land after the switch back to Plain, however slow the click
  await click(page.getByTestId('log-mode-plain'), 200);
  await park(1360, 330);
  {
    const left = await sim.remainingMs(myId);
    if (left > 0) await sim.resume(Math.min(6, Math.max(0.3, left / 1200)));
  }
  await sim.wait(i => { const j = window.__harnessMock.simulator.jobs.find(x => x.id === i); return j && j.status === 'done'; }, myId, 60000);
  await note('verdict');
  await pause(500);
  await sim.pause();
  const sideVerdict = page.getByTestId('page-job').getByTestId('verdict').first();
  const o7 = (await exists(sideVerdict)) ? await outline(sideVerdict, 8) : { dispose: async () => {} };
  await cap(C.verdict);
  await capWait(200);
  await o7.dispose();

  // 5. Report: verdict scoped to the claim, one check row (measured vs threshold), PoseBusters
  await click(page.getByTestId('top-nav').getByRole('link', { name: /^Reports/ }), 200);
  await page.waitForURL(/\/reports\/run_/, { timeout: 30000 });
  // agent_01 goes back to its first step now; the simulator stays paused until the agent scene
  await page.evaluate(() => {
    const s = window.__harnessMock.simulator;
    for (const t of s.agentTasks) {
      if (t.id === 'agent_01') { t.status = 'running'; t.elapsedMs = 0; t.startedAt = s.now(); t.version++; }
      else if (t.status !== 'done') { t.elapsedMs = t.total; t.status = 'done'; t.version++; }
    }
  });
  await note('agent-rewind');
  await park(1390, 300);
  await page.getByTestId('verdict').first().waitFor({ timeout: 15000 }).catch(() => {});
  await pause(500);
  await cap(C.report);
  await capWait(100);
  const row = page.locator(ROW_SELECTOR).first();
  if (await exists(row)) {
    await scrollTo(row, 'center');
    const o5 = await outline(row, 4);
    await cap(C.row);
    await capWait(100);
    await o5.dispose();
  }
  const pb = page.getByTestId('posebusters').first();
  if (await exists(pb)) {
    await scrollTo(pb, 'center');
    await cap(C.pb);
    await capWait(100);
  }

  // 6. Ensemble: structure grid with confidence values, then overlay mode.
  // Mol* renders through SwiftShader here and keeps the page busy, so this scene uses few
  // Playwright round trips: one evaluate for scroll and state, DOM clicks, no cursor moves in
  // overlay mode.
  await page.getByTestId('top-nav').getByRole('link', { name: /^Ensemble/ }).click();
  await page.waitForURL(/\/ensemble/, { timeout: 30000 });
  await pause(700);
  const ens = await page.evaluate(() => {
    const c = document.querySelector('[data-testid="ensemble-controls"]');
    if (!c) return null;
    window.scrollTo({ top: c.getBoundingClientRect().top + window.scrollY - 64, behavior: 'smooth' });
    const b = sel => { const e = document.querySelector(sel); return !!e && !e.disabled; };
    return {
      overlay: b('[data-testid="view-mode"] [data-value="overlay"]'),
      confidence: b('[data-testid="color-mode"] [data-value="confidence"]'),
      flagged: b('[data-testid="color-mode"] [data-value="flagged"]'),
    };
  });
  await note('ensemble-controls', ens);
  if (ens) {
    await pause(PACE.scrollMs);
    // the crystal reference is the one structure with coordinates in mock data
    await waitReady(() => !!document.querySelector('[data-testid="cell-viewer"][data-state="molstar-ready"]'), 60000);
    await note('grid-ready');
    await pause(300);
    const rects = await page.evaluate(() => {
      const r = sel => { const e = document.querySelector(sel); if (!e) return null; const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
      return {
        overlay: r('[data-testid="view-mode"] [data-value="overlay"]'),
        confidence: r('[data-testid="color-mode"] [data-value="confidence"]'),
        flagged: r('[data-testid="color-mode"] [data-value="flagged"]'),
      };
    });
    await cap(C.ensemble);
    await capWait(100);
    const colour = ens.confidence ? 'confidence' : ens.flagged ? 'flagged' : null;
    if (colour) {
      await domClick(`[data-testid="color-mode"] [data-value="${colour}"]`, rects[colour]);
      await pause(900);
      await cap(colour === 'confidence' ? C.colour : C.flagged);
      await capWait(100);
    }
    if (ens.overlay) {
      await domClick('[data-testid="view-mode"] [data-value="overlay"]', rects.overlay);
      await waitReady(() => !!document.querySelector('[data-testid="overlay-viewer"][data-state="molstar-ready"]'), 60000);
      await note('overlay-ready');
      await pause(300);
      await cap(C.overlay);
      await capWait(100);
    }
  } else {
    await cap(C.ensemble);
    await capWait(100);
  }

  // 7. Agent monitor: agent_01 streams from its first step. The script advances the simulator one
  // step at a time, so the pace does not depend on how fast the browser ticks under load.
  await note('click', 'nav agent');
  await page.evaluate(() => document.querySelector('[data-testid="top-nav"] a[href="/agent"]')?.click());
  await page.waitForURL(/\/agent/, { timeout: 30000 });
  await park(1390, 330);
  const stepMs = await page.evaluate(() => window.__harnessMock.simulator.agentTasks.find(t => t.id === 'agent_01').steps.map(x => x.ms));
  await note('agent-steps', stepMs.length);
  await cap(C.agent);
  for (let k = 0; k < stepMs.length; k++) {
    await page.evaluate(ms => window.__harnessMock.advance(ms), stepMs[k] + 10);
    if (k === 7) await cap(C.agentThought);
    if (k === stepMs.length - 1) await cap(C.conclusion);
    await pause(k < 7 ? 800 : 550);
  }
  await capWait(200);

  // 8. Documents: the printable report (the nav is sticky, so no scroll back first)
  await page.getByTestId('top-nav').getByRole('link', { name: /^Documents/ }).click();
  await page.waitForURL(/\/documents\/run_/, { timeout: 30000 });
  await park(1390, 300);
  await pause(900);
  await cap(C.docs);
  await capWait(-800);
  await page.evaluate(() => window.scrollBy({ top: 420, behavior: 'smooth' }));
  await pause(PACE.scrollMs + 600);
  await capWait(300);

  // 9. End card
  await page.screencast.hideActions().catch(() => {});
  await note('end-on');
  await page.screencast.showOverlay(card(END, 'mock data · every value in this recording comes from the simulator'));
  await pause(PACE.chapterMs + PACE.endHoldMs);
  await note('stop');
  } catch (e) {
    error = String(e).slice(0, 2000);
    await note('error', error).catch(() => {});
  }
  const ev = await page.evaluate(() => window.__va ? window.__va.ev : null).catch(() => null);
  await page.screencast.stop().catch(() => {});
  return JSON.stringify({ pageT0, myId, caps, notes, ev, error, cuts, viewport: [W, H] });
}
