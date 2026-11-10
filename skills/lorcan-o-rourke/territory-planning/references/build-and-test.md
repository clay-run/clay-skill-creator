# Build and test (Step 3 and Step 4; the carve workflow in section 7)

## 1. Design worksheet

Fill one row per rubric factor from `references/enrichment-playbook.md`, then confirm every action key
exists in the workspace (Clay plugin `workflows-discover-actions` skill, or `clay routines list` and
`clay routines get`). Show the finished worksheet to the user before building. The cost column is a
prior, not the number anyone approves against; the approvable per-account figure comes from measuring
the five known accounts in section 3. What four measured runs of this skill (200 accounts each, four
different rubrics) established:

- **HG Insights is the cost driver.** It bills about 8 data credits per product record returned, not
  per call, and it was 60 to 90% of spend. The per-account ceiling on that node is 8 x its result
  limit. Mean data credits per account over the four runs: 62, 45, 18 and 73; the 18 came from a build
  that pinned HG to about 34 specific product ids, so most companies returned 0 to 3 records.
- **The two Claygent nodes cost about 1 to 2 data credits each** with the capped prompts in
  `references/research-prompts.md`. Tightening them further does not move the number.
- **The lever is the HG pin**: pin the node to the specific product ids (or exact product names) the
  rubric scores and set the result limit to 12 or fewer. Pinning whole vendors (SAP, Oracle, Microsoft,
  GitHub, Amazon) returns hundreds of unrelated products at 8 credits each, and short vendor names
  (FIS, Alloy) substring-match unrelated products. Resolve names to ids from the action's dynamic
  field list (`clay workflows actions dynamic-fields hg-insights-get-company-tech-stack-v3`), match on
  id in the code node, and record any product HG does not carry as "not detectable" in the rubric.
- Tool nodes cost about one action credit each; the funding providers are flat (about 3 to 4 data
  credits each).

```
| factor id        | data need                                 | source (action keys)                                                                                   | value shape                                                        | cost/acct: measure on the five known accounts (prior) |
| technographics   | CRM, warehouse, any of [competitors]      | one HG call, `hg-insights-get-company-tech-stack-v3`, `product_ids` (or exact `product_names`) pinned to the products the rubric scores, `limit` <= 12; no fallback tiers | crm+dw+competitor, crm+dw, one, none                               | ~8 data per record returned (ceiling 8 x limit) + 1 action |
| gtm_motion       | self-serve vs sales-led                   | one Claygent call shared with business_model (also entity type and status); prompt in research-prompts | hybrid, plg, sales_led, early                                      | ~1-2 data with the capped prompt; budget 6 steps      |
| business_model   | B2B/B2C, SaaS, AI-native                  | same call                                                                                              | b2b, b2b+b2c, b2c + flags                                          | 0 (shared)                                            |
| sales_team       | sales headcount, open SDR roles           | `cpj-get-counts-for-profiles-v2` (job_functions Sales) + `cpj-find-lists-of-jobs` (SDR/BDR titles)     | number; 20+ open SDR roles -> 100; sales >= 5% of staff -> max(count, 50) | ~1 action each                                 |
| ops_team         | ops / RevOps / GTM Engineer headcount     | `cpj-get-counts-for-profiles-v2`, title keywords incl. GTM Engineer; ONE combined roleCount per call  | number                                                             | ~1 action                                             |
| headcount_growth | 12-month % change                         | `cpj-get-company-employee-growth-v2`                                                                   | percent                                                            | ~1 action                                             |
| fundraising      | last round amount and date                | fixed-price providers first (Intellizence, Harmonic, Dealroom, Crunchbase); Claygent only if empty, behind a code gate; skipped for vc_pe, education, government and public or exited companies (provider stage EXITED, IPO, PUBLIC) | USD amount; 1 if older than 18 months; -1 for VC/PE (band 80) | providers ~3-4 data each; Claygent ~1-2 data; budget 8 steps |
| headcount        | employee count                            | from the resolve step (`cpj-enrich-company-v2`)                                                        | number                                                             | 0                                                     |
```

Constraints that hold for every row: a search that completes with no match is status `none`, not
`failed`; a list that hit its result limit is `capped`; no provider call for a factor with weight 0;
every row states its cost prior; every Claygent row states its step budget, and its prompt comes from
`references/research-prompts.md` (source whitelist, early exit, visible step budget). Technographics is
a single pinned HG call; a clean empty result is the "none" band, and only an HG error justifies a
fallback. An HG page that comes back at the limit scores the top band with "(capped)" in the evidence,
since an unseen record can only add a category; the fix for cost is a tighter pin, never a higher limit.
Tool nodes have no run condition, so a fallback that must be gated (the funding Claygent) sits behind a
code or conditional node; the flat-priced providers run unconditionally.

