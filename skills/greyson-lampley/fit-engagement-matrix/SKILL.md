---
name: fit-engagement-matrix
description: |
  Place every inbound contact on a two-axis prioritization matrix and route it to a play.
  Account fit on one axis, computed by rules from firmographics anyone can buy. Engagement on
  the other, anchored on first-party data only the installer holds: product usage on the
  account, seats the person invited, signals on their own Audiences records, with topic intent
  added on top. A rules score decides the fit, and an agent is consulted only when the rules
  land in a borderline band. The result is one of four tiers, Target Accounts, Marketing
  Nurture, Opportunistic Sales, De-Prioritize, written back onto the contact's Audiences record
  with every point explained. Use whenever someone asks: score inbound leads on fit and
  engagement, build a lead scoring matrix, tier contacts into target accounts versus nurture,
  route a signup or form fill to the right play, combine account fit with engagement, score
  PLG signups, or build account and lead scoring in Clay. Do NOT use it to tier a static book of
  accounts with no engagement axis, to classify whether a person is a buyer, to validate or find
  work emails on their own, or to audit the accuracy of firmographic fields. It builds a Clay
  workflow and never routes anyone in your CRM until you approve the write.
category: score-and-qualify
personas: [revops, gtm-engineer]
mechanism: workflow
touches: writes-records
keywords: [lead-scoring, plg]
---

# Fit × engagement matrix (score each axis from the data that can answer it, then route on the quadrant)

The insight: **account fit and engagement are different questions, and they are answered by
different data.** Fit asks whether this company could ever be a customer, and firmographics
answer it: headcount, industry, revenue, a resolved work-email domain. Any competitor can buy
those. Engagement asks whether this company and this person are paying attention to *you*, and
only your own data answers it: workspaces created in your product, seats a person invited,
signal events on your own records. A single blended lead score hides that distinction and tells a
rep to call a perfect-fit company that has never heard of them. Two axes make the play a reading
off a quadrant instead of a guess off a number, and because every point is written into a reasons
string, the argument between sales and marketing about *why* a contact landed where it did ends
on the record.

Two consequences shape the build. **Rules score; an agent is consulted only where the rules are
unsure.** The firmographic rules are deterministic and free, so they run on every contact. The
agent runs only when the fit score lands in a borderline band, and it may move the score by a
bounded amount with a one-sentence reason. **Third-party intent sharpens engagement but never
anchors it.** Topic intent on the company and on the person adds points; the floor of the score is
first-party. Where the installer has no first-party data yet, the skill says so and sets the
engagement line accordingly rather than pretending the axis is populated.

**Do not start a step before the steps above it have their answers. If a declared input is
missing, ask for it. Never assume a default and continue.**

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it,
never substitute a plausible default, and if an answer does not exist say which step becomes
unavailable rather than guessing. Where a default IS defensible it is named below, and using it
means saying so in the output. The values the source workflow used are recorded in
`references/scoring-code.md` as what the author ran, never as what the installer should run.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Contact source** | How a contact arrives: a manual run with name and email, a form or signup webhook, or an Audiences segment. Every contact needs at least an email. | No default. Nothing to score. |
| **Ideal customer profile** | The headcount sweet spot and near band, the industry keywords that count as core fit, and the revenue bands that earn points. | Ask. The author's values are shown in `references/scoring-code.md` as an example; use them only if the installer says so, and say they are borrowed. |
| **Fit weights and band cut-offs** | Points per fit rule, and the score at which each fit band starts. | Ask. The author's weights sum to 100 and are shown; borrowing them must be stated in the output. |
| **Borderline band** | The fit range inside which the agent is consulted, and the maximum points it may move the score. | Defensible default: consult when fit is between 40 and 74, allow ±15. State it. |
| **Engagement model** | Account-side points for workspaces created, recency of the last workspace, a signup on file, account signals, account topic intent. Contact-side points for seniority, GTM function, recent activity, seats invited, person signals, person topic intent. Caps per side. | Ask. The author ran 45 account and 55 contact; if the installer has no first-party product data, say which rules will always score zero. |
| **First-party field mapping** | Which Audiences fields on the company hold workspaces created, last workspace created date, and last signup email; which field on the person holds seats invited, LinkedIn URL and title. | Read the installer's field catalogue, show the mapping found, and ask only about unmatched rows. A rule whose field is unmapped is dropped from the model and named in the output. |
| **Activity vocabulary** | The event names the contact source sends in its activity list, and points per event. | Defensible default: demo request, pricing page visit, email reply, webinar attended, content download, event attended. Unknown events score the "other" value. State it. |
| **Topic intent lists** | Which company topics and which person topics count as intent for this installer. | Ask. Without them the two intent steps are skipped, and the engagement caps shrink by their share. |
| **Matrix lines** | The fit score at which "high fit" starts and the engagement score at which "high engagement" starts, and the three cut-offs for the engagement status label. | Ask, and show the distribution of a ten-contact batch first. The author ran fit 60 and engagement 50, with status at 70, 50 and 25, where first-party product data existed; in a demo workspace without it the engagement line was lowered to 35 as a stated adjustment, not a model. |
| **Tier names and plays** | What the four quadrants are called and what each one triggers: an owner alert, a nurture, inbound-only handling, nothing. | Defensible default: the four names in the description, with placeholder plays that emit the message they would send. State it. |
| **Score fields on the contact record** | Which Audiences person fields receive fit score, engagement score, engagement status, priority tier and priority reason. | Create them if absent, numeric for the two scores and text for the rest, and name what was created. If the workspace is at its text-field cap, fold status and tier into the reason field and say so. |
| **Agent model** | Which model the two agent nodes run on. | Defensible default: the cheapest model the installer's workspace offers while building, then graduate it. State which ran. |

