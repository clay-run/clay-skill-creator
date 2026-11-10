---
name: territory-planning
description: |
  Plan territories end to end in Clay: interview the team about their business, write a weighted
  account-fit rubric from a proven template, have the enrichment built for exactly the factors the
  rubric needs, score a handful of known accounts and tune the weights until the grades match the
  team's judgment, write the scores back to the CRM, build the pool of eligible accounts in Clay
  Audiences, carve that pool into fair books per rep with owners written to the CRM after approval, then
  watch the books with signals so an engagement score sits beside the fit score and book health can be
  asked for mid-quarter. Use whenever someone asks: plan our territories, carve accounts to reps, build an account fit score
  for territory planning, score our accounts and assign them, balance books across reps, re-carve for
  next quarter, set up territory rules in Clay, or turn our rules of engagement into actual rep
  assignments, watch my books for signals, how healthy are the books, who has room for the pool.
  Do NOT use it to tier accounts with no assignment at the end (account-tier-scoring), to score or route
  inbound leads or people, to watch accounts that are not in a territory plan, or to write outreach.
  Every score ships with its component scores and a one-line reason; nothing is written to a CRM
  without an explicit approval.
category: score-and-qualify
personas: [revops, sales-leader]
mechanism: workflow
touches: writes-records
keywords: []
---

# Territory planning (interview, score, test, carve)

Skill version 1.10. Say the version when you start, so a test log can name what ran.

The insight: **the score is a hypothesis and the carve is a filter, so the work is a test loop, not a
build.** Teams fail here in two ways: they treat the rubric as settled and discover it was wrong after
a quarter of bad books, or they let an agent improvise the research and get a different score every
run. This skill fixes the rubric in a file the team can read, fixes the interface between research and
scoring so the maths is deterministic, and makes the team judge five accounts they already know before
anything touches a CRM.

**Do not start a step before the steps above it have their answers.** If a declared input is missing,
ask for it. Never assume a default and continue. Steps 2, 4, 6 and 7 end in a gate; a gate is a question
to the user, and the answer is recorded before moving on. Step 8 ends in one too. **Run every step in this session, in the
foreground, with the user watching.** Never hand the run to a background agent or a sub-agent: the gates
are the user's decisions and the credits and the CRM are theirs. If the user asks for the run to be
delegated, say that the gates then stop at every question and keep it in the foreground.

## Declared inputs

Nothing here ships with a value, and **nothing lying in the project folder stands in for an answer**:
notes, run sheets, summaries, transcripts, or a previous run's `rubric.md`, `territory-rules.md` and
`reps.csv` are not inputs. Treat every run as a fresh install and ask the questions. The one shortcut is
an answer sheet named `territory-planning.answers.yaml` one directory above this skill folder, and only
when the user says to use it: then load it, say which values came from it, and ask for the rest. A value
still in angle brackets, or a count of 0, is unanswered. No sheet, no mention of one. The other shortcut
is a business brief the user hands over by name ("use brief.md as my business profile", a Notion export, a
one-pager): read that one file as the Block 1 answers, say which questions it answered, and ask the rest.
A file nobody named is not read, and a brief never answers a gate. `references/worked-example-clay-ops-rules.md`
is one such brief, the one the recorded run used.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Business profile** | what they sell, who buys it, what drives deal size, must-have technology, disqualifiers | no default; this is Step 1 |
| **Known accounts** | 5 domains, each with the grade the team expects, spanning at least three grades. With real customers, 3 best / 1 lost or churned / 1 obvious non-fit is good guidance, not a form; on a sample list, pick five from the list | ask; without them Step 4 cannot run and the rubric stays untested |
| **Account universe** | CRM object and filter, or a CSV with at least a Name and a Website (domain) column | no default; Step 6 has nothing to score |
| **Territory rules** | segments by size, regions, pooled cities, exclusions, protections, capacity per rep | offer `references/territory-rules-starter.md`, fill it with them and save it as `territory-rules.md` in the project |
| **Reps** | `reps.csv`: name, CRM user id, segment, sub-region, capacity | ask; a carve without reps is a ranking |
| **CRM** | Salesforce (v1); the write-back fields exist or the installer can create them | if no CRM, run Steps 6 and 7 inside Audiences and skip write-back |
| **CRM environment** | `sandbox`, `developer edition`, `production` or `none` | ask; a first run never writes to production (see Step 1) |
| **Budget** | credits available for the full run (`clay credits balance`) | state rows x the cost per account measured in Step 4 (min, mean, max) against the balance and get approval before Step 6 runs |
| **Engagement** | which signals watch the books after the carve (company news and funding, GTM leadership hires, sales and RevOps job postings), points per event, the weekly decay, the re-entry rule for pool accounts | the starter's `engagement` block is the default; Step 8 says so and asks (interview Block 5) before any signal starts |

## What this skill touches

- **Reads** the account list, the five known accounts, the enrichment it runs per account and the company
  hierarchy it resolves per account (the operating parent, if any).
- **Writes** a rubric file and a rules file in the project; five Clay workflows (scoring; Territory Carve and Write
  Owners in Step 7; Territory Engagement and its weekly decay in Step 8), three Audiences segments ("to score" for the
  scoring top-up, "Eligible pool" for the carve, "Territory books (assigned)" for the signals) and three Clay Signals
  (Step 8, created paused); fit fields and the Ultimate Parent on CRM accounts (created in Step 5, written from Step 6), the
  proposal fields (Segment, Sub-region, Carve Status, Carve Reason, Proposed Owner; Step 7, by the carve workflow), the
  Owner field (Step 7, after approval only) and the engagement fields (Engagement Score, Last Signal, Last Signal Date;
  Step 8, by the engagement workflows, in the CRM and in Audiences).
- **Never** changes an Owner during scoring, writes to a CRM without a recorded yes, or scores an
  account whose data source failed to run.
- **Halts**: Step 2 sample-review; Step 4 sample-review, spend-approval; Step 6 spend-approval,
  sample-review; Step 7 write-approval; Step 8 signal-start approval.

## Step 0: check the platform and say where the work runs

Start by asking who you are working with (name and role; the approver named later may be someone else).
Run `clay whoami; echo "exit_code=$?"`. If it fails, run the Clay plugin's `setup` skill and stop until
it passes. Name the workspace and **ask the user to confirm it is the one to build in**; a wrong
workspace is a wrong bill. Then run `clay credits balance` and say the number; every price quoted
later is compared to it. Confirm the Clay plugin's `workflows` and `workflows-discover-actions` skills
are available; Step 3 builds with them. Print the skill folder's absolute path (the directory this file
is in) once and set `SKILL="<that path>"` in the shell; every `scripts/` command below is written as
`"$SKILL/scripts/..."`, because the rubric, rules and reps files live in the project, not in the skill folder.

