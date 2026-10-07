# Growth mechanics — action contract, payload shapes, surfaces, interpretation

Live-verified mechanics 2026-08-12 (isolated eval workspace); re-verify per
workspace — costs, action keys, and payload shapes drift on this platform.

## The action contract (live)

| Fact | Value (live-verified) |
|---|---|
| Display name | **Find Company Headcount Growth** (package "Companies, People, Jobs") |
| Action key | `cpj-get-company-employee-growth` — DRIFTED from the older `get-company-employee-growth-with-mixrank`; find it by display name in the catalog dump, then use the key + packageId the dump gives you |
| Inputs (all optional, ≥1 required) | `url` (Company LinkedIn URL — "Highest Accuracy") · `org_id` (LinkedIn company ID / Sales Nav URL) · `website` (domain — "Lower Accuracy"; used only when the URL arm is absent/fails) |
| Cost | 1 credit per run — **misses bill the same 1 credit as hits** |
| Outputs | `name`, `url`, `domain`, `employee_count`, and per-window pairs: `employee_count_{N}_month(s)_ago` + `percent_employee_growth_over_last_{N}_month(s)` for N ∈ 1, 3, 6, 9, 12, 24, 36, 48, 60 |

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

**One-time workflow build — TWO single-arm workflows** (CLI + the plugin's
workflow tools). Build one URL-arm workflow and one domain-arm workflow; route
each row to the arm matching the identifier it has:

1. `clay workflows create --name "<yours>"` — created workflows are
   trigger-less.
2. Add a manual trigger via the plugin's trigger-edit tool (`triggerType:
   manual`, inputSchema with ONE required field: `{url}` for the URL-arm
   workflow, `{website}` for the domain-arm) — this is the only call that
   creates a runnable trigger node.
3. Read the workflow back (the plugin's workflow-read tool, summary mode) to
   get the trigger's `wfn_…` node id — the trigger-create response returns
   only a UUID resourceId, not the node id you wire edges from.
4. Add a tool node wired from that trigger node id: tool = the growth action;
   map the one arm as a reference (`{{url}}` or `{{website}}`) and map the
   OTHER arm as `skip` — never leave it referencing a variable the trigger
   doesn't carry.
5. Run per company: `echo '{"url":"..."}' |
   clay workflows runs test <wf> --inputs -` → poll
   `clay workflows runs get <wf> <runId> --wait 60 --verbose` → the tool
   node's `outputs.result` is the payload; run-level `dataCreditsUsed` is the
   measured cost.

**Why single-arm (live-verified the hard way)**: the action VALIDATES its
`url` input and HARD-FAILS on a non-LinkedIn value (`ERROR_INVALID_INPUT —
Input URL is not a LinkedIn company page`) — despite the schema's own prose
claiming it "only uses the company domain if we need it". There is no
domain-in-`url` fallback; a both-fields workflow fed a domain in `url` fails
the run (billed 0, but wasted). Schema descriptions are marketing; runtime
validation is the contract. Pinned-input discipline still applies: every
mapped reference must be present and non-empty in every run's inputs
(undefined AND `""` both fail the run).

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
