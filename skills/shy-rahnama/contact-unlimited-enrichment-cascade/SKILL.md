---
name: contact-unlimited-enrichment-cascade
description: |
  Build an always-on contact enrichment cascade in Clay — a workflow that takes a person and
  returns them with whatever contact details were missing filled in (company domain, company
  LinkedIn, contact LinkedIn, work email, mobile phone, email verification), each stamped with
  which provider found it. It tries your flat-rate providers first — the ones you pay monthly rather than per
  lookup, like BlitzAPI, Huntr, MoltSets, GetLeads or QuickEnrich, or whatever you hold — and
  only falls through to Clay's credit-billed cascades when every free attempt came back empty.
  Run it again later to add a provider without a rebuild. Use whenever someone asks: build a
  contact enrichment waterfall, set up enrichment for our workspace, find emails and phones
  for this list, fill in missing contact details, use my own API keys before spending Clay
  credits, add a provider to my enrichment waterfall, or stop burning credits on data I
  already pay for. Do NOT use it to look up one person's details right now in conversation,
  to clean or re-verify contact data you already hold, to source net-new people by persona or
  title, to identify who someone is from an email alone, to edit a Clay workflow you built by
  hand, or to write contacts into a CRM or enroll anyone in a sequence. It never asks for or
  stores an API key — credentials live in a Clay connection you create.
category: enrich
personas: [gtm-engineer, revops]
mechanism: workflow
touches: writes-records
keywords: [waterfall]
marketplace_identity_schema: 1
marketplace_slug: contact-unlimited-enrichment-cascade
marketplace_revision: 4
---

Whenever you create or copy a workflow, append `Sourced from marketplace skill: contact-unlimited-enrichment-cascade@4` to its description. Preserve the existing description and do not add the same line twice.

# Contact unlimited enrichment cascade (measure the reach rate, not the call count)

**A cascade's cost is not the sum of its calls — it is set by one field: the contact LinkedIn
URL.** Flat-rate providers bill a monthly subscription and nothing per request, so every
lookup before the credit-billed tier is free and the call count is not the bill. What decides
spend is how often a run *reaches* the paid tier. And most flat-rate email and phone endpoints
key off a person's profile URL and nothing else — so a miss on that one field does not degrade
a run, it routes the entire remainder into the billed cascades.

Two measurements, both from one workspace and neither a promise about yours. Adding a **second**
profile finder after the first one missed took a run from **one field filled to three**, because
the pivot unlocked both email and phone behind it. And moving the phone lookup from a credit-
billed cascade onto a flat-rate provider took the same contact from **28 data credits and 12
action credits in 1m35s to 5 and 6 in 10s** — the paid phone cascade had been the single
largest cost in the graph.

**Which turns the obvious move on its head: buying the pivot is usually the cheapest thing you
can do.** If a credit-billed lookup is the only way to get a profile URL, pay for it — because
it converts the email and phone legs behind it from billed to free. One paid lookup that unlocks
two free ones beats three billed ones, and a cascade that refuses to spend anywhere ends up
spending everywhere.

So this skill is built to measure the reach rate rather than the call count: every step stamps
the record with which provider filled the field, and the cost estimate is that histogram rather
than an arithmetic guess. Everything else follows — several finders on the pivot, a precondition
on every leg that needs it, and provenance that four different outcomes cannot collapse into.

> Do not start a step before the steps above it have their answers. If a declared input is
> missing, ask for it — never assume a default and continue.

> **The build is field-complete. What gets ATTEMPTED is decided at run time, by the skip flags
> on the record — never at build time.** Build a leg for every field every provider they hold
> can reach, and let each record choose. A field is absent from the graph for exactly one
> reason: nothing they have can fill it. "They only want email" is not that reason — they set
> `skip_phone` and `skip_linkedin` on the records where that is true, and change their mind next
> week without a rebuild.

> **This skill is not finished when the plan is agreed, or when the config is written.** It is
> finished when the workflow is built, validated, smoke-tested on a real record, and either
> published or deliberately left as a draft because the installer said so. Writing a config and
> stopping leaves them with a file and no workflow, which is worse than not starting. If you do
> have to stop early — a missing credential, an unanswered gate — say which step you stopped at,
> what remains, and the exact command that resumes it.

## Declared inputs

**Nothing here ships with a value.** Each one is the installer's, not the author's: ask for it,
never substitute a plausible default, and where an answer does not exist say which step becomes
unavailable rather than guessing. Where a default IS defensible it is named below, and using it
means saying so in the output.

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Which providers they hold** | the flat-rate providers they already pay for, and **which plan** — several sell unlimited only on a top tier, so "flat-rate" is a property of the plan, not the vendor | with none, there is no flat-rate tier: every request goes straight to the credit-billed cascade, and the estimate must be quoted at that rate before building, not after |
| **The connection name per provider** | the name they gave that provider's HTTP API account in Clay — **the name only** | that provider's legs are not built, and the skill says which fields lost a tier. **Never ask for the key itself**, and if one is offered, decline and point at the Clay connection |
| **Provider terms** | confirmation their provider agreements permit sending these identities | ask once and record the answer. The workflow sends contact identities to third parties on every row and cannot read a contract |
| **Existing config (extend only)** | the config and `build-state.json` for a cascade this skill already built | absent means a new build. **A graph whose `build-state.json` is gone is not extended** — see Step 1 |

