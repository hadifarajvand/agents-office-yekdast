// Agents Office v4 — roster + design tokens (ported from v1 command-centre.html)
import { SEED_AGENTS } from './roster.gen.js';

// Nominal.so tokens (locked design language, 30 Jul 2026)
export const TOKENS = {
  cream: '#FDFFF8',
  ink: '#151414',
  grey: '#5A5A5A',
  hairline: 'rgba(21,20,20,0.12)',
};

// V4 (1 Oct 2026): full structural redesign — the office moved from a 6-pod go-to-market/ops
// shape to an 8-pod build-and-run shape that matches how a software company is actually staffed.
// Sales + Marketing merged into REVENUE. Operations split into EXEC (strategy/legal), ENGINEERING,
// FRONTEND, DEVOPS and SECDATA. Emails folded into CONTENT (comms). Finance (fin) kept its key and
// slimmed to 3 seats. Every former id was reassigned to a new seat rather than retired — see each
// agent's comment below for where it came from.
export const DEPT_KEYS = ['exec', 'revenue', 'engineering', 'frontend', 'devops', 'secdata', 'fin', 'content'];
export const DEPTS = {
  exec:        { name: 'STRATEGY & LEGAL',   short: 'STRATEGY',        chip: '#BFA2E3', ink: '#7449A9', floor: '#F2ECFA' },
  revenue:     { name: 'MARKET & SALES',                short: 'MARKET',     chip: '#F0B86E', ink: '#C47A1E', floor: '#FBEEDC' },
  engineering: { name: 'BACKEND BUILD',  short: 'BACKEND', chip: '#8FD3F4', ink: '#2E86AB', floor: '#E6F4FB' },
  frontend:    { name: 'PRODUCT & FRONTEND',      short: 'PRODUCT',    chip: '#5ADEB7', ink: '#1E9070', floor: '#E9F6EF' },
  devops:      { name: 'DEVOPS & QA',            short: 'DEVOPS',      chip: '#E69393', ink: '#C46060', floor: '#FAE9E7' },
  secdata:     { name: 'SECURITY & PRIVACY',        short: 'SECURITY',     chip: '#98A5EF', ink: '#5B66CE', floor: '#EAEDFA' },
  fin:         { name: 'FINANCE & PRICING',      short: 'FINANCE',     chip: '#EADC8F', ink: '#A08A1E', floor: '#F6F1DA' },
  content:     { name: 'CONTENT & SUPPORT',        short: 'CONTENT',     chip: '#B5E8A0', ink: '#5A9E3D', floor: '#EEF8E8' },
  brain:       { name: 'THE BRAIN',              short: 'THE BRAIN',   chip: '#D1DECD', ink: '#4C7A57', floor: '#E9EFE4' },
};

// Seats come from backend/app/seed/roster_seed.json via scripts/gen_roster.mjs (src/roster.gen.js): one source, no drift.
// grid = [col,row] desk slot on the department plinth, assigned below.
export const AGENTS = SEED_AGENTS.map(a => ({ ...a }));

// Up to 10 seats per department (owner, 3 Oct 2026). The named agents above are re-seated onto the
// first slots in order; the rest are FREE_SEATS: empty desks, drawn but unstaffed, with no id, no
// agent and nothing on the backend. Staffing one = moving an entry into AGENTS (and the seed).
export const SEATS_PER_DEPT = 10;
export const SEAT_SLOTS = [[0.5, 0], [0, 1], [1, 1], [0, 2], [1, 2], [0, 3], [1, 3], [0, 4], [1, 4], [0.5, 5]];
export const SEAT_ROWS = 6;
export const FREE_SEATS = [];
for (const k of DEPT_KEYS) {
  const mine = AGENTS.filter(a => a.dept === k);
  if (mine.length > SEATS_PER_DEPT) throw new Error(k + ' has more than ' + SEATS_PER_DEPT + ' seats');
  const ordered = [...mine.filter(a => a.lead), ...mine.filter(a => !a.lead)];
  ordered.forEach((a, i) => { a.grid = SEAT_SLOTS[i]; });
  for (let i = mine.length; i < SEATS_PER_DEPT; i++) FREE_SEATS.push({ dept: k, grid: SEAT_SLOTS[i] });
}

// Plinth placement in world XZ. Brain central; eight departments ringed around it, biggest (revenue)
// given the most room.
export const LAYOUT = {
  brain:       { pos: [0, 0],      w: 16, d: 16 },
  exec:        { pos: [0, -44],    w: 18, d: 40 },
  revenue:     { pos: [42, -34],   w: 26, d: 40 },
  engineering: { pos: [48, 12],    w: 22, d: 40 },
  frontend:    { pos: [26, 56],    w: 18, d: 40 },
  devops:      { pos: [-14, 58],   w: 20, d: 40 },
  secdata:     { pos: [-44, 38],   w: 18, d: 40 },
  fin:         { pos: [-50, -8],   w: 18, d: 40 },
  content:     { pos: [-28, -50],  w: 18, d: 40 },
};

