# Enrichment playbook (Step 3)

How to get each rubric factor's value out of Clay: which source, in what order, what it costs, and how
to emit `<factor>_value`, `<factor>_status` and `<factor>_evidence`. Distilled from production Clay
builds and one real run of this skill. Action keys are the ones that real build used; confirm each exists
in the workspace with the Clay plugin's `workflows-discover-actions` skill before wiring it. Do not take
cost from the catalog: its price is a floor for tool nodes and meaningless for Claygent nodes. The number
to quote comes from the per-node credit breakdown of the test runs (see "Cost per account").

## Action keys confirmed in a real build (2026-10)

Workflow nodes use Clay's first-party "Companies, People, Jobs" actions where tables used Mixrank keys.
Confirmed working: `cpj-enrich-company-v2` (resolve; input `company_identifier`),
`cpj-get-counts-for-profiles-v2` (headcount by `job_functions` or by `job_title_keywords` with
`job_title_mode: contain`; returns ONE combined `roleCount` per call, so one call per count you need),
`cpj-find-lists-of-jobs` (open roles by `job_title_keywords`, with `limit`),
`cpj-get-company-employee-growth-v2`, `hg-insights-get-company-tech-stack-v3` (pin `product_ids` or exact
product names with a `limit`; see Technographics),
`upsert-audiences-record`, and for Salesforce `update-object` (inputs `recordId`, `object_type`,
`object_fields` by API name, `removeNullValues`), `salesforce-lookup-via-soql`,
`salesforce-lookup-record-v2`. Judgment steps are `agent` nodes (Claygent, `claude-haiku-4-5`) with an
`outputSchema` whose enum fields are `select`-typed; they are not `use-ai` tool nodes. Scoring is a
Python code node. If a key is missing, search the catalog by description (Enrich company, Find employee
headcount by criteria, Find active job openings, Find company headcount growth, Verify technology usage).
Table-era names appear below only as "formerly".

## Five rules that apply to every factor

1. **Cheapest reliable source first, stop on a hit.** A waterfall is "first provider that answers",
   not "every provider". The skip-gate for each fallback is `!(prev && prev?.field)`, which covers both
   "never ran" and "ran but empty". In a CLI-built workflow that gate lives in a small conditional or code
   node in front of the step, because tool nodes carry no run condition of their own; a cheap fixed-price
   provider can simply always run, and the gate protects the research step. A Claygent research step is
   the last tier for any factor a provider measures, never the first: a Claygent that finds nothing is the
   most expensive outcome.
2. **Required input is the gate.** A step whose required input is the resolved company only runs when
   the company resolved. No extra run condition needed; an unresolved domain is the hold.
3. **Ran-and-empty is `none`, not `failed`.** Status `failed` is reserved for a step that errored or
   never ran because its input was missing. Status `capped` is a list that hit its result limit before
   the categories you care about were checked. Enum outputs from an agent node are the exception: the
   prompt declares a fallback value per field and that fallback is the not-found answer, so the status
   is `found` and there is no `none` status for enums.
4. **Judgment emits a category plus evidence.** Where no provider measures the value (how they sell,
   business model), a web-research step returns an enum from a fixed list and one evidence phrase.
   It never returns a score and never does arithmetic; the scorer does that.
5. **Some providers charge on a miss.** BuiltWith and HG Insights bill whether or not they find
   anything. HG still runs first for Technographics because it is the only tier reliable on CRMs and
   warehouses, but it bills ~8 data credits per product record returned, not per call, so pin it to the
   products the rubric scores and cap the result (see Technographics); keep it behind the company-resolve
   gate. Every other charge-on-miss tier sits behind HG and runs only if HG errors.

## Step 2 of the workflow: resolve the company (the gate everything hangs on)