State the cost model up front: interview, rubric and the scorer run in this agent at zero credits;
enrichment runs in Clay and costs roughly one action credit per tool node plus a variable number of data
credits. In four measured runs 60 to 90% of the data credits went to HG Insights, which bills about 8
data credits per product record returned, not per call; the two web-research (Claygent) nodes cost
about 1 to 2 credits each with the capped prompts. The lever is pinning HG to the product ids or names
the rubric needs with a result limit, not the prompts. The cost per account is MEASURED on the five
known accounts in Step 4, never estimated from the catalog, which gets both the size and the shape of
the spend wrong. Test runs bill like live runs.

If a CRM is declared, check both connections now, not at Step 5:
- **Salesforce CLI:** ask which org to use. `sf org list` shows the connected aliases; if more than one
  is connected, the user picks, never the skill. If theirs is not listed: `sf org login web -a <alias>`
  (a Developer Edition signs in at login.salesforce.com; a sandbox at test.salesforce.com). Then
  `sf org display -o <alias>` must succeed. If `sf` is missing: `npm install -g @salesforce/cli`.
  `python3` is needed for the scripts.
- **Clay connection:** the catalog's Salesforce actions (`update-object`, `salesforce-lookup-via-soql`)
  must show a connected app account. If not, the user connects Salesforce under Clay settings →
  Connections. The Audiences *source* (Audiences → Sources → Salesforce, syncing Accounts) is a
  separate step, and it is a UI step the user does by hand: the CLI cannot add a source or start a
  sync. It is optional: Step 6 scores the universe through the manual `domain` input from the account
  CSV by default, and the source only matters for the weekly top-up afterwards. Ask now whether the
  source exists and when it last synced, and say that nothing waits on it.

## Step 1: interview (do not guess)

Follow `references/interview.md`. Front-load only what changes scope or cost: the business profile, the
five known accounts, the CRM and its environment, the universe size. Ask the rest at the step that
needs it: Block 2 before Step 2, Block 3 before Step 6, and Block 4 (the production questions: who owns
what today and how, customers in books and at what share, industry mix, whether the fit floor may move,
which teams own the exceptions, hard vs soft exclusions, what reps receive after a carve and who
approves) before Steps 6 and 7. `references/production-example.md` shows what the answers look like
at a company that runs this for real.

The CRM environment sets the path for Steps 5 to 7:
- **sandbox**: their real accounts are the universe; no sample data. The right place for a real test.
- **developer edition**: offer the sample account list and the field package; Step 5 creates the reps
  from `reps.csv`.
- **production**: refused for a first run. Say why (owners change in Step 7, fields are created in
  Step 5) and offer sandbox or developer edition. Production is for a rubric that has already passed
  Step 4 in a sandbox.
- **none**: CSV into Audiences; Steps 6 and 7 run there and no CRM is written.

## Step 2: write the rubric

Start from `references/rubric-starter.md` (eight factors, weights summing to 100, a one-line rationale each) and
adapt it with `references/rubric-template.md`: drop factors that cannot matter for this business,
reweight toward the factor that is their unit of value, add at most one new factor in v1. Every factor
declares its data need, its kind (`map`, `bands` or `linear`) and its "none" band. Save the result as
`rubric.md` in the project and show the table.

**Gate:** "These are the factors that decide a good account for us, and the weights feel right." Record
the yes.

## Step 3: build the enrichment and the scorer

Design one research step per rubric factor from `references/enrichment-playbook.md`: cheapest
reliable source first, fallbacks gated on the previous step being empty, a judgment step only where no
provider measures the value. Fill the design worksheet in `references/build-and-test.md`, confirm each
action exists in the workspace (catalog cost is a floor, not the estimate), then build it as one Clay
workflow with the Clay plugin's `workflows` skill.

Build research, score and the Audiences upsert only. Do NOT build the Salesforce lookup or write nodes
here: the fields they reference (`Territory_Plan__c`, the score fields) do not exist until Step 5, so
both are added in Step 6. The shape:

