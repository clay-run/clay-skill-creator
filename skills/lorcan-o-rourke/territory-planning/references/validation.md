# Acceptance and release gates

## Layer A: offline behavior

Run python3 scripts/test_skill.py from the package directory. Tests use only fictional fixtures and
standard-library Python. They cover deterministic arithmetic, grade boundaries, typed zero/false,
weights, invalid categories, nulls, missing statuses, coverage, cap safety, evidence and identity.
They also exercise a shared carve ledger, stable ties, protections, overflow and unsupported methods.
The complete suite also imports scripts/test_carve_pipeline.py for strict pool metadata, missing/null/
text boolean refusals, corrupted proposals, independent book totals, fixture provenance, builder pins
and refusal before export/overwrite. It imports scripts/test_evidence.py for snapshot normalization, freshness,
seller/consumer/wholesale semantics, unreadable-route holds, supporting-source retention, graph pins
and actual CSV round-trip checks. Run tests from the exact
extracted ZIP, not only the development tree. Passing is local behavior on those inputs, not live
provider accuracy or calibration.

## Layer B: runtime and live workflow

Choose a permitted test workspace. Never use a livestream workspace or organization. A first test
can use CSV or run output with no CRM. If Audiences is the chosen destination, test actual Audience
writes and readback; file-only output cannot certify that path. For CRM choose and verify a sandbox
or Developer Edition, one object, dedicated score fields and record IDs. No owner-write action is
included in scoring. Local test data does not authorize a live CRM test.

Select exact stored test-row IDs after listing them; generated examples are not automatically
authorized or compatible. Inspect one complete live research/export pilot before the remaining
approved rows. Count unintended generated failures separately, not as successful intended cases.

Test the same saved draft on five known domains with installer-provided expected grades. Capture:
- expected/actual identity and stable source ID; wrong-company hits are failures, not rubric misses;
- each raw action input/output and normalized evidence, including source and freshness;
- independent recomputation of every component, weighted contribution, total and boundary grade;
- a one-line reason using accepted evidence; expected-grade differences and owner's explanation;
- zero/false, provider miss, provider error, capped technology and unresolved identity cases;
- valid save and readback, plus held attempt preserving the old valid score but blocking its use;
- actual terminal status and available per-run accounting; unknown actuals remain unknown.

The five-account deliverable includes total / 100, grade, per-factor points, weighted coverage,
expected grade and reason. Do not invent benchmark totals for real accounts. All five must have a
reviewed identity and outcome. A genuine hold can pass its technical hold-policy check; it cannot
substitute for agreement about a graded business benchmark. If all expectations remain unknown,
report technical/provider testing only. Agree any unresolved case's treatment with the owner.

A passing core build requires the business owner to accept the five-account review, not necessarily
force all original expectations. Keep rejected hypotheses and changed rules in the record. Before
more than 100 accounts, run a stratified 10-account independent slice using the same paths, report
failure patterns, then ask before the remaining accounts under the host's cost/approval policy.
No full-population test is implied by the supplied 200-account CSV existing on disk.

## Layer C: optional carve

Use the strict pool and independent checker in pool-and-carve.md, not an unchecked engine result.
Test the frozen entity snapshot with all records accounted for once. Verify eligibility and protection
inputs from authoritative evidence before the preview. Check no protected owner is proposed for a
change, no excluded/held row is assigned, no rep is proposed over capacity, and shared reps have one
ledger across buckets. Existing over-capacity books are reported; the engine does not fix them by
moving protected accounts. Reorder accounts/reps and get the same allocation. Check a zero-capacity
rep, unmatched bucket, named request with no capacity and unsupported family/dynamic policy.

A future CRM writer needs exact row/field preview, organization confirmation, approval, one-row test,
readback, bounded remainder, partial-failure reconciliation and idempotent retry evidence. Until
implemented and tested, optional carve is proposal-only. Never call it a successful CRM end-to-end run.

## Layer D: package and submission

Use the skill-creator repository's tools/package_skill.py to validate the package, fetch the action
catalog read-only, then validate with --action-catalog. Validate the deterministic ZIP manifest.
Keep answer sheets, live data, reports, tokens and receipts outside the package.
A static clean result does not replace Layer B. In a clean project, start a genuinely fresh agent,
verify that this exact skill was discovered, run its local suite/fixture and inspect render-only
builder outputs. Do not pass prior conversation, receipts or expected business grades as a shortcut.
Record discovery failure, an unavailable runner or an unexecuted live path as unconfirmed. Core live tests gate a scoring-first submission;
unimplemented optional paths must be disclosed, not marketed as passing. Do not submit until the
user explicitly accepts the exact package and the required submission consent after preview.
Submission enters review; it is not publication.
