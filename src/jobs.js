// Agents Office — JOBS. The client-job pipeline made visible (J, or the JOBS button).
//
//   intake → verify → scope → build → security → preview → exposure → handoff
//
// Each stage belongs to a department; its lead (an agent) reviews the work and records PASS or
// FAIL with cited evidence. The owner decides only where the plan says so: the verdict, the
// handoff, and the first N gated previews (every public one). When the owner is needed the
// lead of that stage stands and waves like any approval, and the card lands in that lead's chat.
// The building department never approves its own app's exposure; the server enforces that, this
// page only shows it (the exposure stage lists the two keys and the owner's click).
//
// Live only: it needs the backend (/api/jobs). Under file:// the button says so and nothing else.
import { untilText } from './when.js';

const GATE_ASK = {
  verify: j => `Verdict needed on "${j.title}": the client job was checked (deposit, scope, price, deadline). Approve to start building, or reject to stop.`,
  exposure: j => `"${j.title}" wants a ${j.requestedTier >= 2 ? 'PUBLIC' : 'gated'} preview. The security and commercial keys are in. ${j.requestedTier >= 2 ? 'Public exposure is always yours to decide.' : `You approve the first ${j.ownerClicksNeeded} gated previews yourself.`} Approve to open it${j.requestedTier >= 2 ? ' to anyone' : ' to the client behind a login'}; the server then checks that a request without the login is refused, and takes it down if not.`,
  handoff: j => `The handoff for "${j.title}" is ready. Approve to close the job.`,
  research: j => `The market memo for "${j.title}" is ready. Its verdict is computed from the evidence, not written by an agent. Approve to accept the memo; then you can build a landing-page test or the MVP from it.`,
};
const TIER = { 0: ['PRIVATE', 'no public route'], 1: ['GATED', 'public URL behind a login'], 2: ['PUBLIC', 'open to anyone'] };
const STATE_MARK = { pending: '○', working: '◐', review: '◑', waiting: '⏸', approved: '●', failed: '✕' };
const STATUS_LABEL = { running: 'RUNNING', waiting: 'WAITING FOR YOU', parked: 'PARKED', done: 'DONE', killed: 'KILLED', failed: 'FAILED' };

