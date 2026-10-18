// Element screenshots of the live web UI for the input/output scenes of film C (2x device scale).
// Usage: node shoot_live.js <out_dir>
const { chromium } = require('/home/user/harness-hackathon/node_modules/playwright');
const path = require('path');
const OUT = process.argv[2];
const BASE = 'https://persistentepiphany--pah-web.us-east.modal.run';
const RID = 'ligand_pose-249098d10007';
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium', args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  await p.goto(`${BASE}/reports/${RID}`, { waitUntil: 'networkidle', timeout: 90000 });
  await p.waitForTimeout(6000);
  const shot = async (tid, name, opts = {}) => {
    const l = p.getByTestId(tid).first();
    await l.scrollIntoViewIfNeeded().catch(() => {});
    await p.waitForTimeout(400);
    await l.screenshot({ path: path.join(OUT, name + '.png'), ...opts }).catch(e => console.log('fail', name, String(e).slice(0, 120)));
  };
  await p.screenshot({ path: path.join(OUT, 'report_top.png') });
  await shot('verdict', 'verdict');
  await shot('issues', 'issues');
  await shot('structure-panel', 'structure');
  await shot('dimension-strip', 'dimensions');
  await shot('execution', 'execution');
  await shot('check-table', 'checks');
  await shot('thresholds', 'thresholds');
  await shot('outputs', 'outputs');
  await p.goto(`${BASE}/reports/${RID}/ensemble`, { waitUntil: 'networkidle', timeout: 90000 });
  await p.waitForTimeout(5000);
  await p.screenshot({ path: path.join(OUT, 'ensemble_top.png') });
  await shot('structure-grid', 'ensemble_grid');
  await p.goto(`${BASE}/agent`, { waitUntil: 'networkidle', timeout: 90000 });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: path.join(OUT, 'agent.png') });
  await b.close();
  console.log('ok');
})();
