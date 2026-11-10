#!/usr/bin/env python3
"""Carve summary and deliverables (Step 7). Reads what the Territory Carve workflow wrote to Salesforce and renders what the
approver reads; writes nothing to Salesforce or Audiences.

  python3 carve_summary.py --org <alias> --rules territory-rules.md --reps reps.csv [--out ./carve] [--rubric-version X]

Outputs in --out:
  carve-summary.md     counts by carve status, the rep-count proposal from the eligible maths, one row per rep (capacity, count,
                       mean fit, grade mix, core share, self-serve share) with the balance verdict per segment and the composition
                       targets, the ten highest-fit accounts not proposed and why, exclusions by reason, protections the org
                       cannot apply (field absent), and whether family hierarchy data exists but was not used
  carve-proposal.csv   every plan account with segment, sub-region, carve status, reason, proposed owner, rep
  write-owners.jsonl   one row per Proposed account in the Write Owners routine's shape: carve_status Assigned, owner_id = the
                       proposed rep. Protected, Excluded, Not eligible and Unowned rows already carry their status from the
                       carve workflow, so the approved write touches owners only.
  patch-doc.md         the rep-facing doc: what's new (placeholder), the criteria table from the rules, each book, FAQ

`carve.py` (the zero-credit local preview) calls render() on its own simulated decisions, so both read alike.
"""
import argparse, collections, csv, json, os, re, statistics, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import miniyaml      # noqa: E402
import carve_node    # noqa: E402
from carve_node import as_dict, as_list, _num as num, _dom as dom   # noqa: E402


