# Pool and carve (Step 6 and Step 7)

## Step 6: the pool

1. **Get the universe into Salesforce and wire the Salesforce Id lookup.** If the org has no accounts
   (developer edition), import the list first, from the project root:
   `python3 "$SKILL/scripts/sf_setup.py" accounts --org <alias> --accounts <csv>` (`SKILL` is the skill
   folder path printed in Step 0; flags `Territory_Plan__c = true`, writes Website as `https://<domain>`).
   Salesforce requires an owner on every account, so every imported row is owned by the admin who ran
   the import. That admin is the pool owner for the rest of this plan; record their user id.
   Then, now that Step 5 has created the fields, add the Salesforce nodes to the scoring workflow,
   appended after the two Audiences upserts so the tested edges stay as they are: a
   **Find the Salesforce Id** node (`salesforce-lookup-via-soql`) querying `Id` from
   Account where `Territory_Plan__c = true` and Website is in the four URL forms of the domain
   (the `https` and `http` schemes, each with and without a `www.` prefix); a code node that picks
   the first Id into `salesforce_account_id` (empty when no row); an Audiences upsert that writes it to
   the "Salesforce Account Id" field reserved in Step 3; then the `update-object` write nodes, which take
   `recordId` from it. An Audiences record synced from Salesforce does **not** carry the Salesforce
   Account Id, so the lookup is the primary path, not a fallback; if your source happens to map `Id`,
   use it. Test the lookup once on a known domain; an Id must come back before the write nodes are added
   (`build-and-test.md` section 6 has the node specs).
   The Audiences Salesforce source (Audiences → Sources, synced Accounts with Name, Website, OwnerId,
   Industry, NumberOfEmployees, Billing fields, Territory_Plan__c, Open_Opportunities__c,
   Is_Competitor__c in the mapping) is **optional production plumbing for the weekly top-up, not a
   prerequisite** for scoring. It is a UI step the user does by hand; the CLI cannot add a source or
   start a sync. In four of four test runs the source delivered no imported account within 30 minutes,
   so do not wait on it: go straight to item 3's default path. If the user has added the source, check
   whether it is delivering in passing (`clay audiences fields list-values origin_source_type
   --entity-type companies` lists a Salesforce-origin value; `clay audiences records search-ids
   --audience-id <to-score segment>` returns ids) and log the answer, nothing more. Scores land in
   Audiences from the workflow's upsert, not from the source mapping, so the Audiences fields the Record
   node writes must already exist from Step 3; the fields the Step 7 carve mirrors (Segment, Sub-region,
   Carve Status, Carve Reason, Salesforce Account Id, Proposed Owner) are created by
   `carve_workflow.py build` when missing.
2. **Price the run as a range.** Accounts x cost per account from the Step 4 test runs, low (min) and
   high (p90), plus about one action credit per tool node. The measured means across four full runs
   were 18 to 73 data credits per account, and the spread came almost entirely from one node: HG
   Insights bills about 8 data credits **per product record returned**, not per call, and was 60 to 90%
   of spend. The two research agents cost about 1 to 2 credits each with the capped prompts. The lever
   is pinning HG to the specific product ids or names the rubric needs with a result limit of 12 or
   fewer (the run that pinned ids averaged 18); tightening the agent prompts barely moves the number.
   Test runs bill like live runs. Read `clay credits balance` and say what share of it the run is. Get a
   yes for the first batch and for the total.
