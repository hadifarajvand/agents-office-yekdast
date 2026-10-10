// Agents Office — the build loop.
//   node check.mjs                      build, data sync, backend tests, offline browser smoke
//   AO_TEST_DATABASE_URL=postgresql://office:office@localhost:5432/office_ui node check.mjs
//                                       … plus the live-UI smoke: the real server on that database
//                                         with scripted models, driven through the Jobs screen
//   CHECK_CORE=1 node check.mjs         (npm run check:core) the inner loop: build, data sync, config, backend
//                                         tests. No browser smoke, no live UI; run the full check before committing.
//   CHECK_REQUIRE_SERVER=1 node check.mjs   fail (instead of skip) when nothing answers on the port
// Every step prints ✓ or ✗ with the reason; the process exits 1 if anything failed. Nothing here
// calls a real model, 9router, Docker, GitHub or Dokploy: those are the laptop runbook (PLAN.md §11).
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { loadConfig, ROOT } from './config.mjs';

const results = [];
const ok = (name, detail = '') => { results.push([true, name, detail]); console.log(`✓ ${name}${detail ? '  — ' + detail : ''}`); };
const bad = (name, detail = '') => { results.push([false, name, detail]); console.log(`✗ ${name}${detail ? '  — ' + detail : ''}`); };
const step = async (name, fn) => { try { const d = await fn(); ok(name, d || ''); return true; } catch (e) { bad(name, e.message); return false; } };
const sh = (cmd, args, opts = {}) => new Promise((resolve, reject) => {
  const p = spawn(cmd, args, { cwd: ROOT, ...opts }); let out = '', err = '';
  p.stdout?.on('data', d => { out += d; }); p.stderr?.on('data', d => { err += d; });
  p.on('close', c => c === 0 ? resolve(out) : reject(new Error((err || out).trim().split('\n').slice(-3).join(' | '))));
  p.on('error', reject);
});
const cfg = loadConfig();
const CORE = process.env.CHECK_CORE === '1';
// the backend's own venv when it exists, so the tests run with the project's dependencies
const PY = fs.existsSync(path.join(ROOT, 'backend', '.venv', 'bin', 'python')) ? path.join(ROOT, 'backend', '.venv', 'bin', 'python') : 'python3';


/* ---------- browser launcher shared by the smoke sections ---------- */
let chromium = null;
try { ({ chromium } = await import('playwright')); } catch { try { ({ chromium } = await import('playwright-core')); } catch {} }
function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (root && fs.existsSync(root)) {
    for (const d of fs.readdirSync(root).sort().reverse()) {
      const p = path.join(root, d, 'chrome-linux', 'chrome');
      if (/^chromium-/.test(d) && fs.existsSync(p)) return p;
    }
  }
  return undefined;
}
async function launch() {
  const args = ['--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--no-sandbox'];
  const executablePath = findChrome();
  try { return await chromium.launch({ args, ...(executablePath ? { executablePath } : {}) }); }
  catch { return await chromium.launch({ channel: 'chrome', args }); }
}

/* ---------- 1. build ---------- */
import { genRoster } from './scripts/gen_roster.mjs';
genRoster();
const SEATS = JSON.parse(fs.readFileSync(path.join(ROOT, 'backend', 'app', 'seed', 'roster_seed.json'), 'utf8')).agents.length;
const { DEPTS: DEPT_NAMES_ALL, DEPT_KEYS: DK } = await import('./src/data.js');
const DEPT_NAMES = Object.fromEntries(DK.map(k => [k, DEPT_NAMES_ALL[k].short]));
await step('build: braingraph + bundle', async () => {
  const out = await sh('node', ['build.mjs']);
  const html = fs.readFileSync(path.join(ROOT, 'dist', 'command-centre-v2.html'), 'utf8');
  if (html.length < 500000) throw new Error('bundle looks too small: ' + html.length);
  if (!/AGENTS OFFICE/.test(html)) throw new Error('shell missing');
  return out.trim().split('\n').pop();
});
await step('build: graph has linked notes', async () => {
  const { BRAIN } = await import('./src/braingraph.js?' + Date.now());
  if (!BRAIN.nodes.length || !BRAIN.links.length) throw new Error('empty graph');
  if (!BRAIN.floor || BRAIN.floor.length < Math.min(90, BRAIN.nodes.length)) throw new Error('floor layout missing');
  return `${BRAIN.notes} notes · ${BRAIN.nodes.length} linked · ${BRAIN.links.length} links`;
});

