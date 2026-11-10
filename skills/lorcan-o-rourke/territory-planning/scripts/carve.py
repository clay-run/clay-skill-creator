#!/usr/bin/env python3
"""Local carve preview (Step 7). Zero credits, writes NOTHING to Salesforce or Audiences.

  python3 carve.py --org <alias> --rules territory-rules.md --reps reps.csv [--out ./carve-preview] [--import-user 005...]
                   [--named-overrides overrides.json] [--rubric-version 1.1]

Runs exactly the gates and the deal the Territory Carve workflow's code node runs (`carve_node.py`), over every scored account
in the plan, and renders the same summary, proposal CSV and patch doc (`carve_summary.render`). Use it to tune the rules
file before carving in Clay: edit the threshold, a capacity or a pool's city list, run this, read the books; then push the
rules into the workflow with `carve_workflow.py update` and carve for real with `carve_workflow.py run`.

Two differences from the Clay run, both reported in the summary:
- Hierarchy: when `hierarchy.mode` is `family` and the org has ParentId data, this preview rolls families up (segment by the
  family's largest employee count, the parent's owner and open opportunities carry down). The Clay node segments each
  account on its own CRM count (entity mode).
- `write-owners.jsonl` here lists the simulated Proposed rows; the real file comes from `carve_summary.py` after the Clay run.
"""
import argparse, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import miniyaml       # noqa: E402
import carve_node     # noqa: E402
import carve_summary  # noqa: E402
from carve_node import as_dict, _num as num  # noqa: E402


def roll_up_families(rows, rules, import_user):
    """Family mode for the preview: the family's largest employee count, the root's owner and the family's open opportunities."""
    if as_dict(rules.get("hierarchy")).get("mode", "entity") != "family" or not any(x.get("ParentId") for x in rows):
        return False
    by_id = {x["Id"]: x for x in rows}

    def root(x, depth=0):
        p = x.get("ParentId")
        return root(by_id[p], depth + 1) if p and p in by_id and depth < 10 else x
    fam = {}
    for x in rows:
        fam.setdefault(root(x)["Id"], []).append(x)
    for rid, members in fam.items():
        mx = max((m["emp"] or 0) for m in members)
        opps = sum(num(m.get("Open_Opportunities__c"), 0) for m in members)
        owner = by_id[rid].get("OwnerId")
        for m in members:
            if mx:
                m["emp"] = mx; m["NumberOfEmployees"] = mx
            m["Open_Opportunities__c"] = opps
            if owner and owner != import_user:
                m["OwnerId"] = owner
    return True


def main(a):
    rules = miniyaml.load_rules(a.rules)
    reps = list(csv.DictReader(open(a.reps, newline="")))
    accts, have = carve_summary.read_accounts(a.org, rules)
    if not accts:
        sys.exit("no accounts with Territory_Plan__c = true")
    imp = carve_summary.import_user_id(a.org, a.import_user)
    if not imp:
        sys.exit("could not determine the import user; pass --import-user 005...")
    rolled = roll_up_families(accts, rules, imp)
    overrides = json.load(open(a.named_overrides)) if a.named_overrides else None
    decided = carve_node.carve_all(accts, rules, reps, imp, have, overrides)
    for x in decided:
        x["grade"] = x.get("Account_Fit_Grade__c") or ""
    label = "local preview (carve.py simulation of the carve node; nothing written%s)" % ("; families rolled up" if rolled else "")
    carve_summary.render(decided, rules, reps, imp, have, a.out, a.rubric_version, source=label)
    print("\npreview only. To carve in Clay: carve_workflow.py update (if the rules changed), then carve_workflow.py run.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--org", required=True); ap.add_argument("--rules", required=True); ap.add_argument("--reps", required=True)
    ap.add_argument("--out", default="./carve-preview"); ap.add_argument("--import-user"); ap.add_argument("--named-overrides"); ap.add_argument("--rubric-version")
    main(ap.parse_args())