3. **Run everyone in batches from the imported CSV.** This is the default path, not a fallback. Publish
   the workflow now that the lookup and write nodes exist. Build **no segment trigger before the
   batches**: publishing makes an Audiences segment trigger live, a live trigger scores every record in
   the segment at once and skips the checkpoints, and the CLI cannot pause one (a trigger created by
   the CLI is a draft, and a draft cannot be paused). With only the manual `domain` trigger on the
   graph, publishing fires nothing. Then run 25 domains at a time from the CSV through the manual
   `domain` input, the way Step 4 ran the five. Before each batch read `clay credits balance`; compare
   the last batch's spend to the quote and stop for re-approval if it ran more than 25% over. The
   lookup finds the Account Id, so the Salesforce write lands (headline fields first, components
   second); the upsert creates the Audiences record with the Salesforce Account Id on it. Hold, do not
   score, when Resolve returns no domain or an under-10-employee match for a known company (that is a
   wrong match, not a small company); a provider that fails twice is held per scoring rule 2. Funding
   research is skipped for public or exited companies (Harmonic stage `EXITED`) and the prompt answers
   strict JSON even on conflicting sources. Report after each batch: scored, held (and why), credits
   used against credits approved. Rerun the held once the cause is fixed.
   If the Audiences source has synced and the team prefers to feed the segment, the equivalent is
   `clay audiences records search-ids --audience-id <seg>` for the ids, then
   `clay workflows runs test <wf> --audience-segment <seg> --record-ids <25 ids> --live` (`--limit`
   caps at 10; `--record-ids` takes up to 50). Scored accounts leave the "to score" segment, so each
   listing only picks up the new and the held.
   **After the batches**, create the segment trigger on the "to score" segment as a draft and leave it
   unpublished. Say plainly: the next `clay workflows publish` makes it live and it will score every
   record in the segment, so publish only when the team wants the weekly top-up running, after a
   `clay credits balance` check and confirmation that the source delivers. Delete the draft if the
   team does not want the top-up yet.
4. **Define the eligible pool** from the rules file. This is the unassigned eligible set, and it is the
   carve's input. The carve workflow's gates (Step 7) apply it per account from the Salesforce fields,
   for every account with `Territory_Plan__c = true`, so the initial carve needs no Audiences segment.
   The Audiences "Eligible pool" segment that `carve_workflow.py segment` creates in Step 7 is the
   trigger for the always-on top-up; it is defined on the fields the upserted record does carry (scored,
   fit at or above the threshold, Carve Status empty or Unowned), and the gates re-check the rest when a
   record fires. Default filters:
   - in scope for this plan (checkbox)
   - fit score (the field the Record node writes) at or above the threshold (default 60; or the
     alternative gate the rules name for other industries, using `eligibility.competing_vendors`)
   - unassigned: `Carve_Status__c` blank or `Unowned`, and owner is the pool owner from item 1 (there is
     no ownerless account in Salesforce, so "no owner" alone matches nothing)
   - open opportunities = 0
   - not on the exclusion list (industry, company type, competitor, country, education). VC firms, GTM
     agencies and education institutions sit here on purpose and are also capped at 40 by the Score node,
     because another motion owns them; the carve excludes them again so neither rule alone decides. See
     `production-example.md` section 2 for a team that lifts them instead.
   - scoring status = scored
   **Size rules read the CRM employee count first.** The resolved LinkedIn headcount over-counts 5 to
   9x for some companies, so a "too big" rule (for example 5,000+ employees → Low Fit or excluded) must
   fall back to `NumberOfEmployees` in the CRM when it is present and use the resolved count only when
   it is blank; the carve segments on the CRM count for the same reason. Grade, segment and eligibility
   must read the same number, and no Assigned account may carry a Low or Bad Fit grade in the CRM; if
   one does, the size rule fired on the wrong count, so fix the rule and re-score before the carve.
5. **Report the pool:** count, grade mix, segment mix, region mix. Compare to the rules' composition
   targets if any. Before the carve a SOQL count on the filters above is enough; after it,
   `carve_workflow.py status --org <alias>` prints the counts by carve status and the proposed books.

**Gate:** "This is the pool we want to carve."

## Step 7: the carve

Inputs: the scored accounts in Salesforce (`Territory_Plan__c = true`), `reps.csv` with `crm_user_id`
filled by `sf_setup.py reps` at Step 5, the rules file. The carve is a Clay workflow, not prose and not
a local script: "Territory Carve" runs once per account, decides it from the rules YAML and the
Salesforce fields, and writes a proposal. Read the summary with the team, write owners only after the
gate. The rules YAML is the only input the decisions read; the options are catalogued in
`carve-scenarios.md`. The canonical order is exclude, size, eligibility, protect, segment, route, deal,
overflow (family roll-up exists in the local preview only; in Clay each account is its own entity).
Carve Status takes one of the six values `sf_setup.py` created: `Proposed`, `Assigned`, `Protected`,
`Excluded`, `Not eligible`, `Unowned`. The why goes in Carve Reason as short text (status `Protected`,
reason `open opportunity`; status `Proposed`, reason `snake deal, SA / US West, rank 7 of 38`).
`Proposed` means the workflow named a rep in `Proposed_Owner__c` and Owner is untouched; it becomes
`Assigned` when the approved Write Owners run copies Proposed Owner to Owner. Proposed accounts are
still owned by the pool owner, so "unassigned" keeps its definition.

