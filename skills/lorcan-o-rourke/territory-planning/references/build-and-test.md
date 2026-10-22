# Build a controlled scoring draft

Use the current Workflows guidance for nodes, data passing, testing and Audiences mappings. CLI help
is authoritative. This reference is an implementation contract, not a frozen API client.

## Evidence plan before creation

For each active factor record: business question; existing field and freshness; missing data; selected
capability; exact packageId/actionKey or workflow function ID; required input combination; accepted
parameter values; real payload path; status/identity validator; fallback condition; result cap;
source/freshness handling; price status and measurement plan. Actions named in current-actions are
schema-checked candidates, not evidence of provider yield. Resolve identities and dynamic products
before relying on fields. Do not invent a missing action or silently change the criterion.

## Graph contract

- Create a named draft with a controlled manual/CSV/test-data entry. No segment membership or
scheduled trigger during calibration. A workflow create response is not proof a graph was built.
- First preserve stable account ID, input domain and fixed score_as_of. Run a resolve guard before
any material research, or validate the supplied authoritative identity without buying another lookup.
- Add only missing evidence steps; ordinary company enrichment can supply several rubric inputs.
Gate optional research and fallbacks with explicit conditions. Use one no-match path per conditional.
If a provider failure cannot reach the scorer through supported error handling, report that run as
failed. Never hand-patch a success status into the destination.
- Normalize into the account contract and keep the evidence snapshot. The Score step receives
rubric_json (fixed approved JSON) and account_json (a JSON string containing the normalized account).
Use the exact score_account handler and flat outputs result_json:string, scoring_status:string,
rubric_version:string, each with a description. Null totals live inside result_json only.
- A caller must explicitly pin upstream values. Tool results are under $.result; code results are
at $.field. Tool mappings live inside tools[].inputMappingConfig. Confirm saved bindings by reading
nodes back. Tools do not echo input context. Do not use retired map/reduce/collect nodes.
- For branch convergence use only a supported shape that does not wait for an unexecuted branch.
A chain of actual conditional fallbacks is not equivalent to always running all providers.
- A held result writes latest-attempt status, reason and version only. Keep last-valid score and its
version/as-of in separate fields. Never clear populated score fields. Every downstream filter must
check latest-attempt status and freshness before using last-valid values.
- Audience writeback is included only for an authorized Audience destination. Reuse obvious fields,
create missing dedicated fields under that authorization, match stable record IDs and read back.
If the requested destination is a file/run output, do not silently upsert companies by domain.
- More than 8..10 nodes should be grouped into stages as built. Read current grouping mechanics.
Keep a new graph unpublished. Publish/start has separate effects and is not required for draft tests.

## Testing in Clay

First run local regression tests. Use code test with the exact flat output field map on scored and
held inputs and inspect isError and outputSchemaValidated; an exit code of zero is insufficient.
Then test the saved workflow draft using stored test data or the supported draft-run command. Do
not publish merely to make a test command work. Show live run progress before starting/waiting.
Inspect the full steps for every pilot: trigger values, matched entity, action inputs, raw outputs,
normalization, score, destination write and readback. Check terminal status before interpreting costs.
A standalone code test does not test provider bindings, trigger behavior or saved field mappings.

For a weight-only revision keep evidence, re-score and compare old/new by account ID. For a source
or evidence normalization change, re-run affected cases. Create no automatic schedule unless asked.

## Workflow attribution

Only the Marketplace-assigned identity from the installed skill may be used for source attribution.
Announce that a source line will be written. Fresh drafts without assigned identity get no invented
marker. Preserve descriptions, avoid duplicate lines, and report conflicting source markers without
overwriting them. Attribution is editable tracing, not tamper-proof provenance.

## Shipped size + seller-motion adapter

The builder supports exactly two active factors named size and motion. The motion map must include
sales_led, self_serve, hybrid and consumer; use the fictional adapter-fixture as format documentation,
not a production policy. The separate test-fixtures uses the older fictional arithmetic categories
and must not be substituted. Other criteria need reviewed normalization and builder extensions.