**If an answer sheet is present beside this skill, load it and ask only for what it does not
cover.** A partial sheet is normal; a value it is missing gets asked for on its own rather than
restarting the interview. **Say which values came from the sheet** before using them. **If there is
no sheet, say nothing about sheets.** At delivery, offer to save the answers back, identifiers
only, never a token or a password, in words that explain the offer: "want me to save your answers
to a file, so the next person on your team doesn't have to answer these again?"

## What this skill touches

- **Reads** — the contact's name and email from the contact source; the installer's Audiences
  people and company records matched by email and domain, including their signal events; the
  installer's Audiences field catalogue; the live action catalogue for cost and inputs.
- **Writes** — a new Clay workflow in the installer's workspace, and five score fields on the
  matched or newly created Audiences contact record. Nothing else on that record is touched.
  One provenance line into the new workflow's description, when a marketplace identity exists.
- **Never** — deletes a record, clears a populated field, writes to a CRM, sends a message,
  enrols anyone in a sequence, or moves the installer's data anywhere they did not name. The
  routing branches ship as placeholders that emit text; wiring a real action there is the
  installer's step and their approval.
- **Halts** — Step 4 spend-approval, Step 4 write-approval.
- **Derived from** — a workflow the creator built and iterated in their own workspace, read as
  configuration. The creator confirmed the insight as stated in this file.

## Step 0 — Check the platform works, and say where the work runs

Run `clay whoami; echo "exit_code=$?"`. It must return a user id. Say which workspace it names,
out loud, before anything else. If the Clay plugin is installed but signed out, run its `setup`
skill. **If the platform check fails, say which component is wrong, which version is required,
and the one command that fixes it, then stop.** Do not install, upgrade or fetch anything to
repair it.

Then state the posture in two sentences: this skill reads the installer's Audiences records and
builds a workflow that writes five score fields onto contact records; it never writes to a CRM,
sends anything, or deletes anything.

Where the work runs decides what it costs. The scoring arithmetic runs in **code nodes inside the
workflow**: deterministic, free, re-tunable by editing a constants block. Paid steps are the
enrichment and intent lookups, and the two agent nodes bill model usage only when they run. Say
this before pricing anything.

## Step 1 — Collect the definition (interview; do not guess)

Load the answer sheet if one is present, per the rule above. Then collect, in this order, asking
only for what the sheet did not cover:

1. **Contact source**, and whether a person starts a run or a signal does. See Step 2.
2. **Ideal customer profile**: headcount sweet spot, near band, core industry keywords, revenue
   bands. Take their words. Show the author's values from `references/scoring-code.md` only as
   an example of the shape.
