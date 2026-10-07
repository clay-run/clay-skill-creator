---
name: inbound-triggers-monitor
description: |
  Find the people already engaging with you on social and turn each interaction into a
  dated, deduplicated inbound trigger — pull your team's recent posts, pull who reacted,
  commented and reshared, drop your own employees and company pages, resolve each engager
  to a person and account, and rank by how hard they leaned in. Use whenever someone asks:
  who engaged with our posts, who commented on our founder's content, turn social
  engagement into pipeline, find warm leads from people reacting to us, or which accounts
  are showing up in our comments. Do NOT use it to watch accounts for third-party news
  events (monitor-buying-signals), to source net-new accounts from events (signal-sourcer),
  to score and route inbound once you have it (score-inbound-leads), or to track a champion
  changing jobs (track-champion-job-changes). The platform returns a capped top-N sample per
  post, so it reports who it CAN see and never claims a complete engager list.
category: signals
personas: [sales-development, marketing]
mechanism: functions
touches: read-only
keywords: []
---

# Inbound-triggers monitor (engagement → warm rows)

The insight: **this is a ranking problem wearing a detection problem's clothes.** Every
other monitor asks "did the event happen?" — the event either fired or it didn't. Here the
platform hands you a **truncated, self-contaminated top-N sample** of the people who
engaged, and three things follow that the naive build gets wrong:

1. **The cap is the platform's, not your budget's.** Reactions max out at 50 per post,
   comments at 10, shares at 10 — and every one of them **defaults to 10** if you don't
   pass the limit. A post with 400 reactions yields 50 on a good day and 10 by default. So
   a viral post is *less* observable than a quiet one, and absence of a person from the
   feed is never evidence they didn't engage.
2. **Your loudest engagers are your own people.** Employees, the company page itself, and
   partner accounts sit at the top of every reaction list. An inbound monitor without a
   suppression gate reports your own marketing team as buying intent — and it does it
   confidently, because those rows are real interactions.
3. **The same human appears many times.** One person who reacts to four posts and comments
   on two is six rows and one lead. Deduplicating by event (what a news monitor does) is
   wrong here; the key is the **person**, and the interactions are their intensity.

So the output is never "here are the people who engaged." It is **"here is who we can see,
after suppression, ranked by how hard they leaned in — and here is where the sample was
cut off."**

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it, never
substitute a plausible default, and where an answer does not exist say which step becomes unavailable
rather than guessing. Where a default IS defensible it is named below, and using it means saying so in
the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Whose posts** | person profile URLs whose content draws their buyers | no default. The first stage takes a **person** profile; whether a company page is accepted is unverified, so if that is all they have, say so, try it, and report what came back |
| **Window and depth** | how far back, and how many posts per profile | **ten posts is the default and twenty-five is the ceiling.** There is no date filter, so the window is enforced when reading timestamps, not by the call |
| **Which interaction types** | reactions, comments, shares | **all three is defensible** and must be stated. Comments are the strongest signal and the most capped |
| **The suppression set** | their own domains and company pages, their employees, plus partners, agencies and investors | ask — this is non-negotiable. Without it the play degrades into people who engage structurally rather than out of interest |

**If an answer sheet is present beside this skill, load it and ask only for what it does not cover.**
A partial sheet is normal; a value it is missing gets asked for on its own rather than restarting the
interview. **Say which values came from the sheet** before using them — a sheet applied silently is a
wrong field nobody catches. **If there is no sheet, say nothing about sheets** — the check is a file
lookup, not a question, so run the interview as though the feature did not exist rather than reporting
an absence. At delivery, offer to save the answers back (identifiers only — never a token or a
password), private and never published — and phrase the offer so it explains itself: *"want me to save
your answers to a file, so the next person on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — the posts you point it at and the interaction types you choose.
- **Writes** — nothing. The deliverable is handed back to you.
- **Never** — writes to a CRM, pushes anywhere, or contacts anyone who interacted.
- **Halts** — Step 2 spend-approval.

## Step 0 — Verify Clay is working

