# Signal Schema

Every signal in Section 5 is also expressed in this structure. The HTML report and `signals.yaml` are both generated from it, and Account and Refresh modes read it back. Fields marked (required) apply in every run, Clay or not.

## File structure

```yaml
meta:
  seller_company: "NVIDIA"
  seller_domain: "nvidia.com"
  seller_perspective: "NVIDIA Networking sellers prospecting new buyers"
  focus_segment: "manufacturing"
  run_mode: full                  # full | quick
  run_date: 2026-10-07
  backtest_date: 2026-10-07       # null if never back-tested
  clay_mode: public               # off | public | audiences
  icp:                            # filters reused by Refresh mode
    industries: ["Industrial manufacturing", "Automotive"]
    employee_range: [1000, 50000]
    regions: ["North America", "Europe"]
    must_have: ["Operates own data centers or private cloud"]
signals: [ ... ]                  # list of signal objects, fields below
clusters:
  - id: ai_factory_buildout
    name: "The AI Factory Buildout"
    signal_ids: [dc_capex, ml_infra_hiring_surge, liquid_cooling]
board_snapshot:
  run_date: 2026-10-07
  accounts:
    - domain: "example.com"
      name: "Example Corp"
      score: 72
      tier: active
      net_new: true               # null if unknown
      firing: [{ id: ml_infra_hiring_surge, evidence_date: 2026-09-20, evidence_precision: exact }]  # exact | bucket | range
previous_snapshot: null           # Refresh mode moves the old board_snapshot here
```

## Signal fields

```yaml
- id: ml_infra_hiring_surge              # (required) snake_case, unique
  name: "10+ ML infrastructure roles in 30 days"   # (required) matches Section 5 "Signal"
  category: hiring_org_design            # (required) one of the 8 Section 4 categories
  trigger_ref: T3                        # (required) Section 3 trigger it evidences
  buying_stage: consideration            # (required) awareness | consideration | decision
  decay_window_days: 45                  # (required) how long the signal stays actionable
  weight: 25                             # (required) 0-40, used for account scoring
  source: web_research                   # (required) web_research | clay | deal_history | inferred
  clay_source:                           # how Clay detects it (null if not detectable in Clay)
    type: company_data_point             # company_data_point | contact_data_point | custom_company | custom_contact | subroutine | search_filter
    name: "Open Jobs"
    custom_prompt: null                  # exact text for custom data points
  threshold: ">= 10 matching postings in trailing 30 days"   # (required) the firing rule
  external_source: null                  # data needed outside Clay (e.g. "G2 buyer intent")
  backtest:                              # filled by Step 4
    customer_sample: 20
    customer_firing: 13
    baseline_sample: 20
    baseline_firing: 4
    lift: 3.25
    verdict: validated                   # validated | weak | not_observed | not_testable | not_backtested
  personas: ["VP Infrastructure", "Head of ML Platform"]
  play_ref: template_2                   # Section 9 template it fires
```

## Decay window guidance

Pick the window from how fast the opportunity closes, not from how long the data stays visible.

| Signal type | Typical window |
|---|---|
| Funding round closed | 60–90 days |
| Exec / leadership hire | 90 days (first-100-days window) |
| Job posting surge | 30–45 days |
| Product launch, partnership, press release | 30 days |
| Earnings call or 10-K strategic mention | Until the next filing (~90 days) |
| Tech stack adoption or migration | 120–180 days |
| Event attendance / speaking | 14–21 days |
| Intent or review-site activity | 7–14 days |
| National or regulatory program | 6–12 months, re-check quarterly |

## Back-test rules (Step 4)

- **Firing rate** = accounts where the threshold is met / accounts enriched successfully. Exclude accounts where enrichment errored, and report the reduced sample.
- **Lift** = customer firing rate / baseline firing rate. If baseline firing is 0, report "∞ (baseline 0/n)" rather than a number.
- **Verdicts:**
  - `validated`: customer firing rate ≥ 40% and lift ≥ 1.5
  - `weak`: customer firing rate 15–39%, or lift between 1.0 and 1.5
  - `not_observed`: customer firing rate < 15%, or lift < 1.0
  - `not_testable`: no Clay source (e.g. intent data, web visits) — keep the signal, but score it on reasoning alone and say so
- **Timing caveat:** Clay shows current state, so a back-test on existing customers checks whether the signal is *characteristic* of customers, not that it *preceded* the purchase. Deal-history evidence (Step 5) is the only way to check sequence. Note this once in Section 7.
- Scorecard effect: a `validated` signal scores Conversion 4–5; `weak` 2–3; `not_observed` 1, and drop it from Scorecard A unless there is a strong reason to keep it.

## Account scoring (Step 6)

For `bucket` or `range` evidence, count the signal only if the oldest possible date is still inside the decay window, and show days left as a range on the board.


Account score = sum of `weight` for each signal currently firing and still inside its decay window, capped at 100. Add 15 when two or more signals from the same Section 6 cluster fire together.

| Score | Action |
|---|---|
| 80–100 | Immediate: route to AE/SDR this week |
| 50–79 | Active: start the matching Section 9 sequence |
| 25–49 | Nurture: ads and content, re-score in 30 days |
| 0–24 | Watch |
