---
name: score-accounts-with-jev
description: |
  Build an account lead-scoring workflow in Clay that uses Jev, TypeSafe's decision model, for
  the judgment calls and plain code for everything numeric. The agent starts from what it
  already knows about your business (memory, notes, docs in your folder), interviews you only
  for the gaps, and turns that into a rubric of rules and Jev questions: yes/no Nouls,
  categories and scales. It previews the rubric on ten of your real accounts, then builds a
  callable Clay workflow that takes a company's context from a Clay table, a saved Audiences
  audience or any webhook and returns a 0 to 100 score, a tier, the reasons, and the answers
  worth a second look. Works with a TypeSafe key or an OpenRouter key, kept in a local .env and
  in a Clay connection, reusing either if you already have one. A few cents per thousand
  accounts. Use whenever someone asks: score my accounts, build an account or ICP fit score,
  lead scoring for companies in Clay, tier my target accounts, qualify companies with Jev,
  replace an AI column that grades accounts, or set up Jev or TypeSafe in Clay. Do NOT use it to
  score individual people (score-contacts-with-jev does that), to find or enrich companies, to
  route or assign leads, to push scores into a CRM, or to train a model on won and lost deals.
category: score-and-qualify
personas: [revops, gtm-engineer]
mechanism: workflow
touches: writes-records
keywords: [lead-scoring]
---

# Score accounts with Jev (Jev decides, code counts)

**The insight: a lead score is a handful of judgments plus arithmetic, and the arithmetic must never
be asked of the model.** "Is this a distributor?", "do they run their own fleet?", "how strong is
this growth signal?" are judgments. "Are they between 200 and 2,000 staff?", "is the HQ in North
America?", "how many points is that, and is it an A?" are arithmetic. An AI column that is asked for
"a fit score from 0 to 100" mixes the two and returns a number nobody can decompose, audit or
reproduce.

The evidence is Jev's own documentation. TypeSafe publishes a list of what Jev 1.13 is bad at, and
the top of it is numbers, counting and comparing dates; it reads instructions literally; it degrades
when the record is padded with fields the question does not need. Its recommended pattern for
scoring is to break the judgment into atomic questions and **combine them with weights in code**.
And what Jev returns is not a label but a probability for every option, so a score can use how sure
it was.

What follows is the whole design:

- **Rules** (numbers, dates, lists) are worked out in the workflow's code step. Free, exact.
- **Questions** (Jev's Noul, Choice and Score) are sent in **one request per account**, with only
  the fields they read. About $0.042 per million input tokens and output is free: a few cents per
  thousand accounts.
- **Points are expected values over Jev's probabilities.** A 25-point category Jev is 60% sure of
  adds 15. An unsure answer moves the score less than a sure one, in either direction; it never
  flips a verdict outright.
- **Missing data never poses as a verdict.** An account the data cannot judge comes back
  `insufficient_data`, not a D; above that bar, every criterion it had no data for earns nothing and
  is named in the reasons. A competitor comes back `disqualified` before any Jev call.
- **The preview is the workflow.** The ten-account preview runs the identical code the Clay step
  runs, so what the installer approves is what they get.

> **Measured.** Run live against Jev (TypeSafe) and a Clay workspace: a distributor scored 98 A in
> Clay and in the local preview alike, a competitor was disqualified without a Jev call, and one
> audience member's seven "Jev …" fields were written and read back equal to the local score. The
> build caught Clay attaching an unrelated connection to the Jev step and refused to publish. The
> live checks, and what was not run, are in `references/live-checks.md`.

> **This skill is not finished when the rubric is agreed.** It is finished when the workflow is
> published, one account has gone through it in Clay and matched the local preview, and the
> installer has been shown how to call it. If you stop early, say which step you stopped at and the
> command that resumes it.

## How to talk to the installer

- **Every question is a choice they click**, asked with the host's question tool (`AskUserQuestion`
  in Claude Code), one decision at a time, likely answer first, free text only as "Other". Never a
  paragraph of questions.
