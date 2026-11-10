# Cost-capped research prompts (the two Claygent nodes)

Measured across four 200-account builds: with the capped prompts below, the two web-research nodes cost
about 1 to 2 data credits each per account. They are not the cost driver; HG Insights is (it bills per
product record returned, see the pinning note below), so tune the HG pin first and the prompts second.
The step budgets still matter: an uncapped prompt ran 19 to 29 steps on some companies and answered in
prose on others. These prompts put a visible step budget, a source whitelist and an early-exit rule on
both, and the fundraising node only runs when the fixed-price providers return nothing usable. Model for
both: `claude-haiku-4-5`. Paste as the agent prompt; keep the
output schema the node already declares, and mark every field in it required, so a prose answer fails at
the node rather than downstream.

## Order of operations that saves the most

1. **Classify first** (one call: motion, model, flags, entity type, status).
2. **Skip fundraising research** when `entity_type` is `vc_pe`, `education` or `government`, or `status` is
   `inactive`: the rubric already knows the answer (VC default band, Bad Fit, hold).
3. **Fixed-price funding providers before research:** the configured providers (Intellizence, Harmonic,
   Dealroom, Crunchbase) cost 3 to 10 credits each and return a round in one step. Run the cheapest
   configured one first; run the research prompt only if they return nothing usable. A provider answer
   with a stage or round name plus an amount or a date counts as a hit, and so does a public or exited
   company (Harmonic stage `EXITED`, `IPO` or `PUBLIC`, even date-only): skip the research and let the
   scorer band it. Public companies answered in prose when researched, which failed the run. A provider
   error is treated as empty, not as a hit. The gate is a conditional or code node in front of the
   Claygent; tool nodes have no per-node run condition.
4. **Technographics, HG pinning:** one HG Insights call per account, pinned to the specific product ids
   (or exact product names) the rubric scores, with `limit` 12 or lower. HG bills about 8 data credits
   per product record returned, not per call, so an unpinned or vendor-level pin that returns a full
   page costs 8 x limit on every account and was 60 to 90% of spend on the overnight runs. Vendor names
   match by substring (an "Alloy" or "FIS" pin pulls in unrelated products), so prefer ids resolved from
   the action's dynamic fields. No fallback tiers unless HG returns an error; a clean empty result is
   the "none" band.

## Classification (target ≤ 6 web steps)

```
You classify one company for a B2B account-fit model. Inputs: domain={{resolved_domain}},
company_name={{resolved_name}}, provider_industry={{resolved_industry}}.

STEP BUDGET: at most 6 web actions in total (page loads and searches). Plan: (1) load https://{{resolved_domain}};
(2) load its pricing page if linked; (3) load its "get started" / "book a demo" / "contact sales" page if linked;
(4) one search: "{{resolved_name}} linkedin" and open the LinkedIn company page; (5) one search:
"{{resolved_name}} acquired OR acquisition" only if the site suggests a parent brand or a rebrand.
Stop as soon as every field below is decided. Do not open news articles, blogs, review sites or directories.
If the domain does not load, use steps 4 and 5 only and say so in evidence.

Decide these fields, each with exactly one listed value:
gtm_motion: "hybrid" (self-serve signup AND a sales path), "plg" (self-serve only), "sales_led" (demo/contact-sales only),
  "early" (pre-launch, coming-soon, or cannot be determined). Fallback: "early".
business_model: "b2b", "b2b+b2c", "b2c". Fallback: "b2b" and say so in evidence.
business_model_flags: comma-separated subset of "saas" (subscription software), "non_saas", "ai_native" (AI is the
  core product). "" when none apply; that is a normal answer, not a failure.
entity_type: "operating_company", "agency" (marketing, creative, GTM or digital agency), "services_firm" (IT services,
  consultancy, system integrator, MSP, staff augmentation), "vc_pe", "education" (a school or university; an EdTech
  company selling to schools is operating_company), "government". Fallback: "operating_company".
status: "active", "acquired" (operating under a new owner; name the acquirer), "inactive" (shut down, parked domain).
  Fallback: "active".

Edge cases: a VC firm's portfolio is not its product (vc_pe, b2b). An agency with a self-serve tool is still an agency
if services are the main business. Acquired but still operating is "acquired", not "inactive".

Evidence: one sentence for gtm_motion + business_model, one for entity_type + status, each naming the page you saw.
If you hit the step budget before deciding a field, use its fallback and write "budget reached" in that evidence.
Never return "Unknown", "N/A" or null for a string field; the fallbacks above are the only not-found values.

Return strict JSON only:
{"gtm_motion": "hybrid", "business_model": "b2b", "business_model_flags": "saas,ai_native", "entity_type": "operating_company",
 "status": "active", "gtm_bm_evidence": "Pricing page shows a free tier and an Enterprise 'Contact sales' plan; per-seat SaaS.",
 "entity_status_evidence": "Independent company per the About page and LinkedIn; no acquisition found."}
```

