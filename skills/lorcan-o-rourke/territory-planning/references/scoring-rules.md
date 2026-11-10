# Scoring rules

These rules came from real runs. Each one cost a correction cycle; the scorer enforces them so the next
run does not.

## Evidence rules

1. **A search that ran and found nothing is an answer.** Score the factor's "none" band. Do not hold.
2. **A source that failed to run is not an answer.** Status `failed` (domain did not resolve, provider
   error, timeout) holds the whole account: no score, no grade, status `Held: <factor> failed`. In a
   waterfall (fundraising: fixed-price providers, then the research agent) a tier that errors is skipped
   and the next tier runs; the factor is `failed` only when every configured tier errored, and a provider
   error marked transient gets one rerun batch before the hold stands. The gate also skips funding
   research for public or exited companies (Harmonic stage EXITED): the date-only round is the answer,
   not a hold. Every provider node that can hold an account must continue on error, so the run reaches
   the Score node and the headline write lands as `Held`; a run that dies at the provider writes nothing,
   and patching the status in by hand is exactly the ad hoc CRM write this skill does not do.
2a. **A resolve to the wrong company is a failed resolve.** A resolved record with no domain, a domain that
   does not match the input, or under 10 employees when the CRM count is 50 or more, is a wrong match
   (a payroll company's domain matched a 5-person LinkedIn page with no website; a neobank's domain
   matched a 14-person product entity). It counts as `failed`, status `Held: Resolve failed` with the
   reason "likely the wrong company"; every downstream factor would score the wrong company, so nothing
   is scored. The fix is the source, not the
   rubric: re-resolve by LinkedIn URL, or coalesce the trigger domain ahead of the resolved one.
3. **A capped list is incomplete, but only where a cap exists.** `capped` applies to an action that
   exposes a result limit (a jobs or people list with `limit`). An action that returns a complete result,
   such as a provider count or a funding round, is `found`, even when the result is empty. When a
   list comes back at its limit: if unseen results could lower the score, hold; if the cap only matters
   upward (open SDR roles feeding a "20 or more scores 100" rule), either raise `limit` to at least the
   threshold, or map a full page to the top band and write "(capped)" in the evidence. Do not count
   unseen results as absent. Two lists carry a limit in the reference build: open SDR roles, and the
   tech-stack call once it is pinned to the product ids or names the rubric needs with a `limit` of 12 or
   fewer (which it must be; see the test protocol). A full tech-stack page at the limit maps to the top
   band with "(capped)", since unseen records can only add a category, never remove one.
4. **An unknown status is a wiring error, not an answer.** A `<factor>_status` that is missing, empty or
   not one of the four values holds the account as `failed` with reason `status not wired`. It is never
   treated as `none`; that would score the none band for a factor that never ran, and nobody would see.
5. **A zero-weight factor never blocks.** If a factor is retired (weight 0), its status is ignored.
6. **Scoring never touches Owner.** The scorer writes fit fields only. The carve workflow writes a
   Proposed Owner and a Carve Status, never Owner; owners change only when the Write Owners routine
   applies the approved rows after the Step 7 gate (see "How the carve consumes scores" below).
7. **Write the headline first.** Score, grade, reason and rubric version are one write. Component
   fields are a second write, verified separately, so a mapping error cannot block the headline.
8. **A held account writes no component scores and no enrichment values.** Status, reason and rubric
   version only; every `<factor>_score` stays empty, and so do the pass-through values (headcounts,
   growth, motion, model, funding, tech stack, last-enriched time), because on a wrong-match hold they
   describe the wrong company. The component-and-enrichment write runs only when `scoring_status` is
   `scored`; a stale component can never sit beside a held headline.
9. **Growth is clamped to what the CRM field holds.** `Headcount_Growth_Pct__c` is Number(7,1), which
   holds up to 999,999.9; a +39,800% value overflowed the earlier Number(5,1) and failed the whole
   component write for that row. The Score node clamps the pass-through value to the field's range and
   keeps the raw figure in the evidence with "(clamped)". Scoring itself is unaffected: a `bands` factor
   puts any value that large in its top band.
10. **Size rules read the CRM count when LinkedIn disagrees.** The resolved LinkedIn headcount over-counts
   5x to 9x for some companies (one at 7,137 on LinkedIn against 800 in the CRM; 24 of 200 accounts in
   one run). It is fine for a size band, but a "too big" rule (for example 5,000 or more employees scored
   Low Fit or excluded) and segment eligibility must agree, so: the size override and the segment read
   the CRM employee count whenever it is present and fall back to the resolved count only when the CRM
   count is blank, and the evidence names both figures. Without that fallback the grade says Low Fit while the carve deals the
   account into a book.

## The contract between research and scoring

The enrichment workflow emits, per factor in the rubric:

