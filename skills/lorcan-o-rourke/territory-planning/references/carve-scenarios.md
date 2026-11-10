# How teams actually carve (scenario catalog)

Every carve is the same seven decisions. Teams differ in which option they pick for each. The rules file
(`territory-rules-starter.md`, saved as `territory-rules.md` in the project once filled) has one knob per
decision, so the carve node (`scripts/carve_node.py`, run as the "Territory Carve" workflow in Clay and
as the local preview `scripts/carve.py`) never hardcodes a method.
Sources are at the end; numbers are what practitioners publish, not laws.

## Decision 1: What groups accounts (route-by)

| Scenario | Who uses it | Inputs needed | Watch out for |
|---|---|---|---|
| **Geography** (country, state, metro, zip; time zone; language) | Field sales; anyone who travels; EMEA by language | HQ country/state/city; a region table | Potential varies wildly by region; "dead space" regions doom a rep. Use zips not area codes. |
| **Segment by size** (employee or revenue bands: SMB / MM / ENT) | Almost everyone, as the first cut | Employee count or revenue, with hierarchy roll-up | Thresholds must be written down; a 349-employee company next to a 351 one lands in different books. v1 segments on employee count; revenue bands need a CRM revenue field the enrichment does not produce. |
| **Vertical / industry** | Regulated or complex buyers (health, finance, public sector) | Industry taxonomy mapped to the rules' groups | Uneven sizes; reps can't flex when their vertical softens. Usually a layer on top of size, not instead of it. |
| **Named accounts** | Enterprise and strategic (20 to 40 accounts per rep) | A curated list, reviewed quarterly | Books go stale; too many names per rep. |
| **Pooled territory** (a city or segment shared by several reps) | Dense metros (SF, NYC, London); shared SL1/SL2 tiers | Pool membership rule; which reps share it | Needs a deal mechanism (round robin, snake, dynamic) or reps collide. |
| **Dynamic book** (rep fixed, list refreshed continuously) | Inside sales, high-velocity, large TAM | Target-book criteria; capacity per rep; activity data | Compensation has to assume no fixed territory; expansion motions still rebalance quarterly. |
| **Hybrid** (geo for SMB, named for ENT, vertical specialists) | Most companies over ~30 reps | All of the above, with an explicit priority order | Highest data requirement; conflicts need a stated precedence. |

Recommended default when the interview gives no strong signal: **segment by size, then route by region, with pooled metros**. It is the shape Clay runs and the one most mid-market SaaS teams converge on.

## Decision 2: How accounts are dealt (allocation method)