**And these are derived, not asked. Each one has been tried as a question and each is
noise — the answer is shown in the plan at Step 4, where they can change it:**

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **Where finished records are sent** | **nothing — do not ask.** `callback_url` is a per-record input, like the skips. The callback nodes are always built; a record carrying a URL is POSTed there, one without routes to `Done` | so the destination is the caller's, chosen per record, and blank means nothing is sent. Disclose the behaviour at the Step 8 gate; never ask for a destination at build time |
| **Which fields get filled** | **nothing — do not ask.** Derived from what their providers can reach, then governed per record by the skip flags | build every leg the providers support. The plan shows them, and a leg is cut there only when it adds no reach over one ahead of it — **never to switch a field off**, which is a skip flag on a record |
| **Whether the credit-billed tier runs** | **nothing — do not ask.** Every billed leg appears in the plan with its cost, and cutting one is an edit to the plan | every billed leg is built regardless; whether it fires on a record is a skip flag. The plan shows the cost so they can see it, not so they can switch a field off |
| **Leg order within a tier** | **nothing — do not ask.** Ordered by measured hit rate, shown in the plan, correctable there | ordering inside the flat-rate tier saves no money — every call costs the same zero — it only shortens the path to an answer. Say the order was measured, not chosen |

### The input contract — prescribed, and there is nothing to ask

**Never ask where records will arrive, and never ask for a table.** Both entry points are built
every time and neither needs anything from the installer:

- **The webhook** is created by the build. Its schema is the interface below.
- **A Clay table** binds itself later, in Clay's UI, by adding this workflow and choosing
  **`0a Intake`** as the starting node. Clay then maps that table's columns onto these inputs —
  **the column names do not have to match**, that is what the binding screen is for. Binding
  creates the table trigger on its own; the build neither needs nor can create a table.

So a cascade can be built before any table exists, and the same cascade serves any number of
tables later. Asking for a table URL to "inspect the columns" is asking for something the
interface already settles — the columns get mapped onto a fixed shape, not the other way round.

| Input | | |
|---|---|---|
| `contact_name` | **required** | a record without it is rejected at intake |
| `company_name` | **required** | same |
| `contact_email` | optional | supplied means no lookup, and it is kept, never overwritten |
| `contact_linkedin` | optional | the pivot — supplying it is the single biggest cost saving |
| `contact_phone` | optional | as above |
| `skip_email`, `skip_linkedin`, `skip_phone` | optional | **absent means false — do the work.** Present and true switches that field off for that record |
| `want_company_domain`, `want_company_linkedin` | optional | **absent means false — do not go looking.** These are enabling lookups: they fire anyway whenever a leg downstream requires them, and this flag is how you ask for one *as an output* when nothing else needs it |
| `company_domain`, `job_title` | accepted, never required | a domain is the cheapest lever there is; a title sharpens a profile search |
| `source_ref` | accepted | echoed back unchanged so a caller can join the result |
| `callback_url` | accepted | where the finished record is POSTed, if anywhere |

First and last name are **derived** from `contact_name`; a caller supplies one name, not three.

**A value that arrives is never looked up again, and that is a cost guarantee, not just a
courtesy.** Send an email and no email leg runs — not the flat-rate one, not the billed one. The
field resolves as `supplied` and every provider in that chain is skipped entirely. The same holds
for a phone and a LinkedIn URL.

Two consequences worth saying to the installer in these words:

- **Supplying a field is the cheapest thing they can do**, and supplying the contact LinkedIn URL
  is the cheapest of all — it is the pivot, so it also converts the email and phone legs behind it
  from billed to free.
- **A supplied value is never corrected.** If they send a stale email, they get that stale email
  back marked `supplied`. This skill fills gaps; it does not audit what it was given. Re-verifying
  data they already hold is a different job.

**The skips are runtime, not build-time, and that is the point.** Build every leg the providers
can support; let each record decide what it wants. The same workflow then serves a cheap pass
and a full pass without a rebuild, and "what will this cost" becomes a property of the call
rather than of the graph. Never bake a field being off into the build — that is a rebuild every
time somebody changes their mind.

**Absent defaults to false on purpose, and the two families read the same way for different
reasons.** A `skip_` flag is an opt-OUT on a field the cascade exists to fill, so absent means do
the work — a caller who has never heard of these gets the full cascade, and a flag defaulting to
"skip" would silently return empty fields to anyone who did not know to set it.

A `want_` flag is an opt-IN on a field nobody asks for on its own. A company domain exists so the
email leg can run; it fires whenever something downstream needs it, flag or no flag. The flag only
answers a different question — *"fetch one even though nothing needs it, because I want it in the
output"* — and it defaults off because the other polarity would fire it on every record where the
field happened to be missing, adding cost nobody asked for. A field with no flag at all cannot be
requested, only inherited, which is the gap these close.

### The output contract — every key, named

The same shape every time, so a consumer written against one cascade works against all of them.
`record_json` carries exactly this and nothing else; it is the deliverable, and the request
bodies and gate flags the record uses in transit are **not** in it.

**Six keys are guaranteed on every record**, present even when empty, so a consumer never has
to test whether a key exists before reading it. **Blank means skipped or not found — that is a
value, not an absence.** Everything the caller sent passes through unchanged alongside them.

| Guaranteed | |
|---|---|
| `contact_name`, `company_name` | as supplied, never enriched, never overwritten |
| `contact_email`, `contact_linkedin`, `contact_phone` | filled, or blank |
| `contact_email_verified` | `"true"` / `"false"` |

Then everything else, which is detail rather than contract:

| Key | | |
|---|---|---|
| `first_name`, `last_name`, `job_title` | derived or passed through | not part of the guarantee |
| `company_domain`, `company_linkedin` | filled when something needed them, or when asked for with `want_company_domain` / `want_company_linkedin` | enabling lookups that can also be requested; `not_needed` when neither applied |
| `contact_email_verify_status` | the verifier's verdict, lowercased | `not_checked` when no verification leg ran |
| **`<field>_source`** | one per field the cascade can fill | the closed six below. **Nothing else carries a source**, so a source key existing tells you a leg for that field exists |
| `contact_email_verified_only` | the address, or **blank** | **this is what downstream automation should consume.** Blank unless a verifier actually passed it |
| `contact_email_domain_match` | `"true"` / `"false"` / `"unknown"` | whether the address sits on the company's own domain |
| `filled_fields`, `filled_count` | what this run actually added | excludes anything that arrived supplied |
| `captured_fields` | extra data a provider returned beyond its own field | a comma list of the keys, which are present alongside |
| the five flags | echoed back | so a `skipped` or `not_needed` source is explainable without the original request |
| `source_ref` | echoed back unchanged | the caller's own row id, for joining |
| `callback_url`, `has_callback` | where it was sent, if anywhere | |