- **Trigger**: a manual `domain` input only. Tests, the write-path check and the batched full run in
  Step 6 all go through it. Build NO Audiences segment trigger before the batches: publishing a workflow
  makes a segment trigger live and it would score every record in the segment at once, and the CLI
  cannot pause one (a created trigger is a draft, and only a live trigger can be paused). The "to score"
  segment itself may be defined now, on fields the synced company record actually has: Scoring Status
  empty, domain not empty, limited to the Salesforce sync (the record's source type field). Scoring sets
  Scoring Status, so a scored record leaves the segment on its own. The trigger on it is created in
  Step 6 after the batches, as a draft, for the weekly top-up.
- **Hierarchy first**: a parent and its subsidiaries are one account family, and the parent's headcount
  sets the segment (the rules file's `hierarchy` block; `references/worked-example-clay-ops-rules.md`
  has the rule as one team wrote it). So after Resolve, add `cpj-enrich-company-hierarchies` on the
  resolved domain, then **Pick root domain**, the code node from `scripts/pick_root_domain.py`: it takes
  the parent furthest above the account and skips investors and holding companies by a name-keyword list
  and a domain list, because they own companies without operating them. Measured on a live run: the
  provider returned a venture investor as a developer platform's parent, and without the skip the
  account would have been enriched and scored on the investor. Then **Resolve root**
  (`cpj-enrich-company-v2` on `root_domain`). Every research node and the Score node read the root's
  values; an account with no operating parent is its own root ("Own root"). Reserve two Audiences
  fields, `Family Root` (the root domain) and `Ultimate Parent` (the label), and write them with the
  headline upsert; the CRM field for the label is created in Step 5. Cost: one hierarchy call per
  account plus a second Resolve for children only.
- **Salesforce Account Id**: the company record Audiences syncs from Salesforce usually does not carry
  the Account Id (it carries the owner id, not the record id). Here only reserve a "Salesforce Account
  Id" ACCOUNT field in Audiences with the other fields. The lookup that fills it
  (`salesforce-lookup-via-soql` on Website, filtered on Territory Plan) is wired in Step 6, after
  `sf_setup.py fields` has created `Territory_Plan__c`; built before that, every Step 4 test run errors
  on an unknown column. Steps 6 and 7 read the Id from the Audiences field.
- **Research**: one node per factor. Technographics (HG Insights) is pinned to the specific product ids
  or names the rubric scores, resolved from the action's dynamic lists, with a result limit of at most
  12: HG bills per record returned, so an unpinned call is the single largest cost in the workflow and a
  pinned one returns 0 to 3 records for most companies. The two judgment nodes (classification;
  fundraising, only when the fixed-price funding providers return nothing) take their prompts from
  `references/research-prompts.md`: a visible step budget, a source whitelist, an early exit and a
  strict-JSON rule that holds even when sources conflict. Skip funding research for public or exited
  companies (a provider funding stage of EXITED); it only finds IPO history and answers in prose. With
  the capped prompts the two cost about 1 to 2 credits each.
- **Score**: the code node from `scripts/score_account.py`. It accepts `rubric_json` (the JSON block in
  `rubric.md`) as an input and OUTPUTS, per factor, `<factor>_value`, `<factor>_status` (`found`,
  `none`, `failed`, `capped`) and `<factor>_evidence` next to the component scores, so a run's inputs can
  be saved and re-scored offline. It carries a resolve guard: a Resolve that returns no domain, or an
  under-10-employee match for a company the team knows is bigger, is a wrong match, so the account is
  held (`Held: Resolve failed`), not scored. Any "too big" rule (for example 5,000+ employees to Low Fit
  or excluded) reads the CRM employee count first and the LinkedIn count only as a fallback, because
  LinkedIn over-counts 5 to 9x for some companies. The scorer's default overrides apply the rules
  file's entity-type exclusions at scoring time: `vc_pe`, `agency` and `education` keep their component
  scores, have the total capped at 40 (under the eligibility threshold), grade Low Fit, and the reason
  starts "Excluded by rule". The carve excludes the same types again from `Entity_Type__c`, so neither
  rule alone decides. A seller to whom VC firms or agencies are real customers switches the rules file
  to the opt-in lift form instead (`references/scoring-rules.md`, Grade overrides); the Score node takes
  the block as its `overrides_json` input.
- **Record**: upsert the Audience record with the headline and component fields. The Audiences fields the Step 7
  carve mirrors (Segment, Sub-region, Carve Status, Carve Reason, Salesforce Account Id, Proposed Owner) are created
  by `carve_workflow.py build` when missing, so reserve here only what this workflow writes.

Validate with `clay workflows graph validate`. Test the scorer locally, not in Clay: run
`scripts/score_account.py` with no arguments by its `$SKILL` path (its self-test) and a shim `ctx`
around `handler()` with the saved outputs of a test run. `clay workflows code test` has a daily cap of 10, so keep it for one final
check, if any. Do not publish yet.

## Step 4: test on the five known accounts

Run the five as test runs with the manual `domain` input. Tests bill like live runs. For each run read
the data and action credits used (`clay workflows runs get <wf> <run>`) and record both per run in the
table: account, expected grade, grade, score, the weakest and strongest factor, the one-line reason,
data credits, action credits. State the cost per account as a range (min, mean, max). Four measured
builds on 200-account universes came in at means of 18, 45, 62 and 73 data credits per account, with
6 to 8 action credits each; the one at 18 pinned HG Insights to a short list of product ids and the ones
above 60 let it return a full page. If one run is far above the rest, open its HG node first (records
returned x 8) and tighten the pin list or the limit; look at the agent nodes second, they are 1 to 2
credits each. Also check the resolved employee count against the CRM count: a mismatch over 5x, or a
resolved name that is not the account, is a wrong-company resolve, so hold it and re-run rather than
tune the rubric to it. Read the Ultimate Parent on every test row as well: a known subsidiary should
name its operating parent, a standalone company should read "Own root", and an investor or holding
company in that field means the skip list in `scripts/pick_root_domain.py` needs the name or domain.

Save every run's `<factor>_value/_status/_evidence` outputs to a local JSON list. Follow the evidence
rules in `references/scoring-rules.md`; a factor that ran and found nothing scores its "none" band, a
factor whose source failed holds the whole score. Tune weights in `rubric.md` and re-score the saved
outputs locally at zero credits; rebuild only if a factor changes. Then state the cost of ten more
accounts (10 x the measured max), get a yes, and run them.

**Gate:** "The grades match what we know about these accounts." Record the yes and the rubric version.

## Step 5: create the CRM fields and reps

Run from the project root, with `SKILL` set to the path printed in Step 0:

```
python3 "$SKILL/scripts/sf_setup.py" plan   --rubric rubric.md --segments "<names>" --subregions "<names>"
python3 "$SKILL/scripts/sf_setup.py" fields --org <alias> --rubric rubric.md --segments "<names>" --subregions "<names>"
python3 "$SKILL/scripts/sf_setup.py" reps   --org <alias> --reps reps.csv
python3 "$SKILL/scripts/sf_setup.py" verify --org <alias> --rubric rubric.md
```

`--segments` and `--subregions` come from the rules file's machine spec (`segments[].name`, the routing
sub-regions and pools), never from the script's defaults; `--rules territory-rules.md` in place of the two
flags reads them from the file. The fixed enrichment-value set (Sales and Ops headcount, GTM Motion,
Business Model, growth, funding) is a default for the starter rubric, not a contract: a rubric whose unit
of value is something else (Institution Type and Compliance headcount, Sector and Site Count, Engineering
headcount) passes its value fields with `--extra-fields` on `plan` and `fields`, so they are created,
verified and reset with the rest instead of by hand. The hierarchy label from Step 3 goes the same way:
`--extra-fields "Ultimate_Parent__c:Ultimate Parent:text:255"` (add `Family_Root__c:Family Root:text:255`
if the team wants the root domain on the record too), and the Step 6 write node maps it from the Pick
root domain node. `Headcount_Growth_Pct__c` is Number(7,1); a growth
of several hundred times overflows a narrower field and fails the write. `plan` shows the user the field list and the
API names the write node will map to ("GTM Motion" becomes `GTM_Motion_Score__c`, "Headcount (Size)"
becomes `Headcount_Size_Score__c`): headline fields and enrichment values into Account Details, one score
field per rubric factor into a "Fit Score Components" section, segment, sub-region, carve status,
reason and the Step 8 engagement fields (Engagement Score, Last Signal, Last Signal Date) into a "Territory" section, plus a list view, a report (accounts per rep by segment, average fit)
and a permission set. On their yes, run `fields`; it is idempotent. `reps` creates the rep users
(reactivating any it deactivated before; free licence counts are in `references/crm-fields.md`) and
fills `crm_user_id` into `reps.csv` for Step 7. Then `verify`. Details and the manual route in
`references/crm-fields.md`. If there is no CRM, record that and continue in Audiences only.

## Step 6: load the universe and build the pool

If the org is empty (developer edition), import their account list (or `references/sample-accounts.csv`;
`references/sample-accounts-50.csv` for a quick follow-along at about 1,800 data credits) from the project root:

```
python3 "$SKILL/scripts/sf_setup.py" accounts --org <alias> --accounts <csv>
```

It flags every row `Territory_Plan__c = true`. Salesforce requires an owner, so every imported account is
owned by the admin who ran the import.

Now add the Salesforce nodes to the workflow, appended after the Audiences upserts so the tested edges
stay as they are, in this order:

