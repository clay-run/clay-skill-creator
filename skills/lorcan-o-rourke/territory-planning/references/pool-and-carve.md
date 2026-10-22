# Optional carve: reviewed pool, one ledger, checked proposal

Scoring comes first. This path makes an entity-level proposal, never an owner update. No Salesforce
peer query, provisioning/reset, import user, family rollup or owner executor ships. If the requested
policy is unsupported, stop this path and keep the useful scoring result.

## Before the pool

Obtain the approved eligibility cutoff, bucket rules, protections/exclusions, named rep requests,
allowed rep buckets, capacities and existing loads. Never borrow the author's regions, industries,
thresholds or exclusions. Derive attributes using reviewed, separately tested rules and authoritative
ownership/customer/opportunity inputs. Missing information is not permission to treat an account as
unowned or unprotected. A customer or open opportunity without a reviewed owner stops this bounded
implementation rather than inventing an owner.

Use scripts/carve_pipeline.py build_snapshot(scored_accounts, allocation). Validate before coercing:
false is an actual boolean; missing, null, text "false" and numeric zero are not boolean substitutes.
The scorer's held result has no score and is never eligible. Observed numeric zero is valid.

## Allocation input contract

allocation is an object with all of these fields:

| Field | Contract |
|---|---|
| snapshot_id, rules_version | Nonempty strings identifying this frozen population and policy |
| grain | Exactly entity; family is rejected |
| method | Exactly snake or round_robin; no fallback to either |
| min_eligible_score | Finite numeric 0..100; a boolean is invalid |
| fixture_only | Explicit boolean; true means allocation assumptions are fictional |
| account_attributes | Exactly one row per input scoring result or explicit synthetic fixture account |
| reps | Nonempty list with unique rep_id values |
| fixture_accounts | Optional synthetic result rows; allowed only with fixture_only:true |

Each scoring result supplies account_id, scoring_status (scored or held), and account_fit_score.
A scored total is finite 0..100. A held total is null. Use accepted scorer outputs, not invented
production scores. Duplicate IDs, including overlap between scored and synthetic inputs, fail.

Every account_attributes row explicitly supplies:
- account_id; protected, excluded, is_customer and has_open_opportunity as booleans;
- current_owner_id and bucket as strings (empty is explicit, not an omitted lookup);
- nonempty protection_source and exclusion_source, including evidence for reviewed false values;
- protection_reason when protected, exclusion_reason when excluded;
- optional requested_rep_id as a nonempty string.

Existing owners, customers and open opportunities must be explicitly protected. A protected account
requires a current owner and reason. Do not mark unknown ownership/customer/opportunity state false.
An account's eligible flag is calculated as scored AND score >= the approved cutoff; it is not a
substitute for protection or exclusion. An eligible protected/excluded row still cannot be assigned.

Each rep explicitly supplies rep_id, capacity, existing_load_outside_snapshot, and a nonempty list of
allowed buckets. Capacities/loads are nonnegative integers, not booleans or strings. Bucket values
are nonempty unique strings. Do not count an account both inside and outside this snapshot.

build_snapshot validates and returns a snapshot with the reviewed policy, reps and complete accounts.
It retains score_provenance (saved_evidence or synthetic_fixture) separately from
allocation_provenance (reviewed or fictional). fixture_only remains visible in exports. A fixture
flag never converts a synthetic business grade into an approved real score.

## Engine and independent check

Pass the validated snapshot to the unchanged scripts/carve_preview.py engine. Then call
scripts/carve_pipeline.py check_and_export(snapshot, proposal) before delivering any export.
Never certify a proposal by trusting its own capacities or reported totals.

The independent check requires identical snapshot/rules context; every input account and rep exactly
once; retained owner/bucket/reason; no assignment of protected, excluded, held or below-cutoff rows;
allowed rep/bucket and named request; and additions within remaining capacity recomputed from the
original inputs. It independently reconciles existing loads, proposed counts and pre-existing
capacity excess. Any violation raises before usable output rows are returned.

Dispositions are proposed, protected, excluded, not_eligible or unowned. Retained owned/protected
accounts take precedence. Existing over-capacity books are disclosed; protected accounts are not
moved to repair them. Requested reps do not override capacity. Unknown/unavailable reps, unmatched
buckets and exhausted capacity can leave a row unowned with its reason.

Account/rep input order does not change assignments or checked export rows. The snapshot retains
the supplied rep-list order. Within buckets the engine sorts descending fit then stable account ID;
bucket and rep IDs are lexical. Snake balances turn order, not equal revenue or globally optimal
books. Unsupported family, dynamic/draft/manager allocation and custom optimization stop this path.

## Bounds and workflow builder

The engine/local checker has a 2,000-entity implementation bound. The replay workflow has a tighter
controlled bound: 1..50 saved evidence cases, and at most 50 accounts INCLUDING synthetic additions.
These are implementation bounds, not Clay product limits. Never silently chunk a population and
reset the shared capacity ledger. Larger populations require a separately tested aggregate design.

scripts/build_carve_workflow.py renders a manual draft with four processing steps:
Replay scoring with evidence audit -> Validate policy and freeze pool -> Carve proposal only ->
Check input ledger before export. It reuses the shipped normalizer/scorer and unchanged engine.
It has no provider, research, CRM, field creation, execution or publication step. --create is explicit
and requires a private receipt outside the package; default behavior only prints the plan.

Trigger fields are JSON strings:
- evidence_json: list of saved context_json/company_json/research_json cases, as in the scoring
  adapter contract; one complete reviewed population per run;
- allocation_json: the explicit policy/metadata object above, with the same account IDs.

The final step receives BOTH snapshot_json and proposal_json from their actual source steps. It
returns checks_json, account_rows_json and books_rows_json, each a JSON string. Keep the frozen
snapshot and scoring_audit_json alongside reviewed exports so evidence is not lost.

## Exports and local fictional example

Account columns, in order:
snapshot_id, rules_version, fixture_only, account_id, score_provenance, allocation_provenance,
scoring_status, account_fit_score, eligible, bucket, current_owner_id, protected, excluded,
protection_source, status, proposed_owner_id, reason.

Book columns, in order:
snapshot_id, rules_version, fixture_only, rep_id, buckets, capacity, existing_load_outside_snapshot,
existing_in_snapshot, total_load, proposed, over_capacity.

Use references/carve-fixture.json only as fictional format documentation. Its six synthetic results
are explicitly fixture_accounts; none is real saved research. From the package root:

```bash
mkdir -p ../territory-planning-work
python3 -B - <<'PYFIXTURE'
import json
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')
from carve_pipeline import build_snapshot, check_and_export
from carve_preview import carve
f = json.loads(Path('references/carve-fixture.json').read_text())
snapshot = build_snapshot(f['scored_accounts'], f['allocation'])
proposal = carve(snapshot)
checked = check_and_export(snapshot, proposal)
w = Path('../territory-planning-work')
for name, value in [('snapshot', snapshot), ('proposal', proposal), ('checked', checked)]:
    (w / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
PYFIXTURE
python3 -B scripts/carve_pipeline.py ../territory-planning-work/snapshot.json ../territory-planning-work/proposal.json ../territory-planning-work/accounts.csv ../territory-planning-work/books.csv
```

The CLI validates the complete proposal before opening either CSV output. It uses csv.DictWriter and
parses written CSVs to check their width/count. This protects against rejected-proposal overwrite;
it is not an atomic two-file transaction if an I/O error interrupts a valid write. Reconcile partial
files before delivery. A proposal is not an assignment and no rollback/reset is needed.