**`<field>_source` is one of six, and they are not interchangeable:**

| | |
|---|---|
| `supplied` | it arrived populated; nothing was looked up |
| *a provider's label* | that provider found it |
| `not_found` | a leg ran and came back empty |
| `skipped` | the caller switched the field off |
| `blocked_missing_input` | an input the leg needed never arrived, so it never ran |
| `not_needed` | an enabling lookup nothing downstream needed and nobody requested; it cost nothing |

Four of those mean "no value" and they mean completely different things. **Report them
separately** — collapsing them makes every provider hit rate meaningless, which is the only
reason to run a waterfall instead of one call.

**If an answer sheet is present beside this skill, load it and ask only for what it does not
cover.** A partial sheet is normal; a value it is missing gets asked for on its own rather than
restarting the interview. **Say which values came from the sheet** before using them — a sheet
applied silently is a wrong field nobody catches. **If there is no sheet, say nothing about
sheets** — the check is a file lookup, not a question, so run the interview as though the
feature did not exist rather than reporting an absence. At delivery, offer to save the answers
back (identifiers only — never a token or a password), private and never published, and phrase
the offer so it explains itself: *"want me to save your answers to a file, so the next person
on your team doesn't have to answer these again?"*

## What this skill touches

- **Reads** — your workspace's available Clay functions and actions; each provider's published
  API documentation; and the names of the HTTP API accounts you created. **It reads no table.**
  The interface is fixed, and a table's columns are mapped onto it later, in Clay's UI.
- **Writes** — three things, and they are different in kind. It **creates and rewires workflow
  nodes** in your Clay workspace. The workflow it builds then **writes enriched contact values
  back onto the rows of the table you bound to it**. And where you supply a callback URL it
  **POSTs each finished record, email and phone included, to that URL**. It deletes nodes only
  for legs you removed from the config, only when you pass `--allow-prune`, and it reports them
  first.
- **Never** — asks for, receives, stores or transmits an API key; puts a credential in node
  code, a config file or a header literal; overwrites a contact value you supplied; blanks or
  clears a populated field; sends your data anywhere but the providers you connected and the
  `callback_url` carried on each record; contacts anyone; or writes to a CRM or a sending tool.
- **Halts** — Step 4 other, Step 6 write-approval, Step 8 spend-approval, Step 8 write-approval.
  Step 4 is the plan gate: the cascade is agreed before any connection is set up or any node made.

## Representative output

### Provider capability map

Derived from each provider's own spec at Step 3, and shown back before anything is built.
Placeholder providers; the shape is the contract.

| Provider | Fills | Needs | Lands as |
|---|---|---|---|
| flat-rate A | contact LinkedIn | name + company | finder, **before the pivot** |
| flat-rate A | work email · mobile phone | contact LinkedIn | primary, after the pivot |
| flat-rate B | work email | name + domain | second email leg, still free |
| flat-rate B | contact LinkedIn | name + domain | second finder on the pivot |
| native action | email verification | an email address | reporting leg, last |
| Clay cascade | work email · mobile phone | name + domain | **fallback, credit-billed** |

### Proposed cascade plan

What Step 4 puts in front of them, before any connection is created. Placeholder providers.

```
1  company domain      Clay cascade          needs company name           ~1 credit   ENABLER
2  contact LinkedIn    flat-rate A           needs name + company         free
3  contact LinkedIn    Clay cascade          needs name + domain          ~2 credits  ENABLER
4  work email          flat-rate A           needs contact LinkedIn       free
5  work email          Clay cascade          needs name + domain          ~1.1 credits  <- billed
6  mobile phone        flat-rate A           needs contact LinkedIn       free
7  mobile phone        Clay cascade          needs contact LinkedIn       ~9.9 credits  <- billed
8  email verification  native action         needs an email               ~0.1 credits  <- billed

Why leg 3 is billed on purpose: your flat-rate providers can only find a profile URL from name
+ company, which fails on about a third of records. When it does, paying ~2 credits for the URL
turns legs 4 and 6 from billed back into free — instead of ~1.1 for email and ~9.9 for phone.
It pays for itself on any record that wants a phone number.

Every leg above gets built, leg 7 included — the dearest call on the platform. That is not a
commitment to spend it: it fires only on a record that wants a phone and whose free lookup
missed, and `skip_phone` stops it entirely. **Nothing is switched off at build time**, so
changing your mind about phone next week is a flag on a record, not a rebuild.

Enablers have no opt-out either: they run when something downstream needs them and not
otherwise. A record with every skip set costs nothing at all.

Not filled:  company LinkedIn — no connected provider offers it, and nothing needs it as input.
Left out:    flat-rate B's phone endpoint — same input and position as leg 6, no added reach.
You need to create: 1 Clay HTTP API account (flat-rate A).
```

### Enriched record

| source_ref | contact_linkedin | linkedin source | contact_email | email source | contact_phone | phone source | verified |
|---|---|---|---|---|---|---|---|
| row-1041 | /in/a-lovelace | flat-rate A | ada@engines.example | flat-rate A | +1555…0142 | flat-rate A | true |
| row-1042 | /in/c-babbage | flat-rate B | charles@engines.example | Clay cascade | *(none)* | not_found | true |
| row-1043 | *(supplied)* | supplied | grace@navy.example | supplied | *(none)* | skipped | not_checked |
| row-1044 | /in/g-hopper | Clay cascade | grace@navy.example | flat-rate A | +1555…0198 | flat-rate A | true |

### Reach-rate report

