# What the author resolved, dated

**Observed 2026-10-29 to 2026-11-10, in two workspaces on one plan, by builds and test runs that
spent the credits.** This file is evidence of what resolved and what the responses looked like. It
is not a price list and not a roster. **Where this file and the live catalogue disagree, the
catalogue is right.** Read every cost from `clay workflows actions schema` or from the run's own
reported usage before quoting it to anyone.

## The pairs the source workflow bound

Each tool node binds one action by its package id and action key. The pair is the identifier; the
key alone collides across packages. These are the pairs the author's workflow resolved on the
dates above. Re-resolve each one in the installer's catalogue before binding; a pair that no
longer resolves is replaced by another action doing the same job, not by the nearest name.

| Job in the skill | Package id | Action key | What the author observed |
|---|---|---|---|
| Match a contact or company in the installer's own Audiences | `b1ab3d5d-b0db-4b30-9251-3f32d8b103c1` | `lookup-in-audiences` | Clay-native. Returns `result.records[]` with `fields` keyed by the workspace's field display names, `signals` keyed by signal type, and `result.totalMatched`. The record id sits at `records[0].fields.id`. |
| Write five fields onto an existing contact | `b1ab3d5d-b0db-4b30-9251-3f32d8b103c1` | `update-audiences-record` | Takes the record id and a selected-fields list; every selected field needs a binding or the call rejects. Unknown field ids are dropped silently, so a run reads green while writing nothing. Returns `result.upsertedFields`. |
| Create a contact that was not matched | `b1ab3d5d-b0db-4b30-9251-3f32d8b103c1` | `upsert-audiences-record` | Lookup on email, then the same selected-fields contract. |
| Person enrichment | `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2` | `cpj-enrich-person` | Managed function. Accepts a profile identifier or an email; the profile URL is the reliable identifier. By email alone it returned `result: {}` with a "No Profile Found" preview for a real, well-covered person; by profile URL it resolved the same person first try, with `title` and `url` under `result`. Observed at 0 credits and 1 action execution. |
| Company enrichment | `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2` | `cpj-enrich-company-v2` | Managed function. Accepts a domain, a profile URL or a company id. Returns `result.name`, `result.domain`, an exact `employee_count` beside a `size` band string, `industry`, and a revenue band string. An unresolvable domain returns `success: true`, `result: {}`, preview "Company Not Found": a miss, not an error. |
| Company topic intent | `a3ca5432-b8f3-408c-a02e-596bbcc3058e` | `bombora-find-company-topic-intent` | Requires a topic list; topic names are a dynamic option set. Returns `result.topics[]` with `topic_name`, `composite_score`, `event_date`. Catalogue showed 0.6 credits per call on these dates. One topic at 57 for the author's own company; the surge threshold the author used was 60. |
| Person topic intent | `3773a82e-cee4-44d8-957d-1e76b771c7d2` | `intentsify-find-person-topic-intent` | Requires a profile URL and a topic id list; topic ids are a dynamic option set of about forty thousand entries. Returns `result.topics[]` with `topic_name`, `composite_score`, `stage`. Catalogue showed 0.5 credits per call. Fails the whole run if the URL input is empty, which is why a conditional guards it. |

## What else was observed, and bears on the build

- **Audiences field catalogue caps.** One workspace refused to create a sixth text field with a
  message naming a 200-field limit for text, email and URL fields on people. Numeric fields were
  unaffected. The skill folds status into the reason field when this happens, and says so.
- **Audiences record ids are workspace handles.** The lookup returns them; the update needs them;
  neither belongs in a skill. The workflow pins them at run time.
- **Pinned paths with spaces** in a field name resolve with bracket notation. A dotted path with a
  space in it resolves to nothing without an error.
- **A tool node does not echo inputs.** Pins that reach across a tool node resolve to nothing. Pin
  from the producing node.
- **Signal events on people were absent** in both workspaces across six months, while company
  records carried job-post, new-hire and website-visit signals. A model that leans on person
  signals will score zero on that rule until the installer turns such signals on.
- **Test runs are not free of side effects.** A test run writes to Audiences exactly as a live run
  does, because the write is the last node. The ten-contact batch creates or updates ten records.
  Say so at the gate.
- **Run timing** on test runs ranged from a few seconds to about forty when both agents fired.
  Not measured under load or unattended.