/* ---------- 1b. the three roster copies agree (they were drifting apart) ---------- */
await step('data: seed, shipped roster and src/data.js agree on every seat', async () => {
  const seed = JSON.parse(fs.readFileSync(path.join(ROOT, 'backend', 'app', 'seed', 'roster_seed.json'), 'utf8'));
  const shipped = JSON.parse(fs.readFileSync(path.join(ROOT, 'office.agents.json'), 'utf8'));
  const { AGENTS, DEPT_KEYS, DEPTS } = await import('./src/data.js');
  if (seed.agents.length !== AGENTS.length) throw new Error(`seats: seed ${seed.agents.length}, data.js ${AGENTS.length}`);
  const sd = new Map(seed.agents.map(a => [a.id, a]));
  for (const a of AGENTS) {
    const s = sd.get(a.id);
    if (!s) throw new Error('data.js has a seat the seed lacks: ' + a.id);
    if (s.dept !== a.dept) throw new Error(`${a.id}: department ${s.dept} (seed) vs ${a.dept} (data.js)`);
    if (!!s.lead !== !!a.lead) throw new Error(`${a.id}: lead flag differs`);
    if (s.name !== a.name) throw new Error(`${a.id}: name "${s.name}" (seed) vs "${a.name}" (data.js)`);
  }
  for (const e of shipped.agents) if (!sd.has(e.id)) throw new Error('office.agents.json names an unknown seat: ' + e.id);
  const leads = AGENTS.filter(a => a.lead).map(a => a.dept).sort().join(',');
  if (leads !== [...DEPT_KEYS].sort().join(',')) throw new Error('every department needs exactly one lead: ' + leads);
  return `${AGENTS.length} seats · ${DEPT_KEYS.length} departments · ${shipped.agents.length} shipped overrides`;
});
await step('config: office.config.json is valid JSON with no secrets', async () => {
  const text = fs.readFileSync(path.join(ROOT, 'office.config.json'), 'utf8');
  JSON.parse(text);
  if (/(sk-ant-|ghp_|xox[bp]-|AKIA|Bearer\s)/.test(text)) throw new Error('looks like a secret in office.config.json');
});

/* ---------- 1c. the backend's own tests ---------- */
await step('backend: pytest', async () => {
  let out;
  try { out = await sh(PY, ['-m', 'pytest', '-q', '--ignore=tests/e2e', '-p', 'no:cacheprovider'], { cwd: path.join(ROOT, 'backend'), env: { ...process.env } }); }
  catch (e) { throw new Error('backend tests failed or python deps are missing (pip install -r backend/requirements-dev.txt): ' + e.message); }
  return out.trim().split('\n').pop();
});

