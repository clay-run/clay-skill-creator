# Destination preflight and safe recovery

Run this before paid enrichment if persistence is required. The shipped builder is run/file-only;
it does not create fields, save Audience records, or provision CRM metadata. A writer is a separate
implementation using current installed guidance, exact field mappings and an authorized destination.
Do not report that path as tested until actual write/readback tests pass.

## Inspect before spending

1. Resolve the intended records by stable IDs. An Audience segment filters shared records; it is
   not an isolated copy. Several records with the same domain are not proof of a canonical match.
   Never silently choose the first or most-complete record, merge them, or update every duplicate.
2. Inspect existing fields, types, meanings, permissions and reported field-capacity limits. Reuse
   only fields whose semantics match and whose use was authorized. Dedicated total/grade/reason,
   rubric version/as-of, latest-attempt status and coverage must be distinguishable from raw inputs
   and any last-valid result. List required and optional mappings before creating fields.
3. Under a requested writeback scope, create the missing dedicated fields using supported commands;
   no extra confirmation is needed for that implementation detail. If required creation fails,
   stop that path. A successful number field does not prove a text field can also be created.
   A capacity or persistent server error is not a scoring defect. Do not evade it by deleting fields,
   changing types, reusing unrelated scores, or routing data to an undeclared destination.
4. Report exactly which fields exist and which are blocked. Inspect schema after an ambiguous
   creation response before retrying. Preserve already-created resources for review; no automatic
   cleanup/deletion. Ask once for the genuine destination decision if it is needed: wait for safe
   capacity or explicitly use run/file output. Do not ask the same question again after file-only
   was chosen. A file proves its contents, not Audience or CRM delivery.
5. Verify a nonproduction CRM organization from metadata or an administrator before any first CRM
   write test. Connection aliases alone do not establish sandbox safety. No CRM writer ships here.

## Persistence acceptance

A scored attempt may save its total, grade, components, evidence, version/as-of and status to the
approved dedicated fields. A held attempt updates latest-attempt status/reason/version only and
keeps last-valid values separate. Do not clear existing scores, publish raw failed evidence as valid
components, or let an old score appear to be the latest successful result. Every consumer checks
attempt status and freshness. If the destination cannot preserve that distinction, do not enable it.

Test an actual valid save, then a held attempt on the same test record, and read both back by ID.
Confirm ownership, source and lifecycle fields remain unchanged. Verify required mappings separately;
a headline score appearing does not prove its reason/components saved. Report partial writes and
reconcile them before retrying only the failed approved fields. For concurrent or recurring runs,
use supported ordering/conditional-write controls so an old run cannot overwrite a newer result;
otherwise keep that mode disabled and disclose the missing protection.

## Recover the affected step, not the paid chain

Preserve raw company/research envelopes and the rubric before correcting code, pins or exports.
Re-run deterministic normalization, score and export locally or through isolated runtime checks
with those saved values. A revised research prompt needs a new bounded live research pilot; replay
alone cannot certify model behavior. Do not repurchase headcount because an export omitted a URL.

For published failed runs, consult installed recovery guidance and a supported dry-run before using
its rerun mechanism. That mechanism may run the published graph rather than the corrected draft.
For an unpublished draft, use explicit saved test rows or replay inputs. A one-step test does not
run downstream steps. Verify terminal history before retrying anything that may already have run.
Approval can itself execute the action. If its result is unavailable, check read-only state first;
never replay a request merely to check status. Textual permission does not bypass a backend gate.

List stored test rows and select exact intended IDs. Drafts can contain AI-generated examples whose
JSON does not satisfy this adapter. Do not use Run all or an all-rows flag unless every row was
inspected and intentionally included. Count intended passes and extra failures separately. Missing
configuration is a configuration error, not a fabricated successful data hold.

If an upstream provider fails so the graph cannot emit a row through supported error handling,
report that run as failed with its saved evidence. Do not manually manufacture a completed result.