const CSS = `
#topJobs { font-family: var(--ui); font-size: 11px; letter-spacing: .14em; background: var(--cream); color: var(--ink); border: 1px solid var(--hairline); border-radius: 99px; padding: 7px 13px; cursor: pointer; }
#topJobs:hover, body.jobsOpen #topJobs { background: var(--ink); color: var(--cream); border-color: var(--ink); }
#topJobs .n { display: inline-block; min-width: 16px; text-align: center; margin-left: 6px; border-radius: 99px; background: #E69393; color: #151414; font-weight: 700; padding: 0 4px; }
#topJobs .n:empty { display: none; }
#jobsOv { position: fixed; inset: 0; z-index: 41; background: var(--cream); color: var(--ink); font-family: var(--ui); display: flex; flex-direction: column; opacity: 0; pointer-events: none; transition: opacity .35s var(--ease); --jb-line: rgba(21,20,20,.1); --jb-card: #fff; --jb-soft: rgba(21,20,20,.04); }
body.dark #jobsOv { --jb-line: rgba(236,234,227,.12); --jb-card: #1E1F24; --jb-soft: rgba(236,234,227,.05); }
#jobsOv.on { opacity: 1; pointer-events: auto; }
#jobsOv .jb-band { display: flex; align-items: center; gap: 18px; height: 64px; padding: 0 22px; background: #151414; color: #FDFFF8; flex: none; }
#jobsOv .jb-brand { font-family: var(--serif); font-size: 22px; letter-spacing: .05em; }
#jobsOv .jb-brand small { font-family: var(--ui); font-size: 9.5px; letter-spacing: .18em; color: rgba(253,255,248,.55); margin-left: 12px; text-transform: uppercase; }
#jobsOv .jb-sp { flex: 1; }
#jobsOv .jb-band button { background: none; border: 0; color: #FDFFF8; font-size: 18px; cursor: pointer; }
#jobsOv .jb-body { flex: 1; display: grid; grid-template-columns: 340px 1fr; min-height: 0; }
#jobsOv .jb-list { border-right: 1px solid var(--jb-line); overflow: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
#jobsOv .jb-main { overflow: auto; padding: 22px 28px 60px; }
#jobsOv .jb-btn { font-family: var(--ui); font-size: 10.5px; letter-spacing: .14em; font-weight: 700; border: 1px solid var(--ink); background: var(--ink); color: var(--cream); border-radius: 99px; padding: 9px 16px; cursor: pointer; }
#jobsOv .jb-btn.ghost { background: none; color: var(--ink); }
#jobsOv .jb-btn.warn { background: #B5482F; border-color: #B5482F; color: #fff; }
#jobsOv .jb-btn:disabled { opacity: .45; cursor: default; }
#jobsOv .jb-card { background: var(--jb-card); border: 1px solid var(--jb-line); border-radius: 12px; padding: 12px 14px; cursor: pointer; }
#jobsOv .jb-card.sel { outline: 2px solid var(--ink); }
#jobsOv .jb-card h4 { font-size: 13px; margin-bottom: 6px; }
#jobsOv .jb-badge { display: inline-block; font-size: 9px; letter-spacing: .14em; font-weight: 700; border-radius: 99px; padding: 3px 8px; background: var(--jb-soft); }
#jobsOv .jb-badge.waiting { background: #F2B33D; color: #151414; } #jobsOv .jb-badge.parked, #jobsOv .jb-badge.failed, #jobsOv .jb-badge.killed { background: #E69393; color: #151414; } #jobsOv .jb-badge.done { background: #5ADEB7; color: #151414; }
#jobsOv .jb-steps { display: flex; gap: 4px; margin-top: 8px; }
#jobsOv .jb-steps i { flex: 1; height: 5px; border-radius: 3px; background: var(--jb-soft); }
#jobsOv .jb-steps i.approved { background: var(--c, #5ADEB7); } #jobsOv .jb-steps i.working, #jobsOv .jb-steps i.review { background: var(--c); opacity: .55; } #jobsOv .jb-steps i.waiting { background: #F2B33D; } #jobsOv .jb-steps i.failed { background: #E69393; }
#jobsOv .jb-stepper { display: grid; grid-template-columns: repeat(var(--n, 8), 1fr); gap: 8px; margin: 14px 0 20px; }
#jobsOv .jb-stage { border: 1px solid var(--jb-line); border-top: 4px solid var(--c, #999); border-radius: 8px; padding: 8px 9px; background: var(--jb-card); font-size: 10.5px; min-width: 0; }
#jobsOv .jb-stage b { display: block; font-size: 11px; letter-spacing: .04em; } #jobsOv .jb-stage span { color: var(--grey); display: block; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#jobsOv .jb-stage.waiting { background: #FFF4D6; color: #151414; } #jobsOv .jb-stage.failed { background: #FBE3E0; color: #151414; }
#jobsOv h3 { font-family: var(--serif); font-size: 26px; font-weight: 400; } #jobsOv h5 { font-size: 10px; letter-spacing: .16em; color: var(--grey); margin: 22px 0 8px; }
#jobsOv .jb-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; font-size: 12px; color: var(--grey); }
#jobsOv .jb-pill { font-size: 10px; letter-spacing: .12em; font-weight: 700; border-radius: 99px; padding: 4px 10px; border: 1px solid var(--jb-line); color: var(--ink); } #jobsOv .jb-pill.t1 { background: #F2B33D; } #jobsOv .jb-pill.t2 { background: #E69393; } #jobsOv .jb-pill.t0 { background: var(--jb-soft); }
#jobsOv .jb-banner { margin: 16px 0; padding: 14px 16px; border-radius: 12px; border: 1px solid var(--jb-line); background: #FFF4D6; color: #151414; } #jobsOv .jb-banner.bad { background: #FBE3E0; }
#jobsOv .jb-banner p { font-size: 13px; line-height: 1.5; margin-bottom: 10px; } #jobsOv .jb-banner .acts { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } #jobsOv .jb-banner input { flex: 1; min-width: 200px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--jb-line); font: inherit; }
#jobsOv table { border-collapse: collapse; width: 100%; font-size: 12px; } #jobsOv td, #jobsOv th { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--jb-line); vertical-align: top; } #jobsOv th { font-size: 9.5px; letter-spacing: .12em; color: var(--grey); font-weight: 600; }
#jobsOv .ok { color: #1E9070; font-weight: 700; } #jobsOv .no { color: #B5482F; font-weight: 700; }
#jobsOv details { margin: 6px 0; font-size: 12px; } #jobsOv summary { cursor: pointer; } #jobsOv pre { white-space: pre-wrap; word-break: break-word; font-size: 11px; background: var(--jb-soft); padding: 8px; border-radius: 6px; margin-top: 4px; }
#jobsOv form[hidden] { display: none; }
#jobsOv form { display: grid; gap: 8px; background: var(--jb-card); border: 1px solid var(--jb-line); border-radius: 12px; padding: 12px; }
#jobsOv form input, #jobsOv form textarea, #jobsOv form select { width: 100%; min-width: 0; font: inherit; font-size: 12px; padding: 7px 9px; border-radius: 8px; border: 1px solid var(--jb-line); background: var(--cream); color: var(--ink); }
#jobsOv .jb-verdict { margin: 16px 0; padding: 14px 16px; border-radius: 12px; border: 1px solid var(--jb-line); background: var(--jb-card); }
#jobsOv .jb-verdict .big { font-family: var(--serif); font-size: 30px; } #jobsOv .jb-verdict .GO { color: #1E9070; } #jobsOv .jb-verdict .NO-GO { color: #B5482F; } #jobsOv .jb-verdict .TEST { color: #B7791F; }
#jobsOv .jb-verdict ul { margin: 6px 0 0 18px; font-size: 12px; line-height: 1.6; } #jobsOv .jb-verdict a { color: inherit; }
#jobsOv .jb-inbox { border: 1px solid #F2B33D; background: #FFF8E6; color: #151414; border-radius: 12px; padding: 8px 10px 4px; margin-bottom: 10px; }
#jobsOv .jb-need { font-size: 12px; padding: 6px 0; border-top: 1px solid rgba(21,20,20,.08); cursor: pointer; } #jobsOv .jb-need b { display: block; font-weight: 600; } #jobsOv .jb-need span { color: #6b6257; }
#jobsOv .jb-empty { color: var(--grey); font-size: 13px; line-height: 1.6; padding: 30px 6px; }
@media (max-width: 900px) { #jobsOv .jb-body { grid-template-columns: 1fr; } #jobsOv .jb-stepper { grid-template-columns: repeat(4, 1fr); } }
`;

