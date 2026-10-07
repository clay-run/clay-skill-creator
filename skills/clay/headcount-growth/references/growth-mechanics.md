# Growth mechanics — action contract, payload shapes, surfaces, interpretation

Re-verified live **2026-10-07**; re-verify per workspace — costs, action keys and
payload shapes drift on this platform. **The action was versioned to `-v2` between
2026-08 and 2026-10, and its input contract changed with it**, which is what this
table is for.

## The action contract (live)

| Fact | Value (live-verified 2026-10-07) |
|---|---|
| Display name | **Find company headcount growth** (package "Companies, People, Jobs") |
| Action key | `cpj-get-company-employee-growth-v2`, package `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2`. It has drifted twice now — from `get-company-employee-growth-with-mixrank`, then to this `-v2`. Resolve it by display name from the catalogue dump and take the key **and** packageId from there rather than trusting this cell |
| Inputs | **one identifier field, not three.** `company_identifier` (**required**) and `company_identifier_type` (optional, one of `clay_company_id` / `company_linkedin_url` / `company_domain`). **Left empty, the type is inferred from the value:** a profile URL reads as a social URL, a whole number as a Clay company id, anything else as a domain |
| Cost | **0.5 credits per run** — halved from the 1 credit measured in 2026-08. A not-found still bills; an invalid identifier does not |
| Outputs | `name`, `url`, `domain`, `employee_count`, **`clay_company_id`**, and per-window pairs: `employee_count_{N}_month(s)_ago` + `percent_employee_growth_over_last_{N}_month(s)` for N ∈ 1, 3, 6, 9, 12, 24, 36, 48, 60 |

**Measured on shopify.com, 2026-10-07:** `employee_count` 30,135; the 1-month
window came back `null` while 3/6/9/12/24/36/48/60 all carried values — so a null
window is an absent snapshot and not a zero, even on a company this well covered.

Catalog lookup: `clay workflows actions list` (dump, grep by display name) →
`clay workflows actions schema <packageId> <actionKey>` for the input schema.
**Confusable warning**: the catalog also carries a Lusha action named "Find
company headcount growth signal" at **8 credits/run** — an 8× near-namesake.
Match the package ("Companies, People, Jobs") and the key prefix (`cpj-`),
never the display name alone.

## Payload shapes (all three, live-pinned)

**Hit** — numeric values (real numbers, not band strings):

```json
{ "success": true, "isTerminal": true,
  "result": {
    "url": "https://www.linkedin.com/company/acme-robotics",
    "name": "Acme Robotics",
    "employee_count": 412,
    "employee_count_3_months_ago": 398,
    "employee_count_12_months_ago": 300,
    "percent_employee_growth_over_last_3_months": 3.52,
    "percent_employee_growth_over_last_12_months": 37.33,
    "employee_count_1_month_ago": null,
    "percent_employee_growth_over_last_1_month": null } }
```