Run `clay whoami; echo "exit_code=$?"`. If it fails or Clay tools are missing, run the Clay
plugin's `setup` skill, restart if it says to, and re-run this skill. Tell the user which
workspace they're in.

Confirm the arm exists before promising it — never assume the catalog:

```
clay workflows actions list | grep social-posts
```

Expect seven actions. The three this play runs, and their exact limits, are in
`references/interaction-mechanics.md`. Two traps worth naming here:

- `get-post-details` is a **Hacker News** scraper despite the generic name. It is not part
  of this play. Name-matching the catalog is how you end up calling it.
- The `activity-*` family answers "what did this profile do"; the `interaction-*` family
  answers "who engaged with this post". This play is `interaction-*` downstream of one
  `activity-*` call. They are easy to swap and the swap silently inverts the question.

## Step 1 — Collect the monitored surface (interview; do not guess)

1. **Whose posts.** Person profile URLs whose content draws your buyers — founder, execs,
   the people who post. The stage-1 action takes a **person** profile
   (`socialUrl`, e.g. `linkedin.com/in/…`). Whether a company page URL is accepted is
   **unverified here** — if the user only has a company page, say that plainly, try it, and
   report what came back rather than assuming either way.
2. **Window and depth.** How far back (stage 1 returns the most recent posts, default 10,
   **max 25** per profile — there is no date filter, so the window is enforced by you when
   you read `posted_at`, not by the action).
3. **Which interaction types.** Reactions, comments, shares. Comments are the strongest
   and the most capped (10). Default: all three.
4. **The suppression set** — non-negotiable, and the play degrades into noise without it:
   - your own company domain(s) and company page URL(s),
   - your employees (a roster, or the domain that resolves from step 7),
   - partners, agencies, investors, and anyone else who engages structurally rather than
     out of interest.
5. **The book.** Existing customers and open pipeline. These are **not dropped** — an
   engaging customer is an expansion signal — but they must be labelled, because routing a
   customer to an SDR as a new lead is the embarrassing failure here.

## Step 2 — State cost, get approval

Every action in this family costs **0.5 credits per call** (Clay Credits, declared in the
catalog). The arithmetic, stated before spending:

```
stage 1:  0.5 × (number of monitored profiles)
stage 2:  0.5 × (number of posts in window) × (number of interaction types)
```

Worked: 3 profiles, 10 posts each in the window, all three interaction types →
`0.5×3 + 0.5×30×3 = 46.5 credits`. Identity resolution in step 7 is priced separately and
only for rows that survive the gate — which is the whole reason the gate runs first.

Give the number, get a yes, then spend. If the user wants a cheaper first pass: comments
only (`0.5 × posts`), which is also the highest-intent subset.

## Step 3 — Enumerate the posts (stage 1)

Per monitored profile, `social-posts-get-post-activity-posts-and-shares` with `socialUrl`
and **`maxActivitiesLimit` set explicitly** (max 25). Keep for each post: the canonical
post URL, its posted date, and whose profile it came from.

Then apply the window yourself, on `posted_at`. Drop anything older. Report how many posts
each profile contributed — a profile that posted twice this month contributes two posts,
and the digest should not look thin without saying why.

## Step 4 — Pull the interactions (stage 2)

Per post, per chosen type:

| Action | Input | Cap | Default if unset |
|---|---|---|---|
| `social-posts-get-post-interaction-reactions` | `postUrl` | **50** | 10 |
| `social-posts-get-post-interaction-comments` | `postUrl` | **10** | 10 |
| `social-posts-get-post-interaction-shares` | `postUrl` | **10** | 10 |

**Always pass `maxInteractionsLimit` explicitly, at the cap.** Leaving it unset silently
takes 10 reactions out of a possible 50 — a 5× recall loss that looks identical to a quiet
post in the output.

Record per post: how many interactions came back per type, and whether that number
**equals the cap**. A post at the cap is definitely truncated, and step 9 has to say so.