- **Find the Salesforce Id**: synced Audience records do not carry the Salesforce Account Id, so add a
  `salesforce-lookup-via-soql` node with this query:

  ```
  SELECT Id FROM Account WHERE Territory_Plan__c = true
    AND Website IN ('https://{{domain}}', 'https://www.{{domain}}',
                    'http://{{domain}}', 'http://www.{{domain}}')
  ```

  `{{domain}}` is the bare domain, the same coalesce of the Resolve domain and the trigger domain the
  provider nodes use; the import writes Website as `https://<domain>`, so the four URL forms match it. Follow it with a small code node that picks the first Id, then an
  Audiences upsert that writes it to the "Salesforce Account Id" field reserved in Step 3. Steps 6 and 7
  read the Id from that field. Run one test on a known domain and confirm an Id comes back before adding
  the write node.
- **Write the scores**: `update-object` with `recordId` from the picked Id, `object_type` Account,
  `object_fields` mapped by the API names `sf_setup.py plan` printed (including any `--extra-fields`
  values), `removeNullValues` true, headline fields first and component fields second. Never map Owner
  here. If the new fields do not appear on the action yet, wait and refresh the connection before mapping.

Price the full run as a range against `clay credits balance`: accounts x the measured min, mean and max
from Step 4, plus action credits (6 to 8 per account). Say what share of the balance the mean and max
cases are. Get approval for the first batch and for the total; the approved mean-case figure for a batch
of 25 is the quote the checkpoint below compares against.

Publish. Only the manual trigger exists, so publishing fires nothing. Run one live write-path test on a
known domain and read the account back from Salesforce (score, grade, status, components, Owner
unchanged) before the first batch.

Then score the universe through the published workflow's manual `domain` input, 25 domains at a time
from the imported CSV (minus the write-test account), each run the way Step 4 ran the five, with
`--live`. This is the default path: in four of four runs the Audiences Salesforce source delivered no
imported account inside 30 minutes, so the skill does not wait on it. The SOQL lookup finds the Account
Id, so the write lands in Salesforce, and the Audiences record arrives through the upsert. Before each
batch run `clay credits balance`, compare the last batch's actual spend to the quote, and stop for
re-approval if it ran more than 25% over (a batch that happens to hold the large companies can do that
on HG alone; say so, and continue only on a recorded yes). After the last batch check that every
`Territory_Plan__c` account has a non-empty `Scoring_Status__c`; rerun the missing ones through the
workflow rather than patching them by CLI. Record data and action credits per batch.

The Audiences source is optional production plumbing for the weekly top-up, not a prerequisite. Adding
Salesforce as an Audiences source and syncing Accounts is a UI step the user does by hand; the CLI
cannot do it. If the team wants it, check whether it is delivering with
`clay audiences fields list-values origin_source_type --entity-type companies` and
`clay audiences records search-ids --audience-id <to-score segment>`: a Salesforce-origin value and a
non-zero count mean it is live. Batches through the segment use
`clay workflows runs test <wf> --audience-segment <seg> --record-ids <ids> --live` (up to 50 ids;
`--limit` caps at 10), with the same checkpoint. **A segment-scoped run is refused unless the workflow
has an `audience_segment` trigger**, so create one as a draft first:
`clay workflows triggers create <wf> --input '{"triggerType":"audience_segment","segmentId":"<seg>","entityType":"ACCOUNT"}'`.
A draft trigger fires nothing; it also adds a trigger node whose outputs are `$.fields.<Audiences field
name>` (and `id`), so wire the node that picks the identifier to coalesce the manual `domain` with the
trigger's `Domain` field and strip the scheme, because Audiences stores domains with the https scheme in
front. Read
the trigger node back after creating it; the field path can differ by workspace. Leave the draft
unpublished until the team wants the weekly top-up live, and say plainly that the next publish makes
it live for every record in the segment at once, so it must be preceded by a segment count the team is
willing to pay for and a balance check. Two more Audiences traps from live runs: `upsert-audiences-record`
and `update-audiences-record` ignore blank and null values, so a workflow cannot clear a field; to
reset, write a sentinel (Carve Status "Pool") and widen the segment filter to "empty or Pool". And a
segment filter on `domain` needs the scheme variants (an `Or` of `Equal` on the bare domain, the domain
with the https scheme, and the domain with the scheme and www); `NotEqual` and `ContainAny` did not
exclude records reliably, so exclusions are an explicit `Or` of `Equal` matches.

Define the eligible pool from the rules file: fit at or above the threshold, unassigned, no open
opportunity, not excluded, Scoring Status scored. "Unassigned" means `Carve_Status__c` blank or
`Unowned` AND the owner is the import user; "no owner" matches nothing in Salesforce. The carve workflow's
gates apply this definition per account from the Salesforce fields in Step 7 (the upserted Audiences
record carries only what the workflow wrote, so an Audiences segment cannot filter on open opportunities
or employee count). The Audiences "Eligible pool" segment that `carve_workflow.py segment` creates in
Step 7, on the fields the record does have (scored, fit at or above the threshold, Carve Status empty or
Unowned), is the trigger for the always-on top-up. Report the pool size and the grade mix (a SOQL count on
the filters above). See `references/pool-and-carve.md`.

**Gate:** "This is the pool we want to carve." Record the yes.

## Step 7: carve

The carve is a Clay workflow on the pool, not a script. "Territory Carve" runs once per account, decides
it from the rules file and the scored fields in Salesforce, and writes a proposal; Owner is written only
after the gate, by the Write Owners workflow. Build both from the project root after Step 5 (the gates
read `Territory_Plan__c` and the score fields), during the Step 6 batches:

```
python3 "$SKILL/scripts/carve_workflow.py" build  --org <alias> --rules territory-rules.md --reps reps.csv --out ./carve
python3 "$SKILL/scripts/carve_workflow.py" writer --out ./carve
```

