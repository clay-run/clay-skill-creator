# The workflows, node by node, and the traps they avoid

Built by `scripts/build_scorer.py`. Node ids go into `build-state.json` the moment each node exists;
a re-run adopts, updates or removes nodes by comparing with that file, so it is safe to re-run after
any interruption.

## "Jev lead score: <accounts|contacts> · <rubric>" (tables, webhooks, other workflows)

```
webhook trigger (+ every table bound to the workflow in Clay's UI)
  → 1 Intake (code)                inputs arrive as flat fields, one per rubric input, plus source_ref.
                                   Works out every rule; decides which questions have the data they
                                   read; builds the one Jev request; sets ask = true/false
  → 2 Anything to ask Jev? (rules) ask = true → 3 ; otherwise → 2b
  → 2b Score without Jev (code, terminal)   required input missing, a rule disqualified it, or
                                            no question had its data. No Jev call, no cost
  → 3 Ask Jev (HTTP POST)          url, body and headers by reference from 1 Intake; the key comes
                                   from the Clay connection; no retry options (they broke the step);
                                   returnResponseMetadata so a 4xx is data, not a failed run
  → 4 Score (code, terminal)       the verdict: every output key, always present
```

A table binds to the workflow in Clay's UI with **1 Intake** as the starting node, maps its columns
onto the inputs (names need not match), and gets the output written back onto the row.

## "… (audience)" (only when an audience is named)

```
audience_segment trigger (members of the saved audience)
  → 1 Intake … 4 Score             the same four steps; inputs pinned from the trigger's own
                                   output schema (read at build time, never guessed), plus the
                                   record id
  2b → 2c Save to Audiences        update-audiences-record by entity id
  4  → 5 Save it? (rules)          status ≠ failed → 6 Save to Audiences
                                   status = failed → 5b Not saved (an outage never overwrites a score)
```

Fields written, created if missing and adopted by display name if they exist (a create with a taken
name gets a suffix, so adopting is what keeps rebuilds from multiplying them): Jev lead score
(number), Jev lead tier, Jev score status, Jev score reasons, Jev score needs review, Jev score
rubric (text), Jev scored at (date). Every one is always non-blank, because a blank string
overwrites a populated field (`removeNullValues` drops nulls, not empty strings).

## Traps, each of which fails silently

- **Never set the HTTP step's retry options** (`shouldRetry`, `retryOptions|…`), although the action
  schema offers them. With them set, the step failed every live run with
  `ERROR_ACTION_RUNTIME_ERROR` before calling Jev; without them, every run passed.
- **An audience trigger passes the record's fields keyed by DISPLAY NAME** under `$.fields`
  (`fields.Company name`, `fields.Domain`), plus `fields.id`. The build reads the trigger's output
  schema and resolves each mapped field's path from it, never guessing.
- **Connections bind by id, never by name.** A step written without an id lands on whatever HTTP
  connection the workspace already has; its key then goes to Jev (401) or, worse, Jev's key goes
  nowhere and another provider's key goes to Jev. The build reads every tool back and will not
  publish a step on the wrong connection (exit 6). `--reattach` rewrites the Jev step as a new tool
  to pick up a newly set default; otherwise updates carry the node's own `toolId`, because an update
  without it makes a new tool and re-attaches the default.
- **Headers by reference to an object.** A static JSON string is sent one header per character; a
  static object is rejected.
- **Tool-node outputs are read at `$.result.…`, code-node outputs at `$.…`.**
- **Send every pin and edge on every write, then read back.** A partial write reports success and
  drops what it left out. The build stops naming any lost pin.
- **A trigger's schema must be complete on every build.** Fields missing from it are stripped at
  intake, so an input added to the rubric later would arrive blank forever.
- **Wire intake from every trigger node**, including those a table binding added; a rebuild that
  names only the webhook severs the table.
- **Code steps import only `json` and `time`, and use no `time.strptime` or `time.mktime`.**
  `strptime` imports `datetime` and `calendar` behind the scenes, which the runtime lacks, so a date
  rule built on it silently reads nothing in Clay; dates are parsed and counted by hand. Clay's
  code-test sandbox has modules the runtime lacks, so a green sandbox run proves nothing.
  `scripts/test_offline.py` runs every generated step on fixtures.
- **Python literals, never JSON, inside generated code.** The rubric is embedded with `repr`.
- **A webhook or bound table runs the PUBLISHED version**; a test run fires the draft. The build
  publishes, and the smoke test runs `--live`.
- **A conditional with no matching rule fails the run**, so both conditionals have a rule for every
  value.
