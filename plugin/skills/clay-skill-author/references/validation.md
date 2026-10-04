# Validate before you submit

Run this on your package from the root of this repository. It catches, locally, the things that
would otherwise come back as a rejection.

The tools are not on your `PATH` — invoke them by path with `python3`, as written below. An earlier
version of this file documented `package_skill.py validate your-skill/`, which fails with
`command not found` at precisely the moment you are trying to check your work.

```
python3 tools/package_skill.py validate build/<slug>
```

Exit `0` means the package shape and content checks pass. Non-zero prints every finding with its
file and line.

## If your skill names a Clay action, fetch the catalogue too

Run these two in order, not just the second:

```
python3 tools/fetch_action_catalog.py --package build/<slug> -o /tmp/catalog.json
python3 tools/package_skill.py validate build/<slug> --action-catalog /tmp/catalog.json
```

**Without the catalogue, nothing checks the actions your skill calls**, and `ok` means only that the
shape is right. There is no finding to read and no warning that a check was skipped, which is why the
two commands belong together. With it, two things become blocking:

- **An action that no longer resolves.** Providers get retired. On a real 2024 table, 5 of its 15
  distinct actions are gone — a step naming one of them cannot run for anybody.
- **A parameter that action does not accept**, or one whose type contradicts what you feed it. A
  shipped skill put a personal email in a parameter the schema declares as a LinkedIn URL. It
  validated clean, and a person found it by running the skill.

`fetch_action_catalog.py` reads only — it asks the catalogue what exists and what each action's
inputs are, refuses anything that executes, and never spends a credit. `validate` itself never calls
`clay`: it reads the file the fetcher wrote, so a machine without the CLI gets an honest "unverified"
rather than a failure.

If you cannot fetch it, say so under `## What this skill does not claim` and name the actions you
could not check. Unverified and checked-and-clean are different claims.

## The exit codes tell you whose problem it is

Non-zero is not one thing. The code separates a defect in your package from a broken tool from a
mistyped command, so an agent driving this can decide what to do instead of guessing — and so can
you.

| Exit | Meaning | What to do |
|---|---|---|
| **0** | Clean | Continue |
| **4** | **Your package has blocking findings** | Fix them. This is the only code you are expected to act on, and the findings say what and where |
| **2** | `validation_error` — the *command* was wrong | No such directory, the file is not a zip, the manifest is not readable JSON. Check what you typed |
| **1** | `internal_error` — **the tool is broken, not your package** | A dependency is missing, or a required check did not run so the package is *unverified* rather than clean. Not your fault and not a reason to edit your skill |

Codes 1 and 2 print a single-line JSON envelope on stderr — `{"error": {"code": …, "message": …}}` —
rather than a Python traceback, so a caller reading stderr gets the same shape every time. This
mirrors the Clay CLI's own contract, which uses the same meanings for `0`, `1` and `2`, so an agent
that already branches on Clay exit codes needs no new vocabulary.

**`0` still means clean and every failure is still non-zero**, so any script checking
`if exit != 0` keeps working. The codes only add the ability to tell the cases apart.

## What it checks

**Shape** — one root `SKILL.md`, supporting files under `references/` or `scripts/`, every
supporting file referenced, nothing loose at the root, no symlinks.

**Content** — every relative reference resolves inside the package; no workspace identifiers
(table ids, column ids, workspace ids, saved-view names, auth handles); no bare credentials; no
private or unreachable endpoints.

**Declarations** — `## Declared inputs` is required. `## Representative output` is checked and
reported, because without it the marketplace page invents an example instead of showing the one you
wrote. And if you declare a `**Halts**` line, every word in it must come from the closed set —
`sample-review`, `spend-approval`, `send-approval`, `write-approval`, `other` — because an unknown
word stops the page parsing the line at all. A step that waits on two things repeats the step number:
`Step 3 spend-approval, Step 3 send-approval`.

Findings come in two severities. **`block`** must be fixed — the package will not be accepted.
**`report`** is a heuristic worth a look: it can be a false positive, and it does not stop you.

## Thresholds, if you converted a table

```
python3 tools/derive_recipe.py compare <table-config.json> <claims.json>
```

Exit `3` means a threshold in your skill does not match the formula it came from. That is a
transcription error, and it is the one class of defect you are least likely to spot yourself —
your table works, so a skill that misquotes it still reads as correct.

## `NOT RUN` is a third answer, and it is the honest one

Two of the checks here can print **`NOT RUN`** next to a case, and finish with something like:

```
3/3 enforced, 1 NOT RUN
Identity IS enforced on the cases that ran. What did not run is named above,
and is unverified rather than passing.
```

**That is not a broken install and it is not a failure.** It means a case needed something this copy
of the kit does not contain, so instead of guessing, the check says which one and why. Both exit `0`,
because nothing is wrong with your package.

Two of them do it, for two different reasons, and both reasons are deliberate:

- **`run_injection_conformance.py`** withholds one thing on purpose: a complete, working
  prompt-injection payload used to measure how much the scanner catches. Publishing it would hand
  anyone a tested template for the attack it defends against, so it is not distributed. The other 25
  cases run and do enforce the rules; what is unmeasured here is *recall* against that one payload.
- **`run_identity_checks.py`** has one case that walks our own seed library and asserts its exact
  size — a tripwire that catches the walker silently reading nothing, which is a bug it has caught
  before. That library is not part of your copy, so the case cannot run. The three cases that build
  their own test trees do run, and they are the ones that check the rule.

**Why you are being told this rather than shown a green tick.** A check that returns nothing when it
could not run is indistinguishable from a check that ran and found nothing, and the second is what
you would assume. Every guard in this kit has to be able to fail, and one that quietly turns into a
no-op has stopped being a guard while still printing a reassuring number. So the number you see
counts only what was actually verified, and the rest is named.

If you would rather have a clean green line, that line would be a lie about which parts were checked.

## Your skill contains checks too, and they need the same treatment

Anywhere your skill says *refuse*, *skip the row*, *report it as ambiguous*, *stop and ask*, or
*fall back because the yield was too low*, you have written a check. It has a failure branch. And a
failure branch that has never executed is not a safeguard — it is a paragraph.

So before you submit: **make each one fire, once, on purpose.** Feed it the input it is supposed to
refuse. A company name that cannot resolve to one domain. A row with the field your step depends on
left empty. A search that legitimately returns nothing.

Two things go wrong, and the second is the one worth the trouble:

- **Nothing happens.** The condition never triggers, because it was written against a shape the data
  does not actually take — a value arriving as a string where the check expects a number, an empty
  result arriving as `[]` where the check tests for null.
- **The wrong thing happens.** Something *does* stop, but not your check — a different guard
  upstream caught it first and produced a message that reads plausibly. Your check is still untested
  and now looks tested, which is worse than looking untested.

That second case is why "did it stop?" is not the question. The question is **which** part stopped
it. If a threshold you wrote is doing the work, changing that threshold should visibly change the
outcome; if it does not, something else is deciding and your number is decoration.

This costs a few minutes per branch and it is the cheapest quality step in the whole process. A skill
whose honest-failure path works is worth more to an installer than one with a better happy path,
because the happy path is the one they will notice is broken.

## What validation does NOT tell you

It checks that the package is **well-formed and portable**. It does not check that the skill is
*good*: whether the logic is right for the job, whether the thresholds are the ones you want,
whether it helps anyone. A clean validation is a floor, not a verdict.