But **below the cap does not mean complete** — verified on a live call: a request for 50
reactions on a well-engaged post returned **48**. The provider returns what it can reach, not
what exists, so a short return is *unexplained*, not reassuring. Cap-equality is sufficient
evidence of truncation and never necessary. Report the requested limit and the returned count
side by side and let the reader see the gap; do not convert either into a completeness claim.

Each returned interaction carries `author.name`, `author.url`, `author.type`, `author.title`
(the person's headline — **present in the live payload but absent from the catalog's declared
outputs**, so treat it as a bonus that may vanish, never as a required field),
`interaction_type`, `reaction`, and `preview_text`.

**`preview_text` is not content.** On a reaction it is a synthesized label of the form
`"<Reaction> by <name>"` — it restates two fields you already have and carries nothing new.
Only a comment's `preview_text` is the person's own words. Quoting a reaction's `preview_text`
as evidence of what someone said is fabrication with a real field name attached.

## Step 5 — Canonicalize, then key

**Canonicalize the interactor URL before it is used for anything**: strip the query string,
strip the trailing slash, lowercase. The same person arrives with tracking parameters on
one post and bare on another, and un-canonicalized URLs make one human look like three.

Then build the interaction key:

```
interaction_key = clean_profile_url | interaction_type | canonical_post_url
```

That composite is what makes re-running the play idempotent: the same interaction on the
same post is the same key, so a weekly run adds new interactions instead of duplicating
old ones. Key on the **person**, not the interaction, when you aggregate in step 8 —
`interaction_key` is for deduplication, not for grain.

## Step 6 — The suppression gate (runs BEFORE any paid enrichment)

Four rules, evaluated **in this order, stopping at the first match**. A row can satisfy two
rules at once — a partner's company page is both rule 1 and rule 3 — so first match wins and
every dropped row is attributed to **exactly one** rule. Without that, the per-rule counts
are not reproducible, and counts nobody can reproduce are counts nobody can act on. Every
dropped row is counted and reported by rule: a silent gate is indistinguishable from a gate
that isn't running.

1. **Not a person.** Drop where `author.type` indicates a company/organization page. Where
   `author.type` is missing or unrecognized, fall back to the URL shape: a `/in/` path is a
   person, a `/company/` path is not. Two independent tests because `author.type` is a
   provider field and provider fields go missing.
2. **Not us.** Drop your own company page URLs and anyone on the employee roster from
   step 1.5. If no roster was supplied, this rule cannot run — say so in the output rather
   than pretending the gate was complete, and re-apply it after step 7 resolves employers.
3. **Not structural.** Drop partners, agencies, and investors named in step 1.
4. **Label, do not drop, the book.** Customers and open pipeline stay, tagged
   `existing_relationship`, and never enter the new-lead route.

A row that survives all four is a **candidate**. Nothing has been enriched yet.

## Step 7 — Resolve identity (candidates only)

For each surviving candidate, resolve the profile to a person and their current employer,
then the employer to a canonical domain. Two consequences to handle honestly:

- **A resolution miss is not a drop.** Keep the row with `account: unresolved` and the
  profile URL intact. A named human who engaged twice is actionable even without a domain,
  and dropping them hides the strongest signals behind an enrichment failure.
- **Re-run suppression rule 2 now.** This is where "not us" actually becomes checkable
  without a roster: an engager whose resolved employer domain equals the user's own domain
  is an employee, whatever their profile said.

## Step 8 — Aggregate to the person, then rank

Group interactions by `clean_profile_url`. Score each person by summing the weight of
their **distinct** `(post, interaction_type)` pairs — the same person reacting to the same
post twice counts once:

| Interaction | Weight |
|---|---|
| Comment | 3 |
| Share | 2 |
| Reaction | 1 |

`intensity = Σ weights over distinct (post, interaction_type) pairs`

| Intensity | Tier |
|---|---|
| ≥ 5 | `hot` |
| 3 – 4 | `warm` |
| 1 – 2 | `watch` |