```
48 records · 46 enriched · 2 rejected at intake (no company name)

contact_linkedin   flat-rate A 31 · flat-rate B 9 · supplied 4 · not_found 2
contact_email      flat-rate A 27 · flat-rate B 6 · Clay cascade 7 · supplied 3 · not_found 3
contact_phone      flat-rate A 19 · skipped 22 · blocked_missing_input 2 · not_found 3
company_domain     supplied 44 · Clay cascade 1 · not_needed 1   (enabler, no opt-out)

Reached the credit-billed tier: 7 of 46 (15%) · 7 paid calls · 0 on phone — skip_phone was set
on every record that got that far, so the dearest leg in the graph never fired once.
Paid enabling lookups: 6 profile URLs at ~2 credits, which kept 6 phone lookups off the billed
cascade — a net saving of roughly 47 credits.
Email addresses on a domain other than the company's: 1 — verified true, and suspect anyway.
```

## Files in this skill

| | |
|---|---|
| `references/provider-adapters.md` | How to turn a provider's API spec into legs: find the spec, classify each endpoint by what it produces and requires, place it, verify it. Also the guided connection setup. **Read before writing a leg for any provider.** |
| `references/cascade-config.md` | The config schema — every top-level key, every leg field, the four provider types, the record contract, and what the cascade emits. |
| `references/graph-shape.md` | The four-node leg and why it is shaped that way, plus every platform trap the build encodes. Read it before changing the graph or debugging a run that completes and returns nothing. |
| `scripts/build_cascade.py` | The build. Reads a config, creates and rewires the graph, idempotently. `--dry-run` proves a config without creating anything. |
| `scripts/cascade_lib.py` | The build's helpers: state file, provider name resolution, `ensure_node`, pin and edge wiring with read-back verification. Edited only when changing how the build talks to Clay. |
| `scripts/cascade-config.example.json` | A complete config at placeholder values, covering all four provider types. Start here. |
| `scripts/test_codegen.py` | Generates every code node the build would write, parses it, and runs the handlers against a fake context. No Clay, no credentials, no network, no cost. |

## Step 0 — State the posture, then confirm the platform

Say this before anything else, in one short message: **this creates nodes in your Clay
workspace; the workflow it builds writes enriched values back onto the rows of any table you
later bind to it; and any record that arrives carrying a `callback_url` gets POSTed there. It
never asks for or stores an API key.** And say plainly that **no table is needed to build it** —
one gets bound afterwards, whenever they like.

Then say where the cost lives, because that is a design property and not a footnote: calls to
your flat-rate providers go through Clay's generic HTTP action and cost **no Clay credits** —
they bill against subscriptions you already pay for. Clay's own cascades bill credits per call.
Everything the agent works out in conversation is free.

```
clay whoami; echo "exit=$?"
```

`0` and a user id means go. Anything else: **say which component is wrong, which version is
required, and the one command that fixes it — then stop.** Do not install, upgrade or fetch
anything to repair it. An environment the installer has to fix is not this skill's job, and a
skill that starts rebuilding its own prerequisites reads as a hang.

## Step 1 — Route on what you have: a new build, or a provider to add

**The opening request usually settles this — read it before asking.** "Build me a cascade" is a
new build; "add this provider to my cascade" is an extend. Ask only when it is genuinely
ambiguous, and branch on the request rather than on what a lookup returns, so two installers with
the same inputs take the same path:

- **No existing config** → new build. Continue to Step 2.
- **A config and its `build-state.json`** → adding a provider. Skip to Step 3, derive the new
  provider, append its legs, and re-run the same build. It is idempotent: everything already
  built is a no-op and only the new legs are created. There is no separate upgrade path.
- **A workflow but no `build-state.json`** → **stop.** That file is the only record of which
  Clay node is which. Say so, and offer either to restore it or to build fresh into a new
  workflow. Never guess at an existing graph's nodes, and never create a second workflow
  alongside a live one — the build refuses this for you.

## Step 2 — Ask only what nothing can derive, which is very little

**Almost nothing here is an interview.** The interface is prescribed, the fields follow from what
their providers can reach, and the ordering follows from measured hit rates. Everything with a
shape is derived and then shown in the plan for correction — which is a better question than an
abstract one, because they are correcting a document rather than guessing at a form.

**Do not ask any of these. Each has been tried and each is noise:**

| Do not ask | Because |
|---|---|
| where records arrive | both entry points are always built; a table binds itself later |
| for a table, or its URL, or its columns | the interface is fixed; columns map onto it at bind time |
| which fields to fill | it follows from what their providers can reach, and the skip flags decide per record |
| whether the billed tier may run | every billed leg is in the plan with its cost and gets built regardless; whether it fires on a record is a skip flag |
| which provider goes first | ordered by measured hit rate, shown in the plan |
| where finished records should go | `callback_url` is a per-record input; the nodes are always built |
| for an API key, ever | it lives in a Clay connection |

**One thing genuinely needs asking here, because no amount of reading produces it:**

> **Do their provider agreements permit sending these contact identities?** Ask once, record the
> answer. The workflow sends contact details to third parties on every row and cannot read a
> contract.

That is the whole of Step 2, and it is short by design rather than by omission. Everything else
someone might reach for — the destination, the fields, the ordering, the columns — is either
fixed by the interface, derived from what they hold, or decided per record at run time.

Then go to Step 3 and ask which providers they hold. That is the substantive question, and the
last one before they get a plan.

## Step 3 — Ask which providers they hold, then derive what each can actually do

**Do not assume a provider's shape and do not ship a list of known ones.** Ask what they pay
for, then follow `references/provider-adapters.md` for each: find the spec, enumerate the
endpoints, classify each by what it produces and what it requires, and place it.

The placement rule is where the value is, and it is easy to miss: an endpoint needing a profile
URL lands after the finders, but **an endpoint that works from name + company can also be a
finder for the pivot itself** — and the pivot gates everything behind it. One provider
legitimately produces four or five legs in different positions. That is the point.

