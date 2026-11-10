# Territory Rules

Version: 1.0 · Owner: <team> · Applies from: <quarter>

Decides which accounts are eligible, which keep their owner, and how the rest are dealt to reps. Uses
the Account Fit Score from the rubric. Steps run in order; the first that decides an account wins:
exclude → eligibility → protect → segment → route → deal → overflow (under `allocation.method:
manager` the named top-N is dealt first, inside the deal step). When `hierarchy.mode` is `family`, the
family roll-up runs before the first step.

The tables are for people. The YAML block at the end is what the carve node reads: `carve_workflow.py
build --rules territory-rules.md --reps reps.csv` bakes it into the "Territory Carve" workflow (Step 7),
`update` pushes an edit, and `carve.py` reads it for the local preview; keep the two in sync. The
workflow applies every step above per account from the scored fields in Salesforce and writes a
proposal (Proposed Owner, status, reason), never an owner. Every knob is explained in
`carve-scenarios.md`; a filled-in production version is in `production-example.md`.

Statuses below read `Status: reason`. The part before the colon is one of the six `Carve_Status__c`
values (Proposed, Assigned, Protected, Excluded, Not eligible, Unowned); the part after goes in
`Carve_Reason__c`. Proposed becomes Assigned when the approved owner write runs.

Scoring and carving are different decisions. A VC firm or a GTM agency can score Best Fit and still be
excluded here, because another motion owns it. Both rules are intentional; neither is a bug.

## 1. Exclusions (never carved)

| Exclude | Rule |
|---|---|
| Industries | <list, or "industries with zero wins since <date>"> |
| Company types | entity type from the research: agency, vc_pe, services_firm (IT services, consultancies, SIs, MSPs, staff aug), education, government; plus description keywords. Scored normally (VC firms often high); excluded anyway because another motion owns them |
| Competitors | `Is_Competitor__c` = true |
| Partners | domain on `exclusions.partner_list`: Excluded: partner |
| Education | entity type education, or institutions by name. A `.edu` or `.org` domain excludes only when the entity type is not operating_company, so an EdTech company on a `.org` domain stays in |
| Regions | non-sellable; default list: Middle East, Israel, Africa, CIS, Russia, Belarus, Ukraine |
| India-heavy | top country by headcount = India (where applicable) |
| Owned by another team | strategic, Fortune 500, Top-100, PE team, house accounts; read from `exclusions.other_teams_field` (a value on `exclusions.other_teams`), skipped when the field is null or absent: Excluded: owned by another team |
| Too small | under <50> employees: Not eligible: below minimum size |
| Too big | optional, off by default: over <5,000> employees (family max) is Low Fit or excluded, `overrides.size_cap`. Reads the CRM employee count first; the resolved LinkedIn count over-counts 5 to 9x for some companies and is only a fallback when the CRM count is blank. At carve time: Not eligible: too big (action Low Fit) or Excluded: too big (action exclude) |
| Manager exclusions | domains on `exclusions.manager_list`, with the reason. Excluded: manager exclusion; a soft block adds "(soft block, approver decides)" so the approver can put one back |

## 2. Eligibility

| Industry group | Eligible if |
|---|---|
| Core: <list> | Account Fit Score >= threshold (<60>) |
| All other allowed industries | fit >= threshold, or (ops_hc >= 3 and has_competing_vendor and (sales_hc >= 50 or sales_pct >= 5)) |

The threshold lives in one place, `eligibility.threshold`; the gate refers to it by name. `ops_hc` and
`sales_hc` are the Ops and Sales team headcounts from enrichment, `sales_pct` is 100 × sales_hc ÷
employees, and `has_competing_vendor` is true when any vendor on `eligibility.competing_vendors` appears
in the tech-stack field. Fill that list from the interview (the vendors a prospect would be replacing);
it is also the list the Technographics research pins. A company whose own domain is on it is excluded
as a direct competitor. `core_industries` are matched against the CRM Industry picklist values, so spell
them as the org does.

## 3. Protections (keep current owner) and cool-offs

Each protection names the CRM field it reads. If the field is not in the org, the protection is skipped
and the proposal says so.