| Need | Source | Notes |
|---|---|---|
| Company match from domain: LinkedIn URL, employee count, industry, HQ city/state/country | `cpj-enrich-company-v2` (formerly `enrich-company-with-mixrank-v2`), input `company_identifier` = the domain | One call feeds Headcount (Size), the Sales/Ops denominators, industry and HQ for the rules file. Feed every downstream node the resolved domain coalesced with the trigger domain (`resolved_domain || domain`): a real match can come back without a domain, and a provider node that loses its required input fails the whole run. For a known account whose domain is ambiguous, an optional `linkedin_url` trigger input that Resolve prefers over the domain fixes the match (a bare domain once resolved to a product sub-brand with 14 staff and every factor scored the wrong company). No match = `failed` for every downstream factor; hold the account. A wrong match is also a hold, never a `found`: a resolved record with no domain, or an employee count under 10 when the CRM count says 50 or more, is a different company; emit `failed` with "Held: Resolve failed (likely the wrong company)" and score nothing. Put the resolved count next to the CRM count in the Step 4 table so a wrong match shows before the universe runs. The Salesforce Account Id for the write-back is not on the synced record; Step 6 adds a `salesforce-lookup-via-soql` node on Website that finds it (see `build-and-test.md`) unless the Audiences source maps `Id`. |
| Industry mapped to the rules' groups | small `use-ai` classifier (no web, `claude-haiku-4-5`) over the provider industry + description, enum = the rules file's industry list | Only if the provider industry is too coarse for the eligibility table. |
| Company type and status | fold into the classification agent call (below): `entity_type` enum (`operating_company`, `agency`, `services_firm` for IT services, consultancies, system integrators, MSPs and staff augmentation, `vc_pe`, `education`, `government`) and `status` (`active`, `acquired`, `inactive`) | Feeds overrides and the carve exclusions. Run this call before the fundraising step and skip fundraising research for `vc_pe`, `education` and `government` (the scorer already knows their band). Note the two decisions are different: VC firms and GTM agencies score high by design AND are excluded from the carve because another motion owns them; both rules are intentional. Gate everything else on status not inactive when the universe has many defunct entities. Optional zero-cost pre-gate: a code node sets `entity_type = education` for `.edu` and `.ac.*` domains and skips both agent calls. |

## Per factor

### Technographics (CRM + warehouse + competing vendor)

This is targeted detection of named tools, not a full stack map. Lead with the provider that is
reliable on back-office SaaS; HTML scrapers miss CRMs and warehouses because those tools do not drop a
pixel on the marketing site. The real build is one HG call, no waterfall. HG bills per product record
returned, so the pin list and the result limit on this one node are the cost of this factor and, in four
200-account runs, 60 to 90% of the cost of the whole workflow.

| Order | Source | Measured cost | Notes |
|---|---|---|---|
| 1 | HG Insights (`hg-insights-get-company-tech-stack-v3`, formerly `hg-insights-get-company-tech-stack-v2`) | ~8 data credits per product record returned, so the ceiling is 8 x `limit` (96 at a limit of 12); most companies return 0 to 3 records against a tight pin, large software companies a full page; plus ~1 action credit | Pin the call to the specific products the rubric scores and set `limit` to at most 12 (the number of pinned products when that is smaller). Prefer `product_ids`, resolved from the action's `product_ids` dynamic-field list (`clay workflows actions dynamic-fields`; search by name only to find the ids). Exact product names work for single-product vendors. Do not pin `vendor_names`: it is a substring match (SAP pulls in Sapient, Alloy pulls in AlloyDB, FIS pulls in AWS FIS), and a multi-product vendor (SAP, Oracle, IBM, Microsoft, Amazon, Google, GitHub) returns Java, databases and Concur at 8 credits each without ever naming the ERP or the CRM. Semantic or category search returns the same noise. Match the returned names deterministically in the code node against the pinned list (lowercase exact, or substring only where the pinned name is unambiguous); no consolidation LLM. The four runs pinned 10 to 34 products with limits of 12 to 14. |
| Fallback, only if HG errors | BuiltWith (`lookup-technology-stack-new`, charges on miss) then a job-postings scan (`cpj-find-lists-of-jobs`, `job_title_keywords` = tool names; "Experience with Snowflake" in a JD is medium-confidence evidence) | catalog base only, unmeasured | Skip-gate on HG `success` false, not on HG empty. An empty clean HG result is an answer. |