Run from the package directory. Keep working files/receipts outside it so private evidence cannot
enter a later ZIP. These local commands make no Clay requests:

```bash
mkdir -p ../territory-planning-work
python3 -B scripts/test_skill.py
python3 -B - <<'PYFIXTURE'
import json
from pathlib import Path
f = json.loads(Path('references/adapter-fixture.json').read_text())
w = Path('../territory-planning-work')
(w / 'demo-rubric.json').write_text(json.dumps(f['rubric'], indent=2) + '\n')
PYFIXTURE
python3 -B scripts/build_workflow.py --rubric ../territory-planning-work/demo-rubric.json --mode replay > ../territory-planning-work/replay-plan.json
python3 -B scripts/build_workflow.py --rubric ../territory-planning-work/demo-rubric.json --mode research > ../territory-planning-work/research-plan.json
```

Only after scope/environment authorization and inspection of that plan, --create changes Clay:

```bash
python3 -B scripts/build_workflow.py --rubric ../territory-planning-work/demo-rubric.json --mode replay --create --name 'Account fit evidence test' --receipt ../territory-planning-work/draft-receipt.json
```

Use an approved real rubric instead of the demo before business scoring. Research mode adds a
Claygent and can incur research costs when someone subsequently tests it; graph creation itself
starts no run. The model option defaults to gpt-5.4-nano. Check model availability and current
installed guidance. The builder does not fetch fresh company data, create a destination, start a
trigger, publish, or execute its created workflow.

Replay graph: Manual -> Validate identity and evidence -> Versioned rubric -> Deterministic account
score -> Audit result with source fields. Research mode inserts Check identity before research
and Seller motion research after Manual. Each trigger has one outgoing edge. There are five or
seven nodes including the trigger. No branching, parallel trigger fanout or unavailable join is
needed for this bounded reference. A new richer graph must follow installed branching/grouping rules.

### Trigger and code contracts

Trigger inputs are JSON strings:
- context_json: stable account_id, target domain, fixed score_as_of, explicit allowed_entity_types,
  company_source, optional company_retrieved_at and approved_domain_aliases, and evidence_policy.
- company_json: the previously captured action envelope with success:true and an actual result.domain.
  Required headcount semantics are employee_count, size and the selected source-date field. Input
  domain alone is not provider identity. Reuse paid snapshots when still fit under the chosen policy.
- research_json: captured research observation or its actual structuredOutputs envelope, required
  only for replay. Research mode derives authoritative name/domain/date through identity preflight;
  no independent user-supplied scalars may override that identity.

Evidence policy explicitly selects nonnegative headcount_max_age_days and motion_max_age_days,
headcount_date_basis (provider_refresh or observation), and headcount_band_conflict (hold or
ignore_with_disclosure). The observation option requires an actual provider observation field;
never relabel retrieval time. Provider-refresh basis is disclosed as not a count observation date.
Ignoring a count/band conflict requires explicit policy approval, not an agent's convenience.

Handlers and declared string outputs:
- normalize_account.py: context_json, company_json, research_json -> account_json,
  raw_evidence_json, review_status. research_inputs(context, company) supplies the research preflight.
- score_account.py: rubric_json, account_json -> result_json, scoring_status, rubric_version.
- export_results.py: result_json, account_json -> row_json. Raw audit fields do not turn held
  published components/evidence into a valid score.

The local exporter accepts an array of complete audit rows or handler outputs containing row_json.
Write that array to a private rows.json, then run python3 -B scripts/export_results.py rows.json
results.csv. It uses csv.DictWriter and parses the CSV back to verify every row has the declared
field count. The step_output helper supports known code/structuredOutputs envelopes and rejects
conflicting duplicated fields; it does not recursively guess a convenient URL.

### Creation receipt and readback