`build` creates a draft with a manual `domain` trigger and eight nodes: Pick domain; Salesforce: read the
account (SOQL on Website in the four URL forms, Territory Plan true, the fields the org has); **Carve
gates**, the code node from `scripts/carve_node.py` (exclusions, size cap, minimum size, eligibility with
the other-industry gate, protections for an existing owner, an open opportunity and a customer, rep
picks, segment, route); a conditional; Salesforce: eligible peers in the bucket (SOQL, every scored
account in the same segment band and region, zero credits); **Carve deal**, the same code node (it
re-applies the gates to every peer, groups the superset into buckets by segment, region, sub-region and
pool, re-runs the whole deal in canonical order against one shared capacity ledger per rep, with Assigned
accounts counted as load, and returns this account's own slot, so concurrent runs agree); Salesforce:
write the proposal (`Segment__c`, `Sub_Region__c`, `Carve_Status__c`, `Carve_Reason__c`,
`Proposed_Owner__c`, never `OwnerId`); Audiences: mirror the proposal. The rules YAML, `reps.csv`, the
pool owner and the field list are baked into the two code nodes; an edit to either file is
`carve_workflow.py update`, not a rebuild. The builder reads the Salesforce connection id off the scoring
workflow's Salesforce node (`--app-account` otherwise) and creates any Audiences field it mirrors that
does not exist. Carve Status is one of `Proposed`, `Assigned`, `Protected`, `Excluded`, `Not eligible`,
`Unowned`; the why is Carve Reason ("snake deal, SA / US West, rank 7 of 38"). Methods: `snake`
(default), `round_robin`, `dynamic`, `manager`, `draft`. The scoring workflow resolves each
account's operating root (Step 3), so the segment the carve reads comes from the root's headcount; the
deal itself is per account, and the local preview is the only place families roll up. Exclusions are
applied twice on purpose: the Score node caps an excluded entity type (VC/PE, agency, education) at 40
and grades it Low Fit with the reason, and the carve gates exclude it again from `Entity_Type__c`, so a
change in either place alone cannot put one in a book.

Test one account, then carve everyone, at zero data credits (both Salesforce actions are free):

```
python3 "$SKILL/scripts/carve_workflow.py" run --org <alias> --out ./carve --limit 1      # one known domain; read it back: status, reason, proposed owner, Owner unchanged
python3 "$SKILL/scripts/carve_workflow.py" run --org <alias> --out ./carve                # every scored account not yet Assigned, 25 at a time, logged to carve/carve-runs.jsonl
python3 "$SKILL/scripts/carve_summary.py"  --org <alias> --rules territory-rules.md --reps reps.csv --out ./carve [--rubric-version <X>]
```

Every scored account comes back with a status and a reason on its record. Show the user
`carve-summary.md` in `./carve`: the rep-count proposal (eligible per segment divided by capacity, rounded up;
with `dynamic` or a given `reps.csv` it is a note about the gap, not a proposal), the books (Proposed
plus Assigned per rep: capacity, count, mean fit, grade mix, core share, self-serve share) next to the
balance verdict and the composition targets per segment, the ten highest-fit accounts not in a book,
exclusions, not-eligible and protected by reason, and skipped protections. The "Territory – Proposed
Books" report in the org is the same picture. Show `patch-doc.md` too: what's new, the criteria table,
per-rep book, FAQ. To change a knob before the gate: edit the rules file, preview at zero cost with
`scripts/carve.py` (same `--org`, `--rules` and `--reps` flags, `--out ./carve-preview`; it writes nothing),
then `carve_workflow.py update`, `carve_workflow.py reset-proposals --org <alias> --yes` and `run`
again. If the rep count changes, add the rep to `reps.csv`, run `sf_setup.py reps`, then `update`,
`reset-proposals`, `run`. Every option is in `references/carve-scenarios.md`; the carve reads the rules
file and nothing else.

**Gate:** "Approve these books." Record the yes. Snapshot `Id, OwnerId, Carve_Status__c` for the plan
accounts with `sf data query` first. Then the Write Owners workflow (a manual trigger with `account_id`,
`domain`, `owner_id`, `segment`, `sub_region`, `carve_status`, `carve_reason`; a Salesforce
`update-object` writing `OwnerId`, `Segment__c`, `Sub_Region__c`, `Carve_Status__c`, `Carve_Reason__c`
with `removeNullValues` true; an Audiences mirror) copies Proposed Owner to Owner from
`write-owners.jsonl` in `./carve`, which `carve_summary.py` wrote with the Proposed rows only, as three
separate commands:

```
clay workflows publish <write-wf>
clay routines create workflow <write-wf>
clay routines runs start <routine> --bulk carve/write-owners.jsonl
```

Tell the user before the third command that Claude Code's permission classifier will ask them to approve
the bulk write (it shows as "Modify Shared Resources"); the prompt is expected and is the human's
approval of the write, so never chain the three into one command. The write costs action credits only,
no data credits. Verify with the "Territory – Accounts by Owner" report: every Proposed row is now
Assigned with the proposed rep as owner, counts and mean fit match `carve-summary.md`, and no Assigned
account carries a Low or Bad Fit grade. If `deliverables.approval_channel` names a channel, send the
patch doc there; if approval was in-session, the file in `carve/` is the deliverable, so say where it is.

**Always on.**

```
python3 "$SKILL/scripts/carve_workflow.py" segment --org <alias> --rules territory-rules.md --out ./carve
```

This creates the Audiences segment "Eligible pool" (domain not empty, Scoring Status scored, fit at or above
the threshold, Carve Status empty or Unowned) and an `audience_segment` trigger on the carve workflow as
a draft, and wires the Pick domain node to the segment record. Test it with
`clay workflows runs test <carve-wf> --audience-segment <seg> --limit 2` and read the Pick domain
output: the record's domain path can differ by workspace. Say plainly before anyone publishes:
publishing the carve workflow makes the trigger live and proposes an owner for every record in the pool
at once (zero data credits), and from then on a newly scored account that clears the floor gets a
proposed owner on its own; the manager approves on `cadence.top_up` with the summary and a Write Owners
run.

## Step 8: engagement after the carve

The books are not the end. Once Write Owners has run, the same accounts keep moving: one hires a sales
leader, one raises a round, one opens SDR roles. Step 8 watches the assigned books and the pool with
three Clay Signals and keeps an **Engagement Score** next to the fit score, in Salesforce and in
Audiences, so a rep sees heat and a manager can ask for book health mid-quarter. Fit says whether an
account belongs in a book; engagement says when to work it. The two stay separate on purpose, and
neither one moves an owner.

Everything is read from the rules file's `engagement` block (`references/territory-rules-starter.md`,
section 7): which signals, points per event, the weekly decay, the re-entry rule. Ask the user to confirm
the defaults or change them (interview Block 5) before building. Build from the project root:

```
python3 "$SKILL/scripts/engagement.py" build --org <alias> --rules territory-rules.md --carve ./carve --out ./engagement
```

`build` is idempotent (state in `engagement.json` in `./engagement`) and creates, all as drafts: the
Audiences fields Engagement Score, Last Signal and Last Signal Date; the segment "Territory books
(assigned)" (Carve Status = Assigned); one signal per enabled type (company news and funding, GTM
leadership hires, sales and RevOps job postings), **paused**, watching the assigned segment and the
Eligible pool; the "Territory Engagement" workflow (a manual trigger with `domain`, `signal_type` and
`headline` for tests, one `audience_signal` trigger per signal, then Pick the event, Salesforce: read the
account, Score the event, In the plan?, Salesforce: write the engagement score, Audiences: mirror); and
the "Territory Engagement Decay" workflow, an `audience_scheduled` trigger per watched segment that
multiplies the score by `engagement.decay.keep` once a week. The Salesforce fields are part of the Step 5
package; on an org set up before v1.10, run `sf_setup.py fields` again, it is idempotent and adds the
three. The nodes are listed in `references/pool-and-carve.md`.