// Department billboard metrics (v1 rule #5: live metrics float above each dept,
// values tick green on change, "Waiting Approval" pulses amber when > 0).
export const BILLBOARDS = {
  exec:        [{ id: 'initiatives', label: 'INITIATIVES TRACKED', val: 11 }],
  revenue:     [{ id: 'leads',     label: 'LEADS ENRICHED',   val: 47 },
                { id: 'adspend',   label: 'AD SPEND TODAY',   val: 684, fmt: v => '$' + Math.round(v).toLocaleString('en-NZ'), step: 12 }],
  engineering: [{ id: 'builds',    label: 'BUILDS SHIPPED',   val: 14 }],
  frontend:    [{ id: 'components', label: 'COMPONENTS SHIPPED', val: 22 }],
  devops:      [{ id: 'deploys',   label: 'DEPLOYS TODAY',    val: 6 }],
  secdata:     [{ id: 'checks',    label: 'COMPLIANCE CHECKS', val: 18 }],
  fin:         [{ id: 'invoices',  label: 'INVOICES ISSUED',  val: 23 }],
  content:     [{ id: 'emails',    label: 'EMAILS SENT',      val: 128 }],
  brain:       [{ id: 'notes',     label: 'NOTES INDEXED',    val: 1204, fmt: v => Math.round(v).toLocaleString('en-NZ') }],
};

// Approval asks (agent requests → AJ decides; v1 flavour).
// Per-agent first so the ask matches who's asking; dept pool is the fallback.
export const APPROVAL_ASKS = {
  exec:        ['Sign off the Q4 strategy checklist — 3 vendor renewals inside', 'Approve the amended MSA for Kea Logistics — 2 clauses flagged'],
  revenue:     ['Send re-engagement SMS to 214 cold leads', 'Launch 4 Meta ad variants — $120/day budget'],
  engineering: ['Ship the v4 API migration to prod — breaking change for 2 integrations', 'Merge the DB migration — 40-min downtime window needed'],
  frontend:    ['Ship the new onboarding flow — 3 screens, no A/B test yet', 'Release the design-system v2 to all surfaces'],
  devops:      ['Deploy hotfix to prod — bypasses the usual staging soak', 'Roll back the release — error rate spiked 4x after deploy'],
  secdata:     ['Grant the new vendor read access to the customer dataset', 'Rotate the leaked API key — 2 services need a redeploy'],
  fin:         ['Invoice #218 doesn’t match the contract — hold for review?', 'Write off $180 of unmatched card fees'],
  content:     ['Send the price-increase notice to 120 clients — draft attached', 'Publish the September status update to all clients'],
};
export const APPROVAL_BY_AGENT = {
  cmail: 'Send the price-increase notice to 120 clients — draft attached',
  vmail: 'Ship the hotfix release — skips the usual staging soak, 2 services affected',
  piper: 'Send the Ridgeline Property Group proposal — 12 seats, Growth plan',
  iggy:  'Publish reel “the 10am rule” to Instagram — script attached',
  vid:   'Ship the mobile app update — v2.3, 4 screens changed',
  ada:   'Scale “cold call anxiety” creative to $180/day — CPA $29',
  mlead: 'Release the design-system v2 to all surfaces — 6 components changed',
  'exec-ceo-strategist': 'Sign off the Q4 strategy checklist — 3 vendor renewals inside',
  newt:  'Send the August newsletter to 3,400 subscribers — draft v3 attached',
  scout: 'Green-light the CallForge comparison play — memo attached',
  enzo:  'Buy 500 FullEnrich credits — current batch runs out tomorrow',
  dash:  'Deploy the v4 API migration to prod — breaking change for 2 integrations',
  'sec-compliance': 'Rotate the leaked API key — 2 services need a redeploy',
  apay:  'Contractor invoice #218 is $350 over the contract rate — hold payment and query?',
};

// Fake terminal lines for the desk screens (per-dept flavour), matching v1's chat voice.
export const WORKLINES = {
  exec: [
    '▸ strategy memo: Q4 priorities drafted',
    '▸ MSA clause 7.2 flagged — liability cap',
    '▸ competitor scan: DialAxis pricing page',
    '▸ weekly board pack: 4/6 sections done',
  ],
  revenue: [
    '▸ enriching lead — Summit HVAC',
    '▸ meta ads: 4 variants → review',
    '▸ drafting reel hook v3 — "cold call maths"',
    '▸ 32 prospects verified · 91% valid',
    '▸ proposal PDF built — Ridgeline Group',
  ],
  engineering: [
    '▸ API v4 endpoint: /invoices shipped',
    '▸ DB migration dry-run: 0 errors',
    '▸ integration: Stripe webhook wired up',
    '▸ bug #412 fixed — race condition in queue',
  ],
  frontend: [
    '▸ component library: 2 new variants',
    '▸ mobile build: iOS TestFlight uploaded',
    '▸ onboarding flow: screen 3/4 wired',
  ],
  devops: [
    '▸ deploy: staging → prod, 0 rollbacks',
    '▸ smoke suite: 48/48 green',
    '▸ monitoring: latency alert cleared',
    '▸ release notes v4.2 drafted',
  ],
  secdata: [
    '▸ compliance check: SOC2 control 7 passed',
    '▸ dashboard: churn cohort refreshed',
    '▸ access review: 3 stale grants revoked',
  ],
  fin: [
    '▸ reconciling 14 payments · 2 flagged',
    '▸ invoice #218 vs contract — rate variance flagged',
    '▸ invoice issued — Summit HVAC $840',
    '▸ reminder 2/3 sent — Alpine Freight',
  ],
  content: [
    '▸ drafting reply — client scope question',
    '▸ newsletter block 2/5 written',
    '▸ 14 status updates triaged · 3 for AJ',
    '▸ contractor invoice query answered',
  ],
  brain: [
    '▸ indexing vault — 1,204 notes',
    '▸ answering INTEL query — churn cohort',
    '▸ meeting scheduled: enzo × tess',
  ],
};
