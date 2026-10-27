// Record real browser interactions against the isolated demo-media server.
// BASE_URL=http://127.0.0.1:8793 node scripts/record_demo.mjs /tmp/ownflick-recording
import { chromium } from 'playwright-core';
import { mkdirSync, renameSync } from 'node:fs';

const out = process.argv[2] || '/tmp/ownflick-recording';
mkdirSync(out, { recursive: true });
const browser = await chromium.launch(process.env.CHROME_PATH
  ? { executablePath: process.env.CHROME_PATH }
  : { channel: 'chrome' });
const base = process.env.BASE_URL || 'http://127.0.0.1:8793';
for (const [name, path] of [['flow', '/flow'], ['library', '/library?view=explore'], ['home', '/']]) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
    colorScheme: 'light', recordVideo: { dir: out, size: { width: 390, height: 844 } },
  });
  const page = await context.newPage();
  await page.goto(base + path, { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  if (name === 'flow') {
    // Random feed order: begin with the same waterfall used in README screenshots.
    for (let i = 0; i < 80; i++) {
      const current = await page.evaluate(() => [...document.querySelectorAll('#feed-container > *')].find(e => e.style.display === 'block')?.dataset.name || '');
      if (current.endsWith('delaneys-falls.mp4')) break;
      if (i === 79) throw new Error('Demo waterfall was not found');
      await page.keyboard.press('ArrowDown');
      await page.waitForTimeout(150);
    }
  }
  const start = Date.now();
  await page.waitForTimeout(2400);
  if (name === 'flow') {
    await page.keyboard.press('ArrowDown');
    const current = await page.evaluate(() => [...document.querySelectorAll('#feed-container > *')].find(e => e.style.display === 'block')?.dataset.name || '');
    if (current.endsWith('kamakura-underwater-fireworks.mp4')) await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(2600);
    await page.keyboard.press('ArrowDown');
  } else {
    await page.mouse.wheel(0, 350);
    await page.waitForTimeout(2600);
    await page.mouse.wheel(0, 320);
  }
  await page.waitForTimeout(3000);
  const errors = await page.locator('body').innerText();
  if (errors.includes('Internal Server Error')) throw new Error(`${path} failed`);
  await page.screenshot({ path: `${out}/${name}.png` });
  const video = page.video();
  await context.close();
  renameSync(await video.path(), `${out}/${name}.webm`);
  console.log(JSON.stringify({ name, duration: (Date.now() - start) / 1000, start }));
}
await browser.close();