Emit: `value` = `crm+dw+competitor`, `crm+dw`, `one`, or `none` from the matched booleans;
`status` = `found` whenever HG returned (an empty product list is still `found` with value `none`, the
none band), `failed` only if HG (and any fallback) errored; `evidence` = the product names seen ("Salesforce,
Snowflake, ZoomInfo"). A full page at the `limit` is not a hold: with a pinned list every record is a scored
product, so an unseen record can only add a category; map a full page to the top band with "(capped)" in the
evidence (`scoring-rules.md` rule 3). Cost: 0 to 8 x `limit` data credits per account, driven by how many of
the pinned products the company runs.

### GTM Motion and Business Model (one research call for both)

No provider measures these. One Claygent `agent` node (`claude-haiku-4-5`) answers both plus
`entity_type` and `status`, which is the only reason the cost is bearable; never split it. Prompt shape:
a visible step budget (at most 6 web actions), the domain first (pricing page, signup or "book a demo"
flow, product pages), one search for the LinkedIn page, one acquisition search only if the site hints at
a parent brand, no news, blogs, review sites or directories. Return `gtm_motion` in {hybrid, plg,
sales_led, early}, `business_model` in {b2b, b2b+b2c, b2c}, `business_model_flags` subset of {saas,
non_saas, ai_native}, `entity_type` in {operating_company, agency, services_firm, vc_pe, education,
government}, `status` in {active, acquired, inactive}, and one `evidence` sentence each. Declare the
enums as `select` outputs with a fallback value per field (early, b2b, operating_company, active); the
fallback is the not-found answer, so an enum field is never an empty string. Only the free-text evidence
fields may be empty, and "budget reached" goes in the evidence when a fallback was used for that reason.
List every enum value; show the JSON concretely. The capped prompt is in `references/research-prompts.md`.

Emit: `gtm_motion_value` and `business_model_value` from the enums, `business_model_flags` as a
comma-separated string; `status` = `found` whenever the agent returned (a fallback value is still
`found`), `failed` only if the agent node itself errored. There is no `none` status here. Cost: with the
capped prompt in `references/research-prompts.md`, ~1 to 2 data credits per account across four
200-account runs. The uncapped first build measured 6 to 19 web steps at ~2 to 4 credits per step, which
is why the step budget stays in the prompt; it is a guardrail now, not the lever.

### Sales Team and Ops Team (functional headcount)

| Order | Source | Notes |
|---|---|---|
| 1 | `cpj-get-counts-for-profiles-v2` (formerly `get-counts-for-profiles-with-mixrank`), one call with `job_functions` = Sales, a second call with `job_title_keywords` and `job_title_mode: contain` for Ops | Count-only, ~1 action credit each; each call returns ONE combined `roleCount`. Ops title keywords: "Revenue Operations", "Sales Operations", "RevOps", "GTM Operations", "Marketing Operations", "GTM Engineer". Multi-word titles only; a bare "operations" sweeps in warehouse staff. |
| 2 | Denominator for the ratio rule | employee count from the company match (Step 2). Clay's covered slice undercounts the LinkedIn population, so a ratio near the threshold is a judgment call: say so in the evidence. |
| 3 | Open SDR roles (`cpj-find-lists-of-jobs`, formerly `find-lists-of-jobs-with-mixrank`; `job_title_keywords` = SDR, Sales Development Representative, BDR, Business Development Representative; `limit` at least 20) | ~1 action credit. 20 or more open SDR roles maps Sales Team to the top band (100) regardless of the count; a page that comes back at its limit is that top band with "(capped)" in the evidence (`scoring-rules.md` rule 3). |
| Note | GTM Engineer hired | In the real build this is an Ops Team signal: "GTM Engineer" is one of the Ops title keywords, so the combined Ops count already includes it. Do not add a Sales-side count for it. |

Emit: Sales `value` = the count, or `max(count, 50)` when sales headcount is 5% or more of employees
(the ratio rule), or the top band when 20+ SDR roles are open; write the convention in `rubric.md`.
Ops `value` = the combined count. `status` = `found` for any count including 0 (0 is the none band),
`failed` only if the count call errored or the company match failed; `evidence` = "293 in sales of
1,609; 4 open SDR/BDR roles".

### Headcount Growth (12 months)

| Order | Source | Notes |
|---|---|---|
| 1 | `cpj-get-company-employee-growth-v2` (formerly `get-company-employee-growth-with-mixrank`) | Returns `percent_employee_growth_over_last_12_months` directly. ~1 action credit. Prefer this over two snapshots and a subtraction. |
| 2 | PDL `enrich-company` (`employee_count_by_month`) or Harmonic headcount series | Optional fallback when 1 returns null; confirm the key first. |

Emit: `value` = the percent; `status` = `none` if every source returned null (the rubric's unknown
band, 10); `evidence` = "+40.5% YoY". The percent can be absurd on a tiny base (a +39,800% value was real
and overflowed a Number(5,1) field): the CRM field that receives it must be Number(7,1), and the scorer
clamps what it writes rather than letting the write fail.

### Fundraising

Fixed-price providers first, research last, and no research at all for a company that cannot have a
round to find. The first build ran the research agent first for every account and it was the most variable
node in the workflow (3 to 29 web steps); a company with no round to find is the worst case, because the
agent keeps searching, and a public company is worse still, because it finds only IPO history, answers in
prose and fails the run. With the gate below and the capped prompt the agent costs ~1 to 2 credits on the
accounts it still runs for.

| Order | Source | Measured cost | Notes |
|---|---|---|---|
| 0 | Gate on the classification call and on the providers | none | Skip this factor's lookups entirely when `entity_type` is `vc_pe` (the scorer sets value `-1`, band 80), `education` or `government` (overridden anyway), or `status` is `inactive`. Skip the research step (row 2) when a provider reports the company as public or exited (Harmonic `fundingStage` EXITED, IPO or PUBLIC, or a date-only exit round; but EXITED on a company the classification calls *acquired* is an acquired-but-private subsidiary, which still scores its own last round, measured on dbt Labs under Fivetran, 28 Oct): score the date-only round in the older band and never send a public company to the agent. Let the rubric name any other entity type that never raises (banks and credit unions for a fintech seller) and skip those too. Tool nodes carry no run condition, so the providers simply run (cheap and flat) and one conditional or code node in front of the agent decides whether it runs. |
| 1 | The configured fixed-price providers, cheapest first: `intellizence-get-fundraising-data`, `harmonic-get-fundraising-data`, `dealroom-get-fundraising-data`, `crunchbase-enrich-company-latest-funding-round` | catalog 3 to 10 credits each, one step, flat (Intellizence ~3 and Harmonic ~4 measured) | Confirm which are configured with `workflows-discover-actions`. They are flat-priced and tool nodes carry no run condition, so let the configured ones run and pick, in the code node and in this order, the first that returned a round with a name and either an amount or a date. |
| 2 | Claygent funding research (`agent` node, `claude-haiku-4-5`) returning `funding_found`, `round_name`, `amount_usd`, `round_date`, `evidence` | ~1 to 2 data credits per account with the capped prompt (the uncapped first build measured 3 to 29 steps at ~2 to 4 credits per step, 6 to 116 per account); budget 8 steps | Only when every provider in 1 returned nothing or they disagree, and row 0 did not skip it. Step budget, a source whitelist (company newsroom, Crunchbase, PitchBook, SEC, named outlets) and an early-exit rule; the prompt must handle investor-vs-investee (a VC investing is not the VC raising) and must report the real older round when it rejects a re-posted "newer" one. It must answer in the schema JSON even when sources conflict, the company is public or nothing was found (`funding_found` false, evidence "Public company (exchange:ticker)"): a prose answer fails the node and the whole run with it, and every funding failure in four runs was a conflicting-source or public-company case. Prompt in `references/research-prompts.md`. |

Normalize the round name in the code node so "Series B" reads the same from every provider. Emit:
`value` = last round amount in USD if its date is within 18 months, else `1` (lands in band 40, the
"older or smaller" band; write this convention in `rubric.md` and nowhere else differently); `status` =
`none` when no source finds a round (public or bootstrapped companies score 0 here by design, or add an
override); `evidence` = "Series F, $150M, Jun 2025". Sandbox note: the code node has no `datetime`
module; compute the 18-month window from `time.time()` and a days-from-civil-date helper as the
reference node does.

### Headcount (Size)

`value` = employee count from the company match; optional fallback PDL or HG `enrich-company`.
LinkedIn counts over-count via alumni and shared company pages, by 5 to 9x for some companies (one
800-person company read 7,137), which is tolerable for a size band but not for a size rule. Any "too big"
rule (5,000+ employees becomes Low Fit or is excluded) and any minimum-size eligibility must read the CRM
employee count when it exists and fall back to the resolved count only when the CRM has none; write the rule
that way in `territory-rules.md`, carry both counts into the Step 4 table, and name the count the grade used
in the reason line, or the scorer and the carve will disagree on who is too big. Under-counting is the other
failure: an under-10 count for a known company is a wrong match (see the resolve row), not a small company.
`status` = `none` when the company
resolved but no source returned an employee count (the rubric's none band, not a hold); `failed` only if
the company did not resolve, and that account is already held at Step 2. A resolved company must never
be held for a missing headcount.

## Adding a factor the template does not have

1. Write the data need in one sentence ("how many support conversations they handle").
2. Ask whether a provider measures it: `clay routines list`, then `clay routines get` for cost, or
   the `workflows-discover-actions` skill. If yes, it is a waterfall like the ones above.
3. If no provider measures it, pick a public proxy (FAQ size, number of products, length of terms of
   service, support channels listed) and write a Claygent research step that returns an enum from a
   fixed list plus evidence. Step budget first, domain first, then whitelisted third-party sources; a
   declared fallback value for each enum, empty string only for evidence; show the JSON. Use
   `claude-haiku-4-5`; move to a Sonnet-class model only for multilingual or niche sites. Fold the
   enum into the existing classification call if the same pages answer it.
4. Add the factor to the JSON block in `rubric.md` with its kind, bands or map, and a none band.
5. Test on the five known accounts before anyone else sees it.

## Cost per account

Measured across four 200-account runs with the capped prompts and a pinned HG call: 18 to 73 data credits
per account on average (18 with HG pinned to ~34 ERP and maintenance product ids that most companies do not
run, 45 and 62 for compliance and CRM-plus-warehouse stacks, 73 for a developer-tools stack that most of the
universe runs), plus ~1 action credit per tool node (six to nine). Where it goes: HG Insights 60 to 90% of
the data credits, billed ~8 per product record returned (0 to 3 records for most companies, a full page of
12 to 14 for the large software companies); the classification Claygent ~1 to 2; the funding Claygent ~1 to
2 on the accounts it still runs for; the fixed-price funding providers 3 to 4 each; every other tool node
~1 action credit. Catalog prices are wrong in both directions (HG is listed as one call, Claygent as
unbounded), and the earlier "~85, mostly Claygent" story was wrong too: once the prompts were capped the two
agent nodes were not the spend. Test runs bill exactly like live runs.

So: never quote a catalog number or this page. Read the balance with `clay credits balance` before the
first test run, run the five known accounts, read the per-node credit breakdown from the run analysis
(`clay workflows runs analysis`, or the verbose run view node by node), and state the per-account figure
(min, typical, max) and the full-run total before Step 6, naming the top node. Tune the node at the top of
that table, which will be HG. Four levers move the number, in order of effect:

1. **Pin HG to the products the rubric scores** (`product_ids` resolved from the action's dynamic-field
   list, or exact product names for single-product vendors) and set `limit` to the number of pinned
   products, at most 12. The ceiling per account is 8 x `limit`. Narrowing a vendor pin to ten specific
   products took one run's mean from 105 to 57 credits without changing a grade.
2. **Skip research by entity type and public status**: no fundraising research for `vc_pe`, `education`,
   `government`, `inactive`, or any company a provider reports as EXITED, IPO or PUBLIC; the scorer already
   knows the band, and the agent fails on a public company anyway.
3. **Providers-first funding**: the fixed-price providers run before the research agent, which then
   runs only on the accounts they could not answer.
4. **Step budget** in each agent prompt (6 for classification, 8 for fundraising), with a source
   whitelist and an early-exit rule, and the fallback value when the budget is hit. This is what keeps
   the Claygent nodes at ~1 to 2 credits; keep it, but no further savings live there.

Model choice and gating HG behind cheaper tiers do not move the measured cost. Target: under ~45 data
credits per account when the pinned products are back-office tools few companies run; expect more when the
rubric scores tools most of the universe runs (developer tooling, cloud). Confirm it from the runs, not
from this page.

## Prompt shape for any research step

Context and role in one line; the inputs by name; a visible step budget; a methodology with the domain
visited first; the classification logic with every allowed value listed and a fallback per enum; five
to ten edge cases with the expected output; the output JSON shown with real example values; the
not-found rule stated plainly (fallback values for enums, empty string only for evidence); an
`evidence` field in every object. Model: `claude-haiku-4-5` by default. Use an `agent` node for
anything that needs the web and plain `use-ai` for classification over text you already have. Never ask
the model to compute a weighted sum.

Cost constraints every web-research prompt must carry, because each search or page load bills ~2 to 4
data credits, the CLI exposes no per-node step limit, and these constraints are the reason the two agent
nodes measure ~1 to 2 credits per account instead of 12 to 116:

- **Step budget** as a number of web actions (searches plus page loads): 6 for classification, 8 for
  fundraising. On reaching it, return the best answer so far using the declared fallback and write
  "budget reached" in evidence.
- **Source whitelist** as an ordered list the agent may open, and an explicit "do not open any other
  site, including sales-intelligence directories and auto-generated company profiles". Forbidding beats
  down-weighting because it removes the steps, not just the answer.
- **Early exit**: stop at the first whitelisted source that answers; corroborate only when the first is
  ambiguous.
- **One call per set of pages**: every enum the rubric needs from the same pages (motion, model, flags,
  entity type, status) comes from one call.
- **Ask only for what the rubric scores**: for fundraising, the most recent verified round with amount
  and date, nothing more once one is found.
- **Strict JSON, always**: the schema answer even when sources conflict, the company is public, or nothing
  was found. A prose answer fails the node and the whole run with it.

Worked, step-budgeted versions of both prompts are in `references/research-prompts.md`.