1. **Build the two workflows**, from the project root, after Step 5 and during the Step 6 batches:
   `python3 "$SKILL/scripts/carve_workflow.py" build --org <alias> --rules territory-rules.md --reps reps.csv --out ./carve`
   and `python3 "$SKILL/scripts/carve_workflow.py" writer --out ./carve`. Both come out as drafts;
   nothing runs until `run`, nothing is published. `build` refuses to start if any `crm_user_id` in
   `reps.csv` is blank, or if the org lacks `Territory_Plan__c` and `Account_Fit_Score__c`. It reads the
   Salesforce connection id off a Salesforce node of an existing workflow (the scoring workflow;
   `--app-account aa_...` otherwise), creates any of the Audiences fields it mirrors that are missing,
   and saves ids and config to `./carve/carve-workflow.json`. The graph, eight nodes behind a manual
   `domain` trigger:
   - **Pick domain** (code): the first non-empty of the manual domain and, once the segment trigger
     exists, the segment record's domain, in bare form.
   - **Salesforce: read the account** (`salesforce-lookup-via-soql`): by Website in the four URL forms,
     `Territory_Plan__c = true`, selecting the fields the org actually has (standard fields, the score
     and status fields, Entity Type, Tech Stack, headcounts, Open Opportunities, Is Competitor, the
     carve fields, and any field the rules name).
   - **Carve gates** (code, `scripts/carve_node.py` in mode `gates`): items 3 to 6 below. Emits
     `decided` with a final status, or `decided` false with `peer_soql`.
   - **Decided before the deal?** (conditional): decided → write; otherwise → peers.
   - **Salesforce: eligible peers in the bucket** (`salesforce-lookup-via-soql`, the `peer_soql`):
     every scored account in the same segment band and region. Zero credits.
   - **Carve deal** (code, mode `deal`): item 7. Returns this account's slot.
   - **Salesforce: write the proposal** (`update-object`, `removeNullValues` true): `Segment__c`,
     `Sub_Region__c`, `Carve_Status__c`, `Carve_Reason__c`, `Proposed_Owner__c`. Never `OwnerId`.
   - **Audiences: mirror the proposal** (`upsert-audiences-record` by domain): the same fields, the
     proposed rep's name and the Salesforce Account Id.
   The rules YAML, `reps.csv`, the pool owner's user id and the field list are baked into the two code
   nodes as CONFIG. After an edit to the rules file or `reps.csv`, `carve_workflow.py update` pushes the
   new config into the draft; `run` uses the draft unless `--live`. `--dry` prints the node specs
   without touching Clay.
2. **Capacity and rep count** (what the carve node applies; the knobs are in the rules file). Capacity
   per rep comes from `reps.csv` first; if blank, the segment's `capacity` plus any `capacity_bonus`
   for the rep's region; if the rules carry neither, the pool in the segment divided by the reps in the
   segment. One ledger per rep across every bucket, so a rep who serves a pooled metro and a sub-region
   is never dealt more than their capacity in total. `carve-summary.md` opens with the rep-count table:
   eligible accounts per segment divided by capacity per rep, rounded up, next to the reps in the file
   (412 SA accounts / 60 per rep = 6.9, so 7 SA reps, against the 5 they have). When the team has not
   said how many reps, that table is the proposal; show the maths. When `reps.csv` is already given, the
   table is informational: carve with the reps they have, report the rest as `Unowned: over capacity`,
   and add a rep only if the approver says so (then `sf_setup.py reps` creates the user, and `update`,
   `reset-proposals`, `run`). When the method is `dynamic`, the pool is meant to exceed capacity, so read
   the gap as "N weeks of top-up at current capacity", not as a missing rep.
3. **Exclude and size.** In order: the competitor flag or a domain on `eligibility.competing_vendors`
   (`direct competitor`), `partner_list`, `other_teams_field`, `company_types.entity_types` against
   Entity Type, education domains, `exclusions.industries`, `exclusions.regions` (matched on the country
   code or name; Middle East, CIS, Africa and APAC expand to their country codes), `india_heavy`,
   `manager_list`. Then the size cap (`overrides.size_cap`, CRM employee count first), then the minimum
   size: below `exclusions.min_employees` or outside every segment band is `Not eligible: below minimum
   size` (`no employee count` when the CRM count is blank). Then eligibility: the fit floor, or the
   other-industry gate for accounts outside `core_industries`; a held account (Scoring Status not
   `scored`) is `Not eligible: not scored`.
