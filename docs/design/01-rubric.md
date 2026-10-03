# Spec 01 — Decision Rubric: is this idea worth building?

**Status**: DRAFT for owner review · 2026-10-03
**Depends on**: nothing. Specs 02 (objects) and 03 (boundaries) depend on this one.
**Owner inputs this spec encodes**: GO needs *competitors earning revenue* and *public pain posts*; the build is cheap, so the second gate is *acquirability*, not build effort; under **$1** per memo; verdict approved by the owner in the office UI; 1–3 ideas a month.

Numbers in **bold brackets** like **[8]** are proposed defaults. They are guesses until calibrated on the known-answer ideas (section 9). Change them in one place (section 10), not in prompts.

---

## 1. Purpose

Turn a one-paragraph idea into a **GO / TEST / NO-GO** verdict that the owner can trust or overrule in under five minutes of reading. The rubric exists to stop two failures: building things nobody pays for, and a confident-sounding memo built on invented numbers.

The verdict is **computed from the evidence table by the rules below**. Narrative cannot upgrade a verdict.

## 2. Verdicts

| Verdict | Meaning | Required |
|---|---|---|
| **GO** | Both gates pass. Commit build time. | Gate D = PASS, Gate A = PASS, confidence ≥ MEDIUM, no standing kill reason |
| **NO-GO** | Stop. Do not revisit without new facts. | A gate = FAIL on **sufficient search** (see 5.3), or a kill reason stands |
| **TEST** | Cannot decide from desk research. Run the cheapest real-world test. | Any gate = UNKNOWN, or confidence = LOW, or the gates conflict |

Rules:
- **Absence of evidence is not evidence of absence.** A gate FAILS only if the search was sufficient (5.3). Otherwise it is UNKNOWN, and UNKNOWN never becomes GO.
- **No GO at LOW confidence.** Ever.
- **TEST must name the test**: the single cheapest action (landing page with a price, ten outreach messages, a pre-sale) and the result that would flip the verdict to GO or NO-GO. A TEST without a flip condition is invalid.

## 3. Gate D — Demand (both parts required)

### D1. Competitors earning revenue
Pass when **≥ [3]** distinct competitors/alternatives are identified **and ≥ [2]** of them have revenue evidence of Tier 1 or Tier 2.

| Tier | Evidence | Examples |
|---|---|---|
| **T1** (strong) | Revenue stated by the company or a filing | Public MRR/ARR page, founder-posted revenue, S-1, acquisition price with revenue |
| **T2** (usable) | A paid product with visible traction | Paid pricing page **plus** ≥ **[50]** reviews on G2/Capterra/app store/Chrome store, or ≥ **[N]** named customers, or active hiring for the product |
| **T3** (weak, supporting only) | Indirect estimates | Traffic estimates, social followers, funding without revenue |

T3 alone never passes D1. A free product, or one with no pricing, counts as an alternative but not as revenue evidence.

### D2. Public pain posts
Pass when there are **≥ [8]** posts that meet **all** of:
- from **≥ [3]** distinct communities/sites (forum, subreddit, review site, issue tracker, job board);
- published within the last **[12]** months;
- **≥ [5]** of them are *specific*: they describe a concrete task, a cost (time or money), or a workaround the writer already pays for or built.

Vague posts ("this is annoying") count toward the 8 but not toward the 5. Posts must be by distinct authors. Quote ≤ 25 words and link each.

## 4. Gate A — Acquirability (replaces "buildable")

Because the owner expects the build to be cheap, effort is not a gate. The scarce resource is reaching paying customers.

Pass when **all** of:
- **A1. Named reachable audience**: the buyer is a specific role/segment, and at least one concrete place they gather or a list they appear on is identified (community, search term with evidence of volume, directory, marketplace).
- **A2. A path to ten**: a stated, plausible route to the first **[10]** paying customers that needs no paid-ads budget above **[$TBD — owner to set]**.
- **A3. Willingness to pay is shown**: at least one T1/T2 price point from D1 that the target segment could afford (unit price × [10] customers is not absurd for the segment).

**Build estimate** is recorded in the memo (hours/days, main technical risk) but is **informational only** until the owner's claim that an MVP takes minutes–hours is verified on one real build. If that claim fails, Gate B (buildable within **[N]** weeks) is added here.

## 5. Evidence rules

### 5.1 Every claim carries evidence
Each row in the evidence table has: `claim`, `type` (FACT | ASSUMPTION | UNKNOWN), `source URL`, `retrieved date`, `quote (≤ 25 words)`, `tier` (for revenue claims). A number without a URL and date is an **ASSUMPTION** and is labelled so everywhere it appears. ASSUMPTIONS never count toward any gate.

### 5.2 Independence
Two sources count as one if they repeat each other (same press release, same Reddit thread, syndicated review). Gate counts use distinct, independent sources.