Then show the capability map and invite corrections. **Name a provider that turns out to add
nothing** rather than wiring it in for completeness: a leg that can never fire is a node to
maintain and a line in the graph that misleads the next reader.

If a provider's documentation cannot be read, **say so and ask them to paste the endpoint list
or spec.** Never infer an endpoint path — a fabricated URL builds a leg that fails silently on
every row while the graph looks correct.

### Then close the input gaps — this is where the money is

**A free endpoint is only free if you can satisfy its inputs.** Most flat-rate email and phone
endpoints want a profile URL and nothing else, so "we have a free email provider" and "email is
free" are different claims. Before pricing anything, walk every free-tier endpoint's required
inputs and solve for each one, in this order:

1. **Is it always supplied?** Then there is no gap.
2. **Can a free provider produce it?** Check *the same provider first* — a vendor whose email
   endpoint needs a profile URL very often sells a finder for that profile URL too, on the same
   flat-rate plan. Then check every other free provider. This is the outcome most often missed,
   because the natural reading of a capability map is "this provider does email" rather than
   "this provider can also produce the thing its own email endpoint requires".
3. **If no free provider can, use a credit-billed one — and show why that is the cheap move.**
   This is not a concession. One paid lookup that resolves a profile URL converts the email and
   phone legs behind it from billed to free. **Put the arithmetic in the plan**: one lookup at
   roughly N credits, replacing the billed email and phone cascades at roughly X and Y. If the
   numbers do not favour it, say that too and leave the field unreachable.
4. **If nothing can produce it, say which fields are unreachable** — plainly, at the plan.
   Building legs that will always report `blocked_missing_input` is worse than not building
   them: it looks like coverage and delivers nothing.

An enabling lookup is a leg like any other, placed before the legs that need it. It carries an
**opt-IN** flag rather than an opt-out: nobody asks for a company domain for its own sake, so it
runs when something downstream needs it, runs when a caller explicitly sets `want_company_domain`,
and reports `not_needed` otherwise. That is what stops it spending on a record where every field
it feeds was skipped — and it is also why a field that a provider can reach for free is still
worth a leg, because there is now a way to ask for it.

## Step 4 — Propose the cascade plan, get it approved, then collect the connection names

**Nothing is built and no credential is set up until they have seen the whole cascade and said
yes.** A capability map says what each provider *could* do; the plan says what you intend to
actually build, in order. They are different documents and only the second is approvable.

Show one plan, in their words, not in config syntax:

- **The cascade in order** — every leg, which provider fills it, what it needs to run, and
  where the free tier ends and the credit-billed tier begins.
- **What each field costs when it falls all the way through**, read from their workspace.
- **What will NOT be filled** — and there is exactly one reason: no provider they hold can
  reach it. Say which, plainly, rather than letting them find out from the output. **Never
  present a field as off because they said they did not want it** — that is a skip flag on a
  record, and the leg gets built regardless.
- **Which providers you are deliberately leaving out, and why** — an endpoint that duplicates
  one already ahead of it, or one whose input nothing upstream produces.
- **The connections they will need to create**, one line each, so the setup cost is visible
  before they agree rather than after.

Then stop and wait. **Ask them to change the plan, not to approve it** — "anything wrong with
this order, or any provider you'd rather not use for a field?" invites the correction that a
bare yes/no does not. Rework and re-show as many times as it takes; this is the cheapest point
in the whole run to change your mind, and the last one before their time gets spent.

**Only once the plan is agreed, walk them through the connections it needs.** There is no CLI
for this — checked: nothing in Clay's workflow, table, function, routine, webhook or API-key
surfaces manages provider connections — so it is theirs, in Clay's UI, and you learn only a
name. Follow the connection section of `references/provider-adapters.md`.

**Ask whether they already have one before asking them to build one**, and tell them where to
look: **Settings → Connections** (profile picture top-right → Settings → Connections), **and tell
them to filter by account type = user-added** — unfiltered, that list is dominated by Clay's own
built-in integrations and theirs is buried. Ask for the name **as it appears there**, not from
memory — it is workspace-wide shared state and a spelling you cannot verify.

**If they do not have one, walk the actual path** — `references/provider-adapters.md` has the six
steps: **Settings → Connections → Create** → search `http` → **HTTP API (Headers)** → name it
after the provider (`blitz-api`, `huntr`) → set the header values. **Do not send them into a
table to do it** — that route exists, but no table is needed and this cascade does not have one.

**Give them the exact header, not a generic instruction.** You read the provider's spec at
Step 3, so you already know whether it wants `x-api-key: <key>` or `Authorization: Bearer <key>`
or something else — and those are not interchangeable; a provider handed the wrong one answers as
though no auth was sent. Say it per provider. "Put the auth header in it" is an instruction they
have to go research; "add header `x-api-key` with your key as the value" is one they can follow.
If the provider needs a token exchange rather than a static header, Clay has a different account
type for that and the reference says which.

**Then confirm the name by reading it back.** Ask them to paste it exactly as Clay displays it,
and repeat it to them against the leg it will authenticate — because of this:

> **Clay does not validate the account name.** Measured: a tool node naming an HTTP API account
> that does not exist is created without complaint, and the graph still validates. A typo is
> invisible until something actually runs, and Clay is documented to auto-pick an account when
> none is named — so a name that fails to match may fall through to a *different provider's*
> credential rather than erroring. There is no CLI surface to list accounts, so this cannot be
> checked before the build. **Confirm it at the smoke test in Step 7, and say out loud that it
> is unverified until then.**

Setting up a connection is real work for them. Asking for one before the plan is agreed means
some of that work is for legs that get cut, which is why the order of this step matters.

A provider that never comes back with an account name is a provider whose legs are not built;
say which field lost a tier rather than building a leg that cannot authenticate.