3. **Engagement model**: which first-party facts exist for them. Read their Audiences field
   catalogue with `clay audiences fields list --entity-type companies` and `--entity-type people`,
   match it against the shape below, **show the mapping you found**, and ask only about the rows
   you could not match.

   | The rule needs | On | Typical field |
   |---|---|---|
   | workspaces created | company | a count written by their product |
   | last workspace created | company | a date |
   | a signup on file | company | an email or a flag |
   | seats invited | person | a count |
   | LinkedIn URL | person | the standard profile URL field |
   | title | person | the standard title field |

   A rule whose field does not exist is dropped from the model and named in the output. **Do not
   score a missing dimension as zero and move on in silence.**
4. **Topic intent lists**, company and person. If they have none, both intent steps are skipped.
5. **Activity vocabulary** the contact source sends, and points per event.
6. **Matrix lines and tier names**, with the plays each tier triggers. Tiers that trigger nothing
   are decoration; say so.

A threshold the installer cannot justify is recorded as theirs, unjustified, not invented a reason
for.

## Step 2 — Decide the shape: who starts this, you or a signal?

This skill builds a **workflow**, and here is why rather than a loop in this conversation: the
play exists for contacts who arrive when nobody is watching, a form fill at 2 a.m., a signup, a
webinar registrant. A score that only computes while a person is in the conversation computes
once. The source ran on a manual trigger for testing and is meant to sit behind a webhook or a
segment in production.

Put it to the installer as one line and let one word flip it: **you** run it by entering a
contact to score, or **a signal** fires it when a contact arrives. Default to the signal when they
have a webhook or a segment to point at, otherwise build the manual trigger and say the webhook is
a one-step change later.

## Step 3 — Free checks before anything paid

All of these run before a credit is spent, and together they usually eliminate a share of the
input:

- **Classify the email** as work, personal or invalid by its domain against a list of free-mail
  providers. A personal email still flows through, but with no company to resolve its fit will
  score zero and the contact is scored on engagement alone. Say how many of the batch were
  personal.
- **Match the contact in Audiences by email** and **the company by domain**, requesting fields
  and 90 days of signals. These are Clay-native lookups against the installer's own records.
  Confirm their cost in the live catalogue rather than assuming zero.
- **Resolve the LinkedIn URL before any paid person enrichment**: the Audiences record first. Only
  when the record has none does the LinkedIn-finder agent run, and only when no URL exists from
  any source is the person-intent step skipped. An agent search is a model cost, so count it.
- **Read the live action catalogue** for every paid step named in Step 4, with
  `clay workflows actions list` and `clay workflows actions schema`, and read each cost off the
  schema. `references/measured-arms.md` records what the author observed and the date; where it
  disagrees with the live catalogue, the catalogue is right.

## Step 4 — Small batch, then ONE gate: the batch, the cost, the writes, the ask

Build the workflow first (Step 5) as a draft, then run **ten real contacts** through it with
`clay workflows runs test` and read every node's output. Ten rows of output is what the installer
approves against, not an estimate.

Each paid step is named here so two installers reading this call the same thing. The four columns
are the contract; the pairs the author resolved are in `references/measured-arms.md`.

| Step | What runs | What goes in | What to verify in the response | Cost |
|---|---|---|---|---|
| Person enrichment | the managed person-enrichment function | profile URL as the identifier when one exists, else the email | a non-empty `result` object with a `title` and a `url`; `result: {}` with a not-found preview is a miss and still counts | read the schema; the author observed a managed function at 0 credits and 1 action execution |
| Company enrichment | the managed company-enrichment function | the cleaned domain, else the domain of the person's current employer | `result.name`, `result.domain`, an employee count and an industry; `"Company Not Found"` is a miss | read the schema |
| Company topic intent | a company topic-intent action | the resolved domain and the installer's topic list | `result.topics[]` with `topic_name` and `composite_score`; empty is a legitimate no-surge | read the schema; charged per call whatever it returns |
| Person topic intent | a person topic-intent action | a LinkedIn URL and the installer's topic list | `result.topics[]` with `composite_score` and `stage` | read the schema |
| LinkedIn finder | an agent node with web search, only when no URL is on record | name, email, domain, title on file | a URL containing `linkedin.com/in/` plus a confidence; Low means skip | model usage, per run it fires |
| ICP judgment | an agent node, only in the borderline band | company name, domain, industry, headcount, revenue, the rules score and reasons | a verdict, an adjustment inside the allowed bound, one sentence | model usage, per run it fires |