def sf(*args):
    r = subprocess.run(["sf", *args, "--json"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        sys.exit("sf failed: %s\n%s" % (" ".join(args), (r.stdout + r.stderr)[-800:]))


def exclusion_row(k, v, EX):
    """One readable (rule, requirement) pair per exclusions key for the patch doc; None when there is nothing to show."""
    def items(seq):
        return ", ".join(str(s) for s in as_list(seq) if s not in (None, ""))
    if v in (None, "", [], {}) or k in ("min_employees", "size_cap", "other_teams_field", "competitors"):
        return None
    if k == "industries":
        return ("Industries we do not sell to", items(v))
    if k == "company_types":
        if isinstance(v, dict):
            parts = []
            if v.get("entity_types"):
                parts.append("company types %s" % items(v["entity_types"]))
            if v.get("keywords"):
                parts.append("names or descriptions mentioning %s" % items(v["keywords"]))
            return ("Another motion owns them", "; ".join(parts) or items(list(v.values())))
        return ("Another motion owns them", "company types %s" % items(v))
    if k == "competitors_field":
        return ("Direct competitors", "any account flagged in the %s field" % v)
    if k == "partner_list":
        return ("Partners", "the domains %s" % items(v))
    if k == "education":
        if isinstance(v, dict):
            bits = ["entity type %s" % v["entity_type"] if v.get("entity_type") else "",
                    "domains ending %s" % items(v["domains"]) if v.get("domains") else "",
                    "institution names in any language" if v.get("institutions") else ""]
            text = ", ".join(b for b in bits if b) or "schools and universities"
            if v.get("edtech_allowed"):
                text += "; edtech companies stay in"
            return ("Education and institutions", text)
        return ("Education and institutions", "schools and universities" if v is True else str(v))
    if k == "regions":
        return ("Regions we do not sell in", items(v))
    if k == "india_heavy":
        on = v is True or (isinstance(v, dict) and v.get("enabled"))
        if not on:
            return None
        country = v.get("country", "India") if isinstance(v, dict) else "India"
        return ("%s-heavy companies" % country, "headquartered in %s" % country)
    if k == "other_teams":
        fld = EX.get("other_teams_field")
        return ("Owned by another team", "%s, marked by the %s field" % (items(v), fld) if fld else "%s (no CRM field marks them yet, so this is checked by hand)" % items(v))
    if k == "manager_list":
        doms = v.get("domains") if isinstance(v, dict) else v
        if not doms:
            return None
        block = v.get("block", "soft") if isinstance(v, dict) else "soft"
        return ("Manager's list", "the domains %s (%s block: the approver decides)" % (items(doms), block) if block == "soft" else "the domains %s" % items(doms))
    label = str(k).replace("_", " ").capitalize()
    if isinstance(v, dict):
        text = "; ".join("%s %s" % (kk, items(vv)) for kk, vv in v.items() if vv not in (None, "", [], {}))
        return (label, text) if text else None
    return (label, items(v)) if items(v) else None


def read_accounts(org, rules):
    have = {f["name"] for f in (sf("sobject", "describe", "-s", "Account", "-o", org).get("result") or {}).get("fields", [])}
    want = list(carve_node.WANT_FIELDS) + ["LastActivityDate"]
    EX = as_dict(rules.get("exclusions")); PROT = as_dict(rules.get("protections"))
    for f in [EX.get("competitors_field"), EX.get("other_teams_field")]:
        if f:
            want.append(f)
    for p in PROT.values():
        if isinstance(p, dict):
            want += ([p.get("field")] if p.get("field") else []) + as_list(p.get("fields"))
    fields = [f for f in dict.fromkeys(want) if f and f in have]
    extra = ", Proposed_Owner__r.Name" if "Proposed_Owner__c" in have else ""
    q = "SELECT %s, Owner.Name%s FROM Account WHERE Territory_Plan__c = true" % (", ".join(fields), extra)
    recs = (sf("data", "query", "-q", q, "-o", org).get("result") or {}).get("records", [])
    out = []
    for r in recs:
        x = carve_node.norm({k: v for k, v in r.items() if k != "attributes"})
        x["owner_name"] = (r.get("Owner") or {}).get("Name") if isinstance(r.get("Owner"), dict) else ""
        po = r.get("Proposed_Owner__r")
        x["proposed_owner_name"] = po.get("Name") if isinstance(po, dict) else ""
        out.append(x)
    return out, have


def from_salesforce(accts, rules, reps, import_user, have):
    """Turn the carve workflow's written fields into the decided-row shape render() takes."""
    by_id = {r.get("crm_user_id"): r for r in reps}
    rows = []
    for x in accts:
        st = x.get("Carve_Status__c") or ""
        owner = ""
        if st in ("Proposed",):
            owner = x.get("Proposed_Owner__c") or ""
        elif st in ("Assigned", "Protected"):
            owner = x.get("OwnerId") or ""
        rep = by_id.get(owner, {}).get("name") or (x.get("proposed_owner_name") if st == "Proposed" else x.get("owner_name")) or ""
        rows.append(dict(x, segment=x.get("Segment__c") or "", sub_region=x.get("Sub_Region__c") or "", carve_status=st or "(not carved)",
                         carve_reason=x.get("Carve_Reason__c") or "", owner_id=owner, rep=rep, industry_group=carve_node.industry_group(x, rules),
                         grade=x.get("Account_Fit_Grade__c") or ""))
    return rows


def render(decided, rules, reps, import_user, have, out, rubric_version=None, source="Salesforce (written by the Territory Carve workflow)", method=None):
    os.makedirs(out, exist_ok=True)
    EX = as_dict(rules.get("exclusions")); EL = as_dict(rules.get("eligibility")); ALLOC = as_dict(rules.get("allocation"))
    PROT = as_dict(rules.get("protections")); COMP = as_dict(rules.get("composition_targets"))
    SEGS = carve_node.segments(rules)
    method = method or str(ALLOC.get("method") or "snake")
    thr = num(EL.get("threshold"), 60)
    sort_key = ALLOC.get("sort_key") or "fit_score"

    def key(x):
        return (-(num(x.get("Account_Fit_Score__c"), 0) if sort_key == "fit_score" else num(x.get(sort_key), 0)), x.get("Id") or "")
    for x in decided:
        x.setdefault("grade", x.get("Account_Fit_Grade__c") or "")
        x.setdefault("industry_group", carve_node.industry_group(x, rules))
    cnt = collections.Counter(x["carve_status"] for x in decided)
    book_states = ("Proposed", "Assigned")
    for r in reps:
        rid = r.get("crm_user_id")
        r["book"] = [x for x in decided if x["carve_status"] in book_states and x.get("owner_id") == rid]
        n_in_seg = sum(1 for q in reps if q.get("segment") == r.get("segment")) or 1
        pool_seg = sum(1 for x in decided if x["carve_status"] in book_states + ("Unowned",) and x.get("segment") == r.get("segment"))
        r["cap"] = carve_node.capacity(r, rules, n_in_seg, pool_seg)
    proposal = {}
    for s in SEGS:
        elig = sum(1 for x in decided if x.get("segment") == s["name"] and x["carve_status"] in book_states + ("Unowned",))
        cap = int(num(s.get("capacity"), 0)) or 1
        proposal[s["name"]] = {"eligible": elig, "capacity": cap, "reps_needed": -(-elig // cap), "reps_in_file": sum(1 for r in reps if r.get("segment") == s["name"])}
    skipped = [k for k, p in PROT.items() if isinstance(p, dict) and p.get("skip_if_absent")
               and not any(f in have for f in ([p.get("field")] if p.get("field") else []) + as_list(p.get("fields")))]
    L = ["# Carve proposal (rules %s, rubric %s, method %s)" % (rules.get("version"), rubric_version or "n/a", method), "",
         "Source: %s. Accounts in plan: %d. %s" % (source, len(decided), ", ".join("%s: %s" % (k, v) for k, v in sorted(cnt.items()))), "",
         "## Rep count from the eligible maths", "", "| Segment | Eligible | Capacity | Reps needed | Reps in file |", "|---|---|---|---|---|"]
    L += ["| %s | %s | %s | %s | %s |" % (s, p["eligible"], p["capacity"], p["reps_needed"], p["reps_in_file"]) for s, p in proposal.items()]
    ss_src = as_dict(COMP.get("self_serve_source")); ss_field = ss_src.get("field") or "Type"; ss_val = ss_src.get("value") or "Customer"
    L += ["", "## Books (Proposed + Assigned)", "", "| Rep | Segment | Sub-region | Capacity | Count | Mean fit | Best | Good | Moderate | Core share | Self-serve share |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reps:
        bk = r["book"]; fits = [num(x.get("Account_Fit_Score__c"), 0) for x in bk]; g = collections.Counter(x.get("grade") for x in bk)
        corep = sum(1 for x in bk if x["industry_group"] == "core") / len(bk) if bk else 0
        ssp = sum(1 for x in bk if (x.get(ss_field) or "") == ss_val) / len(bk) if bk and ss_field in have else None
        L.append("| %s | %s | %s | %s | %d | %s | %d | %d | %d | %s | %s |" % (r["name"], r.get("segment", ""), r.get("sub_region", ""), r["cap"], len(bk),
                 ("%.1f" % statistics.mean(fits)) if fits else "-", g.get("Best Fit", 0), g.get("Good Fit", 0), g.get("Moderate Fit", 0),
                 ("%.0f%%" % (100 * corep)) if bk else "-", ("%.0f%%" % (100 * ssp)) if ssp is not None else "n/a"))
    L += ["", "## Balance within each segment", ""]
    for s in SEGS:
        bs = [r for r in reps if r.get("segment") == s["name"]]; counts = [len(r["book"]) for r in bs]
        means = [round(statistics.mean([num(x.get("Account_Fit_Score__c"), 0) for x in r["book"]]), 1) for r in bs if r["book"]]
        verdict = "balanced" if counts and max(counts) - min(counts) <= 1 and (not means or max(means) - min(means) <= 5) else "not balanced (pool size or geography)"
        tgt = []
        core_t = as_dict(COMP.get("core_industry_share")).get(s["name"])
        if core_t is not None:
            tgt.append("core target %.0f%%" % (100 * num(core_t, 0)))
        ss_t = as_dict(COMP.get("self_serve_share")).get(s["name"])
        if ss_t:
            tgt.append("self-serve target %s" % "-".join("%.0f%%" % (100 * num(v, 0)) for v in as_list(ss_t)))
        L.append("- %s: counts %s, mean fit %s: %s%s" % (s["name"], counts, means, verdict, (" (" + ", ".join(tgt) + ")") if tgt else ""))
    L += ["", "## Ten highest-fit accounts not in a book", "", "| Account | Fit | Grade | Segment | Sub-region | Status | Reason |", "|---|---|---|---|---|---|---|"]
    for x in sorted([x for x in decided if x["carve_status"] not in book_states and x.get("Account_Fit_Score__c") is not None], key=key)[:10]:
        L.append("| %s (%s) | %g | %s | %s | %s | %s | %s |" % (x.get("Name"), x.get("domain"), num(x["Account_Fit_Score__c"], 0), x.get("grade"), x.get("segment"), x.get("sub_region"), x["carve_status"], x["carve_reason"]))
    L += ["", "## Exclusions by reason", ""] + ["- %s: %s" % (k, v) for k, v in collections.Counter(x["carve_reason"].split(" (")[0] for x in decided if x["carve_status"] == "Excluded").most_common()]
    L += ["", "## Not eligible by reason", ""] + ["- %s: %s" % (k, v) for k, v in collections.Counter(re.sub(r"\d+(\.\d+)?", "N", x["carve_reason"]) for x in decided if x["carve_status"] == "Not eligible").most_common()]
    prot = collections.Counter(x["carve_reason"] for x in decided if x["carve_status"] == "Protected")
    if prot:
        L += ["", "## Protected", ""] + ["- %s: %s" % (k, v) for k, v in prot.most_common()]
    SC = carve_node.size_cap_rule(rules)
    if SC:
        hits = sum(1 for x in decided if x["carve_reason"].startswith(SC["reason"]))
        L += ["", "Size cap: %s+ employees is %s (%d accounts; the CRM employee count wins when present)." % (format(SC["cap"], ","), SC["status"], hits)]
    if skipped:
        L += ["", "Skipped protections (field absent in this org): %s" % ", ".join(skipped)]
    if as_dict(rules.get("hierarchy")).get("mode", "entity") == "family" and any(x.get("ParentId") for x in decided):
        L += ["", "Hierarchy: the rules say family, the org has ParentId data, and the Clay carve segments each account on its own employee count (entity). The local preview (`carve.py`) rolls up families; compare before approving."]
    uncarved = [x for x in decided if x["carve_status"] == "(not carved)"]
    if uncarved:
        L += ["", "%d scored accounts have no carve status yet; run `carve_workflow.py run` again for them." % len(uncarved)]
    open(os.path.join(out, "carve-summary.md"), "w").write("\n".join(L) + "\n")
    cols = ["Id", "Name", "domain", "Industry", "industry_group", "NumberOfEmployees", "BillingCity", "state", "country", "Account_Fit_Score__c", "grade",
            "Scoring_Status__c", "Entity_Type__c", "segment", "sub_region", "carve_status", "carve_reason", "owner_id", "rep"]
    with open(os.path.join(out, "carve-proposal.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(decided)
    json.dump(decided, open(os.path.join(out, "carve-proposal.json"), "w"), indent=1, default=str)
    n_rows = 0
    with open(os.path.join(out, "write-owners.jsonl"), "w") as fh:
        for x in decided:
            if x["carve_status"] == "Proposed" and x.get("owner_id"):
                fh.write(json.dumps({"id": x["Id"], "inputs": {"account_id": x["Id"], "domain": x["domain"], "segment": x["segment"], "sub_region": x.get("sub_region") or "",
                                                             "carve_status": "Assigned", "carve_reason": x["carve_reason"], "owner_id": x["owner_id"]}}) + "\n"); n_rows += 1
    P = ["# Territory patch doc", "", "## What's new this quarter", "", "- <one line per rules or model change; see production-example.md section 5>", "",
         "## Criteria: what is in, what is out, and why", "", "| Category | Rule | Requirement |", "|---|---|---|",
         "| Include | Core industries (%s) | fit >= %g |" % (", ".join(as_list(EL.get("core_industries"))) or "none listed, every industry counts as other", thr),
         "| Include | Other industries | %s |" % (EL.get("other_industries_gate") or "fit >= %g" % thr)]
    if num(EX.get("min_employees"), 0) > 0:
        P.append("| Not eligible | Too small | fewer than %s employees |" % format(int(num(EX.get("min_employees"), 0)), ","))
    if SC:
        P.append("| %s | Too big | %s or more employees; the CRM employee count wins when present |" % (SC["status"], format(SC["cap"], ",")))
    vendors = as_list(EL.get("competing_vendors") or EX.get("competitors"))
    if vendors:
        P.append("| Exclude | Competing vendors | %s: their own domains are out of the plan |" % ", ".join(str(v) for v in vendors))
    for k, v in EX.items():
        row = exclusion_row(k, v, EX)
        if row:
            P.append("| Exclude | %s | %s |" % row)
    P += ["", "## Your book", ""]
    for r in reps:
        P += ["### %s (%s, %s): %d accounts" % (r["name"], r.get("segment", ""), r.get("sub_region", ""), len(r["book"])), ""]
        P += ["- %s (%s), fit %g, %s" % (x.get("Name"), x.get("domain"), num(x.get("Account_Fit_Score__c"), 0), x.get("grade")) for x in sorted(r["book"], key=key)] + [""]
    P += ["## FAQ", "", "- Why is X not in my book? Look it up in carve-proposal.csv: every account has a status and a reason, and the same two fields sit on the account in the CRM.",
          "- How do I swap? One-for-one within your segment, manager approves, reason recorded.",
          "- What happens to my open deals? Accounts with an open opportunity keep their owner.",
          "- When does the pool refill? Scored accounts that clear the fit floor enter the Eligible pool; the carve proposes an owner and the manager approves on the top-up cadence.", ""]
    open(os.path.join(out, "patch-doc.md"), "w").write("\n".join(P))
    print("\n".join(L[:L.index("## Balance within each segment")]).rstrip())
    print("\nwritten to %s: carve-summary.md, carve-proposal.csv/json, write-owners.jsonl (%d Proposed rows), patch-doc.md" % (out, n_rows))
    return L


def import_user_id(org, given=None):
    if given:
        return given
    me = (sf("org", "display", "-o", org).get("result") or {}).get("username")
    recs = (sf("data", "query", "-q", "SELECT Id FROM User WHERE Username = '%s'" % me, "-o", org).get("result") or {}).get("records", [])
    return recs[0]["Id"] if recs else None


def main(a):
    rules = miniyaml.load_rules(a.rules)
    reps = list(csv.DictReader(open(a.reps, newline="")))
    accts, have = read_accounts(a.org, rules)
    if not accts:
        sys.exit("no accounts with Territory_Plan__c = true")
    imp = import_user_id(a.org, a.import_user)
    decided = from_salesforce(accts, rules, reps, imp, have)
    render(decided, rules, reps, imp, have, a.out, a.rubric_version)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--org", required=True); ap.add_argument("--rules", required=True); ap.add_argument("--reps", required=True)
    ap.add_argument("--out", default="./carve"); ap.add_argument("--import-user"); ap.add_argument("--rubric-version")
    main(ap.parse_args())