- **Never ask what you already know or can look up.** Your memory, this conversation, and files in
  the working folder come first (Step 2). Table columns, audience fields and whether a key exists
  are commands.
- **Before any question, apply the test: does the answer change the rubric or the build?** If not,
  do not ask it, and do not defer it to a later step either.
- **Run every command yourself**, in the background when it waits on the installer. The installer
  only does what needs a person: pasting a key into a box, creating a connection in Clay's UI, and
  deciding.
- Show names, never ids, in anything the installer reads.

## Declared inputs

**Nothing here ships with a value.** Where a default is offered it is named, and accepting it is
recorded as borrowed (`"origin": "default"`) and said at delivery.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Where accounts come from** | a Clay table, a saved Audiences audience, or "another system" (webhook). Picked from a list the agent reads | no default. It decides which fields exist, so which criteria are possible |
| **What they sell and to whom** | a line or two, **found in the agent's context first**; asked only if not | stop: no rubric can be written without it |
| **Best-fit, OK and poor-fit kinds of company** | categories with a sentence each | stop at Step 2. Never invented |
| **Size, region and other numeric cuts** | only for fields the source actually carries | the criterion is left out, and the card says so |
| **Disqualifiers** | competitors, partners, excluded segments, or "none" | "none" is a real answer; ask, never assume |
| **Signals worth points** | only those the data carries (hiring, funding, news, tech) | left out |
| **Tier cut-offs** | what an A must reach | A≥70, B≥45, C≥25 offered, recorded as borrowed if accepted |
| **A Jev key** | TypeSafe or OpenRouter. Found in the environment, `./.env` or `~/.config/jev-lead-score/.env`; otherwise saved there through a password box | stop at Step 4: nothing can be previewed |
| **The same key in a Clay connection** | an existing HTTP API connection named by the installer, or a new one they create in Clay's UI | stop at Step 6: the workflow cannot call Jev |

**Not asked, ever:** column or field names (read and shown as a mapping to correct), which fields
the score writes (fixed), a callback URL (the caller's own), whether to preview (always), the
provider when only one key exists, point values for every option (proposed in the draft and
corrected there), and any key in the chat.

### The workflow's interface: prescribed by the rubric

Inputs are the rubric's `inputs`, one flat field each, plus `source_ref` (echoed back for joining).
A typical account rubric reads `company_name` (required), `domain`, `description`, `industry`,
`employee_count`, `country` and one free-text signals field. Output, every key always present:

| Key | |
|---|---|
| `lead_score` | 0 to 100 integer |
| `lead_tier` | the rubric's tiers (A, B, C, D by default), or the status when not `scored` |
| `score_status` | `scored` · `disqualified` · `insufficient_data` · `not_scored` · `failed`. Five, no sixth |
| `score_reasons` | what counted for the record "(+25)", what counted against it "(2 of 25)", and what had no data |
| `needs_review` | answers under the confidence floor, with Jev's split; `none` otherwise |
| `coverage_pct` | how much of the rubric the data let Jev and the rules judge |
| `criteria_json` | every criterion: answer, confidence, points, status |
| `rubric`, `jev_model`, `jev_cost_usd`, `error`, `source_ref`, `scored_at` | provenance |
| `record_id`, `isTerminal` | plumbing: the audience record written to, and the flag a run is settled on |

## What this skill touches

- **Reads**: the agent's own context (memory, this conversation, files in the working folder) for
  what the installer sells and to whom; the column list and up to ten rows of the table, or the
  field list and up to ten records of the audience, the installer picks (Step 1, Step 5); Clay's
  action catalogue; the workspace name.
- **Writes**: a rubric, preview results and build state under
  `~/.local/state/score-accounts-with-jev/`; the Jev key into a `.env` file only through the
  password box, at mode 0600, by default `~/.config/jev-lead-score/.env`, never into a file git
  would commit. In Clay: one workflow "Jev lead score: accounts · <rubric>" (Step 7); with an
  audience, a second workflow and seven "Jev …" fields on company records, adopted if they already
  exist. That audience workflow then **writes those seven fields onto each company record** it
  scores, and never writes on a failed Jev call. The table workflow writes onto the rows of any
  table later bound to it. Only when a wrong connection is fixed through Clay's default (Step 7),
  the installer changes which connection is the workspace default, then changes it back.
- **Sends**: for each scored account, the fields the rubric's questions read (typically name,
  description, industry, a signals field) to Jev at TypeSafe, directly or through OpenRouter.
  Nothing else leaves the installer's systems.
