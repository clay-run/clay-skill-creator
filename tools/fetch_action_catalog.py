#!/usr/bin/env python3
"""Write the action catalogue `package_skill.py validate --action-catalog` reads.

THE SPLIT OF RESPONSIBILITY IS THE POINT. `validate` is offline and deterministic, and its
exit 1 means "a required check did not run, so the package is unverified". A check that shelled
out to `clay` would make every machine without the CLI an exit-1 — so the validator reads a
file, and this script is the only piece that talks to the CLI.

READS ONLY. It calls `clay workflows actions list` and `clay workflows actions schema`, both of
which are configuration reads. It will not call `workflows actions test`, `nodes test` or
anything under `runs`: those execute and spend, and a tool whose job is to make validation
possible must never be the reason a credit left the account.

Usage:
    # every pair named in a package (the usual case)
    python3 tools/fetch_action_catalog.py --package <dir> -o catalog.json

    # every pair a derived recipe carries (table route, post-derive_recipe)
    python3 tools/fetch_action_catalog.py --recipe derived.json -o catalog.json

    # explicit pairs
    python3 tools/fetch_action_catalog.py --pair <packageId>/<actionKey> -o catalog.json

Then:
    python3 tools/package_skill.py validate <dir> --action-catalog catalog.json

A pair that comes back `not_found` is recorded with `resolves: false` rather than omitted.
Omitting it would be indistinguishable from "we never looked", and the validator's whole point
here is to tell those two apart.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PAIR_LINE = re.compile(
    rf"(?P<pid>{UUID}).{{0,200}}?`?(?P<key>[a-z][a-z0-9]*(?:-[a-z0-9]+)+)`?"
    rf"|`?(?P<key2>[a-z][a-z0-9]*(?:-[a-z0-9]+)+)`?.{{0,200}}?(?P<pid2>{UUID})"
)
# Never run these, whatever is asked for.
FORBIDDEN = ("test", "runs", "run")


def _clay() -> str:
    exe = shutil.which("clay") or os.path.expanduser("~/.local/bin/clay")
    if not os.path.exists(exe):
        sys.exit("clay CLI not found. Install it, or run validate without --action-catalog "
                 "and accept that the action pairs are unverified.")
    return exe


def _run(exe: str, args: list[str], timeout: int = 90) -> dict:
    if any(a in FORBIDDEN for a in args):
        sys.exit(f"refusing to run `clay {' '.join(args)}`: this tool performs reads only.")
    p = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout)
    # THE CLI PUTS ERRORS ON STDERR, with a non-zero exit and an EMPTY stdout — measured: a
    # not_found schema read exits 6 and prints `{"error": {"code": "not_found", ...}}` to stderr.
    # Parsing stdout alone recorded every retired action as `unparseable`, which collapsed the one
    # distinction this file exists to keep: a provider that is GONE (actionable — pick another)
    # versus a read that FAILED (not actionable — say so and do not call it a retirement).
    for stream in (p.stdout, p.stderr):
        if not (stream or "").strip():
            continue
        try:
            return json.loads(stream)
        except Exception:
            continue
    return {"error": {"code": "unparseable",
                      "message": f"exit {p.returncode}: {(p.stdout + p.stderr)[:200]}"}}


def pairs_from_text(text: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for line in text.split("\n"):
        m = PAIR_LINE.search(line)
        if not m:
            continue
        pid = m.group("pid") or m.group("pid2")
        key = m.group("key") or m.group("key2")
        if pid and key:
            out.add((pid, key))
    return out


def pairs_from_package(root: str) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith((".md", ".markdown")):
                p = os.path.join(dirpath, f)
                with open(p, errors="replace") as fh:
                    out |= pairs_from_text(fh.read())
    return out


def pairs_from_recipe(path: str) -> set[tuple[str, str]]:
    """Post-Fix-0 recipes carry the identity per action; pre-Fix-0 ones carry none."""
    with open(path) as fh:
        d = json.load(fh)
    out: set[tuple[str, str]] = set()
    for v in (d.get("actions") or {}).values():
        pid, key = v.get("action_package_id"), v.get("action_key")
        if pid and key:
            out.add((pid, key))
    if not out:
        print("note: this recipe carries no (packageId, actionKey) pairs — it predates the "
              "reader change that keeps them. Use --package instead.", file=sys.stderr)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--package", help="package directory; every .md in it is scanned for pairs")
    src.add_argument("--recipe", help="derive_recipe.py config output")
    src.add_argument("--pair", action="append", help="<packageId>/<actionKey>; repeatable")
    ap.add_argument("-o", "--out", default="-", help="output path, or - for stdout")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()

    if a.package:
        pairs = pairs_from_package(a.package)
    elif a.recipe:
        pairs = pairs_from_recipe(a.recipe)
    else:
        pairs = set()
        for s in a.pair:
            pid, _, key = s.partition("/")
            if not (pid and key):
                sys.exit(f"--pair wants <packageId>/<actionKey>, got {s!r}")
            pairs.add((pid, key))

    if not pairs:
        print("no (packageId, actionKey) pairs found — nothing to fetch. The skill names none, "
              "which is the house style for a portable body; its paid steps are then unverified "
              "by this check rather than passing.", file=sys.stderr)
        json.dump({"actions": {}}, sys.stdout if a.out == "-" else open(a.out, "w"), indent=1)
        return 0

    exe = _clay()
    whoami = _run(exe, ["whoami"])
    if whoami.get("error"):
        sys.exit(f"clay is not signed in ({whoami['error'].get('code')}). Run `clay login`.")

    # creditCost and paymentType live on the list dump, not the schema — one free call for all.
    listing = _run(exe, ["workflows", "actions", "list"], timeout=180)
    rows = listing.get("data") or []
    meta = {(r.get("packageId"), r.get("actionKey")): r for r in rows if isinstance(r, dict)}

    def fetch(pair):
        pid, key = pair
        d = _run(exe, ["workflows", "actions", "schema", pid, key])
        err = (d.get("error") or {}).get("code")
        if err == "not_found":
            return pair, {"resolves": False}
        if err:
            # NOT the same as not_found, and must not be recorded as a retirement.
            return pair, {"resolves": None, "fetch_error": err}
        m = meta.get(pair, {})
        return pair, {
            "resolves": True,
            "display_name": d.get("displayName"),
            "payment_type": m.get("paymentType"),
            "credit_cost": m.get("creditCost"),
            "inputs": [
                {"name": p.get("name"),
                 "required": bool(p.get("required")),
                 "semanticType": (p.get("typeSettings") or {}).get("semanticType")}
                for p in (d.get("inputParameters") or [])
            ],
            # The OR-group constraint is a SENTENCE, carried verbatim. 7 of 40 sampled actions
            # mark nothing `required` and 6 of those 7 state the real contract only here, so a
            # flag-only reader concludes nothing is required — which is how an interview ends up
            # asking for neither. Do not parse this into a flag; read it.
            "or_group": next(
                (p["displayHeader"]["description"] for p in (d.get("inputParameters") or [])
                 if isinstance(p.get("displayHeader"), dict)
                 and p["displayHeader"].get("description")), None),
        }

    out: dict = {}
    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        for pair, entry in ex.map(fetch, sorted(pairs)):
            out[f"{pair[0]}/{pair[1]}"] = entry

    dead = [k for k, v in out.items() if v.get("resolves") is False]
    errs = [k for k, v in out.items() if v.get("resolves") is None]
    payload = {
        "catalog_version": 1,
        "workspace": (whoami.get("workspace") or {}).get("id"),
        "fetched_pairs": len(out),
        "actions": out,
    }
    dest = sys.stdout if a.out == "-" else open(a.out, "w")
    json.dump(payload, dest, indent=1)
    if a.out != "-":
        dest.close()
    print(f"{len(out)} pair(s) fetched; {len(dead)} do not resolve"
          + (f"; {len(errs)} could not be read" if errs else ""), file=sys.stderr)
    for k in dead:
        print(f"  not_found: {k}", file=sys.stderr)
    for k in errs:
        print(f"  unreadable (NOT a retirement): {k} — {out[k].get('fetch_error')}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