4. **Protect.** Protections apply to accounts a rep already owns, which sit outside the pool: they stay
   where they are and are reported, never dealt. The node applies, in order: existing owner (owner is
   not the pool owner), an open opportunity on the account (`Open_Opportunities__c`), customer owner
   (per `protections.customer_owner`, default `Type = Customer`), then rep picks (from
   `protected_domains` in `reps.csv`, which become `Proposed`, reason `rep pick`, and are written as
   owners with the rest after approval). Status `Protected`, reason naming the rule. The parent's owner
   and family-wide opportunities apply in the local preview's family mode only. Active pursuit, partner
   registration and churn cool-off need a CRM field most orgs lack (activity, a registration date, a
   churn date); when the field is absent the protection is skipped and `carve-summary.md` says so in
   one line.
5. **Segment** each account per the `segments` table on the CRM employee count: minimum inclusive,
   maximum exclusive, so 350 employees is the first SL1/SL2 account, not the last SA one. The size floor
   lives here and nowhere else; the rules file's "too small" row means this. The "too big" rule reads
   the CRM count first (Step 6 item 4).
6. **Route** per `routing.by`: pooled metros first, by matching the HQ city against each pool's city
   list in the rules YAML (a pool names its cities, not just itself); then sub-region from the state
   lists; then the region's default sub-region. Pooled accounts are dealt across every rep of that
   segment in the region. An account that matches no region is `Unowned`, reason `no routing match`.
