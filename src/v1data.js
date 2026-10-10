// v1 data extracted VERBATIM from command-centre.html (lines 646-666, 671-1095, 2176, 2975-3021).
// Do not hand-edit agent content here — it is the single source of truth shared with v1.
export const clockStr = () => new Date().toLocaleTimeString("en-NZ",{hour:"2-digit",minute:"2-digit",hour12:false});
export const slug = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g,"-");
export const P = {
  first:['Sarah','Mike','Priya','Tom','Aroha','Ben','Chloe','Dev','Emma','Finn','Grace','Hemi','Isla','Jake','Kiri','Liam','Mia','Nikau','Olivia','Pete','Ruby','Sam','Tane','Zoe','Harper','Josh','Nina','Ravi','Sofia','Callum'],
  last:['Walker','Patel','Thompson','Ngata','Chen','Murphy','Kaur','Wilson','Fraser','Hohepa','Brooks','Sharma','Reid','Tui','Marsh','Oduya','King','Parata','Lowe','Baxter'],
  co:['Harbour City Roofing','Southern Cross Fitness','Kea Logistics','Fern & Field Landscaping','Ridgeline Property Group','BlueWater Marine','Totara Legal','Summit HVAC','GoldCoast Solar','Pounamu Recruitment','Marlborough Wines Direct','UrbanNest Realty','Silver Fern Security','Bay Plumbing Co','Crestline Finance','Mako Digital','Kauri Dental Group','Westhaven Charters','Alpine Freight','Nectar Foods'],
  plan:['Starter','Growth','Scale','Enterprise'],
  competitor:['CallForge','RingPilot','Quotient CRM','DialAxis','Velora'],
  city:['Auckland','Wellington','Christchurch','Sydney','Melbourne','Brisbane','Hamilton','Tauranga','Perth','Dunedin'],
};
export const rnd = a => a[Math.floor(Math.random()*a.length)];
export const ri = (a,b) => a + Math.floor(Math.random()*(b-a+1));
export const person = () => rnd(P.first)+' '+rnd(P.last);
export const money = n => '$'+n.toLocaleString('en-NZ');
/* ---------- KPIs ---------- */
export const KPIS = [
  { id:'leads',     label:'Leads Enriched',  val:47,   fmt:v=>v },
  { id:'callhrs',   label:'Call Hrs Routed', val:9.5,  fmt:v=>v.toFixed(1)+'h' },
  { id:'tickets',   label:'Tickets Resolved',val:31,   fmt:v=>v },
  { id:'adspend',   label:'Ad Spend Today',  val:684,  fmt:v=>money(Math.round(v)) },
  { id:'proposals', label:'Proposals Sent',  val:6,    fmt:v=>v },
  { id:'invoices',  label:'Invoices Issued', val:23,  fmt:v=>v },
];
export const V1 = [
/* ============ SALES ============ */
{ id:'enzo', name:'LEAD ENRICHER', dept:'sales', desk:[17,3], sit:[17,4], hair:'#1c1c2e', shirt:'#fbbf24',
  role:'Lead Enrichment Agent',
  tagline:'Enriches every signup via FullEnrich — role, company size, mobile, LinkedIn.',
  tasks:['Enriching {count} overnight signups via FullEnrich','Verifying mobile numbers for the AU batch','Backfilling company size on 12 older leads','Re-running 3 failed enrichments','Scoring the morning batch for the Sales Lead'],
  ev:[
    {i:'🔍', t:()=>`Enriched ${person()} @ ${rnd(P.co)} via FullEnrich — ${rnd(['Sales Manager','Head of Sales','Director','Founder','Ops Manager','GM'])}, ${ri(5,120)} staff, mobile verified ✓`, kpi:{id:'leads',n:1}, p:4},
    {i:'📦', t:()=>`Batch complete: ${ri(6,14)} signups enriched, ${ri(85,97)}% match rate, handed to SALES LEAD for distribution`, kpi:{id:'leads',n:3}, p:2},
    {i:'⚠', t:()=>`FullEnrich low-confidence match on ${rnd(P.co)} — held back for manual check rather than guessing`, p:1},
    {i:'📚', t:()=>`Updated "Lead Scoring Rules" in the Brain — added company-size weighting`, brain:true, p:1},
  ],
  stats:[['Enriched today',()=>ri(40,60)],['Match rate','93%'],['Avg fields filled','11 / 14'],['Held for review','3']],
  chartLbl:'Leads enriched — last 7 days', chart:[52,61,48,67,55,23,47],
  greeting:`G'day AJ. Overnight batch done: 47 signups enriched through FullEnrich at a 93% match rate. Every lead now has role, company size, verified mobile and LinkedIn before the Sales Lead touches it. 3 low-confidence matches held for review — I don't guess.`,
  chat:[
    {k:['fullenrich','enrich','how do you'], r:[`Pipeline: new signup lands → I hit FullEnrich for role, company, headcount, verified mobile, LinkedIn → I score it (title seniority + company size + industry fit) → tag it → hand to the Sales Lead. Whole thing takes under 90 seconds per lead. Anything below 80% match confidence gets held for manual review instead of polluting the pipeline.`]},
    {k:['match','rate','quality','accuracy'], r:[`Match rate this week: 93%. Mobile verification is the star — 89% of enriched leads have a verified mobile, which is what makes the Onboarder's SMS onboarding and the sales team's call lists actually work. The 7% misses are mostly personal-email signups with no digital footprint.`]},
    {k:['held','review','fail','low'], r:[`3 leads held today: two signed up with gmail addresses and FullEnrich couldn't confidently match a company; one matched two different "Sam Reid"s in Auckland. I'd rather hold than send Spencer a wrong number. Want me to list them so you can eyeball?`]},
    {k:['score','scoring'], r:[`Scoring: seniority (manager+ = high) 40%, company size 5–200 sweet spot 30%, industry fit 20%, AU/NZ timezone 10%. Managers and above route toward Spencer per the Sales Lead's rules. I re-tuned size weighting last week after Intel found our best-closing segment is 10–50 seats.`]},
  ],
  fallback:[`I'm the reason no lead reaches a salesperson half-blank. Ask about my match rate, held leads, or how scoring works.`,`Try "what's your match rate?", "any leads held back?" or "how does scoring work?"`],
  chips:['What’s your match rate?','Any leads held back?','How does scoring work?'] },

{ id:'lexi', name:'SALES LEAD', dept:'sales', desk:[20,3], sit:[20,4], hair:'#5a2d0c', shirt:'#f59e0b', lead:true,
  role:'Revenue Lead Agent',
  tagline:'Runs the Revenue pod: pipeline, campaigns and the forecast.',
  tasks:['Reviewing the team’s overnight output before it reaches the reps','Building today’s call lists for Spencer, Arwin & Jack','Checking connect rates by rep and time-slot','Chasing {count} deals sitting quiet past 14 days','Prepping the weekly pipeline review for AJ','Tightening the ICP with Prospector after 3 weak batches'],
  ev:[
    {i:'🧭', t:()=>`Team review: ${ri(28,47)} leads enriched, ${ri(20,40)} prospects sourced, ${ri(18,34)} in first-touch sequence, ${ri(7,14)} quiet deals in chase — ${rnd(['all clean','1 batch sent back for re-scoring','2 duplicates pulled before they hit a list'])}`, p:3},
    {i:'📞', t:()=>`Built ARWIN's list — ${ri(4,9)} leads, ${(ri(10,18)/10).toFixed(1)}h of calling queued (${(ri(30,58)/10).toFixed(1)}h / 6h daily target)`, kpi:{id:'callhrs',n:0.8}, p:3},
    {i:'👔', t:()=>`${ri(2,5)} manager-level leads to SPENCER — ${rnd(['Head of Sales','Sales Manager','GM','Director'])} @ ${rnd(P.co)} at the top`, kpi:{id:'callhrs',n:0.5}, p:2},
    {i:'🎯', t:()=>`Pipeline: ${ri(3,7)} deals moved to ${rnd(['proposal','trial','negotiation'])}, ${ri(1,3)} ${rnd(['closed won','stalled — reassigned','pushed to next week'])}`, p:2},
    {i:'🎓', t:()=>`Coached PROSPECTOR — ${rnd(['tightened the ICP to 5–200 staff','killed the sub-5-staff searches','added the “no competitor employees” rule'])}; next batch should score higher`, brain:true, p:1},
    {i:'⚖', t:()=>`Rebalanced: moved ${ri(2,6)} leads ${rnd(['Arwin→Jack','Jack→Arwin','overflow→tomorrow'])} to keep queues on target`, p:1},
  ],
  stats:[['Agents reporting','5'],['Reps covered','3'],['Call hrs queued','11.3h / 12h'],['Trial→paid (7d)','31%']],
  chartLbl:'Call-hours queued to reps — last 7 days', chart:[11,12,10,12,11,4,9],
  greeting:`Hey AJ. Sales is running. My five agents delivered overnight — 47 leads enriched, 41 prospects sourced, 214 prospects in first-touch sequence, 11 onboarding threads live and 9 quiet deals under chase — and I've checked their output before any of it reached a rep. Today's lists: Spencer 2.8h of manager-level leads, Arwin 5.6h of his 6, Jack 2.9h of his 3. Ask me about the team, the reps, or the pipeline.`,
  chat:[
    {k:['team','agents','report','who','manage'], r:[`Five agents report to me. INBOUND LEADS ENRICHER takes every signup and returns role, company size, verified mobile and LinkedIn — 93% match rate. PROSPECTOR sources outbound against the ICP — 41 last night, dupes and existing customers stripped. OUTREACH warms every one of those with email and SMS before a rep dials — 214 in sequence, 23 warm handoffs this week. ONBOARDER opens a text thread the moment Free Trial flags a high-usage trialist — 78% reply. FOLLOW UPS owns everything that went quiet — 9 deals in chase, 18% of them come back. I review all five before their output reaches a human rep, and I send batches back when the scoring looks soft. Last week that was two batches.`]},
    {k:['spencer'], r:[`Spencer: 2.8h queued of his 3h target — 14 leads, all manager-level or above (my rule for him: title seniority ≥ manager). Top of his list: Head of Sales at Ridgeline Property Group, 40 staff, signed up yesterday 4pm, opened the pricing page twice this morning. That's a call-now lead.`]},
    {k:['arwin'], r:[`Arwin: 5.6h of 6h queued, 31 leads. His list is the volume engine — solid mid-score leads, freshest first. He's connecting at 24% this week, best in the 10am–12pm slot, so I front-load his mornings with the highest scores.`]},
    {k:['jack'], r:[`Jack: 2.9h of his 3h, 16 leads. He gets the same profile as Arwin at lower volume. His connect rate jumped since I stopped giving him leads older than 5 days — freshness beat volume, so I changed the rule for everyone.`]},
    {k:['pipeline','deal','forecast','close','revenue'], r:[`Pipeline right now: 34 live opportunities. 12 in trial, 9 at proposal, 5 in negotiation, 8 quiet past 14 days — those sit with FOLLOW UPS, and I've reassigned 3 of them off Arwin's list because volume calling isn't what they need. Trial→paid is 31% over 7 days. The number I actually watch is call-hours queued: 11.3h against a 12h target. When that dips, everything downstream dips a week later.`]},
    {k:['rule','how do you','route','distribut','logic','list'], r:[`How the lists get built: (1) manager+ titles → Spencer, capped at 3h/day. (2) Everything else split Arwin 6h : Jack 3h by score, freshest first. (3) Nothing older than 5 days without a re-touch. (4) If someone clears their queue, I rebalance from overflow within 15 min. Rules live in the Brain — change them there and I follow instantly, and so does every agent under me.`]},
    {k:['coach','quality','qa','improve','weak'], r:[`Coaching is the half of this job that isn't lists. This week: Prospector's ICP was pulling sub-5-staff businesses that never convert, so I tightened it to 5–200 and the next batch scored 22% higher. Enricher had 3 failed enrichments sitting untouched — now it re-runs them automatically. Onboarder's first text was landing at 40 minutes; it's at 10 now. Outreach was reusing one opener across every trade, so I split it by industry and replies went from 6% to 9.4%. Each fix goes into the Brain so it sticks.`]},
    {k:['hot','best','top'], r:[`Hottest lead right now: Head of Sales @ Ridgeline Property Group — enriched with verified mobile, 40 staff, visited pricing twice today. Top of Spencer's list. Second: founder at Mako Digital who logged 3 test calls in their trial already. If they haven't been called by 2pm I'll ping Spencer myself.`]},
  ],
  fallback:[`I run the sales team — three agents under me, three reps in front of me. Ask about the team, Spencer/Arwin/Jack's lists, or the pipeline.`,`Try "how's the team doing?", "what's in the pipeline?" or "how's Spencer's list?"`],
  chips:['How’s the team doing?','What’s in the pipeline?','How’s Spencer’s list?'] },

/* ============ MARKETING ============ */
{ id:'riley', name:'RESEARCH', dept:'marketing', desk:[4,12], sit:[4,13], hair:'#8a4a1f', shirt:'#f472b6',
  role:'Web Builder Agent',
  tagline:'Builds and maintains the web app surfaces.',
  tasks:['Compiling this morning’s industry scan','Summarising a competitor pricing change','Reading {count} newsletters so you don’t have to','Updating the Competitors folder in the Brain','Flagging a trend worth a LinkedIn post'],
  ev:[
    {i:'📰', t:()=>`Morning scan done: ${ri(30,60)} sources read, 3 items worth your time — briefing in the Brain`, brain:true, p:3},
    {i:'🕵', t:()=>`${rnd(P.competitor)} ${rnd(['raised prices 8%','launched an AI call-summary feature','changed their free trial to 7 days','is hiring 4 AU sales reps','dropped their annual discount'])} — logged & flagged to Intel`, p:2},
    {i:'📈', t:()=>`Trend: ${rnd(['"AI SDR" searches up again this month','voicemail drop regs tightening in AU','LinkedIn outbound fatigue rising — SMS interest up','video prospecting cooling off'])}`, p:2},
    {i:'📚', t:()=>`Updated "Industry Landscape" in the Brain — ${ri(2,5)} new entries`, brain:true, p:1},
  ],
  stats:[['Sources scanned today','47'],['Items flagged','3'],['Competitor moves (7d)','5'],['Briefings this month','21']],
  chartLbl:'Items flagged — last 7 days', chart:[4,2,3,5,3,1,3],
  greeting:`Morning AJ. Today's 6am scan: 47 sources, 3 things worth your attention — CallForge raised prices 8%, "AI SDR" search volume is climbing again, and there's a new AU ruling on voicemail drops. Full briefing is in the Brain under Research → Daily Briefings.`,
  chat:[
    {k:['today','briefing','scan','news','what'], r:[`Today's top 3:\n\n1. CallForge raised prices 8% across all plans — their customers are grumbling on LinkedIn. Window for a comparison campaign.\n2. "AI SDR" search volume up 22% month-on-month. Our messaging doesn't use that phrase anywhere — maybe it should.\n3. New AU telecom guidance on voicemail drops — doesn't affect us today, but Intel is assessing.\n\nFull briefing with links: Brain → Research → Daily Briefings.`]},
    {k:['competitor','callforge','ringpilot','quotient'], r:[`Competitor moves this week: CallForge +8% pricing, RingPilot launched AI call summaries (reviews say it's rough), Quotient CRM is hiring 4 AU reps — they're coming for our patch. Everything's logged in the Brain's Competitors folder with sources. Intel turns these into "so what" recommendations; I just make sure nothing gets missed.`]},
    {k:['trend','industry','market'], r:[`Biggest trend I'm tracking: buyers going cold on LinkedIn outbound while SMS-first outreach engagement climbs. Second: "AI SDR" as a category label is winning the naming war. Third: consolidation — two mid-size dialler tools acquired in the last quarter. Each has a note in the Brain with my confidence level and sources.`]},
    {k:['source','where','read'], r:[`My daily route: competitor changelogs and pricing pages (checked programmatically), 6 industry newsletters, LinkedIn posts from 40 tracked voices, G2 review feeds on 5 competitors, and AU/NZ telecom regulator updates. ~47 sources, 20 minutes, every morning at 6. You read 3 bullets instead.`]},
  ],
  fallback:[`I read everything so you read 3 bullets. Ask me for today's briefing, competitor moves, or the trends I'm tracking.`,`Try "what's in today's briefing?", "any competitor moves?" or "what trends are you watching?"`],
  chips:['Today’s briefing?','Competitor moves?','Trends you’re watching?'] },

{ id:'newt', name:'NEWSLETTER', dept:'marketing', desk:[7,12], sit:[7,13], hair:'#26140a', shirt:'#ec4899',
  role:'Newsletter Agent',
  tagline:'Writes and sends the newsletter signups actually open.',
  tasks:['Drafting the August issue — "The 10am Rule"','Pulling last month’s open-rate report','Rewriting the subject line 6 ways','Sourcing a customer win for the lead story','Waiting on AJ’s approval for the draft'],
  ev:[
    {i:'✍', t:()=>`August draft progressing — lead story: "${rnd(['The 10am Rule: when connect rates double','Why your best rep’s script won’t scale','3 signups tell us why they switched'])}"`, p:3},
    {i:'📊', t:()=>`July issue final numbers: ${ri(38,46)}% open, ${ri(4,8)}% click — best performer: the customer-story section`, p:2},
    {i:'🧪', t:()=>`Subject line A/B shortlist ready — 2 finalists in your approvals queue soon`, p:1},
    {i:'📚', t:()=>`Pulled 3 customer wins from support threads (thanks Tech Support) for the social-proof block`, brain:true, p:1},
  ],
  stats:[['July open rate','43%'],['July click rate','6.1%'],['Subscribers',()=>ri(2100,2400)],['Unsubs last issue','4']],
  chartLbl:'Open rate % — last 6 issues', chart:[31,34,38,36,41,43],
  greeting:`Hey AJ. August issue is 80% drafted — lead story is "The 10am Rule" (why connect rates double mid-morning, with our own anonymised data). July hit 43% opens, best yet. Draft will land in your approvals queue today; nothing ships without you.`,
  chat:[
    {k:['draft','august','issue','next'], r:[`August issue structure:\n\n1. Lead: "The 10am Rule" — our data shows connect rates nearly double between 10–11.30am. Actionable, no fluff.\n2. Customer story: an Auckland roofing company that went from 0 to 40 tracked calls/week.\n3. One tool tip: the pinned-list trick most users miss.\n4. Industry snippet from Research's research.\n\nOne CTA at the end, soft. Draft hits your approvals queue today.`]},
    {k:['open','click','number','perform','stat'], r:[`July: 43% open (list avg for SaaS is ~28%), 6.1% click, 4 unsubs from 2,260 sends. What's working: subject lines that sound like a text from a mate, and leading with the customer story. What flopped historically: anything with "newsletter" in the subject line. Never again.`]},
    {k:['subject','headline'], r:[`Current A/B finalists for August:\n\nA: "calls before 10am are a trap"\nB: "we looked at 40,000 calls — call at this time"\n\nA is punchier, B has curiosity + proof. My data says B wins opens by ~3 points but A gets better replies. Your call — they'll be in the approvals queue.`]},
    {k:['approve','when','send','ship'], r:[`Timeline: draft in your approvals queue today, your edits back whenever suits, final send Tuesday 10am NZT (best send-slot from the last 6 issues). I never send without your explicit approval — that's a hard rule, not a setting.`]},
  ],
  fallback:[`I write the monthly newsletter — and nothing sends without your sign-off. Ask about the August draft, July's numbers, or the subject-line A/B.`,`Try "what's in the next issue?", "how did July perform?" or "show me the subject lines".`],
  chips:['What’s in the next issue?','How did July perform?','Show me subject lines'] },

{ id:'gfx', name:'GRAPHICS DESIGNER', dept:'marketing', desk:[1,15], sit:[1,16], hair:'#0e0e16', shirt:'#f0abfc',
  role:'UI Designer Agent',
  tagline:'Designs UI components and visual assets.',
  tasks:['Designing the 10am Rule carousel for Instagram Organic','Producing 3 ad variants for Meta Ads','Refreshing the proposal cover template','Exporting webinar slide backgrounds','Building a quote-card set from customer wins'],
  ev:[
    {i:'🎨', t:()=>`Delivered ${rnd(['a 6-slide carousel','3 ad creative variants','a quote-card set','proposal cover art','webinar title slides'])} — on brand kit, ${rnd(['first pass','v2 after feedback','final'])}`, p:3},
    {i:'⚡', t:()=>`Turnaround: ${rnd(['carousel','ad set','one-pager'])} briefed ${rnd(['this morning','at 9am','after standup'])}, delivered in ${ri(2,5)} hours`, p:2},
    {i:'🧪', t:()=>`Variant test prepped for META ADS — same copy, ${rnd(['3 layouts','2 colourways','device-frame vs flat'])}`, p:2},
    {i:'📚', t:()=>`Brand kit updated in the Brain — ${rnd(['new chart style','carousel grid template','logo-safe zones documented'])}`, brain:true, p:1},
  ],
  stats:[['Assets shipped (7d)',()=>ri(12,20)],['Avg turnaround','3.4 h'],['Revision rate','18%'],['Open briefs','2']],
  chartLbl:'Assets delivered — last 7 days', chart:[2,3,2,4,3,1,2],
  greeting:`Hi AJ. 14 assets out the door this week — carousels for Instagram Organic, ad variants for Meta Ads, and a refreshed proposal cover for Proposals. Everything runs off the one brand kit in the Brain, so it all looks like us. Two briefs open, both on schedule.`,
  chat:[
    {k:['queue','brief','open','working'], r:[`Open briefs:\n\n1. 10am Rule carousel (Instagram Organic) — slides 1–4 done, chart slide in progress, delivery today.\n2. Retargeting ad refresh (Meta Ads) — 3 variants, same copy, different visual weight. Tomorrow morning.\n\nNothing else waiting. Average turnaround this week: 3.4 hours brief-to-delivery.`]},
    {k:['brand','kit','style','consistent'], r:[`One brand kit, zero drift: the ink/cream palette, serif display + sans body, chart styles, logo-safe zones — all documented in the Brain under Brand Kit. Every asset starts from it, which is why a carousel, an ad and a proposal cover all read as the same company. When you want the look evolved, we change the kit once and everything downstream follows.`]},
    {k:['ad','meta','variant'], r:[`For Meta Ads I ship in variant sets — same message, 3 visual treatments — so Ada can let the auction decide instead of guessing. Current set: device-frame screenshot vs flat illustration vs big-number card. Historically the big-number cards win cold traffic and device-frames win retargeting.`]},
    {k:['revision','feedback','change'], r:[`Revision rate is 18% — mostly copy tweaks after design, not rework. The loop: brief in → first pass → one feedback round → final. If something needs a third round, that's a brief problem not a design problem, and I flag it back to whoever briefed me.`]},
  ],
  fallback:[`If marketing ships it, I designed it — ads, carousels, decks, covers. Ask about my open briefs, the brand kit, or ad variants.`,`Try "what's in your queue?", "how do you keep it on-brand?" or "what's shipping for Meta?"`],
  chips:['What’s in your queue?','How do you keep it on-brand?','What’s shipping for Meta?'] },

/* ============ OPERATIONS ============ */
{ id:'piper', name:'PROPOSALS', dept:'sales', desk:[15,12], sit:[15,13], hair:'#3a1d08', shirt:'#60a5fa',
  role:'Proposal Generator Agent',
  tagline:'Drafts and sends proposals from the offer ladder.',
  tasks:['Building a proposal for {co} ({count} seats)','Drafting the cover email for {person}','Updating pricing tables from the Brain','Waiting on AJ’s approval for the {co} proposal','Checking which proposals were opened this week'],
  ev:[
    {i:'📄', t:()=>`Proposal built: ${rnd(P.co)} — ${ri(5,40)} seats, ${rnd(P.plan)} plan, ${money(ri(400,3000))}/mo. Email drafted, queued for AJ`, approval:'proposal', p:2},
    {i:'👀', t:()=>`${rnd(P.co)} opened their proposal ${ri(2,5)} times today — worth a call while it’s warm`, p:2},
    {i:'✅', t:()=>`Proposal accepted 🎉 ${rnd(P.co)} — ${money(ri(500,2500))}/mo. Handing to onboarding`, kpi:{id:'proposals',n:1}, p:1},
    {i:'📚', t:()=>`Pulled current pricing + case study from the Brain for the ${rnd(P.co)} proposal`, brain:true, p:2},
  ],
  stats:[['Proposals this week','9'],['Awaiting your approval','2'],['Open rate','89%'],['Accepted this month','11']],
  chartLbl:'Proposals sent — last 7 days', chart:[2,3,1,4,2,0,2],
  greeting:`Hi AJ. 9 proposals out this week, 2 more built and waiting on your approval — Kea Logistics (18 seats) and UrbanNest Realty (7 seats). Ridgeline opened theirs 4 times today; someone should call them while it's warm. Spencer's been pinged.`,
  chat:[
    {k:['pending','waiting','queue','approval'], r:[`Two awaiting your sign-off:\n\n1. Kea Logistics — 18 seats, Scale plan, ${money(1620)}/mo, 12-month term with the standard 10% annual discount. Cover email references their freight-team use case.\n2. UrbanNest Realty — 7 seats, Growth, ${money(630)}/mo.\n\nBoth in your approvals queue with the full PDF and email. One click and they're gone.`]},
    {k:['opened','warm','engag'], r:[`Engagement this week: Ridgeline opened their proposal 4× today (call them!), Southern Cross Fitness twice yesterday, BlueWater Marine hasn't opened after 3 days — I've drafted a gentle nudge email, also in your queue. Open rate across the week: 89%.`]},
    {k:['how do you','build','write','template'], r:[`My build process: deal brief in → I pull current pricing, the closest case study, and terms from the Brain → assemble proposal (their branding colours on the cover, their use case on page 1, pricing table, social proof, next steps) → draft a 6-line cover email in your voice → queue both for your approval. Average build time: 4 minutes. Nothing sends itself.`]},
    {k:['accept','won','close','month'], r:[`11 accepted this month, ${money(14300)}/mo in new MRR. Average time from brief to signed: 6 days. Pattern worth knowing: proposals opened within 2 hours of sending close at nearly double the rate — which is why I always tell you the moment one gets opened.`]},
  ],
  fallback:[`Brief in, proposal + email out, your approval in between. Ask what's pending, who's opened theirs, or this month's wins.`,`Try "what's pending?", "who opened their proposal?" or "how many accepted this month?"`],
  chips:['What’s pending?','Who opened theirs?','Accepted this month?'] },

/* ============ FINANCE — ACCOUNTING TEAM ============ */
{ id:'alead', name:'ACCOUNTING LEAD', dept:'fin', desk:[21,12], sit:[21,13], hair:'#1f1f1f', shirt:'#60a5fa', lead:true,
  role:'Finance Lead Agent',
  tagline:'Runs the Finance pod: invoicing, payables and reconciliation.',
  tasks:['Reviewing exceptions from the accounting team','Tracking month-end close progress','Checking {count} flagged transactions','Preparing the weekly cash summary for AJ','Auditing a flagged contractor invoice before it reaches AJ'],
  ev:[
    {i:'🗂', t:()=>`Reviewed team output: ${ri(4,9)} invoices, ${ri(2,6)} bills, ${ri(10,30)} transactions matched — ${rnd(['no exceptions','1 exception, handled','2 exceptions, investigating'])}`, p:3},
    {i:'📊', t:()=>`Month-end close: ${ri(55,90)}% complete, tracking ${rnd(['on schedule','1 day ahead'])}`, p:2},
    {i:'🔎', t:()=>`Exception resolved: ${rnd(['duplicate supplier bill caught by PAYABLES','unmatched deposit traced to a plan upgrade','invoice rounding mismatch corrected'])}`, p:2},
    {i:'💼', t:()=>`Weekly cash summary drafted for AJ — in your queue ${rnd(['tonight','tomorrow 8am'])}`, brain:true, p:1},
  ],
  stats:[['Team throughput (7d)','214 items'],['Open exceptions','1'],['Close progress','72%'],['Cash position','healthy']],
  chartLbl:'Exceptions caught — last 7 days', chart:[2,1,3,1,2,0,1],
  greeting:`AJ — accounting team is running clean. This week: 214 items processed across Invoicing, Payables and Reconciliation, with one open exception (an unmatched deposit I'm tracing — looks like a plan upgrade paid manually). Month-end close is 72% done, on schedule. Nothing needs you today.`,
  chat:[
    {k:['team','manage','control','how do you'], r:[`I sit above the three specialists: INVOICING raises and chases invoices, PAYABLES audits card charges and contractor invoices, RECONCILIATION matches everything against the bank. They handle volume; anything unusual escalates to me. I resolve what I can, and only what's genuinely above my authority — contract variances, write-offs, anything odd — reaches you. You should hear from accounting rarely; that's the KPI.`]},
    {k:['exception','flag','issue','problem'], r:[`One open exception: a ${money(340)} deposit with no matching invoice. Traced so far: it matches Kauri Dental's plan-upgrade amount — likely paid by manual transfer instead of card. I've asked Invoicing to confirm and issue the receipt. Everything else this week was caught and closed inside the team.`]},
    {k:['close','month','month-end'], r:[`Month-end close: 72% complete, on schedule for the 1st. Remaining: final bank rec (waiting on 2 pending transactions to clear), depreciation entries, and my summary memo. You'll get the close pack without asking — revenue, costs, cash movement, and anything I'd want explained if I were you.`]},
    {k:['cash','summary','position'], r:[`Cash position is healthy — collections are ahead of last month (Invoicing's reminder sequence is working: DSO down 4 days). Weekly cash summary lands in your queue tomorrow 8am with the detail. Headline: more coming in, on time, and payables scheduled to terms — no surprises.`]},
  ],
  fallback:[`I run the accounting team so you don't have to think about it. Ask about exceptions, month-end close, or the team's throughput.`,`Try "any exceptions?", "how's month-end going?" or "how's our cash?"`],
  chips:['Any exceptions?','How’s month-end?','How’s our cash?'] },

{ id:'invo', name:'INVOICING', dept:'fin', desk:[17,15], sit:[17,16], hair:'#4a2c14', shirt:'#7ab8f7',
  role:'Invoicing Agent',
  tagline:'Issues and tracks client invoices.',
  tasks:['Raising invoices for yesterday’s signups','Running the overdue reminder sequence','Issuing a credit note for {co}','Checking GST lines on the AU batch','Confirming a manual payment with {co}'],
  ev:[
    {i:'🧾', t:()=>`Invoice issued: ${rnd(P.co)} — ${money(ri(90,1400))} (${rnd(P.plan)} plan), GST correct, sent ✓`, kpi:{id:'invoices',n:1}, p:4},
    {i:'⏰', t:()=>`Reminder ${ri(1,3)} of 3 sent to ${rnd(P.co)} — ${money(ri(120,900))} now ${ri(3,21)} days overdue`, p:2},
    {i:'💰', t:()=>`Paid ✓ ${rnd(P.co)} settled ${money(ri(120,1400))} after reminder ${ri(1,2)} — DSO improving`, p:2},
    {i:'🚩', t:()=>`${rnd(P.co)} at ${ri(30,45)} days overdue — escalated to ACCOUNTING LEAD`, p:1},
  ],
  stats:[['Invoices this week',()=>ri(30,45)],['Overdue book',()=>money(ri(1800,4200))],['DSO','21 days (↓4)'],['Collection rate','96%']],
  chartLbl:'Invoices issued — last 7 days', chart:[7,9,6,11,8,2,5],
  greeting:`Hi AJ. 38 invoices out this week, all clean on GST. The overdue book is ${money(2400)} across 5 accounts — my 3-step reminder sequence has DSO down to 21 days, 4 better than last month. One account is past 30 days and with the Accounting Lead now.`,
  chat:[
    {k:['overdue','late','chase','remind'], r:[`Overdue book: ${money(2400)} across 5 accounts. My sequence: day 3 friendly nudge, day 10 firmer with a payment link, day 21 final notice + flag to the Accounting Lead. 96% pays by step 2 — the tone stays warm the whole way because these are customers, not debtors. Only 1 account is past 30 days right now.`]},
    {k:['dso','collect','cash'], r:[`DSO is 21 days, down from 25 last month. What moved it: invoicing same-day instead of weekly batches, and putting the payment link in every reminder. Faster invoice out = faster cash in — boring and true.`]},
    {k:['gst','credit','error'], r:[`Zero GST errors since the template fix Billing and I did (the pre-March NZ entity issue). One credit note this week — ${rnd(P.co)} downgraded mid-cycle, pro-rata credit issued and reconciled. Every credit note gets a reason code so Reconciliation never has to guess.`]},
    {k:['how','process','raise'], r:[`Flow: plan event (new/upgrade/renewal) → I raise the invoice same-day with correct GST → send → track. Manual payments get confirmed and receipted within the hour. Anything unusual — odd amounts, disputes — goes up to the Accounting Lead, not out to you.`]},
  ],
  fallback:[`Invoices out fast, cash in faster. Ask about the overdue book, DSO, or this week's volume.`,`Try "what's overdue?", "how's DSO?" or "any credit notes?"`],
  chips:['What’s overdue?','How’s DSO?','This week’s volume?'] },

{ id:'apay', name:'ACCOUNTS PAYABLE', dept:'fin', desk:[20,15], sit:[20,16], hair:'#111', shirt:'#4d94e8',
  role:'Accounts Payable Agent',
  tagline:'Processes and reconciles vendor and contractor payments.',
  tasks:['Matching this week’s card charges to their subscriptions','Checking invoice #218 against the design contract','Verifying a duplicate-looking card charge','Flagging renewals due on the card this quarter','Updating vendor records in the Brain'],
  ev:[
    {i:'📥', t:()=>`Card charge matched: ${rnd(['Meta Ads','FullEnrich','Xero','AWS','the SMS provider','Canva'])} — ${money(ri(40,900))}, expected amount ✓`, p:3},
    {i:'🛑', t:()=>`Duplicate caught: ${rnd(['a vendor charged the card twice','same invoice emailed twice'])} — ${money(ri(80,600))} NOT paid twice`, p:2},
    {i:'📋', t:()=>`Invoice audited: ${rnd(['contractor #218 — rate over contract, HELD for AJ','contractor hours vs brief — checks out, cleared','a renewal 12% over last year — flagged'])}`, approval:'payment', p:1},
    {i:'🤝', t:()=>`Savings note: ${rnd(['annual prepay would save 8% on the SMS provider','FullEnrich tier drop possible — usage is under plan'])} — flagged to ACCOUNTING LEAD`, p:1},
  ],
  stats:[['Charges matched (7d)',()=>ri(14,24)],['Duplicates caught (30d)','3'],['Held for review','1'],['Surprise charges','0']],
  chartLbl:'Charges audited — last 7 days', chart:[3,4,2,5,3,0,2],
  greeting:`Hi AJ. 18 card charges matched this week — every subscription billed what it was supposed to. One thing is held: the design contractor's invoice #218 came in at $110/hr against the $85/hr we signed in March. Nothing gets paid over contract without you seeing it. Always.`,
  chat:[
    {k:['218','invoice','contract','held','hold','match'], r:[`Invoice #218, the design contractor: 14 hours at $110/hr = ${money(1540)}. The contract we signed 12 March says $85/hr — that's ${money(350)} over, and there's no signed variation covering a rate change. Hours and scope check out fine; only the rate is off. It's held in your approvals queue: approve the hold and I draft the query email, reject and it pays as billed.`]},
    {k:['duplicate','double','caught'], r:[`3 duplicates caught in 30 days — vendors double-charging the card is more common than anyone thinks. My check: amount + vendor + period fingerprint against every charge already matched. Anything that smells the same gets held and verified before it clears.`]},
    {k:['save','negotiat','cost','spend'], r:[`Two savings flagged to the Accounting Lead: annual prepay on the SMS provider (saves ~8%), and our FullEnrich usage is running under the tier we pay for — a plan drop saves ${money(90)}/mo with zero impact. I spot these because I see every charge; the Lead decides if they're worth pursuing.`]},
    {k:['vendor','supplier','bill','card','who'], r:[`Most of the stack auto-charges the card: Meta, FullEnrich, Canva, hosting, the SMS provider, accounting software. Those I match against their plan — right amount, right cadence, no surprises. Contractors and agencies invoice instead, and every one of those gets checked against its contract before it's paid. All vendor records and agreed rates live in the Brain.`]},
  ],
  fallback:[`Every charge matched, every invoice checked against its contract — nothing over-agreed gets paid without you. Ask about invoice #218, duplicates, or savings I've spotted.`,`Try "what's held?", "caught any duplicates?" or "any savings?"`],
  chips:['What’s held right now?','Caught any duplicates?','Any savings spotted?'] },

/* ============ EMAILS (V3.1, 5 Sep 2026 — replaced Customer Support) ============ */
{ id:'elead', name:'EMAILS LEAD', dept:'emails', desk:[7,6], sit:[7,7], hair:'#2b2b2b', shirt:'#2dd4bf', lead:true,
  role:'Content Lead Agent',
  tagline:'Runs the Content pod: comms, status updates and the newsletter.',
  tasks:['Routing the overnight inbox — {count} emails','Tone pass on replies before they go out','Escalating a thread from {co} to AJ','Updating the reply templates','Writing the weekly inbox summary'],
  ev:[
    {i:'📬', t:()=>`Routed ${ri(28,60)} overnight emails — ${ri(2,4)} flagged for AJ, the rest handled by the desks`, p:3},
    {i:'✍', t:()=>`Tone pass on a reply to ${rnd(P.co)} — softened one line, sent`, p:2},
    {i:'⬆', t:()=>`Escalated a thread from ${rnd(P.co)} — pricing dispute, AJ needs to see it`, p:1},
  ],
  stats:[['Emails routed today',()=>ri(60,140)],['Avg first reply',()=>ri(9,22)+' min'],['Escalated to AJ','3'],['Templates live','18']],
  chartLbl:'Emails handled — last 7 days', chart:[118,131,96,142,127,88,121],
  greeting:`Morning AJ. Inbox is clear — ${ri(60,120)} emails routed since last night, 3 sitting with you (two pricing questions, one contractor dispute). Ask me about anything in the inbox, response times, or what's waiting on you.`,
  chat:[
    {k:['waiting','escalat','need','me'], r:[`Three for you: ${rnd(P.co)} asking about the price change, ${rnd(P.co)} disputing a scope line, and the video contractor about a late payment. Drafts for all three are ready — you just approve or edit.`]},
    {k:['response','fast','time','sla'], r:[`Average first reply today: ${ri(9,22)} minutes. Client emails go first, vendors and contractors within the hour, internal by end of day. Nothing older than 3 hours is unanswered.`]},
    {k:['template','tone','voice'], r:[`Every reply passes a tone check against the voice rules in the Brain — plain, warm, no hedging. I rewrote two templates this week because they read stiff. Want to see the before and after?`]},
  ],
  fallback:[`I run the inbox — routing, tone, escalation. Ask what's waiting on you, how fast we reply, or about any thread.`,`Try "what's waiting on me?", "how fast are we replying?" or "show me the client threads".`],
  chips:['What’s waiting on me?','How fast are we replying?','Any escalations?'] },

{ id:'cmail', name:'CLIENT EMAILS', dept:'emails', desk:[4,3], sit:[4,4], hair:'#3b2b1d', shirt:'#2dd4bf',
  role:'Status Writer Agent',
  tagline:'Writes client status updates and replies to scope questions.',
  tasks:['Replying to {co} about the timeline','Sending the kickoff summary to {co}','Answering {count} client emails from overnight','Drafting the price-increase notice','Chasing {person} for the brief sign-off'],
  ev:[
    {i:'📨', t:()=>`Replied to ${person()} @ ${rnd(P.co)} — timeline question, answered from the project plan`, p:3},
    {i:'📚', t:()=>`Pulled the ${rnd(P.co)} scope from the Brain to answer a "is this included?" email`, brain:true, p:2},
    {i:'⏸', t:()=>`Price-increase notice drafted for ${ri(90,140)} clients — waiting on AJ`, p:1},
  ],
  stats:[['Client emails today',()=>ri(18,40)],['Avg reply',()=>ri(8,20)+' min'],['Open threads','4'],['Happy replies (7d)','92%']],
  chartLbl:'Client emails answered — last 7 days', chart:[31,28,36,24,39,22,30],
  greeting:`Hi AJ. ${ri(18,40)} client emails answered today, 4 threads still open — all waiting on the client, not us. The price-increase notice is drafted and sitting in your approvals.`,
  chat:[
    {k:['open','thread','waiting','client'], r:[`Open threads: ${rnd(P.co)} (waiting on their sign-off), ${rnd(P.co)} (asked for a call — booked Thursday), ${rnd(P.co)} (scope question, answered, awaiting reply) and one new lead who emailed directly — handed to the Inbound Leads Manager.`]},
    {k:['price','increase','notice'], r:[`The price-increase notice: 120 clients, goes out in two waves, 30 days notice, with the "what you get now" section up top. Draft is in your approvals. Nothing sends without your tick.`]},
    {k:['scope','included','timeline'], r:[`Scope and timeline questions I answer straight from the Brain — the project plan and the signed proposal are the source. If a client asks for something outside scope, I say so kindly and hand it to the Project Co-ordinator.`]},
  ],
  fallback:[`I look after client emails. Ask about open threads, reply times, or the price notice.`,`Try "any open threads?", "what did ${rnd(P.co)} ask?" or "status of the price notice".`],
  chips:['Any open threads?','Status of the price notice?','How fast are replies?'] },

/* ============ SALES additions (V3.1) ============ */
{ id:'ilm', name:'INBOUND LEADS MANAGER', dept:'sales', desk:[20,3], sit:[20,4], hair:'#26140a', shirt:'#fbbf24',
  role:'Inbound Leads Manager Agent',
  tagline:'Triages and routes inbound leads to the right rep.',
  tasks:['Qualifying {count} inbound leads from the website','Routing 6 hot leads to the reps','Replying to {co} within the hour','Booking a discovery call with {co}','Cleaning 12 duplicates out of the inbound queue'],
  ev:[
    {i:'🔥', t:()=>`Hot lead: ${person()} @ ${rnd(P.co)} — ${rnd(['asked for pricing','booked a call','replied to the newsletter'])}, routed to ${rnd(['Spencer','Arwin','Jack'])}`, p:3},
    {i:'✅', t:()=>`Qualified ${ri(4,12)} inbound leads — ${ri(1,4)} hot, ${ri(2,6)} nurture, rest not a fit`, p:3},
    {i:'📅', t:()=>`Discovery call booked with ${rnd(P.co)} — ${rnd(['tomorrow 10am','Thursday 2pm','Friday 11am'])}`, p:2},
  ],
  stats:[['Inbound today',()=>ri(8,24)],['Qualified hot',()=>ri(2,6)],['Avg response',()=>ri(6,30)+' min'],['Calls booked (7d)','11']],
  chartLbl:'Inbound leads qualified — last 7 days', chart:[14,11,19,16,22,8,17],
  greeting:`Hi AJ. ${ri(8,24)} inbound leads today, ${ri(2,6)} hot and already with the reps. Average response ${ri(6,30)} minutes. Ask me what's hot, who's booked, or how the routing rules work.`,
  chat:[
    {k:['hot','best','today'], r:[`Hot today: ${person()} @ ${rnd(P.co)} (asked for pricing, 12-seat team), ${person()} @ ${rnd(P.co)} (booked a call from the website). Both routed within 15 minutes with the enriched profile attached.`]},
    {k:['route','routing','rule','rep'], r:[`Routing rules live in the Brain: hot = pricing ask, demo request or 10+ seats → straight to a rep by territory. Warm → nurture sequence. Not a fit → polite no with the guide link. The Sales Lead reviews my calls weekly.`]},
    {k:['response','fast','time'], r:[`Every inbound gets a human-sounding reply inside the hour, most inside 15 minutes — the Lead Enricher gives me the company profile first so the reply is specific, not a template.`]},
  ],
  fallback:[`I run inbound leads — qualify, route, book. Ask what's hot, who's booked, or about the routing rules.`,`Try "what's hot today?", "who's booked this week?" or "how do you route?".`],
  chips:['What’s hot today?','Who’s booked?','How do you route?'] },

/* ============ DELIVERY (V3.1, 5 Sep 2026 — new department) ============ */
{ id:'mlead', name:'MARKETING LEAD', dept:'marketing', desk:[3,0], sit:[3,1], hair:'#2a1a0e', shirt:'#f87171', lead:true,
  role:'Frontend Lead Agent',
  tagline:'Runs the Frontend pod: UI, mobile and the design system.',
  tasks:['Reviewing the week’s content before it ships','Rebalancing the ad budget toward the winner','Setting the reel line-up for next week','Writing the weekly marketing summary','Briefing Research on the next angle'],
  ev:[
    {i:'🧭', t:()=>`Team review: ${ri(3,6)} reels cut, newsletter issue ${ri(30,34)} ${rnd(['scheduled','in draft','sent'])}, ad set ${rnd(['refreshed','held','scaled'])} — ${rnd(['all on plan','one reel sent back for a stronger hook','two creatives swapped'])}`, p:3},
    {i:'📈', t:()=>`Weekly numbers: reach ${rnd(['up','flat','down'])} ${ri(4,28)}%, ${ri(2,5)} posts above the baseline multiple, CPA $${ri(24,38)}`, p:2},
    {i:'🎓', t:()=>`Coached ${rnd(['INSTAGRAM ORGANIC','NEWSLETTER','META ADS'])} — ${rnd(['hook first, promise second','one idea per reel','kill the sub-baseline variant sooner'])}`, brain:true, p:1},
  ],
  stats:[['Posts this week','6'],['Above baseline','2'],['Ad spend today','$684'],['Newsletter open rate','41%']],
  chartLbl:'Posts above baseline — last 8 weeks', chart:[1,2,1,3,2,2,3,2],
  greeting:`Morning AJ. Six posts out this week, two above the baseline multiple. Meta CPA is holding at $${ri(26,32)}; I've asked Meta Ads to shift $50 a day into the winner. The October content plan is in your approvals.`,
  chat:[
    {k:['plan','calendar','week','next'], r:[`Next week: three reels (Research has the angles), newsletter issue ${ri(31,34)}, and one ad refresh. Video Editor has capacity; Graphics is at 80%. Say the word and I'll swap a reel for a carousel.`]},
    {k:['ads','spend','cpa','budget'], r:[`Ad spend today $684, CPA $${ri(26,32)}. One creative is fatigued — Meta Ads has a refresh in progress. I don't scale anything past $180 a day without your tick.`]},
    {k:['working','what worked','best','top'], r:[`Best this week: the "10am rule" reel at ${(ri(21,34)/10).toFixed(1)}× baseline. Worst: the pricing carousel, under 0.5×. Research is pulling the angle apart to see why.`]},
  ],
  fallback:[`I run marketing — the plan, the budget, what worked. Ask about next week, the ads, or the numbers.`,`Try "what's the plan next week?", "how are the ads doing?" or "what worked?".`],
  chips:['What’s the plan next week?','How are the ads doing?','What worked?'] },


];
export const STATS = { emailsSent:128, drafts:41, reports:9, projects:12, onTrack:11, chats:11, insMkt:3, insOps:5, cpa:41.0, spencer:14, arwin:31, jack:16, managers:5, autoOnb:17, billsPaid:14 };
export const FILE_GEN = {
  gfx: ()=>({ icon:'🎨', name:rnd(['carousel-10am-rule','ad-variants-retargeting','quote-cards-july'])+'.fig', meta:'design delivery · on brand kit · click to view',
    content:`DESIGN DELIVERY\n\nbrief: ${rnd(['6-slide IG carousel — the 10am Rule','3 Meta ad variants — same copy, 3 layouts','quote-card set — 4 customer wins'])}\nbriefed by: ${rnd(['INSTAGRAM ORGANIC','META ADS','PROPOSALS'])}\nturnaround: ${ri(2,5)} hours\n\nspecs\n  palette ........ ink #151414 / cream #FDFFF8 + chips\n  type ........... serif display + sans body (brand kit)\n  formats ........ 1080×1350 + 1080×1920 exports\n\nstatus: delivered ✓ · source files in the Brain → Brand Kit` }),
  piper: ()=>{ const co=rnd(P.co), n=ri(6,28), pl=rnd(P.plan), m=ri(500,2400);
    return { icon:'📄', name:`proposal-${slug(co)}.pdf`, meta:'proposal draft · awaiting AJ approval · click to view',
    content:`AGENTS OFFICE — PROPOSAL\nClient: ${co}\nSeats: ${n} · Plan: ${pl} · ${money(m)}/mo (12-mo term, 10% annual disc.)\n\n1. YOUR USE CASE\n   ${co} needs call tracking and coaching across ${n} reps.\n   Current stack loses ~30% of call outcomes to manual logging.\n\n2. PRICING\n   ${n} seats × ${pl} = ${money(m)}/mo · locked for 12 months\n\n3. PROOF\n   Auckland roofing co: 0 → 40 tracked calls/week in 14 days.\n\n4. NEXT STEPS\n   Reply to the cover email or sign online — link included.\n\n— drafted by PROPOSALS in 4 min · pulled pricing + case study from the Brain` };},
  newt: ()=>({ icon:'✍', name:'newsletter-august-draft.md', meta:'draft v3 · awaiting AJ approval · click to view',
    content:`SUBJECT A: calls before 10am are a trap\nSUBJECT B: we looked at 40,000 calls — call at this time\n\n# The 10am Rule\nConnect rates nearly double between 10:00–11:30am.\nWe pulled the (anonymised) numbers across 40,000 dials:\n\n  before 10am ......... 11% connect\n  10:00–11:30 ......... 21% connect\n  after 4pm ........... 9% connect\n\nCustomer story: Harbour City Roofing went 0 → 40 tracked\ncalls/week. One tool tip: pin your top list to the dialler.\n\nCTA (soft): reply "10AM" and we'll send the full breakdown.` }),
  riley: ()=>({ icon:'📰', name:'daily-briefing-'+clockStr().replace(':','')+'.md', meta:'6am scan · 47 sources · click to view',
    content:`DAILY BRIEFING — worth your time (3)\n\n1. CallForge raised prices 8% — customers grumbling on\n   LinkedIn. Window for a comparison campaign. → INTEL\n2. "AI SDR" searches +22% MoM — our messaging doesn't\n   use the phrase anywhere. Positioning gap?\n3. AU voicemail-drop guidance updated — no impact today.\n\nscanned: 47 sources · 6 newsletters · 40 tracked voices\neverything else did not meet the bar.` }),
  enzo: ()=>{ const p=person(), co=rnd(P.co);
    return { icon:'🔍', name:`lead-${slug(p)}.json`, meta:'FullEnrich · 11/14 fields · click to view',
    content:`{\n  "name": "${p}",\n  "company": "${co}",\n  "title": "${rnd(['Head of Sales','Sales Manager','Founder','GM'])}",\n  "headcount": ${ri(5,120)},\n  "mobile": "+64 2• ••• •${ri(100,999)}",  // verified ✓\n  "linkedin": "in/${slug(p)}",\n  "city": "${rnd(P.city)}",\n  "score": ${ri(62,94)},\n  "route": "${rnd(['SPENCER (manager+)','ARWIN','JACK'])}",\n  "confidence": "${ri(81,97)}%"\n}` };},
  lexi: ()=>({ icon:'📞', name:'call-list-arwin-'+clockStr().replace(':','')+'.csv', meta:'freshest first · 6h target · click to view',
    content:`rank,lead,company,score,age\n1,${person()},${rnd(P.co)},91,4h\n2,${person()},${rnd(P.co)},88,7h\n3,${person()},${rnd(P.co)},84,1d\n4,${person()},${rnd(P.co)},81,1d\n5,${person()},${rnd(P.co)},78,2d\n6,${person()},${rnd(P.co)},74,2d\n…31 rows · 5.6h of calling queued` }),
  alead: ()=>({ icon:'💼', name:'weekly-cash-summary.md', meta:'prepared for AJ · click to view',
    content:`WEEKLY CASH SUMMARY — prepared by ACCOUNTING LEAD\n\nin\n  collections .......... ahead of last month (DSO 21d, ↓4)\n  invoices issued ....... 38, all clean GST\nout\n  card charges ......... 18/18 matched, no surprises\n  invoice #218 ......... HELD · +${money(350)} over contract rate\n  duplicates blocked .... ${money(340)} saved this week\n\nexceptions: 1 open (unmatched ${money(340)} deposit — tracing)\nmonth-end close: 72% · on schedule for the 1st\nverdict: healthy. one decision waiting: invoice #218.` }),
  invo: ()=>{ const co=rnd(P.co);
    return { icon:'🧾', name:`invoice-${slug(co)}-${ri(1040,1090)}.pdf`, meta:'issued + sent · click to view',
    content:`TAX INVOICE #${ri(1040,1090)}\n${co}\n\n  ${rnd(P.plan)} plan — ${ri(3,20)} seats     ${money(ri(150,1400))}\n  GST (15%)                        included\n  due: 7 days · payment link included\n\nstatus: sent ✓ · reminder sequence armed (day 3 / 10 / 21)\nreason code: renewal · auto-reconciles on payment` };},
  apay: ()=>({ icon:'📋', name:'invoice-218-audit.md', meta:'rate variance · held for AJ · click to view',
    content:`INVOICE AUDIT — #218 (design contractor)\n\ninvoiced ......... 14 hrs × $110/hr = ${money(1540)}\ncontract ......... $85/hr · signed 12 Mar\nvariance ......... +${money(350)} ⚠ no signed variation\n\nchecks\n  hours vs brief ....... ✓ matches\n  scope ................ ✓ matches\n  duplicate ............ ✓ clear\n\nrecommendation: HOLD · query the rate before paying\ncard charges this week: 18/18 matched, no surprises` }),
};
