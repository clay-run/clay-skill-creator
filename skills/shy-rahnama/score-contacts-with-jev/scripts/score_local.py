#!/usr/bin/env python3
"""
Score a small batch of real records on THIS machine, with the local .env key, running the exact
code the Clay workflow will run. This is the preview the installer corrects the rubric against
before anything is built.

    python3 score_local.py --provider openrouter --table <table id> [--limit 10] [--map key=Column] [--show-map]
    python3 score_local.py --provider openrouter --audience <audience id> [--limit 10] [--map key=Field]
    python3 score_local.py --provider openrouter --file records.csv|records.json|records.jsonl

--show-map prints how the source's columns map onto the rubric's inputs and stops, without calling
Jev: show it, take corrections as --map, then run. Reads at most --limit records (max 50). Each
record is one Jev request (a fraction of a cent); a record a rule disqualifies, or with nothing to
ask, costs nothing. Results are written to the state folder as JSON lines and summarised here.
"""
import argparse
import csv
import json
import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jev_lib as L  # noqa: E402


def _cell(c):
    if isinstance(c, dict):
        if c.get("status") == "success":
            v = c.get("value")
            return v if not isinstance(v, (dict, list)) else json.dumps(v)
        return ""
    return c


def from_table(table_id, limit):
    cols = L.clay("tables", "columns", "list", table_id)
    cols = cols.get("data") or cols.get("columns") or (cols if isinstance(cols, list) else [])
    columns = [{"id": c.get("id") or c.get("columnId"), "name": c.get("name")} for c in cols]
    rows = L.clay("tables", "rows", "list", table_id, "--limit", str(limit)).get("data") or []
    recs = [dict([(cid, _cell(v)) for cid, v in (r.get("cells") or {}).items()] + [("__ref", r.get("id"))])
            for r in rows]
    return columns, recs


def from_audience(audience_id, limit):
    fields = L.clay("audiences", "fields", "list", "--entity-type", L.AUDIENCE_FLAG)
    fields = fields.get("data") or fields.get("fields") or (fields if isinstance(fields, list) else [])
    columns = [{"id": f.get("id") or f.get("fieldId"), "name": f.get("name") or f.get("displayName")} for f in fields]
    ids = L.clay("audiences", "records", "search-ids", "--audience-id", audience_id,
                 "--entity-type", L.AUDIENCE_FLAG, "--limit", str(limit)).get("data") or []
    if not ids:
        return columns, []
    got = L.clay("audiences", "records", "get", "--entity-type", L.AUDIENCE_FLAG,
                 "--ids", ",".join(str(i) for i in ids[:limit])).get("data") or []
    recs = [dict(list((r.get("fields") or {}).items()) + [("__ref", r.get("recordId"))]) for r in got]
    return columns, recs


def from_file(path, limit):
    if path.endswith(".csv"):
        with open(path, newline="") as f:
            recs = list(csv.DictReader(f))
    else:
        with open(path) as f:
            txt = f.read()
        try:
            recs = json.loads(txt)
            recs = recs if isinstance(recs, list) else recs.get("records") or [recs]
        except json.JSONDecodeError:
            recs = [json.loads(l) for l in txt.splitlines() if l.strip()]
    recs = recs[:limit]
    names = []
    for r in recs:
        for k in r:
            if k not in names:
                names.append(k)
    return [{"id": n, "name": n} for n in names], [dict(r, __ref="row %d" % (i + 1)) for i, r in enumerate(recs)]


def label_of(rec_in, ref):
    order = ("full_name", "name", "email", "company_name") if L.ENTITY == "contact" else ("company_name", "name", "domain")
    for k in order:
        if rec_in.get(k):
            return str(rec_in[k])[:28]
    return str(ref)[:28]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", required=True, choices=sorted(L.PROVIDERS))
    ap.add_argument("--rubric")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--table")
    src.add_argument("--audience")
    src.add_argument("--file")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--map", action="append", default=[])
    ap.add_argument("--show-map", action="store_true")
    a = ap.parse_args()
    limit = max(1, min(a.limit, 50))

    ws = L.workspace()
    r = L.load_rubric(a.rubric, ws["id"])
    if a.table:
        columns, recs = from_table(a.table, limit)
    elif a.audience:
        columns, recs = from_audience(a.audience, limit)
    else:
        columns, recs = from_file(a.file, limit)

    mapping = L.apply_overrides(L.propose_map(r["inputs"], columns), columns, a.map)
    L.say(L.mapping_card(r["inputs"], mapping, columns))
    missing = [k for k, s in r["inputs"].items() if s["required"] and not mapping.get(k)]
    if a.show_map:
        print(json.dumps({"mapping": mapping, "unmapped": [k for k in mapping if not mapping[k]]}))
        return
    if missing:
        L.fail("Required input(s) not mapped: %s. Map them with --map key=Column." % ", ".join(missing), code=2)
    if not recs:
        L.fail("The source returned no records to score.", code=2)
    if not L.find_key(a.provider):
        L.fail("No %s key on this machine yet: jev_key.py guide %s" % (L.PROVIDERS[a.provider]["label"], a.provider), code=3)

    out_dir = os.path.join(L.state_dir(ws["id"]), "previews")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "%s-v%d-%d.jsonl" % (L.slug(r["name"]), r["version"], int(time.time())))
    L.say("")
    L.say("%-28s %5s  %-18s %s" % (L.NOUN, "score", "tier", "why (top reasons) / needs review"))
    tiers, cost, review = {}, 0.0, 0
    with open(out_path, "a") as f:
        for rec in recs:
            inp = dict((k, rec.get(c) if c else None) for k, c in mapping.items())
            inp["source_ref"] = str(rec.get("__ref") or "")
            res = L.score_record(r, a.provider, inp)
            f.write(json.dumps({"input": inp, "result": res}) + "\n")
            f.flush()
            tiers[res["lead_tier"]] = tiers.get(res["lead_tier"], 0) + 1
            cost += float(res["jev_cost_usd"] or 0)
            review += res["needs_review"] != "none"
            L.say("%-28s %5s  %-18s %s" % (label_of(inp, inp["source_ref"]), res["lead_score"], res["lead_tier"],
                                           res["score_reasons"][:150]))
            if res["needs_review"] != "none":
                L.say("%-28s %5s  %-18s review: %s" % ("", "", "", res["needs_review"][:150]))
            if res["error"]:
                L.say("%-28s %5s  %-18s error: %s" % ("", "", "", res["error"][:150]))
    L.say("")
    L.say("%d %s scored with %s v%d: %s. %d with an answer worth reviewing. Jev cost $%.5f." % (
        len(recs), L.NOUNS, r["name"], r["version"],
        ", ".join("%s %d" % kv for kv in sorted(tiers.items())), review, cost))
    L.say("Every result, with each criterion's answer and points: %s" % out_path)


if __name__ == "__main__":
    main()