## 2. Workflow shape

Build one workflow with the Clay plugin's `workflows` skill. Keep the shape fixed so every build looks
the same:

1. **Trigger**: in Step 3, one manual trigger with `domain` (plus an optional `linkedin_url` that
   Resolve prefers when given, for re-running a wrong match). Do NOT build an Audiences segment trigger
   before the Step 6 batches: publishing makes a live segment trigger score every record in its segment
   at once, skipping every credit checkpoint, and the CLI cannot pause one (a created trigger is a
   draft, and only a live trigger can be paused). The "to score" segment itself (scoring status empty,
   domain not empty, limited to the Salesforce source; each record carries the domain and the owner id,
   not the Account Id) can be created at any time; its trigger is created after the batches as a draft
   and left unpublished until the team wants the weekly top-up live (section 6). The Salesforce lookup
   and write nodes are added in Step 6 and do not exist before that, so a Step 4 test run cannot touch
   the CRM.
2. **Resolve**: `cpj-enrich-company-v2` from the domain; status `failed` if it does not resolve (the
   gate that holds). Feed every provider node the coalesce of the Resolve node's domain and the trigger
   domain (`resolved_domain || domain`): a resolved record can come back without a domain, and a node
   fed `resolved_domain` alone then loses its required input and fails the run. **Resolve guard** (in
   the adapter, item 4): a match with no domain, or with under 10 employees for a company the CRM says
   is larger, is the wrong company, not a find. Hold it (`Held: Resolve failed`, "likely the wrong
   company") and re-run with `linkedin_url`; never score the wrong entity. Do not look up the Salesforce
   Account Id here: the SOQL lookup filters on
   `Territory_Plan__c`, which `sf_setup.py fields` creates in Step 5, so a lookup built now errors every
   Step 4 test run on an unknown column. Reserve the "Salesforce Account Id" Audiences field (item 5)
   and add the lookup in Step 6 (section 6).
2b. **Hierarchy**: `cpj-enrich-company-hierarchies` on the resolved domain, then **Pick root domain**
   (`scripts/pick_root_domain.py`): the parent furthest above the account, skipping investors and
   holding companies by name keywords and a domain list ("Own root" when none), then **Resolve root**
   (`cpj-enrich-company-v2` on `root_domain`). Feed every research node and the Score node the root's
   domain and values, so a subsidiary is enriched, scored and segmented on its parent. Write `Family Root`
   (root domain) and `Ultimate Parent` (label) with the headline upsert, and `Ultimate_Parent__c` in the
   Step 6 write node. Pin `$.result` of the hierarchy node only; extract `parent_companies` inside the
   code node. Cost: one hierarchy call per account and a second Resolve for children.
3. **Research**: one node per worksheet row. Tool nodes return the provider's raw result; the two
   Claygent nodes (`claude-haiku-4-5`) take their prompts from `references/research-prompts.md` and
   return the schema the node declares. A conditional code node must call `context.transition_to(<node name>, <transition id>)` on **every** path,
   the skip path included; a path that returns without it fails the run with "did not choose which step to run
   next" (the first test run of the 28 Oct live build failed on exactly this). The funding Claygent runs only behind a code or conditional gate
   (tool nodes have no run condition): skip it when a provider returned a round, when the provider stage
   is EXITED, IPO or PUBLIC (public companies answered in prose when researched, which failed the run),
   and for vc_pe, education, government and inactive entities. Both prompts return strict JSON in every
   case, including conflicting sources, per `references/research-prompts.md`.
   **Input pinning**: on the Score node pin `$.result` only for each research node (plus the flat
   `$.success` flag where `failed` must be told from `none`). Never pin a deep path such as
   `$.result.roleCount`; a provider null on a deep path hard-fails input resolution and holds every
   account. Extract fields inside the code node with `.get()`.
4. **Score**: code node from `scripts/score_account.py`, two layers. The adapter turns raw results into
   `<factor>_value`, `<factor>_status` and `<factor>_evidence`; the normalisation rules live here and
   nowhere else (HG product list to crm+dw+competitor, sales ratio and the 20+ SDR rule, GTM Engineer
   counted under Ops, the 18-month funding rule, VC/PE fundraising value -1, fundraising skipped for
   vc_pe, education and government, the resolve guard from item 2, and the growth percent clamped to
   the range of `Headcount_Growth_Pct__c`, which must be Number(7,1): a +39,800% value overflowed a
   Number(5,1) field and failed the whole component write, so clamp to -999999.9..999999.9 and add
   "(clamped)" to the evidence). The adapter also passes the enrichment values the CRM stores
   (headcounts, growth, funding round, amount and date, motion, model, entity type, tech stack) through
   under stable names, so the Step 6 write nodes map them from this one node. The scorer then reads
   `rubric_json`, pasted from the JSON block
   in `rubric.md`. A hardcoded fallback rubric is allowed only when that input is empty, and it must
   still output `rubric_version`. The node returns every `<factor>_value/_status/_evidence` alongside
   the scores, so a test run can be saved and re-scored offline (section 4).
5. **Record**: the Audiences fields must exist before the upsert node can map them. Audiences must be
   enabled on the workspace; create the ACCOUNT fields (fit score, grade, reason, scoring status, rubric
   version, entity type, entity status, Salesforce Account Id, one score field per rubric factor) with
   `clay audiences fields create --entity-type companies ...` and record the ids. The fields the Step 7
   carve mirrors (Segment, Sub-region, Carve Status, Carve Reason, Proposed Owner) are created by
   `carve_workflow.py build` when missing, so reserve only what this workflow writes. Then
   `upsert-audiences-record`, lookup on domain, `removeNullValues` true; headline fields in one node,
   component scores in a second so a mapping error cannot block the headline.
6. **Write back**: not built in Step 3. `update-object` maps `object_fields` by API name, and those
   names exist only after `sf_setup.py fields` has run in Step 5, so the Salesforce lookup and write
   nodes are added in Step 6. The node specs are in section 6 below; `references/crm-fields.md` has the field list. Never
   map Owner anywhere in this workflow; the carve is the only step that writes it.

Validate before any run. Test the Score node's code locally first: `python3 "$SKILL/scripts/score_account.py"`
with no arguments runs the scorer's self-test at zero credits, and a small shim `ctx` exercises the
adapter the same way. `clay workflows code test` has a daily cap of 10 and is often already spent; use
it only to confirm the sandbox runtime, and skip it when the cap is hit. Do not publish the workflow
until Step 6. Test runs bill the same credits as live runs: iterate a prompt on one account, and re-run
all five only to confirm.

## 3. Running the five known accounts

Before the first run, read `clay credits balance` and say the test cost as a ceiling from the worksheet:
fifteen test runs x (8 x the HG limit + the flat provider prices + about 4 for the two Claygents), plus
action credits. On the four measured runs the five known accounts cost between about 170 and 525 data
credits in total, depending on how many pinned HG records they returned. Run each known account from
the manual trigger with its `domain`. Collect outputs into a table:

```
account        expected   grade       score  resolved (emp)  strongest             weakest                 data_cr  action_cr  reason
hex.tech       Good       Good Fit    74.5   Hex (282)       Sales Team (59 reps)  Technographics (none)   91       8          Good Fit (74.5). Strongest: ...
```

Read the credits per run from the workflow run data (the `clay workflows` run and analysis commands
report data credits and action credits used, and the verbose node view shows each Claygent node's
step count), or take `clay credits balance` before and after a run and difference it. Keep the raw
list and state min, mean, p90 and max: the spread comes from HG (0 records to a full page at the limit,
8 credits each), so the biggest companies cost the most, and the Step 6 checkpoint needs the mean and
the max (section 6). Check the `resolved (emp)` column against the CRM or CSV employee count: a resolved
name that is not the account, a missing domain, or a count off by an order of magnitude is a wrong
match; hold it and re-run with `linkedin_url` before reading its grade. Save each run's Score node
output to `saved_outputs.json` as you go (section 4).

If any row is `Held`, read the status: `failed` means fix the source or the domain (a wrong-company
resolve is a source problem; re-run by LinkedIn URL); `capped` means the research step needs a tighter
query (for HG, a tighter pin: a higher limit costs 8 more credits per record). A funding Claygent that
answered in prose has lost its strict-JSON rule; restore it from `references/research-prompts.md`. If a
Claygent node blew its step budget, fix the prompt per `references/research-prompts.md` (one more
allowed source or one more early-exit rule), not the scorer. A provider error (Harmonic has returned
transient errors) gets one rerun before the account is held.

## 4. Tuning without credits

Every run's Score node output already carries `<factor>_value/_status/_evidence`; append it to a local
JSON list, `saved_outputs.json` (`clay workflows runs steps <workflow> <run>` shows the step outputs if
a run was not captured). To try new weights or bands: edit the JSON block in `rubric.md`, bump the
version, and run from the project directory

```
python3 "$SKILL/scripts/score_account.py" rubric.md saved_outputs.json
```

The script reads the JSON block straight from `rubric.md`; `SKILL` is this skill's absolute path, printed
in Step 0, because the scripts live under it, not in the project. No Clay call, no credits. When the grades
match, paste the new `rubric_json` into the Score node and record the version. Rebuild only when a
factor is added, removed, or its data need changes. The same script with no arguments runs its
self-test; use it in place of `clay workflows code test` (daily cap of 10) whenever the Score node's
code changes.

## 5. The ten

Pick ten accounts from the universe and run them the same way: at least half from the rules file's
core industries when it names them, the rest at random with a fixed seed, and say so in the log (a
random slice of a software-heavy list tests only the non-core path). You are looking for:

- **Everything Good or Best**: the rubric cannot separate; the heaviest factor is probably identical
  across the universe. More than half of the ten grading Best is this failure unless the universe was
  hand-picked for fit; say so and ask whether the top band should be harder before scoring everyone.
  Reweight or replace the factor. One exception: VC firms, GTM agencies and education institutions
  grading Low Fit at exactly 40 is the exclusion override, not a rubric failure (with the opt-in lift
  they grade Best Fit instead); the carve excludes them either way. Do not reweight around them.
- **Everything Held**: one source is failing for this universe (a region a provider does not cover, a
  domain format). Fix the source, not the rubric.
- **Reasons that do not read**: evidence phrases missing; fix the research step's output, not the scorer.

Then state the full-run cost as a range, next to `clay credits balance`: accounts x the measured min,
mean, p90 and max data credits from the test runs, plus accounts x action credits. If the mean total
exceeds 10% of the balance, say so explicitly. Approval covers the first batch of 25 and the total; the
batches, the checkpoint before each one and the 25% rule are in section 6.

## 6. The Salesforce lookup and write nodes, and the batches (Step 6, after the fields exist)

Add the nodes only after `sf_setup.py fields` and `verify` have passed. If the new fields do not yet
appear in the action's dynamic field list, wait and refresh; Clay can lag the deploy. Confirm the
connected app account appears on the action before building; if it does not, the Clay connection is
missing. Append the new nodes after the two Audiences upserts, in this order, rather than inserting
them after Resolve: the graph is a validated serial chain by now, and appending leaves every tested
edge alone.

- **Find the Salesforce Id**: the company record Audiences syncs from Salesforce does not carry the
  Account Id (it carries the owner id), so a `salesforce-lookup-via-soql` node finds it on Website:

  ```
  SELECT Id FROM Account WHERE Territory_Plan__c = true
    AND Website IN ('https://{{domain}}', 'https://www.{{domain}}',
                    'http://{{domain}}', 'http://www.{{domain}}')
  LIMIT 1
  ```

  `{{domain}}` is the bare domain (the same coalesce the provider nodes use); the import writes Website
  as `https://<domain>`, so the four URL forms match it. Follow it with a code node that picks the Id
  into `salesforce_account_id` (empty when no row), then an `upsert-audiences-record` node that writes
  it to the "Salesforce Account Id" Audiences field reserved in Step 3. Steps 6 and 7 read the Id from
  that field. Test once on a known domain as a draft run; an Id must land on the Audiences record
  before the write nodes are added.
- **Write the scores**: `update-object`, `recordId` = `salesforce_account_id` from the pick node,
  `object_type` = Account, `object_fields` by the API names `sf_setup.py plan` prints
  (`Account_Fit_Score__c` <- `{{fit_score}}`; `GTM_Motion_Score__c`, `Headcount_Size_Score__c` and the
  other component names follow the factor names). `removeNullValues` = true so a held account does not
  blank existing values.
- Two write nodes: headline fields first (score, grade, reason, status, version, last enriched), then
  component scores and enrichment values. Enrichment values map from the Score node's pass-through
  outputs (section 2, item 4), where the growth percent is already clamped to `Headcount_Growth_Pct__c`
  Number(7,1). Rubric-specific values (a compliance headcount, a sector, an engineering headcount) map
  to the fields `sf_setup.py fields --extra-fields` created; see `references/crm-fields.md`.
- `salesforce-lookup-record-v2` reads a record back to verify a write.
- Never Owner. The Write Owners run writes it in Step 7 after approval; the carve workflow writes
  Carve Status, the reason and Proposed Owner.

**Publish and test the write path.** Only the manual trigger exists, so `clay workflows publish` fires
nothing. Run one known domain live and read the account back: score, grade, components and the
Audiences Id present, Owner unchanged. Then take that domain out of the batch list.

**Run the batches.** The Audiences Salesforce source is optional production plumbing, not a
prerequisite: in four of four runs it delivered no imported account within 30 minutes. The default
path is the published workflow's manual `domain` input over the imported CSV, 25 domains per batch,
one run per domain:

```
clay credits balance
clay workflows runs test <wf> --inputs '{"domain": "<domain>"}' --live     # x 25
```

Before every batch read `clay credits balance` and compare the last batch's spend with the quote
(25 x the mean data credits per account measured in Steps 4 and 5). Stop and get a fresh yes if a
batch ran more than 25% over the quote, or if the next batch at the measured max would cross the
approved total. A batch of large companies can trip the rule legitimately (HG returns a full page for
them; one run saw +48% on such a batch); the re-approval is the point, not a fault. Failed runs go on a
rerun list for one rerun batch behind the same checkpoint; an account that fails twice is held with its
status, reason and rubric version written, no component scores. A fix between batches is a draft edit
plus a republish; runs already in flight finish on their version. If the Audiences source has delivered
the records, a batch can instead be
`clay workflows runs test <wf> --audience-segment <seg> --record-ids <25 ids> --live`
(ids from `clay audiences records search-ids --audience-id <seg>`; the `--limit` form caps at 10).
The SOQL lookup finds the Account Id either way, so the write lands in Salesforce on both paths.

**After the batches**, create the segment trigger on "to score" as a draft and leave it unpublished;
say so. A republish would make it live and score every record in the segment at once with no
checkpoint, so it goes live only when the team wants the weekly top-up and the source is confirmed to
be syncing.

## 7. The carve workflow (Step 7, after the fields exist)

The carve is a second Clay workflow, "Territory Carve", built by a script rather than by hand so every
build has the same eight nodes. From the project root, after `sf_setup.py fields` and `verify`, during
the Step 6 batches:

```
python3 "$SKILL/scripts/carve_workflow.py" build  --org <alias> --rules territory-rules.md --reps reps.csv --out ./carve   # draft; --dry prints the node specs
python3 "$SKILL/scripts/carve_workflow.py" writer --out ./carve                                                           # the two-node Write Owners draft
```

Shape, behind a manual `domain` trigger: **Pick domain** (code; first non-empty of the manual domain and
the segment record's domain, bare) → **Salesforce: read the account** (`salesforce-lookup-via-soql` on
Website in the four URL forms, `Territory_Plan__c = true`, the fields the org has) → **Carve gates**
(code, `scripts/carve_node.py`, mode `gates`: exclusions, size cap, minimum size, eligibility,
protections, rep picks, segment, route; emits `decided` or `peer_soql`) → **Decided before the deal?**
(conditional) → **Salesforce: eligible peers in the bucket** (`salesforce-lookup-via-soql` with
`peer_soql`: every scored account in the same segment band and region, zero credits) → **Carve deal**
(code, mode `deal`: re-gates every peer, deals the whole superset in canonical order against one
shared capacity ledger, returns this account's slot) → **Salesforce: write the proposal**
(`update-object`: `Segment__c`, `Sub_Region__c`, `Carve_Status__c`, `Carve_Reason__c`,
`Proposed_Owner__c`, `removeNullValues` true, never `OwnerId`) → **Audiences: mirror the proposal**
(`upsert-audiences-record` by domain). The write node takes each value from the deal node when it ran
and from the gates node otherwise (a coalesce), so one write node serves both paths.

The rules YAML, `reps.csv`, the pool owner and the field list are baked into the two code nodes as a
CONFIG block appended to `carve_node.py`'s source; `carve_workflow.py update` re-pushes it after an edit.
The builder reads the Salesforce connection id off the scoring workflow's Salesforce node (pass
`--app-account aa_...` if none exists), looks up the Audiences field ids by name and creates "Proposed
Owner" (and any other mirrored field) when missing, validates the graph, and saves everything to
`./carve/carve-workflow.json`, which `run`, `update`, `segment` and `writer` read.

Test the node locally, not in Clay: `python3 "$SKILL/scripts/carve_node.py"` runs its self-test (every
account gets a status, each account's own slot equals the whole-bucket deal, books balanced within
one). The sandbox ships only `json`, so the node imports nothing else. Then one draft run on a known
domain, `carve_workflow.py run --limit 1`, and read the account back before carving everyone. The
procedure, the summary and the approval are in `references/pool-and-carve.md` Step 7.
