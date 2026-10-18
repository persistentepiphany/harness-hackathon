// Capture the scene pages as 1920x1080 PNG stills. Usage: node shoot.js <work_dir> [prep|scenes]
const { chromium } = require('/home/user/harness-hackathon/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const WORK = process.argv[2];
const MODE = process.argv[3] || 'scenes';
const RUN = '/home/user/harness-hackathon/bench/runs/2026-10-17T1859Z-849c856/harness/cdk2_pert_boltz2/run';
const EXE = '/opt/pw-browsers/chromium';

(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--allow-file-access-from-files'] });
  const out = path.join(WORK, 'stills');
  fs.mkdirSync(out, { recursive: true });
  if (MODE === 'prep') {
    // report.html and graph.svg as they open in Chromium
    const p = await browser.newPage({ viewport: { width: 1160, height: 820 }, deviceScaleFactor: 1.5 });
    await p.goto('file://' + RUN + '/report.html', { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(800);
    await p.screenshot({ path: path.join(out, 'report_shot.png') });
    const g = await browser.newPage({ viewport: { width: 1120, height: 800 } });
    fs.writeFileSync(path.join(WORK, 'graph_wrap.html'), `<html><body style="margin:0;background:#fff">
      <img src="file://${RUN}/graph.svg" style="width:1120px;display:block"></body></html>`);
    await g.goto('file://' + path.join(WORK, 'graph_wrap.html'));
    await g.waitForTimeout(800);
    await g.screenshot({ path: path.join(out, 'graph_tall.png'), fullPage: true });
  } else {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    const files = fs.readdirSync(path.join(WORK, 'html')).filter(f => f.endsWith('.html')).sort();
    for (const f of files) {
      await page.goto('file://' + path.join(WORK, 'html', f), { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(out, f.replace('.html', '.png')) });
    }
    console.log('stills', files.length);
  }
  await browser.close();
})();
