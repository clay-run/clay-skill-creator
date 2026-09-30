# How a verdict is decided

All of this runs inside the workflow's code steps (`2r Prepare`, `5 Verdict`), from one source in
`scripts/active_lib.py`. The local preview runs the identical text.

## 1. Read the profile, in whatever shape it came

The work history is found under the first of `experience`, `experiences`, `positions`,
`work_experience`, `employment_history`, `jobs`, `employments`, `workExperience`,
`current_experience`, searched one level down under `profile`, `person`, `data` or `result` too.
Each role's company, title, dates, current flag, website and LinkedIn company page are read from
whichever field name the provider used (Clay's own Enrich person, People Data Labs style
`company: {name, website}`, and scraper style `starts_at: {year, month}` are all covered). A
profile can arrive as an object or as JSON text.

A role is **open** when it is flagged current, or has no end date and is not flagged ended, or
its end date is in the future. Every date is turned into a day count by calendar arithmetic, never
`time.strptime`: that imports `datetime`, which Clay's code runtime does not have, and it failed
silently in the first live run.

## 2. Which roles could be at the company (code)

| Match | When | Jev asked "same company?" |
|---|---|---|
| `confirmed` | same website (by root domain: `shop.northwind.example` = `northwind.example`, two-part endings such as `.co.uk` handled) or same LinkedIn company page | no |
| `name_match` | the names are the same once legal words (`Inc`, `LLC`, `GmbH`, `Group` …) are dropped; a website's first label counts as a name | yes |
| `name_overlap` | one name's words are all inside the other's | yes |
| `id_conflict` | the names match but the websites or LinkedIn pages differ | yes |
| `name_unrelated` | nothing names the company at all, so each **current** role is asked, in case of a rename or a parent | yes |
| `none` | none of the above; the role is context, not a candidate | no |

Up to six candidate roles are kept, current ones first. Up to five other current roles are kept as
context.

## 3. The questions (one Jev request per person)

Jev's own documentation says it counts and compares dates badly, reads literally, and does best
with one small question per item, combined in code. So each candidate role gets its own questions,
and every date is already worked out:

| Question | Type | Asked when |
|---|---|---|
| `same_i`: is the company in this role the same company as the target (or a brand, division, earlier or later name)? | Noul | the match is not `confirmed` |
| `kind_i`: what relationship does this role describe? `employee` (incl. founders who run it), `contractor`, `intern`, `advisor_or_board`, `investor`, `honorary`, `not_enough_information` | Choice | always |
| `other_k`: the same kind question for each OTHER current role | Choice | the person has other current roles |
| `held_i`: this role has no end date and the person started other jobs after it; do they still hold it? | Noul | the role is open and a later current role exists |
| `main_i`: is this role their main job? | Noul | the role is open and another current role exists |

Names, emails and phone numbers are never sent. The state is only the person's headline; each
question carries the one role it is about.

## 4. Combining the answers (code)

For each candidate role:

- `P(same)` = 1 when `confirmed`, otherwise Jev's Noul.
- `P(held)` = 0 when the role has ended. Otherwise, with `P(job)` = how likely the **later** current
  role is a job rather than a side role (from `other_k`), `P(held) = P(job) × held_i + (1 − P(job))`.
  A later trustee seat leaves a CEO job held; a later full-time job makes Jev's answer count.
- `P(main)` the same way from `main_i` and the other current roles.
- `P(works there) = P(same) × P(held) × P(employee + contractor + intern)`;
  `P(passive only) = P(same) × P(held) × P(advisor_or_board + investor + honorary)`.

Then, first match wins:

| Rule | `active_at_company` | `relationship` |
|---|---|---|
| no company given, or nothing to enrich | `not_checked` | `unknown` (`check_status` `blocked_missing_input`) |
| the profile has no work history | `not_checked` | `unknown` (`no_profile`) |
| Jev failed | `not_checked` | `unknown` (`failed`) |
| no candidate is the same company (P < 0.5) | `no` | `no_record` |
| P(works there) ≥ 0.6 | `yes` | `primary_job` if P(main) ≥ 0.5, else `side_job` |
| P(passive only) ≥ 0.6 | `passive` | `advisor_or_board`, `investor` or `honorary` |
| every same-company role has P(held) < 0.4 | `no` | `former` |
| otherwise | `unsure` | `unknown` |

`verdict_confidence` is the probability behind the chosen value, 0 to 100. `needs_review` lists
answers Jev was less than 60% decisive on, a profile last refreshed over a year ago, and a profile
(supplied or bought) whose name shares no word with `full_name` (confidence capped at 50). When a
profile was bought because the supplied one was too old and the purchase came back empty, the old
one is used and that is noted too. A purchase that came back empty with nothing to fall back on is
`no_profile`, with the reason in `check_note`.

## What was measured (2026-09-29, jev-1.13.0)

- 11 invented cases (`scripts/fixtures.json`): all correct, in Clay and locally, and identical
  between the two.
- 10 people from a real table with a Clay Enrich person column: all correctly `yes / primary_job`.
- Three real public profiles bought through the workflow: a CEO with a university trustee seat
  (`yes / primary_job`, 100, after the side-role fix; 64 before it), a founder whose co-founder
  title at an earlier company has no end date, beside two newer current roles (`unsure`, about 50, main job named as the
  newer company), and a made-up URL.
- **The made-up LinkedIn URL returned somebody's profile and was billed.** Clay's Enrich person
  does not fail on a URL that is not the person you meant. Pass `full_name` when you have it.
- Jev's probabilities move by a point or two between calls; the fractional-executive case sat at
  59–62% until the "still held?" criteria named several fractional roles at once, and has read 78–80%
  since.
