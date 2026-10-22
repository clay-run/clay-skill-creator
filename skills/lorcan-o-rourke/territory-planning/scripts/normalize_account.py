"""Reference adapter for company headcount + seller-motion evidence.

Pure standard-library code, usable unchanged in a Clay code step. Other rubric
factors need their own reviewed adapters, not guessed field mappings.
Inputs: context_json, company_json, research_json (JSON text or objects).
Outputs: account_json, raw_evidence_json, review_status (all strings).
"""
import datetime
import json
import math
import re
from urllib.parse import urlsplit


def obj(value, name):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError(name + " must be an object")
    return value


def host(value):
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlsplit(text if "://" in text else "https://" + text)
    h = parsed.hostname or ""
    return h[4:] if h.startswith("www.") else h


def moment(value):
    text = str(value or "").strip()
    if not text:
        raise ValueError("date is missing")
    if len(text) == 10:
        return datetime.datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    result = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp needs a timezone")
    return result


def fresh(value, as_of, max_days):
    try:
        observed = moment(value)
        # Research may be observed after midnight on the same fixed scoring day.
        age = (as_of.date() - observed.date()).days
        return 0 <= age <= max_days
    except (TypeError, ValueError, OverflowError):
        return False


def structured(value):
    value = obj(value, "research_json")
    if "structuredOutputs" not in value:
        return value
    inner = obj(value["structuredOutputs"], "structuredOutputs")
    for k, v in inner.items():
        if k in value and value[k] != v:
            raise ValueError("conflicting structured output: " + k)
    return inner