- **Never**: asks for, prints or stores a key in the chat or in a workflow step; writes a key into a
  file git would commit; clears or blanks a field; overwrites a score when Jev failed; edits a
  table's columns; writes to a CRM or a sequencer; deletes anything outside its own nodes.
- **Halts**: Step 1 `other`, Step 2 `other`, Step 3 `other`, Step 4 `other`, Step 5 `sample-review`,
  Step 6 `other`, Step 7 `write-approval`, Step 7 `spend-approval`.
- **Vendor-specific**: Jev, from TypeSafe, reached with a TypeSafe or an OpenRouter key. Without one
  of the two there is nothing to call, so the skill stops at Step 4.

## Representative output

The companies, domains and numbers are invented.

### The rubric card (Step 3, what the installer corrects)

What `rubric_tool.py check` prints for `scripts/rubric.example.json`, saved under the installer's
own name with the cut-offs accepted as defaults.

```
Rubric: Route-planning fit (v1) — scores accounts, 0 to 100

Worked out in code (free, no Jev call):
  Company size               from Employees: under 50 → +0; 50–199 → +10; 200–1,999 → +15;
                             2,000+ → +5
  Region                     from HQ country: is one of united states, us, usa, canada → +10,
                             otherwise +0
  Competitor                 from Website domain: is one of routewise.example,
                             fleetplan.example → DISQUALIFIES

Asked of Jev (one request per account, all questions together):
  Runs its own fleet         Noul (yes/no) on What the company does, Industry: yes +25; no +0
  Segment                    Choice on What the company does, Industry: distributor +25;
                             field_service +15; retailer +8; logistics_provider +0 (disqualifies);
                             other +0; not_enough_information +0
  Growth signal              Score (4 levels) on Recent news or signals: 0 to +15

Most points possible: 90. Tiers: A ≥ 70, B ≥ 45, C ≥ 25, D ≥ 0.
Below 50% coverage (too little data to judge) an account is 'insufficient_data', not a low tier.
Answers under 60% confidence are listed in needs_review.
Borrowed defaults you accepted rather than chose: tier cut-offs.
Jev cost through TypeSafe: about 799 input tokens per account (output is free),
so roughly $0.034 per 1,000 accounts.
```

### The preview (Step 5)

Scores, tiers and review notes are from a live run of the example rubric against Jev; the reasons
are shortened (the tool writes "Segment: a distributor (+25) | …"), and the companies are invented.
A reason counts for the record as "(+25)" and against it as "(2 of 25)", so a low score names what
pulled it down.

| Account | Score | Tier | Why |
|---|---|---|---|
| Northwind Supply | 98 | A | a distributor (+25) · runs its own delivery fleet (+24) · 200–1,999 staff (+15) · explicit fleet expansion (+15) |
| Adventure Works HVAC | 58 | B | a field service business (+15) · 50–199 staff (+10) · in North America (+10) · against: no own fleet (8 of 25); **review: Runs its own fleet: unsure (32% yes)** |
| Contoso Home | 39 | C | 200–1,999 staff (+15) · in North America (+10) · against: no own fleet (2 of 25), a retailer (8 of 25) |
| Fabrikam Freight | 51 | disqualified | Disqualified: a logistics provider · runs its own delivery fleet (+16) |
| RouteWise | 22 | disqualified | Disqualified: a competitor (a rule; Jev was never called) |
| Tailspin Tools | 11 | insufficient_data | 50–199 staff (+10) · No data for: Region, Runs its own fleet, Segment, Growth signal |