| Field | Type | Values |
|---|---|---|
| `<factor>_value` | string or number | the category (for `map`) or the number (for `bands`, `linear`) |
| `<factor>_status` | string | `found`, `none`, `failed`, `capped` |
| `<factor>_flags` | string, optional | comma-separated modifier keys for a `map` factor that declares `modifiers` (`saas,ai_native`) |
| `<factor>_evidence` | string | one phrase: what was seen (`"Salesforce, Snowflake, ZoomInfo"`, `"293 in sales of 1,609"`); when it arrives empty the scorer renders `(no evidence recorded)` in the reason line, never a blank |

The scorer reads the rubric JSON and these fields. It does not call any provider and it does not reason
about meaning; meaning-level judgment (who they sell to, product complexity) happens in the research
step, which must still emit a category and an evidence phrase.

The three fields may come straight from the research nodes, or from a code node that derives them from
raw tool outputs (a product list, a role count, the funding JSON) just before scoring. Either shape
satisfies the contract on one condition: the node OUTPUTS `<factor>_value`, `<factor>_status` and
`<factor>_evidence` for every factor, so they land in the run output. Saved outputs are what make
re-scoring free; a score node that derives them internally and returns only scores forces a paid rerun
for every weight change.

## The scorer's output

| Field | Example |
|---|---|
| `account_fit_score` | 74.5 |
| `account_fit_grade` | Good Fit |
| `account_fit_reason` | Good Fit (74.5). Strongest: Sales Team (293 reps, 18% of HC). Weakest: Technographics (no CRM or warehouse found). |
| `<factor>_score` | one per factor, 0..100; empty on a held account |
| `rubric_version` | 1.2 |
| `scoring_status` | `scored`, or `Held: <factor> failed` |

The reason names the strongest and weakest factor with their evidence. A rep reads that line; they do
not read the components.

## Grade overrides

Overrides change the grade after the weighted score (see `rubric-template.md`). Two rules from real runs:

- **A factor score of 0 is a real zero.** The opt-in VC/PE and agency lift ("Best Fit unless a factor
  scored 0") must test `score is not None and score == 0`. Writing `(score or 1) > 0` turns a 0 into a 1 and the
  override fires on exactly the account the rubric meant to keep out. A retired factor (weight 0) has no
  score and does not count.
- **Exclusions run twice on purpose.** The default overrides are `{exclude: true}` for `vc_pe`, `agency`
  and `education`: the component scores stay, the total is capped at 40 (under the eligibility
  threshold), the grade is Low Fit and the reason starts "Excluded by rule", so the CRM grade and the
  carve status say the same thing. The carve excludes the same types again from `Entity_Type__c`, so a
  change in either place alone cannot put one in a book. A seller to whom VC firms or agencies are real
  customers replaces the exclude with the opt-in lift `{min_grade: Best Fit, unless_factor_zero: true}` in
  the rules file (the Score node reads the block as `overrides_json`); they still leave the carve as
  `Excluded`. `production-example.md` shows a team that chose the lift; a PLG team dropped it as
  irrelevant. Either way it is a rules file edit, not a scorer change.
- **"Too big" can be a band and a grade override at once.** The template treats a size disqualifier as a
  rules exclusion, but a team that wants the CRM grade itself to read Low Fit for a 5,000+ company gets a
  Headcount band in the rubric AND a size override in the rules file. The override reads the headcount
  by rule 10 (the CRM count when present, the resolved count only as a fallback), and its reason names
  the rule so a rep sees why a company that maxes every other factor grades Low. At carve time the same
  `overrides.size_cap` knob takes the account out of the pool (`Not eligible: too big` for action
  `Low Fit`, `Excluded: too big` for action `exclude`), so no Assigned account carries a Low grade for
  size.

## Test protocol

- **Scorer first, at zero credits.** `clay workflows code test` has a daily cap of 10 runs, so do not
  spend it on the scorer: run `python3 "$SKILL/scripts/score_account.py"` for its self-test, and
  re-score saved outputs with it locally. The code test is for the one-off check of a derive node.
- **Five first.** Five known accounts, each with the grade the team expects. The "three best, one lost,
  one non-fit" roles are guidance for picking them, not a form: a team may bring two Best, one Good, one
  Moderate and one Low, or a fifth whose expectation is a carve status ("too small, Not eligible") rather
  than a grade; record that expectation and check it in Step 7. Compare grade to expected grade, not
  score to score; enrichment varies by a few points between runs. Check that every one of the five
  resolved to itself (rule 2a) before reading a single grade; a wrong match looks like a rubric miss.
- **Then ten.** A random slice of the universe (stratified when the universe is mostly one industry, so
  both the core and the other path get tested). Look for the two failure shapes: everything Good or Best
  (the rubric cannot separate) or everything Held (a source is failing). Give the first one a number:
  if more than half of the ten grade Best, say so and ask whether the top band should be harder before
  scoring everyone; a universe hand-picked for fit is the one expected exception.
- **Then everyone.** Only after both gates, and only after the cost is stated and approved.
- **Record credits per account on every test run.** Test runs bill like live runs. After the five and
  after the ten, read credits used from the run data and divide by accounts; that figure, not the
  catalog, is the quote. Know where the money goes: the tech-stack lookup (HG Insights) bills about 8
  data credits per product record returned, not per call, and was 60% to 90% of spend on every build;
  the two research (Claygent) nodes with the capped prompts in `research-prompts.md` cost about 1 to 2
  credits each. Measured means on four 200-account runs were 18, 45, 62 and 73 data credits per account,
  and the spread is almost entirely how many tech-stack records came back. The lever is pinning that
  call to the specific product ids or names the rubric scores with a `limit` of 12 or fewer, not
  shortening the prompts. If one account is far above the rest, open its tech-stack result first. Check
  headroom with `clay credits balance` before the ten and before everyone.

Tune weights by editing `rubric.md` and re-scoring the saved research outputs locally; that costs
nothing. Rebuild the workflow only when a factor is added, removed, or its data need changes.

## Acceptance (Step 4 gate)

- [ ] The five known accounts land in their expected grades.
- [ ] No account is held unless a source actually failed, a capped list could lower its score, or a
      status was not wired (and that one is fixed in the build, not scored around).
- [ ] Every known account resolved to itself: the resolved domain matches, and the headcount is not
      under 10 when the CRM says 50 or more (rule 2a).
- [ ] Held accounts carry no component scores and no enrichment values; the reason line never shows a
      blank where evidence goes.
- [ ] A size override and the segment read the same headcount (rule 10); no account grades Low Fit for
      size while the CRM count puts it inside a segment.
- [ ] Changing one weight and re-scoring moves scores the expected direction.
- [ ] The reason line names a real strongest and weakest factor for every scored account.
- [ ] `rubric_version` matches the file.
- [ ] Credits per account recorded, and at or below the quote given to the user or no more than 20% over
      it; a cheaper run than quoted passes.

## How the carve consumes scores

The carve is the "Territory Carve" workflow in Clay, built by `scripts/carve_workflow.py build` and run
over the pool by `scripts/carve_workflow.py run`; its code node is `scripts/carve_node.py`, and
`scripts/carve.py` runs the same gates and deal locally as a zero-credit preview (both from the project
root; see `pool-and-carve.md`). Each run reads one scored account from the CRM, and the scorer's fields
decide the first two phases:

- **Eligibility reads `scoring_status`, then the score.** An account is eligible only when
  `Scoring_Status__c` is `scored` and `Account_Fit_Score__c` is at or above the rules file's threshold; a
  held account (any `Held:` status) is `Not eligible` with reason "not scored", never dealt and never
  guessed at. Rerun the held accounts through the workflow and carve again; do not patch a status in.
- **The other-industries gate reads the raw values, not the component scores.** Ops and sales headcounts,
  the CRM employee count and the tech-stack evidence (matched against `eligibility.competing_vendors`)
  let a below-threshold account in a non-core industry through. That is why rule 8 keeps the raw values
  honest and rule 10 keeps the headcount the same one the scorer used.
- **`Is_Competitor__c` means the account IS a competitor** (its own domain or name is on the competing-vendor list), never
  "uses a competing vendor". Keep the vendor signal as a separate value (`has_competing_vendor`, feeding Technographics).
  Measured on the 28 Oct live run: the first build set the flag on 28 accounts that merely ran ZoomInfo, and the carve
  excluded every one of them as a direct competitor until the Score node was corrected and the flag rewritten.
- **Exclusions read `Entity_Type__c` and `Is_Competitor__c`.** A VC firm or agency arrives capped at 40 and
  graded Low Fit by the default override and leaves the carve as `Excluded`; both fields in the CRM say the
  same thing. With the opt-in lift it arrives Best Fit and still leaves as `Excluded`.
- **Grade and segment travel with the proposal.** The summary shows mean fit and grade mix per book, so a
  rubric that cannot separate shows up as identical books before anything is written.

The workflow writes Segment, Sub-region, Carve Status, Carve Reason and Proposed Owner on the account
and mirrors them on the Audiences record; `scripts/carve_summary.py` then reads the CRM and writes
`carve-summary.md`, `carve-proposal.csv/json`, `write-owners.jsonl` (the Proposed rows) and
`patch-doc.md` into `--out`. Owners land only when the team approves the books and the rows are applied
through the Write Owners routine, which asks the human for one more approval before it runs in bulk.