The private receipt records workflow/trigger/node IDs, saved graph, validation and partial errors.
An existing receipt is refused so retries cannot create a second draft silently. A stopped builder
can leave an incomplete draft; inspect and repair its named resources through supported commands
rather than rerunning --create or deleting user data. An approval result may already have executed
the blocked operation. Never assume failure from a missing response.

Require valid:true with no validation errors. The receipt also keeps warnings/suggestions for review.
Read each saved code, binding and required field against the rendered plan. Saved code output
fields may be wrapped in an object with properties by the read API; compare field definitions after
accounting for that representation, not by deleting required declarations to make equality pass.
Structural validation is not semantic readback or a test run. Select explicit stored test rows;
never count generated incompatible examples as passes. See destination-preflight.md for recovery.

## Multi-source seller research in rc3

The researcher also returns business_sales_evidence, unresolved_sales_routes and source_urls_json.
The last field is a JSON-encoded array of official URLs actually inspected; it does not list search-only
or unreadable pages as inspected sources. The adapter retains/deduplicates the primary source and
supporting URLs and validates every host. Mixed needs both consumer and business purchase evidence.
A nonempty unresolved-sales note holds the factor, including nonsensical model output; never silently
clear it. The export adds business_sales_evidence, unresolved_sales_routes and motion_sources_json.
Use the shipped COLUMNS definition, not a stale handwritten CSV header.

Retail checkout plus confirmed sales-assisted wholesale can be hybrid + mixed. This changes the
research verdict when evidence supports it; it does not silently change the rubric. The demo still
gives hybrid full motion points, so it is not a calibrated B2B-only fit model. Generic bulk ordering
and a support email are insufficient to prove business buyers. An unreadable potential wholesale
route must remain unresolved until inspected or covered by a reviewed alternative source.

## RC4 scoring-to-carve replay draft

Use scripts/build_carve_workflow.py for the optional complete-population replay. It is separate from
build_workflow.py, which builds scoring only. The strict allocation/attribute and export contracts,
plus a completely local fictional run, are in pool-and-carve.md.

After creating the private demo-rubric.json above, rendering makes no Clay request:

```bash
python3 -B scripts/build_carve_workflow.py --rubric ../territory-planning-work/demo-rubric.json > ../territory-planning-work/carve-replay-plan.json
```

Only under the user's explicit create authorization:

```bash
python3 -B scripts/build_carve_workflow.py --rubric ../territory-planning-work/demo-rubric.json --create --name 'Account fit and reviewed carve proposal' --receipt ../territory-planning-work/carve-draft-receipt.json
```

Creation starts no run and writes no company, owner or CRM field. Read the private receipt and saved
graph against the rendered plan. Test only explicit stored rows after inspecting their actual inputs.
Each row must contain one complete population, not one account, so shared rep capacity is never reset.
The manual trigger takes evidence_json (1..50 saved scoring-adapter cases) and allocation_json (all
reviewed policy, account attributes and rep loads). The pool step enforces at most 50 total accounts,
including synthetic additions, and refuses missing/null/text protections and unsupported policy.

Step outputs are strings:
- Replay scoring: scored_accounts_json and scoring_audit_json.
- Validate/freeze: snapshot_json.
- Proposal engine: proposal_json.
- Independent check/export: checks_json, account_rows_json and books_rows_json.

Pin the final step's snapshot_json to the pool step and proposal_json to the engine. Never substitute
the proposal's self-reported capacities for the original ledger. Keep scoring_audit_json and the
frozen snapshot with the checked exports. Reordering retains supplied snapshot rep-list order but
must not change proposals, books or checked export rows. CSV creation uses the pipeline's real writer
and parsed readback; do not paste a handwritten header from an older release.

The strict pipeline and new fixture are covered by scripts/test_carve_pipeline.py, imported by the
complete test_skill.py suite. Wrong proposal context, held assignment, fabricated capacities, missing
population rows and unsafe flags must fail before usable export. A failed test is not an authorized
reason to change a source fact, clear existing values, remove a protection or reset the destination.
