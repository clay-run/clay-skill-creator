# Account Fit Rubric

Version: 1.0 · Owner: <team> · Last change: <date> · <why>

Score each factor 0 to 100 by its rule, multiply by its weight, add them up. That is the Account Fit
Score. Grades: Best Fit 80+, Good Fit 65 to 79, Moderate Fit 50 to 64, Low Fit below 50. Every
account is written with its factor scores, the score, the grade, a one-line reason and this version.

## Factors

| Factor | Weight | Rule (0 to 100) | Data need | Why this weight |
|---|---|---|---|---|
| Technographics | 28 | CRM + warehouse + competing vendor = 100 · CRM + warehouse = 80 · any one = 50 · none = 20 | tech stack | Best predictor of a win: they already buy tools like ours |
| GTM Motion | 20 | hybrid (self-serve + sales) = 100 · self-serve only or sales only = 75 · early = 50 · none found = 50 | how they sell | Our product fits a sales-assisted motion |
| Sales Team | 12 | 50+ reps or 5%+ of headcount = 100 · 20+ open SDR roles = 100 · 10 to 49 = 70 · 1 to 9 = 40 · none = 10 | sales headcount, open SDR roles | The team our buyer runs |
| Headcount Growth | 12 | 30%+ in 12 months = 100 · 15 to 30 = 70 · 5 to 15 = 40 · below 5 or shrinking = 10 · unknown = 10 | headcount now vs 12 months ago | Growing teams buy tooling |
| Fundraising | 10 | 20M+ in last 18 months = 100 · 5M+ = 70 · older or smaller = 40 · VC/PE firm = 80 (flat default, not researched) · none = 0 | last round amount and date | Budget exists |
| Business Model | 10 | B2B = 100 · B2B + B2C = 70 · B2C = 30 · none found = 30; then SaaS +15, non-SaaS -15, AI-native +15, clamp 0 to 100 | business model | Who we sell to |
| Ops Team | 4 | 3+ = 100 · 1 to 2 = 70 · none = 20 · a GTM Engineer hire counts here | ops / RevOps headcount | Someone to run the tool |
| Headcount (Size) | 4 | 0 to 500 employees maps to 0 to 100, capped | employee count | Segment proxy; low weight on purpose |

Weights sum to 100. Retired factors (weight 0) stay listed with the date and reason, and are not scored.

## Machine spec

The scorer reads this block, and so does `sf_setup.py plan` (one Salesforce field per factor, named from `name`).
Keep it in sync with the table; the table is for people.

```json
{
  "version": "1.0",
  "factors": [
    {"id": "technographics", "name": "Technographics", "weight": 28, "kind": "map",
     "map": {"crm+dw+competitor": 100, "crm+dw": 80, "one": 50, "none": 20}},
    {"id": "gtm_motion", "name": "GTM Motion", "weight": 20, "kind": "map",
     "map": {"hybrid": 100, "plg": 75, "sales_led": 75, "early": 50, "none": 50}},
    {"id": "sales_team", "name": "Sales Team", "weight": 12, "kind": "bands",
     "bands": [[50, 100], [10, 70], [1, 40], [0, 10]], "none_score": 10},
    {"id": "headcount_growth", "name": "Headcount Growth", "weight": 12, "kind": "bands",
     "bands": [[30, 100], [15, 70], [5, 40], [-999, 10]], "none_score": 10},
    {"id": "fundraising", "name": "Fundraising", "weight": 10, "kind": "bands",
     "bands": [[20000000, 100], [5000000, 70], [1, 40], [0, 0], [-1, 80]], "none_score": 0},
    {"id": "business_model", "name": "Business Model", "weight": 10, "kind": "map",
     "map": {"b2b": 100, "b2b+b2c": 70, "b2c": 30, "none": 30},
     "modifiers": {"saas": 15, "non_saas": -15, "ai_native": 15}},
    {"id": "ops_team", "name": "Ops Team", "weight": 4, "kind": "bands",
     "bands": [[3, 100], [1, 70], [0, 20]], "none_score": 20},
    {"id": "headcount", "name": "Headcount (Size)", "weight": 4, "kind": "linear",
     "from": 0, "to": 500, "cap": 100, "none_score": 0}
  ]
}
```

Notes for the research step (the scorer only reads numbers, so the research step encodes each rule
as a value that lands in the right band):

- `sales_team` value = the sales headcount, or `max(headcount, 50)` when sales / employees >= 5%, so the
  ratio rule lands in the 100 band. 20+ open SDR roles -> value `9999` (lands in the 100 band). A GTM
  Engineer hire is an Ops Team signal, not a Sales Team one. Bands are read top down, first match wins.
- `ops_team` value = the ops / RevOps headcount, one combined count; GTM Engineer titles count in it.
- `fundraising` value = the last round amount in USD when the round is within 18 months, else `1` (the
  40 band); `-1` for a VC or PE firm (the 80 band, no funding research); `status` = `none` when no round
  is found. The scorer reads bands from the highest minimum down, so a real zero lands in `[0, 0]` and only `-1`
  reaches the 80 band. VC firms, GTM
  agencies and education institutions are capped at 40 and graded Low Fit by default, and the carve
  excludes them again: another motion owns them (the opt-in lift scores them high instead).
- Write any convention you add here so the next run matches.
