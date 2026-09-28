#!/usr/bin/env python3
"""Package contract + deterministic manifest/ZIP export for a generated skill.

Scope discipline: this module implements the PACKAGE SHAPE only. Every content check —
workspace handles, dangling relative references, bare credentials, endpoints, stale action keys —
is delegated to `eval/validators/portability.py`, which already carries four things this would
otherwise reimplement and get wrong at least once:

  * fence masking, so a handle quoted inside a fenced example does not fire
  * URL span masking (1.4.0), so a URL containing digits is not read as a workspace id
  * severity classes, so heuristic evidence reports instead of blocking
  * system-failure separation with the attribution triple

A standalone re-implementation would reproduce at least one of those bugs. It already cost six
`built` skills a false BLOCK once.

DETERMINISM means **content-manifest equality**, not archive-byte equality:
same relative paths, same per-file SHA-256, manifest verification succeeds. Archive bytes are
*additionally* stable here because entry order and timestamps are deliberately normalized — but
the contract a caller may rely on is the manifest, because a ZIP's bytes depend on the writer's
compression library version and that is not something a creator's machine can be held to.

ZIP intake is server-side. This writes files and reads them back; it touches no service.

Usage:
  package_skill.py validate <dir> [--action-catalog <actions.json>]
  package_skill.py manifest <dir>
  package_skill.py zip      <dir> <out.zip>
  package_skill.py verify   <out.zip> [--manifest <manifest.json>]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile

class _MissingDependency(Exception):
    """A hard dependency is absent. Raised at import time, which is BEFORE any handler in
    `__main__` exists — so the import-time call site catches it inline. See below."""


def _validators_dir() -> str:
    """Locate `portability.py`, in either layout this file legitimately lives in.

    SIBLING FIRST, canonical second — and the order is the fix, not a nicety. An earlier version
    only walked up looking for an `eval/validators/` directory, a layout this file does not ship
    in. That made the tool robust in one place and *unusable* where it actually runs, beside
    `portability.py` in the same directory — so the very first command a creator runs died on
    import. Replacing a hard-coded level count with a hard-coded directory
    name is not a fix; both bind to a layout, and the second bound to the one layout the recipient
    does not have.

    Checking the sibling first also means one file serves both trees, so there is no second copy
    to drift.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(here, "portability.py")):
        return here
    d = here
    while True:
        cand = os.path.join(d, "eval", "validators")
        if os.path.isfile(os.path.join(cand, "portability.py")):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            # Mirrors the shim's glibc-loader check: a missing hard dependency fails with a
            # categorical error naming what is absent, not a crash the caller has to parse.
            raise _MissingDependency(
                f"cannot locate portability.py: not beside {os.path.abspath(__file__)}, and no "
                "eval/validators/portability.py in any parent directory. It ships beside this file "
                "— re-download the skill or fetch tools/portability.py from the "
                "clay-skill-creator repository")
        d = parent


# Resolved AT IMPORT TIME, so the `__main__` handler below does not exist yet and cannot catch a
# failure here. An earlier version of this file carried a comment claiming it would — the test
# disproved the comment, not the code. So the envelope is emitted inline, which is what the shim
# does too: it validates its preconditions and dies with the contract BEFORE exec'ing anything.
try:
    _VALIDATORS_DIR = _validators_dir()
except _MissingDependency as _exc:
    print(json.dumps({"error": {"code": "internal_error", "message": str(_exc)}}), file=sys.stderr)
    raise SystemExit(1)

sys.path.insert(0, _VALIDATORS_DIR)

try:
    import portability as P  # noqa: E402
except Exception as _exc:  # a broken dependency is still ours, not the caller's
    print(json.dumps({"error": {"code": "internal_error", "message":
                                f"portability.py found at {_VALIDATORS_DIR} but failed to import: "
                                f"{type(_exc).__name__}: {_exc}"}}), file=sys.stderr)
    raise SystemExit(1)

PACKAGE_VERSION = "skill-package/1.0.0"
MANIFEST_VERSION = "package-manifest/1.0.0"

ROOT_FILE = "SKILL.md"

# An answer sheet, by name or by shape. Deliberately narrow in both directions: the name pattern only
# matches a file that announces itself, and the body pattern requires a top-level `answers:` mapping
# with at least one child — so a reference file that merely discusses answers is untouched, while a
# sheet somebody renamed to `config.yml` is not.
_ANSWER_SHEET_NAME = re.compile(r"(?i)^(?:answers?|answer[-_]sheet|my[-_]answers)\.(?:ya?ml|json|txt)$")
_ANSWER_SHEET_BODY = re.compile(r"(?m)^answers:\s*$\s*^\s+\S+\s*:")

# An ALLOWLIST of supporting directories, per RULE 0b's own lesson applied to paths: a denylist of
# "bad" locations fails the moment someone invents a new one. Widening this is a deliberate edit.
PORTABLE_DIRS = ("references", "scripts")

# THE RESOLVERS THAT APPLY TO EVERY FILE WE PUBLISH, not only to `SKILL.md`.
#
# Two questions wear the same name. SHAPE — is there a `## What good looks like`, is the frontmatter
# a legal taxonomy value — is a question about `SKILL.md` and meaningless for a reference file.
# CONTENT — does this text carry a workspace identifier, a credential, a private endpoint — is a
# question about anything that leaves the author's machine, and a `references/` file leaves it in
# exactly the same package.
#
# Until this existed, `validate` ran the content resolvers over the body ALONE. Measured on a real
# submission: `t_<table-id>`, a live Clay table id, sat in `references/workflow-graph.md`
# and the package returned `verdict: ok` — while the identical string in `SKILL.md` blocked. The
# guide tells creators to push depth into `references/`, so the gap pointed detail straight at the
# one file nothing read.
#
# `unfilled_marker` and `optional_marker` are deliberately NOT here. They report a draft awaiting
# its author, which is a different claim, and a build-notes file legitimately carries `{{handles}}`
# by the page's own design — including them would flag correct work on every workflow-route package.
CONTENT_RESOLVERS = ("workspace_handle", "endpoint")

# The ZIP epoch. Fixed so entry metadata carries no build clock — a timestamp is the usual reason
# two byte-identical trees produce different archives.
FIXED_DATE = (1980, 1, 1, 0, 0, 0)

