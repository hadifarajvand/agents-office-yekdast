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
#jobsOv .jb-stepper { display: grid; grid-template-columns: repeat(8, 1fr); gap: 8px; margin: 14px 0 20px; }
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
#jobsOv .jb-empty { color: var(--grey); font-size: 13px; line-height: 1.6; padding: 30px 6px; }
@media (max-width: 900px) { #jobsOv .jb-body { grid-template-columns: 1fr; } #jobsOv .jb-stepper { grid-template-columns: repeat(4, 1fr); } }
`;

export function initJobs(ctx) {
  const { DEPTS, R, esc, chatPush, feedPush, setStuck, clearStuck, isLive } = ctx;
  const API = '/api/jobs';
  let jobs = [], sel = null, open = false, timer = null, pipe = null, showForm = false, detail = null;
  const announced = new Set();   // "job|stage|attempt" gates already announced to a lead
  const wanted = new Map();      // stuck-sid -> agent id, for clearing when resolved elsewhere

  const style = document.createElement('style'); style.textContent = CSS; document.head.appendChild(style);
  const btn = document.createElement('button'); btn.id = 'topJobs'; btn.title = 'client jobs — the pipeline from intake to handoff (J)';
  btn.innerHTML = '⛓ JOBS<span class="n"></span>';
  const anchor = document.getElementById('topCal');
  if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(btn, anchor); else document.getElementById('topbar')?.appendChild(btn);
  const ov = document.createElement('div'); ov.id = 'jobsOv';
  ov.innerHTML = '<div class="jb-band"><div class="jb-brand">JOBS <small>client work · intake to handoff</small></div><div class="jb-sp"></div><span style="font-size:10px;letter-spacing:.14em;opacity:.6">J · ESC</span><button id="jbClose" title="close (Esc · J)">✕</button></div><div class="jb-body"><div class="jb-list"><button class="jb-btn" id="jbNew">+ NEW CLIENT JOB</button><form id="jbForm" hidden><input name="title" placeholder="Job title" required><input name="client" placeholder="Client"><input name="deposit_ref" placeholder="Deposit / contract reference (required)"><textarea name="description" rows="4" placeholder="What the client wants, in their words (20+ characters)"></textarea><textarea name="acceptance" rows="2" placeholder="What must be true when it is done"></textarea><select name="requestedTier"><option value="0">Preview stays PRIVATE (nobody outside sees it)</option><option value="1">Gated preview — a public link behind a login</option><option value="2">PUBLIC — open to anyone (always your decision)</option></select><button class="jb-btn" type="submit">START THE JOB</button><div id="jbErr" class="no"></div></form><div id="jbCards"></div></div><div class="jb-main"></div></div>';
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
    if (sel && open) { try { detail = await call('/' + sel); } catch { detail = null; } }
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
    const waiting = jobs.filter(j => j.status === 'waiting' && j.pending[0] && j.pending[0].needsOwner).length;
    btn.querySelector('.n').textContent = waiting ? String(waiting) : '';
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
  function stepBar(j) { return `<div class="jb-steps">${j.stages.map(s => `<i class="${s.state}" style="--c:${deptInk(s.dept)}" title="${esc(s.label)}: ${s.state}"></i>`).join('')}</div>`; }
  $new.onclick = () => { showForm = !showForm; $form.hidden = !showForm; $new.textContent = showForm ? '− CLOSE FORM' : '+ NEW CLIENT JOB'; };
  $form.onsubmit = async e => {
    e.preventDefault(); const d = Object.fromEntries(new FormData($form).entries()); d.requestedTier = +d.requestedTier;
    try { const j = await call('', 'POST', d); sel = j.id; $form.reset(); $new.onclick(); $form.querySelector('#jbErr').textContent = ''; await poll(); } catch (err) { $form.querySelector('#jbErr').textContent = err.message; }
  };
  function renderList() {
    $list.innerHTML = jobs.length ? [...jobs].reverse().map(j => `<div class="jb-card${j.id === sel ? ' sel' : ''}" data-id="${j.id}"><h4>${esc(j.title)}</h4><span class="jb-badge ${j.status}">${STATUS_LABEL[j.status] || j.status}</span> <span class="jb-badge">${esc(j.stage.toUpperCase())}</span>${stepBar(j)}</div>`).join('') : '<div class="jb-empty">No jobs yet. A client job starts when you press <b>NEW CLIENT JOB</b> and give it the deposit or contract reference. Nothing is built before that.</div>';
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
    const stages = j.stages.map(s => `<div class="jb-stage ${s.state}" style="--c:${deptInk(s.dept)}"><b>${STATE_MARK[s.state] || '○'} ${esc(s.label)}</b><span>${esc(nameOf(s.lead))}</span><span>${s.state}${s.attempts > 1 ? ' · try ' + s.attempts : ''}</span></div>`).join('');
    const appr = (j.approvals || []).map(a => `<tr><td>${esc(a.stage)}</td><td>${esc(a.role === 'owner' ? 'YOU' : nameOf(a.role))}</td><td class="${a.verdict === 'PASS' ? 'ok' : 'no'}">${a.verdict}</td><td>${esc(a.note || '')}</td><td>${(a.evidence || []).length} cited</td></tr>`).join('');
    const ev = (j.evidence || []).map(e => `<details><summary><span class="${e.ok === false ? 'no' : e.ok ? 'ok' : ''}">${e.ok === false ? '✕' : e.ok ? '✓' : '•'}</span> ${esc(e.stage)} · ${esc(e.title)}</summary><pre>${esc(JSON.stringify(e.body, null, 2))}</pre></details>`).join('');
    const ownerClicks = (j.approvals || []).filter(a => a.role === 'owner' && a.stage === 'exposure').length;
    $main.innerHTML = `<h3>${esc(j.title)}</h3>
      <div class="jb-row"><span class="jb-badge ${j.status}">${STATUS_LABEL[j.status] || j.status}</span><span class="jb-pill t${j.tier || 0}" title="${esc(tier[1])}">NOW ${tier[0]}</span><span class="jb-pill t${j.requestedTier || 0}" title="${esc(req[1])}">ASKED FOR ${req[0]}</span><span>${esc(cost)}</span><span>${j.status === 'done' || j.status === 'killed' ? '' : esc(fmtLeft(j.deadlineAt))}</span>${j.preview && j.preview.expiresAt && !j.preview.stopped ? `<span>preview expires ${esc(untilText(j.preview.expiresAt))}</span>` : ''}${j.preview && j.preview.url ? `<a href="${esc(j.preview.url)}" target="_blank" rel="noopener noreferrer">${esc(j.preview.url)}</a>` : ''}</div>
      ${banner}<div class="jb-stepper">${stages}</div>
      ${j.requestedTier ? `<h5>EXPOSURE · THREE KEYS</h5><div class="jb-row"><span>security: <b>${esc(nameOf((pipe && pipe.exposure.keys.security) || ''))}</b></span><span>commercial: <b>${esc(nameOf((pipe && pipe.exposure.keys.commercial) || ''))}</b></span><span>you${j.requestedTier >= 2 ? ': always' : `: the first ${j.ownerClicksNeeded} gated previews (${ownerClicks} so far on this job)`}</span></div>` : ''}
      <h5>DECISIONS</h5>${appr ? `<table><tr><th>STAGE</th><th>WHO</th><th>VERDICT</th><th>WHY</th><th>EVIDENCE</th></tr>${appr}</table>` : '<div class="jb-empty" style="padding:6px 0">None yet.</div>'}
      <h5>EVIDENCE</h5>${ev || '<div class="jb-empty" style="padding:6px 0">None yet.</div>'}
      <h5>WHAT HAPPENED</h5><div style="font-size:12px;line-height:1.7">${(j.events || []).slice().reverse().map(e => `${esc(new Date(e.at).toLocaleTimeString())} · ${esc(e.text)}`).join('<br>') || '—'}</div>
      ${['done', 'killed'].includes(j.status) ? '' : `<h5>KILL SWITCH</h5><button class="jb-btn warn" id="jbKill">STOP THE JOB AND TAKE THE PREVIEW DOWN</button>`}`;
    const note = () => ($main.querySelector('#jbNote') || {}).value || '';
    const q = s => $main.querySelector(s);
    if (q('#jbYes')) q('#jbYes').onclick = () => decide(j.id, pend.stage, 'PASS', note());
    if (q('#jbNo')) q('#jbNo').onclick = () => decide(j.id, pend.stage, 'FAIL', note() || 'rejected by the owner');
    if (q('#jbRetry')) q('#jbRetry').onclick = async () => { try { await call(`/${j.id}/retry`, 'POST', { note: note() }); } catch (e) { alert(e.message); } setTimeout(poll, 400); };
    if (q('#jbKill')) q('#jbKill').onclick = async () => { if (!confirm('Stop this job and take its preview down? This cannot be undone.')) return; try { await call(`/${j.id}/kill`, 'POST', {}); } catch (e) { alert(e.message); } setTimeout(poll, 400); };
  }
  // Re-render only when the data changed, and keep what the owner is doing: the note being typed
  // and the evidence entries they opened. (A poll every 6 s must never eat a half-written note.)
  let lastSig = '';
  function render() {
    if (!open) return;
    const sig = JSON.stringify([jobs, detail, sel]);
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

  return {
    start(health) { pipe = health && health.pipeline; if (timer) return; poll(); timer = setInterval(poll, 6000); },
    toggle: () => (open ? closeIt() : openIt()), close: closeIt, isOpen: () => open,
    resolveGate, owns: sid => String(sid || '').startsWith('job:'), jobs: () => jobs, poll,
  };
}