| Keep when | Needs | Status |
|---|---|---|
| owner is anyone other than the user who imported the accounts | `OwnerId` (always present) | Protected: existing owner |
| the family's ultimate parent has such an owner (`hierarchy.mode` family; local preview only, the Clay carve node is entity mode) | `ParentId`, `OwnerId` | Protected: parent's owner |
| open opportunity on the account (or in its family, local preview only) | `Open_Opportunities__c` (created by `sf_setup.py`). The roll-up is an unfiltered count, so `min_stage` is not applied in v1: any open opp protects | Protected: open opportunity |
| active pursuit: <8> touches in 30 days or a meeting in the last <60> days | `LastActivityDate`, a meeting-date field; skip if absent | Protected: active pursuit |
| on the rep's protected list (max <5> per rep, `protections.rep_picks.max`; later entries are ignored) | `protected_domains` in `reps.csv` | Proposed: rep pick |
| existing customer with a relationship owner | `Type` = Customer and an owner other than the import user | Protected: existing customer |
| partner-registered within <90> days | `Deal_Registration_Date__c`; skip if absent | Protected: partner |
| churned in the last <12> months | `Churn_Date__c`; skip if absent | Excluded: churn cool-off |

## 4. Segments

| Segment | Employees (family max) | Default capacity per rep |
|---|---|---|
| <SA> | 50 to 350 | 60 |
| <SL1 / SL2> | 350 to 3,000 | 50 (+10 EMEA) |
| <SL3> | over 3,000 | 45 |

Capacity precedence, stated once: a `capacity` on the rep's row in `reps.csv` wins; otherwise the
segment default plus any `capacity_bonus` for the rep's region; otherwise derive it (quota ÷ ACV ×
pipeline coverage ÷ opportunity rate). A rep's region is the one in `routing.regions` whose sub-regions
or pools contain the rep's `sub_region`.

## 5. Routing

| Region | Sub-region or pool | Rule |
|---|---|---|
| <NAMER> | countries | HQ country US or CA (`regions.NAMER.countries`); checked before pools and states |
| <NAMER> | US West | <states> |
| <NAMER> | US East | all other US states and DC |
| <NAMER> | Pooled: SF Bay Area | HQ city in San Francisco, Oakland, Berkeley, San Mateo, Redwood City, Palo Alto, Menlo Park, Mountain View, Sunnyvale, San Jose; dealt across every rep of the segment in the region |
| <NAMER> | Pooled: New York City | HQ city in New York, Brooklyn, Queens, Jersey City, Hoboken; dealt across every rep of the segment in the region |
| <EMEA> | countries | HQ country on `regions.EMEA.countries` |
| <EMEA> | Pooled: London | HQ city London; dealt across every EMEA rep of the segment |
| <EMEA> | Rest of EMEA | <sub-regions, language routing> |

Routing tests the country first: an account lands in the first region whose `countries` list holds its
HQ country, and an account outside every list is Unowned: no routing match. Inside the region, pools
are checked before states. An account whose HQ city is on a pool's list gets the pool's Sub-region
value (for example `Pooled: SF Bay Area`); every Sub-region value here must be in the `--subregions`
list given to `sf_setup.py fields`. A region that routes accounts but has no rep in `reps.csv` for the
segment leaves them Unowned: no rep for segment / region; either add the rep or exclude the region.

## 6. Dealing and balance

Method <snake> within each segment and sub-region, from the highest fit down, until each rep reaches
capacity. Balance on <count and mean fit>. Carve the whole pool in one run. Left-over accounts:
Unowned: over capacity.

What each `allocation.method` does in the carve node, exactly (per account, over every scored account in the same segment band and region, against one shared capacity ledger):