- The result's `name`/`url` echo the entity the action MATCHED — the entity
  check compares them against the company you asked about. This echo is the
  wrong-entity detector; it matters most on domain-arm rows. Compare the asked
  identity's registrable LABEL (and name words), NEVER its TLD — a token like
  `com` substring-matches "company" in every LinkedIn URL and washes out the
  check. Shared-stem collisions (asked `meridianfintech.example`, matched "Meridian
  Health Group") are exactly what the check exists to catch: disjoint echo →
  wrong-entity flag; partial-stem overlap → judgment, say why you accepted it.
- **Per-window nulls occur inside healthy hits** (1-month and the oldest
  windows are null even for large public companies). Null window = no
  snapshot, never 0%.

**Miss** — the empty-success shape:

```json
{ "success": true, "isTerminal": true, "result": {} }
```

Run status `completed`, `success: true`, empty `result`; the only readable
signal is a "❌ Company Not Found" text preview. Gate on payload VALUES
(`result.employee_count` present and numeric), never on run status. The credit
is spent either way — count misses in delivered cost.

**Wrong-entity hit** — shaped exactly like a hit; only the entity echo betrays
it. There is no error channel for "found a different company".

## Surfaces (quota-aware routing)

| Surface | When | Notes |
|---|---|---|
| Ad-hoc action execution (`execute_clay_action` MCP tool) | small lists (≤20 companies) | 25 test-runs/day per WORKSPACE quota, shared with everything else ad-hoc that day; hitting it blocks for ~a day |
| Workflow surface | batches, or when the ad-hoc quota is spent | free of the ad-hoc quota; one-time build below |

**One-time workflow build — ONE workflow** (the growth action now takes a single
identifier, so the two single-arm workflows the 2026-08 build needed are obsolete;
delete them rather than maintaining them).

1. `clay workflows create --name "<yours>"` — created workflows are trigger-less.
   A workspace with no budgets can still create and run drafts.
2. `clay workflows triggers create <wf> --input '{"triggerType":"manual",
   "inputSchema":{"type":"object","properties":{"company_identifier":{"type":"string"}}}}'`
   — `inputSchema` needs `type` AND `properties` or it is rejected. The response
   carries `workflowNodeId` (`wfn_…`), which is the id you wire edges from; the
   `resourceId` UUID is not.
3. Add the tool node wired from that trigger node:
   `clay workflows nodes insert <wf> --input '{"target":{"type":"after-node",
   "nodeId":"<trigger wfn_…>"},"step":{"kind":"action","actionPackageId":
   "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2","actionKey":
   "cpj-get-company-employee-growth-v2","name":"growth"}}'`.
   A tool node's `inputSchema` is **not writable** — it takes its inputs from
   upstream fields matching by NAME, so a code node feeding it must emit
   `company_identifier` (and `company_identifier_type` if you are setting it).
4. Run per company: `clay workflows runs test <wf> --inputs
   '{"company_identifier":"acme.com"}'`. **Every run returns
   `approval_required` with an `aar_…` id and spends nothing until
   `clay approvals approve <aar_…>` is called** — so a batch driver has to
   handle that, and an unattended schedule needs that question answered first.
   Then `clay workflows runs steps <wf> <runId>` → the tool step's
   `stepOutputs.result` is the payload; run-level `dataCreditsUsed` is the
   measured cost.

**What changed, and why the old rationale is gone**: the 2026-08 action validated a
separate `url` field and hard-failed on a non-profile value, which is why two
single-arm workflows existed. The v2 action has one `company_identifier` and infers
the type, so there is no wrong field to put a domain in. The empty-pin rule is also
retired — an empty pin now arrives as `""` and a missing path as `None`, and neither
fails the run. What still holds: a **required** input that is absent fails the step
outright, and a failed step fails the run.

## Interpretation rules (deterministic — code, not judgment)

```javascript
// Bucket (12-month window default; KB vocabulary)
pct < 0    → "shrinking"
0 ≤ pct 10 → "flat"
10 ≤ pct 30 → "growing"
30 ≤ pct 100 → "high-growth"
pct ≥ 100  → "hyper-growth"

// Denominator gate — base = the window's backdated count
base < 50  → verdict carries "(micro-base: X→Y)"; the bucket label NEVER
             ships alone; sort/filter on absolute delta for micro-base rows

// Trajectory (short window S = 3mo, long window L = 12mo; both non-null)
// L/4 ≈ the year's average quarterly rate — S compares against it
L ≥ 10 && S < 0            → "reversing"   (grew over the year, shrinking now)
L ≥ 10 && S > L/2          → "accelerating" (last quarter is running ≥2x the
                             year's average quarterly pace — speed-ups are a
                             verdict too, not just slowdowns)
L ≥ 10 && 0 ≤ S < L/8      → "decelerating"
L < 10 && S ≥ 2.5          → "inflecting up"
otherwise                  → "steady <bucket>"
S or L null                → trajectory "single-window" — say which window
                             the bucket came from; never infer the missing one
// Backdated-count shape check: when the intermediate counts show a dip-and-
// rebound (12mo > 3mo-ago < now), say so — the windows alone smooth it out.
```

Thresholds are conventions, not truths — state them in the delivery so the
user can re-cut. The un-negotiable parts: base counts travel with every
percentage; two windows before a trajectory word; nulls never coerce to 0.

## Measurement caveats (ship with every delivery)

- Counts are professional-profile presence, not payroll: hourly, offshore,
  contractor-heavy, and franchise workforces undercount badly; consulting
  firms overcount alumni-heavy pages. Growth DIRECTION is more trustworthy
  than the absolute level; cross-provider count disagreement is normal.
- Data persists for dead and acquired companies (the enrichment-presence ≠
  liveness rule): a flat-line on a company with liveness doubts is an
  artifact, not stability — corroborate liveness separately before reading
  stability into it.
- New-hire counts and job postings measure GROSS adds / intent; this action
  measures NET headcount. They diverge exactly when attrition is the story —
  don't substitute one for the other.