export function initJobs(ctx) {
  const { DEPTS, R, esc, chatPush, feedPush, setStuck, clearStuck, isLive, syncJobs } = ctx;
  const API = '/api/jobs';
  let jobs = [], inbox = [], sel = null, open = false, timer = null, pipe = null, showForm = false, detail = null, promo = null;
  const announced = new Set();   // "job|stage|attempt" gates already announced to a lead
  const wanted = new Map();      // stuck-sid -> agent id, for clearing when resolved elsewhere

  const style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
  const btn = document.createElement('button'); btn.id = 'topJobs'; btn.title = 'client jobs — the pipeline from intake to handoff (J)';
  btn.innerHTML = '⛓ JOBS<span class="n"></span>';
  const anchor = document.getElementById('topCal');
  if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(btn, anchor); else document.getElementById('topbar')?.appendChild(btn);
  const ov = document.createElement('div'); ov.id = 'jobsOv';
  ov.innerHTML = '<div class="jb-band"><div class="jb-brand">JOBS <small>ideas and client work · research to handoff</small></div><div class="jb-sp"></div><span style="font-size:10px;letter-spacing:.14em;opacity:.6">J · ESC</span><button id="jbClose" title="close (Esc · J)">✕</button></div><div class="jb-body"><div class="jb-list"><button class="jb-btn" id="jbNew">+ NEW JOB</button><form id="jbForm" hidden><select name="kind" id="jbKind"><option value="client">Client job — scope, build and preview it</option><option value="own">My idea — check the market first (web research)</option></select><input name="title" placeholder="Job title" required><input name="client" placeholder="Client"><input name="deposit_ref" placeholder="Deposit / contract reference (required)"><textarea name="description" rows="4" placeholder="What the client wants, in their words (20+ characters)"></textarea><textarea name="acceptance" rows="2" placeholder="What must be true when it is done"></textarea><input name="audience" placeholder="Who would pay for it (idea only)" hidden><input name="price" placeholder="Price you have in mind (idea only)" hidden><input name="links" placeholder="Links you already know: competitors, forum threads (optional)" hidden><select name="requestedTier"><option value="0">Preview stays PRIVATE (nobody outside sees it)</option><option value="1">Gated preview — a public link behind a login</option><option value="2">PUBLIC — open to anyone (always your decision)</option></select><button class="jb-btn" type="submit">START THE JOB</button><div id="jbErr" class="no"></div></form><div id="jbCards"></div></div><div class="jb-main"></div></div>';
  document.body.appendChild(ov);
  const $list = ov.querySelector('#jbCards'), $main = ov.querySelector('.jb-main');
  const $new = ov.querySelector('#jbNew'), $form = ov.querySelector('#jbForm');

  const deptInk = k => (DEPTS[k] && DEPTS[k].ink) || '#999';
  const nameOf = id => (R[id] && R[id].a.name) || id;
  const fmtLeft = ms => { const m = Math.round((ms - Date.now()) / 60000); return m < 0 ? 'overdue by ' + Math.abs(Math.round(m / 60)) + ' h' : m < 120 ? m + ' min left' : Math.round(m / 60) + ' h left'; };

  async function call(path, method = 'GET', body) {
    const r = await fetch(API + path, { method, headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  }

  /* ---------- polling and announcing ---------- */
  async function poll() {
    if (!isLive()) return;
    try { jobs = await call(''); } catch { return; }
    try { const r = await fetch('/api/inbox'); inbox = r.ok ? await r.json() : []; } catch { inbox = []; }
    if (sel && open) {
      try { detail = await call('/' + sel); } catch { detail = null; }
      promo = null;
      if (detail && detail.lane !== 'validate' && detail.status === 'done') { try { promo = await call(`/${sel}/promote`); } catch { promo = null; } }
      // the detail is fetched after the list, so it can be newer: use it for the list entry too, or the
      // banner could show a gate the lead has not been asked to wave at yet
      if (detail) { const k = jobs.findIndex(x => x.id === detail.id); if (k >= 0) jobs[k] = { ...jobs[k], ...detail, approvals: undefined, evidence: undefined }; }
    }
    if (syncJobs) syncJobs(jobs);
    announceGates(); render();
  }
  function announceGates() {
    const live = new Set();
    for (const j of jobs) {
      if (j.status !== 'waiting' || !j.pending[0] || !j.pending[0].needsOwner) continue;
      const stage = j.pending[0].stage, st = j.stages.find(s => s.name === stage); if (!st) continue;
      const sid = `job:${j.id}:${stage}`; live.add(sid);
      const key = `${j.id}|${stage}|${st.attempts}`;
      if (announced.has(key) || !R[st.lead]) continue;
      announced.add(key); wanted.set(sid, st.lead);
      const ask = (GATE_ASK[stage] || (jj => `"${jj.title}" waits for your decision at ${stage}.`))(j);
      chatPush(st.lead, { who: 'appr', text: ask, pending: true, live: true });
      feedPush(R[st.lead], '⏸', `Waiting for your OK: ${j.title} · ${stage}`);
      setStuck(st.lead, ask, sid);
    }
    for (const [sid, agent] of [...wanted]) if (!live.has(sid)) { wanted.delete(sid); clearStuck(agent, sid); }
    btn.querySelector('.n').textContent = inbox.length ? String(inbox.length) : '';
  }

  /* ---------- decisions ---------- */
  async function decide(jobId, stage, verdict, note) {
    try { await call(`/${jobId}/gates/${stage}`, 'POST', { verdict, note }); } catch (e) { alert(`Could not record it: ${e.message}`); }
    setTimeout(poll, 400);
  }
  // APPROVE / REJECT on the lead's chat card (main.resolveApproval calls this for sids that start with "job:")
  function resolveGate(agentId, sid, approved) {
    const [, jobId, stage] = String(sid).split(':');
    wanted.delete(sid);
    decide(jobId, stage, approved ? 'PASS' : 'FAIL', approved ? '' : 'rejected by the owner from the chat card');
    chatPush(agentId, { who: 'agent', text: approved ? '✓ Understood — carrying on.' : '✗ Understood — I have sent it back.' });
  }

  /* ---------- rendering ---------- */
  // Production is the owner's button. Prepare = the product's own repo + a production app (not deployed);
  // deploy = only after the owner has set the variables in Dokploy; the server then probes /healthz.
  function productionPanel(p) {
    const prod = p.production || {};
    const list = (p.checklist || []).map(i => `<li class="${i.ok ? 'ok' : 'no'}">${i.ok ? '✓' : '✕'} <span style="color:var(--ink);font-weight:400">${esc(i.name)}${i.detail ? ' — ' + esc(i.detail) : ''}</span></li>`).join('');
    let act = '';
    if (!p.ready) act = '<p style="font-size:12px">Not ready: every line above must be ✓.</p>';
    else if (!prod.state) act = `<div class="jb-row"><input id="jbDomain" placeholder="production domain, e.g. orders.acmebakery.com" style="flex:1;min-width:220px;padding:8px 10px;border-radius:8px;border:1px solid var(--jb-line);font:inherit"><button class="jb-btn" id="jbPrep">PREPARE PRODUCTION</button></div>`;
    else if (['prepared', 'unhealthy'].includes(prod.state)) act = `<p style="font-size:12px">Repo: ${esc(prod.repo || '')}<br>Set these in the Dokploy app before deploying: <b>${esc((prod.env || []).join(', ') || 'see the app README')}</b>. Point ${esc(prod.domain || '')} at the server.${prod.state === 'unhealthy' ? `<br><span class="no">Last deploy did not answer /healthz (status ${esc(String((prod.probe || {}).status))}).</span>` : ''}</p><div class="jb-row"><label><input type="checkbox" id="jbEnvOk"> the variables are set</label><button class="jb-btn" id="jbDeploy">DEPLOY TO PRODUCTION</button></div>`;
    else act = `<p style="font-size:12px">${prod.state === 'live' ? '● LIVE' : esc(prod.state)} · <a href="${esc(prod.url || '')}" target="_blank" rel="noopener noreferrer">${esc(prod.url || '')}</a></p>`;
    return `<h5>PRODUCTION · YOUR DECISION ONLY</h5><div class="jb-verdict jb-prod"><ul style="list-style:none;margin-left:0">${list}</ul>${act}</div>`;
  }
  // The validate lane's memo: the verdict is computed by the server from verified claims.
  function verdictCard(j, m) {
    const g = m.gates || {}, c = m.counts || {}, log = m.run_log || {};
    const claims = (m.claims || []).slice(0, 12).map(x => `<li><b>${esc(x.gate)}</b> ${esc(x.subject || '')}: “${esc(x.quote)}” <a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">source</a></li>`).join('');
    const next = j.status === 'done' ? `<div class="jb-row"><button class="jb-btn" data-build="landing">BUILD A LANDING-PAGE TEST</button><button class="jb-btn ghost" data-build="mvp">BUILD THE MVP</button></div>` : '';
    return `<div class="jb-verdict"><div class="jb-row"><span class="big ${esc(m.verdict)}">${esc(m.verdict || '?')}</span><span>confidence ${esc(m.confidence || '?')}</span><span>D1 competitors ${esc(g.D1)} · D2 pain ${esc(g.D2)} · A audience ${esc(g.A)}</span></div>
      <div class="jb-row"><span>${c.competitors || 0} competitors (${c.with_revenue || 0} earning)</span><span>${c.posts || 0} pain posts from ${c.communities || 0} places (${c.specific_posts || 0} specific)</span><span>${log.queries || 0} searches · ${log.fetched || 0} pages · ${log.claims_dropped || 0} unverifiable claims dropped</span></div>
      ${(m.reasons || []).length ? `<ul>${m.reasons.map(r => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}
      ${m.verdict === 'TEST' ? `<p style="font-size:12px;margin-top:8px"><b>Cheapest test:</b> ${esc(m.cheapest_test || '')}<br><b>Flips when:</b> ${esc(m.flip_condition || '')}</p>` : ''}
      ${claims ? `<ul>${claims}</ul>` : ''}${next}</div>`;
  }
  function stepBar(j) { return `<div class="jb-steps">${j.stages.map(s => `<i class="${s.state}" style="--c:${deptInk(s.dept)}" title="${esc(s.label)}: ${s.state}"></i>`).join('')}</div>`; }
  $new.onclick = () => { showForm = !showForm; $form.hidden = !showForm; $new.textContent = showForm ? '− CLOSE FORM' : '+ NEW JOB'; };
  const kindFields = () => {
    const own = $form.querySelector('#jbKind').value === 'own';
    for (const n of ['client', 'deposit_ref', 'acceptance', 'requestedTier']) $form.querySelector(`[name=${n}]`).hidden = own;
    for (const n of ['audience', 'price', 'links']) $form.querySelector(`[name=${n}]`).hidden = !own;
  };
  $form.querySelector('#jbKind').onchange = kindFields;
  $form.onsubmit = async e => {
    e.preventDefault(); const d = Object.fromEntries(new FormData($form).entries()); d.requestedTier = +d.requestedTier;
    if (d.kind === 'own') { delete d.deposit_ref; d.requestedTier = 0; }
    try { const j = await call('', 'POST', d); sel = j.id; $form.reset(); $new.onclick(); $form.querySelector('#jbErr').textContent = ''; await poll(); } catch (err) { $form.querySelector('#jbErr').textContent = err.message; }
  };
  const INBOX_MARK = { gate: '⏸', parked: '⚠', production: '▲', promote: '↑', memo: '✎' };
  function renderList() {
    const needs = inbox.length ? `<div class="jb-inbox"><h5 style="margin:4px 0 6px">NEEDS YOU · ${inbox.length}</h5>${inbox.map(i => `<div class="jb-need" data-id="${esc(i.jobId)}"><b>${INBOX_MARK[i.kind] || '•'} ${esc(i.title)}</b><span>${esc(i.text)}</span></div>`).join('')}</div>` : '';
    $list.innerHTML = needs + (jobs.length ? [...jobs].reverse().map(j => `<div class="jb-card${j.id === sel ? ' sel' : ''}" data-id="${j.id}"><h4>${esc(j.title)}</h4><span class="jb-badge ${j.status}">${STATUS_LABEL[j.status] || j.status}</span> <span class="jb-badge">${esc(j.stage.toUpperCase())}</span>${stepBar(j)}</div>`).join('') : '<div class="jb-empty">No jobs yet. Press <b>NEW JOB</b>: an idea of yours gets market research first; a client job needs the deposit or contract reference before anything is built.</div>');
    $list.querySelectorAll('.jb-need').forEach(c => c.onclick = () => { sel = c.dataset.id; lastSig = ''; poll(); });
    $list.querySelectorAll('.jb-card').forEach(c => c.onclick = () => { sel = c.dataset.id; lastSig = ''; poll(); });
  }
  function renderMain() {
    const j = detail || jobs.find(x => x.id === sel);
    if (!j) { $main.innerHTML = '<div class="jb-empty">Pick a job on the left to see where it stands: the eight stages, who has to approve what, the evidence behind every approval, and the cost so far.</div>'; return; }
    const tier = TIER[j.tier || 0], req = TIER[j.requestedTier || 0];
    const pend = j.pending && j.pending[0];
    const cost = j.costs ? `${(j.costs.tokens / 1000).toFixed(1)}k tokens · $${j.costs.usd.toFixed(3)}` : '';
    let banner = '';
    if (j.status === 'waiting' && pend && pend.needsOwner) {
      const ask = (GATE_ASK[pend.stage] || (jj => `Decision needed at ${pend.stage}.`))(j);
      banner = `<div class="jb-banner"><p><b>YOUR DECISION</b> · ${esc(pend.stage.toUpperCase())}<br>${esc(ask)}</p><div class="acts"><input id="jbNote" placeholder="note (optional, shown to the team if you reject)"><button class="jb-btn" id="jbYes">APPROVE</button><button class="jb-btn ghost" id="jbNo">REJECT</button></div></div>`;
    } else if (j.status === 'waiting') banner = `<div class="jb-banner"><p>Waiting for: ${esc((pend && pend.roles || []).join(', '))}</p></div>`;
    if (j.status === 'parked') banner = `<div class="jb-banner bad"><p><b>PARKED</b> · ${esc(j.parkReason || 'a stage could not finish')}</p><div class="acts"><input id="jbNote" placeholder="what should change? (optional)"><button class="jb-btn" id="jbRetry">RETRY THE STAGE</button></div></div>`;
    if (j.status === 'failed') banner = `<div class="jb-banner bad"><p><b>FAILED</b> · ${esc(j.parkReason || 'see the server log')}</p></div>`;
    const memo = (j.evidence || []).find(e => e.stage === 'research' && e.kind === 'memo');
    const verdict = memo ? verdictCard(j, memo.body || {}) : '';
    const stages = j.stages.map(s => `<div class="jb-stage ${s.state}" style="--c:${deptInk(s.dept)}"><b>${STATE_MARK[s.state] || '○'} ${esc(s.label)}</b><span>${s.live === false ? 'OWNER' : esc(nameOf(s.lead))}</span><span>${s.state}${s.attempts > 1 ? ' · try ' + s.attempts : ''}</span></div>`).join('');
    const appr = (j.approvals || []).map(a => `<tr><td>${esc(a.stage)}</td><td>${esc(a.role === 'owner' ? 'YOU' : nameOf(a.role))}</td><td class="${a.verdict === 'PASS' ? 'ok' : 'no'}">${a.verdict}</td><td>${esc(a.note || '')}</td><td>${(a.evidence || []).length} cited</td></tr>`).join('');
    const ev = (j.evidence || []).map(e => `<details><summary><span class="${e.ok === false ? 'no' : e.ok ? 'ok' : ''}">${e.ok === false ? '✕' : e.ok ? '✓' : '•'}</span> ${esc(e.stage)} · ${esc(e.title)}</summary><pre>${esc(JSON.stringify(e.body, null, 2))}</pre></details>`).join('');
    const ownerClicks = (j.approvals || []).filter(a => a.role === 'owner' && a.stage === 'exposure').length;
    $main.innerHTML = `<h3>${esc(j.title)}</h3>
      <div class="jb-row"><span class="jb-badge ${j.status}">${STATUS_LABEL[j.status] || j.status}</span><span class="jb-pill t${j.tier || 0}" title="${esc(tier[1])}">NOW ${tier[0]}</span><span class="jb-pill t${j.requestedTier || 0}" title="${esc(req[1])}">ASKED FOR ${req[0]}</span><span>${esc(cost)}</span><span>${j.status === 'done' || j.status === 'killed' ? '' : esc(fmtLeft(j.deadlineAt))}</span>${j.preview && j.preview.expiresAt && !j.preview.stopped ? `<span>preview expires ${esc(untilText(j.preview.expiresAt))}</span>` : ''}${j.preview && j.preview.url ? `<a href="${esc(j.preview.url)}" target="_blank" rel="noopener noreferrer">${esc(j.preview.url)}</a>` : ''}</div>
      ${banner}<div class="jb-stepper" style="--n:${j.stages.length}">${stages}</div>${verdict}
      ${j.requestedTier ? `<h5>EXPOSURE · THREE KEYS</h5><div class="jb-row"><span>security: <b>${esc(nameOf((pipe && pipe.exposure.keys.security) || ''))}</b></span><span>commercial: <b>${esc(nameOf((pipe && pipe.exposure.keys.commercial) || ''))}</b></span><span>you${j.requestedTier >= 2 ? ': always' : `: the first ${j.ownerClicksNeeded} gated previews (${ownerClicks} so far on this job)`}</span></div>` : ''}
      ${promo ? productionPanel(promo) : ''}
      <h5>DECISIONS</h5>${appr ? `<table><tr><th>STAGE</th><th>WHO</th><th>VERDICT</th><th>WHY</th><th>EVIDENCE</th></tr>${appr}</table>` : '<div class="jb-empty" style="padding:6px 0">None yet.</div>'}
      <h5>EVIDENCE</h5>${ev || '<div class="jb-empty" style="padding:6px 0">None yet.</div>'}
      <h5>WHAT HAPPENED</h5><div style="font-size:12px;line-height:1.7">${(j.events || []).slice().reverse().map(e => `${esc(new Date(e.at).toLocaleTimeString())} · ${esc(e.text)}`).join('<br>') || '—'}</div>
      ${['done', 'killed'].includes(j.status) ? '' : `<h5>KILL SWITCH</h5><button class="jb-btn warn" id="jbKill">STOP THE JOB AND TAKE THE PREVIEW DOWN</button>`}`;
    const note = () => ($main.querySelector('#jbNote') || {}).value || '';
    const q = s => $main.querySelector(s);
    if (q('#jbYes')) q('#jbYes').onclick = () => decide(j.id, pend.stage, 'PASS', note());
    if (q('#jbNo')) q('#jbNo').onclick = () => decide(j.id, pend.stage, 'FAIL', note() || 'rejected by the owner');
    if (q('#jbRetry')) q('#jbRetry').onclick = async () => { try { await call(`/${j.id}/retry`, 'POST', { note: note() }); } catch (e) { alert(e.message); } setTimeout(poll, 400); };
    $main.querySelectorAll('[data-build]').forEach(b => b.onclick = async () => {
      const landing = b.dataset.build === 'landing', br = j.brief || {};
      const desc = landing
        ? `A one-page landing site that tests demand for: ${br.description || j.title}. Show the offer and the price (${br.price || 'price to be set'}), and a waitlist / pre-order form that stores name and email. An admin page lists the sign-ups.`
        : (br.description || j.title);
      try { const nj = await call('', 'POST', { kind: 'own', lane: 'build', fromJob: j.id, title: (landing ? 'Landing test: ' : 'MVP: ') + j.title, description: desc, acceptance: landing ? 'A visitor can join the waitlist; the owner sees the sign-ups on /admin.' : '', deposit_ref: '' }); sel = nj.id; lastSig = ''; await poll(); } catch (e) { alert(e.message); }
    });
    const promote = async body => { try { await call(`/${j.id}/promote`, 'POST', body); } catch (e) { alert(e.message); } lastSig = ''; setTimeout(poll, 300); };
    if (q('#jbPrep')) q('#jbPrep').onclick = () => promote({ step: 'prepare', domain: (q('#jbDomain') || {}).value || '' });
    if (q('#jbDeploy')) q('#jbDeploy').onclick = () => { if (!q('#jbEnvOk').checked) { alert('Tick the box once the variables are set in Dokploy.'); return; } promote({ step: 'deploy', envConfirmed: true }); };
    if (q('#jbKill')) q('#jbKill').onclick = async () => { if (!confirm('Stop this job and take its preview down? This cannot be undone.')) return; try { await call(`/${j.id}/kill`, 'POST', {}); } catch (e) { alert(e.message); } setTimeout(poll, 400); };
  }
  // Re-render only when the data changed, and keep what the owner is doing: the note being typed
  // and the evidence entries they opened. (A poll every 6 s must never eat a half-written note.)
  let lastSig = '';
  // Live updates for the selected job: the server pushes (SSE); each push triggers one poll. The
  // 6 s timer stays as the fallback if the stream is unavailable.
  let es = null, esFor = '', esT = 0;
  function watch() {
    const want = open && sel && typeof EventSource !== 'undefined' ? sel : '';
    if (want === esFor) return;
    if (es) { es.close(); es = null; }
    esFor = want;
    if (!want) return;
    try {
      es = new EventSource(`${API}/${want}/stream`);
      es.onmessage = () => { clearTimeout(esT); esT = setTimeout(poll, 150); };
      es.onerror = () => { if (es && es.readyState === 2) { es = null; esFor = ''; } };
    } catch { es = null; esFor = ''; }
  }
  function render() {
    watch();
    if (!open) return;
    const sig = JSON.stringify([jobs, detail, sel, promo, inbox]);
    if (sig === lastSig) return;
    lastSig = sig;
    const keepNote = ($main.querySelector('#jbNote') || {}).value;
    const openKeys = [...$main.querySelectorAll('details[open] summary')].map(x => x.textContent);
    const scroll = $main.scrollTop;
    renderList(); renderMain();
    const n = $main.querySelector('#jbNote'); if (n && keepNote) n.value = keepNote;
    $main.querySelectorAll('details').forEach(d => { if (openKeys.includes(d.querySelector('summary').textContent)) d.open = true; });
    $main.scrollTop = scroll;
  }

  /* ---------- open / close ---------- */
  function openIt() { if (!isLive()) { alert('Jobs need the office server (docker compose + uvicorn). This page is the offline demo.'); return; } open = true; lastSig = ''; ov.classList.add('on'); document.body.classList.add('jobsOpen'); poll(); }
  function closeIt() { open = false; ov.classList.remove('on'); document.body.classList.remove('jobsOpen'); }
  btn.onclick = () => (open ? closeIt() : openIt());
  ov.querySelector('#jbClose').onclick = closeIt;
  // Escape closes the screen even while a field has focus (the page's own hotkeys ignore typing contexts)
  ov.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); closeIt(); } });

  return {
    start(health) { pipe = health && health.pipeline; if (timer) return; poll(); timer = setInterval(poll, 6000); },
    toggle: () => (open ? closeIt() : openIt()), close: closeIt, isOpen: () => open,
    resolveGate, owns: sid => String(sid || '').startsWith('job:'), jobs: () => jobs, poll,
  };
}