| Method | Deal | Notes |
|---|---|---|
| `snake` | sort each segment and sub-region by `sort_key`, deal 1, 2, 3, 3, 2, 1 to reps with room | default; balances mean fit as well as count |
| `round_robin` | same order, fixed rotation 1, 2, 3, 1, 2, 3 | balances count only |
| `manager` | within each segment and region, the top `allocation.named_accounts.top_n` by `sort_key` go first, each to the rep an override names (the node's `named_overrides_json`, domain to CRM user id; not wired by the builder yet) or else the first rep of its segment and sub-region, reason "named account, manager allocation"; the rest by rotation as round robin | named accounts count against capacity; the manager edits the proposal before approval |
| `dynamic` | each account, highest fit first, to the rep with the most remaining capacity | the first carve looks like a static one; what is dynamic is the top-up per `cadence.top_up`, where the carve workflow's segment trigger deals new accounts to whoever has room. Over-capacity accounts stay Unowned by design, and the rep-count gap in the summary is a note, not a proposal |
| `draft` | no owners; marks every pooled account Unowned: awaiting draft pick (pick N of M, segment / sub-region) | record the picks in `protected_domains` in `reps.csv`, set the method for the rest, then `update`, `reset-proposals`, `run` |

`named_accounts` is read only when the method is `manager`; `top_n: 0` means no named tier. Unowned
reasons the carve can write: over capacity, no routing match, no rep for segment / region, named account
with no rep with capacity, awaiting draft pick.

Every Salesforce account has an owner, so "unowned" means `Carve_Status__c` blank or Unowned and the
owner is the user who imported the accounts.

## 7. Composition targets (checked after the carve, not enforced)

Measured across the whole book, self-serve and net-new combined. A self-serve customer is `Type` =
Customer; if the org has no such field the target is reported as not measured.

| Target | <SA> | <SL1 / SL2> | <SL3> |
|---|---|---|---|
| Existing self-serve customers in book | 30 to 40% | 20 to 25% | 20 to 25% |
| Core vs other industries | 70 / 30 | 70 / 30 | 70 / 30 |

## 8. Cadence and governance

Recarve <quarterly>; top up <weekly>; retrieve accounts with no activity for <90> days after a <30>-day
rest. Swaps are one-for-one within a segment, approved by <manager>, reason recorded. <2 to 4> weeks
notice before a recarve takes effect. Approver for books: <name or channel>.

Every carve ships a patch doc: a "what's new" list in the reps' language, the criteria tables above,
and a FAQ (why is X not in my book, how do I swap, what happens to my open deals). `carve_summary.py`
writes the skeleton (`patch-doc.md`) next to `carve-summary.md`, `carve-proposal.csv` and
`write-owners.jsonl` (the Proposed rows); the proposal goes to <approval channel> before any owner
changes, and the owner write is a separate bulk routine run that the human approves. See
`production-example.md` section 5.

## 9. Overrides (grade, not score)

| Account type | Rule |
|---|---|
| Education institution | excluded by default: capped at 40, Low Fit, reason "Excluded by rule" |
| Too big (optional, `overrides.size_cap`) | employees over <5,000> (family max): grade Low Fit in the Score node; at carve time `Not eligible: too big`, or `Excluded: too big` when `action` is `exclude`. CRM `NumberOfEmployees` wins when present; the resolved headcount is the fallback only (`crm_count_fallback: true`), so the grade, the segment and eligibility read the same number |
| VC / PE firm | excluded by default (capped at 40, Low Fit); opt-in lift instead: raise to Best Fit unless a factor is 0, only if VC firms are genuinely good customers for this seller |
| GTM agency | excluded by default (capped at 40, Low Fit); opt-in lift instead, same condition |

Overrides run in the Score step before the write, so the grade in the CRM already reflects them. By default
an excluded type shows Low Fit at 40 or under AND leaves the carve as Excluded (section 1); with the lift
enabled it shows Best Fit and is still excluded. Both are intended. A size disqualifier may be both a Headcount band in the rubric and this override; the
override is what makes the CRM grade say Low. The shipped scorer keys its default overrides by entity
type, so when `size_cap` is enabled, add the headcount rule to the Score node and confirm no Assigned
account carries a Low or Bad Fit grade after the carve.

## Machine spec

## 7. Engagement after the carve (Step 8)

Fit says whether an account belongs in a book; engagement says when to work it. After Write Owners, three
Clay Signals watch the assigned books and the pool, and every event adds points to an **Engagement Score**
next to the fit score, in the CRM and in Audiences. A weekly decay keeps the number about this week.
`engagement.py build` reads the block below; `health` reads `reentry`.

| Signal | Watches | Points | Default filter |
|---|---|---|---|
| Company news and funding (`News`) | assigned books + pool | <25> | fundraising, investment, M&A, executive changes, expansion, product launch, IPO; 3 items per domain; last <30> days |
| GTM leadership hires (`NewHire`) | assigned books + pool | <30> | VP Sales, Head of Sales, CRO, VP/Head of RevOps, Director of Sales, GTM Engineer, Head of Growth; director and up; last <3> months |
| Sales and RevOps job postings (`JobPost`) | assigned books + pool | <15> | SDR, BDR, AE, RevOps, Sales Ops, GTM Engineer; full-time; posted in the last <30> days |

| Rule | Default | Knob |
|---|---|---|
| Cap | 100 | `engagement.cap` |
| Decay | weekly, keep 75% | `engagement.decay` (publish the decay workflow to turn it on) |
| Re-entry | a pool account with engagement >= 40 and fit >= 50 is a candidate again; the carve gates read it | `engagement.reentry` |

Signals are created **Paused**; `engagement.py resume --yes` starts them after the Step 8 gate, because each
event found costs data credits. Owner is never written here: a hot pool account goes through the Step 7
loop (`carve_workflow.py run --only-pool`, summary, approval, Write Owners).

```yaml
version: "1.0"
hierarchy:
  mode: family              # family | entity | buying_centre. Default family when ParentId data exists, else entity
  family_field: ParentId
  fallback: entity
exclusions:
  industries: []
  company_types:            # entity_type values the research emits; scored normally, excluded here because another motion owns them
    entity_types: [agency, vc_pe, services_firm, education, government]
    keywords: [agency, consulting, consultancy, system integrator, managed service, staffing, staff augmentation, outsourcing]
  competitors_field: Is_Competitor__c
  partner_list: []          # domains
  education:
    entity_type: education
    domains: [".edu", ".org"]
    institutions: true      # name match, multi-language
    edtech_allowed: true
  regions: [Middle East, Israel, Africa, CIS, Russia, Belarus, Ukraine]   # non-sellable default; edit per interview
  india_heavy: {enabled: false, rule: top_country_by_headcount, country: India}
  other_teams: [strategic, fortune_500, top_100, pe_team, house]
  other_teams_field: null   # e.g. Type or a picklist that marks them; skip if absent
  min_employees: 50         # keep equal to segments[0].min_employees; below it: "Not eligible: below minimum size"
  manager_list: {domains: [], block: soft}   # soft: flagged in the proposal, the approver decides
eligibility:
  core_industries: []       # spelled as the CRM Industry picklist values
  competing_vendors: []     # vendors a prospect would replace; drives has_competing_vendor and the Technographics pin. A domain on it is itself excluded
  threshold: 60             # the only place the number lives
  other_industries_gate: "fit >= threshold or (ops_hc >= 3 and has_competing_vendor and (sales_hc >= 50 or sales_pct >= 5))"
  gate_inputs:
    ops_hc: Ops_Team_Headcount__c
    sales_hc: Sales_Team_Headcount__c
    sales_pct: "100 * Sales_Team_Headcount__c / NumberOfEmployees"
    has_competing_vendor: "any vendor on eligibility.competing_vendors named in Tech_Stack__c, case-insensitive"
protections:                # each names its field; skipped if the field is absent, and the proposal says so. Existing owner is always on; parent's owner only in the local preview (family mode)
  open_opportunity: {min_stage: 2, scope: family, field: Open_Opportunities__c}   # min_stage not applied in v1: the roll-up is an unfiltered count
  active_pursuit: {touches_30d: 8, meeting_days: 60, fields: [LastActivityDate, Last_Meeting_Date__c], skip_if_absent: true}
  rep_picks: {max: 5, source: "reps.csv protected_domains"}
  customer_owner: {enabled: true, field: Type, value: Customer, owner_not: import_user}
  partner_registration: {days: 90, field: Deal_Registration_Date__c, skip_if_absent: true}
  churn_cooloff: {months: 12, field: Churn_Date__c, skip_if_absent: true}
segments:                   # capacity precedence: reps.csv capacity > capacity + capacity_bonus[rep region] > derived from quota maths
  - {name: SA, min_employees: 50, max_employees: 350, capacity: 60}
  - {name: "SL1/SL2", min_employees: 350, max_employees: 3000, capacity: 50, capacity_bonus: {EMEA: 10}}
  - {name: SL3, min_employees: 3000, capacity: 45}
routing:
  by: [segment, region, sub_region]      # options: country, state, metro, vertical, named_list
  pools_first: true         # an HQ city on a pool list wins over the state rule
  regions:                  # first region whose countries list holds the HQ country wins; outside every list: "Unowned: no routing match"
    NAMER:
      countries: [US, CA]   # BillingCountryCode; add the full names (United States, Canada) if the org has no state and country picklists
      sub_regions:
        US West: [WA, OR, CA, NV, ID, MT, WY, UT, CO, AZ, NM, AK, HI]
        US East: default
      pools:
        - name: SF Bay Area
          sub_region_value: "Pooled: SF Bay Area"
          cities: [San Francisco, Oakland, Berkeley, San Mateo, Redwood City, Palo Alto, Menlo Park, Mountain View, Sunnyvale, San Jose]
        - name: New York City
          sub_region_value: "Pooled: New York City"
          cities: [New York, Brooklyn, Queens, Jersey City, Hoboken]
    EMEA:
      countries: [GB, IE, FR, DE, NL, BE, LU, ES, PT, IT, CH, AT, DK, SE, NO, FI, PL, CZ]   # edit per interview; non-sellable countries belong in exclusions.regions
      sub_regions:
        Rest of EMEA: default
      pools:
        - name: London
          sub_region_value: "Pooled: London"
          cities: [London]
allocation:
  method: snake             # as the carve node deals, per segment band and region with one shared capacity ledger: snake: 1,2,3,3,2,1 by sort_key | round_robin: fixed rotation | manager: named top_n first (within the segment and region), rest by rotation | dynamic: each account to the rep with the most room, the top-up method | draft: marks the pool "Unowned: awaiting draft pick (pick N of M)", no owners
  named_accounts: {top_n: 0}   # read only when method is manager; top_n highest by sort_key dealt first (overrides: the node's named_overrides_json, domain to CRM user id), counted against capacity
  sort_key: fit_score       # fit_score | revenue | propensity (revenue, propensity: not in v1, need a field)
  balance_on: [count, mean_fit]   # count | mean_fit | revenue | workload | composition (last three: not in v1, need a revenue or activity field)
  one_run: true
  unowned_means: "Carve_Status__c blank or Unowned, and OwnerId = the import user"
composition_targets:        # measured across the whole book, self-serve and net-new combined; reported, not enforced
  self_serve_source: {field: Type, value: Customer, skip_if_absent: true}
  self_serve_share: {SA: [0.30, 0.40], "SL1/SL2": [0.20, 0.25], SL3: [0.20, 0.25]}
  core_industry_share: {SA: 0.70, "SL1/SL2": 0.70, SL3: 0.70}
cadence:
  recarve: quarterly
  top_up: weekly
  stale_days: 90
  rest_days: 30
governance:
  approver: "<name or channel>"
  swap_rule: one_for_one_same_segment
  notice_weeks: 2
deliverables:
  patch_doc: true           # criteria tables in the reps' language
  whats_new: true           # changes since last quarter, first
  faq: true                 # why is X not in my book, how do I swap, open deals
  approval_channel: "<Slack channel or name>"
engagement:                 # Step 8, read by engagement.py: signals on the assigned books (and the pool), points per event, weekly decay, re-entry
  segment_name: "Territory books (assigned)"
  watch_pool: true          # the signals also watch the Eligible pool segment from carve/carve-workflow.json, so pool accounts can heat up
  cap: 100
  manual_points: 20         # a test event fired through the manual trigger without a known type
  signals:                  # created Paused; `engagement.py resume --yes` starts them (data credits per event)
    news:      {enabled: true, type: News,    points: 25, schedule: weekly, max_per_domain: 3, lookback_days: 30,
                topics: [Fundraising, Investment, "Merger & Acquisition", Executive Appointment, Executive Change, Business Expansion, New Product Launch, Initial Public Offering]}
    gtm_hires: {enabled: true, type: NewHire, points: 30, schedule: weekly, seniority_floor: director, limit_per_company: 5, lookback_months: 3,
                titles: [VP Sales, VP of Sales, Head of Sales, Chief Revenue Officer, CRO, VP Revenue Operations, Head of Revenue Operations, Director of Sales, GTM Engineer, Head of Growth]}
    job_posts: {enabled: true, type: JobPost, points: 15, schedule: weekly, limit_per_company: 5, max_days_since_posted: 30,
                titles: [SDR, BDR, Sales Development Representative, Business Development Representative, Account Executive, Revenue Operations, RevOps, GTM Engineer, Sales Operations]}
  decay: {enabled: true, every: weekly, keep: 0.75, timezone: "Europe/London"}   # the Decay workflow multiplies the score by keep once a week; a draft until published
  reentry: {min_engagement: 40, min_fit: 50}   # a pool account this hot comes back into the carve gates below the fit floor; `health` lists them
overrides:                  # applied in the Score step (the node reads this block as overrides_json). The same types also sit in exclusions on purpose
  education: {exclude: true}   # keep component scores, cap the total at 40 (cap: N to change), grade Low Fit, reason "Excluded by rule"
  vc_pe: {exclude: true}
  agency: {exclude: true}
  size_cap: {enabled: false, min_employees: 5000, action: Low Fit, crm_count_fallback: true, reason: "too big; sells elsewhere"}   # action: Low Fit | exclude. CRM NumberOfEmployees wins when present; the resolved headcount is only the fallback
  # vc_pe: {min_grade: Best Fit, unless_factor_zero: true}     # opt-in lift instead of exclude: only if VC firms are genuinely good customers for this seller
  # agency: {min_grade: Best Fit, unless_factor_zero: true}    # opt-in lift instead of exclude: same condition for GTM agencies
```

## Open questions

List anything resolved with a default above. Confirm each before production use.
