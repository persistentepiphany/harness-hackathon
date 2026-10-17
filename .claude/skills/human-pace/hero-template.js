// Human-paced demo recording for `playwright-cli run-code --filename <this file>`.
// Copy it, set URL and OUT, then replace the steps in the "Script" section.
// Timings come from the human-pace skill (SKILL.md). Change PACE there first, then here.
async page => {
  const URL = 'http://127.0.0.1:3000/';
  const OUT = 'out/videos/demo.webm';

  const PACE = {
    cursorMs: 900,        // cursor travel and click marker per action
    typeMsPerChar: 90,    // about 11 characters a second
    afterClickMs: 800,    // let the UI react before the next move
    readMsPerWord: 300,   // hold new text long enough to read
    minHoldMs: 1500,
    chapterMs: 2500,
    scrollMs: 1200,       // smooth scroll plus a beat to look
    endHoldMs: 2000,
  };

  const pause = ms => page.waitForTimeout(ms);
  const holdFor = text => pause(Math.max(PACE.minHoldMs, text.split(/\s+/).length * PACE.readMsPerWord));
  // One call per string: showActions paces every action, so typing key by key
  // would add a full cursor delay to each character.
  const type = async (locator, text) => {
    await locator.click();
    await locator.pressSequentially(text, { delay: PACE.typeMsPerChar });
    await pause(PACE.afterClickMs);
  };
  const click = async locator => {
    await locator.click();
    await pause(PACE.afterClickMs);
  };
  // One smooth browser scroll. Wheel ticks are paced like clicks and crawl.
  const scrollTo = async locator => {
    await locator.evaluate(el => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
    await pause(PACE.scrollMs);
  };

  await page.screencast.start({ path: OUT, size: { width: 1280, height: 800 }, fps: 60 });
  await page.screencast.showActions({ duration: PACE.cursorMs, style: { title: 'display: none' } });
  await page.goto(URL, { waitUntil: 'networkidle' });
  await pause(PACE.minHoldMs);

  // Script
  await page.screencast.showChapter('Add a task', { duration: PACE.chapterMs });
  const input = page.getByRole('textbox').first();
  await type(input, 'Book the demo room');
  await click(page.getByRole('button', { name: 'Add' }));
  await holdFor('Book the demo room');
  await scrollTo(page.getByText('Bottom of the page'));

  await pause(PACE.endHoldMs);
  await page.screencast.stop();
}
