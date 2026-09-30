# Live checks: what was run against Jev and Clay (a test workspace, 2026-09-29)

Both skills share their scripts, so a check run with one exercises the other's code. Every run used
a TypeSafe key; the OpenRouter route was not called.

| # | What | Result |
|---|---|---|
| 1 | Key check, TypeSafe direct | `jev-1.13.0` answered a one-question request; cost about $0.00001 |
| 2 | Account preview, six invented companies, the example rubric | Real Jev answers parsed on every path: a distributor 98 A; a competitor `disqualified` by a rule with no Jev call; a logistics firm `disqualified` by Jev at ≥ 80%; a blank record `insufficient_data`; unsure answers listed for review. $0.0001 in total |
| 3 | Contact preview, six invented people | VP Operations at an A-tier account 96 A; a recruiter `disqualified`; no title `not_scored`; a date rule (time in role) scored. |
| 4 | First build, no connection id | Clay attached an unrelated HTTP connection to the Jev step. The read-back caught it and the workflow was not published (exit 6) |
| 5 | Connection bound with `--connection-id` | Read back on the right connection on the first write; published |
| 6 | `--reattach` | Rewrote the Jev step as a new tool; Clay attached the workspace default (the Jev connection); published |
| 7 | Picking the connection on the step in Clay's UI | Did **not** persist in this test (the step reloaded on the old connection). Kept as a last resort only |
| 8 | HTTP step retry options (`shouldRetry`, `retryOptions`) | With them: `ERROR_ACTION_RUNTIME_ERROR` on every run, before Jev was called (three runs, two workflows). Without them: every run passed. They are off |
| 9 | Account workflow, one record through the published version | Clay 98 A = local 98 A; same reasons |
| 10 | Account workflow, a real POST to its webhook | Scored 48 B, `source_ref` echoed, unsure answer flagged |
| 11 | Contact workflow, one record through the published version | Clay 96 A = local 96 A |
| 12 | Account audience workflow: 7 fields created, trigger output read, one member run | The trigger passes fields keyed by display name under `fields`; paths resolved from its schema. Jev answered 200 through the connection; the score and all seven fields were written onto the record and read back equal to the local score. Publishing the audience trigger started no runs by itself |

Offline, not live: date rules are exercised by `scripts/test_offline.py` with every import but
`json` and `time` refused, which is how Clay's code runtime behaves (`time.strptime` would read
nothing there).

Not run live: the OpenRouter route; a Clay table bound to the workflow (the webhook path was run,
and a table binding maps onto the same inputs); the contact audience workflow; `backfill` over a
whole audience; a Jev 429.