**Never ask for a key in chat. If one is offered, decline and point back at the Clay
connection.** Node source is stored by Clay and readable by anyone who can open the workflow.

## Step 5 — Write the config, then prove it without building anything

Write the legs in placement order per `references/cascade-config.md`, starting from
`scripts/cascade-config.example.json`. Show the resulting cascade as an ordered list so they can
see what runs before what, and where the free tier ends and the billed tier begins.

Then two checks, both free and both offline of Clay's billing:

```
python3 scripts/test_codegen.py <your config>
python3 scripts/build_cascade.py --config <your config> --dry-run
```

The first generates every code node the build would write, parses it, and runs the handlers
against a fake context — no Clay, no credentials, no network. The second resolves every provider
name against the live workspace and validates every declared input against the provider's real
schema, **creating nothing**. A name that does not resolve fails loudly, listing what the
workspace does have.

Do not skip either. A parameter name guessed wrong fails at run time, which is *after* the graph
exists, and a wrong response path reads as "not found" forever.

## Step 6 — Build the graph, without publishing it

Say exactly what is about to happen before running it: the node count and their roles in
dependency order, both triggers, and — if this is an extend — which legs are new. If the build
reports nodes belonging to legs no longer in the config, **read that list out and confirm the
legs were removed on purpose rather than renamed**; pruning is the only step that destroys
anything, and a renamed key looks identical to a removed one from the inside.

Also price the smoke test Step 7 will run, so one gate covers both and there is not a second
one for a handful of rows.

The node shape this creates, and the platform traps it works around, are in
`references/graph-shape.md`. Read it before hand-editing anything the build made: several of
those traps fail silently, and one of them produces a run that never finishes rather than one
that errors.

**This writes to their workspace. Say so, in the word, and wait.** Then:

```
python3 scripts/build_cascade.py --config <your config>
```

It leaves a **draft**. Nothing is live yet, and it says so.

## Step 7 — Validate, then run one real record

```
clay workflows graph validate <the workflow it created>
```

Then two runs, and **read the output rather than the status**. **Gate on non-empty values, never
on completion** — a provider call can succeed and return nothing, and a wrong response path
returns null while reporting success.

**Run A — nothing supplied.** Everything has to be found, so this exercises the whole cascade:

```
clay workflows runs test <workflowId> --inputs '{"contact_name":"Kareem Amin","company_name":"Clay"}'
clay workflows runs get <workflowId> <runId>
```

Use a contact whose answers the installer can eyeball. **Kareem Amin at Clay is the default**
because anyone building this has a Clay account and can check the result in seconds; swap in
someone of theirs if they would rather. `runs test` fires the **draft**, which is what you want
before publishing — and it returns immediately without polling, so fetch the run separately.

**Run B — one field supplied.** Take the contact LinkedIn URL that run A returned and send it
back in, with everything else identical:

```
clay workflows runs test <workflowId> --inputs '{"contact_name":"Kareem Amin","company_name":"Clay","contact_linkedin":"<the URL run A found>"}'
```

This is the one case that proves the no-re-enrichment guarantee, and it is worth doing
deliberately rather than trusting the code: `contact_linkedin_source` must read `supplied`, **no
LinkedIn leg may have run at all**, and the email and phone legs must still fire using the URL
that was handed to them. A build that re-looks-up a supplied value works perfectly and quietly
charges for every field the caller already had.

Reusing run A's output rather than a hardcoded URL also means the fixture cannot rot.

Six things to confirm, because each is a distinct failure that looks like another:

1. A field that arrived populated reads `supplied`, and **no leg for it ran** — run B above.
   Reading `supplied` alone is not enough; that could be a label on a lookup that happened anyway.
2. A flat-rate hit is attributed to **that provider**, not to `supplied` — if a later leg on the
   same field relabels an earlier leg's find, provider hit rates become unmeasurable.
3. A miss on the pivot makes the legs behind it read `blocked_missing_input`, not `not_found`.
4. A record sent with `skip_phone` set reads `skipped` on phone AND no phone leg ran — which is
   what proves the flag governs spend rather than just labelling the output.
5. **A record with a skip set costs nothing on that field**, and an enabler nobody needs reads
   `not_needed` rather than firing. Send a second record with every skip set and confirm no leg
   ran — that is the cheapest proof that the opt-outs actually govern spend.
6. **Every HTTP leg actually authenticated.** This is the first moment a wrong connection name
   can surface, because nothing before it can check one. A `401` or `403` in the response means
   the account name does not match anything; an unexpectedly empty result from a provider you
   expect to hit means the same thing until you have ruled it out. Read the raw response, not
   the resolved field.

Fix pins here, where it is cheap. **A test run fires the draft; a webhook or a bound table fires
the published version** — so nothing you see here is evidence about live traffic yet.

## Step 8 — Publish and go live

One message, then stop and wait. It carries four things, and the last two are the ones a
cost-only gate would miss:

1. **The credit estimate, from the measured reach rate** — how many of the sample rows reached a
   billed leg, and the per-call cost read from *their* workspace. **Quote it as a unit rate —
   per record, and per hundred records — and apply a volume only if they offer one.** Volume is
   the one number here that nothing can derive, and asking for it just to produce a headline
   figure is a question the build does not need. Say it is a rate measured on a handful of rows,
   not a forecast.
2. **The zero that is not a zero** — the flat-rate calls cost no Clay credits, and they are not
   free: they bill against their own subscriptions, and they send each person's name, company and
   identifiers to those providers on every row.
3. **The write, in the word** — this writes these named fields back onto each row of any table
   later bound to it, and returns them on the webhook path. That is a mutation, not a read. It
   sets only those fields and touches nothing else. Say it conditionally: no table need exist
   yet, and presupposing one invites a question the build does not need answered.
4. **The destination, which the caller sets per record** — any record carrying a `callback_url`
   is POSTed there, email and phone included; one without it is not sent anywhere. Disclose that
   this is how it works rather than naming a URL, because there is no single destination — and
   nothing goes anywhere else.

