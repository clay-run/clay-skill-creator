#!/usr/bin/env python3
"""
The preview: check up to 50 of the installer's own people on THIS machine, with the exact code the
Clay workflow runs, before anything is built or bought.

    python3 check_local.py --provider typesafe --table <table id> --show-map        # the column mapping, nothing checked
    python3 check_local.py --provider typesafe --table <table id> [--map key=Column …] [--limit 10] [--skip 10]
    python3 check_local.py --provider typesafe --file people.json                   # a JSON list of records
    python3 check_local.py --provider typesafe --fixtures                           # the invented cases
    ... add --enrich to BUY profiles for people that have only a LinkedIn URL (0.5 Clay credits each;
        the count and the cost are printed first)

The inputs are the workflow's own: company_name, company_domain, company_linkedin_url (at least
one), profile (an enriched profile: the value of a Clay "Enrich person" column is ideal),
linkedin_url, full_name. A table's columns are proposed onto them by name and by content (the
column whose cells hold a work history is the profile) and SHOWN for correction.

Jev costs a fraction of a cent for ten people. Results go to last-preview.json in this skill's
state folder, which the smoke test reuses.
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import active_lib as L  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MAPPABLE = ("company_name", "company_domain", "company_linkedin_url", "profile", "linkedin_url", "full_name")
HINTS = {"company_domain": (("domain",), ("website",), ("company", "url")),
         "company_linkedin_url": (("company", "linkedin"),),
         "company_name": (("company", "name"), ("company",), ("account", "name"), ("organization",)),
         "linkedin_url": (("linkedin", "profile"), ("linkedin", "url"), ("linkedin",), ("profile", "url")),
         "full_name": (("full", "name"), ("name",)),
         "profile": (("enrich", "person"), ("profile",))}


def words(s):
    out, cur = [], ""
    for ch in str(s or "").lower() + " ":
        if ch.isalnum():
            cur += ch
        elif cur:
            out.append(cur)
            cur = ""
    return set(out)


def cell_value(c):
    if not isinstance(c, dict) or c.get("status") != "success":
        return None
    return c.get("fields") if isinstance(c.get("fields"), dict) and c.get("fields") else c.get("value")


def propose(columns, rows):
    """{input: column id or None}. The profile column is found by CONTENT (cells holding a work
    history); the rest by name, most specific hint first, never reusing a column."""
    core = L.load_core("typesafe")
    out, used = {}, set()
    def is_profile(v):
        roles = core["read_profile"](core["_obj"](v))[0] if v else []
        return any(r["company"] for r in roles)

    for c in columns:
        vals = [cell_value((r.get("cells") or {}).get(c["id"])) for r in rows]
        if any(is_profile(v) for v in vals):
            out["profile"] = c["id"]
            used.add(c["id"])
            break
    for key in ("company_linkedin_url", "company_domain", "linkedin_url", "company_name", "full_name", "profile"):
        if out.get(key):
            continue
        for hint in HINTS[key]:
            hit = next((c["id"] for c in columns if c["id"] not in used and set(hint) <= words(c["name"])
                        and not words(c["name"]) & {"data", "table", "json", "steps"}
                        and not (key == "linkedin_url" and "company" in words(c["name"]))
                        and not (key == "full_name" and words(c["name"]) & {"company", "account", "first", "last"})), None)
            if hit:
                out[key] = hit
                used.add(hit)
                break
    return dict((k, out.get(k)) for k in MAPPABLE)


def apply_map(mapping, columns, overrides):
    by_name = dict((str(c["name"]).strip().lower(), c["id"]) for c in columns)
    for o in overrides:
        if "=" not in o:
            L.fail("--map takes key=Column, got %r" % o, code=2)
        k, v = o.split("=", 1)
        if k not in MAPPABLE:
            L.fail("Unknown input %r. Inputs: %s" % (k, ", ".join(MAPPABLE)), code=2)
        v = v.strip()
        mapping[k] = None if v.lower() in ("", "none", "-") else (by_name.get(v.lower()) or
                                                              (v if v in {c["id"] for c in columns} else None))
        if v.lower() not in ("", "none", "-") and not mapping[k]:
            L.fail("No column called %r." % v, code=2)
    return mapping


def show_map(mapping, columns):
    names = dict((c["id"], c["name"]) for c in columns)
    L.say("How your columns map onto the workflow's inputs (correct any with --map input=Column):")
    for k in MAPPABLE:
        L.say("  %-22s ← %s" % (k, repr(names[mapping[k]]) if mapping.get(k) else "(none)"))
    if not any(mapping.get(k) for k in ("company_name", "company_domain", "company_linkedin_url")):
        L.say("  ! No company column: every row would come back not_checked. Map one.")
    if not mapping.get("profile") and not mapping.get("linkedin_url"):
        L.say("  ! Neither a profile nor a LinkedIn URL: nothing can be checked. Map one.")


def table_records(table, overrides, limit, show, skip=0):
    cols = L.clay("tables", "columns", "list", table)
    cols = cols.get("data") or cols.get("columns") or (cols if isinstance(cols, list) else [])
    columns = [{"id": c.get("id") or c.get("columnId"), "name": c.get("name")} for c in cols]
    listed = (L.clay("tables", "rows", "list", table, "--limit", str(min(100, max(limit + skip, 10)))).get("data") or [])
    listed = listed[skip:]
    # `rows list` returns an enrichment column's DISPLAY text (a person's name); only `rows get`
    # returns the structured profile. Measured on a live "Enrich person" column.
    rows, lost = [], []
    for r in listed[:limit]:
        got = L.clay("tables", "rows", "get", table, r["id"], allow_fail=True)
        if not (isinstance(got, dict) and got.get("cells")):
            got = L.clay("tables", "rows", "get", table, r["id"], allow_fail=True)
        if isinstance(got, dict) and got.get("cells"):
            rows.append(got)
        else:
            lost.append(str(r["id"]))
    if lost:
        L.say("  ! %d row(s) could not be read from Clay and are left out: %s" % (len(lost), ", ".join(lost)))
    mapping = apply_map(propose(columns, rows), columns, overrides)
    show_map(mapping, columns)
    if show:
        print(json.dumps({"mapping": mapping}))
        raise SystemExit(0)
    recs = []
    for r in rows[:limit]:
        cells = r.get("cells") or {}
        rec = dict((k, cell_value(cells.get(cid))) for k, cid in mapping.items() if cid)
        rec["source_ref"] = "row " + str(r.get("id"))
        recs.append(rec)
    return recs


def enrich_fn(pkg):
    def run(url):
        out = L.clay("workflows", "actions", "test", pkg, L.ENRICH_ACTION, "--inputs",
                     json.dumps({"person_identifier": url}), allow_fail=True)
        return out.get("result") if isinstance(out, dict) else None
    return run


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", choices=sorted(L.PROVIDERS), required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--table")
    src.add_argument("--file")
    src.add_argument("--fixtures", action="store_true")
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--show-map", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--skip", type=int, default=0, help="table: leave out the first N rows (ten other rows: --skip 10)")
    ap.add_argument("--enrich", action="store_true", help="buy profiles for URL-only people (0.5 credits each)")
    a = ap.parse_args()
    a.limit = max(1, min(50, a.limit))

    if a.table:
        records = table_records(a.table, a.map, a.limit, a.show_map, max(0, min(90, a.skip)))
    elif a.file:
        records = json.load(open(a.file))
        records = (records if isinstance(records, list) else [records])[:a.limit]
    else:
        records = [c["record"] for c in json.load(open(os.path.join(HERE, "fixtures.json")))["cases"]][:a.limit]

    core = L.load_core(a.provider)
    need = [r for r in records if core["intake"](r)["need_enrichment"]]
    enrich = None
    if need:
        if a.enrich:
            L.say("Buying %d profile(s) with Clay's Enrich person: %.1f credits." % (len(need), len(need) * L.ENRICH_CREDITS))
            pkg = next((x.get("packageId") for x in (L.clay("workflows", "actions", "list").get("data") or [])
                        if x.get("actionKey") == L.ENRICH_ACTION), None)
            if not pkg:
                L.fail("Clay's Enrich person action is not in this workspace's catalogue.")
            enrich = enrich_fn(pkg)
        else:
            L.say("%d of these people have only a LinkedIn URL; they come back not_checked unless you add "
                  "--enrich (%.1f credits)." % (len(need), len(need) * L.ENRICH_CREDITS))

    results, cost = [], 0.0
    for r in records:
        v = L.check_record(a.provider, r, enrich=enrich)
        cost += v["jev_cost_usd"]
        results.append(v)
        who = (r.get("full_name") or core["read_profile"](core["_obj"](r.get("profile")))[1].get("name")
               or r.get("linkedin_url") or r.get("source_ref") or "?")
        L.say("  %-26s %-22s %-11s %-16s %3s%%  %s%s" % (
            str(who)[:26], str(v["company_checked"])[:22], v["active_at_company"], v["relationship"],
            v["verdict_confidence"], v["evidence"][:110],
            "" if v["needs_review"] == "none" else "  [review: %s]" % v["needs_review"][:90]))
    tally = {}
    for v in results:
        tally[v["active_at_company"]] = tally.get(v["active_at_company"], 0) + 1
    L.say("%d people: %s · Jev cost $%.5f" % (len(results), ", ".join("%s %d" % kv for kv in sorted(tally.items())), cost))
    try:
        ws = L.workspace()["id"]
    except SystemExit:
        ws = "local"
    L.save(os.path.join(L.state_dir(ws), "last-preview.json"), {"records": records, "results": results})


if __name__ == "__main__":
    main()
