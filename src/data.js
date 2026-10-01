// Agents Office v4 — roster + design tokens (ported from v1 command-centre.html)

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
  exec:        { name: 'EXECUTIVE & STRATEGY',   short: 'EXEC',        chip: '#BFA2E3', ink: '#7449A9', floor: '#F2ECFA' },
  revenue:     { name: 'REVENUE',                short: 'REVENUE',     chip: '#F0B86E', ink: '#C47A1E', floor: '#FBEEDC' },
  engineering: { name: 'ENGINEERING & BACKEND',  short: 'ENGINEERING', chip: '#8FD3F4', ink: '#2E86AB', floor: '#E6F4FB' },
  frontend:    { name: 'FRONTEND & MOBILE',      short: 'FRONTEND',    chip: '#5ADEB7', ink: '#1E9070', floor: '#E9F6EF' },
  devops:      { name: 'DEVOPS & QA',            short: 'DEVOPS',      chip: '#E69393', ink: '#C46060', floor: '#FAE9E7' },
  secdata:     { name: 'SECURITY & DATA',        short: 'SECDATA',     chip: '#98A5EF', ink: '#5B66CE', floor: '#EAEDFA' },
  fin:         { name: 'FINANCE & BILLING',      short: 'FINANCE',     chip: '#EADC8F', ink: '#A08A1E', floor: '#F6F1DA' },
  content:     { name: 'CONTENT & COMMS',        short: 'CONTENT',     chip: '#B5E8A0', ink: '#5A9E3D', floor: '#EEF8E8' },
  brain:       { name: 'THE BRAIN',              short: 'THE BRAIN',   chip: '#D1DECD', ink: '#4C7A57', floor: '#E9EFE4' },
};