On yes: `--publish`, enable the triggers, and say plainly that **a standing trigger is a
standing cost** — every row that arrives from now on runs the cascade unattended.

## Step 9 — Deliver, and say what was not covered

The reach-rate report above: source histogram per field, records rejected at intake, fields that
never resolved, and actual spend against the estimate. Then three things worth saying out loud:

- **A provider that never produced a hit is a leg to remove.** Name it.
- **A field that read `blocked_missing_input` more often than `not_found`** is a pivot problem,
  not a provider problem — the answer is another finder, not another email source.
- **`verified: true` with a domain mismatch is suspect, not clean.** Say how many.

### Then tell them how to actually use it — all three ways

**This is the step the build deliberately does not do, so it is the one most likely to be left
out.** A cascade nobody knows how to call is not finished. There are three entry points and they
suit different jobs; name all three, then give them the webhook URL and the workflow link.

**1. From a Clay table** — the common case, for a list you already hold.

> Open the table, add this workflow as an enrichment, and choose **`0a Intake`** as the starting
> node. Map your columns onto its inputs — **your column names do not have to match**. Binding
> creates the table trigger by itself, nothing needs rebuilding, and you can bind as many tables
> as you like to the same cascade. Enriched values are written back onto the row.

**2. From another Clay workflow** — for a pipeline, where enrichment is one stage of several.

> POST to the webhook from an HTTP node in the calling workflow, and set `callback_url` to that
> workflow's own webhook so the finished record comes back to it. That is the pattern to use when
> a later stage — scoring, copywriting, routing — needs a contactable person before it can run.
> Pass `source_ref` so the returning record can be matched to the one that left.

**3. From outside Clay** — a script, a job, another system.

> POST the interface as JSON to the webhook URL. Either supply a `callback_url` and receive the
> finished record there, or omit it and read the result from wherever the run lands. `source_ref`
> is echoed back unchanged for joining.
>
> ```
> curl -X POST <webhook URL> -H 'Content-Type: application/json' \
>   -d '{"contact_name":"Ada Lovelace","company_name":"Analytical Engines",
>        "skip_phone":"true","source_ref":"row-1041","callback_url":"https://your.app/hook"}'
> ```

**Say the two things that decide cost, whichever path they pick:** send any field they already
have and its lookups are skipped entirely, and set `skip_email` / `skip_linkedin` / `skip_phone`
per record for anything they do not want — neither needs a rebuild, and phone is the dearest
field on the platform.

Then offer the answer sheet.

## What this skill does not claim

- The two credit figures in the opening claim were measured on **one contact, in one workspace,
  on two dates**. They show that the paid phone cascade dominated that graph's cost. They are
  not a benchmark and not a yield you should expect.
- No hit rate is claimed for any provider. The whole point of the source histogram is that hit
  rates are a property of the installer's data and have to be measured, not quoted.
- Nothing is claimed about a provider's coverage, accuracy, or geography. Several flat-rate
  phone products are region-limited, which shows up as fall-through to the billed tier rather
  than as an error.
- Verification proves a mailbox is deliverable. It does **not** prove the address belongs to the
  person, which is why the domain comparison is reported separately and why a mismatch is
  flagged rather than resolved.
- The skill has not been run against every provider it names in its description. The derivation
  procedure is general; a specific provider's spec may be unreadable or may have changed.
- It does not measure latency. Find-email lookups are known to be asymmetric — a miss can take
  far longer than a hit — so a batch's wall time is not the per-record time times the rows.

## What good looks like

A good run ends with **every filled field naming the provider that filled it**, and with the
four non-hit outcomes distinguishable: `supplied`, `skipped`, `blocked_missing_input` and
`not_found` are four different facts, and a run that reports them as one is a failed run even if
every field is populated — the numbers it produces cannot be acted on.

The reach-rate report should let a reader see the *shape of what is missing*: how many records
never reached a tier at all, which field blocked the rest, and what it cost. A good report often
recommends removing a leg.

A thin run looks different and should be said out loud rather than dressed up: most fields
`not_found` with the pivot empty means one missing finder is starving the whole cascade, and the
fix is upstream. Most fields `blocked_missing_input` means a precondition is never satisfied —
usually a company domain the caller was expected to supply. A run where everything reads
`supplied` did no work and cost nothing, which is a correct outcome and worth stating plainly.

A failed run is one that returns values with no provenance, or that reports a credit estimate
without naming the write and the callback. Both are unreviewable.

## Rules

- **NEVER ask for, accept, or handle an API key.** Credentials live in a Clay HTTP API account
  the installer creates; a leg references it by name. There is no code path that takes a key,
  and the build refuses a credential-shaped config field.
- **ALWAYS set the connection name explicitly.** A production build was observed picking up a
  workspace's only HTTP API account without being told to. That is undocumented and unconfirmed,
  but naming the account costs nothing and removes the question.
- **ALWAYS have them read the connection name off Settings → Connections, filtered to
  user-added,** rather than recall it. There is no way to check it before a row runs.
- **NEVER report a connection as working before a leg using it has run.** Clay accepts an
  account name that matches nothing, so "configured" and "authenticating" are different claims
  and only the smoke test can make the second one.
- **Say which things were checked and which were taken on trust.** Clay functions and actions
  are resolved by name against the live workspace and their inputs validated against real
  schemas — those are verified. HTTP connection names cannot be listed or checked at all. An
  installer who thinks both were verified will not look at the one that was not.
- **NEVER ask for a table, or for column names.** The interface is prescribed; a table binds
  onto it later in Clay's UI and creates its own trigger. A cascade can be built before any
  table exists, and one cascade serves many tables.
- **NEVER ask anyone to set up a connection before the plan is agreed.** Creating an HTTP API
  account is their work, and work spent on a leg that gets cut is work wasted.
