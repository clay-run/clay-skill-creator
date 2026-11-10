"""Pick the operating root of an account family. Deterministic, zero credits.

Paste into a Clay code node (Python, `handler(context)`) placed after the hierarchy enrichment
(`cpj-enrich-company-hierarchies`) and the Resolve node. Inputs: `hier_result` (the hierarchy action's
`$.result`), `resolved_domain`, `bare_domain`, `resolved_name`. Output: `root_domain` and `root_name`
(what every research node and the Score node should run on), `is_child`, `ultimate_parent` (a label
for the CRM), `family_root`, `hierarchy_status`, `hierarchy_note`.

The rule (Clay Ops Rules, Hierarchy): a parent and its subsidiaries are one family and the Ultimate
Parent's headcount sets the segment, EXCEPT holding companies and investors, whose subsidiaries run
independently. Measured on a live run: the provider returned a venture investor as a well-known
developer platform's parent, which would have scored the account on the investor. So an investor or
holding company is never a root: the account stays its own root and the note says why.

Local use: `python3 pick_root_domain.py` runs the self-test. Stdlib only.
"""

HOLDCO = ("private equity", "venture", "ventures", "capital", "partners", "investment", "investments",
          "investors", "holding", "holdings", "equity", "management", "fund", "funds", "advisors",
          "advisers", "asset")
# Domains of investors the provider has returned as "parents". Extend it for your market; a miss only
# means an account is scored on its investor until you add the domain here.
INVESTOR_DOMAINS = {
    "coatue.com", "sequoiacap.com", "a16z.com", "tigerglobal.com", "softbank.com", "accel.com",
    "benchmark.com", "greylock.com", "lsvp.com", "indexventures.com", "kleinerperkins.com",
    "generalcatalyst.com", "insightpartners.com", "thrivecap.com", "iconiqcapital.com", "foundersfund.com",
    "bvp.com", "battery.com", "khoslaventures.com", "nea.com", "gv.com", "ycombinator.com", "dragoneer.com",
    "altimeter.com", "d1capital.com", "kkr.com", "blackstone.com", "vistaequitypartners.com",
    "thomabravo.com", "silverlake.com", "tpg.com", "carlyle.com", "warburgpincus.com", "generalatlantic.com",
    "hf.com", "baincapital.com", "goldmansachs.com", "jpmorgan.com", "morganstanley.com",
}


def _is_investor(domain, name):
    return domain in INVESTOR_DOMAINS or any(k in (name or "").lower() for k in HOLDCO)


def _domain_fits_name(dom, name):
    """A parent whose domain does not look like its name (a LinkedIn shortlink such as 5tran.co for Fivetran, measured on
    a live run) would send every provider to a domain they do not know; such a parent keeps its label but not its domain."""
    label = "".join(ch for ch in (dom or "").split(".")[0].lower() if ch.isalnum())
    n = "".join(ch for ch in (name or "").lower() if ch.isalnum())
    tokens = [t for t in "".join(ch if ch.isalnum() else " " for ch in (name or "").lower()).split() if len(t) >= 3]
    return bool(label) and bool(n) and (label in n or n in label or label[:4] in n or any(t in label for t in tokens))


def pick_root(hier, own_domain, own_name):
    own_domain = (own_domain or "").lower().strip()
    own_name = own_name or own_domain
    status = (hier or {}).get("result_status") or "none"
    parents = (hier or {}).get("parent_companies") or []
    root = None
    if status == "found" and parents:
        # The ultimate parent is the company furthest above the input; skip investors and holdcos.
        for p in sorted(parents, key=lambda p: (p.get("distance_from_input_company") or 0), reverse=True):
            dom = (p.get("domain") or "").lower().strip()
            if not dom or dom == own_domain or _is_investor(dom, p.get("name")):
                continue
            root = p
            break
    if root and not _domain_fits_name(root["domain"], root.get("name")):
        label = f"{root.get('name') or root['domain']} ({root['domain']})"
        return {"root_domain": own_domain, "root_name": own_name, "is_child": True, "ultimate_parent": label,
                "family_root": root["domain"], "hierarchy_status": status,
                "hierarchy_note": f"Child of {label}, but the parent's domain does not match its name (likely a shortlink); enriched and scored on the account's own domain."}
    if root:
        label = f"{root.get('name') or root['domain']} ({root['domain']})"
        return {"root_domain": root["domain"], "root_name": root.get("name") or root["domain"], "is_child": True,
                "ultimate_parent": label, "family_root": root["domain"], "hierarchy_status": status,
                "hierarchy_note": f"Child of {label}; enriched and scored on the parent."}
    return {"root_domain": own_domain, "root_name": own_name, "is_child": False, "ultimate_parent": "Own root",
            "family_root": own_domain, "hierarchy_status": status,
            "hierarchy_note": "Own root; no operating parent found."}


def handler(context):
    """Clay code-node entry point."""
    hier = context.get_input("hier_result") or {}
    own_domain = context.get_input("resolved_domain") or context.get_input("bare_domain") or ""
    return pick_root(hier, own_domain, context.get_input("resolved_name"))


def _self_test():
    found = {"result_status": "found", "parent_companies": [
        {"domain": "contoso.com", "name": "Contoso", "distance_from_input_company": 1},
        {"domain": "northwindcapital.com", "name": "Northwind Capital Partners", "distance_from_input_company": 2}]}
    o = pick_root(found, "fabrikam.com", "Fabrikam")
    assert o["root_domain"] == "contoso.com" and o["is_child"] and o["ultimate_parent"] == "Contoso (contoso.com)", o
    inv = {"result_status": "found", "parent_companies": [{"domain": "coatue.com", "name": "Coatue Management", "distance_from_input_company": 1}]}
    o = pick_root(inv, "fabrikam.com", "Fabrikam")
    assert o["root_domain"] == "fabrikam.com" and not o["is_child"] and o["ultimate_parent"] == "Own root", o
    o = pick_root({"result_status": "none"}, "Fabrikam.com", None)
    assert o["root_domain"] == "fabrikam.com" and o["root_name"] == "fabrikam.com" and o["hierarchy_status"] == "none", o
    o = pick_root(None, "", "")
    assert o["root_domain"] == "" and o["ultimate_parent"] == "Own root", o
    short = {"result_status": "found", "parent_companies": [{"domain": "5tran.co", "name": "Fivetran", "distance_from_input_company": 1}]}
    o = pick_root(short, "getdbt.com", "dbt Labs")
    assert o["root_domain"] == "getdbt.com" and o["is_child"] and o["ultimate_parent"] == "Fivetran (5tran.co)" and "shortlink" in o["hierarchy_note"], o
    o = pick_root({"result_status": "found", "parent_companies": [{"domain": "atlassian.com", "name": "Atlassian", "distance_from_input_company": 1}]}, "loom.com", "Loom")
    assert o["root_domain"] == "atlassian.com", o
    print("self-test ok")


if __name__ == "__main__":
    _self_test()