Then **one message** carries: what the ten contacts scored, with their tiers and reasons; the
share that was personal-email, not found, or skipped intent; the per-contact cost read from the
run's own reported usage, and what the full population costs at that rate; **and that this writes
five fields onto each contact's Audiences record, creating a record for contacts not already
there** — a mutation, not a read. Then the ask. Then stop and wait.

Stop a second time only if the batch reveals something the installer could not have anticipated:
every contact landing in one tier, a field mapping returning nothing, a cost far off the
expectation. That second halt is the gate working.

## Step 5 — Build the workflow

**Confirm node syntax against the installed version first**: `clay workflows nodes --help`,
`clay workflows triggers create --help`. Never hardcode a command form from memory; read the help
on the CLI that is actually installed.

Create the workflow with `clay workflows create --name` and then, in a **second** call, set its
description. If this skill carries a marketplace identity, append one line to that description so
the workflow can be traced to its listing: read the description first, append `Sourced from
marketplace skill:` followed by the slug and revision on its own line, keep whatever was there, and
read it back. If no identity is present, say attribution is unavailable and carry on. Never write
a placeholder.

Then create the nodes in dependency order. The full graph, every node's type, what feeds it, its
edges, and the Python for the code nodes are in `references/workflow-graph.md` and
`references/scoring-code.md`. The shape, in one screen:

1. **Trigger** → **Clean contact** (code): email type, name fallback, domain fallback.
2. **Match contact in Audiences** (tool, by email, fields plus 90 days of signals).
3. **LinkedIn URL on the record?** (conditional, rules). No → **Find LinkedIn URL** (agent).
   Both paths → **Enrich person** (tool, identifier first, email fallback).
4. **Enrich company** (tool) → **Match company in Audiences** (tool, by domain) → **Company topic
   intent** (tool).
5. **Any LinkedIn URL?** (conditional) → **Person topic intent** (tool) when yes; both paths →
   **Account fit** (code).
6. **Borderline fit?** (conditional, rules). In band → **ICP judgment** (agent). Both paths →
   **Engagement** (code).
7. **Place on the matrix** (code) → **Contact already in Audiences?** (conditional) →
   **Update record** or **Create record** (tool) → **Route by play** (conditional) → four
   placeholder code nodes, one per tier, each emitting the play, the action and the message.

**Where judgment lives is a MUST, not a style:** every comparison, threshold and route is a code
node or a rules conditional. The two agent nodes produce a URL and a bounded adjustment with a
sentence; neither one scores, compares or routes.

**Node traps that break a build halfway**, all measured on this graph or the platform:

- A tool node does not echo its inputs. Anything a later node needs from the trigger or from a
  code step is pinned from that step directly, never through a tool node.
- Tool-node outputs are read under `$.result.…`; code-node outputs under `$.…`.
- A field name with a space in a pinned path uses bracket notation, `$.result.records[0].fields['Field Name']`.
- A conditional's destinations are wired from the destination side: each incoming edge names the
  rule id, and exactly one carries the default route. Updating a node's incoming edges replaces
  the whole set, so re-send the existing ones.
- A tool action with a required input that resolves to empty fails the whole run. Gate it with a
  conditional, as the LinkedIn checks do, rather than letting it reach the action.
- Code-node output schemas are a flat map of field to type and description; agent output schemas
  require a description on every field and a JSON-encoded options list for a select.
- Topology is in the edges, never in the node list. The source is wired **serially**, with the
  only branches being the conditionals above; build the same shape.

Validate with `clay workflows graph validate`, then run the Step 4 batch. **The workflow stays a
draft until the gate passes.** Publishing it, and pointing a live webhook or segment at it, is the
installer's explicit step after the gate.

## Step 6 — The verdict, single-valued

Every contact gets exactly one tier, chosen by the first matching rule, from a closed set of
four plus one abstention:

| Order | Condition | Tier |
|---|---|---|
| 1 | fit at or above the fit line, and engagement at or above the engagement line | Target Accounts |
| 2 | fit at or above the fit line | Marketing Nurture |
| 3 | engagement at or above the engagement line | Opportunistic Sales |
| 4 | otherwise | De-Prioritize |
| — | the email was invalid, or no identity of any kind resolved | **Not scored**, reported separately |

Fit is the rules score plus the agent's bounded adjustment when the agent ran. Engagement is the
account side plus the contact side, each capped, with the subtotals kept. Engagement status is a
label on the same score: Highly Engaged, Engaged, Aware, Passive, in that order.

Every contact also carries its **position**: the distance of each score from its line, signed, so
a reader can tell a contact two points from Target Accounts from one thirty points away.

## Step 7 — Deliver

Per contact, written onto the Audiences record: fit score, engagement score, engagement status,
priority tier, and a priority reason carrying every rule that fired on both axes, the agent's
sentence when it ran, and the surging intent topics. To the installer, in the conversation: the
batch table, the tier distribution, the not-scored list with reasons, the per-contact cost as
reported by the runs, and the constants block so they can re-tune without a rebuild. Offer the
four saved segments on the two score fields that turn the matrix into a live view in Audiences.
Offer to save the answers to a file beside the skill, as described under **Declared inputs**.

## Representative output

### Scored contact record

| Contact | Fit | Engagement | Status | Tier | Position | Reason |
|---|---|---|---|---|---|---|
| Priya Nandakumar, VP Sales, northwind.example | 100 / 100 | 58 / 100 (account 18, contact 40) | Engaged | Target Accounts | fit +40 vs line, engagement +8 vs line | 838 employees in the 50 to 5,000 band (+40); software (+25); $10M+ revenue (+20); work email resolved (+10); profile verified (+5). Three workspaces created (+10); signup on file (+5); one account signal (+3). Executive buyer (+15); GTM function (+5); demo request and pricing visit (+15, capped); 4 seats invited (+6). |
| Tomás Rivera, CTO, contoso.example | 100 / 100 | 15 / 100 (account 0, contact 15) | Passive | Marketing Nurture | fit +40, engagement −35 | Same fit rules. Executive but not in a GTM function (+15); no activity; company not in Audiences, so no first-party engagement on file. |
| Mei Okonkwo, CMO, fabrikam-bank.example | 53 / 100 | 53 / 100 (account 10, contact 43) | Engaged | Opportunistic Sales | fit −7, engagement +3 | Rules fit 65: 11,600 employees near band (+20); banking is outside core industry (+10); $10M+ (+20); email (+10); profile (+5). Agent judged Weak, −12: "a large bank outside B2B tech poorly matches the target." Two account signals (+5); one surging company topic (+5). Executive in GTM (+20); demo request and pricing visit (+15); one surging person topic (+5); one person signal (+3). |
| Sam Varga, general manager, litware-hotels.example | 45 / 100 | 13 / 100 (account 5, contact 8) | Passive | De-Prioritize | fit −15, engagement −37 | 84,000 employees outside the band (+0); hospitality (+10); $10M+ (+20); email (+10); profile (+5). Manager (+8); no activity; two account signals (+5). |

The tier is one of exactly four values, plus a separate **Not scored** list for invalid emails and
contacts where no identity resolved.

### Run summary

10 contacts scored · 2 Target Accounts · 4 Marketing Nurture · 1 Opportunistic Sales · 3
De-Prioritize · 0 not scored. 7 of 10 matched an existing Audiences record and were updated; 3 were
created. Agent consulted on 3 of 10 (fit in the borderline band). Person intent skipped on 2 of 10
(no LinkedIn URL from any source). Cost as reported by the runs: 1.6 credits and 1 action
execution per contact on average; the full population of 420 at that rate is about 670 credits
before approval.

## What this skill does not claim

- The insight was confirmed by the creator, who built the workflow. The ICP definition and
  weights are the creator's for their own market; nothing in this file establishes that they fit
  anyone else's, which is why every one of them is a declared input.
- No cost in this file is a price. The author observed specific figures for specific arms on one
  day in one workspace, recorded in `references/measured-arms.md`, and the installer reads the
  live catalogue.
