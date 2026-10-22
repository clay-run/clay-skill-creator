# Optional CRM boundary

No Salesforce setup/reset/writer script is included in this candidate. The original reset deletes
accounts/opportunities and metadata; an approval gate does not make a destructive Marketplace skill
appropriate. Never run it. A CRM import, custom user creation or layout change is not needed to prove
the scoring skill. No API token, direct login command or default organization is embedded here.

Core scoring can finish without any CRM connection. For an explicitly requested writer, discover the
current connector action, inspect dynamic fields and usable app accounts, and verify organization,
object, match key and write permissions. More than one plausible connection requires the user's
selection. Never identify a sandbox from alias text alone. Refuse first-run production writes.

Score-only allowlist: dedicated total, grade, reason, component values, version/as-of and attempt
status fields. No Owner/lifecycle/source fields and no unspecified object_fields. Preserve stable IDs.
Never match the first Website substring result; require exactly one reviewed entity match, or hold.
A multi-row lookup is ambiguous even when the action returns success.

Do not clear populated fields on a held attempt. Write latest-attempt status/reason separately from
last-valid score/version/time. All downstream consumers must check attempt status and freshness.
If the destination cannot preserve that distinction, do not activate writeback. Partial writes need
an explicit partial state and readback; a headline save alone does not establish component delivery.

An owner writer is a separate extension, disabled by default and not shipped here. Before any owner
write: reviewed frozen proposal, exact IDs/old/new owners, unchanged protection state, selected test
organization, explicit approval and readback. Revalidate current ownership before each approved
change; stale proposals hold. A changed snapshot or expanded scope needs fresh approval. Test one
row first, then a bounded approved batch with idempotent retries of failed rows only. A rollback plan
requires current-owner conflict checks and its own approval; never advertise blanket reversibility.

No record deletion, field clearing, automatic reset, cleanup of user data, external export or outreach
is an allowed fallback. Return the reviewed list for the user to act on in their own audited system.


## Test receipt is not a shipped writer

A separate, creator-private one-record plumbing experiment can establish that selected connector
fields save and read back. It cannot certify this package's integrated scoring persistence. Do not
copy its organization/record IDs, app account, field setup or supplied score into the portable skill.

When comparing before/after Salesforce records, separately report system audit fields and view/
reference timestamps (LastModifiedDate, LastModifiedById, SystemModstamp, LastViewedDate and
LastReferencedDate). They are not score-field permissions. Continue to reject unexpected changes to
Owner or any other returned business field. Validate the exact score allowlist and compare actual
readback, not just a successful update response. A post-write verification error does not undo a save;
inspect persisted values before any retry, and never reset the organization to retry one record.