`insufficient_data` is not a D: Tailspin's record had no description, so Jev was never asked.
Adventure Works' technicians drive vans but it delivers no goods, and Jev was unsure which that
counts as, so the answer is flagged rather than silently scored. Six accounts cost $0.00010.

### The delivery card and how to call it

````
Account scoring is live: "Jev lead score: accounts · Route-planning fit" (published)

  Rubric       Route-planning fit v1 · 3 rules, 3 Jev questions · tiers A/B/C/D (cut-offs borrowed)
  Jev          TypeSafe, jev-1.13.0 · key in Clay connection "Jev (TypeSafe)"
               and locally in ~/.config/jev-lead-score/.env
  Smoke test   Northwind Supply: local 98 A · Clay 98 A · answers match ✓
  Preview      10 accounts: A 2, B 3, C 1, D 1, disqualified 2, insufficient_data 1 · $0.0002

From a Clay table: add this workflow to the table, starting node "1 Intake", and map
company_name, domain, description, industry, employee_count, country, recent_news onto your
columns (names need not match). The score comes back onto the row.

From anywhere else:
curl -X POST 'https://api.clay.com/v3/sources/webhook/…' -H 'Content-Type: application/json' \
  -d '{"company_name":"Northwind Supply","domain":"northwind.example",
       "description":"Regional foodservice distributor with 60 refrigerated trucks.",
       "employee_count":"501-1,000","country":"United States","source_ref":"row-1041"}'
````

## Files in this skill

| File | What it is for |
|---|---|
| `scripts/jev_lib.py` | the rubric check, the scoring code the Clay steps run, key discovery, state paths, the `clay` wrapper |
| `scripts/rubric_tool.py` | check, save (with version bumps), show and export a rubric |
| `scripts/rubric.example.json` | a complete, invented account rubric to start from |
| `scripts/jev_key.py` | find an existing key, guide, save one through a password box into a `.env`, test it |
| `scripts/score_local.py` | the preview: score up to 50 real accounts on this machine with the exact workflow code |
| `scripts/build_scorer.py` | build, check the connection on, and publish the workflow(s); backfill an audience |
| `scripts/smoke_test.py` | one account through the published workflow, compared with the local score |
| `scripts/test_offline.py` | every generated step, the arithmetic and the builder, with no Clay, network or key |
| `references/jev-api.md` | Jev's two routes, request and answer shapes, price, limits, what it is bad at |
| `references/rubric-format.md` | the rubric file, how a score is worked out, writing questions Jev answers well |
| `references/graph-shape.md` | both workflows node by node, and the traps each avoids |
| `references/live-checks.md` | what was run live against Jev and Clay, and what was not |

Run every script with `python3 -B`. They need only the standard library and the `clay` CLI.

**Do not start a step before the steps above it have their answers.** If a declared input is
missing, ask for it; never assume one and continue.

## Step 0: Say what this builds, what it costs, and check the platform

Three short paragraphs:

1. **What it builds.** A scoring rubric for accounts, previewed on their own records, then a Clay
   workflow that scores any account sent to it and says why.
2. **Where the work runs and what it costs.** Numbers and lists are worked out in the workflow's
   code step, free. Judgments go to Jev, one request per account: about $0.04 per million input
   tokens, a few cents per thousand accounts, billed by TypeSafe or OpenRouter. Each run also counts
   toward Clay's workflow usage; no Clay data credits are spent.
3. **What leaves their systems.** The fields the questions read go to Jev (TypeSafe, directly or via
   OpenRouter). The key never passes through the chat.

Then, without asking: `clay --version && clay whoami` (say the workspace name back),
`python3 -B scripts/test_offline.py`, `python3 -B scripts/rubric_tool.py list` and
`python3 -B scripts/jev_key.py find`. A saved rubric or a found key means those steps are offered as
done, which is how "change the rubric" and "rebuild" resume. If the platform check fails, say which
part and the one command that fixes it, and stop.

## Step 1: Where the accounts come from

Ask **"Where will the accounts you want scored come from?"** (A Clay table / A Clay audience /
Another system, by webhook). Then look, never ask:

- **Table:** list the installer's own tables
  (`clay tables list --filter owner.id=<id from clay whoami>`) and ask **"Which table?"** with up to
  four names as options. Read its columns (`clay tables columns list`).
- **Audience:** `clay audiences list --entity-type companies`, ask **"Which audience?"** the same
  way, read the company fields (`clay audiences fields list --entity-type companies`).
- **Webhook:** no fields to read; the rubric's inputs will be the interface.

The fields that exist decide which criteria are possible. A size rule needs a headcount field; a Jev
question about what the company does needs a description. Carry that list into Step 2.

## Step 2: Build the scoring brief from what you already know, then ask only the gaps

**Before asking anything, write the brief from your own context.** Look in: your memory files and
the project instructions loaded in this session; this conversation; and documents in the working
folder a person would keep about their go-to-market (an ICP or persona doc, a positioning or
messaging doc, a strategy or "anchor context" document, sales notes, case studies). Read, do not
guess.

The brief has seven parts:

| Part | Becomes |
|---|---|
| What they sell, the problem it solves | the frame for every question's wording |
| Best-fit kinds of company, and OK and poor fits | a Choice with described options |
| Traits that make an account a fit (runs X, uses Y, sells to Z) | Nouls |
| Size, region, other numeric or list cuts | rules (only for fields Step 1 found) |
| Disqualifiers | a match rule (domains, names) or a disqualifying Noul or option |
| Signals worth points | a Score over the signals field (only if one exists) |
| What an A must be, and what the tiers are used for | cut-offs |