# Description length — NO CHECK, and the constant that used to live here is retired.
#
# Three versions of one idea, each softer than the last, all wrong:
#
#   1. A 1024 cap asserted as real. It hard-BLOCKED descriptions the platform accepts, and two of
#      the three skills trimmed to satisfy it had already submitted successfully at 1,187 and 1,182.
#   2. A report past 1,187 — the longest length DEMONSTRATED to store intact — on the reasoning that
#      reporting past the edge of the evidence is honest.
#   3. Nothing, which is this.
#
# (2) failed in a way worth recording, because it looked defensible. An observation about the size
# of our own sample reads, to the person receiving it, as a limit. A submission was refused at the
# door with this as the ONLY finding on the package, so a 1,358-character description became the
# leading hypothesis and the creator was told to cut roughly 200 characters. The real cause was the
# injection scan never running locally. The report did not merely fail to help: it produced a
# confident, specific, wrong instruction, because it was the only thing speaking.
#
# A length nobody has sampled is not a length there is evidence against. Same conclusion already
# reached for body word count, for the same reason: no measured limit, no check.


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def walk_package(root: str) -> list[str]:
    """Relative paths of every regular file, sorted. Excludes nothing — an unexpected file must
    surface as a finding, not be silently skipped, or the manifest and the package disagree."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fn in sorted(filenames):
            out.append(os.path.relpath(os.path.join(dirpath, fn), root))
    return sorted(out)


def _description_chars(skill_md: str) -> int | None:
    """Length of the frontmatter description as the form will see it, or None if absent.

    A block scalar (`description: |`) is measured with its lines joined by single spaces, because
    that is what the value becomes once parsed — counting the raw bytes would include the indentation
    and over-report by roughly the line count.
    """
    m = re.match(r"^---\n(.*?)\n---\n", skill_md, re.S)
    if not m:
        return None
    fm = m.group(1)
    block = re.search(r"^description:\s*[|>][-+]?\s*\n((?:[ \t]+.*\n?)+)", fm, re.M)
    if block:
        return len(" ".join(l.strip() for l in block.group(1).rstrip().split("\n")))
    one = re.search(r"^description:[ \t]*(.+)$", fm, re.M)
    return len(one.group(1).strip().strip("\"'")) if one else None


HALT_VOCABULARY = ("sample-review", "spend-approval", "send-approval", "write-approval", "other")


def _check_halts_axis(payload: str, add) -> None:
    """Validate a declared `**Halts**` axis against the closed vocabulary.

    The axis exists so a page can say *this step stops* without a classifier reading step bodies,
    and that only works while every word in it is one the page knows. A word outside the list makes
    the axis unparseable, which drops the page back to guessing from prose — the failure the closed
    list was written to prevent. So an unknown word BLOCKS: it is a one-word edit for the author and
    a silently wrong page for everyone else.

    The case that produced this check: a workflow-derived skill needed one gate covering both the
    spend and the send — which is the shape the flow actually mandates — and wrote `cost-and-send`
    for it, because nothing in the vocabulary looked like it could say that. It can: the step number
    repeats. `Step 3 spend-approval, Step 3 send-approval`. A closed vocabulary that cannot express
    the design it mandates gets widened by whoever hits it first, so the notation carries the case
    and the list stays five words long.

    Deliberately NOT checked: which steps ought to halt. That is the author's declaration, and a
    checker second-guessing it is the classifier this axis replaced.
    """
    payload = payload.strip().lstrip("*").strip()
    payload = re.sub(r"^\s*[—–:-]\s*", "", payload)
    if not payload:
        add("halts_axis_empty", "report",
            "`**Halts**` is declared with nothing after it. Either name the steps that stop — "
            f"`Step 4 spend-approval`, from {', '.join('`' + w + '`' for w in HALT_VOCABULARY)} — "
            "or take the axis out. An empty axis reads on the page as a skill that pauses somewhere "
            "unspecified", ROOT_FILE)
        return

    # `none` is a real declaration and not a missing one — the same reassurance `Writes: nothing`
    # carries, on the axis that says whether a prompt is ever coming.
    if re.fullmatch(r"(?i)(none|nothing|no halts?)\.?", payload):
        return

    # Pairs are found across the whole payload rather than by splitting it, because the separator
    # varies (`,`, `and`, `·`) and a split on `and` shreds any trailing sentence into fragments that
    # each report separately. One pass, one finding per real defect.
    pairs = list(re.finditer(
        r"(?i)\bstep\s+([0-9]+[a-z]?)\s*[—–:-]?\s*`?([A-Za-z][A-Za-z-]*)`?", payload))
    if not pairs:
        if re.search(r"(?i)\bstep\s+[0-9]", payload):
            add("halts_entry_without_word", "report",
                f"`Halts` names a step and not what it waits on: {payload[:60]!r}. One word from "
                f"{', '.join('`' + w + '`' for w in HALT_VOCABULARY)}, directly after the step "
                "number", ROOT_FILE)
        else:
            add("halts_entry_without_step", "report",
                f"`Halts` does not name a step number: {payload[:60]!r}. Each entry is "
                "`Step <n> <word>`, because the page has to point the reader at the step that "
                "stops. A skill that never pauses declares `none`", ROOT_FILE)
        return

    blocked = False
    for m in pairs:
        word = m.group(2).lower()
        if word not in HALT_VOCABULARY:
            blocked = True
            add("halts_word_not_in_vocabulary", "block",
                f"`Halts` declares `{word}` at Step {m.group(1)}, which is not one of "
                f"{', '.join('`' + w + '`' for w in HALT_VOCABULARY)}. The vocabulary is closed so "
                "the page can render *this step stops* without guessing, and an unknown word stops "
                "it parsing the axis at all. **A step that waits on two things repeats rather than "
                "compounding the word** — `Step 3 spend-approval, Step 3 send-approval`, never "
                "`cost-and-send`. One gate carrying both the spend and the send is the shape this "
                "kit asks for; this is how it is written down", ROOT_FILE)

    # Everything the pairs did not account for. Reported only when the words themselves parsed —
    # a rejected word will be rewritten anyway, and two findings for one line is noise.
    if not blocked:
        residue = payload
        for m in reversed(pairs):
            residue = residue[:m.start()] + " " + residue[m.end():]
        residue = re.sub(r"(?i)[,;·.`]|\band\b|\bthen\b", " ", residue).strip()
        if len(residue.split()) > 2:
            add("halts_entry_carries_prose", "report",
                f"the `Halts` axis carries a sentence around the step words: {residue[:60]!r}. The "
                "axis is step numbers and words only — the step title already says why it stops, and "
                "whoever writes the page supplies the sentence. Prose here is either duplicated on "
                "the page or contradicted by it", ROOT_FILE)


def validate(root: str, action_catalog: dict | None = None) -> dict:
    """Package-shape findings plus delegated content findings. `blocking` decides generation."""
    findings: list[dict] = []
    files = walk_package(root)

    def add(kind: str, severity: str, detail: str, path: str | None = None) -> None:
        findings.append({"check": kind, "severity": severity, "detail": detail, "path": path})

    # 1 — exactly one root SKILL.md.
    roots = [f for f in files if f == ROOT_FILE]
    if not roots:
        add("root_skill_md", "block", f"no {ROOT_FILE} at the package root")
    stray = [f for f in files if os.path.basename(f) == ROOT_FILE and f != ROOT_FILE]
    for f in stray:
        add("root_skill_md", "block",
            f"a second {ROOT_FILE} exists at {f}; a package has exactly one, at the root", f)

    # 2 — supporting files live under an allowlisted portable directory, and nowhere escapes.
    for f in files:
        if f == ROOT_FILE:
            continue
        norm = f.replace(os.sep, "/")
        top = norm.split("/", 1)[0]
        if norm.startswith("/") or ".." in norm.split("/"):
            add("portable_path", "block", f"path escapes the package: {f}", f)
        elif "/" not in norm:
            add("portable_path", "block",
                f"{f} sits at the package root; supporting files belong under "
                f"{'/, '.join(PORTABLE_DIRS)}/", f)
        elif top not in PORTABLE_DIRS:
            # "is not an allowlisted supporting directory" described OUR config, not their package;
            # a creator has never seen the allowlist and cannot act on the word. Phrased to match
            # the sits-at-the-root sibling above, so the two read as one rule rather than two.
            add("portable_path", "block",
                f"{f} sits under {top}/; supporting files belong under "
                f"{'/, '.join(PORTABLE_DIRS)}/", f)
        if os.path.islink(os.path.join(root, f)):
            add("portable_path", "block", f"{f} is a symlink; a package carries real files", f)

    body = ""
    if roots:
        with open(os.path.join(root, ROOT_FILE), encoding="utf-8") as fh:
            body = fh.read()

        # 2b — description length. REPORT, never block: the kit must not reject what the
        # marketplace accepts, and a local checker that overrules the platform has authority it does
        # not have. The mirror of an under-recognizing extractor certifying rather than missing — a
        # check stricter than its contract rejects rather than passes, and either way the check wins
        # an argument it should lose.
        # THE LENGTH REPORT IS GONE, and the third failure of one idea is why.
        #
        # A 1024 cap was asserted as real and hard-BLOCKED descriptions the platform accepts. It
        # was softened to a report against the longest length we had DEMONSTRATED, 1,187, on the
        # reasoning that reporting past the edge of the evidence is honest. It is not: an
        # observation about our own sample reads, to the person receiving it, as a limit.
        #
        # Measured cost. A submission was refused at the door and this report was the only finding
        # on it, so the description — 1,358 characters — became the leading hypothesis and the
        # creator was told to cut about 200. The real cause was the injection scan never running
        # locally, found later the same day. The report did not merely fail to help: it produced a
        # confident, specific, wrong instruction, because it was the only thing speaking.
        #
        # There is no known cap at either door. A length we have not sampled is not a length we
        # have evidence against, and a check whose entire content is "we have not seen one this
        # long" is a check with nothing to say. Absent a measured limit, nothing here reports on
        # length — the same conclusion already reached for body word count, for the same reason.
        n = _description_chars(body)
        if n is None:
            add("description_missing", "block",
                f"no `description` in the frontmatter of {ROOT_FILE}; it is what decides when the "
                "skill is chosen, so a skill without one is unreachable", ROOT_FILE)

        # 2b — a declared-inputs section. REPORT, never block, and the severity is the whole point.
        #
        # This exists here rather than only server-side because of WHEN each runs. The server
        # validator runs after submission, so it can tell a REVIEWER that a section is missing; it
        # structurally cannot tell the CREATOR before they send. This one can, which is the only
        # reason a local check earns its place now that the server owns authoritative validation.
        #
        # Never blocking, for a reason that generalises: no check can tell a considered threshold
        # from a hardcoded one, so the section's PRESENCE is mechanical while its QUALITY is not. A
        # blocking check on presence would buy an empty heading, and an empty heading is worse than
        # an absent one because it looks answered. Presence is a nudge; a person reads the content.
        if not re.search(r"(?im)^#{2,3}\s+declared inputs\b", body):
            # THE NEAR MISS FIRST, because "missing" is the wrong word for it and the wrong word
            # costs a rewrite. Observed on a real workflow-route submission: the section existed in
            # full — fourteen rows, every one with a degrade — under `## Step 4 — Declared inputs`.
            # This check said "no section", the agent renamed the heading to satisfy it, and the
            # steps then read 0, 1, 2, 3, <section>, 5, 6. A report that describes present work as
            # absent gets obeyed literally, and the obedient repair left a hole nothing looked at.
            # THE HEADING MUST *END* ON THE PHRASE, not merely contain it, and the first draft of
            # this got it wrong in the way that matters. `.*declared inputs.*` matched
            # `## Step 1 — Elicit the installer's systems (these are declared inputs, ask at install
            # time)` — a step whose parenthetical happens to say the words — and the message then
            # told the creator to retitle THAT heading, which would have deleted a real step and
            # still left the actual section unreadable. Naming the wrong heading is worse than
            # naming none: this report is obeyed literally, as the numbering hole already proved.
            # So: require the phrase to be the heading's subject, and if nothing qualifies, fall
            # through to the plain message rather than pointing at a guess.
            near = None
            for m in re.finditer(r"(?im)^#{2,3}\s+(.*)$", body):
                head = m.group(1).strip().rstrip(":.")
                if re.search(r"(?i)declared inputs$", head):
                    near = m
                    break
            if near:
                add("declared_inputs_heading_not_exact", "report",
                    f"the declared-inputs section is titled `{near.group(1).strip()}`, and the "
                    "extractor matches `## Declared inputs` exactly — so the content is there and "
                    "nothing downstream can see it. Retitle it to `## Declared inputs`. **It is a "
                    "required section rather than a step, so it carries no number — and if you are "
                    "taking a number off it, renumber the steps after it so the sequence stays "
                    "contiguous**", ROOT_FILE)
            else:
                add("missing_declared_inputs", "report",
                    "no `## Declared inputs` section. This is the section that decides whether "
                    "anyone else can run this: every value that is yours rather than theirs — table "
                    "and column ids, auth accounts, and equally the CRM, the ICP, the weights, the "
                    "thresholds, what counts as senior — needs a row saying what they supply and "
                    "what happens without it. A hardcoded threshold is indistinguishable from a "
                    "considered one to every check downstream, so this is the part only you can get "
                    "right. All four worked examples model it", ROOT_FILE)

        # 2b-ii — a gap in the step numbering. Deterministic, and it exists because the repair above
        # created one: a creator told to drop a number from a heading has no reason to think about
        # what that leaves behind, and neither did this file until it happened.
        _steps = [int(m.group(1)) for m in
                  re.finditer(r"(?im)^#{2,3}\s+step\s+([0-9]+)\b", body)]
        if len(_steps) >= 3:
            _seen = sorted(set(_steps))
            _gaps = [n for n in range(_seen[0], _seen[-1]) if n not in _seen]
            if _gaps:
                add("step_numbering_gap", "report",
                    f"the steps run {', '.join(str(n) for n in _seen)} — "
                    f"{'no step ' + ', '.join(str(g) for g in _gaps)}. A reader who sees Step 3 "
                    "followed by Step 5 looks for the missing one, and an installing agent told to "
                    "run the steps in order has to decide whether it lost part of the file. "
                    "Renumber so the sequence is contiguous", ROOT_FILE)

        # 2c — a representative-output section, UNDER THAT EXACT HEADING.
        #
        # Same severity and the same reasoning as 2b: presence is mechanical, quality is not, and a
        # blocking check buys an empty heading. But this one carries a second finding 2b does not
        # need, because the failure it was written from is not absence.
        #
        # Counted across all 39 skills in the library: 39 declared their inputs, 38 carried a worked
        # example, and ZERO used a heading the marketplace page's extractor reads for representative
        # output. So on 38 of 39 pages the extractor found nothing, fell back to a model, and had it
        # rewrite an output table that was sitting in the file under some other heading. The tables
        # existed. The heading did not. That is why the second finding fires on a body that has a
        # table SOMEWHERE and no `## Representative output`: a creator in that state has already done
        # the work and is one heading away, which is a far more useful thing to be told than that a
        # section is missing.
        #
        # A table is a pipe row followed by a delimiter row. Requiring the delimiter is what keeps
        # ordinary prose containing a `|` from matching.
        #
        # AND THE SEARCH SKIPS `## Declared inputs`, which is the whole difficulty. That section is
        # a table in 39 of 39 files, so "this file has a table" is trivially true everywhere and a
        # naive version of this check fired the table-exists branch on all 39 — the same defect it
        # was written to describe, reproduced one layer up. Sectioning the body first is the fix: the
        # question is whether a table exists that is a CANDIDATE for being the output, and the
        # inputs table never is.
        if not re.search(r"(?im)^#{2,3}\s+representative output\b", body):
            _TABLE = re.compile(r"(?m)^\s*\|.*\|\s*$\n\s*\|[\s:|-]+\|\s*$")
            _SKIP = re.compile(r"(?i)^\s*declared inputs\b|answer sheet")
            candidate = False
            # Split on top-level headings, keeping each heading with its body.
            parts = re.split(r"(?m)^(#{2,3}\s+.*)$", body)
            # parts[0] is anything before the first heading; then heading/body pairs.
            if _TABLE.search(parts[0]):
                candidate = True
            for i in range(1, len(parts) - 1, 2):
                head = parts[i].lstrip("#").strip()
                if _SKIP.search(head):
                    continue
                if _TABLE.search(parts[i + 1]):
                    candidate = True
                    break
            # THE MESSAGE STATES THE FACT AND NOT THE GUESS, and this is load-bearing. The table it
            # found may not be the output one: `hiring-radar` matched a provider-comparison table,
            # `renewal-risk-radar` matched its real output table sitting under `## Worked example`.
            # "There is a table and no heading" is true in both cases; "your output table is at line
            # N" would be wrong in the first. Do not improve this into naming the table it found.
            if candidate:
                add("output_table_not_under_heading", "report",
                    "there is a table in this file but no `## Representative output` heading, so the "
                    "marketplace page cannot tell which table is your output and will generate its "
                    "own example instead of showing yours. Move the output table under a heading "
                    "spelled exactly `## Representative output` and the page renders it as written. "
                    "That is one line of work, and it is the difference between your columns on the "
                    "page and a generated sentence in their place", ROOT_FILE)
            else:
                add("missing_representative_output", "report",
                    "no `## Representative output` section. Everything else the marketplace page "
                    "needs it reads off this file; what it cannot read off this file is what a "
                    "plausible score, evidence sentence or exclusion reason looks like in your "
                    "domain — so without this section something else invents them. Give the literal "
                    "table: headers, then two or three rows of transparently invented data "
                    "(`Northwind`, `Contoso`), never real rows. If the output is prose rather than "
                    "rows, write one filled instance instead of a bracketed frame — an empty frame "
                    "has been rendered on a live page verbatim, brackets and all", ROOT_FILE)
        else:
            # 2d — the section EXISTS, so check its internal shape. One `###` block per thing the
            # installer receives, because the page needs an artifact COUNT and cannot get one from a
            # table's column count.
            #
            # This is the fix for a modelling error rather than a missing field: "the columns of the
            # output table" and "the things the skill delivers" were treated as one concept and are
            # not. A five-column table under one heading is ONE artifact with five fields. A skill
            # delivering a ranked list plus a coverage line was written up as eight peer outputs,
            # which were the fields and sub-reports of a single deliverable wearing the shape of
            # eight. So blocks carry the count and columns never do.
            #
            # Three rejections, each because it makes the count unknowable rather than because it
            # looks untidy: no label at all, a label used twice, and a label with nothing under it.
            sect = re.split(r"(?im)^#{2}\s+representative output\b[^\n]*\n", body, maxsplit=1)[1]
            sect = re.split(r"(?m)^#{1,2}\s+\S", sect)[0]
            blocks = re.split(r"(?m)^#{3}\s+(.+)$", sect)
            labels = [b.strip() for b in blocks[1::2]]
            bodies = blocks[2::2]
            if not labels:
                # Unlabelled is legal for a single-artifact skill and only then, so this reports
                # rather than blocks: the common case is one table, and demanding a heading over it
                # would be ceremony. It matters the moment there are two.
                #
                # COUNT CHUNKS, DO NOT PATTERN-MATCH "TABLE THEN SOMETHING". The first version of
                # this used a regex for a table followed by further content, and a single multi-row
                # table tripped it, because the row-repeat group can match zero rows and then read
                # the next row of the SAME table as the following content. Splitting on blank lines
                # and counting what is left cannot make that mistake.
                chunks = [c for c in re.split(r"\n\s*\n", sect.strip()) if c.strip()]
                if len(chunks) > 1:
                    add("representative_output_unlabelled_blocks", "report",
                        "`## Representative output` holds more than one thing and none of them is "
                        "labelled, so the page cannot tell whether this is one artifact or several. "
                        "Put a `### ` heading over each thing the installer receives. Columns are "
                        "not deliverables: five columns under one heading is one artifact with five "
                        "fields", ROOT_FILE)
            else:
                dupes = sorted({l for l in labels if labels.count(l) > 1})
                if dupes:
                    add("representative_output_duplicate_label", "block",
                        f"`## Representative output` uses the heading {dupes[0]!r} more than once, so "
                        "two different artifacts arrive under one name and whichever renders second "
                        "silently replaces the first. Give each block a heading no other block in "
                        "the section repeats", ROOT_FILE)
                empty = [l for l, b in zip(labels, bodies) if not b.strip()]
                if empty:
                    add("representative_output_empty_block", "block",
                        f"the `### {empty[0]}` block under `## Representative output` has a heading "
                        "and nothing under it, which reads on the page as a promised artifact that "
                        "was never described. Fill it in with the literal output, or take the "
                        "heading out", ROOT_FILE)

            # 2d-ii — RAW ENUM TOKENS IN THE TABLE CELLS, which is the one readability defect that
            # is mechanical rather than a matter of taste.
            #
            # This section is the only part of the file read by a person CHOOSING rather than an
            # agent RUNNING, and it is the part most likely to be written for the author's own
            # reviewer. A cell reading `QUALIFIED_FOR_REVIEW` is a log line: the reader cannot tell
            # whether it is good news without going back to a step they have not read.
            #
            # Found the way everything here gets found — by writing a bad one. A proposed
            # improvement to a live submission came back with the verdict enum in every row, a
            # two-source floor, an unmatched identity and a sentence about uncalibrated
            # coefficients, and the owner's response was that it was unreadable and inside-baseball.
            # The enum still belongs in the file; it belongs ONCE, beside the table, not in every
            # cell of it.
            #
            # SCREAMING_SNAKE only, and that narrowness is the point. Lowercase `mid_market` is a
            # literal output value an installer configured and reads fine; `RESEARCH_REQUIRED` is a
            # constant addressed to a machine. Four characters minimum so `CRM`, `ICP`, `TAM`, `API`
            # and `URL` do not trip it, and a lone all-caps word is not a token either.
            enum_cells = set()
            for line in sect.splitlines():
                if not line.lstrip().startswith("|"):
                    continue
                for cell in line.split("|"):
                    for tok in re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", cell):
                        if len(tok) >= 5:
                            enum_cells.add(tok)
            if enum_cells:
                shown = ", ".join(sorted(enum_cells)[:3])
                add("representative_output_raw_enum_in_cells", "report",
                    f"the table(s) under `## Representative output` put machine constants in the "
                    f"cells ({shown}). This section is the one part of the file read by a person "
                    f"deciding rather than an agent running, and a cell reading like a log line "
                    f"makes them go and find a step they have not read. State the enum ONCE beside "
                    f"the table — \"the first table is X, the second is Y, and those are the only "
                    f"two verdicts\" — and let the rows say what happened in words. Lowercase "
                    f"literal values an installer configured are fine and do not trip this",
                    ROOT_FILE)

        # 2e — the steps that stop must be DECLARED. Reported, never blocking, and only for skills
        # that plainly have a gate to declare.
        #
        # The alternative is a classifier reading step bodies for approval language, and a page that
        # says a step waits for approval when it does not is worse than a page that says nothing.
        # So the check never guesses which steps halt: it asks whether a file with gate language
        # anywhere in it has told anyone which steps those are.
        #
        # A boundary is not a halt. A step that drafts instead of sending declines to act rather
        # than pausing, and that fact belongs in `Never`, which is why the message says so.
        if re.search(r"(?im)^#{2,3}\s+what this skill touches\b", body):
            halts_line = re.search(r"(?im)^\s*[-*]\s*\*\*Halts\*{0,2}\s*(.*)$", body)
            if halts_line:
                _check_halts_axis(halts_line.group(1), add)
            else:
                gateish = re.search(
                    r"(?i)\b(wait for approval|waits for approval|then wait|get approval|"
                    r"before (?:any )?spend|approval gate|ONE gate|the gate)\b", body)
                if gateish:
                    add("undeclared_halts", "report",
                        "this skill stops and waits for a person somewhere, and "
                        "`## What this skill touches` does not say where. Add a `**Halts**` line "
                        "naming the step numbers and what each waits on, from `sample-review`, "
                        "`spend-approval`, `send-approval`, `write-approval`, `other` — for example "
                        "`**Halts** — Step 4 spend-approval`. Without it the marketplace page has to "
                        "guess which steps pause, and a page that promises an approval prompt that "
                        "never comes is worse than one that stays silent. A step that drafts instead "
                        "of sending is not a halt: it declines to act, and that belongs in `Never`",
                        ROOT_FILE)

        # 2f — A SKILL THAT CLAIMS TO BUILD A WORKFLOW MUST CONTAIN THE BUILD.
        #
        # `mechanism: workflow` is a promise that installing this skill leaves a workflow running in
        # the installer's own workspace. Measured: the first skill the workflow route produced
        # declared it and derived as `logic-only`, because it said "wire five nodes in dependency
        # order" and never told the agent to create one. And it predates the route: of the six
        # workflow-declaring skills in the library, FOUR derive as something else.
        #
        # Why that is worse than a wrong label. The installing agent reads "score the lead with a
        # deterministic code step", scores the lead in the conversation, and finishes. Building nodes
        # is a write, needs an approval and is more work than doing the task — so the path of least
        # resistance is to do it by hand once, and the unattended machine the workflow existed to be
        # never appears. The page, the description and the frontmatter all still say workflow.
        #
        # BLOCKING, and the argument for blocking a heuristic is that the failure it catches is
        # ACCIDENTAL. A check keyed on vocabulary can be satisfied by adding vocabulary — but nobody
        # was gaming anything here; the route simply emitted a description instead of a build. A
        # gameable check stops accidents perfectly well, and accidents are what this is.
        #
        # So the message names the missing BUILD STEP rather than the words, because a creator who
        # reads "add `code node`" adds two words, and a creator who reads "add a step that creates
        # the nodes" fixes the skill. Derivation is delegated to portability's resolver — one
        # definition of "reads as a workflow", shared with the finding that reports the contradiction.
        declared_mech = re.search(r"(?im)^mechanism:\s*([a-z-]+)\s*$", body)
        if declared_mech and declared_mech.group(1).strip().lower() == "workflow":
            try:
                derived_mech = P._mechanism_from_body(body)
            except Exception:
                derived_mech = None          # a resolver failure is not the creator's finding
            if derived_mech is not None and derived_mech != "workflow":
                add("workflow_declared_without_build_step", "block",
                    f"the frontmatter declares `mechanism: workflow`, which promises that installing "
                    f"this skill leaves a workflow running in the installer's workspace — but the "
                    f"body reads as `{derived_mech}`: no step creates a node. An agent reading a "
                    "description of the shape will do the work inline in the conversation and finish, "
                    "and the unattended workflow never gets built. **Add a Build step** that says why "
                    "it must be a workflow, confirms node syntax on the installed CLI first "
                    "(`clay workflows nodes --help` — never a hardcoded command form), names the "
                    "nodes in dependency order with their edges, and carries the node traps. If the "
                    "skill genuinely runs as agent-side calls, the honest fix is the other one: "
                    "change `mechanism` to `functions` or `logic-only`", ROOT_FILE)

        # 3 — every supporting file must be REFERENCED from the body. This is the mechanical form
        # of "never add supporting files merely to make a package look complete": an unreferenced
        # file is either decoration or dead weight, and both mislead a reader about the package's
        # real surface. The inverse (a reference with no file) is portability's `missing_file`.
        #
        # THE MESSAGE NAMES NO FILE TYPE, DELIBERATELY. The case that prompted this rewrite was a
        # creator packaging an internal notes file, and the temptation was to special-case it and
        # say so. Two reasons not to. The check cannot know what the file IS — only that nothing
        # points at it — so any name it guessed would sometimes be wrong. And "internal record" is
        # OUR word for OUR eval notes: it means nothing to someone who has never seen one, and a
        # finding written in the vocabulary of the tool rather than the reader is a finding they
        # cannot act on. State the fact that is actually known, from their side: they shipped a
        # file their skill never mentions.
        for f in files:
            if f == ROOT_FILE:
                continue
            # A SUBMISSION RECEIPT IN THE PACKAGE IS A CREDENTIAL IN THE PACKAGE, and it needs its
            # own finding rather than being left to `unreferenced_file` below. Both fire, but only
            # this one says the word "secret", and the difference is what a creator does next:
            # `unreferenced_file` invites them to reference it from the body, which would ship the
            # retry secret deliberately.
            #
            # This existed because `submit_skill.py` wrote the receipt beside the SKILL.md rather
            # than beside the package root when submitting by file path — fixed there too. The check
            # stays because the receipts already written that way are sitting in creators' package
            # directories now, and a fix to where new ones go does nothing about those.
            if re.search(r"(?i)\.receipt\.json$", f):
                add("receipt_in_package", "block",
                    f"{f} is a submission receipt and it holds your private retry secret. It must "
                    f"never be inside a package: zipping this directory puts the secret in an "
                    f"archive built for upload. Move it somewhere outside the package folder — you "
                    f"do want to keep it, just not here", f)
                continue
            if f.replace(os.sep, "/") not in body:
                add("unreferenced_file", "block",
                    f"nothing in {ROOT_FILE} points at {f}, so whoever installs this skill gets "
                    f"the file and never opens it. Link to it from the body if it earns its "
                    f"place, or leave it out of the package — a file that ships unread "
                    f"misrepresents what the skill actually is", f)

        # 3a — AN ANSWER SHEET MUST NEVER BE IN THE PACKAGE, and until now nothing checked.
        #
        # THE PROMISE EXISTED WITHOUT THE MECHANISM, which is the exact distinction the promise makes
        # about itself. `SUBMITTING.md` says the sheet is "structurally excluded rather than promised
        # out: a sheet inside a package fails validation before anything can be sent", and the flow
        # repeats it. Measured: a filled sheet at `references/answers.yml`, referenced from the body
        # like any supporting file, validated `ok` with zero findings.
        #
        # The exposure is NEW and the kit created it. Before answer sheets there was no reason for a
        # creator to have a YAML of live CRM field names, table ids and thresholds sitting beside a
        # package. Now the kit tells them to make one, and the only thing standing between that file
        # and a public repository was putting it in the wrong folder — `answers.yml` at the root
        # happens to trip the path contract, `references/answers.yml` does not.
        #
        # SHAPE, NOT JUST NAME. A renamed sheet is still a sheet, so the content test carries the
        # check and the filename is a second way in rather than the only one. Both are narrow: a
        # top-level `answers:` key with at least one child, or a filename that says what it is.
        for f in files:
            if f == ROOT_FILE:
                continue
            looks_named = _ANSWER_SHEET_NAME.search(os.path.basename(f)) is not None
            looks_shaped = False
            if f.lower().endswith((".yml", ".yaml", ".json", ".txt", ".md")):
                try:
                    with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
                        looks_shaped = _ANSWER_SHEET_BODY.search(fh.read(8192)) is not None
                except OSError:
                    looks_shaped = False          # cannot read it, so cannot claim it is one
            if not (looks_named or looks_shaped):
                continue
            add("answer_sheet_in_package", "block",
                f"{f} looks like a filled answer sheet. Those hold real values — field names, table "
                f"ids, thresholds — and a package is published, so shipping one publishes your "
                f"workspace's shape to anyone who installs the skill. It belongs BESIDE the package, "
                f"not inside it: move it one directory up, out of the skill folder, and send it to a "
                f"teammate the way you send any other file. Nothing about it is submitted, and the "
                f"skill still finds it there", f)

    # 3b — PAGE COPY IS NO LONGER THIS FILE'S CONCERN, and the deletion is recorded because an
    # absent check reads as an oversight otherwise.
    #
    # There was a `## Listing` block here: five declared page fields, checked at `report` severity.
    # It existed because page copy used to be mined out of agent-facing prose, and every extraction
    # round found the same defect one layer down. Declaring it fixed that.
    #
    # It is gone because the ownership moved rather than because the problem went away. The
    # marketplace writes the page now, from the skill, for a person; `SKILL.md` is written for an
    # agent end to end. A validator here would be enforcing a contract this repo no longer owns, and
    # the five-field shape was the last thing making one section of an agent-facing file secretly
    # human-facing.
    #
    # DO NOT REINSTATE A PAGE-COPY CHECK HERE. A page that reads badly is a defect for whoever owns
    # the page. If the marketplace ever hands page authorship back, that is a contract change and it
    # arrives with its own checker.

    # 4a — the one PACKAGE-scoped content check, run here because only here are the files on disk.
    #
    # Whether a skill names the Clay command it spends money on is a question about the package, not
    # about `SKILL.md`: a command named in `references/sourcing-arms.md` is named, and two of the five
    # skills this first fired on did exactly that. `check_portability` receives the body alone, so it
    # goes deliberately quiet when the body points at files it cannot see. This is the caller that
    # supplies the rest. A reference we cannot open degrades to the same silence — a check run on text
    # that failed to read is not a check.
    ref_text: str | None = ""
    for rel in files:
        if rel == ROOT_FILE or not rel.lower().endswith((".md", ".txt", ".py")):
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                ref_text += "\n" + fh.read()
        except OSError:
            ref_text = None
            break
    if body and ref_text is not None:
        for fnd in P._resolve_mechanism(body, ref_text):
            findings.append({
                "check": "portability/mechanism", "severity": fnd.severity,
                "detail": fnd.detail[:300], "evidence": fnd.evidence[:120], "line": fnd.line,
            })

    # 4b — THE SAME CONTENT RESOLVERS, OVER EVERY OTHER FILE IN THE PACKAGE.
    #
    # `check_portability` below is handed the body alone, so before this every supporting file was
    # unread by the checks that matter most about it. See CONTENT_RESOLVERS for the shape/content
    # split and for the submission that proved the gap. Findings carry `file`, because "a table id
    # is in this package" is not actionable and "line 257 of references/workflow-graph.md" is.
    # `.py` AND `.json` WERE MISSING FROM THIS LIST, and `scripts/` is the one directory whose whole
    # purpose is to hold them. Found on a real submission — a multi-file package shipping three
    # Python files and a `cascade-config.example.json`, none of which any check here read. That
    # package was clean, and its author had even written his own credential-shaped-field guard into
    # the build script, so nothing leaked. The hole is that his discipline was the only thing
    # standing there: a creator who pasted a live key into an example config would have passed
    # `verdict: ok` with the key in the archive.
    #
    # This is the same gap, one file type later, as the one CONTENT_RESOLVERS records for
    # `references/*.md`: a live table id sat in a reference file and returned ok while the identical
    # string in `SKILL.md` blocked. Fixing it for prose and leaving it open for code re-aims the
    # miss at whatever the guide tells creators to put in `scripts/`.
    #
    # `.example.json` is deliberately NOT exempted. An example config is the most likely place for a
    # real key to be left behind, because it is the file whose job is to be filled in.
    for rel in files:
        if rel == ROOT_FILE or not rel.lower().endswith(
                (".md", ".txt", ".yml", ".yaml", ".py", ".json")):
            continue
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                ref_body = fh.read()
        except OSError:
            # A file we could not open is not a file we checked. Same rule as 4a: silence beats a
            # pass we did not earn, and `portable_path`/`unreferenced_file` already speak to shape.
            continue
        for fnd in P.check_portability(ref_body, [rel], None).findings:
            d = fnd if isinstance(fnd, dict) else getattr(fnd, "__dict__", {})
            if str(d.get("resolver")) not in CONTENT_RESOLVERS:
                continue
            findings.append({
                "check": "portability/" + str(d.get("resolver", "?")),
                "severity": str(d.get("severity", "report")),
                "detail": str(d.get("detail", ""))[:300],
                "evidence": str(d.get("evidence", ""))[:120],
                "line": d.get("line"),
                "path": rel,
            })

    # 4 — delegated content checks. Not reimplemented; see the module docstring.
    #
    # THIS PROJECTION USED TO DROP `remediation` AND CUT `detail` MID-SENTENCE, and both were found
    # by a reviewer reading real output rather than by any test. Twenty-seven Finding constructions
    # in the validator supply a `remediation`; none of it reached anyone, because this dict copied
    # five keys and that was not one of them. A remediation nobody can read is not a remediation —
    # it is a comment in a file the audience never opens.
    #
    # The truncation was the same class of quiet loss. `marketplace_identity`'s detail is 327
    # characters, the cap was 300, so the sentence that names the consequence ended "any provenance
    # marker it writes w". Both fields are authored prose whose length the author already controls,
    # so they are emitted whole; the caps stay only on `evidence`, which quotes matched source text
    # and can be arbitrarily long.
    port = P.check_portability(body, files, action_catalog)
    for fnd in port.findings:
        d = fnd if isinstance(fnd, dict) else getattr(fnd, "__dict__", {})
        findings.append({
            "check": "portability/" + str(d.get("resolver", "?")),
            "severity": str(d.get("severity", "report")),
            "detail": str(d.get("detail", "")),
            "evidence": str(d.get("evidence", ""))[:120],
            "line": d.get("line"),
            "remediation": str(d.get("remediation", "")) or None,
        })
    sysfail = [str(s) for s in (getattr(port, "system_failures", None) or [])]

    # 4c — THE INJECTION SCAN, which until now ran in CI against fixtures and NOWHERE against a
    # creator's actual package.
    #
    # Found the expensive way. A creator's submission was refused at the door for "credential
    # solicitation" — and both local checks passed it, because neither of them is that scan. The
    # door has a rule this tree never ran, so the first person to learn the two disagreed was the
    # creator, told to "remove the exposed credential" from a package that contains none.
    #
    # `injection.py` gets the discriminator right and its own rationale says so: "a skill may
    # legitimately require that the installer has a key configured in their workspace. Configured
    # versus pasted is the line." Run against that submission it returns `verdict: ok`, 0 blocking,
    # 8 entries. So the reference rule already exempts exactly the shape that was refused — and
    # running it here is what makes that difference visible on the creator's machine instead of in
    # a rejection email.
    #
    # EVERY ENTRY, NEVER `SKILL.md` ALONE, per the scanner's own declared scope: "A clean SKILL.md
    # carrying the identical payload in references/notes.md yields 0 findings scanned alone against
    # 12 blocking scanned fully." Findings keep their path, because the scope note requires it.
    #
    # Absence of the scanner is a SYSTEM failure, not a pass. A package that could not be scanned
    # has not been cleared, and saying so beats a clean verdict nobody earned.
    try:
        sys.path.insert(0, _VALIDATORS_DIR)
        import injection as _INJ  # noqa: PLC0415

        entries: dict[str, str] = {}
        for rel in files:
            try:
                with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                    entries[rel.replace(os.sep, "/")] = fh.read()
            except OSError:
                continue
        inj = _INJ.scan_package(entries)
        for f in inj.get("findings", []):
            findings.append({
                "check": "injection/" + str(f.get("pattern_id", "?")),
                "severity": str(f.get("severity", "report")),
                "detail": str(f.get("creator_message") or f.get("label", ""))[:300],
                "evidence": str(f.get("evidence", ""))[:120],
                "line": f.get("line"),
                "path": f.get("path"),
            })
    except Exception as _exc:  # our defect, never the creator's — same channel as a resolver crash
        sysfail.append(
            f"injection scan unavailable ({type(_exc).__name__}: {_exc}); this package has NOT "
            "been cleared for prompt-injection content and the submission door runs that check "
            "independently"
        )

    # `reject` COUNTS. The contract is explicit — the conformance suite's own rules say
    # "expect_blocking is the number of findings with severity block|reject — the number that must
    # stop intake" — and `validators.md` documents `reject` as the MORE severe of the two: tier D,
    # an embedded credential, evidence redacted in the finding. This line counted only "block".
    #
    # So the single worst thing a package can contain returned a clean verdict. Measured on an
    # isolated single-file package carrying one live-shaped project key: `verdict: ok`,
    # `blocking: 0`, with the `reject` finding sitting right there in `findings` being ignored.
    # Pre-existing, in both computations, and found only because extending the content scan to
    # `.py`/`.json` made a planted key show up as `reject` in a package that still passed.
    #
    # A local checker that refuses to transmit a secret is the one job here that cannot be
    # delegated to the server, because a transmitted secret cannot be recalled.
    blocking = [f for f in findings if f["severity"] in ("block", "reject")]
    return {
        "schema": PACKAGE_VERSION,
        "portability": P.attribution() if hasattr(P, "attribution") else {"version": P.VERSION},
        "files": files,
        "findings": findings,
        "blocking": blocking,
        "system_failures": sysfail,
        # A system failure is not a pass and not a content defect: it means a check did not run.
        "verdict": ("blocked" if blocking else "system_failure" if sysfail else "ok"),
    }


def scan_content(root: str, exts: tuple[str, ...] = (".md", ".txt", ".yml", ".yaml")) -> dict:
    """Content checks over a TREE that is not a skill package — e.g. the public projection.

    `validate()` asserts package shape (one root SKILL.md, allowlisted dirs), which a repo does not
    have and should not be forced into. But the content half applies to anything we publish: no
    workspace identifiers, no credentials, no private endpoints. So this runs the delegated
    resolvers over each file and skips the shape rules.

    It keeps `CONTENT_RESOLVERS` and drops the rest, which is what "skips the shape rules" above
    always claimed and did not do: dropping `missing_file` alone left the section-presence resolvers
    running, so scanning any reference file reported `what_good_looks_like` and
    `what_this_skill_touches` as "section absent" — true, meaningless, and two lines of noise per
    supporting file. A sentence in a docstring is not a check; sharing the constant is.

    `missing_file` is dropped here deliberately. It resolves relative references against a package
    manifest, and in a repo a link to a sibling document is correct rather than dangling — keeping
    it would flag every internal cross-link as a defect. Shape and content are different questions;
    this answers only the second.
    """
    findings = []
    scanned = []
    for rel in walk_package(root):
        if not rel.lower().endswith(exts):
            continue
        scanned.append(rel)
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        res = P.check_portability(body, [rel], None)
        for fnd in res.findings:
            d = fnd if isinstance(fnd, dict) else getattr(fnd, "__dict__", {})
            if str(d.get("resolver")) not in CONTENT_RESOLVERS:
                continue
            findings.append({
                "file": rel,
                "check": "portability/" + str(d.get("resolver", "?")),
                "severity": str(d.get("severity", "report")),
                "evidence": str(d.get("evidence", ""))[:120],
                "detail": str(d.get("detail", ""))[:200],
                "line": d.get("line"),
            })
    # `reject` COUNTS. The contract is explicit — the conformance suite's own rules say
    # "expect_blocking is the number of findings with severity block|reject — the number that must
    # stop intake" — and `validators.md` documents `reject` as the MORE severe of the two: tier D,
    # an embedded credential, evidence redacted in the finding. This line counted only "block".
    #
    # So the single worst thing a package can contain returned a clean verdict. Measured on an
    # isolated single-file package carrying one live-shaped project key: `verdict: ok`,
    # `blocking: 0`, with the `reject` finding sitting right there in `findings` being ignored.
    # Pre-existing, in both computations, and found only because extending the content scan to
    # `.py`/`.json` made a planted key show up as `reject` in a package that still passed.
    #
    # A local checker that refuses to transmit a secret is the one job here that cannot be
    # delegated to the server, because a transmitted secret cannot be recalled.
    blocking = [f for f in findings if f["severity"] in ("block", "reject")]
    return {
        "schema": PACKAGE_VERSION,
        "portability": P.attribution() if hasattr(P, "attribution") else {"version": P.VERSION},
        "scanned": scanned,
        "findings": findings,
        "blocking": blocking,
        "verdict": "blocked" if blocking else "ok",
    }


def manifest(root: str) -> dict:
    """Content manifest — the determinism contract.

    `manifest_sha256` digests the canonical (path, sha256) pairs only: not file order as walked,
    not mtimes, not sizes. Two builds of identical content therefore agree even if produced on
    different machines by different ZIP writers.
    """
    entries = []
    for rel in walk_package(root):
        with open(os.path.join(root, rel), "rb") as fh:
            data = fh.read()
        entries.append({"path": rel.replace(os.sep, "/"),
                        "sha256": _sha256(data), "bytes": len(data)})
    canonical = "\n".join(f"{e['path']}\t{e['sha256']}" for e in entries)
    return {
        "schema": MANIFEST_VERSION,
        "files": entries,
        "file_count": len(entries),
        "manifest_sha256": _sha256(canonical.encode()),
    }


def write_zip(root: str, out_path: str) -> dict:
    """Deterministic archive. Entry order sorted, timestamps fixed, compression pinned.

    Byte-stability is a bonus, not the contract — see the module docstring. It is still worth
    having, because a caller diffing two archives should see nothing rather than see noise.
    """
    m = manifest(root)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for e in m["files"]:
            zi = zipfile.ZipInfo(filename=e["path"], date_time=FIXED_DATE)
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3  # fixed, so the writer's OS does not leak into the bytes
            with open(os.path.join(root, e["path"].replace("/", os.sep)), "rb") as fh:
                z.writestr(zi, fh.read())
    with open(out_path, "rb") as fh:
        m["archive_sha256"] = _sha256(fh.read())
    m["archive_path"] = out_path
    return m


def verify_zip(zip_path: str, expected: dict | None = None) -> dict:
    """Recompute the manifest FROM the archive and compare. Reports per-path divergence."""
    entries = []
    with zipfile.ZipFile(zip_path) as z:
        for name in sorted(z.namelist()):
            data = z.read(name)
            entries.append({"path": name, "sha256": _sha256(data), "bytes": len(data)})
    canonical = "\n".join(f"{e['path']}\t{e['sha256']}" for e in entries)
    got = {"schema": MANIFEST_VERSION, "files": entries, "file_count": len(entries),
           "manifest_sha256": _sha256(canonical.encode())}
    if expected is None:
        return {"manifest": got, "verified": None}

    exp_map = {e["path"]: e["sha256"] for e in expected.get("files", [])}
    got_map = {e["path"]: e["sha256"] for e in entries}
    return {
        "manifest": got,
        "verified": got["manifest_sha256"] == expected.get("manifest_sha256"),
        "missing_paths": sorted(set(exp_map) - set(got_map)),
        "extra_paths": sorted(set(got_map) - set(exp_map)),
        "changed_paths": sorted(p for p in set(exp_map) & set(got_map)
                                if exp_map[p] != got_map[p]),
    }


# ── Failure contract, mirrored from the Clay plugin's `bin/clay` bootstrapper ─────────────
#
# That shim emits a JSON error envelope on stderr with a CATEGORICAL exit code on every failure
# path, explicitly so "an agent that branches on the first `clay` invocation sees the same shape
# the binary emits". Ours did the opposite: measured across four failure modes, every one exited
# 1, and three dumped a raw Python traceback. So "your package has a blocking defect", "this tool
# is broken", "you gave me a path that does not exist" and "that file is not a zip" were
# indistinguishable to the caller — and an agent cannot decide whether to fix the skill, fix the
# invocation, or stop.
#
# Codes follow the Clay CLI's own space where the meanings line up, so an agent already branching
# on Clay exit codes needs no new vocabulary:
#
#   0  ok                 clean
#   1  internal_error     THIS TOOL is broken or a dependency is missing. Not the creator's fault.
#   2  validation_error   the INVOCATION is wrong: no such directory, unreadable manifest, not a zip
#   4  blocked            the PACKAGE has blocking findings. Not an error — a verdict, and the one
#                         outcome a creator is expected to act on.
#
# BACKWARDS COMPATIBLE on purpose: 0 still means clean and every failure is still non-zero, so
# `if exit != 0` logic already published in VALIDATION.md keeps working. The codes only ADD the
# ability to tell the cases apart.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_VALIDATION = 2
EXIT_BLOCKED = 4


def _envelope(code: str, message: str, exit_code: int) -> int:
    """Emit the plugin's envelope shape on stderr and return the categorical code.

    Escaping matters for the same reason it does in the shim: messages interpolate paths, and a
    stray quote or backslash would hand the caller invalid JSON at exactly the moment it is trying
    to find out what went wrong.
    """
    print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
    return exit_code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)
    v = sub.add_parser("validate"); v.add_argument("dir"); v.add_argument("--action-catalog")
    sc = sub.add_parser("scan", help="content-only checks over a tree that is not a package")
    sc.add_argument("dir")
    mf = sub.add_parser("manifest"); mf.add_argument("dir")
    z = sub.add_parser("zip"); z.add_argument("dir"); z.add_argument("out")
    vz = sub.add_parser("verify"); vz.add_argument("zip"); vz.add_argument("--manifest")
    a = ap.parse_args()

    def need_dir(d: str) -> int | None:
        if os.path.isdir(d):
            return None
        # A PATH TO `SKILL.md` IS THE COMMONEST WRONG INVOCATION, and the old message was actively
        # misleading: "no such directory: …/SKILL.md" names a path that exists, as a file, so a
        # creator reads it as their file being missing or unreadable. Found by a launch-day
        # walkthrough with the file sitting in `~/Downloads`.
        #
        # `submit_skill.py preview` accepts a bare file and this refused one, so the two halves of
        # the kit disagreed about what a package is — the same defect class as preview not consulting
        # the validator at all. Resolved toward the documented shape rather than by matching
        # preview's leniency: a lone SKILL.md in its own folder IS a package, so use the folder; a
        # SKILL.md sharing a folder with anything else is not, and sweeping that folder in would
        # produce an `unreferenced_file` finding per sibling, which on a Downloads directory is
        # dozens of findings about files the creator never meant to ship.
        if os.path.isfile(d) and os.path.basename(d).lower() == "skill.md":
            parent = os.path.dirname(os.path.abspath(d))
            siblings = [f for f in os.listdir(parent) if not f.startswith(".")]
            if siblings == [os.path.basename(d)]:
                return None
            return _envelope(
                "validation_error",
                f"{d} is a file, and a package is the FOLDER holding it. That folder also holds "
                f"{len(siblings) - 1} other item(s), which would all be treated as part of your "
                f"skill. Put the file in a folder of its own and validate that:\n"
                f"    mkdir -p <slug> && mv {d} <slug>/SKILL.md\n"
                f"    package_skill.py validate <slug>",
                EXIT_VALIDATION)
        # A `.md` FILE UNDER ANY OTHER NAME lands here, and the message above was written for one
        # basename only. Found on the first skill delivered through the workflow route: it wrote
        # `~/Downloads/inbound-lead-router-SKILL.md`, which is the obvious name for a loose file and
        # the one name that could not be validated — the creator got "no such directory" for a path
        # that plainly exists. The delivery now writes a folder; this covers everyone who already
        # has the loose file, and everyone who renames on the way out of a chat.
        if os.path.isfile(d) and d.lower().endswith(".md"):
            return _envelope(
                "validation_error",
                f"{d} is a file, and a package is a FOLDER whose skill file is named exactly "
                f"`SKILL.md` — the name is how the validator, the zip and the marketplace all find "
                f"it. One rename and one folder:\n"
                f"    mkdir -p <slug> && cp {d} <slug>/SKILL.md\n"
                f"    package_skill.py validate <slug>",
                EXIT_VALIDATION)
        return _envelope("validation_error", f"no such directory: {d}", EXIT_VALIDATION)

    def load_json(path: str, what: str):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            raise _BadInvocation(f"{what} not found: {path}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise _BadInvocation(f"{what} is not readable JSON ({path}): {exc}")

    if a.mode in ("validate", "scan", "manifest", "zip"):
        bad = need_dir(a.dir)
        if bad is not None:
            return bad
        # need_dir ACCEPTS a lone `SKILL.md`, so the path has to be rewritten to the folder it
        # accepted. Without this the file path flows on as the package directory and the walk finds
        # nothing, which surfaced as a blocking finding about a package that is actually fine —
        # a worse failure than the confusing message this replaced.
        if not os.path.isdir(a.dir):
            a.dir = os.path.dirname(os.path.abspath(a.dir))

    if a.mode == "validate":
        cat = load_json(a.action_catalog, "action catalog") if a.action_catalog else None
        res = validate(a.dir, cat)
        print(json.dumps(res, indent=1))
        # `blocked` and `system_failure` are DIFFERENT dispositions and now say so. A blocking
        # finding is the creator's to fix; a system failure means a check did not run, which is
        # ours, and neither is "this tool crashed".
        if res["verdict"] == "ok":
            return EXIT_OK
        if res["verdict"] == "system_failure":
            return _envelope("internal_error",
                             "a required check did not run, so this package is unverified rather "
                             "than clean: " + "; ".join(res.get("system_failures") or ["unknown"]),
                             EXIT_INTERNAL)
        return EXIT_BLOCKED
    if a.mode == "scan":
        res = scan_content(a.dir)
        print(json.dumps(res, indent=1))
        return EXIT_OK if res["verdict"] == "ok" else EXIT_BLOCKED
    if a.mode == "manifest":
        print(json.dumps(manifest(a.dir), indent=1))
        return EXIT_OK
    if a.mode == "zip":
        print(json.dumps(write_zip(a.dir, a.out), indent=1))
        return EXIT_OK
    if not os.path.isfile(a.zip):
        return _envelope("validation_error", f"no such file: {a.zip}", EXIT_VALIDATION)
    try:
        exp = load_json(a.manifest, "manifest") if a.manifest else None
        res = verify_zip(a.zip, exp)
    except zipfile.BadZipFile as exc:
        return _envelope("validation_error", f"{a.zip} is not a zip archive: {exc}",
                         EXIT_VALIDATION)
    print(json.dumps(res, indent=1))
    return EXIT_OK if res["verified"] in (True, None) else EXIT_BLOCKED


class _BadInvocation(Exception):
    """The caller gave us something unusable. Distinct from a package defect."""


if __name__ == "__main__":
    try:
        sys.exit(main())
    except _BadInvocation as exc:
        sys.exit(_envelope("validation_error", str(exc), EXIT_VALIDATION))
    except _MissingDependency as exc:
        sys.exit(_envelope("internal_error", str(exc), EXIT_INTERNAL))
    except KeyboardInterrupt:
        sys.exit(EXIT_INTERNAL)
    except Exception as exc:  # noqa: BLE001 — a traceback is not a contract
        sys.exit(_envelope("internal_error", f"{type(exc).__name__}: {exc}", EXIT_INTERNAL))