def normalize(context, company, research):
    context = obj(context, "context_json")
    envelope = obj(company, "company_json")
    research = structured(research)
    as_of = moment(context.get("score_as_of"))
    policy = obj(context.get("evidence_policy"), "evidence_policy")
    for k in ("headcount_max_age_days", "motion_max_age_days"):
        v = policy.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(k + " must be an explicit nonnegative number")
    if policy.get("headcount_date_basis") not in ("provider_refresh", "observation"):
        raise ValueError("explicit headcount_date_basis required")
    if policy.get("headcount_band_conflict") not in ("hold", "ignore_with_disclosure"):
        raise ValueError("explicit headcount_band_conflict policy required")
    allowed = context.get("allowed_entity_types")
    if not isinstance(allowed, list) or not allowed or any(v not in ("operating_company", "institution") for v in allowed):
        raise ValueError("allowed_entity_types must explicitly name the supported entity scope")
    aliases = context.get("approved_domain_aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
        raise ValueError("approved_domain_aliases must be an array of strings")
    raw_company = envelope.get("result")
    company = raw_company if isinstance(raw_company, dict) else {}
    expected = host(context.get("domain"))
    matched = host(company.get("domain"))
    approved_hosts = {expected} | {host(a) for a in aliases}
    identity_ok = bool(expected and matched and matched in approved_hosts and "." in expected)
    review, warnings = [], []
    account = {"account_id": str(context.get("account_id") or "").strip(),
               "domain": expected, "matched_domain": matched,
               "identity_status": "matched" if identity_ok else "unresolved",
               "approved_domain_aliases": aliases, "score_as_of": context["score_as_of"],
               "review_reasons": review, "warnings": warnings, "factors": {}}
    if not identity_ok:
        review.append("provider company identity is missing or does not match the input domain")
    provider_name = str(context.get("company_source") or "").strip()
    if not provider_name:
        raise ValueError("company_source must name the actual company action or source")
    date_key = "last_refresh" if policy["headcount_date_basis"] == "provider_refresh" else "observed_at"
    head_date = company.get(date_key)
    source_ref = company.get("url") or company.get("company_id") or company.get("clay_company_id")
    size = {"status": "failed", "value": None, "source": provider_name,
            "evidence": "Company lookup did not return usable headcount evidence.",
            "source_record": str(source_ref or ""), "observed_at": head_date or "",
            "freshness_basis": policy["headcount_date_basis"],
            "retrieved_at": context.get("company_retrieved_at", "")}
    value = company.get("employee_count")
    usable_number = False
    if value is not None and value != "" and not isinstance(value, bool):
        try:
            n = float(str(value).replace(",", ""))
            usable_number = math.isfinite(n) and n >= 0 and n.is_integer()
        except (ValueError, TypeError):
            usable_number = False
    if envelope.get("success") is not True:
        size["evidence"] = "Company success flag is false or not wired; do not infer a successful miss."
    elif value is None or value == "":
        size.update(status="none", evidence="Successful company lookup returned no employee-count observation.")
    elif not usable_number:
        size["evidence"] = "Employee count is not a finite nonnegative integer."
    elif not fresh(head_date, as_of, policy["headcount_max_age_days"]):
        size["evidence"] = "Employee-count freshness is missing, stale or future-dated under the approved policy."
    else:
        n = int(n)
        size.update(status="found", value=n,
                    evidence=str(n) + " employees from " + provider_name + "; date basis: " + policy["headcount_date_basis"] + "; " + str(head_date))
        if policy["headcount_date_basis"] == "provider_refresh":
            warnings.append("Provider refresh is not an employee-count observation date.")
        band = str(company.get("size") or "")
        span = re.fullmatch(r"\s*([\d,]+)\s*-\s*([\d,]+)\s*(?:employees)?\s*", band)
        plus = re.fullmatch(r"\s*([\d,]+)\+\s*(?:employees)?\s*", band)
        conflict = bool(span and not int(span[1].replace(",", "")) <= n <= int(span[2].replace(",", "")))
        conflict = conflict or bool(plus and n < int(plus[1].replace(",", "")))
        if conflict:
            note = "Employee count " + str(n) + " conflicts with provider size band " + band + "."
            if policy["headcount_band_conflict"] == "hold":
                size.update(status="failed", evidence=note + " Review sources; do not choose an exact number from the band.")
            else:
                warnings.append(note + " Exact count retained under the explicit ignore-with-disclosure policy.")
    account["factors"]["size"] = size

    entity = research.get("entity_type")
    audience = research.get("customer_segment")
    motion = research.get("selling_motion")
    source = str(research.get("source_url") or "").strip()
    evidence = str(research.get("evidence") or "").strip()
    observed = str(research.get("observed_at") or "").strip()
    failure = str(research.get("failure_reason") or "").strip()
    perspective_raw = str(research.get("evidence_perspective") or "").strip()
    perspective = perspective_raw.lower()
    # Exact documented formatting alias only, never a substring test for "seller".
    if perspective == "seller only":
        perspective = "seller"
        warnings.append("Mapped the exact formatting alias 'seller only' to 'seller'; raw value retained.")
    consumer_evidence = str(research.get("consumer_sales_evidence") or "").strip()
    business_evidence = str(research.get("business_sales_evidence") or "").strip()
    unresolved_routes = str(research.get("unresolved_sales_routes") or "").strip()
    raw_urls = research.get("source_urls_json", "[]")
    source_issue = ""
    try:
        more_urls = json.loads(raw_urls) if isinstance(raw_urls, str) else raw_urls
        if not isinstance(more_urls, list) or any(not isinstance(u, str) or not u.strip() for u in more_urls):
            raise ValueError("source URL list must contain nonempty strings")
    except (ValueError, TypeError):
        more_urls = []
        source_issue = "Supporting source URL list is malformed."
    source_urls = list(dict.fromkeys(([source] if source else []) + more_urls))
    for url in source_urls:
        parsed = urlsplit(url)
        h = host(url)
        official = h in approved_hosts or any(h.endswith("." + v) for v in approved_hosts if v)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or not official:
            source_issue = "Every supporting URL must be an official target-company source."

    motion_obs = {"status": "failed", "value": None, "evidence": "Research evidence is incomplete.",
                  "source": source, "observed_at": observed,
                  "entity_type": entity, "customer_segment": audience,
                  "selling_motion": motion, "evidence_perspective": perspective,
                  "evidence_perspective_raw": perspective_raw,
                  "consumer_sales_evidence": consumer_evidence,
                  "business_sales_evidence": business_evidence,
                  "unresolved_sales_routes": unresolved_routes, "source_urls": source_urls}
    parsed_source = urlsplit(source)
    source_ok = parsed_source.scheme in ("http", "https") and bool(parsed_source.hostname)
    source_host = host(source)
    official_source = source_host in approved_hosts or any(source_host.endswith("." + h) for h in approved_hosts if h)
    if entity == "unknown" or entity not in ("operating_company", "institution"):
        review.append("entity type is unresolved")
    elif entity not in allowed:
        review.append("entity type " + str(entity) + " is outside the explicitly approved rubric scope")
    if perspective != "seller":
        motion_obs["evidence"] = "Research describes buying/procurement or has no verified seller perspective."
    elif entity not in allowed:
        motion_obs["evidence"] = "Research entity type is unresolved or outside the approved scope."
    elif unresolved_routes:
        motion_obs["evidence"] = "Selling routes remain unresolved: " + unresolved_routes
    elif source_issue:
        motion_obs["evidence"] = source_issue
    elif audience not in ("b2b", "b2c", "mixed"):
        motion_obs["evidence"] = "Customer segment is unknown; self-serve alone does not establish consumer sales."
    elif audience in ("b2c", "mixed") and not consumer_evidence:
        motion_obs["evidence"] = "Consumer sales are not evidenced; free personal/developer use alone cannot establish b2c or mixed."
    elif audience == "mixed" and not business_evidence:
        motion_obs["evidence"] = "Mixed customer segment requires separate business-sales evidence."
    elif audience == "b2c" and business_evidence:
        motion_obs["evidence"] = "Consumer-only customer segment conflicts with observed business sales."
    elif motion == "consumer" and business_evidence:
        motion_obs["evidence"] = "Consumer-only motion conflicts with observed business sales."
    elif not source_ok or not official_source or not evidence:
        motion_obs["evidence"] = "A nonempty evidence statement and target-company source URL are required."
    elif not fresh(observed, as_of, policy["motion_max_age_days"]):
        motion_obs["evidence"] = "Motion evidence date is missing, stale or future-dated."
    elif failure:
        motion_obs["evidence"] = "Research reported a failure: " + failure
    elif motion not in ("sales_led", "self_serve", "hybrid", "consumer"):
        motion_obs["evidence"] = "Selling motion is unknown or outside the approved categories."
    elif motion == "consumer" and audience != "b2c":
        motion_obs["evidence"] = "Consumer-only motion conflicts with the declared customer segment."
    else:
        motion_obs.update(status="found", value=motion, evidence=evidence)
    account["factors"]["motion"] = motion_obs
    return account


def research_inputs(context, company):
    """Preflight before paid research. Invalid configuration fails, never invents a hold."""
    c = obj(context, "context_json")
    e = obj(company, "company_json")
    # Reuse the policy/identity validator, without making a research call.
    a = normalize(c, e, {})
    if not a["account_id"]:
        raise ValueError("stable account_id required before research")
    if a["identity_status"] != "matched" or e.get("success") is not True:
        raise ValueError("verified successful company identity required before research")
    return {"name": str(e["result"].get("name") or a["domain"]),
            "domain": a["domain"], "score_as_of": c["score_as_of"]}


def handler(context):
    c = context.get_input("context_json")
    company = context.get_input("company_json")
    research = context.get_input("research_json")
    account = normalize(c, company, research)
    raw = {"company": obj(company, "company_json"), "research": obj(research, "research_json")}
    return {"account_json": json.dumps(account, allow_nan=False, sort_keys=True),
            "raw_evidence_json": json.dumps(raw, allow_nan=False, sort_keys=True),
            "review_status": "needs_review" if account["review_reasons"] or any(v["status"] != "found" for v in account["factors"].values()) else "ready"}