The bands are exhaustive and non-overlapping over the integers the weights can produce, and
the minimum possible score for a surviving row is 1, so every candidate lands in exactly
one tier. A single comment (3) is `warm`; a comment plus any two other interactions (≥5) is
`hot`; one reaction is `watch`. Roll the same interactions up to the account grain by
summing person intensities within a resolved domain, and report both grains — a single `hot`
person and four `watch` people from the same account are different situations.

## Step 9 — Deliver, with the sample disclosed

Per person: name · clean profile URL · resolved title and account (or `unresolved`) ·
intensity and tier · the distinct interactions with dates · the comment text where there
is one · `existing_relationship` where it applies. Per account: summed intensity, the
people, the tier mix.

Then the part that makes the digest honest, and it is not optional:

- **Coverage.** How many posts were pulled, and **which posts hit a cap** — by name, with
  the type that truncated. `"4 of 11 posts returned the maximum 50 reactions; the engager
  list for those posts is incomplete."`
- **Suppression counts, by rule.** How many rows each rule dropped, and explicitly whether
  rule 2 ran with a roster or only after resolution.
- **A quiet window is reported quiet.** No posts in the window, or no surviving candidates,
  is `0` with the reason. Never pad a digest by widening the window without saying you
  widened it, and never re-report last week's people as this week's triggers.

Hand the surviving rows to `score-inbound-leads` for scoring and routing. This play detects
and ranks; it does not score against an ICP, write outreach, or push to a CRM.

## What good looks like

- The user recognizes the names, and **isn't shown their own colleagues**.
- Every reported person traces to a specific post and a specific dated interaction.
- The digest states where the platform cut the sample off, so nobody reads a truncated list
  as a complete one.
- A re-run next week adds new interactions rather than re-reporting the same ones.
- The common failure: a long list of reactions from employees and company pages, ranked by
  nothing, presented as intent. The second-worst: 10 reactions per post reported as the
  engagement, because the limit was left unset.

## Rules

- MUST pass `maxInteractionsLimit` and `maxActivitiesLimit` explicitly; NEVER rely on the
  default 10, and never report a capped list without saying it was capped.
- MUST canonicalize the interactor URL (strip query, strip trailing slash, lowercase)
  before keying or deduplicating; NEVER key on the raw URL.
- MUST run the suppression gate before any paid enrichment; NEVER enrich first and filter
  after — it inverts the cost and buries the drops.
- MUST test person-vs-company on `author.type` AND on URL shape; NEVER treat a missing
  provider field as "person".
- MUST label existing customers rather than dropping them; NEVER route one as a new lead.
- MUST keep an unresolved candidate with the profile URL intact; NEVER let an enrichment
  miss delete a real signal.
- MUST report suppression counts by rule and the per-post coverage; NEVER present a filtered
  digest as the raw feed.
- MUST state the credit arithmetic before spending; NEVER run stage 2 across a post list
  without approval.
- NEVER claim a complete engager list, and NEVER infer that someone did not engage from
  their absence in a capped sample.

## Representative output

Three artifacts. **Every person, account and post title below is invented.** Intensity sums
distinct (post, interaction) pairs at comment 3 · share 2 · reaction 1; tiers are
**hot ≥5 / warm 3–4 / watch 1–2**, and every surviving row lands in exactly one.

### Per person

| person | profile | title · account | intensity | tier | distinct interactions | their words |
|---|---|---|---|---|---|---|
| M. Torres | socialsite.example/m-torres | Head of Growth · Brightloop | 8 | hot | commented on "Why pipeline reviews fail" (09-29) · reacted on three posts (09-22, 09-25, 10-01) · shared "Our Q3 benchmark report" (09-30) | "We ran exactly this and the hand-off step is where it broke for us." |
| D. Okonkwo | socialsite.example/d-okonkwo | VP Engineering · Brightloop | 3 | warm | commented on "Why pipeline reviews fail" (09-28) | "Curious how this handles multi-region." |
| R. Calloway | socialsite.example/r-calloway | unresolved | 2 | watch | shared "Our Q3 benchmark report" (09-30) | — |
| J. Lindgren | socialsite.example/j-lindgren | Operations Manager · Meridian Ops | 1 | watch | reacted on "Why pipeline reviews fail" (09-27) | — |