Test one event before anything runs on its own, at zero data credits, on a plan account the user picks:

```
python3 "$SKILL/scripts/engagement.py" test --org <alias> --out ./engagement --domain <known domain> --type NewHire --headline "VP Sales joined"
```

It fires the manual trigger, waits for the run and reads the account back: Engagement Score up by the
points for the type, Last Signal and Last Signal Date set, the same three on the Audience record, Owner
unchanged. Show the record in both places. A test run executes the two writes for real; say so first.

**Gate:** "Start the signals." Say first what starts: three weekly checks over the watched accounts (the
command prints the count), each event found costs data credits as Clay Signals do, and the Engagement
workflow must be published for events to score (a draft trigger fires nothing; the test above ran the
draft by hand). On the yes, as two commands:

```
clay workflows publish <engagement-wf>
python3 "$SKILL/scripts/engagement.py" resume --out ./engagement --yes
```

Publish the decay workflow only if the team wants the score to fade (Block 5); unpublished, the score is a
running total for the quarter. `engagement.py status` shows each signal's state, last run and error, and
the accounts with the most heat; `pause` stops all three.

**Book health, mid-quarter.** When the user asks how the books are doing, who has room, or what to do
with the pool, in any wording, run:

```
python3 "$SKILL/scripts/engagement.py" health --org <alias> --rules territory-rules.md --reps reps.csv --out ./engagement
```

It writes `book-health.md` in `./engagement`: per rep, capacity (same precedence as the carve), Assigned
count, room, mean fit, mean engagement and the hottest accounts in the book; then the pool accounts that
clear the re-entry rule (`engagement.reentry`: engagement at or above `min_engagement` with fit at or
above `min_fit`) or the fit floor, ranked by heat, each with the rep who has the most room in its segment
and region. Those are candidates, not assignments. Assigning them is the Step 7 loop on the pool, with
its approval: `carve_workflow.py run --only-pool` (it now re-decides Not eligible accounts too, and the
gates read the re-entry rule, so a hot account below the floor can be dealt), the summary, "Approve
these books", Write Owners. Nothing here moves an account out of a book; re-carving Assigned accounts is
a quarterly decision, not a signal.

## Next quarter

A weight change is an edit to `rubric.md` and a re-score. A new factor goes back to Step 3. A rules
change (threshold, capacity, exclusions, routing) is an edit to the rules file, then
`carve_workflow.py update`, `reset-proposals`, `run`, the summary and the approval; Assigned accounts
stay where they are and count as load. Keep the rubric versioned; the version is written with every score.

To reset a developer edition after a test run: `sf_setup.py reset --org <alias> --yes` removes the
accounts, fields, layout changes, reports and rep users; `clay workflows delete <wf>` removes a workflow
(it takes no `--yes` flag; there are five: scoring, Territory Carve, Write Owners, Territory Engagement,
Territory Engagement Decay), `clay signals delete <id>` removes a signal (the three Step 8 ids are in
`engagement.json`), and the "to score", "Eligible pool" and "Territory books (assigned)" segments are archived. The CLI prints JSON by default; the list
commands have no `--json` flag.

## Representative output

### Step 4: the test table

As the team reads it (invented companies, rubric 1.0, threshold 60):

| Account | Expected | Fit | Grade | Ultimate Parent | Strongest | Weakest | Reason |
|---|---|---|---|---|---|---|---|
| Contoso | strong | 86.4 | Best Fit | Own root | Technographics (CRM + warehouse + competing vendor) | Fundraising (no round in 18 months) | Best Fit (86.4). Strongest: Technographics (CRM + warehouse + competing vendor). Weakest: Fundraising (no round in 18 months). |
| Northwind Traders | middle | 61.2 | Moderate Fit | Contoso (contoso.com) | GTM Motion (PLG + sales) | Sales Team (4 sellers, no GTM Engineer) | Moderate Fit (61.2). Strongest: GTM Motion (PLG + sales). Weakest: Sales Team (4 sellers, no GTM Engineer). |
| Fabrikam Ventures | off | 40.0 | Low Fit | Own root | Technographics (CRM + warehouse) | Business Model (B2B, non-SaaS) | Excluded by rule (vc_pe): not carved into a territory. Unadjusted score 71.5. Good Fit (71.5). Strongest: … |

### Step 7: the carve summary

The part of `carve-summary.md` the approver reads first:

| Rep | Segment / region | Capacity | Proposed + Assigned | Mean fit | Best / Good / Moderate |
|---|---|---|---|---|---|
| Rep A | SA / US West | 60 | 58 | 74.1 | 21 / 25 / 12 |
| Rep B | SA / US East | 60 | 57 | 73.6 | 19 / 27 / 11 |
| Rep C | SL1/SL2 / NAMER pooled | 50 | 50 | 77.9 | 24 / 20 / 6 |

Balance: counts within 2, mean fit within 4.3 points. Not in a book: 14 eligible accounts over capacity
(highest fit 79.0), 3 `Excluded: vc_pe`, 9 `Protected: open opportunity`. Each account's record carries
the same decision as `Carve_Status__c` plus `Carve_Reason__c`, for example "snake deal, SA / US West,
rank 7 of 38".

## What good looks like

- The team can answer "why is this account in this book?" from the record: component scores, the one-line
  reason, the segment, the carve reason and the proposed rep, with no black box.
- The five known accounts graded the way the team expected before anything was written to the CRM, and
  the rubric version that passed is written with every score.
- Excluded types read as excluded in both places, the grade and the carve status, and no Assigned account
  carries a Low or Bad Fit grade.
- A subsidiary shows its operating parent and sits in the parent's segment; a standalone company reads
  "Own root"; no account shows an investor as its parent.
- Credits were quoted as a measured range per account before the universe ran, and every batch was
  checked against the balance.
- After the carve, an assigned account that hires a sales leader shows the event and a higher engagement
  score on its record in both places within the week, Owner unchanged, and a pool account that heats up
  appears in the book-health candidates with the rep who has room.
- A re-carve next quarter is a rules file edit plus a rerun, not a rebuild, and Assigned accounts stay put.
- The common mistake: a rubric that cannot separate, visible as identical books in the summary, or an
  excluded type reaching a book because only one of the two exclusion rules was edited.

## What this skill does not claim

