// UI side of the go-live slice check. Run against a booted office:
//   BASE_URL=http://127.0.0.1:4520 node scripts/verify_ui.mjs
// Needs at least one finished or running job (run scripts/verify_slice.py first).
// On a machine with no GPU the page starves; ?norender=1 skips 3D drawing and keeps the DOM honest.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:4520').replace(/\/$/, '');
const LIVE = new Set(['exec', 'engineering']);
const SHOTS = path.join(ROOT, 'data', 'verify-shots');
fs.mkdirSync(SHOTS, { recursive: true });

let chromium;
try { ({ chromium } = await import('playwright')); } catch { ({ chromium } = await import('playwright-core')); }
function chrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (root && fs.existsSync(root)) for (const d of fs.readdirSync(root).sort().reverse()) {
    const p = path.join(root, d, 'chrome-linux', 'chrome'); if (/^chromium-/.test(d) && fs.existsSync(p)) return p;
  }
}
const results = [];
function check(name, ok, detail = '') { results.push({ name, ok }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  — ' + detail : ''}`); }

const browser = await chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--no-sandbox'], ...(chrome() ? { executablePath: chrome() } : {}) });
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });
const errors = []; page.on('pageerror', e => errors.push(e.message));
try {
  await page.goto(`${BASE}/?norender=1`);
  await page.waitForFunction(() => window.CC && Object.keys(window.CC.R).length > 0, null, { timeout: 30000 });
  await page.waitForTimeout(2500);
  const seats = await page.evaluate(() => Object.values(window.CC.R).map(r => ({ id: r.a.id, dept: r.a.dept, standby: r.pill.classList.contains('standby') })));
  const live = seats.filter(s => LIVE.has(s.dept)), off = seats.filter(s => !LIVE.has(s.dept));
  check('page: 27 seats are drawn', seats.length === 27, String(seats.length));
  check('page: the live departments’ seats are not on STANDBY', live.length > 0 && live.every(s => !s.standby), live.map(s => s.id).join(','));
  check('page: every other seat shows STANDBY', off.length > 0 && off.every(s => s.standby), `${off.filter(s => s.standby).length}/${off.length}`);
  await page.screenshot({ path: path.join(SHOTS, 'overview.png') });

  await page.keyboard.press('j');
  await page.waitForSelector('#jobsOv .jb-card', { timeout: 15000 });
  await page.click('#jobsOv .jb-card');
  await page.waitForSelector('#jobsOv .jb-stage', { timeout: 15000 });
  const stages = await page.evaluate(() => [...document.querySelectorAll('#jobsOv .jb-stage')].map(e => ({ label: e.querySelector('b').textContent.replace(/^\S+\s/, '').trim(), who: e.querySelectorAll('span')[0].textContent.trim() })));
  const by = Object.fromEntries(stages.map(s => [s.label.toLowerCase(), s.who]));
  for (const k of ['security review', 'preview deploy', 'exposure', 'handoff']) check(`jobs: ${k} shows OWNER`, by[k] === 'OWNER', by[k]);
  for (const k of ['verify', 'scope', 'build']) check(`jobs: ${k} shows its lead, not OWNER`, !!by[k] && by[k] !== 'OWNER', by[k]);
  await page.screenshot({ path: path.join(SHOTS, 'jobs.png') });
  check('page: no script errors', errors.length === 0, errors[0] || '');
} catch (e) {
  check('ui: the checks ran', false, String(e.message || e).split('\n')[0]);
} finally {
  await browser.close();
}
const bad = results.filter(r => !r.ok).length;
console.log(`\n${results.length - bad} passed, ${bad} failed  ->  data/verify-shots/`);
process.exit(bad ? 1 : 0);