### Per account

| account | summed intensity | people | tier mix |
|---|---|---|---|
| Brightloop | 11 | 2 | 1 hot, 1 warm |
| unresolved | 2 | 1 | 1 watch |
| Meridian Ops | 1 | 1 | 1 watch |

### Coverage and suppression — the part that makes it honest

```
Posts enumerated: 11, window 2026-09-15 → 2026-10-01
Types pulled: reactions, comments, shares

COVERAGE. Four of 11 posts returned the maximum 50 reactions, so the engager
list for those four is INCOMPLETE:

    "Why pipeline reviews fail"      requested 50, returned 50   at cap
    "Our Q3 benchmark report"        requested 50, returned 50   at cap
    "Three things we got wrong"      requested 50, returned 50   at cap
    "Hiring for ambiguity"           requested 50, returned 50   at cap
    "A note on forecasting"          requested 50, returned 48

The 48 is not reassurance. The provider returns what it can reach rather than
what exists, so a short return is UNEXPLAINED, not complete. Requested and
returned are both printed so the gap is visible instead of being asserted away.

SUPPRESSION, by rule, all of it before any paid enrichment:
    own employees and company pages      31 rows
    existing customers and open opps      6 rows   (ran WITH a roster)
    competitors                           2 rows
                                         --
                                         39 rows dropped, at zero cost

Spend: 3 profiles + 11 posts × 3 types = (0.5 × 3) + (0.5 × 33) = 18 credits.
Every interaction limit was passed explicitly at its cap. Left unset it
defaults to 10 of a possible 50 — a 5× recall loss that looks exactly like a
quiet post in the output.
```

Two fields that invite fabrication, and how these rows handle them:

- **A reaction's preview text is not content.** It is a synthesized label of the form
  *"<Reaction> by <name>"* — it restates two fields already in the row and adds nothing.
  Only a comment's preview text is the person's own words, so the quotes shown above come
  from comments and from nothing else. Quoting a reaction's preview text as something a
  person said is fabrication wearing a real field name.
- **The headline field is a bonus, not a contract.** It is present in the live payload and
  absent from the action's declared outputs, so it may vanish without notice. `R. Calloway`
  shows `unresolved` rather than an inferred title.

A quiet window is reported quiet: no posts, or no surviving candidates, is zero with the
reason. The window is never widened to fill a digest without saying so, and last week's
people are never re-reported as this week's triggers.

**This play detects and ranks.** It does not score against an ICP, write outreach, or push
anything to a CRM — the surviving rows are handed to a scoring skill for that.

## Worked example

Three monitored profiles: a founder and two AEs. The window is 14 days;
`maxActivitiesLimit: 25` returns 6, 3 and 2 posts respectively, of which 8 fall inside the
window. All three interaction types → `0.5×3 + 0.5×8×3 = 13.5 credits`, approved.

Reactions come back at 50 on two of the eight posts — both flagged capped. 214 raw
interactions collapse to 96 distinct `(person, post, type)` triples after canonicalization,
which is the first sign the URLs needed cleaning: 31 of those collapses were the same
people arriving with tracking parameters.

The gate drops 22 company pages (rule 1), 19 employees (rule 2, from the roster), and 4
agency accounts (rule 3) — 45 rows, reported by rule. Two customers are labelled, not
dropped. 49 candidates go to resolution; 41 resolve, 8 stay `unresolved` with their profile
URLs.

Ranking puts one person at intensity 8 — a comment on the founder's post (3), reactions to
three others (1+1+1), and a reshare (2) — and the digest shows that sum term by term rather
than asserting the total, because a tier nobody can recompute is a tier nobody trusts. One
account contributes
three `watch` people and no comments: interesting, but not the same as the single `hot`
commenter, and the account grain says so. The delivered digest leads with the two capped
posts, because the person who matters most may be in the 350 reactions nobody can see.