7. **Deal** per `allocation.method`. The deal node reads the peers back, re-applies items 3 to 6 to
   each, keeps every account that lands in a pool (Assigned ones count as their rep's load instead),
   groups the superset into buckets (segment, region, sub-region, pooled), sorts each by `sort_key`
   descending then Id, and deals every bucket in canonical order (pooled metros first, then by segment,
   then by sub-region) against the shared ledger. It then reports the slot of the one account it is
   running for. Same inputs, same books, whichever account's run computes them.
   - `snake` (default): within each bucket deal 1, 2, 3, 3, 2, 1 to the reps with room. Reason
     `snake deal, <segment> / <sub-region>, rank N of M`. This equalises mean fit, not just count.
   - `round_robin`: same order, fixed rotation 1, 2, 3, 1, 2, 3.
   - `manager`: within each segment and region, the top `allocation.named_accounts.top_n` accounts by
     `sort_key` go to the rep an override names (the node's `named_overrides_json` input, a JSON object
     of domain → `crm_user_id`; `build` does not wire that input yet, so in Clay they go to the first rep
     routed for the segment and sub-region) with reason `named account, manager allocation`; a named
     account whose rep is at capacity is `Unowned: named account, no rep with capacity`. The remainder is
     dealt in rotation.
   - `dynamic`: each account, from the highest fit down, to the rep with the most remaining capacity;
     reason `dynamic deal, <segment> / <sub-region>: rep with the most room`. Whatever is left stays
     `Unowned: over capacity` by design and feeds the top-up (item 13), where the same rule deals new
     accounts to whoever has room.
   - `draft`: no owners; every pooled account is `Unowned: awaiting draft pick (pick N of M, <segment> /
     <sub-region>)`, so the pick order is on the record and in `carve-proposal.csv`. Reps pick in the
     agreed order; record the picks in `protected_domains` in `reps.csv` (up to `protections.rep_picks.max`
     each), switch the method to `snake` or `round_robin` for the rest, then `update`, `reset-proposals`,
     `run`.
   Carve the whole pool in one `run` so every account sees the same superset.
8. **Overflow.** Accounts left when every rep is at capacity: `Unowned`, reason `over capacity`. They
   stay in the pool for the next run.
9. **Run it.** One known domain first, then everyone:
   `python3 "$SKILL/scripts/carve_workflow.py" run --org <alias> --out ./carve --limit 1`, read the
   account back (Carve Status, Carve Reason, Proposed Owner written; Owner unchanged), then
   `python3 "$SKILL/scripts/carve_workflow.py" run --org <alias> --out ./carve`. `run` takes every
   scored plan account that is not already `Assigned` (ordered by fit; `--only-pool` restricts it to the
   unassigned eligible set, `--domains <file>` to a list, `--limit N` to the first N), fires 25 runs at a
   time through the manual trigger, polls each batch to completion, logs run id, domain, status,
   credits and duration to `./carve/carve-runs.jsonl`, and prints failed domains and the credit totals
   (data credits should read 0; action credits only). Rerun failed domains with `--domains`. Every
   scored account ends with a status and a reason on its record, which is what the FAQ's "why is X not
   in my book" points at.
10. **Summary, review, iterate** (nothing is sent, no owner is written).
    `python3 "$SKILL/scripts/carve_summary.py" --org <alias> --rules territory-rules.md --reps reps.csv --out ./carve [--rubric-version <X>]`
    reads the proposal back from Salesforce and writes to `./carve`:
    - `carve-summary.md`: counts by carve status, the rep-count table, one row per rep (capacity,
      count, mean fit, grade mix, core share, self-serve share; books are Proposed plus Assigned), the
      balance verdict and the composition targets per segment, the ten highest-fit accounts not in a
      book and why, exclusions, not-eligible and protected by reason, skipped protections, a hierarchy
      note when the org has ParentId data, and how many scored accounts have no status yet. This is
      what the approver reads; the "Territory – Proposed Books" report in the org shows the same books.
    - `carve-proposal.csv` and `.json`: every account in the plan with segment, sub-region, carve status,
      reason, proposed owner and rep.
    - `write-owners.jsonl`: one row per **Proposed** account in the Write Owners routine's shape, with
      `carve_status` `Assigned` and `owner_id` the proposed rep. Nothing else goes in it: the carve
      workflow already wrote the other statuses, so the approved write touches owners only.
    - `patch-doc.md`: the skeleton of the rep-facing doc (what's new placeholder, criteria table from the
      rules, each rep's book, FAQ). You fill in the what's-new lines.
    Read `carve-summary.md` with the team: per rep count, mean fit, grade mix, core and self-serve
    share, next to the rules' composition targets, which are keyed by segment name
    (`composition_targets.<measure>.<segment>`); the balance verdict per segment; the ten highest-fit
    accounts that went unassigned and why. If a knob is wrong (threshold, capacity, a pool's city list),
    edit the rules file and iterate here, not after the write, at zero credits: preview with
    `python3 "$SKILL/scripts/carve.py" --org <alias> --rules territory-rules.md --reps reps.csv --out ./carve-preview`
    (same gates and deal, nothing written; the only place family roll-up runs), then
    `carve_workflow.py update`, `carve_workflow.py reset-proposals --org <alias> --yes` (clears Carve
    Status, Carve Reason and Proposed Owner on every plan account that is not Assigned; the Audiences
    mirror refreshes on the next run) and `run` again. Then fill in `patch-doc.md`'s "what's new" lines
    since the last carve in the reps' language (the criteria table, each book and the FAQ are already
    there), and write the approval message for the approver in `governance.approver`: the per-rep
    summary, the balance measures hit and missed, where the proposal lives. `production-example.md`
    section 5 is the shape. If the approver is a person in this session (or
    `deliverables.approval_channel` names none), record the yes here and leave the docs in the project;
    send only when a channel is named.

**Gate:** "Approve these books." No owner is written before this.

11. **Write the owners through the Write Owners workflow and a bulk routine.** `update-object` is a
    Clay action, so the write runs through the second workflow `carve_workflow.py writer` built, left
    unpublished until now. Shape: a manual trigger with inputs `account_id`, `domain`, `owner_id`,
    `segment`, `sub_region`, `carve_status`, `carve_reason`; one Salesforce `update-object` node
    (`recordId` = `account_id`, `object_type` Account, `object_fields` by API name: `OwnerId`,
    `Segment__c`, `Sub_Region__c`, `Carve_Status__c`, `Carve_Reason__c`, `removeNullValues` true, so an
    empty `owner_id` would leave Owner unchanged); then an `upsert-audiences-record` node that mirrors
    the owner and the four fields on the Audience record (matched on domain). Before writing, take a
    rollback snapshot:
    `sf data query -q "SELECT Id, OwnerId, Carve_Status__c, Proposed_Owner__c FROM Account WHERE Territory_Plan__c = true" -o <alias>`
    saved to the project. Then three commands, each after the recorded yes:
    1. `clay workflows publish <write-owners wf>`
    2. `clay routines create workflow <write-owners wf>` (prints the routine id)
    3. `clay routines runs start <routine> --bulk ./carve/write-owners.jsonl`
    The bulk run is a write to shared resources, so Claude Code's permission classifier stops and asks
    the human to approve it ("Modify Shared Resources"); say so before running it, and run the three
    commands separately rather than chained, so the prompt is about the write alone. The write costs
    action credits only. Check the run with `clay routines runs get <run> --bulk` (`--limit` cannot be
    combined with `--bulk`). Headline count: Proposed rows written as Assigned, against
    `carve-summary.md`. If the Clay write is blocked and the team prefers the Salesforce CLI, the same
    fields can go in with `sf data update bulk --sobject Account --file <csv>` from
    `carve-proposal.csv` (admin-controlled, zero credits) with the Audiences mirror run afterwards; say
    which route was used. Send the patch doc and the approval message once the counts match the
    proposal.
12. **Verify.** Open the "Territory – Accounts by Owner" report. Every Proposed row is now Assigned with
    the proposed rep as owner, counts and mean fit per rep match `carve-summary.md`, and no Assigned
    account carries a Low or Bad Fit grade.
13. **Always on.** `python3 "$SKILL/scripts/carve_workflow.py" segment --org <alias> --rules territory-rules.md --out ./carve`
    creates the Audiences segment "Eligible pool" (domain not empty, Scoring Status `scored`, Account Fit
    Score at or above `eligibility.threshold`, Carve Status empty or `Unowned`; it needs the Audiences
    fields the scoring workflow upserts) and an `audience_segment` trigger on the carve workflow, as a
    DRAFT, and rewires the Pick domain node to read the segment record's domain as well. Test it first:
    `clay workflows runs test <carve-wf> --audience-segment <seg> --limit 2`, then read the Pick domain
    output of those runs; the record's domain path can differ by workspace, and a blank domain means the
    path is wrong. Say plainly before anyone publishes: `clay workflows publish <carve-wf>` makes the
    trigger live and proposes an owner for every record in the pool at once (zero data credits). From
    then on a newly scored account that clears the floor gets a proposed owner on its own, and the
    manager approves on `cadence.top_up` with items 10 to 12. A proposed or assigned record leaves the
    segment through the Audiences mirror. Delete the draft trigger if the team does not want the top-up
    yet.

## Fairness, stated

"Fair" is whatever `allocation.balance_on` says, measured within a segment. Defaults: the same number
of accounts per rep (within one) and mean fit within a few points. Published yardsticks when the team
asks for a number: potential within ±10% of the team average, workload variance under 15%, no book
depending on its top five accounts for more than 40% of pipeline. Report the composition targets next
to the actuals, per segment. Say which measures the carve hit and which it could not, and why (usually
pool size).

## Rerun behaviour

- Assigned accounts count as their rep's load and are never re-dealt, so a rerun only deals the new and
  the freed; `reset-proposals` clears Proposed, never Assigned.
- A rep who closes or drops an account falls below capacity; the next run tops them up from the pool.
- Accounts idle for `cadence.stale_days` are retrieved, rested for `cadence.rest_days`, then re-enter
  the pool. This needs an activity field in the CRM; without one, skip it and say so. Say so to the team
  before turning it on; it is the rule reps notice most.
- A rep leaving: protect their active pipeline the same day (temporary owner), re-deal the top 20% of
  their book within a week, hold the rest for the next run. A rep joining: deal from the pool's best
  available, at ramp capacity, and lock their book for the ramp.
- Swaps follow `governance.swap_rule`; the reason is recorded on both accounts.
- Schedule the run (per `cadence.top_up`) only after two manual runs produced the expected books.
  Until then, it is a button.
- A threshold, capacity or routing change is an edit to the rules file and a rerun. A weight change is
  a re-score first (Step 4), then a rerun.

## Segment-scoped runs and Audiences traps (from the 16 Oct live run)

- **`runs test --audience-segment` needs a trigger.** The CLI refuses a segment-scoped run unless the
  workflow has an `audience_segment` trigger. Create one as a draft:
  `clay workflows triggers create <wf> --input '{"triggerType":"audience_segment","segmentId":"<seg>","entityType":"ACCOUNT"}'`,
  then `clay workflows triggers get <trigger>` for its `workflowNodeId`. A draft fires nothing; publishing
  the workflow makes it live for every record in the segment at once.
- **The trigger node's outputs are `$.fields.<Audiences field name>` plus `id`.** Wire the identifier node
  to coalesce the manual `domain` with the trigger's `Domain` (`domain or s_domain`), and strip the scheme,
  because Audiences stores domains with the https scheme in front. Pass `--record-ids` (up to 50) to run exact
  records; `--limit` caps at 10.
- **Upsert and update ignore blank and null values.** A workflow cannot clear an Audiences field. To reset
  a carve, write a sentinel (Carve Status "Pool", Carve Reason "In the eligible pool, not yet carved",
  Proposed Owner "Unassigned") and widen the eligible segment's filter to "Carve Status is empty OR Pool".
- **Domain filters need the scheme variants.** A segment that must include or exclude exact domains uses an
  `Or` of `Equal` on the bare domain, the domain with the https scheme, and the domain with the scheme and
  www; `NotEqual` and
  `ContainAny` did not exclude records reliably. Filter on the record's creation date too when the
  audience holds older imports of the same companies.
- **Salesforce bulk updates**: `#N/A` nulls a field (a blank is ignored), and the CSV needs LF line endings.

## Step 8: engagement after the carve

Built by `engagement.py build` from the rules file's `engagement` block; the state is `engagement.json`
in `./engagement` (segment id, signal ids, workflow ids, trigger node ids, Audiences field ids).

**Objects.** Audiences fields Engagement Score (number), Last Signal (text), Last Signal Date (text).
Segment "Territory books (assigned)": domain not empty and Carve Status = Assigned. Three signals,
created Paused, each watching the assigned segment and (with `watch_pool`) the Eligible pool segment from
`carve-workflow.json`; the builder creates new signals rather than moving existing ones, because a
signal's watched segment is set at creation. Two workflows, both drafts.

**"Territory Engagement".** Triggers: `manual` (`domain`, `signal_type`, `headline`, optional `points`)
for tests, and one `audience_signal` per signal (`signalId` is the `signal.id`, not the entry id). A signal
trigger node's output is `$.fields` (the Audience record, by display name) and `$.signal` (`signalEventId`,
`signalId`, `signalType`, `emittedAt`, `activityTime`, `data`, the type-specific payload). Nodes, in order:

| Node | Kind | Does |
|---|---|---|
| Pick the event | code | first non-empty source wins: the manual inputs, else each signal trigger's `fields` and `signal`; returns domain, signal_type, headline (from `data`: title, headline, person and job title, name), activity_date, points by type from the baked config |
| Salesforce: read the account | `salesforce-lookup-via-soql` | Id, Name, Engagement_Score__c, Carve_Status__c for Territory Plan accounts whose Website is one of the four URL forms of the domain; zero credits |
| Score the event | code | new = min(cap, old + points); last_signal = "type: headline (+points)"; last_signal_date |
| In the plan? | conditional | `found` → write, else → Not in the plan |
| Salesforce: write the engagement score | `update-object` | Engagement_Score__c, Last_Signal__c, Last_Signal_Date__c; never Owner |
| Audiences: mirror the engagement score | `upsert-audiences-record` | by domain: the three fields plus Salesforce Account Id |

**"Territory Engagement Decay".** One `audience_scheduled` trigger per watched segment (`scheduleConfig`
simple weekly, `startDate` the next Monday 08:00 in `engagement.decay.timezone`); Pick the record,
Salesforce: read the account, Decay (new = round(old × keep, 1), zero under 1), In the plan?, the same
two writers with the score only. A draft fires nothing; publish it to turn decay on.

**Test.** `engagement.py test --domain <d> --type NewHire --headline "..."` fires the manual trigger with
`runs test --inputs`, waits, and reads the account back from Salesforce (before and after). Test runs
execute the writes for real, so the domain should be a plan account the user picked.

**Start.** Publish the Engagement workflow (events on a draft fire nothing), then `resume --yes`. The
command prints how many accounts are watched (segment counts) and that each event found costs data
credits. `pause` stops the three; `status` shows run state, last run, errors and the hottest accounts.

**Book health.** `engagement.py health` writes `book-health.md`: per rep, capacity (same precedence as
the carve), Assigned count, room, mean fit, mean engagement, hottest accounts; then pool candidates
(Unowned, Not eligible or never carved, owned by the import user) that clear `engagement.reentry` or the
fit floor, ranked by engagement then fit, each with the rep who has the most room in its segment and
region. Assigning them is Step 7 on the pool: `carve_workflow.py run --only-pool` now includes Not
eligible accounts, and the gates accept the re-entry rule.