- It has not been run end to end against a HubSpot CRM; v1 write-back is Salesforce only.
- Hierarchy: the scoring workflow resolves the operating root (investors and holding companies skipped)
  and scores the account on it, writing Family Root and Ultimate Parent, so the segment follows the
  parent's headcount. The carve still deals per account: the parent's owner is not carried down to
  children, F500 parents are not detected, and `family` roll-up (the parent's owner and opportunities
  carried down) exists in the local preview only. The investor skip list is a name-keyword list plus a
  domain list; a provider that returns an investor not on it scores the account on the investor until
  the list is extended. `buying_centre` is not implemented.
- The carve workflow's segment-trigger path is tested with `runs test --audience-segment` before anyone
  publishes, because the segment record's domain path can differ by workspace; the manual-trigger path
  is the proven one.
- It does not back-test weights against closed-won history automatically; the five known accounts are
  the test, and a closed-won back-test is a manual follow-up the skill suggests.
- Enrichment results vary by a few points between runs; the test asks for grades, not exact scores.
- Cost per account varied from 18 to 73 data credits across four measured builds, depending almost
  entirely on how tightly the HG Insights node is pinned (it bills per product record returned); the two
  research nodes are 1 to 2 credits each. The skill quotes a measured range, not a price list.
- v1 segments on employee count only; revenue bands need a CRM revenue field the enrichment does not
  produce. v1 balances books on count and mean fit; revenue, workload and composition are reported next
  to the books, not balanced.
- Adding or syncing the Audiences Salesforce source is a UI step the user does by hand; the CLI cannot do
  it, and in four of four runs it delivered nothing inside 30 minutes. The universe is therefore scored
  through the manual `domain` input from the imported CSV by default; the source and the segment trigger
  are optional plumbing for the weekly top-up. `references/sample-accounts.csv` is a B2B software list;
  a seller to another vertical should bring its own CSV or expect few core-industry accounts.

## Files

- `references/interview.md`: the questions and how answers map to factors.
- `references/rubric-template.md`: how to adapt the template, factor kinds, overrides, grades.
- `references/scoring-rules.md`: evidence rules, the scorer's contract, the reason line, the test protocol.
- `scripts/score_account.py`: reference scoring node, rubric-driven, zero credits; default overrides exclude vc_pe, agency and education (cap 40, Low Fit) with the opt-in lift form still available.
- `scripts/pick_root_domain.py`: the hierarchy code node; picks the operating root and skips investors and holding companies; `python3 pick_root_domain.py` runs the self-test.
- `scripts/sf_setup.py`: Salesforce fields, layout sections, report, reps, account import and a dev-org reset, from the rubric, via the `sf` CLI.
- `scripts/carve_node.py`: the carve code node (gates and deal, deterministic, `json` only) plus the shared logic and a self-test; `python3 carve_node.py` runs the self-test.
- `scripts/carve_workflow.py`: builds the "Territory Carve" and Write Owners workflows in Clay (`build`, `writer`), pushes rules edits (`update`), carves the universe through the manual trigger (`run`), creates the "Eligible pool" segment and its draft trigger (`segment`), and reports or clears proposals (`status`, `reset-proposals`).
- `scripts/carve_summary.py`: reads the proposal back from Salesforce and writes `carve-summary.md`, `carve-proposal.csv/json`, `write-owners.jsonl` (Proposed rows only) and `patch-doc.md`.
- `scripts/carve.py`: zero-credit local preview of the same gates and deal (with family roll-up), nothing written.
- `scripts/engagement.py`: Step 8: builds the "Territory books (assigned)" segment, the three signals (paused), the "Territory Engagement" workflow and its weekly decay (`build`), fires one test event (`test`), starts and stops the signals (`resume`, `pause`), reports (`status`) and writes `book-health.md` with the pool candidates (`health`).
- `scripts/miniyaml.py`: stdlib reader for the rules file's YAML machine spec, imported by the carve scripts.
- `references/sample-accounts.csv`: 200 real B2B companies for a developer edition that has no accounts; `references/sample-accounts-50.csv` is the 50-account cut used in the recorded run (the known five, ten non-US accounts, five non-tech ones), the right size for a first follow-along.
- `references/enrichment-playbook.md`: source, order, cost and output contract for every factor; how to add one.
- `references/build-and-test.md`: the design worksheet, workflow shape, running and re-scoring.
- `references/crm-fields.md`: field spec and the three ways to create the fields.
- `references/pool-and-carve.md`: Audiences import, segment definition, the carve, the report.
- `references/carve-scenarios.md`: how teams carve in practice, every option per decision, benchmarks, and the knob each maps to.
- `references/research-prompts.md`: step-budgeted prompts for the two research nodes; providers before research; when to skip funding research.
- `references/production-example.md`: a real company's V2 model, segmentation from the Ultimate Parent, composition targets, eligibility gate, exclusion list, and the "what's new" and FAQ patch doc.
- `references/rubric-starter.md`, `references/territory-rules-starter.md`, `references/reps-starter.csv`: starting files to copy into the project.
- `references/worked-example-clay-ops-rules.md`: one team's complete rules document (segments, weighted score, eligibility, exclusions, hierarchy) as the interview's worked example.

## Changelog

- 2026-10-02, v1.4: cost is measured on the five known accounts (about 85 data credits each, ~10x
  variance on the research nodes) and checked against `clay credits balance`; the Salesforce write node
  moves from Step 3 to Step 6, after the fields exist; the trigger is an Audiences "to score" segment
  with a manual domain input for tests; the score node outputs `<factor>_value/_status/_evidence` for
  offline re-scoring; Step 5 commands use the skill's absolute path and the rules file's segments;
  `reps` fills `crm_user_id` into `reps.csv`; the universe is scored in batches of 25 with a credit
  checkpoint; "unassigned" is defined against the import user; one canonical carve order with family
  roll-up, a proposed rep count and capacity precedence; the patch doc is a Step 7 output; new
  references `research-prompts.md` and `production-example.md`.
- 2026-10-02, v1.5: the Salesforce Account Id is found by a `salesforce-lookup-via-soql` node on Website
  (four URL forms, Territory Plan true) and written to a "Salesforce Account Id" Audiences field, since the
  synced record does not carry it; the "to score" segment is defined on fields that exist; the segment
  trigger is paused right after publish (or created after the batches; superseded in v1.7, since a
  CLI-created trigger is a draft that cannot be paused) and batches run with
  `runs test --audience-segment --record-ids` because `--limit` caps at 10; the fundraising prompt gets a
  conflicting-sources rule and a strict-JSON rule, with the output schema fields required.
- 2026-10-02, v1.6: the `salesforce-lookup-via-soql` and Pick-Id nodes move from Step 3 to Step 6 with
  the write node, since the query filters on `Territory_Plan__c`, which Step 5 creates; Step 3 only
  reserves the "Salesforce Account Id" Audiences field. Step 6 checks the Audiences source with
  `origin_source_type` and the segment count before waiting, bounds the wait at 15 minutes, and falls
  back to scoring from the imported CSV through the manual `domain` input in batches of 25; Step 0 says
  the source is a UI step the user does by hand and confirms it for a developer-edition run. Interview
  Q12 and Q16 state the v1 limits: segments on employee count, balance on count and mean fit.
