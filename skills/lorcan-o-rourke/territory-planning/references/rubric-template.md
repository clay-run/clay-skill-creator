# Adapting the rubric

`references/rubric-starter.md` is a working rubric for a B2B SaaS seller: eight factors, weights summing to 100.
Start there. Change it only for reasons the interview gave you, and write the reason in the rationale
column so the next reader knows why.

## Rules for the table

1. **Weights sum to 100.** Renormalise after every change; never divide at score time.
2. **One factor, one row, one data need.** If a factor needs two sources, its research step combines
   them and emits one value.
3. **Every factor has a "none" band.** A search that ran and found nothing lands there. Without it the
   scorer cannot tell "no CRM" from "search failed".
4. **The heaviest factor is the unit-of-value proxy.** If deal size follows support volume, the heaviest
   factor is the best public proxy for support volume, not the one with the best data.
5. **At most one new factor in v1.** New factors need research prompts, bands and a test; they are the
   expensive change. Reweighting is free.
6. **Drop what cannot matter.** A factor the business cannot act on, or that is identical across the
   whole universe, is noise with a weight.

## Factor kinds

The scorer supports three kinds. Pick one per factor and write the spec in the JSON block.

| Kind | Input value | Spec | Example |
|---|---|---|---|
| `map` | a category string the research step emits | `{"category": score, ..., "none": score}` | Technographics: `crm+dw+competitor` 100, `crm+dw` 80, `one` 50, `none` 20 |
| `bands` | a number | ordered `[[min, score], ...]`, first band whose min is met wins (check from the top) | Growth: `[[30,100],[15,70],[5,40],[-999,10]]` |
| `linear` | a number | `{"from": 0, "to": 500, "cap": 100}` | Size: 0 to 500 employees maps to 0 to 100 |

Modifiers (SaaS +15, non-SaaS -15) are a second `map` applied after the first, then clamped to 0..100.
Write them as `"modifiers": {"saas": 15, "non_saas": -15, "ai_native": 15}` on the factor.

## Overrides

Overrides change the grade after the weighted score, and they live in the rules file, not the rubric.
The default is the exclusion form: VC/PE firms, GTM agencies and education institutions keep their
component scores, have the total capped at 40 (under the eligibility threshold), grade Low Fit, and the
reason says "Excluded by rule". Keep the list short and name the reason.

**Excluding at scoring time and at carve time is deliberate, not redundant.** The carve excludes the same
entity types again from the CRM's entity type field, so a change in either place alone cannot put one in
a rep's book, and the grade on the record agrees with the carve status. A seller to whom VC firms or
agencies are real customers switches those two to the opt-in lift (`min_grade: Best Fit` unless a factor
is 0); the carve still excludes them because another motion owns them. Write both rules down, each in its
own place, so nobody "fixes" one by deleting the other. `references/production-example.md` section 2
shows a team that chose the lift.

### Optional risk/rescue layer

A second grade override, also in the rules file, for sellers who want to catch low-quality accounts
that still clear the weighted score:

- **Risk signals** add penalty points: no funding, under 20 employees, no GTM motion, no sales team,
  pure B2C, education domain, weak region, no CRM or warehouse.
- **Rescue signals** subtract: recent raise, high growth, real sales presence, SaaS, strong PLG,
  mature stack.
- **Net risk** is risk minus rescue. High net risk plus a low weighted score = Bad Fit.
- **SaaS gets a stricter threshold** for the override, so promising early-stage SaaS companies are
  not thrown out for being small.

Keep it out of the weighted maths. It never changes a factor score or the Account Fit Score; it only
moves the grade, and the reason is written with the grade. Signal lists and thresholds come from the
interview; `references/production-example.md` section 2 has one company's version.

## Grades

| Grade | Score |
|---|---|
| Best Fit | 80 and above |
| Good Fit | 65 to 79 |
| Moderate Fit | 50 to 64 |
| Low Fit | below 50 |
| Bad Fit | override only (education, or high net risk with a low score) |

The eligibility threshold (default 60) sits inside Moderate on purpose: a Moderate account can still
be worth a book if the rules allow it. The threshold is a rules decision, not a grade.

## Versioning

Every change bumps the version line at the top of `rubric.md` and is written with every score as
`rubric_version`. When grades move between runs, the version tells you whether the data moved or the
rubric did.

Three habits go with the version, all shown in `references/production-example.md` section 1:

1. **A rationale per weight.** The "Why this weight" column is filled for every factor, in one line.
   A weight with no reason is the first one the next reader will change.
2. **A back-test against closed-won when a weight changes.** Score the closed-won accounts from a fixed
   window under the old and new rubric and report recall at the eligibility threshold (for example,
   "non-SaaS winners at fit 65 or above went from 51% to 83%"). A reweight with no back-test is an
   opinion.
3. **The alternative you rejected and why.** One sentence in the change note, so the same debate does
   not happen again next quarter.