/* ---------- 2. offline smoke (Playwright) ---------- */
if (CORE) console.log('· browser smoke and live UI skipped (CHECK_CORE=1)');
else if (!chromium) bad('smoke: playwright', 'not installed — npm i -D playwright-core (uses your Chrome)');
else {
  let browser = null;
  try {
    browser = await launch();
    const page = await browser.newPage({ viewport: { width: 1512, height: 900 } });
    const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error') errors.push(m.text().slice(0, 120)); });
    await page.goto('file://' + path.join(ROOT, 'dist', 'command-centre-v2.html') + '?s=check&norender=1'); await page.waitForTimeout(3000);
    await step('smoke: loads without page errors', async () => { if (errors.length) throw new Error(errors[0]); });
    await step('smoke: every seat at its desk', async () => { const n = await page.evaluate(() => Object.keys(window.CC.R).length); if (n !== SEATS) throw new Error('agents: ' + n); return n + ' agents'; });
    await step('smoke: eight department cards + the Brain tag', async () => {
      const t = await page.evaluate(() => [...document.querySelectorAll('.badge .b-name')].map(e => e.textContent.trim()));
      for (const k of [...Object.values(DEPT_NAMES), 'THE BRAIN']) if (!t.some(x => x.startsWith(k))) throw new Error('missing card ' + k);
    });
    await step('smoke: task panel has rows and counts', async () => {
      const n = await page.evaluate(() => document.querySelectorAll('.tp-row').length); if (n < 10) throw new Error('rows: ' + n);
      const chips = await page.evaluate(() => document.querySelectorAll('.tp-chip').length); if (chips !== 6) throw new Error('chips: ' + chips);
      return n + ' rows';
    });
    await step('smoke: command bar adds a task in demo mode', async () => {
      await page.click('.tp-dd'); await page.click('.tp-menu button[data-k="revenue"]');
      await page.fill('.tp-in', 'cut a 15 second teaser from the demo reel'); await page.keyboard.press('Enter'); await page.waitForTimeout(600);
      const hint = await page.evaluate(() => document.querySelector('.tp-hint').textContent); if (!/Added/.test(hint)) throw new Error('hint: ' + hint);
      await page.waitForFunction(() => [...document.querySelectorAll('.tp-row .tp-t')].some(e => /teaser/i.test(e.textContent)), null, { timeout: 8000 }).catch(() => {});
      const row = await page.evaluate(() => [...document.querySelectorAll('.tp-row .tp-t')].some(e => /teaser/i.test(e.textContent))); if (!row) throw new Error('row not in the feed');
      return hint.trim().slice(0, 60);
    });
    await step('smoke: a routine typed in the bar lands in SCHEDULED (demo)', async () => {
      await page.click('.tp-dd'); await page.click('.tp-menu button[data-k="content"]');
      await page.fill('.tp-in', 'every weekday at 8am, triage the inbox and tell me what needs me');
      await page.evaluate(() => document.querySelector('.tp-in').dispatchEvent(new Event('input', { bubbles: true })));
      await page.waitForFunction(() => /Routine/.test(document.querySelector('.tp-hint').textContent), null, { timeout: 5000 }).catch(() => {});
      const pre = await page.evaluate(() => document.querySelector('.tp-hint').textContent); if (!/Routine/.test(pre) || !/every weekday · 08:00/.test(pre)) throw new Error('hint before Add: ' + pre);
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => /Routine set|couldn/.test(document.querySelector('.tp-hint').textContent), null, { timeout: 5000 }).catch(() => {});
      const hint = await page.evaluate(() => document.querySelector('.tp-hint').textContent); if (!/Routine set/.test(hint)) throw new Error('hint: ' + hint);
      await page.waitForTimeout(400);
      const n = await page.evaluate(() => window.CC.routines().length); if (n !== 1) throw new Error('routines: ' + n);
      const row = await page.evaluate(() => [...document.querySelectorAll('.tp-row.sched .tp-t')].some(e => /triage the inbox/i.test(e.textContent))); if (!row) throw new Error('no SCHEDULED row');
      const strip = await page.evaluate(() => { const e = document.querySelector('.tp-next'); return e.hidden ? '' : e.textContent; }); if (!/NEXT/.test(strip) || !/triage/i.test(strip)) throw new Error('next-up strip: ' + strip);
      await page.keyboard.press('b'); await page.waitForTimeout(600);
      const col = await page.evaluate(() => [...document.querySelectorAll('#board .lh')].map(e => e.textContent)); if (col[1] !== 'SCHEDULED') throw new Error('board columns: ' + col.join(','));
      const card = await page.evaluate(() => document.querySelectorAll('#board .tk.sched').length); if (!card) throw new Error('no SCHEDULED card on the board');
      await page.keyboard.press('Escape'); await page.waitForTimeout(400);
      await page.evaluate(() => window.CC.tasks.rtAct(window.CC.routines()[0].id, 'run')); await page.waitForTimeout(500);
      const fired = await page.evaluate(() => window.CC.tasks.tasks.some(t => t.routine && /triage the inbox/i.test(t.title))); if (!fired) throw new Error('RUN NOW did not make a task');
      await page.click('.tp-dd'); await page.click('.tp-menu button[data-k="engineering"]');
      await page.fill('.tp-in', 'every day at 9am post the reel'); await page.keyboard.press('Enter'); await page.waitForTimeout(400);
      const no = await page.evaluate(() => document.querySelector('.tp-hint').textContent); if (/later release/.test(no)) throw new Error('engineering routine refused: ' + no);
      const still = await page.evaluate(() => window.CC.routines().length); if (still !== 2) throw new Error('engineering routine not added: ' + still);
      const opts = await page.evaluate(() => [...document.querySelectorAll('.tp-model option')].map(o => o.value).join(',') + '|' + document.querySelector('.tp-model').value); if (opts !== 'sonnet,opus,fable,haiku|haiku') throw new Error('model menu: ' + opts);
      const eff = await page.evaluate(() => [...document.querySelectorAll('.tp-effort option')].map(o => o.value).join(',') + '|' + document.querySelector('.tp-effort').value); if (eff !== ',low,medium,high,xhigh,max|') throw new Error('effort menu: ' + eff);
      // V3.7: the box grows with the text, and the big editor mirrors it both ways
      await page.fill('.tp-in', 'line one\nline two\nline three'); await page.evaluate(() => document.querySelector('.tp-in').dispatchEvent(new Event('input', { bubbles: true }))); await page.waitForTimeout(200);
      const grown = await page.evaluate(() => document.querySelector('.tp-in').offsetHeight); if (grown < 50) throw new Error('box did not grow: ' + grown + 'px');
      await page.click('.tp-big-btn'); await page.waitForTimeout(300);
      const bigOn = await page.evaluate((EN) => document.getElementById('tpBig').classList.contains('on') && document.querySelector('.tb-in').value === document.querySelector('.tp-in').value && document.querySelector('.tb-dept').textContent === EN, DEPT_NAMES_ALL.engineering.name); if (!bigOn) throw new Error('big editor did not open with the text');
      await page.type('.tb-in', ' and more'); await page.waitForTimeout(200);
      const back = await page.evaluate(() => document.querySelector('.tp-in').value.endsWith(' and more') && /VP ENGINEERING|Goes to|Probably/.test(document.querySelector('.tb-hint').textContent)); if (!back) throw new Error('big editor did not mirror back');
      await page.keyboard.press('Escape'); await page.waitForTimeout(200);
      const bigOff = await page.evaluate(() => !document.getElementById('tpBig').classList.contains('on')); if (!bigOff) throw new Error('Esc did not close the big editor');
      await page.fill('.tp-in', ''); await page.evaluate(() => document.querySelector('.tp-in').dispatchEvent(new Event('input', { bubbles: true }))); await page.evaluate(() => document.querySelector('.tp-in').blur()); await page.click('.tp-chip[data-f="all"]'); // hand the keys back, feed back to All
      const rest = await page.evaluate(() => document.querySelector('.tp-in').offsetHeight); if (rest > 34) throw new Error('box did not shrink back: ' + rest + 'px');
      return 'hint says the schedule · SCHEDULED row + next-up strip + board column · RUN NOW fires · engineering routine accepted · box grows + big editor mirrors';
    });
    await step('smoke: department focus opens the chat rail', async () => {
      await page.keyboard.press('1'); await page.waitForTimeout(1800);
      const cls = await page.evaluate(() => document.getElementById('rail').className); if (!/agentOpen/.test(cls) || !/open/.test(cls)) throw new Error('rail: ' + cls);
      const strip = await page.evaluate(() => document.querySelector('#topconn').className); if (!/focus/.test(strip)) throw new Error('top strip not centred');
      await page.keyboard.press('Escape'); await page.waitForTimeout(1200);
    });
    await step('smoke: B opens and closes the company board', async () => {
      await page.keyboard.press('b'); await page.waitForTimeout(700);
      if (!(await page.evaluate(() => window.CC.tasks.isOpen()))) throw new Error('board did not open');
      await page.keyboard.press('Escape'); await page.waitForTimeout(500);
      if (await page.evaluate(() => window.CC.tasks.isOpen())) throw new Error('board did not close');
    });
    await step('smoke: G opens the Brain graph with notes', async () => {
      await page.keyboard.press('g'); await page.waitForTimeout(700);
      if (!(await page.evaluate(() => window.CC.brain.isOpen()))) throw new Error('graph did not open');
      const n = await page.evaluate(() => window.CC.brain.nodes.length); if (n < 10) throw new Error('nodes: ' + n);
      await page.keyboard.press('Escape'); await page.waitForTimeout(300);
      if (await page.evaluate(() => window.CC.brain.isOpen())) throw new Error('graph did not close');
      return n + ' notes';
    });
    await step('smoke: approval flow reaches the panel', async () => {
      await page.evaluate(() => window.CC.requestApproval('piper'));
      await page.waitForFunction(() => document.querySelectorAll('.tp-row.waiting').length > 0, null, { timeout: 4000 }).catch(() => {}); // the panel renders on the next frame; headless WebGL frames can be slow
      const w = await page.evaluate(() => document.querySelectorAll('.tp-row.waiting').length); if (!w) throw new Error('no waiting row (piper: ' + (await page.evaluate(() => window.CC.R.piper.state)) + ')');
    });
    await step('smoke: no errors after the run', async () => { if (errors.length) throw new Error(errors[0]); });
  } catch (e) { bad('smoke: browser', e.message); }
  finally { if (browser) await browser.close(); }
}