- **NEVER decide at build time what a caller can decide per record.** Build a leg for every
  field every provider they hold can reach. The ONLY reason a field has no leg is that nothing
  they have can fill it. The skip flags decide what is attempted, per record, at run time —
  baking a field being off into the graph means a rebuild the moment somebody changes their mind.
- **An enabling lookup that is worth paying for IS the cheap option.** Do not refuse to spend on
  a profile URL and then let the email and phone legs fall through to the billed cascades. Show
  the arithmetic and let the installer decide.
- **NEVER stop at the config.** The run is finished when the workflow is built, validated and
  smoke-tested. Stopping earlier leaves a file and no workflow.
- **NEVER build from a plan nobody saw.** The capability map is what a provider could do; the
  plan is what you intend to build. Only the second is approvable, and it is approved in their
  words rather than in config syntax.
- **NEVER overwrite a supplied value, and never blank a populated field.** This skill fills gaps.
- **NEVER POST a record anywhere but the `callback_url` that record itself carried.** The
  installer names no destination; each record chooses, and a blank field means nothing is sent.
- **The credit estimate is computed on rows that REACH the paid tier, not rows that get an
  answer.** A miss can still bill; at least one phone waterfall charges when it finds nothing.
  Estimating on hits is the most likely way this comes in low.
- **Name the job, not the vendor, in every step.** Which providers are in play is a declared
  input: ask which ones they hold, then read each one's spec.
- **Read the documentation before probing, and verify with a probe before relying on it.** One
  provider's published request property was simply wrong; the live API named a different one.
- **Judgment lives in a code node, never an LLM node.** Every decision here is deterministic.
- **Confirm node command syntax against the installed CLI** (`clay workflows nodes --help`)
  before any node operation. Never a hardcoded command form.
- **Resolve a Clay action by the (package id, action key) PAIR**, never the key alone.
- **While inspecting an existing workflow, stay read-only**: list, graph get, graph validate,
  nodes get, diagram. Never a run, never a node test — those execute and spend, and a node test
  reads like a read.
- **Publishing is a separate, gated act.** A build leaves a draft; a test fires the draft and a
  webhook fires the published version.

## Worked example

*Placeholder names throughout.*

An installer pays for two flat-rate providers and wants a cascade. They have no Clay table yet;
that turns out not to matter.

**Step 0** states the posture: nodes get created, enriched values get written back onto any table
bound later, records carrying a `callback_url` get POSTed there, no API key is ever handled — and
no table is needed to build any of it. `clay whoami` returns cleanly.

**Step 1** routes: no existing config, so a new build.

**Step 2** asks one question — whether their provider agreements permit sending contact
identities. They confirm. Nothing else is asked, because nothing else changes what gets built.

**Step 3** asks which providers they hold and on what plan, then reads both specs. Provider A does
email and phone, both keyed off a profile URL, and *also* resolves a profile URL from name +
company. Provider B does email from name + domain, and a profile URL too. Closing the input gaps
is what the map makes obvious: **two legs land on the pivot before any email leg runs**, because
without a profile URL provider A's two best endpoints cannot fire at all. Their workspace also has
a billed cascade that can resolve a profile URL from name + domain, which matters in a moment.

**Step 4** puts the plan in front of them: nine legs in order, the free tiers, the billed email
and phone fallbacks, the billed profile-URL enabler, and a note that company LinkedIn will not be
filled because nothing they hold offers it. The arithmetic for the enabler is shown — ~2 credits
for a profile URL, against ~1.1 for the billed email and ~9.9 for the billed phone it displaces.
They cut provider B's email leg, which sits behind provider A at the same cost and adds no reach,
taking it to eight. **Nothing is cut for being unwanted** — the billed phone leg stays, because a
record that does not want a phone sends `skip_phone` rather than needing a different graph. Only
then are they asked to create the two Clay HTTP API (Headers) accounts; they do, and name them.

**Step 5** writes the config and runs both free checks. The dry run rejects the first version —
the billed phone cascade requires a contact name and a company name the config had not mapped,
caught before anything was created. Fixed, both pass.

**Step 6** builds 34 nodes as a draft, publishing nothing.

**Step 7** runs the two checks. Run A sends Kareem Amin at Clay with nothing else: the pivot
resolves via provider A, then email and phone via provider A, verification deliverable with a
matching domain. Run B sends the same contact with the LinkedIn URL run A found — it reads
`supplied`, **no LinkedIn leg runs at all**, and email and phone still fire off the supplied URL.
Then a ten-record sample, one of which carries `skip_phone`: phone reads `skipped` and neither
phone leg fires. Every HTTP leg's raw response is checked for a `401`, since a wrong connection
name surfaces nowhere earlier.

**Step 8** reports: 3 of the 12 records run so far reached a billed leg, so roughly 0.25 paid calls
per record — about 25 credits per hundred at their rates. No total is quoted, because nobody has
said how many records are coming. The flat-rate calls cost no Clay credits but send every
contact's identifiers to both providers on every row; six named fields are written back onto each
row of any table they later bind; and any record carrying a `callback_url` is POSTed there with
email and phone included. They approve. Published.

**Step 9**, over their first 48 records: 46 enriched, 2 rejected at intake for no company name. The pivot
resolved 40 times — 31 on provider A, 9 on provider B, which is the argument for having kept
both. Seven records fell through to the billed email cascade. 22 records carried `skip_phone`, so
the dearest leg in the graph never ran on them. One address verified true on a domain that was not
the company's, flagged as suspect. The recommendation: provider B never once won an email, only
the pivot — so drop its email leg and keep its finder.

Then the handoff, all three ways: bind a table by adding this workflow to it and choosing
`0a Intake` as the starting node; or call the webhook from another Clay workflow with
`callback_url` pointed back at itself; or POST to the webhook from outside Clay. With the
reminder that sending a field they already have skips its lookups, and the skip flags cost
nothing to change.
