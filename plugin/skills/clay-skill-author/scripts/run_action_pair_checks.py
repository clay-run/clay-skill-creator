#!/usr/bin/env python3
"""Acceptance suite for R5 — the (packageId, actionKey) resolver.

EVERY CASE CARRIES A POSITIVE CONTROL, because a check whose failure path has never executed
is not a check. Cases 4, 5 and 6 are the three blocking branches; case 3 is the clean twin of
case 4 (same action, correct value) and case 8 is the control for pair-keying — it feeds the
same bad wiring under a DIFFERENT packageId and must stay silent, which is what proves the
lookup is not resolving on the action key alone.

Case 1 is the one that matters. It is the real shipped skill that motivated this resolver,
reconstructed inline: a per-paid-step table naming `cpj-enrich-person` and feeding
`person_identifier` a personal email. That parameter is `semanticType: person-linkedin-url`.
The skill validated `ok`, 0 blocking, 0 findings, and a human found the defect by running it.
If case 1 ever passes, this resolver has stopped working.

Offline: every case supplies its own catalogue dict. Nothing here calls `clay`.
Run:  python3 tools/run_action_pair_checks.py
Exit: 0 all enforced · 1 a case failed
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "package_skill.py")
sys.path.insert(0, HERE)
import portability as P  # noqa: E402

CPJ_PKG = "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2"
CPJ = f"{CPJ_PKG}/cpj-enrich-person"

# `cpj-enrich-person` as the live schema reports it. BOTH parameters are optional and the real
# contract is the sentence in `or_group` — 7 of 40 sampled actions are shaped this way, so a
# reader that trusts `required` alone concludes nothing is required at all.
SCHEMA = {
    "actions": {
        CPJ: {
            "resolves": True,
            "payment_type": "Clay Credits",
            "credit_cost": 0.5,
            "or_group": "At least one of the following fields is required for the enrich "
                        "person action.",
            "inputs": [
                {"name": "person_identifier", "required": False,
                 "semanticType": "person-linkedin-url"},
                {"name": "email", "required": False, "semanticType": "email"},
            ],
        }
    }
}
RETIRED = {"actions": {CPJ: {"resolves": False}}}
WRONG_PACKAGE = {
    "actions": {
        "00000000-0000-0000-0000-000000000000/cpj-enrich-person": {
            "resolves": True,
            "inputs": [{"name": "something_else", "semanticType": None}],
        }
    }
}

MIN_BODY = """---
name: fixture-skill
description: |
  A fixture. Not a real skill.
---

# Fixture

## Declared inputs

| Input | What the installer supplies | If it is missing |
|---|---|---|
| **A person** | a LinkedIn URL or an email | ask |

## What this skill touches

- **Reads** — nothing.
- **Writes** — nothing.

## What good looks like

- The fixture validates.

## Representative output

### Result

```
nothing
```

## What this skill does not claim

- It has never been run.
"""


def row(params: str, pkg: str = CPJ_PKG, key: str = "cpj-enrich-person") -> str:
    return (f"| 1 | CPJ | `{pkg}` | `{key}` | `{params}` |\n")


def run(ref_body: str, catalog: dict | None) -> tuple[str, list[str]]:
    d = tempfile.mkdtemp()
    try:
        root = os.path.join(d, "p")
        os.makedirs(os.path.join(root, "references"))
        with open(os.path.join(root, "SKILL.md"), "w") as fh:
            fh.write(MIN_BODY + "\nSee `references/action-mechanics.md`.\n")
        with open(os.path.join(root, "references", "action-mechanics.md"), "w") as fh:
            fh.write("# Action mechanics\n\n| # | Provider | packageId | actionKey | input |\n"
                     "|---|---|---|---|---|\n" + ref_body)
        argv = [sys.executable, PKG, "validate", root]
        if catalog is not None:
            cat = os.path.join(d, "cat.json")
            with open(cat, "w") as fh:
                json.dump(catalog, fh)
            argv += ["--action-catalog", cat]
        p = subprocess.run(argv, capture_output=True, text=True)
        o = json.loads(p.stdout)
        return o["verdict"], [f.get("check") for f in (o.get("blocking") or [])]
    finally:
        shutil.rmtree(d, ignore_errors=True)


CASES = [
    # (name, reference-table rows, catalogue, expected verdict, must the finding be action_pair?)
    ("1  THE REAL DEFECT: email into person_identifier",
     row('{"person_identifier":"<personal email>","email":"<personal email>"}'),
     SCHEMA, "blocked", True),
    ("2  no catalogue: unverified, NOT failing",
     row('{"person_identifier":"<personal email>"}'), None, "ok", False),
    ("3  control for 1: correct wiring is clean",
     row('{"person_identifier":"<linkedin url>"}'), SCHEMA, "ok", False),
    ("4  arrow notation is read too",
     "| 1 | CPJ | `%s` | `cpj-enrich-person` | input `person_identifier` ← the personal email |\n"
     % CPJ_PKG, SCHEMA, "blocked", True),
    ("5  parameter absent from the schema",
     row('{"profile_handle":"<linkedin url>"}'), SCHEMA, "blocked", True),
    ("6  action no longer resolves",
     row('{"person_identifier":"<linkedin url>"}'), RETIRED, "blocked", True),
    ("7  empty catalogue behaves like none",
     row('{"person_identifier":"<personal email>"}'), {"actions": {}}, "ok", False),
    ("8  CONTROL: same key, different package, must NOT fire",
     row('{"person_identifier":"<personal email>"}'), WRONG_PACKAGE, "ok", False),
]


def main() -> int:
    failures = 0
    print("R5 — action pair resolver\n")
    for name, body, cat, want, want_ap in CASES:
        got, checks = run(body, cat)
        ap = "portability/action_pair" in checks
        ok = (got == want) and (ap == want_ap)
        failures += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"         expected {want} (action_pair={want_ap}), got {got} {checks}")

    print("\nR4 — stale-action remap, across every accepted catalogue shape")
    body = "Prose naming `cpj-find-lists-of-people` descriptively."
    flat = {"cpj-find-lists-of-people": "cpj-find-people-v2"}
    r4 = [
        ("legacy flat {stale: current}", flat, 1, "remap"),
        ("nested, renames present", {"renames": flat, "actions": {}}, 1, "remap"),
        ("nested, no renames (R4 off, R5 on)", {"actions": {CPJ: {"resolves": True}}}, 0, None),
        ("no catalogue", None, 0, None),
    ]
    for label, cat, n, sev in r4:
        f = P._resolve_stale_actions(body, [], cat)
        ok = len(f) == n and (not f or f[0].severity == sev)
        failures += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {len(f)} finding(s)"
              + (f", severity={f[0].severity}" if f else ""))

    total = len(CASES) + len(r4)
    print(f"\n{total - failures}/{total} enforced")
    if failures:
        print("R5 is NOT enforced. A skill can name an action it cannot call.")
        return 1
    print("Every blocking branch has executed its failure path at least once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
