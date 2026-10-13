#!/usr/bin/env python3
"""Check a skill's output before it is returned as complete.

Usage:
    python3 scripts/check-output.py <output file> [--contract scripts/output-contract.json]

The output file is the Markdown (or JSON) the skill produced. The contract next to this
script lists what a complete output holds for this skill. Exit codes:

    0  COMPLETE    every required part is present and filled
    2  INCOMPLETE  something is missing or half empty; the reasons are printed
    1  usage error (no file, unreadable contract)

A skill that gets exit 2 must report the output as incomplete, name each reason, and
never present it as finished. Standard library only, no install needed.
"""
import json, os, re, sys

EMPTY_CELLS = {"", "-", "?", "tbd", "todo", "xxx", "..."}


def load_contract(path):
    with open(path) as f:
        c = json.load(f)
    c.setdefault("required_sections", [])
    c.setdefault("table_sections", [])
    c.setdefault("min_chars", 200)
    c.setdefault("max_empty_cell_share", 0.2)
    c.setdefault("placeholders", ["TODO", "TBD", "lorem ipsum", "[insert", "XXX", "<fill"])
    c.setdefault("json_required_fields", [])
    c.setdefault("json_min_fill", 0.8)
    c.setdefault("json_min_items", 1)
    return c


def split_sections(text):
    sections, current = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            current = m.group(1).strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def table_rows(lines):
    rows = [l for l in lines if l.strip().startswith("|")]
    rows = [r for r in rows if not re.match(r"^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$", r)]
    return rows[1:] if rows else []  # drop the header row


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def check_markdown(text, c):
    problems = []
    if len(text.strip()) < c["min_chars"]:
        problems.append("output is %d characters, under the %d minimum" % (len(text.strip()), c["min_chars"]))
    low = text.lower()
    for p in c["placeholders"]:
        if p.lower() in low:
            problems.append("placeholder text '%s' is still in the output" % p)
    sections = split_sections(text)
    for req in c["required_sections"]:
        key = req.lower()
        hit = [s for s in sections if s == key or s.startswith(key)]
        if not hit:
            problems.append("required section '## %s' is missing" % req)
            continue
        body = "\n".join(sections[hit[0]]).strip()
        if not body:
            problems.append("section '## %s' is empty" % req)
    for req in c["table_sections"]:
        key = req.lower()
        hit = [s for s in sections if s == key or s.startswith(key)]
        if hit and not table_rows(sections[hit[0]]):
            problems.append("section '## %s' should hold a table with at least one row and has none" % req)
    allcells = []
    for name, lines in sections.items():
        for r in table_rows(lines):
            allcells += cells(r)
    if allcells:
        empty = sum(1 for x in allcells if x.lower() in EMPTY_CELLS)
        share = empty / float(len(allcells))
        if share > c["max_empty_cell_share"]:
            problems.append("%d of %d table cells are empty (%.0f percent, limit %.0f percent)"
                            % (empty, len(allcells), share * 100, c["max_empty_cell_share"] * 100))
    return problems, len(sections), len(allcells)


def check_json(data, c):
    problems = []
    items = data if isinstance(data, list) else data.get("items", [data]) if isinstance(data, dict) else []
    if len(items) < c["json_min_items"]:
        problems.append("%d items, expected at least %d" % (len(items), c["json_min_items"]))
    for field in c["json_required_fields"]:
        filled = sum(1 for i in items if isinstance(i, dict) and i.get(field) not in (None, "", [], {}))
        if items and filled / float(len(items)) < c["json_min_fill"]:
            problems.append("field '%s' is filled on %d of %d items, under %.0f percent"
                            % (field, filled, len(items), c["json_min_fill"] * 100))
    return problems, len(items), 0


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    out = argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    cpath = os.path.join(here, "output-contract.json")
    if "--contract" in argv:
        cpath = argv[argv.index("--contract") + 1]
    try:
        c = load_contract(cpath)
        text = open(out).read()
    except (OSError, ValueError) as e:
        print("ERROR: %s" % e)
        return 1
    if out.endswith(".json"):
        problems, n, m = check_json(json.loads(text), c)
    else:
        problems, n, m = check_markdown(text, c)
    if problems:
        print("INCOMPLETE: %d problem(s). Do not present this output as finished." % len(problems))
        for p in problems:
            print("  - " + p)
        return 2
    print("COMPLETE: %d sections, %d table cells checked against %s" % (n, m, os.path.basename(cpath)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
