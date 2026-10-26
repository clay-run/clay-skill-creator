# Node graph — build order, edges, and node code

Read off the author's workflow configuration on 2026-10-26: 67 nodes, one webhook trigger, wired
serially apart from the convergences named below. **Every value in a code sample is read from a declared
input** — the author's own values appear in prose, labelled as theirs, and never in a line meant to be
pasted. The few places this graph differs from the author's are listed under **Deviations**.

Confirm node syntax with `clay workflows nodes --help`, and read one existing node of each type with
`clay workflows nodes get` before creating it. The field shapes below are the ones the author's workflow
used; the installer's workspace decides what it accepts.

## Conventions every node follows

- Blank or null values become `-` before they are pinned anywhere, so a missing field cannot fail the
  run. `-`, `none`, `null`, `n/a` and `na` are treated as blank when read back.
- Tool-node outputs are read at `$.result`; code-node outputs at `$`.
- Every value a node needs is pinned from **the node that produced it**, never through another node.
- **A gate that reads a lookup pins the lookup's whole `$.result` (plus `$.success` and `$.textPreview`)
  and decides in code.** It never requires `$.result.foundAtLeastOne`: an empty lookup does not return
  that key, and a required pin that cannot resolve fails the run outright.
- Every terminal node returns `{"status", "reason", "detail"}`.
- CRM lookups retry up to 3 tool-call failures; alert sends and the copy step retry 0.

## The chain, in dependency order

`→` is an edge; conditional edges are named by the transition that takes them. **Bold** targets are
terminal nodes.