- The 45/55 split between the account and contact sides of engagement, and the points inside each
  ladder, were proposed by the author and accepted in design, not validated against conversion
  outcomes. They ship as the editable constants block, not as a calibrated model.
- The creator's matrix lines are fit 60 and engagement 50, with status cut-offs at 70, 50 and 25.
  In a demo workspace with no product-usage data the engagement line was lowered to 35 and the
  status cut-offs with it; that pair appears in the source as a stated adjustment and is not what
  the skill records as the model. The installer sets the lines after seeing a batch either way.
- The LinkedIn-finder agent returned a plausible but wrong URL for a fabricated contact on one run
  and an honest empty on another. Its confidence field is reported, not trusted; Medium is not
  High.
- Person enrichment by email alone found no profile for a real, well-covered person; by profile
  URL it found them on the first call. The skill orders the identifiers that way because of that
  observation, not because the email arm is known to fail generally.
- The routing branches are placeholders that emit text. No owner alert, nurture enrolment or ad
  audience is built or tested by this skill.
- The workflow was never run unattended behind a webhook. Every run observed was a manual test run.
- Per-run latency was not measured beyond "a few seconds to about forty seconds" on test runs, and
  not under load.

## What good looks like

- A rep can answer "why is this contact in Marketing Nurture?" from the reason field alone, with
  every point named and the agent's sentence quoted when it ran.
- The ten-contact batch spans more than one tier. A batch that lands entirely in one quadrant
  means a line or a weight is wrong for this installer, not that the population is uniform.
- Contacts with no first-party data score low on the account side and the reason says "company
  not in Audiences", rather than the model quietly inventing engagement from intent alone.
- Not-scored contacts are listed and counted. A run with zero of them usually means invalid
  emails were scored as if they resolved.
- The agent ran on a minority of contacts, the borderline ones, and each run has a sentence. An
  agent that ran on everyone, or never, means the band is wrong.
- A thin or failed run looks like this: one tier for all ten, reasons that read "unknown" on most
  rules, or a write step reporting zero fields written. Any of those stops the gate.

## Rules

- MUST compute every score and route in a code node or a rules conditional. The agent nodes
  return a URL or a bounded adjustment with a sentence; NEVER let an agent score, compare or route.
- MUST keep the two axes separate on the record and in the badge; NEVER deliver a single blended
  lead score without its components.
- MUST write every rule that fired, with its points, into the reason field; NEVER deliver a bare
  tier.
- MUST name the Audiences fields that will be written, and create missing ones by name, before the
  gate; NEVER write to any other field on the record, and NEVER clear a populated one.
- MUST gate the person-intent step on a LinkedIn URL existing from some source; NEVER let a
  required input reach an action empty.
- MUST read every cost from the live schema or the run's own reported usage; NEVER quote a figure
  from this file as the installer's price.
- MUST drop a rule whose first-party field does not exist and say so; NEVER score a missing
  dimension as zero in silence.
- MUST leave the workflow unpublished until the gate passes; NEVER point a live webhook or segment
  at it without the installer's yes.
- NEVER write to a CRM, send a message, enrol anyone, or move the installer's data anywhere they
  did not name.

## Worked example

Ask: "Score our inbound signups on fit and engagement and tell sales who to work." The installer
sells B2B software, their ideal customer is 50 to 5,000 employees in software and adjacent tech,
and their product writes workspaces created and last workspace date onto company records in
Audiences and seats invited onto people. Interview takes the ICP, keeps the author's fit weights
after seeing them and says so, maps the three first-party fields, supplies eight company topics
and ten person topics, keeps the default activity vocabulary, and sets the lines at fit 60 and
engagement 50 because the product data exists.

Build: 24 nodes created in dependency order, validated clean, description stamped. Batch of ten:
two Target Accounts, four Marketing Nurture, one Opportunistic Sales, three De-Prioritize, none
unscored. One contact's agent verdict moved a bank from fit 65 to 53, which is what put it in
Opportunistic rather than Target. Cost read from the runs: about 1.6 credits per contact. Gate
message states that, states the five fields and that three records will be created, asks. Yes.
Full run of 420, then the installer moves the engagement line from 50 to 45 after seeing the
distribution, a one-line change in the matrix node. Four segments on the two score fields become
the live matrix in Audiences.
