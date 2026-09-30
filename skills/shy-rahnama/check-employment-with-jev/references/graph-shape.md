# The two workflows, step by step, and the traps they avoid

Built by `scripts/build_workflow.py`. Node ids go into `build-state.json` (in this skill's state
folder, computed from the Clay workspace) the moment each exists; a re-run adopts, updates or
removes steps by comparing with that file, so it is safe to re-run after any interruption.

## "Person Active At Company (Jev)" (tables, other workflows, anything that can POST)

```
webhook (+ any table that invokes it)
  → 1 Intake (code)              company? profile? or only a LinkedIn URL?   [holds the Jev key]
  → 2 Need a profile? (rules)    need_enrichment → 2a ; otherwise → 2r
  → 2a Enrich person (0.5 credits)   Clay's own Enrich person, from the LinkedIn URL
  → 2p Enrichment ran (rules)    both rules → 2r
  → 2r Prepare (code)            candidate roles, context roles, the one Jev request
  → 3 Anything to ask Jev? (rules)   ask → 4 ; otherwise → 3b
  → 3b Verdict without Jev (code, terminal)
  → 4 Ask Jev (HTTP POST, no Clay connection)
  → 5 Verdict (code, terminal)
```

Measured per run: `2a` moves 0.5 data credits when it runs; `2a` and `4` each count as one action
execution; code and rules steps, and the Audiences lookup and writes below, counted none.
Both workflows are published together or not at all.

## "Person Active At Company (Jev) · Audiences"

```
audience trigger (people joining one saved audience, or all of it on a schedule)
  → 1 Intake (code)              the person's LinkedIn URL field, optional profile field, first linked company   [holds the key]
  → 1g Linked to a company? (rules)   yes → 1a ; no → 1r
  → 1a Look up the company       Look up in Audiences, companies, by company id (free)
  → 1p Lookup ran (rules)        both rules → 1r
  → 1r Company (code)            website and LinkedIn page from the lookup; then the same intake
  → 2 … 5                        as above
  3b → 3c Save which? → 3d Save verdict (all nine fields) | 3e Save status only (the two last-attempt fields)
  5  → 6 Save it?     → 6a Save verdict (all nine fields) | 6b Not saved (Jev failed)
```

The audience trigger hands a workflow `fields` (the person, keyed by field **display name**) and
`accounts` (linked companies, `id` and `name`, most relevant first). The company's website is not
in it, which is why `1a` exists. The CLI cannot read a person's linked company at all (`audiences
records get` returns fields only), so the Audiences workflow has no local preview: its first ten
members, run after the build, are the preview.

Fields written on people records, created if missing and adopted by display name if they exist:
Active at company, Active relationship, Active company checked, Active evidence, Active confidence
(number), Active needs review, Active last attempt, Active last attempt note, Active checked at
(date). All are always non-blank, because a blank string overwrites a populated field. The two
"last attempt" fields describe the most recent run; the other seven keep the last run that reached
a verdict, so a later run that could not check the person never erases what an earlier one found.

`build_workflow.py backfill` sends existing members through the published workflow in batches of
50. What is left is recomputed from Clay each time: a member is done once its "Active last
attempt" field holds a value; one sent over 15 minutes ago with nothing written (a failed Jev call
writes nothing) is sent again. `--plan` counts and prices without sending.

## Traps, each of which fails silently

- **The key is in the first step, and must move.** Clay's CLI can neither create an HTTP API
  connection nor bind one to a step (it binds by id and lists none), so the key is written into
  `1 Intake` as a constant, with a TODO there to move it to a connection when the CLI can. Anyone
  in the workspace who opens the workflow, or a run's `1 Intake` output, can read it. Rebuild to
  rotate it. The Audiences workflow reads the person's name from a named field (default "Name"),
  for the wrong-person check.
- **An HTTP step written without a connection id gets one anyway.** `appAccountId: ""` is the only
  form that leaves it with none. The build reads every tool back and will not publish a workflow
  whose Jev step came back on a connection (exit 6). Updates carry the node's own `toolId`.
- **Headers by reference to an object.** A static JSON string is sent one header per character; a
  static object is rejected.
- **A plain edge into a step with several parents hangs the run** whenever a sibling lane was not
  taken. `2p` and `1p` exist so every parent of `2r` and `1r` is a conditional.
- **A conditional with no matching rule fails the run**, so every conditional has a rule for every
  value.
- **An action parameter needs a pin AND a `{{reference}}`** in `inputMappingConfig` (inside
  `tools[0]`). A pin alone is dropped silently; a pin nothing references is deleted on write.
- **Tool outputs are read at `$.result.…`, code and trigger outputs at `$.…`.**
- **Send every pin and edge on every write, then read back.** A partial write reports success and
  drops what it left out.
- **Code steps import only `json` and `time`, and `time.strptime` counts as `datetime`.** Clay's
  code-test sandbox has modules the runtime lacks. `scripts/test_offline.py` runs the code with
  `datetime`, `_strptime` and `calendar` made unimportable.
- **`tables rows list` returns an enrichment column's display text** (a person's name), not the
  profile; `tables rows get` returns the structured object. What a table *invoking* the workflow
  passes for such a column has not been observed; if it is the display text, the workflow finds no
  work history and buys the profile again from the LinkedIn URL.
- **A webhook or table fires the PUBLISHED version**; a test run fires the draft. The build
  publishes, and the smoke test posts to the webhook.
- **A trigger's type cannot change in place.** Switching the Audiences workflow between "when people
  join" and "on a schedule" means deleting its trigger in Clay first; the build says so and stops.