// 35 agents, 8 departments, every department has a lead (V4, 1 Oct 2026).
// grid = [col,row] desk slot on the department plinth.
export const AGENTS = [
  // EXECUTIVE & STRATEGY (3) — was OPERATIONS's lead + Intel + Legal Review
  { id: 'olead', name: 'EXEC LEAD',           dept: 'exec',        lead: true,  grid: [0.5, 0], hair: '#111111', skin: '#F0C9A0' },
  { id: 'scout', name: 'STRATEGY',            dept: 'exec',        grid: [0, 1], hair: '#101820', skin: '#B07850' },
  { id: 'legal', name: 'GENERAL COUNSEL',     dept: 'exec',        grid: [1, 1], hair: '#20242e', skin: '#F0C9A0' },
  // REVENUE (8) — merged Sales + Marketing; Sales Lead at the head
  { id: 'lexi',  name: 'REVENUE LEAD',        dept: 'revenue',     lead: true,  grid: [0.5, 0], hair: '#5a2d0c', skin: '#F0C9A0' },
  { id: 'enzo',  name: 'LEAD ENRICHER',       dept: 'revenue',     grid: [0, 1], hair: '#1c1c2e', skin: '#E0A878' },
  { id: 'ilm',   name: 'INBOUND LEADS MANAGER', dept: 'revenue',   grid: [1, 1], hair: '#26140a', skin: '#F5D5B0' },
  { id: 'pros',  name: 'PROSPECTOR',          dept: 'revenue',     grid: [0, 2], hair: '#2a1a0e', skin: '#E8B98E' },
  { id: 'piper', name: 'PROPOSAL GENERATOR',  dept: 'revenue',     grid: [1, 2], hair: '#2d1a0a', skin: '#F0C9A0' },
  { id: 'folo',  name: 'FOLLOW UPS',          dept: 'revenue',     grid: [0, 3], hair: '#171717', skin: '#F5D5B0' },
  { id: 'ada',   name: 'PPC MANAGER',         dept: 'revenue',     grid: [1, 3], hair: '#3d2814', skin: '#C68B59' },
  { id: 'iggy',  name: 'SOCIAL MEDIA',        dept: 'revenue',     grid: [0.5, 4], hair: '#552200', skin: '#E8B98E' },
  // ENGINEERING & BACKEND (6) — Delivery Lead retrained; former delivery crew became the build team
  { id: 'dlead', name: 'ENGINEERING LEAD',    dept: 'engineering', lead: true,  grid: [0.5, 0], hair: '#1f1f1f', skin: '#F0C9A0' },
  { id: 'pco',   name: 'SERVICE BUILDER',     dept: 'engineering', grid: [0, 1], hair: '#3d2814', skin: '#E8B98E' },
  { id: 'crep',  name: 'API DESIGNER',        dept: 'engineering', grid: [1, 1], hair: '#6b3410', skin: '#F5D5B0' },
  { id: 'cass',  name: 'DB MIGRATOR',         dept: 'engineering', grid: [0, 2], hair: '#141414', skin: '#D9A97E' },
  { id: 'dasst', name: 'INTEGRATIONS',        dept: 'engineering', grid: [1, 2], hair: '#552200', skin: '#F0C9A0' },
  { id: 'ona',   name: 'BUG FIXER',           dept: 'engineering', grid: [0.5, 3], hair: '#0d0d0d', skin: '#9C6B43' },
  // FRONTEND & MOBILE (4) — Marketing Lead retrained; the visual + build-facing crew
  { id: 'mlead', name: 'FRONTEND LEAD',       dept: 'frontend',    lead: true,  grid: [0.5, 0], hair: '#2a1a0e', skin: '#E0A878' },
  { id: 'gfx',   name: 'UI DESIGNER',         dept: 'frontend',    grid: [0, 1], hair: '#141414', skin: '#F0C9A0' },
  { id: 'vid',   name: 'MOBILE DEV',          dept: 'frontend',    grid: [1, 1], hair: '#1b1b24', skin: '#D9A97E' },
  { id: 'riley', name: 'WEB BUILDER',         dept: 'frontend',    grid: [0.5, 2], hair: '#8a4a1f', skin: '#F5D5B0' },
  // DEVOPS & QA (5) — QA Checker retrained as Devops Lead; the ship-it crew
  { id: 'qa',    name: 'DEVOPS LEAD',         dept: 'devops',      lead: true,  grid: [0.5, 0], hair: '#101820', skin: '#C68B59' },
  { id: 'dash',  name: 'CD DEPLOYER',         dept: 'devops',      grid: [0, 1], hair: '#0d0d0d', skin: '#9C6B43' },
  { id: 'report', name: 'SMOKE TESTER',       dept: 'devops',      grid: [1, 1], hair: '#2e2118', skin: '#E8B98E' },
  { id: 'imail', name: 'MONITORING ENGINEER', dept: 'devops',      grid: [0, 2], hair: '#111111', skin: '#C68B59' },
  { id: 'vmail', name: 'RELEASE MANAGER',     dept: 'devops',      grid: [1, 2], hair: '#7a3b12', skin: '#F5D5B0' },
  // SECURITY & DATA (3) — Compliance Checker leads; security + analytics
  { id: 'comply', name: 'SECDATA LEAD',       dept: 'secdata',     lead: true,  grid: [0.5, 0], hair: '#5a3a1a', skin: '#C68B59' },
  { id: 'recon', name: 'DATA ANALYST',        dept: 'secdata',     grid: [0, 1], hair: '#33221a', skin: '#E8B98E' },
  { id: 'kmail', name: 'DASHBOARD BUILDER',   dept: 'secdata',     grid: [1, 1], hair: '#4a2a10', skin: '#D89F70' },
  // FINANCE & BILLING (3) — the accounting team, slimmed; Accounting Lead at the head
  { id: 'alead', name: 'FINANCE LEAD',        dept: 'fin',         lead: true,  grid: [0.5, 0], hair: '#1f1f1f', skin: '#E0A878' },
  { id: 'invo',  name: 'INVOICING',           dept: 'fin',         grid: [0, 1], hair: '#4a2a10', skin: '#F5D5B0' },
  { id: 'apay',  name: 'ACCOUNTS PAYABLE',    dept: 'fin',         grid: [1, 1], hair: '#0a0a0a', skin: '#8A5A32' },
  // CONTENT & COMMS (3) — Emails Lead retrained; comms + newsletter
  { id: 'elead', name: 'CONTENT LEAD',        dept: 'content',     lead: true,  grid: [0.5, 0], hair: '#2b2b2b', skin: '#E8B98E' },
  { id: 'newt',  name: 'NEWSLETTER AGENT',    dept: 'content',     grid: [0, 1], hair: '#26140a', skin: '#D89F70' },
  { id: 'cmail', name: 'STATUS WRITER',       dept: 'content',     grid: [1, 1], hair: '#3b2b1d', skin: '#F0C9A0' },
];

// Plinth placement in world XZ. Brain central; eight departments ringed around it, biggest (revenue)
// given the most room.
export const LAYOUT = {
  brain:       { pos: [0, 0],      w: 16, d: 16 },
  exec:        { pos: [0, -42],    w: 16, d: 20 },
  revenue:     { pos: [40, -28],   w: 26, d: 32 },
  engineering: { pos: [46, 12],    w: 22, d: 28 },
  frontend:    { pos: [30, 48],    w: 18, d: 24 },
  devops:      { pos: [-12, 56],   w: 20, d: 26 },
  secdata:     { pos: [-42, 32],   w: 16, d: 20 },
  fin:         { pos: [-48, -10],  w: 16, d: 20 },
  content:     { pos: [-26, -46],  w: 16, d: 20 },
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
  olead: 'Sign off the Q4 strategy checklist — 3 vendor renewals inside',
  newt:  'Send the August newsletter to 3,400 subscribers — draft v3 attached',
  scout: 'Green-light the CallForge comparison play — memo attached',
  enzo:  'Buy 500 FullEnrich credits — current batch runs out tomorrow',
  dash:  'Deploy the v4 API migration to prod — breaking change for 2 integrations',
  comply: 'Rotate the leaked API key — 2 services need a redeploy',
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