Show the brief as a short table: each part, what you found, and **where it came from** (a memory
file, the doc name, "this conversation"), or *missing*. Then ask only for the missing parts that
change the rubric, one click at a time, with options drawn from what you found. For example **"Which
kinds of company are your best fit?"** (options from their case studies or docs, plus Other),
**"Anything that should rule an account out entirely?"** (Competitors / Existing customers / A
segment you don't serve / None). If the brief is complete from context, ask one question instead:
**"I built this from <sources>. Anything wrong or missing?"** (Looks right / Correct something).

Never invent a segment, a disqualifier or a signal the installer did not state or a source did not
say. If "what they sell" cannot be found or answered, stop: there is nothing to score against.

## Step 3: Draft the rubric, and have it corrected

Write the rubric JSON following `references/rubric-format.md`, from the brief and the fields Step 1
found:

- **Every number, date or list is a rule.** Headcount bands, region, a competitor's domain.
- **Every judgment is a Jev question**, stating one condition, naming the fields it reads in
  backticks, describing every option. Three to eight questions is typical; more rarely helps.
- A Choice gets `not_enough_information` automatically. Level 0 of a Score means "no evidence".
- Mark anything the installer accepted from you rather than chose with `"origin": "default"`.
- Put what they sell and where each part came from in `about`.

Run `python3 -B scripts/rubric_tool.py check draft.json --provider <provider if known>` and show the
card. Ask **"Does this match how you would judge an account?"** (Looks right / Change the points or
cut-offs / Change a criterion / Other). Edit and re-check until it does, then
`rubric_tool.py save draft.json`. The card's cost line is the price per thousand accounts.

## Step 4: The Jev key, on this machine

`jev_key.py find` already ran. Then:

- **A key sits in a project `.env` in the working folder** (not the shared file, not the
  environment): it may belong to another project or client. Ask **"Use the <provider> key in <that
  file> for this?"** (Yes / No, save a separate key). Never bill one project's key silently.
- **One provider has a key** in the shared file or the environment: use it. Say where it was found
  (the file or the environment, never the value).
- **Both have keys:** ask **"Which should scoring use?"** (OpenRouter / TypeSafe). Same model and
  price; OpenRouter bills the installer's existing OpenRouter account.
- **Neither:** ask **"Which will you use for Jev?"** (OpenRouter: any OpenRouter key works, no
  TypeSafe account / TypeSafe: a key from TypeSafe's console). Run `jev_key.py guide <provider>` and
  relay the steps, then run **in the background** `python3 -B scripts/jev_key.py save <provider>`: a
  password box opens and the key is written to `~/.config/jev-lead-score/.env` at
  0600. If they would rather keep it in a project `.env`, add `--env-file <path>`; the script
refuses a file git would commit. If a key is pasted into the chat, do not use it: say it is now
exposed, ask them to revoke it, and open the box for a fresh one.

Prove it: `python3 -B scripts/jev_key.py check <provider>` (one tiny request).

## Step 5: Preview on ten real accounts

Run `python3 -B scripts/score_local.py --provider <p> --table <id>` (or `--audience <id>`, or
`--file` for a webhook installer's sample) with **`--show-map` first**: it prints how their columns
map onto the rubric's inputs. Show it, take corrections as `--map key=Column`, and never ask them to
type field names from memory. Then run it for real (ten accounts, a fraction of a cent) and show the
table: score, tier, top reasons, anything to review.

**Stop here.** Ask **"Do these scores look right for accounts you know?"** (Yes, build it / Some are
off: adjust the rubric / Try ten different accounts). "Some are off" goes back to Step 3 with the
specific accounts in hand: which criterion moved them, and whether the fix is points, an option's
description, or a missing criterion. Rescore after every change; it costs almost nothing. Point out
any `insufficient_data` rows: that is missing data, not a bad account.

## Step 6: The key in Clay

Ask **"Do you already have a Clay connection holding this <provider> key?"** (No, I'll create one
now / Yes, I'll tell you its name).

- **No:** give the steps from `jev_key.py guide <provider>`: Settings → Connections → Create →
  search "http" → **HTTP API (Headers)** → name it exactly `Jev (OpenRouter)` (or `Jev (TypeSafe)`)
  → one header, `Authorization`, value `Bearer ` followed by the key → Save. Wait for "done".
- **Yes:** take its exact name; it goes to the build as `--connection "<name>"`.

Clay's CLI cannot create or list connections, which is why this one step is theirs.

## Step 7: Build and publish, after one gate

**Build it; never score in the conversation instead.** It has to be a workflow because it runs
unattended: every row of a bound table, every new audience member, every POST from another system,
long after this session ends.

First confirm the node and trigger commands on the installed CLI: `clay workflows nodes --help` and
`clay workflows triggers --help`. `build_scorer.py` creates the workflow (`clay workflows create`),
its trigger (`clay workflows triggers create`) and its nodes (`clay workflows nodes create`, then
`update` with every pin and edge, then read back), in dependency order:

- **Jev lead score: accounts · <rubric>**: webhook trigger → `1 Intake` (code: rules, which
  questions have data, the one Jev request) → `2 Anything to ask Jev?` (conditional) → either
  `2b Score without Jev` (code, terminal) or `3 Ask Jev` (HTTP, key from the Clay connection) →
  `4 Score` (code, terminal).
- **… (audience)**, only with an audience: an audience trigger → the same four steps →
  `2c Save to Audiences` after 2b; after 4, `5 Save it?` → `6 Save to Audiences`, or
  `5b Not saved (Jev failed)`.

The traps it guards against (connections bind by id, headers by reference, complete trigger schemas,
every trigger wired, `$.result` on tool outputs, code steps importing only `json` and `time`) are in
`references/graph-shape.md`.

Run `python3 -B scripts/build_scorer.py --provider <p> --plan` (add `--audience <id>` if Step 1
picked an audience; `--show-audience-map` shows the field mapping to confirm). Then one message with
everything, and the word *write* in it:

> This **writes** to your Clay workspace: one workflow, "Jev lead score: accounts · Route-planning
> fit", published, calling Jev through your connection "Jev (TypeSafe)". [With an audience: a second
> workflow triggered by members of "Target accounts", and seven "Jev …" fields on your company
> records, which it **writes onto every account it scores** from then on.] Each account scored costs
> about $0.00003 in Jev. Nothing is scored until you call it or bind a table [or: until members
> join; scoring the 1,240 members already there is a separate run, about $0.04].

Ask **"Go ahead?"** (Yes, build it / Build it, but don't score existing audience members yet /
Change something first). On yes:

```bash
python3 -B scripts/build_scorer.py --provider typesafe [--connection "<name>"] [--audience <id>]
```

**Exit 6 means the Jev step is on the wrong connection, and its workflow was not published.** Clay
binds a connection to a step by id, its CLI lists no connection ids, and a step written without one
gets whatever connection Clay treats as the workspace default (in testing, the first build landed on
an unrelated connection). Never publish around it: that connection's key would go to Jev. Fix it in
this order, then the same build checks every step again and publishes:

1. **The id, when someone can read it:** re-run with `--connection-id <connection id>`. Verified in
   testing: binds on the first write.
2. **Through Clay's default:** have them open Settings → Connections, find the Jev connection and
   choose **Set as default** from its … menu. Re-run with `--reattach`, which rewrites the Jev step
   so Clay attaches its default (verified in testing). Then have them set the connection the report
   named back as default, so HTTP steps added elsewhere do not pick up the Jev key.
3. Picking the connection on the step itself, in the workflow's draft, and saving. That choice did
   not persist in testing (`references/live-checks.md`, check 7), so treat it as the last resort and
   let the re-run's check say whether it held.

If they approved scoring existing audience members:
`python3 -B scripts/build_scorer.py backfill --audience <id>`. It submits, in batches of 50, every
member whose "Jev score rubric" field does not already read this rubric's name and version, so a
re-run after any interruption or Jev outage submits only what is left.

## Step 8: Prove it with one account

`python3 -B scripts/smoke_test.py --from-preview` sends the first preview account through the
published workflow and scores it locally again. **Match** means the wiring, the connection's key and
the published rubric are all right. A 401 in Clay's result means the connection holds the wrong key;
if the run fails, the script names the step and Clay's error. With an audience, also run
`smoke_test.py --audience`: one member goes through the audience workflow and its "Jev …" fields are
read back from Audiences and compared. Do not call either workflow live until it matches.

## Step 9: Deliver, ending with how to call it

The delivery card from "Representative output", with the real numbers, then **end with how to call
it**, all three ways:

1. **From a Clay table:** add the workflow to the table, starting node **1 Intake**, map the columns
   onto the inputs (names need not match). The score lands on the row.
2. **From an audience** (if built): new members are scored as they join; the fields are filterable,
   so "A-tier accounts not yet in a sequence" is a saved audience.
3. **From anything that can POST:** the webhook URL and a `curl` with a real-shaped body, including
   `source_ref`.

Say what was borrowed rather than chosen, and what was not tested. When asked later: **"change the
rubric"** is Steps 3, 5, 7 and 8 (the version bumps, results say which version scored them);
**"score contacts too"** is the sibling contact skill, which can take this score as an input.

## What this skill does not claim

- The rubric is the installer's judgment written down, not a model trained on won and lost deals.
  Nothing here measures whether A-tier accounts convert better.
- Jev's accuracy on the installer's accounts is not measured beyond the ten-account preview they
  review by eye. TypeSafe publishes its own weaknesses; `references/jev-api.md` lists them.
- Jev's probabilities move slightly between calls on the same input, so a score can differ by a
  point or two on a re-run, and a tier can flip at a cut-off.
- The OpenRouter route is on a path OpenRouter labels `alpha`, and was not run live: the live runs
  used a TypeSafe key. The two take the same request and return the same answers, per both docs.
- The Jev step does not retry. Clay's own retry options on its HTTP step made the step fail before
  calling Jev on every live run, so they are off: a Jev 429 or 529 comes back as `failed` with
  "re-run later", and nothing is written.
- Picking a connection on a workflow step in Clay's UI did not persist in testing; the id and
  default routes in Step 7 did. What was run live is in `references/live-checks.md`.
- A record written to argue for its own classification can move Jev's answer; TypeSafe says so.
- `insufficient_data` means the record lacked fields, not that the account is poor. The skill does
  not enrich; feeding it better data is the installer's move.

## What good looks like

A good run ends with **one account scored identically in Clay and locally**, a published workflow
whose **3 Ask Jev** step is on the installer's named connection, and a preview the installer read
and agreed with. Every score it returns names the criteria that moved it with their points, and an
account with too little data says `insufficient_data` with the fields it lacked rather than posing
as a D. A competitor is `disqualified` without a Jev call.

A thin run looks finished and is not:
- The rubric asks Jev a numeric question ("more than 500 employees?"). That belongs in a rule.
- Every account lands in one tier. The points or cut-offs were never checked against the preview.
- The workflow is published but the smoke test never ran, so the connection's key is unproven.
- The installer was asked what they sell when a doc in the folder said it, or asked to type column
  names.
- A key appeared in the chat, or sits in a project `.env` git will commit.

## Rules

- **Jev decides, code counts.** Never put a number, a date comparison or a count in a question.
- **Context before questions.** Memory, conversation and working-folder docs first; ask only gaps
  that change the rubric.
- **Never invent** a segment, disqualifier, signal or cut-off the installer did not give or a source
  did not state. Accepted proposals are marked borrowed.
- **Always preview on real accounts before building**, and rescore after every rubric change.
- **Missing data is `insufficient_data`, never a low tier.** Five statuses, no sixth.
- **Never ask for, accept, print or log a key in the chat.** Keys go through the password box or
  Clay's connection dialog.
- **Never write a key where git would commit it.**
- **Never publish a workflow whose Jev step is on the wrong connection.**
- **One write gate (Step 7).** Say it is a write, name every workflow and field, price it.
- **Never blank a field; never overwrite a score because Jev failed.**
- **Do not call it live until the smoke test matches.**

## Worked example

The workspace, company and accounts are invented; the steps and outputs are the real shapes.

**Ask:** "Can you set up account scoring in Clay with Jev? We'll feed it from our target accounts
table."

**Step 0.** What it builds, the cost (a few cents per thousand), what goes to Jev; workspace
*Northwind GTM*. `test_offline.py` passes. `jev_key.py find`: "TypeSafe key: found (TYPESAFE_API_KEY
in /Users/ana/work/.env)". No saved rubric.

**Step 1.** Table, named in the ask. "Which table?" → *Target accounts Q4*. Its columns include
Company, Website, About, Industry, Employees, HQ Country, Recent news.

**Step 2.** The brief, from context: *what they sell* and *best-fit segments* from `positioning.md`
in the folder; *disqualifiers* (two competitor domains) from the agent's memory of an earlier
session. Missing: signals and cut-offs. "Should recent news about new locations or fleet growth add
points?" → Yes. Cut-offs: the defaults, accepted, so marked borrowed.

**Step 3.** Three rules, three questions (the card above). "Does this match how you would judge an
account?" → Looks right. Saved as v1.

**Step 4.** The only key is in the project's own `.env`, so: "Use the TypeSafe key in
/Users/ana/work/.env for this?" → Yes. `check typesafe` → "key works".

**Step 5.** `--show-map`: every input matched except `description`, which no column is called; they
point it at *About* (`--map description=About`). Ten accounts scored for $0.0002: A 2, B 3, C 1, D
1, disqualified 2, insufficient_data 1. "Some are off": one field-service company scored C because
its About column was one line. That is data, not the rubric; they accept it.

**Step 6.** "Do you already have a Clay connection holding this TypeSafe key?" → No. The five steps;
they name it `Jev (TypeSafe)` and say done.

**Step 7.** The gate: one workflow, published, $0.00003 an account, nothing scored until called.
Yes. The build exits 6: "3 Ask Jev: on 'Enrichment API', needs 'Jev (TypeSafe)'". They set
`Jev (TypeSafe)` as the default connection in Settings; `--reattach` re-runs and publishes; they set
`Enrichment API` back as default.

**Step 8.** Smoke test: local 98 A, Clay 98 A, answers match.

**Step 9.** The card, then: bind *Target accounts Q4* to **1 Intake** and map the seven columns; or
POST the curl shown. Borrowed: the tier cut-offs. Said plainly: a Jev 429 is not retried; those rows
come back `failed` and are re-run.