/* ---------- 3. live-UI smoke: the real server (real Postgres, scripted models) driven through the page ---------- */
const DB = process.env.AO_TEST_DATABASE_URL;
if (CORE) {}
else if (!chromium) bad('live-ui: playwright', 'not installed');
else if (!DB) ok('live-ui: skipped', 'set AO_TEST_DATABASE_URL to drive the real server through the Jobs screen');
else {
  const port = 4590 + Math.floor(Math.random() * 9);
  const brain = fs.mkdtempSync(path.join(fs.realpathSync('/tmp'), 'ao-check-brain-'));
  let server = null, browser = null;
  try {
    await sh(PY, ['-c', "import os, psycopg; c = psycopg.connect(os.environ['AO_TEST_DATABASE_URL'], autocommit=True); c.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')"], { env: { ...process.env } });
    server = spawn(PY, ['-m', 'tests.ui_server', String(port)], { cwd: path.join(ROOT, 'backend'), env: { ...process.env, DATABASE_URL: DB, AO_BRAIN: brain }, stdio: ['ignore', 'pipe', 'pipe'] });
    let serverLog = ''; server.stdout.on('data', d => { serverLog += d; }); server.stderr.on('data', d => { serverLog += d; });
    const base = `http://127.0.0.1:${port}`;
    let up = false;
    for (let i = 0; i < 60 && !up; i++) { try { up = (await fetch(base + '/api/health')).ok; } catch {} if (!up) await new Promise(r => setTimeout(r, 500)); }
    await step('live-ui: the server starts on real Postgres', async () => { if (!up) throw new Error('no answer on ' + base + ': ' + serverLog.slice(-300)); });
    if (up) {
      browser = await launch();
      const page = await browser.newPage({ viewport: { width: 1100, height: 720 } });
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      await step('live-ui: the API refuses a request without the office header and a foreign origin', async () => {
        const noHeader = await page.request.post(base + '/api/tasks', { data: { dept: 'fin', text: 'x' } });
        if (noHeader.status() !== 403) throw new Error('without X-AO-Client: ' + noHeader.status());
        const foreign = await page.request.get(base + '/api/health', { headers: { origin: 'https://evil.example' } });
        if (foreign.status() !== 403) throw new Error('foreign origin: ' + foreign.status());
        const text = await page.request.post(base + '/api/tasks', { data: 'dept=fin', headers: { 'x-ao-client': 'office', 'content-type': 'text/plain' } });
        if (text.status() !== 415) throw new Error('text/plain body: ' + text.status());
      });
      await page.goto(base + '/?norender=1');
      await page.waitForFunction(() => document.querySelector('.tp-mode') && !document.querySelector('.tp-mode').hidden, null, { timeout: 20000 }).catch(() => {});
      await step('live-ui: the page goes live and shows no invented work', async () => {
        const live = await page.evaluate(() => document.querySelector('.tp-mode').textContent);
        if (live !== 'LIVE') throw new Error('mode badge: ' + live);
        const demo = await page.evaluate(() => window.CC.tasks.tasks.filter(t => !t.live).length);
        if (demo) throw new Error(demo + ' demo tasks are still on a live office');
      });
      await step('live-ui: a client job runs from the form to the owner’s verdict', async () => {
        await page.click('#topJobs'); await page.click('#jbNew');
        await page.fill('#jbForm [name=title]', 'Bakery site'); await page.fill('#jbForm [name=client]', 'Acme Bakery');
        await page.fill('#jbForm [name=deposit_ref]', 'INV-001 paid');
        await page.fill('#jbForm [name=description]', 'A small ordering site for a bakery with a menu and an order form.');
        await page.selectOption('#jbForm [name=requestedTier]', '1');
        await page.click('#jbForm button[type=submit]');
        await page.waitForSelector('#jbYes', { timeout: 20000 });
        const txt = await page.$eval('.jb-banner p', e => e.textContent); if (!/VERIFY/.test(txt)) throw new Error('first gate: ' + txt);
        const stages = await page.$$eval('.jb-stage b', els => els.map(e => e.textContent.replace(/^\S+\s/, '')));
        if (stages.join('|') !== 'Intake|Verify|Scope|Build|Security review|Preview deploy|Exposure|Handoff') throw new Error('stage order: ' + stages.join('|'));
        const stuck = await page.evaluate(() => Object.values(window.CC.R).filter(r => r.state === 'stuck').map(r => r.a.id));
        if (stuck.join() !== 'olead') throw new Error('the exec lead should be waving, got: ' + stuck.join());
        return 'eight stages in order · the exec lead waves';
      });
      await step('live-ui: the exposure gate shows the three keys; the owner approves from the lead’s chat card', async () => {
        await page.click('#jbYes');
        await page.waitForFunction(() => /EXPOSURE/.test(document.querySelector('.jb-banner p')?.textContent || ''), null, { timeout: 20000 });
        const keys = await page.$eval('.jb-main', e => e.innerText); if (!/EXPOSURE · THREE KEYS/.test(keys)) throw new Error('keys row missing');
        await page.keyboard.press('Escape');
        if (await page.evaluate(() => document.body.classList.contains('jobsOpen'))) throw new Error('Escape did not close the Jobs screen');
        const lead = await page.evaluate(() => Object.values(window.CC.R).find(r => r.state === 'stuck')?.a.id);
        if (lead !== 'comply') throw new Error('the security lead should wave at exposure, got ' + lead);
        await page.evaluate(id => window.CC.openAgent(id), lead);
        await page.waitForSelector('.m-appr .a-yes', { timeout: 8000 });
        await page.click('.m-appr .a-yes');
        await page.waitForTimeout(2500);
        await page.click('#topJobs');
        await page.waitForFunction(() => /NOW GATED/.test(document.querySelector('.jb-main')?.innerText || ''), null, { timeout: 15000 })
          .catch(() => { throw new Error('tier pill did not become GATED after the owner approved'); });
        const t = await page.$eval('.jb-main', e => e.innerText);
        if (!/https:\/\/p1\.example\.test/.test(t)) throw new Error('preview URL missing');
      });
      await step('live-ui: the handoff closes the job', async () => {
        await page.waitForSelector('#jbYes', { timeout: 15000 });
        await page.click('#jbYes');
        await page.waitForFunction(() => document.querySelector('.jb-main .jb-badge')?.textContent === 'DONE', null, { timeout: 15000 })
          .catch(async () => { throw new Error('status: ' + await page.$eval('.jb-main .jb-badge', e => e.textContent)); });
      });
      await step('live-ui: no page errors', async () => { if (errors.length) throw new Error(errors[0]); });
    }
  } catch (e) { bad('live-ui: browser run', e.message); }
  finally {
    if (browser) await browser.close();
    if (server) server.kill('SIGTERM');
    fs.rmSync(brain, { recursive: true, force: true });
  }
}

/* ---------- 4. a server already running on the configured port ---------- */
await step('server: reachable and honest, if one is running', async () => {
  let r;
  try { r = await fetch(`http://127.0.0.1:${cfg.port}/api/health`, { signal: AbortSignal.timeout(2500) }); }
  catch { if (process.env.CHECK_REQUIRE_SERVER === '1') throw new Error(`nothing answers on :${cfg.port}`); return `nothing on :${cfg.port} — skipped (CHECK_REQUIRE_SERVER=1 makes this a failure)`; }
  const h = await r.json();
  for (const k of ['ok', 'version', 'agents', 'pipeline', 'roles', 'router']) if (!(k in h)) throw new Error('health lacks ' + k);
  if (!Array.isArray(h.agents) || h.agents.length !== SEATS) throw new Error('health.agents should list ' + SEATS + ' seats');
  return `v${h.version} · worker ${h.worker}`;
});

/* ---------- summary ---------- */
const fails = results.filter(r => !r[0]);
console.log(`\n${fails.length ? '✗' : '✓'} ${results.length - fails.length}/${results.length} checks passed${fails.length ? ' — ' + fails.map(f => f[1]).join(', ') : ''}`);
process.exit(fails.length ? 1 : 0);