## Fundraising (target ≤ 8 web steps; runs only when the providers returned nothing)

```
Find the most recent VERIFIED equity round raised BY the company at domain={{resolved_domain}}, name={{resolved_name}}.
A round this company led as an investor does not count. Provider results so far: {{provider_summary}} (may be empty).

STEP BUDGET: at most 8 web actions. Plan, in order, stop at the first source that gives round name, amount and date:
(1) https://{{resolved_domain}}/press, /news, /newsroom or /blog (one load; follow at most one link to a funding post);
(2) one search: "{{resolved_name}} raises series" and open ONLY a result from: the company's own domain, crunchbase.com,
pitchbook.com, sec.gov, techcrunch.com, bloomberg.com, reuters.com, wsj.com, theinformation.com, ft.com, axios.com;
(3) one more search with the year if (2) found nothing.
Do not open sales-intelligence directories, "company profile" sites, or auto-generated company report pages. They are
not sources and they re-label old rounds as new ones.

Verification rule: a round counts only if an allowed source states its name and either the amount or the date. If a
non-allowed page claims a newer round with the SAME amount as an older documented round, it is a re-post: ignore it and
report the documented round. Report the real round even if it is years old; age is handled downstream, not by you.
If allowed sources conflict on the round, amount or date, pick the best-supported round (the one stated by the
best-ranked allowed source in the order above, or by two allowed sources), name the conflict and your choice in
evidence, and still return the JSON below. Never answer in prose, markdown or an explanation outside the JSON, not
even to describe a conflict or a failure; a reply that is not strict JSON fails the run.
Public or exited companies: if the provider summary already says EXITED, IPO or PUBLIC, or the first page you load shows
the company is listed, do no further research. Return funding_found false with evidence "Public company (exchange:ticker)"
and the IPO year if you saw it.

funding_found: true when a verified round of any age exists; false only when every allowed source you checked has
nothing (bootstrapped, public with no private rounds, or an investment fund). Never invent a number or a date.

Return strict JSON only:
{"funding_found": true, "round_name": "Series C", "amount_usd": 150000000, "round_date": "2025-06-15",
 "evidence": "Series C, $150M, June 2025, per the company newsroom and TechCrunch (URLs)."}
When not found: {"funding_found": false, "round_name": "", "amount_usd": null, "round_date": "",
 "evidence": "No equity round found; checked newsroom and one search. Appears bootstrapped."}
When public: {"funding_found": false, "round_name": "", "amount_usd": null, "round_date": "",
 "evidence": "Public company (NASDAQ:TREE), IPO 2000; private rounds not researched."}
Dates: YYYY-MM-DD; if only month and year are known, use the first of the month; if only the year, use YYYY-01-01 and
say so in evidence.
```

## How to tell it is working

On the five known accounts, read the step count and credits per node from the run data (the workflow
`analysis` commands). Targets: classification ≤ 6 steps, fundraising research skipped for most accounts
and ≤ 8 steps when it runs, each research node at ~1 to 2 data credits. Expect the HG node at the top of
the per-node table; measured per-account means ran from about 18 (HG pinned to a short product-id list)
to about 73 (a 20-product pin that filled the page), so quote the measured figure, not a flat prior. If
HG dominates, shorten the pin list or lower its limit. If a prompt blows its budget on a company, the fix
is usually one more allowed source or one more early-exit rule, not a longer prompt.