### 5.3 Sufficient search (required before any FAIL)
A gate may FAIL only if the run recorded at least **[6]** distinct search queries for it (competitor names, category terms, pain phrasing, review sites) and **[3]** fetched pages from independent sources, and the memo lists the queries. Otherwise the gate is UNKNOWN.

### 5.4 Source quality
Prefer first-party and primary sources. Down-weight listicles, AI-generated content farms, and sources with no date. A source that cannot be fetched is recorded as UNKNOWN, not guessed.

## 6. Kill reasons

The Critic must produce a list of kill reasons, each tagged **STANDING** or **REBUTTED** with the evidence that rebuts it. Any STANDING kill reason forces NO-GO (or TEST if evidence to resolve it is cheap). The Critic must check at least:

1. **Incumbent lock-in**: a dominant free or bundled alternative makes paying unlikely.
2. **Commodity**: AI models/platforms already do this natively or will within a year.
3. **Tiny or non-paying segment**: the people with the pain do not buy software.
4. **Distribution wall**: the only reachable channel is closed, gated, or paid-saturated.
5. **Regulatory/trust barrier**: data, finance, health, or legal exposure the owner has not accepted.
6. **Evidence is from one place**: demand rests on a single community or a single source.

The Critic **must not** be the agent that gathered the evidence.

## 7. Confidence

| Level | Condition |
|---|---|
| **HIGH** | Every gate part satisfied by ≥ **[2]** independent T1/T2 or specific-post sources beyond the minimum, and sufficient search recorded |
| **MEDIUM** | Gates satisfied at the minimum, sufficient search recorded |
| **LOW** | Any gate part rests on a single source, any ASSUMPTION is load-bearing, or sufficient search not recorded |

Confidence is computed from the table, not stated by an agent.

## 8. Run budget and stop rules

- Hard cap **[$1]** model + search spend per memo. The run records spend and stops at the cap with whatever it has, marking unfinished gates UNKNOWN.
- At most **[12]** searches and **[20]** fetched pages per run.
- Cheap model for gathering; a stronger model only for the Critic and the final verdict write-up, if budget allows.
- A run that ends with all gates UNKNOWN returns **TEST**, never GO, with the missing evidence listed.

## 9. Memo format (one page)

1. **Verdict** and **confidence**, one line each, then the single most important reason.
2. **Gate table**: D1, D2, A1, A2, A3 → PASS / FAIL / UNKNOWN, with counts (e.g. "competitors with T1/T2: 2 of 3").
3. **Evidence table** (5.1), grouped by gate.
4. **Kill reasons** with STANDING/REBUTTED.
5. **Build note** (informational): estimate, main technical risk.
6. **If TEST**: the cheapest test and what result flips the verdict.
7. **What would change this verdict** (facts, not feelings).
8. **Run log**: queries run, pages fetched, spend, anything that failed.

### Acceptance tests (known-answer ideas)
The rubric is accepted only if a run on three ideas **chosen by the owner** reaches the right verdict:
- one idea the owner is confident has real demand → expect **GO** or **TEST** (never NO-GO);
- one idea the owner is confident is bad → expect **NO-GO** (never GO);
- one genuinely ambiguous idea → expect **TEST** with a sensible flip condition.

Pass criteria: correct verdict on the clear two; every number in the memo traceable to a URL; spend under cap; owner agrees the memo was worth reading. **Kill criterion**: if memos are still generic or uncited after two prompt/skill revisions, stop and reconsider the approach before building anything further.

## 10. Calibration table (single source of truth for the bracketed numbers)

| Name | Default | Meaning |
|---|---|---|
| `D1_min_competitors` | 3 | competitors identified |
| `D1_min_revenue_evidenced` | 2 | with T1/T2 revenue evidence |
| `T2_min_reviews` | 50 | reviews to count as visible traction |
| `D2_min_posts` | 8 | pain posts |
| `D2_min_communities` | 3 | distinct sources |
| `D2_min_specific` | 5 | specific posts |
| `D2_max_age_months` | 12 | recency window |
| `A2_first_customers` | 10 | path-to-ten target |
| `A2_ad_budget_cap` | TBD | owner to set |
| `search_min_queries` | 6 | for a FAIL |
| `search_min_fetches` | 3 | for a FAIL |
| `max_searches` / `max_fetches` | 12 / 20 | per run |
| `budget_cap_usd` | 1.00 | per memo |

## 11. Open items (owner decisions needed before this is final)

1. **Ideas for the three acceptance tests** — the owner must pick them; an AI-chosen "known answer" proves nothing.
2. **`A2_ad_budget_cap`** — how much may a first-customers path assume spending?
3. **Segment limits** — any categories to exclude outright (health, finance, children, regulated data)? These become automatic kill reasons.
4. **Build-claim test** — which small real idea will be built end to end to verify "MVP in hours", so Gate B can be kept or dropped on facts.
5. **Tool dependency** — this rubric cannot be executed until a web search and a web fetch tool exist and are bound to the researcher through the policy gate (spec 03).