| # | Node | Type | Fed by | Edges out |
|---|---|---|---|---|
| 1 | Webhook | trigger | — | → 2 |
| 2 | Intake — normalize payload | code | 1 (`$`) | → 3 |
| 3 | Payload OK? | rules conditional | 2 `payload_ok` | true → 4 · default → **Skip: invalid payload** |
| 4 | Audience OK? | code conditional | 2 `audience_skip` | `continue` → 5 · `filtered` → **Skip: audience filter** |
| 5 | Excluded tier? | code conditional | 2 `is_excluded` | `continue` → 6 · `excluded` → **Skip: excluded tier** |
| 6 | Persona? | code conditional | 2 `persona_normalized` | `continue` → 7 · `persona_not_live` → **Skip: unknown persona** |
| 7 | Look up contact by email | tool — CRM lookup | 2 `contact_email` | → 8 |
| 8 | Resolve contact | code | 7 `$`, 2 name / title / LinkedIn / account | → 9 |
| 9 | Has contact id? | rules conditional | 8 `lookup_error`, `contact_exists` | `lookup_error` → **Skip: lookup error** · `contact_exists` → 10 · default → **Skip: would create contact** |
| 10 | Look up route contact | tool — CRM lookup | 8 `contact_id` | → 11 |
| 11 | Check route contact fields | code | 10 `$.result` | → 12 |
| 12 | Route contact complete? | rules conditional | 11 `contact_complete` | true → 13 · default → **Skip: incomplete contact** |
| 13 | Prepare routing inputs | code | 8 name, email, LinkedIn, contact id | → 14 |
| 14 | Routing and rules of engagement | tool — installer's step | 13 | → 15 |
| 15 | Final qualification OK? | code conditional | 14 qualification | `ok` → 16 · `dq` → **Skip: disqualified** |
| 16 | Ids match? | code conditional | 14 resolved contact and account ids, 8 `contact_id`, 2 `new_account_id` | `match` → 17 · `mismatch` → **Skip: ids mismatch** |
| 17 | Get account | tool — CRM lookup | 2 `new_account_id` | → 18 |
| 18 | Suppressed? | code conditional | 17 `$.result` | `clear` → 19 · `suppressed` → **Skip: suppressed** · `lookup_error` → **Skip: lookup error** |
| 19 | Resolve assignee | code | 17 `$.result` | → 20 |
| 20 | Has assignee? | code conditional | 19 `assignee_user_id` | `has_rep` → 21 · `no_rep` → **Skip: no rep** |
| 21 | Look up assignee user | tool — CRM lookup (user) | 19 `assignee_user_id` | → 22 |
| 22 | Eligible for outreach? | code conditional | 14 `$.result`, 21 `$.result` | `eligible` → 23 · `not_enrolled` → **Not enrolled** |
| 23 | Check in-flight | tool — CRM lookup | 14 resolved contact id | → 24 |
| 24 | In-flight gate | code conditional | 23 `$.result`, `$.success`, `$.textPreview` | `clear` → 25 · `in_flight` → **Skip: in flight** · `lookup_error` → **Skip: lookup error** |
| 25 | Check account cooldown | tool — CRM lookup | 2 `new_account_id` | → 26 |
| 26 | Account cooldown? | code conditional | 25 `$.result`, `$.success`, `$.textPreview` | `clear` → 27 · `hit` → **Skip: account cooldown** · `lookup_error` → **Skip: lookup error** |
| 27 | Dry run? | code conditional | 2 `dry_run` | `live` → 28 · `dry` → **Would enroll** |
| 28 | Prepare outreach | code | 14 `$.result`, 21 `$.result`, 2 persona and subtype, 17 lookalike fields | → 29 |
| 29 | Generate outreach | subworkflow call (installer's generator), or LLM node | 28 | → 30 |
| 30 | Normalize copy | code | 29 `$` | → 31 |
| 31 | Copy generated? | rules conditional | 30 `status` | `status = generated` → 32 · default → **Skip: copy failed** |
| 32 | Which sequence? | rules conditional | 28 `sequence_type`, 11 `has_phone` | `automatic` → 33a · `manual` + phone → 33b · `manual` without phone → 33a · default → **Skip: blank guidelines** |
| 33a | Add to automatic sequence | tool — sequencer add | 30 copy fields, 21 rep email, 14 resolved contact id | → 34 |
| 33b | Add to manual sequence | tool — sequencer add | same as 33a | → 34 |
| 34 | Normalize enrollment result | code | 33a `$.result`, 33b `$.result` | → 35 |
| 35 | Enroll OK? | rules conditional | 34 `enroll_ok` | true → 38 · default → 36 |
| 36 | Wait for sequencer | delay (verify delay) | 35 | → 37 |
| 37 | Verify enrollment | tool — sequencer read assigned sequences | 14 resolved contact id | → 37b |
| 37b | Verify OK? | code conditional | 37 `$`, 34 `expected_sequence_id` | `verified` → 38 · `not_verified` → **Alert path** |
| 38 | Prepare campaign member | code | 34 `sequence_id`, 14 resolved contact id | → 39 |
| 39 | Attribution ready? | rules conditional | 38 `contact_id`, `campaign_id` | both not empty → 40 · default → **Alert path** |
| 40 | Write campaign member | tool — installer's create-or-update step | 38 | → 40b |
| 40b | Campaign member OK? | rules conditional | 40 `$.result` campaign member id | not empty → 41 · default → **Post-enroll alert** |
| 41 | Add to task queue *(optional)* | tool — installer's step | 14, 21, 34, 38, 40 | → 41b |
| 41b | Queue OK? | rules conditional | 41 `$.result` record id | not empty → **Enrolled** · default → **Post-enroll alert** |

Without a task queue, 40b's not-empty edge goes straight to **Enrolled**.

**The four convergences, and why none of them is a merge node** — in each, only one feeding branch runs:

- **Skip: lookup error** is fed by 9, 18, 24 and 26. It returns `lookup_error` and feeds the alert path.
- **Alert path** (error monitoring → alert send → terminal `error`) is fed by Skip: lookup error, 37b and
  39.
- **34 Normalize enrollment result** is fed by 33a and 33b. It reads both and keeps the one with a
  non-empty result.
- **Post-enroll alert** (code → alert send, terminal) is fed by 40b and 41b.

## Deviations from the author's workflow

- **Persona (6).** The author's workflow is currently configured to let every persona continue. Here it
  passes everyone **unless the installer turned the persona filter on**, in which case only their list
  continues.
- **Cooldown (26).** The author's workflow currently runs with the cooldown off. Here the cooldown skips
  **when the installer turned it on**; with cooldown off, nodes 25 and 26 are not built and 24's `clear`
  edge goes to 27.
- **Dry-run switch (27).** New. The author's workflow has a pause flag only.
- **Left out:** a pass-through "product user?" conditional, and an unused contact-creation stub.

## Node code

### 2 — Intake — normalize payload

`field_map` maps this node's names onto the installer's signal field names from Step 1 of the skill. The
excluded tier, placeholder names, identity length and switches are declared inputs.

```python
def handler(context):
    import json
    payload = context.get_input("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if isinstance(payload.get("payload"), dict) and not payload.get("event_id"):
        payload = payload["payload"]

    fmap = context.get_input("field_map")                       # DECLARED: the signal's field names
    excluded_tier = (context.get_input("excluded_tier") or "").strip().lower()
    placeholders = [p.strip().lower() for p in (context.get_input("placeholder_names") or [])]
    max_len = int(context.get_input("max_identity_length") or 0)
    paused = context.get_input("paused") is True
    dry_run = context.get_input("dry_run") is True

    def s(key):
        v = payload.get(fmap.get(key, key))
        return "" if v is None else str(v).strip()

    def pin(v):
        return v if v else "-"

    name = s("contact_name")
    parts = name.replace(",", " ").split()
    old_id, new_id = s("old_account_id").lower(), s("new_account_id").lower()
    old_name, new_name = s("old_account_name").lower(), s("new_account_name").lower()
    old_dom, new_dom = s("old_domain").lower(), s("new_domain").lower()

    subtype_raw = s("usage_subtype").lower()
    if "power" in subtype_raw:
        subtype = "power_user"
    elif "product user" in subtype_raw:
        subtype = "product_user"
    else:
        subtype = "regular"

    skip = ""
    if paused:
        skip = "workflow_paused"
    elif (old_id and old_id == new_id) or (old_name and old_name == new_name) or (old_dom and old_dom == new_dom):
        skip = "same_company"
    elif new_name in placeholders:
        skip = "placeholder_new_account"
    elif "{{" in name or "}}" in name or (max_len and (len(name) > max_len or len(new_name) > max_len)):
        skip = "unusable_identity"

    return {
        "event_id": pin(s("event_id")),
        "contact_name": pin(name),
        "first_name": pin(parts[0] if parts else ""),
        "last_name": pin(" ".join(parts[1:])),
        "contact_email": pin(s("contact_email").lower()),
        "contact_title": pin(s("contact_title")),
        "contact_linkedin": pin(s("contact_linkedin")),
        "persona_normalized": pin(s("persona").lower().replace(" ", "_")),
        "usage_subtype": subtype,
        "old_account_name": pin(s("old_account_name")),
        "new_account_id": pin(s("new_account_id")),
        "new_account_name": pin(s("new_account_name")),
        "is_excluded": bool(excluded_tier) and s("new_tier").lower() == excluded_tier,
        "payload_ok": bool(s("event_id")) and bool(new_id or new_dom),
        "audience_skip": skip or "clear",
        "dry_run": dry_run,
    }
```

The author's workflow used an 80-character identity limit, skipped the placeholder employers `stealth`
and `undefined`, and excluded the `enterprise` product tier. Its subtype rule is the one above. It also
normalises the person's usage at the old company, which this graph does not need.

### 6 — Persona?

```python
def handler(context):
    persona = str(context.get_input("persona_normalized") or "").strip().lower()
    filter_on = context.get_input("persona_filter_on") is True          # DECLARED
    live = [p.strip().lower() for p in (context.get_input("personas") or [])]
    if not filter_on or any(persona == p or persona.startswith(p + "_") for p in live):
        context.transition_to("Look up contact by email", "continue")
    else:
        context.transition_to("Skip: unknown persona", "persona_not_live")
```

### 7 — Look up contact by email

A CRM lookup by work email that **cannot match a blank email**: filter on email equal to the value, email
not null and email not empty, limit 1. Return id, name, first and last name, email, title, account link,
LinkedIn URL, and the "in an active sequence" flag, using the installer's field names.

### 8 — Resolve contact

The rule that matters: **a failed lookup is not a missing contact.**

```python
def handler(context):
    import json

    def as_dict(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {"_parse_error": True}
        return v if isinstance(v, dict) else {}

    lookup = as_dict(context.get_input("lookup"))
    if isinstance(lookup.get("result"), dict):
        inner = lookup["result"]
        inner["_success"] = lookup.get("success")
        lookup = inner

    def failed(l):
        if not l or l.get("_parse_error"):
            return True
        if l.get("_success") is True:
            return False
        return not any(k in l for k in ("foundAtLeastOne", "records", "totalSize"))

    email = str(context.get_input("work_email") or "").strip().lower()
    if email in ("", "-"):
        return {"contact_exists": False, "lookup_error": False, "contact_id": "-",
                "identity_reason": "missing_work_email"}
    if failed(lookup):
        return {"contact_exists": False, "lookup_error": True, "contact_id": "-",
                "identity_reason": "lookup_error"}

    records = lookup.get("records") or []
    rec = records[0] if records else {}
    if rec.get("Id"):
        return {"contact_exists": True, "lookup_error": False, "contact_id": rec["Id"],
                "work_email": (rec.get("Email") or email).lower(),
                "identity_reason": "reuse_existing_contact"}
    return {"contact_exists": False, "lookup_error": False, "contact_id": "-",
            "identity_reason": "contact_not_found"}
```

The keys inside `rec` are the installer's CRM field names.

### 11 — Check route contact fields

Reads the contact by id (with phone) and returns `contact_complete` (every required field usable and an
id present), `missing_fields` as a comma-separated list, and `has_phone`. A value is unusable if it is
blank, one of `-`, `n/a`, `na`, `null`, `none`, `undefined`, `unknown`, `nil`, or contains `{{`. The
required list is a declared input.

### 14 — Routing and rules of engagement

**This is the installer's step, not this skill's.** It must return, at `$.result`:

| Field | Used by |
|---|---|
| qualification (`Disqualified` stops the run) | 15 |
| resolved contact id and account id | 16, 23, 33, 37, 38 |
| whether the person belongs to another team's motion (true stops the run) | 22 |
| which booking link to use — the rep's own, or one it returns — with a flag for each | 22 |
| sequence type — `automatic`, `manual` or blank | 28, 32 |

In the author's workspace this was a separate function, called with full name, email, LinkedIn URL and a
fixed qualification-trigger label. It was not read.

### 15, 16 — Final qualification OK? and Ids match?

```python
def handler(context):                       # 15
    qual = str(context.get_input("qualification") or "").strip()
    if qual == "Disqualified":
        context.transition_to("Skip: disqualified", "dq")
    else:
        context.transition_to("Ids match?", "ok")
```

```python
def handler(context):                       # 16
    a = str(context.get_input("resolved_contact_id") or "").strip().lower()
    b = str(context.get_input("routed_contact_id") or "").strip().lower()
    if a and b and a == b:
        context.transition_to("Get account", "match")
    else:
        context.transition_to("Skip: ids mismatch", "mismatch")
```

To also require the same account, add the account ids to the condition and say so.

### 17, 18 — Get account and Suppressed?

Read the new account by id: name, domain, size, tiers, suppression flag, suppression reasons, the rep
field, and the lookalike use-case fields. Node 18 pins the whole `$.result`:

```python
def handler(context):
    res = context.get_input("account") or {}
    records = res.get("records") or []
    if not (res.get("foundAtLeastOne") or records):
        context.transition_to("Skip: lookup error", "lookup_error")      # not found is not clear
        return
    flag = records[0].get(context.get_input("suppression_field"))       # DECLARED field name
    if flag is True or str(flag or "").strip().lower() in ("true", "1", "yes"):
        context.transition_to("Skip: suppressed", "suppressed")
    else:
        context.transition_to("Resolve assignee", "clear")
```

**Skip: suppressed** returns the account's suppression reasons as its detail.

### 19–22 — Assignee and eligibility

Node 19 reads the rep field off the account and returns `assignee_user_id`, or `-`. **The sender is
always the rep field — never the account owner, never a fallback.** Node 21 reads that user's id, name,
email, active flag and booking link. Node 22:

```python
def handler(context):
    route = context.get_input("routing") or {}
    users = (context.get_input("assignee") or {}).get("records") or []
    rep = users[0] if users else {}

    def is_true(v):
        return v is True or str(v or "").strip().lower() in ("true", "1", "yes", "y")

    def usable_link(v):
        v = str(v or "").strip()
        bad = v.lower() in ("", "-", "none", "null", "n/a", "na") or "{{" in v or "/inbound" in v.lower()
        return "" if bad else v

    if is_true(route.get("other_motion")):                      # installer's field names throughout
        context.transition_to("Not enrolled", "not_enrolled")
        return
    if is_true(route.get("use_routed_link")):
        link = usable_link(route.get("routed_link"))
    elif is_true(route.get("use_rep_link")):
        link = usable_link(rep.get("booking_link"))
    else:
        link = ""
    active = rep.get("active") is not False and str(rep.get("active") or "").lower() not in ("false", "0", "no")
    if route.get("resolved_contact_id") and link and rep.get("email") and active:
        context.transition_to("Check in-flight", "eligible")
    else:
        context.transition_to("Not enrolled", "not_enrolled")
```

### 23–26 — In flight and cooldown

Node 23 asks the CRM for this contact **with the in-sequence flag true**, limit 1. Node 25 asks for a
campaign member on **any of this play's campaigns** for the new account, created inside the cooldown
window, limit 1. Nodes 24 and 26 share one shape:

```python
def handler(context):
    import json
    raw = context.get_input("sfdc")
    raw = json.loads(raw) if isinstance(raw, str) else (raw or {})
    success = context.get_input("success")
    preview = str(context.get_input("textPreview") or "").strip().lower()
    if raw.get("error") or raw.get("errorMessage") or success is False:
        context.transition_to("Skip: lookup error", "lookup_error")
        return
    ok = success is True or preview.startswith("no records")
    if not ok and raw and not any(k in raw for k in ("foundAtLeastOne", "records", "totalSize")):
        context.transition_to("Skip: lookup error", "lookup_error")
        return
    if raw.get("foundAtLeastOne") or raw.get("records") or raw.get("totalSize"):
        context.transition_to(SKIP_NODE, HIT)      # 24: "Skip: in flight", "in_flight" · 26: "Skip: account cooldown", "hit"
        return
    context.transition_to(NEXT_NODE, "clear")      # 24: "Check account cooldown" (or "Dry run?") · 26: "Dry run?"
```

The author queried a 30-day window across five campaigns.

### 27 — Dry run?

```python
def handler(context):
    if context.get_input("dry_run") is True:
        context.transition_to("Would enroll", "dry")
    else:
        context.transition_to("Prepare outreach", "live")
```

**Would enroll** is a terminal code node returning `status: would_enroll` with the persona, usage subtype,
contact id, rep email, sequence type and campaign it would use.

### 28–31 — Copy

Node 28 passes the resolved contact id, the rep's user id and email, the sequence type, and — for the
copy rules — the persona, the usage subtype, the old and new company names, the lookalike use cases and
the booking link. The author's node passed a contact id, a sender and a fixed signal label to a separate
generator workflow, which was not read.

**If the installer has a generator, node 29 calls it.** Otherwise node 29 is an LLM node, **prose only**,
after a code node picks the usage claim and the opening angle from the installer's two tables in Step 5
of the skill:

> You are drafting outreach from {rep_name} to {first_name}, who just joined {new_company} as {title}
> after leaving {old_company}, a paying customer of {product_line}.
>
> What you may claim about their history with the product: {usage_claim}. Claim nothing beyond it.
> Open on this angle: {opening_angle}.
> If these lookalike use cases are present, rewrite them as two or three short bullets for the use-case
> email; if the list is empty, leave that section out entirely: {lookalike_use_cases}.
>
> Never criticise {old_company} or {new_company}. Never state anything about {old_company}'s stack that
> is not in this prompt. Close every email with {booking_link}.
>
> Return the fields below and `status: generated` — or `status: error` with a `reason` if you cannot
> follow these rules.

Node 30 reads the output, unwrapping a `result` or `output` key if present, and returns each field as
trimmed text:

| Field | Used for |
|---|---|
| `insight_subject`, `insight_email` | first email |
| `use_case_subject`, `use_case_email` | second email |
| `value_nugget_subject`, `value_nugget_email` | third email |
| `final_email_subject`, `final_email_body` | fourth email |
| `insight_linkedin`, `use_case_linkedin`, `value_nugget_linkedin` | three LinkedIn touches |
| `call_notes_html` | every call task |
| `status`, `reason` | node 31 |

### 32–34 — Sequence and enrollment

Nodes 33a and 33b use the installer's sequencer add action with the sequence id, the rep's email as the
flow owner, the resolved contact id as the CRM prospect id, and one body override per step plus a subject
override on each step that starts a new thread. The author's two layouts, **as an illustration only**:

| Step | Automatic sequence | Manual sequence |
|---|---|---|
| 1 | email — insight (subject) | LinkedIn connect — insight |
| 2 | email — use case (subject) | call — notes |
| 3 | email — value nugget (subject) | email — insight (new subject) |
| 4 | email — final (subject) | LinkedIn message — use case |
| 5 | | call — notes |
| 6 | | email — use case (reply) |
| 7 | | LinkedIn message — value nugget |
| 8 | | call — notes |
| 9 | | email — value nugget (new subject) |
| 10 | | call — notes |
| 11 | | email — final (reply) |
| 12–15 | | call — notes |

Node 34 reads both enrollment results, keeps the one that ran, and sets `enroll_ok` only when the call did
not report failure, the returned sequence id equals the one that branch was given, and an instance id came
back. It returns `expected_sequence_id`, `sequence_id` and `instance_id`.

### 36–37b — Verify

Wait the verify delay, then read the contact's assigned sequences. **Verified only if one of them has the
expected sequence id.** The author waited 60 seconds.

### 38–41b — Campaign member and task queue

Node 38 maps the sequence id to the installer's campaign for that sequence and emits campaign id, contact
id, status `Sent`, final status `Sent`, a qualification-status label and a notes label. **It sets these
fields and no others**, and never emits a blank date or status. Node 40 is the installer's create-or-update
step for campaign members. Node 41 passes contact id, campaign id, campaign member id, rep user id,
sequence id and instance id — the instance id doubles as the external id, since it is unique per
enrollment. The author deliberately left the job-change event id out of the queue call: it belongs to the
person's old contact record and would resolve the entry to the wrong contact.

## Alert path

Error monitoring (code) builds one message; the alert send (tool) posts it to the installer's channel and
mentions the owners they named:

```
*[<play name>] soft-fail* `<reason>`
<mentions>
• node: `<node that failed>`
• workflow: <this workflow's URL, from the id returned at build>
• contact: `<contact id>`  rep: <rep email>
• error: `<first error message found, capped at 500 characters>`
```

The reason is `lookup_error` from Skip: lookup error and `enroll_failed` otherwise. The post-enroll alert
uses `campaign_member_failed` when node 40 returned no campaign member id and `queue_failed` otherwise.
**Build the workflow URL from the id `clay workflows create` returned**, never a fixed URL, so the alert
always links to the workflow that sent it.
