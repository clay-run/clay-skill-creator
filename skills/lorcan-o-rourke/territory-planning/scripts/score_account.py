"""Territory planning 2.0 candidate. Pure scoring, no network or workspace writes.

Local: python3 score_account.py rubric.json accounts.json
Clay: paste this file into a code node; handler inputs are rubric_json and account_json.
The flat output uses JSON text so held scores can be null without nullable flat fields.
"""
import json
import math
import re


def number(value):
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError("expected a finite number")
    try:
        n = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        raise ValueError("expected a finite number")
    if not math.isfinite(n):
        raise ValueError("expected a finite number")
    return n


def domain(value):
    s = str(value or "").strip().lower()
    s = re.sub(r"^https?://", "", s).split("/")[0].split("?")[0].split("#")[0]
    if s.startswith("www."):
        s = s[4:]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", s) or "." not in s or ".." in s:
        return ""
    return s


def key(value):
    # False and zero are observed map values, never shorthand for missing.
    return str(value).strip().lower()


def validate_rubric(rubric):
    if not isinstance(rubric, dict) or not str(rubric.get("version") or "").strip():
        raise ValueError("rubric version is required")
    fs = rubric.get("factors")
    if not isinstance(fs, list) or not fs:
        raise ValueError("factors must be a nonempty list")
    ids, weights = set(), []
    for f in fs:
        fid = f.get("id", "")
        if not isinstance(fid, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", fid) or fid in ids:
            raise ValueError("factor IDs must be unique lowercase identifiers")
        ids.add(fid)
        w = number(f.get("weight"))
        if w < 0 or w > 100:
            raise ValueError("weight outside 0..100")
        weights.append(w)
        if not str(f.get("name") or "").strip():
            raise ValueError("factor name required")
        kind = f.get("kind")
        if kind == "map":
            m = f.get("map")
            if not isinstance(m, dict) or not m or any(not isinstance(k, str) or k != key(k) for k in m):
                raise ValueError("map keys must be explicit lowercase strings")
            vals = list(m.values())
        elif kind == "bands":
            bs = f.get("bands")
            if not isinstance(bs, list) or not bs or any(not isinstance(b, list) or len(b) != 2 for b in bs):
                raise ValueError("bands must contain [inclusive_minimum, points] pairs")
            lows = [number(b[0]) for b in bs]
            if len(lows) != len(set(lows)):
                raise ValueError("duplicate band threshold")
            vals = [b[1] for b in bs]
        elif kind == "linear":
            if number(f.get("to")) <= number(f.get("from")):
                raise ValueError("linear to must exceed from")
            vals = []
        else:
            raise ValueError("kind must be map, bands, or linear")
        vals += [f.get("none_score")]
        if any(not 0 <= number(v) <= 100 for v in vals):
            raise ValueError("factor points must be within 0..100")
        mods = f.get("modifiers", {})
        if not isinstance(mods, dict) or any(k != key(k) for k in mods):
            raise ValueError("invalid modifiers")
        for v in mods.values():
            number(v)
        if "allow_saturated_count" in f and not isinstance(f["allow_saturated_count"], bool):
            raise ValueError("allow_saturated_count must be boolean")
    if not math.isclose(math.fsum(weights), 100, abs_tol=1e-8, rel_tol=0):
        raise ValueError("weights must sum to 100, without rounding or normalization")
    gs = rubric.get("grades")
    if not isinstance(gs, list) or not gs:
        raise ValueError("grades required")
    mins, labels = [], []
    for g in gs:
        mins.append(number(g.get("min")))
        labels.append(g.get("label"))
    if any(not isinstance(x, str) or not x.strip() for x in labels) or len(set(labels)) != len(labels):
        raise ValueError("grade labels must be unique and nonempty")
    if len(set(mins)) != len(mins) or min(mins) != 0 or max(mins) > 100:
        raise ValueError("grades need unique minima starting at zero, up to 100")
    if rubric.get("missing_policy") not in ("hold", "score_none"):
        raise ValueError("explicit missing_policy required")
    if not 0 <= number(rubric.get("min_weighted_coverage")) <= 100:
        raise ValueError("coverage threshold must be within 0..100")
    return rubric


def factor_score(spec, value):
    if spec["kind"] == "map":
        k = key(value)
        if k not in spec["map"]:
            raise ValueError("unrecognized category: " + k)
        return number(spec["map"][k])
    n = number(value)
    if spec["kind"] == "bands":
        bands = sorted(spec["bands"], key=lambda b: number(b[0]), reverse=True)
        for lo, points in bands:
            if n >= number(lo):
                return number(points)
        raise ValueError("value below lowest defined band")
    return min(100.0, max(0.0, (n - number(spec["from"])) / (number(spec["to"]) - number(spec["from"])) * 100))


def safe_saturated_count(spec, value):
    # Hitting a page limit alone does not establish the highest score.
    if spec["kind"] != "bands" or not spec.get("allow_saturated_count", False):
        return False
    bands = sorted(spec["bands"], key=lambda b: number(b[0]))
    points = [number(b[1]) for b in bands]
    return points == sorted(points) and number(value) >= number(bands[-1][0])


def score(rubric, account):
    validate_rubric(rubric)
    aid = str(account.get("account_id") or "").strip()
    as_of = str(account.get("score_as_of") or "").strip()
    expected, matched = domain(account.get("domain")), domain(account.get("matched_domain"))
    out = {"account_id": aid, "domain": expected, "rubric_version": rubric["version"],
           "score_as_of": as_of, "account_fit_score": None, "account_fit_grade": None,
           "scoring_status": "held", "weighted_coverage": 0.0, "components": {},
           "evidence": {}, "blocking_inputs": [], "account_fit_reason": ""}

    def hold(reasons, coverage=0):
        out.update(blocking_inputs=reasons, weighted_coverage=round(coverage, 2),
                   account_fit_reason="Held: " + "; ".join(reasons))
        return out

    if not aid or not as_of:
        return hold(["account_id and fixed score_as_of are required"])
    aliases = {domain(v) for v in account.get("approved_domain_aliases", []) if domain(v)}
    if not expected or not matched or account.get("identity_status") != "matched" or matched not in ({expected} | aliases):
        return hold(["company identity unresolved or mismatched"])
    review = account.get("review_reasons", [])
    if not isinstance(review, list) or any(not isinstance(v, str) or not v.strip() for v in review):
        return hold(["review_reasons must be an array of nonempty strings"])
    if review:
        return hold(review)
    factors = account.get("factors") or {}
    parts, evidence, problems, weighted, coverage = {}, {}, [], 0.0, 0.0
    for f in rubric["factors"]:
        fid, w = f["id"], number(f["weight"])
        if w == 0:
            continue
        obs = factors.get(fid)
        if not isinstance(obs, dict):
            problems.append(fid + ": not wired")
            continue
        status = obs.get("status")
        ev = str(obs.get("evidence") or "").strip()
        src = str(obs.get("source") or "").strip()
        if not ev or not src:
            problems.append(fid + ": source and evidence required")
            continue
        if status not in ("found", "none", "capped"):
            problems.append(fid + ": " + str(status or "not wired") + "; " + ev)
            continue
        try:
            if status == "none":
                if rubric["missing_policy"] == "hold":
                    raise ValueError("no observation")
                s = number(f["none_score"])
            else:
                value = obs.get("value")
                if value is None or value == "":
                    raise ValueError("found without a value")
                if status == "capped" and not safe_saturated_count(f, value):
                    raise ValueError("incomplete results can change points")
                s = factor_score(f, value)
            flags = obs.get("flags", [])
            if not isinstance(flags, list) or any(not isinstance(v, str) for v in flags):
                raise ValueError("flags must be an array of strings")
            if status == "none" and flags:
                raise ValueError("no modifiers on a missing observation")
            for flag in sorted(set(key(v) for v in flags)):
                if flag not in f.get("modifiers", {}):
                    raise ValueError("unrecognized modifier: " + flag)
                s += number(f["modifiers"][flag])
            s = min(100.0, max(0.0, s))
            if status != "none":
                coverage += w
            contribution = s * w / 100
            weighted += contribution
            parts[fid] = {"name": f["name"], "points": s, "weight": w,
                          "contribution": contribution, "status": status}
            evidence[fid] = dict(obs)
        except ValueError as e:
            problems.append(fid + ": " + str(e))
    if coverage + 1e-8 < number(rubric["min_weighted_coverage"]):
        problems.append("usable evidence below coverage threshold")
    if problems:
        return hold(problems, coverage)
    # Grade uses the unrounded total. Display rounding cannot promote a boundary row.
    grade = next(g["label"] for g in sorted(rubric["grades"], key=lambda g: number(g["min"]), reverse=True)
                 if weighted >= number(g["min"]))
    strongest = max(parts, key=lambda k: parts[k]["contribution"])
    weakest = min(parts, key=lambda k: parts[k]["contribution"])
    out.update(account_fit_score=round(weighted, 2), account_fit_grade=grade, scoring_status="scored",
               weighted_coverage=round(coverage, 2), components=parts, evidence=evidence,
               account_fit_reason=(grade + ". Strongest: " + parts[strongest]["name"] + " (" + evidence[strongest]["evidence"]
                                   + "). Weakest: " + parts[weakest]["name"] + " (" + evidence[weakest]["evidence"] + ")."))
    return out


def handler(context):
    rubric = context.get_input("rubric_json")
    account = context.get_input("account_json")
    rubric = json.loads(rubric) if isinstance(rubric, str) else rubric
    account = json.loads(account) if isinstance(account, str) else account
    result = score(rubric, account)
    return {"result_json": json.dumps(result, allow_nan=False, sort_keys=True),
            "scoring_status": result["scoring_status"], "rubric_version": str(result["rubric_version"])}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: score_account.py rubric.json accounts.json")
    with open(sys.argv[1], encoding="utf-8") as f:
        rubric = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        accounts = json.load(f)
    print(json.dumps([score(rubric, a) for a in accounts], indent=2, allow_nan=False))
