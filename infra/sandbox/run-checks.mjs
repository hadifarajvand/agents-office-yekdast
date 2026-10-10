// Runs INSIDE the build-job container after the coding agent has finished: install, build,
// test, start the app and probe it, then the browser test if the app has one. Writes
// /out/checks.json = [{name, ok, detail, ms}] for the host to read; the host never runs the
// app's code itself. Every command has a time limit; output kept is the tail only.
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';

const OUT = process.env.CHECKS_OUT || '/out/checks.json';
const PORT = process.env.CHECK_PORT || '3000';
const BASE = `http://127.0.0.1:${PORT}`;
const results = [];
const tail = (s, n = 2500) => (s.length > n ? '…' + s.slice(-n) : s);

function run(cmd, args, { timeoutMs = 600_000, env = {} } = {}) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    let out = '';
    const p = spawn(cmd, args, { env: { ...process.env, CI: '1', ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
    p.stdout.on('data', (d) => (out += d));
    p.stderr.on('data', (d) => (out += d));
    const timer = setTimeout(() => { out += `\n[timed out after ${timeoutMs / 1000}s]`; p.kill('SIGKILL'); }, timeoutMs);
    p.on('close', (code) => { clearTimeout(timer); resolve({ ok: code === 0, out, ms: Date.now() - t0 }); });
    p.on('error', (e) => { clearTimeout(timer); resolve({ ok: false, out: String(e), ms: Date.now() - t0 }); });
  });
}

function record(name, ok, detail, ms = 0) {
  results.push({ name, ok: !!ok, detail: tail(String(detail || '')), ms });
}

async function probe(path, tries) {
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(BASE + path, { redirect: 'manual' });
      return { status: r.status, body: (await r.text()).slice(0, 400) };
    } catch { await new Promise((r) => setTimeout(r, 1000)); }
  }
  return { status: 0, body: 'no answer' };
}

async function main() {
  if (!existsSync('package.json')) {
    record('the app has a package.json', false, 'no package.json in /workspace');
    return;
  }
  const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
  const scripts = pkg.scripts || {};

  // The builder may add a dependency to package.json without refreshing the lockfile, which
  // makes `npm ci` refuse. Fall back to `npm install` (it rewrites the lock) so a legitimate
  // dependency is not a failed build; a genuine install error still fails on the second try.
  const installOnce = () => existsSync('package-lock.json')
    ? run('npm', ['ci', '--prefer-offline', '--no-audit', '--no-fund'])
    : run('npm', ['install', '--prefer-offline', '--no-audit', '--no-fund']);
  let install = await installOnce();
  if (!install.ok && existsSync('package-lock.json')) {
    install = await run('npm', ['install', '--prefer-offline', '--no-audit', '--no-fund']);
  }
  // A dropped connection through the egress proxy (ECONNRESET, ETIMEDOUT) is the network's fault:
  // retry with backoff instead of failing the whole build on one reset.
  for (let i = 1; !install.ok && /ECONNRESET|ETIMEDOUT|EAI_AGAIN|network/i.test(install.out) && i <= 3; i++) {
    await new Promise((r) => setTimeout(r, 5000 * i));
    install = await installOnce();
  }
  record('dependencies install', install.ok, install.out, install.ms);
  if (!install.ok) return;

  if (scripts.build) {
    // A retry reuses the workspace: a stale .next/standalone from an earlier attempt (read-only
    // files) made the template's cpSync step fail with EACCES, so the gate failed on leftovers,
    // not on the builder's code. Build from clean.
    await run('sh', ['-c', 'chmod -R u+rwX .next 2>/dev/null; rm -rf .next']);
    const b = await run('npm', ['run', 'build']);
    record('the app builds (npm run build)', b.ok, b.out, b.ms);
    if (!b.ok) return;
  }

  if (!scripts.test) record('unit tests pass (npm test)', false, 'package.json has no "test" script');
  else {
    const t = await run('npm', ['test']);
    record('unit tests pass (npm test)', t.ok, t.out, t.ms);
  }

  if (!scripts.start) { record('the app starts (npm start)', false, 'package.json has no "start" script'); return; }
  const t0 = Date.now();
  let log = '';
  if ((await probe('/healthz', 1)).status !== 0) {
    record('the app starts and /healthz answers 200', false, `port ${PORT} was already answering before the app started`);
    return;
  }
  const server = spawn('npm', ['start'], { env: { ...process.env, PORT, HOSTNAME: '127.0.0.1', NODE_ENV: 'production', EPHEMERAL_DB: '1' }, stdio: ['ignore', 'pipe', 'pipe'], detached: true });
  server.stdout.on('data', (d) => (log += d));
  server.stderr.on('data', (d) => (log += d));
  try {
    const health = await probe('/healthz', 60);
    if (health.status === 200 && server.exitCode !== null) health.status = 0; // answered by something else: the app itself exited
    record('the app starts and /healthz answers 200', health.status === 200, `status ${health.status}\n${tail(log, 1500)}`, Date.now() - t0);
    const home = await probe('/', 5);
    record('the home page answers without a server error', home.status > 0 && home.status < 500, `status ${home.status}`);
    if (scripts['test:e2e']) {
      const e = await run('npm', ['run', 'test:e2e'], { env: { BASE_URL: BASE } });
      record('browser tests pass (npm run test:e2e)', e.ok, e.out, e.ms);
    } else record('browser tests pass (npm run test:e2e)', false, 'package.json has no "test:e2e" script');
  } finally {
    try { process.kill(-server.pid, 'SIGKILL'); } catch { /* already gone */ }
  }
}

main()
  .catch((e) => record('run-checks finished', false, String(e && e.stack || e)))
  .finally(() => writeFileSync(OUT, JSON.stringify(results, null, 1)));