| Method | How it works | Fairness property | Best for |
|---|---|---|---|
| **Snake order by score** | Sort eligible accounts by fit, deal 1-2-3-3-2-1 until capacity | Equal count and near-equal mean fit per rep, deterministic, auditable | Default. Any scored pool. |
| **Round robin** | Walk the fit-sorted pool and hand accounts to reps in a fixed rotation until each is at capacity | Equal count; mean fit roughly even only because the pool is still sorted | Inbound, short cycles, similar tenure. Does not correct fit drift the way snake does. |
| **Weighted optimizer** | Solve for minimum variance across several objectives (potential, workload, travel) | Balanced on several axes at once | Field teams with travel; large recarves. Output is a draft, ops still edits. Not in v1: no `allocation.method` value; use `snake` and let the manager edit. |
| **Rep draft** | Reps pick in rounds, often after ranking the pool. The carve node deals nothing under `draft`: it marks every pooled account `Unowned: awaiting draft pick (pick N of M, <segment> / <sub-region>)`, so the pick order is on the record and in `carve-proposal.csv`. Record the picks in `protected_domains` in `reps.csv` (up to `protections.rep_picks.max` each; they come back as `Proposed: rep pick`), switch the method to `snake` or `round_robin` for the rest, then `update`, `reset-proposals`, `run` | Perceived fairness and buy-in; reps know things data doesn't | Small teams, named-account tiers, annual recarves. Slow; political if the order isn't agreed first. |
| **Manager allocation** | method `manager`: within each segment and region, the top `allocation.named_accounts.top_n` accounts by `sort_key` go to the rep an override names (the node's `named_overrides_json` input, domain to CRM user id; `carve_workflow.py build` does not wire that input yet, so in Clay they go to the first rep eligible for the segment and sub-region), reason `named account, manager allocation`; a named account whose rep is at capacity is `Unowned`. The remainder is dealt by rotation, and the manager edits `reps.csv` picks or the rules before approval | Judgment; relationships and skill fit | Strategic tier on top of a bulk deal. The one hybrid with a knob in v1 (an industrial team used top 20 named, rest dealt). |
| **Dynamic distribution** | method `dynamic`: each account, from the highest fit down, goes to the rep with the most remaining capacity (`dynamic deal, <segment> / <sub-region>: rep with the most room`); the rest stays `Unowned: over capacity` by design and is dealt by the top-up as reps free capacity, by the same rule, through the carve workflow's segment trigger | Continuous balance | Inside sales, high-velocity, a pool meant to exceed capacity. Read the rep-count table in `carve-summary.md` as weeks of top-up, not as missing reps (a PLG team kept two reps against a proposal of six). Retrieving stale accounts needs an activity field. |

Production teams combine them: a method deals the bulk, a protected-pick allowance (Clay: max 5 per rep) lets reps keep a few, and a manager approves the result. In v1 the combination with a knob is `manager` with `allocation.named_accounts.top_n`; `snake`, `round_robin` and `dynamic` share one dealing loop and differ only in how the next rep is chosen; `draft` deals nothing until picks are recorded. In Clay every method runs per account over the same superset (every scored account in the segment band and region) against one shared capacity ledger, so `manager` and `draft` work within each segment and region rather than across the whole plan.

## Decision 3: What "balanced" means (balance-by)

| Objective | Measure | Published guidance |
|---|---|---|
| **Count** | accounts per rep within a segment | Equal within one; sizes by segment: Strategic 1 to 20, Enterprise 20 to 40 named, Mid-Market 60 to 80, SMB 120 to 150 workable accounts |
| **Fit / potential** | mean (and median) fit score, or sum of TAM / propensity | Potential within ±10% of the team average; no territory depending on its top 5 accounts for more than 40% of pipeline |
| **Workload** | activity hours implied by account count and cycle length | Workload variance under 15% |
| **Revenue / ACV** | sum of revenue bands or expected ACV | Used when deal size varies more than fit does |
| **Composition** | share of customers vs prospects, core vs other industries, self-serve vs net-new | Clay: self-serve 30 to 40% of an SA book, 20 to 25% of an SL book; industry mix 70/30. Checked after the carve, not enforced (`composition_targets`); self-serve share is not measured in v1 unless a customer flag is synced from the CRM. |
| **Attainment history** | coefficient of variation of rolling attainment | Under 15%; a territory under 70% of modelled potential for two quarters triggers a recarve. No knob in v1; a review input, not a carve input. |

Only `count` and `mean_fit` are balanced in v1. `revenue`, `workload` and `composition` are listed as
options in the YAML but need a revenue or activity field that the enrichment does not produce yet; they
are reported next to the books, not balanced. The interview says so in Q12 and Q16. `carve-summary.md`
calls a segment balanced when the books differ by at most one account and at most 5 points of mean fit;
anything else is reported as "not balanced (pool size or geography)" for the approver to read, not fixed.

Capacity itself comes from quota maths, not from a benchmark: quota ÷ ACV = deals needed; × pipeline coverage (3 to 5x) = opportunities needed; ÷ opportunity rate = accounts needed. Sanity-check the implied activity per day.

Where capacity lives: the `capacity` column on the rep's row in `reps.csv` is authoritative. The segment's
`capacity` in the YAML (plus any `capacity_bonus` for the rep's region) is the default used when that cell
is blank. One source per rep, so two people carving the same pool get the same book sizes.

## Decision 4: What stays put (protections) and what never enters (exclusions)

**Protections (account stays with its owner):**
- Open opportunity on the account or anywhere in its corporate family; "keeper account" rules usually protect stage 2 and beyond until close or stall.
- Active pursuit (e.g. 8+ touches in 30 days, a meeting in the last 60 days).
- Rep protected picks (a small fixed allowance, from `protected_domains` on the rep's row in `reps.csv`; the carve records them as `Proposed: rep pick`, written as owners with the rest after approval).
- Existing customers with a relationship owner; expansion motions keep the owner.
- Deal registration windows for partner-sourced accounts (60 to 90 days).
- Recently churned customers: a cooling-off exclusion from the pool (6 to 12 months), because churn is a CRM fact, not a fit signal.

**Exclusions (never carved):**
- Owned by another team: strategic / Fortune 500 / Top-100 / PE-team / house accounts.
- Company types the business does not sell to: agencies, VC/PE firms, consultancies, SIs, MSPs, staff aug.
- Competitors and partners.
- Education institutions (EdTech allowed), government where not sold to.
- Non-sellable regions (sanctions, GDPR posture, no coverage) and India-heavy accounts where applicable.
- Industries with zero wins over the lookback window.
- Manager exclusions from past reviews, with a reason.
- Below the smallest segment (e.g. under 50 employees): not carved, left to self-serve or inbound.
- Above the largest size this motion sells to (e.g. 5,000+ employees for a PLG or SMB seller): another team or no one sells there; see the size rules below.

**Size rules (both ends):**

| Scenario | Rule | Watch out for |
|---|---|---|
| Too small for this motion | Below `exclusions.min_employees` (kept equal to the first segment's `min_employees`): `Not eligible: below minimum size`. A rules decision, not a grade | A known account the team calls "obviously not a fit" for size gets a carve-status expectation, not a grade, in Step 1 |
| Too big for this motion | `overrides.size_cap` (off by default): at or over `min_employees` (family max), grade `Low Fit` in the Score node, and at carve time `Not eligible: too big` (action `Low Fit`) or `Excluded: too big` (action `exclude`). A PLG team wanted Shopify to read Low in the CRM, so the cap is both a Headcount band in the rubric and a grade override in the rules file | LinkedIn headcount over-counts 5 to 9x for some companies (an 800-person company read 7,137). The cap reads the CRM `NumberOfEmployees` first and the resolved count only when the CRM count is blank (`crm_count_fallback`), so grade, segment and eligibility read the same number. In one run 24 of 200 accounts would have been wrongly capped on the LinkedIn count alone |
| No usable size | Resolve returned no domain, or an under-10-employee match for a company the team knows is bigger | A wrong match, not a small company. Hold it (`Scoring_Status__c` not `scored`); the carve reports it as `Not eligible: not scored` and it waits for the rerun |

Exclusions run twice on purpose. By default the Score node caps VC/PE firms, GTM agencies and education
institutions at 40 and grades them Low Fit (the opt-in lift raises them instead where they are real
customers), and the carve excludes them again, because another motion owns them. Both rules are
intentional; write both down. See `production-example.md`.

Order matters. The canonical sequence, the same in the rules file, `pool-and-carve.md` and SKILL.md Step 7:
roll-up (local preview only, if `hierarchy.mode` is `family`) → exclude → size → eligibility → protect →
segment → route → deal → overflow. The first rule that decides an account wins. The category goes in
Carve Status (Proposed, Assigned, Protected, Excluded, Not eligible, Unowned); the detail goes in Carve
Reason, as the carve node writes it: `direct competitor`, `partner`, `owned by another team`, `company
type <type>: another motion owns it`, `education / institution domain`, `industry <value>: excluded`,
`non-sellable region (<list entry>)`, `India-heavy (HQ)`, `manager exclusion`, `too big: ...`, `below
minimum size`, `no employee count`, `not scored`, `fit 54 below 60`, `existing owner`, `open
opportunity`, `existing customer`, `rep pick`, `no routing match`, `named account, manager allocation`,
`named account, no rep with capacity`, `<method> deal, <segment> / <sub-region>, rank N of M`, `dynamic
deal, <segment> / <sub-region>: rep with the most room`, `over capacity`, `no rep for segment / region`,
`awaiting draft pick (pick N of M, <segment> / <sub-region>)`; `parent's owner` in the preview's family
mode.
Every account in the proposal has a status and a reason, which is what the FAQ's "why is X not in my
book" points at.

## Decision 5: Hierarchy and multinationals

| Scenario | Rule |
|---|---|
| Parent and subsidiaries | One family, one owner: the parent's owner owns the children; segment by the family's maximum employee count (GitLab's "max family employees" pattern). |
| Divisions sold separately | Treat each operating entity as its own account; subsidiary inherits segment unless an exception is written. |
| Multinational with regional buying centres | Assign by buying-centre location, not HQ. |
| Franchisees | The franchisee is the account; the franchisor is context only. |
| Duplicates and fragmented ownership | Dedupe before carving; a lead or account matching a subsidiary routes to the owner at the top of the family. |

Native CRMs do not traverse hierarchies in assignment rules; the carve has to roll up explicitly.

## Decision 6: Cadence and lifecycle events

| Event | What practitioners do |
|---|---|
| **Annual plan** | Full redesign: segments, capacity, quotas, named lists. |
| **Quarterly recarve** | Default for SaaS: re-run eligibility and the deal; top up books; move accounts whose segment changed. |
| **New account enters** | Scored on arrival by the scoring workflow's "to score" trigger; clears the floor and lands in the "Eligible pool" segment; the carve workflow's segment trigger proposes an owner; the manager approves on the top-up cadence. Both triggers are created as drafts after the first universe is scored and carved, and left unpublished until the team wants them live: publishing scores, or carves, every record in the segment at once. |
| **Rep closes or disqualifies an account** | Account leaves the book; a fresh one is dealt (dynamic) or the gap waits for the next run (static). |
| **Account goes stale** | Retrieve after 15 to 90 days without meaningful activity; rest it before redistributing. Common rule: 4 touches per 90 days to keep an account. |
| **Rep leaves** | Protect active pipeline within 48 hours (temporary owner); reassign the top 20% of the book in week one; hold the rest for the next full run; no active account unassigned for more than a week. |
| **Rep joins** | Ramping reps get smaller or lower-potential books with ramped quota; lock their territory for the ramp; dealing from the pool's best available is the dynamic-book answer. |
| **Mid-quarter swap** | One-for-one, same segment, manager approves, reason recorded. |
| **30-60-90 validation** | After a recarve: engagement and pipeline per rep vs the proposal; keeper-account close rate dropping more than 20% signals a bad handoff. |
| **Communication** | 2 to 4 weeks notice; show the data per rep; phase big moves over two quarters; transition guarantees (a draw) when income drops more than ~10%. |

## Decision 7: Governance

- Rules of engagement written down: who owns, who can prospect where, how credit splits (80/20 primary/support, 50/50, or attribution-based), transition periods.
- Disputes: reps first with a template, then manager and RevOps reading CRM activity, then a single final arbiter. Escalations should be rare.
- Approval before any owner changes; exclusions carry a reason; everything versioned.
- Routing of inbound leads follows the carve: open-opportunity owner beats named owner beats territory rule beats round robin.

## Mapping the scenarios to the rules file

One row per top-level key in the YAML block of `territory-rules-starter.md`, with the sub-keys spelled as
the carve reads them. Defaults are the starter's values.

| Decision | Knob (exact keys) | Default |
|---|---|---|
| Hierarchy | `hierarchy.mode: family \| entity \| buying_centre`; `hierarchy.family_field`; `hierarchy.fallback` | `family` when `ParentId` data exists, else `entity`; `buying_centre` is not implemented in v1 |
| Exclusions | `exclusions: {industries: [], company_types: {entity_types: [...], keywords: [...]}, competitors_field, partner_list: [], education: {entity_type, domains, institutions, edtech_allowed}, regions: [], india_heavy, other_teams: [...], other_teams_field, min_employees, manager_list: {domains: [], block: soft}}`. The carve node applies, in order: `competitors_field` true or a domain on `eligibility.competing_vendors` (`direct competitor`), `partner_list` (`partner`), `other_teams_field` holding a value on `other_teams` (`owned by another team`; skipped when the field is null or absent), `company_types.entity_types` against `Entity_Type__c` (`keywords` are not matched in v1), education domains, `industries`, `regions` (each entry matched against the HQ country code and name; the region names Middle East, CIS, Africa and APAC expand to their country codes), `india_heavy`, then `manager_list` (`manager exclusion`, with "(soft block, approver decides)" when `block` is `soft`) | entity types agency, vc_pe, services_firm, education, government (the enum the research emits); `Is_Competitor__c`; 50 employees; the rest per interview |
| Eligibility | `eligibility: {core_industries: [], competing_vendors: [], threshold, other_industries_gate, gate_inputs}`; `competing_vendors` is the list a prospect would be replacing: it is what `has_competing_vendor` matches in `Tech_Stack__c`, what the Technographics research pins (product ids, result limit no higher than the products scored), and a domain on it is `Excluded: direct competitor`. Only accounts with `Scoring_Status__c` = `scored` are tested; held ones are `Not eligible: not scored` | threshold 60; `core_industries` spelled as the CRM Industry picklist; other industries pass the fit floor or the ops/sales headcount gate; vendor list from interview Q7 |
| Protections | `protections: {open_opportunity: {min_stage, scope: account \| family, field}, active_pursuit: {touches_30d, meeting_days, fields}, rep_picks: {max, source}, customer_owner: {enabled, field, value, owner_not}, partner_registration: {days, field}, churn_cooloff: {months, field}}`; each names its field and is skipped when the org lacks it. The carve node checks, in order: an owner other than the pool owner, an open opportunity on the account, customer owner, then rep picks (`Proposed: rep pick`); the parent's owner and family-wide opportunities apply in the local preview's family mode only | existing owner and parent's owner always on; open opp in the family (`min_stage` is not applied in v1, the roll-up is an unfiltered count); 5 picks; customer owner kept; 8 touches / 60 days, 90 days, 12 months. Pursuit, partner and churn need activity and churn dates the sync does not carry yet; they are skipped and `carve-summary.md` says so |
| Segments | `segments: [{name, min_employees, max_employees, capacity, capacity_bonus: {<REGION>: n}}]` | SA 50 to 350 / 60; SL1/SL2 350 to 3,000 / 50 (+10 EMEA); SL3 over 3,000 / 45. Min inclusive, max exclusive |
| Route-by | `routing.by: [segment, region, sub_region]` (also `country`, `state`, `metro`, `vertical`, `named_list`); `routing.pools_first`; `routing.regions.<REGION>.countries: [codes]`; `routing.regions.<REGION>.sub_regions.<Sub-region>: [states]` or `default`; `routing.regions.<REGION>.pools: [{name, sub_region_value, cities}]`. Regions are tried in file order and an account lands in the first whose `countries` holds its HQ country (code or full name); inside it, pools by HQ city, then the state lists, then `default`. Outside every list: `Unowned: no routing match`. A region with no `countries` list takes everything the regions above it left, so list countries for every region | segment, then region, then sub-region; pools checked first; NAMER = US, CA with US West states listed and US East default, pools SF Bay Area and New York City; EMEA with its country list, Rest of EMEA default and pool London |
| Allocation | `allocation.method: snake \| round_robin \| manager \| dynamic \| draft` (Decision 2 says what the carve node does for each); `allocation.named_accounts: {top_n}`, read only when the method is `manager`, the named tier dealt first within each segment and region and counted against capacity, overrides via the node's `named_overrides_json` input (domain to CRM user id; not wired by the builder yet); `allocation.sort_key: fit_score \| revenue \| propensity`; `allocation.one_run: true` | snake by `fit_score`, `top_n: 0`, whole pool in one run |
| Balance-by | `allocation.balance_on: [count, mean_fit]` (also `revenue`, `workload`, `composition`, not in v1); `composition_targets: {self_serve_share: {<segment>: [low, high]}, core_industry_share}` | count and mean fit; targets 30 to 40% SA, 20 to 25% SL, 70% core, checked not enforced |
| Cadence | `cadence: {recarve, top_up, stale_days, rest_days}` | quarterly, weekly, 90, 30 |
| Governance | `governance: {approver, swap_rule, notice_weeks}` | named approver or channel, `one_for_one_same_segment`, 2 weeks |
| Grade overrides | `overrides: {education: {exclude}, vc_pe: {exclude}, agency: {exclude}, size_cap: {enabled, min_employees, action: Low Fit \| exclude, crm_count_fallback, reason}}`; opt-in lift form `{min_grade, unless_factor_zero}` | education, VC/PE and agency excluded by default: component scores kept, total capped at 40, Low Fit, reason "Excluded by rule"; the lift instead only where those firms are real customers (a PLG team dropped it); `size_cap` off, example 5,000 employees to Low Fit, CRM count first and the resolved headcount only when the CRM count is blank (Decision 4, size rules). Applied when scoring; the carve excludes the same types again (see Decision 4) |
| Size cap | the same `overrides.size_cap` knob read at carve time: `action: exclude` makes capped accounts `Excluded: too big`, `action: Low Fit` makes them `Not eligible: too big` (the Low grade itself comes from the Score node); either way they leave the pool, so no Assigned account carries a Low or Bad Fit grade for size | off; when the shipped scorer is used, add the headcount rule to the Score node so the CRM grade matches |
| Deliverables | `deliverables: {patch_doc, whats_new, faq, approval_channel}`; produced by the propose step, sent to `governance.approver` inside `governance.notice_weeks` | all three on; what's new note, criteria table, FAQ (next section) |

The carve node reads these knobs, `reps.csv` (`crm_user_id` filled) and the scored accounts, and
nothing else; `carve_workflow.py build` bakes the rules and reps into the Territory Carve workflow and
`update` pushes an edit. The workflow writes the proposal (Segment, Sub-region, Carve Status, Carve
Reason, Proposed Owner) to Salesforce and Audiences and never Owner; `carve_summary.py` reads it back
into `carve-summary.md`, `carve-proposal.csv` and `.json`, `write-owners.jsonl` (the Proposed rows) and
`patch-doc.md`; `carve.py` previews the same decisions locally at zero cost. Owners change only when the
Write Owners routine runs that jsonl in bulk after the approver says yes; Claude Code asks the human to
approve that bulk write before it runs. A team that routes by state and recarves monthly changes two
lines; the deal logic is unchanged. Decisions 2 and 3 list options with no knob value (weighted optimizer,
attainment history); they are there so the interview recognises the answer, not because the carve
implements them.

## What production teams ship with the carve

The books are not the deliverable; the explanation is. The worked example in `production-example.md`
shows the shape, and every recarve should ship with:

- **A "what's new" note** at the top, in the reps' language: what changed since last quarter and why
  (model version, weights moved, new inclusions, the floor).
- **A criteria lookup table** reps can read: what is in, what is out, and the one-line reason for each
  rule. Reps get a table, not a spreadsheet.
- **A FAQ** for the questions every carve raises: why is X not in my book, how do I swap, what happens to
  my open deals.
- **A soft manager block**: accounts a manager excluded in a past review stay excluded, with the reason,
  so the same account is not swapped back in next quarter (`exclusions.manager_list`).
- **Floor changes announced**: moving the eligibility threshold (for example 65 to 60 to keep enough
  assignable accounts) is a rules change, not a model change, and is called out in the note before it
  takes effect, inside the `governance.notice_weeks` window.

## Sources

Internal: Clay GTM Rules of Engagement and Q3 Territory Logic (segments, pooled cities, exclusions, approvals, 30-day validation, one-for-one swaps); the Clay territories app (patches, book reshuffle, overrides); the customer POC (flat V1 score misranked accounts, carve across 5 reps).

Web: [Gradient Works, guide to dynamic books](https://www.gradient.works/resources/guide-to-dynamic-books) · [Gradient Works, territory model by sales motion](https://www.gradient.works/blog/sales-territory-models-inside-sales-field-enterprise) · [Mostly Metrics, complete guide to territory planning](https://www.mostlymetrics.com/p/your-complete-guide-to-sales-territory) · [RevOps Co-op, designing territories](https://www.revopscoop.com/post/territory-planning-strategies-tactics) · [Fullcast, territory design](https://www.fullcast.com/content/sales-territory-design/) · [Maptive, rebalancing after a team change](https://www.maptive.com/how-to-rebalance-sales-territories-after-a-team-change/) · [Maptive, fair territory planning](https://www.maptive.com/sales-territory-planning/) · [LeanData, parent-child accounts](https://www.leandata.com/blog/parent-account-salesforce-hierarchy-limitations/) · [LeanData, account-based routing](https://www.leandata.com/blog/account-based-routing-salesforce/) · [Everstage, types of territory](https://www.everstage.com/sales-territory/types-of-sales-territory) · [Humanr, AE-to-account ratio benchmarks](https://www.humanr.ai/intelligence/sales-territory-design-ae-account-ratio-benchmarks-2026) · [Boogieboard, how many accounts should reps carry](https://boogieboard.ai/resources/how-many-accounts-should-you-have-2026-territ/) · [ORM, how many accounts per rep](https://orm-tech.com/blog/how-many-accounts-per-sales-rep/) · [Unifyr, rules of engagement](https://www.unifyr.com/atlas/rules-of-engagement/) · [SalesOptecs, reducing territory disputes](https://salesoptecs.com/article/85) · [Alexander Group, hunter/farmer coverage](https://www.alexandergroup.com/insights/technology-coverage-model-and-hunter-farmer-concepts/) · [OnlineDraft, drafting accounts](https://www.onlinedraft.com/draft-accounts-or-leads) · [Xactly AlignStar](https://xactly.bynder.com/m/67aa09e6e4ae6214/original/Datasheet-AlignStarProductOverviewMin-Alignstar.pdf) · [GitLab handbook, sales operations GTM](https://handbook.gitlab.com/handbook/sales/field-operations/sales-operations/go-to-market/) · [Salesforce, territory assignment rules](https://help.salesforce.com/s/articleView?id=000385116&language=en_US&type=1)