- 2026-10-02, v1.7: from four end-to-end runs on empty developer editions. Cost: HG Insights bills about
  8 data credits per product record returned and was 60 to 90% of spend; the two Claygent nodes cost 1 to
  2 credits each; measured means were 18 to 73 per account, so HG is pinned to product ids or names with
  a result limit of at most 12 and the "85 mostly Claygent" prior is gone. Trigger: no segment trigger
  before the batches; it is created afterwards as a draft and left unpublished (the CLI cannot pause a
  draft, and publishing makes it live). Batches: the Audiences Salesforce source delivered nothing in 30
  minutes in four of four runs, so the default path is the published workflow's manual `domain` input,
  25 domains at a time, `clay credits balance` before each batch, re-approval over 25%; the source is
  optional top-up plumbing. The Salesforce Id comes from a `salesforce-lookup-via-soql` node on Website
  plus a Pick-Id node writing an Audiences "Salesforce Account Id" field. Owner write is a "Write Owners"
  workflow published, registered as a routine and run in bulk, with the permission prompt named. Step 7
  runs `scripts/carve.py` (with `scripts/miniyaml.py`). Size: too-big rules read the CRM employee count,
  `Headcount_Growth_Pct__c` is Number(7,1), a no-domain or under-10-employee resolve is held, funding
  research is skipped for public or exited companies. `sf_setup.py --extra-fields` for rubric-specific
  values; known accounts are five with expected grades; the scorer is tested locally because `code test`
  caps at 10 a day; reset notes.
- 2026-10-02, v1.8: the carve moves from a local script into the "Territory Carve" Clay workflow on the
  pool. `scripts/carve_node.py` is a deterministic code node in two modes: gates (exclusions, size,
  eligibility, protections, rep picks, segment, route) and deal (every scored account in the same segment
  band and region is read back by SOQL, the whole superset's deal is re-run against one shared capacity
  ledger with Assigned accounts as load, and the account's own slot is returned, so concurrent runs
  agree); `scripts/carve_workflow.py` builds it, pushes rules edits, carves 25 domains at a time at zero
  data credits, builds the Write Owners workflow, and creates the "Eligible pool" segment with a draft
  `audience_segment` trigger (publish makes it live: the always-on top-up). Carve Status gains `Proposed`,
  Salesforce gains a `Proposed_Owner__c` lookup and a "Territory – Proposed Books" report for the
  approver; the approved write copies Proposed Owner to Owner from the Proposed rows
  `scripts/carve_summary.py` writes. `scripts/carve.py` stays as the zero-credit local preview (the only
  place family roll-up runs). Region exclusions match country codes and names (Middle East, CIS, Africa,
  APAC expand to codes). `sf_setup.py --without` leaves a planned field out if an org rejects it.
- 2026-10-19, v1.9: from a recorded end-to-end run on 16 Oct. Hierarchy moves into the scoring workflow:
  `cpj-enrich-company-hierarchies` after Resolve, then `scripts/pick_root_domain.py` picks the operating
  root and skips investors and holding companies (a provider returned a venture investor as a parent),
  then a second Resolve on the root; research and scoring run on the root; Family Root and Ultimate Parent
  are written to Audiences and `Ultimate_Parent__c` to the CRM via `--extra-fields`. Exclusions now run
  at scoring time too: the default overrides cap `vc_pe`, `agency` and `education` at 40 and grade Low Fit
  with an "Excluded by rule" reason (the opt-in lift form remains in the rules file; the Score node takes
  the block as `overrides_json`). Segment-scoped runs: `runs test --audience-segment` needs a draft
  `audience_segment` trigger, whose node outputs `$.fields.<name>`; the identifier node coalesces the
  manual domain with the trigger's and strips the scheme. Audiences traps recorded: upsert and update
  ignore blank values (reset by sentinel), domain filters need scheme variants. Marketplace frontmatter
  (category, personas, mechanism, touches), Representative output and What good looks like added.
  `references/worked-example-clay-ops-rules.md` added as the interview's worked example.
- 2026-10-28, v1.10: Step 8, engagement after the carve. `scripts/engagement.py` builds the "Territory books
  (assigned)" segment, three paused Clay Signals (company news and funding, GTM leadership hires, sales and
  RevOps job postings) watching the books and the pool, the "Territory Engagement" workflow (manual test
  trigger plus one `audience_signal` trigger per signal; each event adds points to an Engagement Score,
  capped, written to Salesforce and mirrored to Audiences with Last Signal and Last Signal Date) and a
  weekly "Territory Engagement Decay" workflow on `audience_scheduled` triggers; `test`, `resume`,
  `pause`, `status`, and `health` (book-health.md: capacity, load, room, heat per rep; pool candidates
  under the re-entry rule with the rep who has room). The rules starter gains section 7 and an
  `engagement` block; the interview gains Block 5; Step 5 creates `Engagement_Score__c`, `Last_Signal__c`
  and `Last_Signal_Date__c`; the carve gates accept the re-entry rule and `run --only-pool` re-decides
  Not eligible accounts. A business brief the user names is read as the Block 1 answers. Measured on the
  CLI: an `audience_signal` trigger node outputs `$.fields` and `$.signal` (`signalType`, `emittedAt`,
  `activityTime`, `data`); `audience_scheduled` takes `segmentId` plus a simple weekly `scheduleConfig`.
- 2026-10-29, v1.10 live-run fixes (recorded end-to-end run on a fresh Developer Edition and a fresh workspace, 50
  accounts, 1,742 data credits, 39 owners written, signals live): `pick_root_domain.py` keeps a parent whose domain
  does not match its name (a LinkedIn shortlink, 5tran.co for Fivetran) as the label only and scores the account on
  its own domain; `engagement.py` reads the event headline from the nested signal payload (`newsData.newsTitle` +
  publisher, person + job title) instead of raw JSON, and says "engagement" rather than "heat"; `carve_workflow.py`
  reads the Salesforce connection id from the catalog's `availableAppAccounts` when no workflow node carries it yet,
  and strips `codeTimeoutMs`, which this CLI version rejects; `run --only-pool` re-decides Not eligible accounts.
  References: `Is_Competitor__c` means a direct competitor, never "uses a competing vendor" (28 accounts were
  wrongly excluded before the fix); Harmonic EXITED on an acquired-but-private company still scores its own round;
  a conditional node must call `transition_to` on every path. Measured: the `dynamic-fields` probe reports
  MISSING_ACCOUNT unless `--account` is passed, even when the connection works.
