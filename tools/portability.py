"""The portability check — ONE check, FIVE resolvers.

    "Does this skill reference something the installer will not have?"

This is the reference implementation, and it runs in three places that must not drift:

  1. THE SUBMISSION DOOR   — server-side, synchronous, rejects before anything is stored
  2. THE REVIEW STAGE      — the same check, emitting findings instead of rejecting
  3. HERE                  — local validation, before you submit anything

`fixtures/` plus `run_conformance.py` are the CONTRACT between those three. A port that passes
the conformance suite is conformant; nothing else counts as evidence. Having two callers
protects against a wiring bypass; only the fixtures protect the shared logic.

Design rules, each of which is load-bearing:

  * DETERMINISTIC EVIDENCE BLOCKS; HEURISTIC EVIDENCE REPORTS. A hard block on a regex over
    English is the one failure mode a creator cannot debug.
  * NO NETWORK, EVER. Not DNS, not HTTP. Endpoint reachability is decided on host SYNTAX
    alone. Sandboxes routinely deny outbound access, so a network-dependent check would be
    non-comparable between callers even if it were safe.
  * THE STALE-ACTION RESOLVER REMAPS, IT DOES NOT BLOCK. That dangling reference points at
    OUR surface, so we hold the mapping. Blocking a creator over our own rename
    would be indefensible.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence

# BOTH MOVE WHEN A RESOLVER IS ADDED, and the first version of R5 moved neither. A new resolver is
# a rules change by this file's own definition — it creates dispositions that did not exist before —
# so a port carrying R5 and a port without it would both have reported `1.4.0` / `1.2`, and
# attribution could not tell them apart. That is the exact question these fields exist to answer,
# and a handoff asking another caller to port R5 needs a version they can assert they did it at.
# BOTH BUMPED 2026-09-26, and the split matters for whoever ports this. `touches_consistency` is a
# NEW RESOLVER, which is a rules change (1.3 -> 1.4): a port that does not implement it is no longer
# conformant, even though nothing it reports blocks. And `_MECH_FUNCTIONS` gained two Clay surfaces,
# which changes derived values on four skills without changing any rule — the implementation half
# (1.5.0 -> 1.6.0). A caller comparing two results across this boundary needs both numbers to tell
# which kind of difference they are looking at.
# 1.7.1: the marketplace_identity prose only. The seven MI conformance cases assert `resolver`,
# `severity`, `evidence_contains` and `expect_blocking` — never `detail` or `remediation` — so
# rewriting those two changes what a reviewer reads and nothing a port is held to. RULESET stays at
# 1.5 for exactly that reason: the rules did not move, the readable half did. Correcting the
# `evidence` string, which still reads "draft carries" on a correctly issued package, IS a ruleset
# change because MI1 and MI2 pin it, and is deliberately not done here.
VERSION = "portability-check/1.7.1"
RULESET_VERSION = "portability-ruleset/1.5"  # the RULES: resolvers, severities, dispositions


def attribution() -> dict:
    """The structured attribution recorded on EVERY result — clean ones included.

    Requiring attribution only when a finding exists is backwards, and one real escape proves
    it: the result that let a broken skill through **looked clean** — `findings: []`,
    `finding_count: 0`. So the zero-finding verdict is precisely where attribution matters —
    without it there is no way to say which validator produced a clean verdict, which was the
    whole point of versioning the check.

    Three components, because they answer different questions:
      ruleset_version       — did the RULES change? (a disposition change)
      implementation_version— did the CODE change? (a bug fix with identical rules)
      fixture_suite_hash    — did the CONTRACT change? The fixtures ARE the contract between
                              the three callers above, so a silent fixture edit
                              is a silent contract change. Hashing them makes that visible.
    """
    return {
        "ruleset_version": RULESET_VERSION,
        "implementation_version": VERSION,
        "fixture_suite_hash": _fixture_suite_hash(),
    }


def _fixture_suite_hash() -> str:
    import hashlib
    import os

    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
    path = os.path.join(here, "conformance.json")
    try:
        with open(path, "rb") as fh:
            return "sha256:" + hashlib.sha256(fh.read()).hexdigest()[:32]
    except OSError:
        pass
    # PUBLIC-DISTRIBUTION FALLBACK. The fixture suite is a corpus of deliberately-bad inputs, so it
    # embeds real-shaped workspace handles — a live table id, our workspace number, a column id and
    # an auth handle. Those must not leave this repo, but a published checker still has to attribute
    # itself or every verdict it gives a creator carries the fail-closed sentinel. So a distribution
    # may ship a one-line digest sidecar instead of the corpus: identical attribution value, none of
    # the corpus content. Read-only, and it changes nothing where the fixture is present.
    try:
        with open(os.path.join(here, "SUITE_SHA256"), encoding="utf-8") as fh:
            token = fh.read().strip()
        if re.fullmatch(r"sha256:[0-9a-f]{32}", token):
            return token
    except OSError:
        pass
    if True:
        # Absent fixtures is reportable state, never a silent empty string. And it must not
        # ride along on a normal ACCEPTED result either: if
        # attribution is required and validation fails closed, an unverifiable build cannot
        # produce an accept. `check_portability` raises this into a SystemFailure, so the
        # disposition becomes `validation_unavailable` — retriable, no domain rows, no blame.
        return "sha256:UNAVAILABLE"

# ─────────────────────────────────────────────────────────────────────────────────────────
# Findings
# ─────────────────────────────────────────────────────────────────────────────────────────

# block  — deterministic, unrunnable for every installer. Intake rejects synchronously.
# reject — deterministic AND a secret is present. Hard stop until parameterized.
# remap  — our surface drifted; we hold the mapping. Never blocks.
# report — heuristic evidence. Surfaced for a human to read. NEVER a rejection.
SEVERITIES = ("reject", "block", "remap", "report")


@dataclass
class Finding:
    resolver: str  # missing_file | workspace_handle | unfilled_marker | optional_marker
    #                | retired_frontmatter
    #                | endpoint | stale_action | third_party_dependency
    severity: str  # one of SEVERITIES
    evidence: str  # the exact matched substring — quoted back, never paraphrased
    line: int  # 1-indexed line in the submitted body
    detail: str  # what the installer will experience
    remediation: str  # what makes it portable
    suggested: str | None = None  # only for remap

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class SystemFailure:
    """OUR defect, never the creator's. A separate channel from `findings`.

    This caught a real defect: a fail-closed design turned a
    resolver exception into a `block`-severity *portability finding*. That blocks the submission
    — correct — but attributes our crash to the creator's skill, so they go hunting for a
    portability problem that does not exist. Internal defects must never become false creator
    rejections. Both channels block; only one blames the creator.
    """

    code: str  # resolver_exception | fixture_suite_unavailable
    detail: str
    component: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Result:
    version: str = VERSION
    findings: list[Finding] = field(default_factory=list)
    system_failures: list[SystemFailure] = field(default_factory=list)

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.severity in ("block", "reject")]

    @property
    def disposition(self) -> str:
        """`validation_unavailable` outranks everything: if the check could not complete, we do
        not know whether the submission is clean, and saying "blocked" would imply we found
        something. Retriable, and it creates no domain rows."""
        if self.system_failures:
            return "validation_unavailable"
        return "blocked" if self.blocking else "ok"

    @property
    def is_portable(self) -> bool:
        # Only a COMPLETED clean check means portable. An incomplete one is not a pass.
        return self.disposition == "ok"

    def as_dict(self) -> dict:
        return {
            "version": self.version,
            # Present on EVERY result, clean or not. Authored here — by the
            # shared component — never claimed by a caller.
            "attribution": attribution(),
            "disposition": self.disposition,
            "retriable": self.disposition == "validation_unavailable",
            "portable": self.is_portable,
            "finding_count": len(self.findings),
            "blocking_count": len(self.blocking),
            "findings": [f.as_dict() for f in self.findings],
            "system_failures": [f.as_dict() for f in self.system_failures],
        }


# ─────────────────────────────────────────────────────────────────────────────────────────
# Line bookkeeping + code-fence masking
# ─────────────────────────────────────────────────────────────────────────────────────────


def _line_of(body: str, index: int) -> int:
    return body.count("\n", 0, index) + 1


def _fenced_spans(body: str) -> list[tuple[int, int]]:
    """Character spans inside ``` fences.

    Fenced blocks are ILLUSTRATIVE, not instructions to the installer's agent — a fenced
    `http://localhost:8080` in an example is not the skill depending on localhost. The fixture
    suite carries code-block false positives; this is the mechanism they exercise.
    """
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    for m in re.finditer(r"^[ \t]*(?:```|~~~).*$", body, re.MULTILINE):
        if open_at is None:
            open_at = m.end()
        else:
            spans.append((open_at, m.start()))
            open_at = None
    if open_at is not None:  # unterminated fence — treat the remainder as fenced
        spans.append((open_at, len(body)))
    return spans


def _in_fence(index: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(a <= index < b for a, b in spans)


# ─────────────────────────────────────────────────────────────────────────────────────────
# R1 — missing local file  (deterministic → block).  The missing-reference resolver.
# ─────────────────────────────────────────────────────────────────────────────────────────

# Relative markdown/text paths with a file extension. Anchored so we do not match bare
# words: requires either a leading ./ or a directory segment.
_EXT = r"(?:md|markdown|txt|json|ya?ml|csv|py|js|ts|sql|sh)"
_REL_PATH = re.compile(
    rf"""
    (?P<path>
        /(?:[\w.-]+/)*[\w.-]+\.{_EXT}          # ABSOLUTE — the author's filesystem
      | (?<![\w/.-])
        (?:
            (?:\.\./)+(?:[\w.-]+/)*[\w.-]+\.{_EXT}   # traversal out of the package
          | (?:\./)?(?:[\w.-]+/)+[\w.-]+\.{_EXT}      # nested relative
          | \./[\w.-]+\.{_EXT}                        # ./file.md
        )
    )
    """,
    re.VERBOSE,
)

_URL_ISH = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://")


def _normalize_ref(raw: str) -> str | None:
    """Normalize a claimed reference to a package-relative path, or None if unsafe/absolute.

    Traversal is NOT silently normalized away: `../secrets.md` escapes the package, so it is
    never resolvable and must surface rather than be rewritten into something that resolves.
    """
    p = raw.split("#", 1)[0].split("?", 1)[0]  # strip anchor / query
    if not p or p.startswith("/"):
        return None
    parts: list[str] = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            return None  # traversal — report, never resolve
        parts.append(seg)
    return "/".join(parts) if parts else None


def _url_spans(body: str) -> list[tuple[int, int]]:
    """Character ranges occupied by URLs, so a path INSIDE one is never read as a package path.

    `_in_fence` is span-membership, not fence-specific, so it is reused verbatim here rather than
    duplicating the logic — one implementation, two callers.
    """
    return [(m.start(), m.end()) for m in _URL.finditer(body)]


def _resolve_missing_files(body: str, manifest: Iterable[str], fences) -> list[Finding]:
    url_spans = _url_spans(body)
    have = set()
    for f in manifest:
        n = _normalize_ref(f)
        if n:
            have.add(n)
    out: list[Finding] = []
    seen: set[str] = set()
    for m in _REL_PATH.finditer(body):
        raw = m.group("path")
        start = m.start("path")
        if _in_fence(start, fences):
            continue
        # Skip paths that are part of a URL (those are R3's business, not R1's).
        #
        # This WAS a 12-character lookback, and it could never work: in
        # `https://raw.githubusercontent.com/clay-run/agent-plugins/main/GETTING_STARTED.md`
        # the host alone is 26 characters, so `https://` is far outside the window and the path
        # component was reported as a package-relative missing file — evidence read
        # `/raw.githubusercontent.com/...`, the URL with its scheme and host shaved off.
        #
        # Consequence, found by a library-wide sweep (2026-08-14): SIX skills already marked
        # `built` carried a BLOCKING finding for one boilerplate line linking to public GitHub
        # docs. A blocking finding means intake rejects, so any creator linking to public
        # documentation would have been told their skill references a missing local file. That is
        # a FALSE CREATOR REJECTION — the precise failure this design exists to avoid, and the fix was
        # nearly applied in the wrong direction by editing six correct skills to satisfy it.
        #
        # A fixed-width lookback cannot bound a hostname, so span-masking replaces it: URL spans
        # are computed once and membership is tested, exactly as fences are.
        if _in_fence(start, url_spans):
            continue
        norm = _normalize_ref(raw)
        key = f"{raw}@{_line_of(body, start)}"
        if key in seen:
            continue
        seen.add(key)
        if norm is None:
            out.append(
                Finding(
                    resolver="missing_file",
                    severity="block",
                    evidence=raw,
                    line=_line_of(body, start),
                    detail="Reference escapes the package (absolute path or `..` traversal); "
                    "it can never resolve on an installer's machine.",
                    remediation="Reference a file inside the package, or inline the content.",
                )
            )
        elif norm not in have:
            out.append(
                Finding(
                    resolver="missing_file",
                    severity="block",
                    evidence=raw,
                    line=_line_of(body, start),
                    # The filename is IN the message, not only in `evidence`. Two of these used
                    # to render as the same sentence twice, with the name in a structured field a
                    # reader had to go dig for. That reasoning stays here; a creator does not need
                    # our defect history in a finding they are trying to act on.
                    detail=f"`{raw}` is referenced but is not in the package. The agent will "
                    "stall or INVENT the content — which looks like success.",
                    remediation=f"Add `{raw}` to the submission, or inline what it says. Keep the "
                    "reference relative and in a code span: an absolute URL is not checkable, so "
                    "this guard cannot see it and a missing file would validate clean.",
                )
            )
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# R2 — workspace-scoped handle
#      structured ids → block   ·   natural-language prose → report
# ─────────────────────────────────────────────────────────────────────────────────────────

# The `{{f_…}}`, `aa_…` and `t_…` forms were added after reading a REAL Clay table's
# `columns get` output (workspace <id>, 2026-08-13). They are not edge cases — they are the
# dominant shape: one 22-column table carried 74 `{{f_…}}` column references and 5 `aa_…`
# auth-account handles. A converter that transcribes formulas verbatim emits nothing BUT
# these, so a check that missed them would pass every table-derived skill unread.
# Clay SYSTEM columns are PORTABLE and must never be flagged. They carry semantic ids
# (`f_created_at`, `f_updated_at`) and exist identically in every table in every workspace,
# whereas user columns carry random ids (`f_<random-id>`). The patterns below already
# skip them because the alphanumeric class stops at the underscore — but that was ACCIDENT,
# not design, so it is pinned by conformance cases and stated here. A future regex tweak that
# starts blocking `{{f_created_at}}` would reject portable skills for referencing a built-in.
_SYSTEM_COLUMN = re.compile(r"^f_[a-z][a-z0-9_]*$")


def is_system_column(column_id: str) -> bool:
    """True for Clay built-ins, which are portable. Exported: the converter needs this too,
    to keep system columns OUT of its dead-column analysis (see the table-to-skill design note)."""
    return bool(_SYSTEM_COLUMN.match(column_id or ""))


_STRUCTURED_HANDLE = [
    # (regex, human label)
    (re.compile(r"\{\{\s*(?P<v>f_[A-Za-z0-9]{8,})\s*\}\}"), "Clay column reference"),
    (re.compile(r"(?<![\w-])(?P<v>f_[A-Za-z0-9]{12,})(?![\w-])"), "Clay column id"),
    (re.compile(r"(?<![\w-])(?P<v>aa_[A-Za-z0-9]{8,})(?![\w-])"), "Clay auth-account handle"),
    (re.compile(r"(?<![\w-])(?P<v>t_[A-Za-z0-9]{8,})(?![\w-])"), "Clay table id"),
    (re.compile(r"\btable[ _-]?(?:id)?\s*[:=#]?\s*(?P<v>\d{5,})\b", re.I), "table id"),
    (re.compile(r"\bcolumn[ _-]?id\s*[:=]?\s*(?P<v>[\w-]{6,})\b", re.I), "column id"),
    (re.compile(r"\bworkspace[ _-]?(?:id)?\s*[:=#]?\s*(?P<v>\d{4,})\b", re.I), "workspace id"),
    (re.compile(r"\bview[ _-]?id\s*[:=]?\s*(?P<v>[\w-]{6,})\b", re.I), "saved-view id"),
    (re.compile(r"https?://app\.clay\.com/\S*?/tables?/(?P<v>[\w-]+)", re.I), "table URL"),
]

# Heuristic prose. Reports only — never blocks. The converter is supposed to have
# parameterized these already; this catches hand-written (mode C) skills, which have no
# converter in the path.
# TWO DEFECTS, one read, 2026-08-20. This check was 100% of the measured noise floor: 6 findings
# across 30 known-good skills, all 6 wrong — "the email column", "the unknown column", "the evidence
# column".
#
# 1. THE TITLE-CASE REQUIREMENT WAS ALREADY HERE AND A FLAG DEFEATED IT. The old pattern demanded
#    `[A-Z]` for the noun phrase, under `(?ix)` — and `i` makes `[A-Z]` match lowercase. So the
#    discriminating condition was written, then silently switched off by a flag added for the
#    keywords. `i` is now scoped to the literals that want it, with `(?i:...)`, and nowhere else.
#
# 2. THE CANONICAL TRUE POSITIVE MATCHED NOTHING. "the Enterprise Accounts view" — the example this
#    check exists for — hit no branch: the view branch requires `the view called "…"`, with the name
#    AFTER the keyword, and real prose puts it before. So the check was firing only on the sentences
#    it should ignore and silent on the one it was built for. Both halves wrong is worse than either.
#
# The rule now, and it is the whole rule: the noun phrase before column/view/table must be QUOTED
# (any case — quoting is itself the author pointing at a named thing) or TITLE CASE THROUGHOUT.
# "the email column" is generic prose about a column; "the Enterprise Accounts view" names an
# artifact. That distinction is mechanical, which is what makes it worth having in a heuristic —
# and it is still `report` severity, because a capital letter is evidence, not proof.
_PROSE_HANDLE = re.compile(
    r"""(?x)
    \b(?:
        (?i:the|your|our|my)\s+
          (?: [`"'][^`"'\n]{2,40}[`"']                       # quoted — any case
            | [A-Z][\w./-]* (?:\s+[A-Z][\w./-]*){0,5}        # Title Case, every word
          )\s+
          (?i:column|view|table)
      | (?i:saved\s+view|the\s+view)\s+ (?i:called|named)\s+ [`"'][^`"'\n]{2,40}[`"']
      | (?i:in\s+(?:the\s+)?table)\s+ [`"'][^`"'\n]{2,40}[`"']
    )
    """
    # NO TRAILING \b, and that is a THIRD defect this rewrite found rather than introduced.
    # Two of these three branches end with a quote character. `\b` after a non-word character
    # requires a word character next, so at end of line — where a quoted name usually sits —
    # the boundary could never be satisfied and the branch could never match. Both quoted
    # branches were dead in the previous pattern for the same reason, which is why the check
    # fired only on the generic-prose branch: the noise floor was 100% of its output because
    # the signal branches were switched off. Each branch now ends on its own literal, which is
    # anchor enough.
)

# Two marker CLASSES, and the split is by executability. Until now `{{OPTIONAL}}`
# failed to match this regex and therefore did not block — correct behaviour, but by ACCIDENT of
# the character class rather than by agreement. Pinned deliberately so a future tweak cannot
# start blocking it, and so unanswered optional context is still visible to a reviewer.
_UNFILLED_MARKER = re.compile(r"\{\{\s*(?:UNKNOWN|TODO|FILL)\b[^}]*\}\}", re.I)
_OPTIONAL_MARKER = re.compile(r"\{\{\s*OPTIONAL\b[^}]*\}\}", re.I)


def _resolve_prose_handles(body: str, fences) -> list[Finding]:
    out: list[Finding] = []
    for m in _PROSE_HANDLE.finditer(body):
        if _in_fence(m.start(), fences):
            continue
        out.append(
            Finding(
                resolver="workspace_handle",
                severity="report",
                evidence=m.group(0).strip(),
                line=_line_of(body, m.start()),
                detail="Reads like a reference to a workspace artifact by name. This is a guess from "
                "wording alone, so it never blocks — if the name is generic prose rather "
                "than a real artifact, ignore it.",
                remediation="If it is a real workspace artifact, make it a declared input.",
            )
        )
    return out


# The frontmatter fields that are read, and the ones that are not. A CLOSED list on purpose: an
# open one cannot tell "a field we retired" from "a field we never had", and both are the same
# problem for a creator — they wrote something nothing consumes.
# TAXONOMY V2. `type` (task|play) and `tags` are retired: `type` was unvalidated free text —
# `type: banana` passed clean — and `tags` was doing three jobs in one bag, mixing what the installer
# brings, what machinery runs, and who it is for. Six skills were tagged `workflow` while building
# no workflow, which is what an unvalidated shared bag produces. Now: `category` (1 of 10),
# `personas` (1-2 of 8), `touches` (derived from the body block, so it cannot drift), `keywords`
# (<=5, managed registry).
LIVE_FRONTMATTER = ("name", "description", "category", "personas", "mechanism", "touches",
                    "keywords")
# `keyword` (singular) was a slug that duplicated `name` on 34 of 36 — but on two it held a search
# SYNONYM (find-work-phone -> find-phone-number, score-inbound-leads -> lead-scoring), which the
# migration nearly deleted. Both were rescued into `keywords`. They belong in the listing block's
# `also asked as` once every skill has one; until then the long tail is the honest home.
RETIRED_FRONTMATTER = ("proof_status", "proof_gaps", "measure_class", "stage_p", "stage_e",
                       "type", "tags", "keyword")

_FRONTMATTER_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:", re.M)

# ─────────────────────────────────────────────────────────────────────────────────────────
# The taxonomy, as VALUES rather than field names.
#
# WHY THESE ARE LITERALS HERE AND NOT READ FROM A FILE. The human-editable registry is three text
# files with the reasoning written beside each list — adding a category is a decision, and a decision
# wants a place to be argued. But that registry does not travel: this validator runs on a creator's
# machine, from inside a package, with no repository above it. A check that needs a file it cannot
# reach is the third state — silent because it could not run, indistinguishable from silent because
# everything passed. So the values are baked in, and a canonical-only control asserts the two copies
# are identical. The registry stays the source a human edits; this is the copy that ships.
#
# WHAT IS *NOT* CHECKED, DELIBERATELY: whether these fields are PRESENT. A creator is told plainly
# that there is no taxonomy homework — they do not pick a category, guess a persona, or invent a
# keyword; those are worked out from what they wrote and confirmed by a person. Reporting absence
# would hand back as a finding the exact work we promised not to ask for. So: a field that is there
# must hold a real value; a field that is not there is not a defect.
TAXONOMY_CATEGORIES = (
    "build-lists", "enrich", "find-contact-data", "paid-ads", "personalize-outbound",
    "research", "route-and-automate", "score-and-qualify", "signals", "verify-and-clean",
)
TAXONOMY_PERSONAS = (
    "account-executive", "founder", "gtm-engineer", "marketing", "recruiter", "revops",
    "sales-development", "sales-leader",
)
# Ordered least-to-most invasive, and that order is the point: it is what lets a filter say "show me
# nothing that writes" without knowing the vocabulary. `writes-own-output` is the middle case that
# v1 had no way to say — a skill that creates its own table or CSV is not read-only, and calling it
# `writes-records` puts it beside one that edits a CRM contact.
TAXONOMY_TOUCHES = ("read-only", "writes-own-output", "writes-records")
# WHAT THE SKILL ACTUALLY RUNS ON, ordered most to least Clay-dependent. The reason this is a facet
# and not a note: measured across 36 published skills, FIVE build a workflow, 24 name a function or a
# routine, and seven name no Clay mechanism at all — and nobody knew that until it was grepped. A
# property that only exists when somebody greps for it is a property nobody manages.
#
# THE FIRST MEASUREMENT SAID ONE WORKFLOW, NOT FIVE, and the gap is the whole argument for reading the
# package instead of the file. Four skills build a workflow and document the node work in
# `references/`, so a `SKILL.md`-only sweep reported them as calling nothing. A number that wrong in
# that direction would have been used to argue the shape is unused, which it is not.
#
# `logic-only` IS A LEGITIMATE VALUE and it is not an accusation. Some jobs are all judgment: given
# these rows, decide. Making Clay usage a gate would push an author to bolt on the cheapest call that
# passes validation, which spends the installer's money to satisfy us. What the check below cares
# about is narrower and fair: a skill that TALKS about credits, providers and waterfalls while naming
# no Clay command at all has claimed a cost it cannot attribute.
TAXONOMY_MECHANISM = ("workflow", "functions", "logic-only")
TAXONOMY_KEYWORDS = (
    "catch-all-domains", "cold-email", "crm-hygiene", "csv", "event-follow-up",
    "find-phone-number", "job-change", "lead-scoring", "livestream", "local-business",
    "plg", "sequencer", "tech-stack", "waterfall", "webinar",
)
MAX_PERSONAS = 2
MAX_KEYWORDS = 5

# The report/block flip, one constant, same shape as TOUCHES_BLOCKS. Reports today for the same
# reason: 30 of the 30 library skills in the canonical tree carry no taxonomy at all yet, and the
# three live external submissions were migrated by hand. Flipping this before the corpus is caught
# up would reject the launch cohort on a field its authors were told not to write.
TAXONOMY_BLOCKS = False

# KEYWORDS ARE EXEMPT FROM THE FLIP, permanently, and that is a policy and not an oversight. The
# other three are closed vocabularies where an unknown value is a typo. Keywords are the managed long
# tail: an unknown one is usually a real term that belongs in the registry, and the fix is a
# one-line commit by whoever reviews it, not a rejected submission. Blocking it would push authors
# toward reusing a term that nearly fits, which is how a long tail turns into a shrug.
_ENUMS = (  # (field, singular noun, allowed values, takes a list, eligible for the block flip)
    ("category", "category", TAXONOMY_CATEGORIES, False, True),
    ("personas", "persona", TAXONOMY_PERSONAS, True, True),
    ("mechanism", "mechanism", TAXONOMY_MECHANISM, False, True),
    ("touches", "posture", TAXONOMY_TOUCHES, False, True),
    ("keywords", "keyword", TAXONOMY_KEYWORDS, True, False),
)
_CAPS = (("personas", MAX_PERSONAS), ("keywords", MAX_KEYWORDS))

# `key: rest-of-line`, top level only. No leading whitespace in the pattern, which is what keeps a
# `description: |` block's indented continuation lines from reading as keys of their own.
_FRONTMATTER_PAIR = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)[ \t]*:[ \t]*(.*)$", re.M)


def _frontmatter_block(body: str) -> tuple[str, int] | None:
    """The frontmatter text and the offset it starts at, or None if there is no block."""
    if not body.startswith("---"):
        return None
    end = body.find("\n---", 3)
    if end == -1:
        return None
    return body[3:end], 3


def _taxonomy_values(body: str) -> dict[str, tuple[list[str], int]]:
    """The taxonomy fields present in the frontmatter, as (values, line).

    Accepts the three shapes YAML allows for a list — `[a, b]`, `a, b`, and a block of `- a` lines —
    because reading a block list as EMPTY would report "no values" on a file that has them, which is
    a worse lie than not checking at all. A scalar field comes back as a one-element list so the
    caller has one code path.
    """
    blk = _frontmatter_block(body)
    if blk is None:
        return {}
    block, base = blk
    lines = block.split("\n")
    starts, pos = [], 0
    for ln in lines:                      # offset of each line within `block`
        starts.append(pos)
        pos += len(ln) + 1
    wanted = {e[0] for e in _ENUMS}   # indexed, so widening the tuple cannot break the reader
    out: dict[str, tuple[list[str], int]] = {}
    for i, ln in enumerate(lines):
        m = _FRONTMATTER_PAIR.match(ln)
        if not m or m.group(1) not in wanted or m.group(1) in out:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        vals = [v.strip().strip("'\"") for v in raw.split(",")]
        vals = [v for v in vals if v]
        if not vals:                      # block list: `key:` then `  - a` lines
            for nxt in lines[i + 1:]:
                s = nxt.strip()
                if s.startswith("- "):
                    vals.append(s[2:].strip().strip("'\""))
                elif s:
                    break
        line = body[:base + starts[i]].count("\n") + 1
        out[key] = (vals, line)
    return out


def _resolve_taxonomy(body: str) -> list[Finding]:
    """A taxonomy field that is present must hold a value the marketplace can actually file under.

    THE DEFECT THIS REPLACES, stated plainly because it is the reason the check exists: `type` was
    free text for the whole of v1. `type: banana` validated clean, published clean, and would have
    become a facet of one. Nothing in the pipeline had an opinion about the value of a field the
    front end filters on. The fields are new; the failure mode is the old one, and renaming a field
    does not fix an unvalidated field.
    """
    sev = "block" if TAXONOMY_BLOCKS else "report"
    found = _taxonomy_values(body)
    out: list[Finding] = []

    for field, noun, allowed, is_list, blocks in _ENUMS:
        if field not in found:
            continue                      # absence is not a defect — see the note above the enums
        vals, line = found[field]
        for v in vals:
            if v in allowed:
                continue
            near = [a for a in allowed if a.startswith(v[:4]) or v in a] if len(v) >= 3 else []
            hint = f" Closest to what you wrote: {', '.join(near[:3])}." if near else ""
            out.append(Finding(
                resolver="taxonomy_value",
                severity=(sev if blocks else "report"),
                evidence=f"{field}: {v}",
                line=line,
                detail=f"`{v}` is not a {noun} the marketplace knows. Browsing filters on these, so "
                       f"an unknown value does not create a new filter — it creates a facet of one "
                       f"that nobody will ever click.{hint}",
                remediation=f"Use one of: {', '.join(allowed)}. If `{v}` is a real term the list is "
                            f"missing, say so rather than reaching for the nearest fit — for a "
                            f"keyword that is the normal path and it is added, and for the other "
                            f"three it is a decision somebody makes on purpose.",
            ))
        if not is_list and len(vals) > 1:
            out.append(Finding(
                resolver="taxonomy_value",
                severity=(sev if blocks else "report"),
                evidence=f"{field}: {', '.join(vals)}",
                line=line,
                detail=f"`{field}` takes exactly one value and this declares {len(vals)}. A skill "
                       f"filed under two categories is a skill that does two jobs, and the honest "
                       f"fix is usually two skills.",
                remediation="Pick the one that describes what an installer came for.",
            ))

    for field, cap in _CAPS:
        if field not in found:
            continue
        vals, line = found[field]
        if len(vals) <= cap:
            continue
        out.append(Finding(
            resolver="taxonomy_value",
            severity=(sev if field == "personas" else "report"),
            evidence=f"{field}: {len(vals)} values, max {cap}",
            line=line,
            detail=f"{len(vals)} `{field}` where the limit is {cap}. The cap is not tidiness: a "
                   f"skill listed for everyone is listed for nobody, because a reader filtering to "
                   f"their own role learns nothing from a result that matches every role.",
            remediation=f"Keep the {cap} that would make someone install it, and drop the rest.",
        ))

    out += _touches_agrees_with_body(body, found)
    return out


def _touches_agrees_with_body(body: str, found: dict[str, tuple[list[str], int]]) -> list[Finding]:
    """`touches:` in the frontmatter versus the `**Writes**` line in the body.

    A CONTRADICTION CHECK, not a truth check, and the difference is the whole design. No regex can
    read a skill and decide whether it writes — that read is an LLM pass in the parser. What a regex
    CAN do is hold two statements by the same author side by side and notice they disagree: the
    frontmatter says `read-only`, the body says it writes to a table you name. One of the two is
    wrong, the author knows which, and neither of them is a judgement we had to make.

    ALWAYS REPORTS, never blocks, even after the flip. The body value is DERIVED from prose, so a
    mismatch can be the derivation's fault rather than the author's — `Writes — nothing to your CRM;
    rows land in your own table` is a correct sentence this reads as read-only. A heuristic that can
    be wrong must not be able to reject a submission.
    """
    if "touches" not in found:
        return []
    declared = found["touches"][0]
    derived = _touches_from_body(body)
    if derived is None or len(declared) != 1 or declared[0] == derived:
        return []
    if declared[0] not in TAXONOMY_TOUCHES:
        return []                         # already reported as an unknown value; one finding is enough
    return [Finding(
        resolver="taxonomy_value",
        severity="report",
        evidence=f"touches: {declared[0]} / body reads as {derived}",
        line=found["touches"][1],
        detail=f"The frontmatter declares `touches: {declared[0]}` and the **Writes** line in "
               f"`## What this skill touches` reads as `{derived}`. Two statements about the same "
               f"thing, by the same author, that do not agree — and the frontmatter is the one the "
               f"marketplace shows to somebody deciding whether to point this at their CRM.",
        remediation="Make them match. If the body is right, correct the frontmatter; if the "
                    "**Writes** line is worded in a way that reads as more (or less) than it does, "
                    "that wording is what an installer reads too.",
    )]


# The **Writes** axis, extracted from the body block. Tolerant about the separator (em dash, en
# dash, colon, hyphen) and about the bullet, because the block is prose an author typed and a
# derivation that only works on one exact rendering is a derivation that mostly returns None.
_TOUCHES_WRITES = re.compile(
    r"(?im)^[\s>*+\-]{0,8}\**[ \t]*writes?\b\**[ \t]*(?:—|–|--|:|-)[ \t]*(.+)$")


# WHAT RUNS THE WORK, read off the body. Three vocabularies, and the exclusion in the first is the
# whole reason this is not a one-line grep: `clay whoami`, `clay plugin` and `clay tools` are PREFLIGHT
# and appear in nearly every skill in the library. Counting them as a mechanism made ten skills that
# name no Clay work at all look Clay-shaped, which is how a naive version of this measurement comes
# back reassuring and wrong.
_MECH_PREFLIGHT = re.compile(r"clay\s+(?:whoami|plugin|tools|is)\b", re.I)
_MECH_WORKFLOW = re.compile(
    r"clay\s+workflows\s+(?:nodes|create|runs|triggers)\b|\bnodes\s+create\b|\bnode\s+graph\b"
    r"|\bmerge\s+node\b|\bcode\s+node\b|\btool\s+node\b", re.I)
# `campaigns` and `tables` were MISSING until 2026-09-26, and the miss was silent in the direction
# that matters. Four skills call Clay through them and nothing else — `clay campaigns analytics`,
# `clay tables rows list`, `clay tables columns list` — so the derivation returned `logic-only`, the
# value that means "needs no Clay account at all". Found on `matteo-fois/kill-or-keep`,
# `matteo-fois/list-clearance`, `matteo-fois/swap-test` and `clay/buyer-classification`, and found
# only because a provenance gate was about to EXEMPT skills on this value. A wrong `logic-only` reads
# as a skill that spends nothing and needs nothing, which is the most load-bearing thing this axis
# says — so an omission here is not a narrower answer, it is the opposite answer.
#
# The general lesson, which is why this comment is longer than the fix: the pattern enumerates
# surfaces, so every surface the CLI grows is a silent false `logic-only` until someone adds it.
# `platform-surfaces.md` names four surfaces; this pattern must cover all of them plus `campaigns`
# and `tables`. Check it against that page when the CLI changes, not against this list.
_MECH_FUNCTIONS = re.compile(
    r"clay\s+(?:routines|functions|search|campaigns|tables|workflows\s+actions)\b"
    r"|\brun_subroutine\w*|\brun_action\b"
    r"|\broutines?\s+(?:get|list|create|runs)\b|\bmanaged\s+function", re.I)
# Money the skill says it will spend. THE PROPERTY IS A QUANTITY, not cost vocabulary, and the first
# version of this got that wrong in a way worth keeping written down. It matched `credit|enrich\w*|
# provider` anywhere in the file and fired on ten of thirty-six — of which ONE was real. The other
# nine were three distinct noise classes, and none of them is a defect:
#
#   1. A BOUNDARY CARVE IN THE DESCRIPTION. "Do NOT use it to enrich raw signups" is a skill
#      being careful about its own boundary, which is the single thing this kit asks for most.
#      Three skills fired on nothing else. (These carves named a sibling slug when this was
#      written; the neighbour map is gone and they now name adjacent JOBS only.)
#   2. AN EXPLICIT ZERO. "CSV dedupe costs zero credits", "Classification itself spends no credits."
#      These are the OPPOSITE of an unattributed cost claim, and flagging them punishes the exact
#      scrupulousness the check is meant to encourage.
#   3. THE TAXONOMY VALUE ITSELF. `category: enrich` in the frontmatter.
#
# The tempting fix was a longer exclusion list. That calibrates the check to today's corpus rather
# than to the property, which is how a check comes to encode "whatever we already wrote". So instead:
# the BODY only (classes 1 and 3 live in the frontmatter), lines that state a zero are skipped
# (class 2), and what remains must name a QUANTITY of money — a number of credits, a per-row price, a
# spend that is reported. "This will cost about 31 credits" with no command named is the defect.
# "Enrichment is not part of this play" never was.
_MECH_ZERO_COST = re.compile(
    r"(?i)\b(?:zero|no|nothing|free|0)\s+credits?\b|\bspends?\s+(?:no|zero)\b"
    r"|\bcosts?\s+(?:nothing|zero)\b|\bcredits?\s*[:=]\s*0\b")
_MECH_COST_CLAIM = re.compile(
    r"(?i)\d[\d,.]*\s*(?:×\s*)?credits?\b|\bcredits?\s*(?:×|/|per\b|spent\b|each\b|consumed\b)"
    r"|\bcreditCost\b|\bpaymentType\b|\bcost\s+per\s+row\b")


# DOES THE PACKAGE CREATE A WORKFLOW? The eligibility predicate for the provenance marker, and it is
# a separate question from `mechanism` — a skill can be `writes-records` and never create a workflow
# (every column play is), while `_MECH_WORKFLOW` matches `workflows runs`, which RUNS an existing one.
#
# THREE FORMS, AND THE SECOND ONE IS WHY THIS IS A FUNCTION RATHER THAN A GREP. A literal search for
# `clay workflows create` over all 59 packages found 6 and MISSED 3 — `tam-audience-loader`,
# `contact-unlimited-enrichment-cascade` and `get-top-conference-attendees`, all of which create
# workflows from a bundled script through an argv list:
#
#     wf = clay("workflows", "create", "--name", ...)          # build_loader.py:205
#
# The words are never adjacent, so no command-string pattern can see them. Every one of the three
# misses is in the 6-of-59 packages that ship a `scripts/` directory, which characterises the blind
# spot exactly: a package with scripts can reach any CLI verb through a list, and a reviewer who greps
# for commands will under-count creators by 3 of 9. Found because a reviewer refused to accept a grep
# as proof of scope, not because a test failed.
_WF_CREATE_FORMS = (
    ("cli-literal", re.compile(r"clay\s+workflows\s+create\b", re.I)),
    ("argv-list", re.compile(r"""["']workflows["']\s*,\s*["']create["']""", re.I)),
    ("http-endpoint", re.compile(
        r"""(?:POST|requests\.post|curl\s+-X\s*POST)[^\n]{0,120}workflows""", re.I)),
)


def workflow_creation_forms(package_text: str) -> list[str]:
    """Which creation forms the WHOLE PACKAGE shows — SKILL.md plus every supporting file.

    Pass the concatenated package, not the body: the misses this exists for were all in `scripts/`.
    Returns [] when none are found, which means "no creation path was detected in these three forms",
    never "this skill does not create a workflow" — a fourth form would be invisible here too, and the
    honest reading of an empty list is that it is a shortlist rather than a proof.
    """
    return [name for name, rx in _WF_CREATE_FORMS if rx.search(package_text or "")]


def _mechanism_from_body(body: str) -> str:
    """Which of TAXONOMY_MECHANISM the body reads as. Always returns a value; `logic-only` is real."""
    if _MECH_WORKFLOW.search(body):
        return "workflow"
    stripped = _MECH_PREFLIGHT.sub(" ", body)
    if _MECH_FUNCTIONS.search(stripped):
        return "functions"
    return "logic-only"


def _points_at_supporting_files(body: str) -> bool:
    """Does the body reference a `references/` or `scripts/` file? Reuses the same path pattern the
    missing-file resolver runs on, so "there are supporting files" cannot mean two different things
    in two checks."""
    try:
        fences = _fenced_spans(body)
    except Exception:
        fences = []
    for m in _REL_PATH.finditer(body):
        if _in_fence(m.start("path"), fences):
            continue
        if _normalize_ref(m.group("path")):
            return True
    return False


def _cost_claim_in_body(body: str) -> tuple[str, int] | None:
    """The first stated quantity of money, in the BODY, on a line that is not stating a zero."""
    blk = _frontmatter_block(body)
    start = body.find("\n---", 3) + 4 if blk else 0
    for i, line in enumerate(body[start:].split("\n")):
        if _MECH_ZERO_COST.search(line):
            continue
        m = _MECH_COST_CLAIM.search(line)
        if m:
            return m.group(0).strip(), body[:start].count("\n") + i + 1
    return None


def _resolve_mechanism(body: str, reference_text: str | None = None) -> list[Finding]:
    """Two findings, and only the second one is about money.

    THE CONTRADICTION, same shape as `touches`: the frontmatter says one thing and the steps read as
    another. Body-scoped and correct as such. Always reports, because the derivation is a heuristic
    and a heuristic must not reject.

    THE UNATTRIBUTED SPEND, which is the one worth having. A skill that states a price — "~1 credit
    per page", "≈70 credits" — and names no Clay command anywhere has told the installer it will cost
    money and given them nothing to point at. That is not a business complaint about Clay usage; a
    skill that is honestly all judgment is fine and says so. It is the ordinary determinism rule this
    kit applies everywhere else: **a step that spends money must name what it spends it on.**

    BOTH HALVES ARE PACKAGE-SCOPED, and that was learned the expensive way inside one edit. This was
    first registered in `check_portability` — which receives the body alone — AND called separately by
    the caller that holds the files. The body-only copy read four skills as `logic-only` whose commands
    are named in `references/`, and then reported each one as CONTRADICTING its own frontmatter. Five
    manufactured findings, every one of them the tool disagreeing with a better-informed copy of
    itself. A command named in `references/sourcing-arms.md` is named; a derivation that cannot see
    that file is not a weaker derivation, it is a wrong one.
    So: the whole resolver runs only when the package is actually visible — either the caller supplied
    the supporting text, or the body references none and therefore IS the package. Otherwise it
    returns nothing at all. NOT RUN, rather than a verdict on a partial read.
    """
    if reference_text is None and _points_at_supporting_files(body):
        return []
    out: list[Finding] = []
    derived = _mechanism_from_body(body if reference_text is None
                                  else body + "\n" + reference_text)
    found = _taxonomy_values(body)
    if "mechanism" in found:
        declared = found["mechanism"][0]
        if len(declared) == 1 and declared[0] != derived and declared[0] in TAXONOMY_MECHANISM:
            out.append(Finding(
                resolver="mechanism",
                severity="report",
                evidence=f"mechanism: {declared[0]} / steps read as {derived}",
                line=found["mechanism"][1],
                detail=f"The frontmatter declares `mechanism: {declared[0]}` and the steps read as "
                       f"`{derived}`. Whoever browses for a skill that builds them a workflow, or "
                       f"for one that needs no Clay account at all, is filtering on the field — not "
                       f"on the steps.",
                remediation="Make them agree. If the steps are right, correct the field; if a step "
                            "means to call something and never names it, that is the bigger of the "
                            "two problems and the next finding is probably about it.",
            ))
    if derived != "logic-only":
        return out
    claim = _cost_claim_in_body(body)
    if claim is None:
        return out                        # honestly all judgment, claims no cost. Nothing to say.
    evidence, line = claim
    out.append(Finding(
        resolver="mechanism",
        severity="report",
        evidence=evidence,
        line=line,
        detail="This skill discusses cost — credits, providers, enrichment — and names no Clay "
               "command anywhere in its steps. An installer reading it is told to expect a bill and "
               "given nothing to point it at, so they cannot estimate it, cannot check it against "
               "their plan, and cannot tell which step to cut when it comes back too high.",
        remediation="Name the command or the function each spending step actually calls, and confirm "
                    "the name against `--help` on the installed version. If the work genuinely "
                    "spends nothing and the words are habit, say `mechanism: logic-only` and cut the "
                    "cost language — a skill that is all judgment is a real kind of skill, and "
                    "saying so plainly is better than implying a cost it never charges.",
    ))
    return out


def _touches_from_body(body: str) -> str | None:
    """Which of TAXONOMY_TOUCHES the body's **Writes** line reads as, or None if it has none."""
    section = _TOUCHES_BODY.search(body)
    if not section:
        return None
    m = _TOUCHES_WRITES.search(section.group(1))
    if not m:
        return None
    text = m.group(1).strip().lower()
    if text.startswith(("nothing", "none")):
        return "read-only"
    if "own output" in text or "its own table" in text:
        return "writes-own-output"
    return "writes-records"


def _resolve_retired_frontmatter(body: str) -> list[Finding]:
    """A frontmatter field nothing reads.

    REPORTS, never blocks. Nothing consumes these, so the skill runs correctly with them present —
    blocking would be punishing a creator for a field that costs them nothing at run time.

    WHY THIS EXISTS AS A CHECK RATHER THAN MORE PROSE. The authoring flow named `proof_gaps` and
    `proof_status` NINE times, every mention a prohibition, and showed no positive frontmatter
    template at all. A skill authored through that flow emitted both fields anyway. Nine negative
    mentions of a field name are still nine mentions: the prohibition was the exposure, which is the
    same failure already recorded for comments that demonstrate what a check catches and get caught
    by it. So the tenth prohibition is not the fix. A machine that names the field and the line is.

    Scoped to the frontmatter block, not the body: `proof_gaps` discussed in prose is a creator
    explaining what their skill does not claim, which is exactly what we asked them to do.
    """
    if not body.startswith("---"):
        return []
    end = body.find("\n---", 3)
    if end == -1:
        return []
    block = body[3:end]
    out: list[Finding] = []
    for m in _FRONTMATTER_KEY.finditer(block):
        key = m.group(1)
        if key not in RETIRED_FRONTMATTER:
            continue
        out.append(Finding(
            resolver="retired_frontmatter",
            severity="report",
            evidence=key,
            line=body[:3 + m.start()].count("\n") + 1,
            detail=f"`{key}` in the frontmatter is not read by anything. It was a field once and "
                   f"is not one now, so it has no effect on how the skill is routed, validated or "
                   f"published.",
            # "and nothing else" was true until the Marketplace identity fields existed. A published
            # package legitimately carries three more that a creator does not write and must not
            # delete, so the sentence names what the CREATOR writes rather than everything that can
            # appear — the distinction the old wording lost.
            remediation=f"Delete `{key}`. If it held what the skill does NOT claim, that belongs in "
                        f"the body as a section a reader can see — the fields you write are "
                        f"{', '.join(LIVE_FRONTMATTER)}. A published copy also carries "
                        f"{', '.join(MARKETPLACE_IDENTITY_FIELDS)}, which the Marketplace issues: "
                        f"leave those exactly as they are.",
        ))
    return out


_GOOD_SECTION = re.compile(r"^##+\s*What good looks like\s*$", re.M | re.I)

_TOUCHES_SECTION = re.compile(r"^##+\s*What this skill touches\s*$", re.M | re.I)
_TOUCHES_BODY = re.compile(
    r"^##+\s*What this skill touches\s*$(.*?)(?=^##\s|\Z)", re.M | re.I | re.S)
# The three axes, matched as labels rather than prose so a PARTIAL declaration is visible. `Never` is
# the one authors drop and the one a reviewer most wants.
_TOUCHES_AXES = (
    ("reads",  re.compile(r"(?im)^\W{0,6}\**\s*reads?\b")),
    ("writes", re.compile(r"(?im)^\W{0,6}\**\s*writes?\b")),
    ("never",  re.compile(r"(?im)^\W{0,6}\**\s*never\b")),
)

# WHY THIS REPORTS AND DOES NOT BLOCK, TODAY. Measured before choosing, not assumed: 0 of 39 skills
# in this repository carry the section — not the 30 library skills, not the four curated examples,
# not the three live external submissions. Blocking would reject the entire launch cohort on its
# first day, which is the mid-launch rejection the owner ruled against. Flipping it is this one
# constant, once the corpus has caught up.
#
# WHAT IT IS FOR, WHICH IS NOT WHAT IT LOOKS LIKE. It cannot tell whether a declaration is TRUE — no
# regex can, and the safety read is an LLM pass in the parser. Its job is to guarantee the
# declaration EXISTS, because that converts an unbounded question into a checkable one: "is this
# skill dangerous?" is a judgement call, while "it declares `Writes: nothing` — does any step write?"
# is a contradiction check against a stated claim. The three named axes are the point: something an
# LLM can diff against the body rather than prose it has to interpret.
TOUCHES_BLOCKS = False


def _resolve_what_this_skill_touches(body: str) -> list[Finding]:
    """`## What this skill touches` must be PRESENT, and must name all three axes."""
    sev = "block" if TOUCHES_BLOCKS else "report"
    if not _TOUCHES_SECTION.search(body):
        return [Finding(
            resolver="what_this_skill_touches",
            severity=sev,
            evidence="section absent",
            line=1,
            detail="No `## What this skill touches` section. An installer pointing this at their CRM "
                   "cannot tell what it reads, what it writes, or what it will never go near — and "
                   "the end of the file is too late to find out.",
            remediation="Add it near the top, with three labelled lines: **Reads** — the systems and "
                        "objects it reads. **Writes** — the same, or `nothing`. **Never** — what it "
                        "will not touch under any circumstances. Say `Writes: nothing` explicitly "
                        "where that is true; it is the most reassuring line a read-only skill has.",
        )]
    section = _TOUCHES_BODY.search(body)
    text = section.group(1) if section else ""
    missing = [name for name, rx in _TOUCHES_AXES if not rx.search(text)]
    if not missing:
        return []
    return [Finding(
        resolver="what_this_skill_touches",
        severity="report",
        evidence=", ".join(missing),
        line=body[:section.start()].count("\n") + 1 if section else 1,
        detail=f"`## What this skill touches` does not name: {', '.join(missing)}. A partial "
               f"declaration reads as a complete one, and the axis left out is the one nobody "
               f"checked.",
        remediation="Name all three, even where the answer is one word. `Writes: nothing` and "
                    "`Never: deletes or clears a field` are complete answers.",
    )]


# WHAT THE **WRITES** LINE SAYS, as one of four postures. Four rather than two, because the two
# uninteresting answers are where a naive version of this does its damage.
#
# `local-only` exists because three skills write "three files in your working directory" and nothing
# else. `touches` is about the installer's CLAY WORKSPACE, so a local file is not a write for this
# purpose, and a classifier that counted it would call those three skills liars for declaring
# themselves read-only — which is the correct declaration.
#
# `unknown` exists because two skills say "only its own output: the drafts, to wherever you point
# them". That is honest prose and genuinely undecidable from the sentence. It must produce silence,
# not a guess: see the resolver below on why.
_WRITES_NOTHING = re.compile(r"(?i)^\W*(?:nothing|none)\b")
_WRITES_LOCAL = re.compile(r"(?i)\b(?:files?|report|csv|markdown|\.md|\.csv)\b[^.\n]{0,40}"
                           r"\b(?:working\s+director|local|on\s+disk|beside\s+this)")
_WRITES_ARTIFACT = re.compile(
    r"(?i)\b(?:columns?|fields?|records?|rows?|tables?|audiences?|workflows?|objects?|CRM"
    r"|sequencer|campaigns?)\b")


def _writes_posture(line: str | None) -> str:
    """One of: absent, nothing, local-only, writes, unknown. Never raises, never guesses."""
    if not line:
        return "absent"
    if _WRITES_NOTHING.match(line):
        return "nothing"
    # Order matters: a line naming BOTH a local file and a workspace artifact is a write. Only a line
    # whose sole write target is local counts as local-only, which is why the artifact test runs on
    # the line with the local clause removed.
    if _WRITES_LOCAL.search(line) and not _WRITES_ARTIFACT.search(_WRITES_LOCAL.sub(" ", line)):
        return "local-only"
    if _WRITES_ARTIFACT.search(line):
        return "writes"
    return "unknown"


# MARKETPLACE-SUPPLIED IDENTITY. Three fields the Marketplace writes into a reviewable revision, and
# which an authoring draft must NOT carry: an unpublished skill has no listing slug and no assigned
# revision, so a draft holding them is claiming an identity nobody issued. The runtime marker is built
# from these and from nothing else — not from frontmatter `name` (which `source-candidates-2` already
# shows can differ from its slug), not from the folder path, and not from the live listing's latest
# revision, because an installed package is frozen while the listing moves.
MARKETPLACE_IDENTITY_FIELDS = ("marketplace_identity_schema", "marketplace_slug",
                               "marketplace_revision")
IDENTITY_SCHEMA_SUPPORTED = (1,)
_IDENT_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IDENT_PLACEHOLDER = re.compile(r"[<>]|^\s*$|\b(?:tbd|todo|xxx|placeholder)\b", re.I)


def marketplace_identity(body: str) -> tuple[dict, list[str]]:
    """The identity fields present in the frontmatter, and why any of them is unusable.

    Returns (values, problems). `problems` empty AND all three present means a runtime marker may be
    written. Anything else means attribution is UNAVAILABLE — which is a complete outcome to report,
    never a reason to fall back to a derived value.
    """
    found = {}
    blk = _frontmatter_block(body)
    if blk:
        for m in _FRONTMATTER_PAIR.finditer(blk[0]):
            if m.group(1) in MARKETPLACE_IDENTITY_FIELDS:
                found[m.group(1)] = m.group(2).strip()
    problems: list[str] = []
    missing = [f for f in MARKETPLACE_IDENTITY_FIELDS if f not in found]
    if missing:
        problems.append("absent: " + ", ".join(missing))
        return found, problems          # nothing else is worth saying about a partial set
    schema = found["marketplace_identity_schema"]
    if not schema.isdigit() or int(schema) not in IDENTITY_SCHEMA_SUPPORTED:
        problems.append(f"unsupported identity schema {schema!r}")
    slug = found["marketplace_slug"]
    if _IDENT_PLACEHOLDER.search(slug) or not _IDENT_SLUG.match(slug):
        problems.append(f"slug is not a canonical slug: {slug!r}")
    rev = found["marketplace_revision"]
    if not (rev.isdigit() and int(rev) >= 1):
        problems.append(f"revision is not a positive integer: {rev!r}")
    return found, problems


def _resolve_marketplace_identity(body: str) -> list[Finding]:
    """A DRAFT must not carry Marketplace identity, and a package that carries it must carry it whole.

    Two findings, and the first is the one that matters for authoring. The Marketplace assigns the slug
    and the revision when it prepares a revision for review; a draft that arrives with them filled in
    has either copied them from another skill or invented them, and either way the runtime marker it
    writes will name a listing that does not correspond to it.

    The second covers a package that has been through publication and come back damaged — a partial or
    malformed identity set. That is reported rather than blocked, because the remedy is on the
    publication side and a creator holding such a package cannot fix it.

    Reports, never blocks. A skill whose identity is unusable still works; it just cannot attribute,
    and the flow's instruction for that case is to say so and carry on.
    """
    values, problems = marketplace_identity(body)
    if not values:
        return []                       # the ordinary case for a draft: none present, nothing to say
    out: list[Finding] = []
    present = sorted(values)
    line = 1
    blk = _frontmatter_block(body)
    if blk:
        m = re.search(r"(?m)^marketplace_\w+:", blk[0])
        if m:
            line = body[:blk[1] + m.start()].count("\n") + 1
    out.append(Finding(
        resolver="marketplace_identity",
        severity="report",
        evidence=f"draft carries {', '.join(present)}",
        line=line,
        detail="This package carries Marketplace identity fields. They are assigned when the "
               "Marketplace prepares an immutable revision for review — BEFORE publication, not by "
               "it — so a package that has been through that step carries them correctly and this "
               "finding is expected. A package that has NOT is claiming an identity nobody issued, "
               "and the provenance marker it writes will name the wrong listing. Note the evidence "
               "line above says `draft carries` in every case: that wording is fixed by this "
               "ruleset's conformance contract and is not a claim that this package is a draft.",
        remediation="Decide by provenance, not by this finding, and note that syntactic validity is "
                    "not proof of issuance — an issued package also matches the authoritative "
                    "revision record and package hash. Came from an issued package: preserve the "
                    "values exactly and change nothing. Editing a draft whose base was a verified "
                    "issued package: preserve them too, because the Marketplace assigns the new "
                    "revision inside the bytes it reviews, so discarding them is not your step. No "
                    "issued package behind it: delete them, since nothing assigned them. And absent "
                    "identity stays a normal state to handle rather than a defect to fix here — not "
                    "every publication path issues these fields, so a skill that cannot read a "
                    "usable identity must skip attribution and say so.",
    ))
    if problems:
        out.append(Finding(
            resolver="marketplace_identity",
            severity="report",
            evidence="; ".join(problems)[:120],
            line=line,
            detail=f"The Marketplace identity set is unusable: {'; '.join(problems)}. A skill in this "
                   f"state must skip attribution and say attribution is unavailable — it must not "
                   f"fall back to the frontmatter `name`, the folder path, or the live listing's "
                   f"latest revision.",
            remediation="This is fixed where the identity is issued, not here. Report it rather than "
                        "working around it, and do not write a marker from a derived value.",
        ))
    return out


def _resolve_touches_consistency(body: str) -> list[Finding]:
    """The frontmatter `touches:` axis and the prose **Writes** line must not contradict each other.

    WHY THIS IS WORTH A RESOLVER WHEN IT FIRES ON NOTHING. Measured across all 59 skills in the
    library: `touches: read-only` and a **Writes** line reading "nothing" select the IDENTICAL set of
    31, with no skill disagreeing with itself either way. So this is a guard on an invariant that
    currently holds, not a finding hunting for a corpus — and that is the strongest form available,
    because the cost of adding it is zero and the thing it protects is load-bearing.

    WHAT IT PROTECTS. Whether a skill writes anything into the installer's workspace is the question
    that decides who has to declare provenance, what a browsing installer is promised, and which
    skills a reviewer reads closely. Two independent fields answer it — one machine-readable, one
    prose — and NOTHING checked that they agreed. Edit `touches: read-only` onto a skill whose Writes
    line describes six fields written onto account records and every consumer downstream believes the
    field, silently, including any gate built on it.

    WHY IT DOES NOT BLOCK, AND WHY THAT IS NOT TIMIDITY. A contradiction proves the two declarations
    disagree. It does not say WHICH is wrong, and the resolver cannot know — the prose may be stale or
    the axis may be a typo, and the remediation is different in each case. A finding that cannot name
    the fix should report it to a person, not reject the submission.

    THE ONLY TWO SHAPES IT CLAIMS, and everything else is deliberately silent:

      read-only + a Writes line naming a workspace artifact ....... contradiction
      writes-* + a Writes line saying "nothing" ................... contradiction

    Absent axis, absent Writes line, a local-file-only write, and prose too loose to classify all
    return NOTHING. **Missing is unknown, not failure** — the frontmatter axes are tolerated absent by
    policy (see `TAXONOMY_BLOCKS`, whose comment records that 30 library skills carry no taxonomy and
    flipping it would reject the launch cohort), and a consistency check is the wrong place to
    re-litigate that.

    AND IT PROVES NOTHING ABOUT BEHAVIOUR. Two descriptions agreeing is two descriptions agreeing.
    This resolver reads a file; it has never seen the skill run, and a skill whose Writes line and
    `touches` axis are in perfect agreement can still do something else entirely. It reports that the
    declaration is self-consistent, which is a precondition for trusting it and not evidence for it.
    """
    tv = _taxonomy_values(body)
    declared = tv.get("touches")
    if not declared:
        return []
    values, line_no = declared
    if len(values) != 1 or values[0] not in TAXONOMY_TOUCHES:
        return []          # an invalid value is `taxonomy_value`'s finding, not this one's
    axis = values[0]
    m = _TOUCHES_WRITES.search(body)
    posture = _writes_posture(m.group(1).strip() if m else None)
    quoted = (m.group(1).strip()[:70] if m else "")

    if axis == "read-only" and posture == "writes":
        detail = (f"The frontmatter declares `touches: read-only`, and the **Writes** line describes "
                  f"a write into the installer's workspace — “{quoted}”. Whoever filters the "
                  f"marketplace for read-only skills is trusting the axis; whoever reads the file is "
                  f"trusting the line. One of them is being misled.")
        remediation = ("Fix whichever is wrong. If it does write, the axis is `writes-own-output` (its "
                       "own output columns) or `writes-records` (existing records). If it does not, "
                       "the **Writes** line should say `nothing` — a local file in the installer's "
                       "working directory is not a workspace write and does not need the axis changed.")
    elif axis in ("writes-own-output", "writes-records") and posture == "nothing":
        detail = (f"The frontmatter declares `touches: {axis}`, and the **Writes** line says nothing "
                  f"is written — “{quoted}”. A skill that writes nothing is `read-only`, and "
                  f"that is a stronger claim to make than a write it does not perform.")
        remediation = ("Fix whichever is wrong. If it writes nothing into the workspace, the axis is "
                       "`read-only`. If it does write, say what — the object and the fields, so an "
                       "installer knows what appears in their workspace.")
    else:
        return []

    return [Finding(
        resolver="touches_consistency",
        severity="report",
        evidence=f"touches: {axis} / Writes reads as {posture}",
        line=line_no,
        detail=detail,
        remediation=remediation,
    )]


def _resolve_what_good_looks_like(body: str) -> list[Finding]:
    """`## What good looks like` must be PRESENT. Whether it is any good is a reader's call.

    REPORTS, never blocks: absence is the reviewer's signal, and the stated consequence for a thin
    one — it gets sent back — is a human decision, not a regex verdict.

    WHAT THIS DELIBERATELY DOES NOT CHECK, because the first version did and was wrong. It also
    flagged a section as "a bare checklist" when the prose outside its bullets was short. Measured
    against the library that fired on 3 of 30, and reading them settled it: one is
    `account-health-audit`, a curated example, whose section names the two most common failure modes
    — inside its bullets. The bullets WERE the substance. The property that matters is whether a
    reader can tell a good run from a run that merely finished, and prose-words-outside-bullets does
    not measure that.

    The tempting fix was to tune the threshold until the library stopped complaining. That calibrates
    the check to the corpus instead of to the property, and it is how a check comes to encode
    "whatever we already wrote" as the standard. So the heuristic is gone and only the unambiguous
    half ships: the section is there, or it is not.
    """
    if _GOOD_SECTION.search(body):
        return []
    return [Finding(
        resolver="what_good_looks_like",
        severity="report",
        evidence="section absent",
        line=1,
        detail="No `## What good looks like` section. Without it, whoever installs this skill has no "
               "way to tell a run that worked from a run that merely finished — and neither will you, "
               "the next time you come back to it.",
        remediation="Add it, and describe the shape of a good outcome rather than listing steps: what "
                    "the output looks like when the skill worked, what a thin or empty run looks like "
                    "instead, and how to tell those apart at a glance.",
    )]


def _resolve_optional_markers(body: str, fences) -> list[Finding]:
    """`{{OPTIONAL: …}}` — context whose absence does not stop the skill running correctly.

    REPORTS, never blocks. Blocking on a question only memory can answer does not
    extract truth, it applies pressure to invent — and a plausible guess is indistinguishable
    from a real reason once it is prose. So the split is one test: *if the creator answers "I
    don't remember", can the skill still run correctly?* Yes → optional.

    It still surfaces, because a reviewer should be able to see what context is missing without
    that gating the creator.
    """
    out: list[Finding] = []
    for m in _OPTIONAL_MARKER.finditer(body):
        if _in_fence(m.start(), fences):
            continue
        out.append(
            Finding(
                resolver="optional_marker",
                severity="report",
                evidence=" ".join(m.group(0).split())[:110],
                line=_line_of(body, m.start()),
                detail="Optional context you left unanswered. Does NOT block: the skill runs "
                "correctly without it. Surfaced rather than hidden so the gap is visible, "
                "but leaving it is a legitimate answer.",
                remediation="Answer it if you can; leaving it is legitimate.",
            )
        )
    return out


def _resolve_unfilled_markers(body: str, fences) -> list[Finding]:
    """Unfilled unknown markers ARE deterministic — a structured artifact, not prose.

    This is how the interview-as-validation-rule works: the converter emits markers where it
    could not determine something, and intake blocks on any that survive.
    """
    out: list[Finding] = []
    for m in _UNFILLED_MARKER.finditer(body):
        if _in_fence(m.start(), fences):
            continue
        out.append(
            Finding(
                # Its OWN resolver, not workspace_handle. Found during the
                # v1 dogfood: a draft blocked purely on markers read as a "portability
                # problem", when it is the opposite — an honestly-incomplete draft awaiting
                # its author. Mislabelling it would send creators hunting for a handle that
                # is not there.
                resolver="unfilled_marker",
                severity="block",
                evidence=m.group(0).strip(),
                line=_line_of(body, m.start()),
                detail="An unfilled unknown marker from the authoring tool. The skill is "
                "incomplete by its own admission.",
                remediation="Fill the marker in your editor before submitting.",
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# R3 — an endpoint the installer cannot reach, and an embedded credential.
# (The internal tier letters are deliberately not used here: they appear nowhere else in
# the published file, so they would name a taxonomy the reader cannot resolve.)
#      SYNTAX ONLY. No DNS. No HTTP. Ever.
# ─────────────────────────────────────────────────────────────────────────────────────────

# "]" is ALLOWED so bracketed IPv6 authorities survive; excluding it truncated
# `http://[::1]:9000` to `http://[::1` and made host extraction raise — a fail-OPEN bug of
# exactly the shape of that escape, caught by the conformance suite against this very file.
_URL = re.compile(r"\b(?P<scheme>https?|ws|wss)://(?P<rest>[^\s`'\"<>)}]+)", re.I)
_URL_TRAILING = ".,;:!?'\""

_PRIVATE_SUFFIX = (".internal", ".local", ".localdomain", ".home.arpa", ".lan", ".intranet")
_LOCAL_NAMES = ("localhost", "localhost.localdomain", "ip6-localhost")

_CRED_IN_QUERY = re.compile(
    r"(?i)[?&](?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|token|key|secret|"
    r"password|passwd|pwd|signature|sig)=(?P<v>[^&\s]{6,})"
)
# Values that look like a live credential. This list is a deliberately NARROW BLOCKING SUBSET of
# the server-side validator, not parity with it: local only has to refuse to TRANSMIT something
# key-shaped, because a transmitted secret cannot be recalled. Wrong-and-strict is the correct
# direction here — a false positive costs one conversation, a false negative is permanent.
#
# `sk-[A-Za-z0-9]{20,}` used to sit here and it MISSED current OpenAI project keys: the character
# class has no hyphen, so it broke at the second dash of `sk-proj-…`. Verified live.
_CRED_SHAPES = re.compile(
    # The leading boundary is load-bearing: with hyphens inside the `sk-` class, any hyphenated
    # English phrase whose second word begins with "sk" matched from that point on. Found by
    # scanning our own corpus straight after widening the class — one false positive, in prose.
    #
    # SECOND-ORDER, and it happened twice while writing this file: a comment that DEMONSTRATES what
    # a check catches gets caught by the check. Both the assignment example above and the phrase
    # here had to be described rather than shown. If a comment needs the literal to be understood,
    # the check is under-specified, not the comment.
    r"(?<![A-Za-z0-9])(?:sk-ant-[A-Za-z0-9_-]{12,}"
    r"|sk-[A-Za-z0-9_-]{20,}"                      # sk-…, sk-proj-…: hyphens INSIDE the class
    r"|pat-[A-Za-z0-9-]{10,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"           # classic PAT plus oauth/user/server/refresh
    r"|github_pat_[A-Za-z0-9_]{20,}"        # fine-grained, underscores are inside the shape
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}"
    r"|clay_scoped_[A-Za-z0-9]{20,}"              # Clay's own scoped key — the one shape missing
    r"|AKIA[0-9A-Z]{16}"
    r"|AIza[A-Za-z0-9_-]{35}"                      # Google API key, fixed 39-char total
    r"|-----BEGIN(?:\s[A-Z]+)*\sPRIVATE KEY-----"  # PEM block, any key type
    r")"
)

# A secret that carries no recognizable prefix, caught by its ASSIGNMENT instead. This is the shape
# most likely to appear in a real Clay column config, and no prefix list can reach it.
#
# Sentinels are excluded rather than the pattern being narrowed: a skill legitimately assigns a
# key name to a stand-in such as "not_observed_in_this_run", and angle-bracket placeholders are
# already outside the value class. Excluding a short list of known stand-ins keeps the check strict
# where it matters without flagging the vocabulary our own corpus uses to mean "absent".
#
# Deliberately described rather than demonstrated: an inline example of the assignment shape trips
# the disclosure scanner's own credential axis, which has no sentinel list. Two checks, one string,
# opposite verdicts — and the comment does not need the literal to make its point.
_CRED_ASSIGNMENT = re.compile(
    # The left anchor used to be `\b`, and `_` is a word character — so there was no boundary
    # between `CLAY_` and `API_KEY`, and every realistically-named variable escaped. Measured:
    # `API_KEY=` caught, `CLAY_API_KEY=` missed; `SECRET=` caught, `AWS_SECRET_ACCESS_KEY=` missed;
    # `TOKEN=` caught, `MY_TOKEN=` missed. The bare names were the only ones ever checked.
    # An optional `[A-Za-z0-9_]*` prefix lets the keyword match as the SUFFIX of a longer
    # identifier. Precision is carried by the 16-character value floor and the sentinel list
    # below, not by this anchor.
    # The identifier may continue on BOTH sides of the keyword, which the first attempt at this
    # missed: `AWS_SECRET_ACCESS_KEY=` matched `SECRET` and then wanted the `=` immediately after
    # it, so the variable escaped on its own suffix. Prefix and suffix are both optional runs.
    r"(?i)(?:^|[^A-Za-z0-9_])[A-Za-z0-9_]*?"
    r"(?:api[_-]?key|apikey|secret|token|access[_-]?token|auth[_-]?token|authorization"
    r"|bearer|password|passwd)[A-Za-z0-9_]*"
    # An optional scheme word, so `authorization: Bearer <token>` is measured on the TOKEN.
    # Without it the value seen is "Bearer" — six characters, under the floor, silently safe.
    r"\s*[:=]\s*(?:Bearer\s+|Token\s+|Basic\s+)?[\"\']?(?P<v>[A-Za-z0-9_\-]{16,})[\"\']?"
)
_CRED_SENTINELS = re.compile(
    r"(?i)^(?:not[_-]?observed|not[_-]?exercised|none|null|example|placeholder|redacted|removed|"
    r"your[_-].*|the[_-].*|installer[_-].*|declared[_-].*|see[_-].*|x{4,}|\.{3,})"
)


def _decode_host_to_ip(host: str) -> ipaddress._BaseAddress | None:
    """Decode a host to an IP, including the encoded forms the fixture suite requires.

    Covers dotted-quad, bracketed IPv6, bare decimal (http://2130706433/), hex
    (0x7f000001), and octal (0177.0.0.1) — all of which resolve to 127.0.0.1 and all of
    which a naive `host.startswith("127.")` check misses.
    """
    h = host.strip().strip("[]")
    try:
        return ipaddress.ip_address(h)
    except ValueError:
        pass
    try:  # bare decimal / hex — int(x, 0) handles 0x and 0o prefixes
        if re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|\d+)", h):
            val = int(h, 0)
            if 0 <= val <= 0xFFFFFFFF:
                return ipaddress.IPv4Address(val)
    except ValueError:
        pass
    if re.fullmatch(r"0[0-7]*(?:\.0[0-7]*){3}", h):  # dotted octal
        try:
            octets = [int(p, 8) for p in h.split(".")]
            if all(0 <= o <= 255 for o in octets):
                return ipaddress.IPv4Address(".".join(str(o) for o in octets))
        except ValueError:
            pass
    # Mixed hex octets, e.g. 0x7f.0.0.1
    if "." in h and any(p.lower().startswith("0x") for p in h.split(".")):
        try:
            octets = [int(p, 0) for p in h.split(".")]
            if len(octets) == 4 and all(0 <= o <= 255 for o in octets):
                return ipaddress.IPv4Address(".".join(str(o) for o in octets))
        except ValueError:
            pass
    return None


def _classify_host(host: str) -> str | None:
    """Return a reason string if the host is syntactically non-portable, else None."""
    h = host.lower().rstrip(".")
    if h in _LOCAL_NAMES:
        return "loopback hostname"
    if any(h.endswith(s) for s in _PRIVATE_SUFFIX):
        return "private/internal domain suffix"
    ip = _decode_host_to_ip(h)
    if ip is not None:
        if ip.is_loopback:
            return "loopback address"
        if ip.is_link_local:
            return "link-local address"
        if ip.is_private:
            return "private address range"
        if ip.is_unspecified:
            return "unspecified address"
        if getattr(ip, "is_reserved", False):
            return "reserved address range"
        # A public literal IP is portable but brittle; report, not block.
        return None
    if "." not in h and h not in ("",):
        return "single-label host (resolves only inside a private network)"
    return None


def _authority_host(authority: str) -> str:
    """Host from an authority component. TOTAL — never raises, whatever the input.

    Bracketed IPv6 keeps its brackets; everything else drops a trailing :port. A partial or
    malformed authority returns something classifiable rather than exploding, because an
    exception in a validator is an accept.
    """
    a = authority.strip()
    if a.startswith("["):
        end = a.find("]")
        return a[: end + 1] if end != -1 else a  # unterminated bracket: hand back as-is
    return a.rsplit(":", 1)[0] if ":" in a else a


def _resolve_endpoints(body: str, fences) -> list[Finding]:
    out: list[Finding] = []
    for m in _URL.finditer(body):
        if _in_fence(m.start(), fences):
            continue
        url = m.group(0).rstrip(_URL_TRAILING)
        rest = m.group("rest").rstrip(_URL_TRAILING)
        authority = rest.split("/", 1)[0]
        line = _line_of(body, m.start())

        userinfo = None
        if "@" in authority:
            userinfo, authority = authority.rsplit("@", 1)

        host = _authority_host(authority)

        if userinfo:
            out.append(
                Finding(
                    resolver="endpoint",
                    severity="reject",
                    evidence=f"{m.group('scheme')}://{userinfo.split(':')[0]}:***@{host}",
                    line=line,
                    detail="Credential embedded in the URL's user-info component.",
                    remediation="Parameterize the credential as an installer-supplied input. If "
                    "this is a real credential rather than a placeholder, rotating it is your "
                    "call — we cannot see what it has access to.",
                )
            )

        cq = _CRED_IN_QUERY.search(url)
        if cq:
            out.append(
                Finding(
                    resolver="endpoint",
                    severity="reject",
                    evidence=url.replace(cq.group("v"), "***"),
                    line=line,
                    detail="Credential embedded in the query string.",
                    remediation="Parameterize the credential as an installer-supplied input. If "
                    "this is a real credential rather than a placeholder, rotating it is your "
                    "call — we cannot see what it has access to.",
                )
            )

        reason = _classify_host(host)
        if reason:
            out.append(
                Finding(
                    resolver="endpoint",
                    severity="block",
                    evidence=url,
                    line=line,
                    detail=f"Non-portable endpoint — {reason}. Unrunnable for every "
                    "installer. Determined from host SYNTAX; we never resolve or call it.",
                    remediation='Make the endpoint a declared input ("your own scoring '
                    'endpoint"), or remove the dependency.',
                )
            )
    return out


def _resolve_bare_credentials(body: str, fences) -> list[Finding]:
    """Credentials are scanned EVERYWHERE, fenced code blocks included.

    The fence exemption this used to carry read: "a fenced example key is illustrative; Stage S
    still reads the body." That was sound while a second pass existed. Stage S is retired, so the
    exemption became a hole in the only check standing in front of an unrecallable action — and a
    fenced block is precisely where a person pastes a config example with a live key in it.
    Verified before removal: bare key -> 1 reject, same key inside a fence -> 0 findings.

    It was never a tested behaviour. The conformance suite's single credential case is unfenced,
    so no fixture encoded the exemption, which is why it survived review.

    Fences stay exempt for the URL and localhost resolvers, where an illustrative example genuinely
    is illustrative: a fenced `http://localhost:8080` is not a dependency on localhost. The
    difference is the cost of being wrong, not the confidence of the match.
    """
    out: list[Finding] = []
    seen: set[int] = set()
    for m in _CRED_SHAPES.finditer(body):
        seen.add(m.start())
        tok = m.group(0)
        out.append(
            Finding(
                resolver="endpoint",
                severity="reject",
                evidence=f"{tok[:8]}…{tok[-2:]} ({len(tok)} chars)",  # never echo the secret
                line=_line_of(body, m.start()),
                detail="A live-looking credential is present in the skill body.",
                remediation="Remove it and declare it as an installer-supplied input. If this is a "
                            "real credential rather than a placeholder, rotating it is your call — "
                            "we cannot see what it has access to.",
            )
        )
    for m in _CRED_ASSIGNMENT.finditer(body):
        val = m.group("v")
        # A query parameter (`?api_key=…` / `&token=…`) is already reported as an embedded credential by the URL
        # resolver, so matching it here too produces TWO findings for ONE secret. Caught by an
        # existing conformance case that expects exactly one — the value of a suite that asserts
        # counts rather than presence. Not a coverage loss: the secret is still rejected, once.
        if m.start() and body[m.start() - 1] in "?&":
            continue
        if _CRED_SENTINELS.match(val) or m.start("v") in seen:
            continue
        out.append(
            Finding(
                resolver="endpoint",
                severity="reject",
                evidence=f"{m.group(0).split(chr(61))[0].split(chr(58))[0].strip()} = "
                         f"{val[:3]}… ({len(val)} chars)",  # the KEY name, never the value
                line=_line_of(body, m.start()),
                detail="A credential-shaped assignment is present in the skill body.",
                remediation="Remove the value and declare it as an installer-supplied input. If it "
                            "is a real credential rather than a placeholder, rotating it is your "
                            "call — we cannot see what it has access to.",
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# R5 — a third-party dependency with no stated fallback.
#      THE CREDENTIAL ROW BLOCKS. THE UNDECLARED SERVICE CALL REPORTS.
# ─────────────────────────────────────────────────────────────────────────────────────────
#
# Written from a real scenario rather than a hypothetical: data providers want to contribute skills
# to the library. A provider-authored skill was drafted the way a provider would write one — the
# vendor named in six steps, a hardcoded `api.<vendor>` endpoint, a declared input of
# "<vendor> API key — no default", and a Rules line mandating the vendor's own threshold. It
# returned `verdict: ok`, exit 0, ZERO blocking findings. Nothing here read the vendor lock at all.
#
# THIS RESOLVER KNOWS NO VENDOR NAMES, AND THAT IS THE DESIGN, not a shortcut. A vendor list is the
# same rotting artefact as a function catalogue — RULE 0b's lesson, and `_resolve_stale_actions`
# below already carries the version of it we own. The question that needs no list is narrower and
# strictly better: **does this skill require a credential it cannot supply, while saying nothing
# about what happens without it?** Whose credential it is does not enter into it. A skill needing
# any key with no stated fallback is unrunnable for everyone who lacks that key, and the author has
# declared both halves of that in their own table.
#
# So the blocking path reads STRUCTURE, never English: a row in the declared-inputs table whose
# name matches a closed credential vocabulary, and whose last column is one of a closed set of
# no-fallback sentinels. Both sides are the author's own words, in fixed positions. That is the same
# decidability the halts vocabulary has, and it keeps this clear of the file's own rule that a hard
# block on a regex over English is the one failure a creator cannot debug.
#
# THE ESCAPE HATCH IS A DECLARATION, NOT AN EXEMPTION. `**Vendor-specific**` in
# `## What this skill touches` lifts the block — deliberately, because a vendor-only skill is a
# legitimate thing to publish. It is not a way to skip the thinking: the axis is what the
# marketplace page renders as "needs a <vendor> account", so declaring it moves the fact in front of
# the installer BEFORE they install rather than removing it. The axis parallels `**Halts**` exactly:
# same section, same notation, same reason — a page cannot render a fact it has to infer from prose.
#
# Measured before the trigger was designed, because a trigger picked without that measurement fires
# everywhere: across all 39 skills in the library, the bodies hold 8 URLs total (7 × our own
# `raw.githubusercontent.com`, 1 × `mail.google.com`) and ZERO credential-shaped declared inputs.
# Both signals are silent on the entire existing corpus, so this adds no noise to anything already
# published — it fires on the shape that has not arrived yet.

# A closed vocabulary, matched against the declared-inputs row NAME. Its job is to recognise the
# class of thing an installer cannot be talked into having: a secret, or a vendor-side artefact.
# `account` and `connected account` are deliberately ABSENT — Clay's own connected accounts are the
# portable path this kit recommends, and 3 of the 39 route their writes through exactly that, with
# a real degrade already written. Adding the word would flag the pattern we want.
_CREDENTIAL_INPUT = re.compile(
    r"(?i)\b(api[- ]?keys?|api[- ]?tokens?|access[- ]?tokens?|auth[- ]?tokens?|bearer[- ]?tokens?"
    r"|client[- ]?secrets?|client[- ]?ids?|secret[- ]?keys?|private[- ]?keys?"
    r"|pixels?|tracking[- ]?scripts?|tracking[- ]?tags?)\b"
)

# The closed set of ways an author says "there is no fallback". Anything else in that cell — any
# sentence at all — satisfies the check, because a sentence is the author having thought about it,
# and judging whether they thought WELL is a reviewer's call and not a regex's. Cells are
# normalised for case, surrounding emphasis and trailing punctuation before comparison.
_NO_FALLBACK = frozenset({
    "", "-", "—", "–", "n/a", "na", "none", "no default", "no defaults",
    "required", "mandatory", "must be supplied", "no fallback", "no alternative",
})

_VENDOR_SPECIFIC_AXIS = re.compile(r"(?im)^\s*[-*]?\s*\*{2}vendor-specific\*{2}")

# A service the skill CALLS, as opposed to one it cites. `api.` as the leading label is the signal,
# and it is the reason this half only reports: it is a guess about the role a URL plays in a
# sentence. `raw.githubusercontent.com` and `mail.google.com` — the only hosts the real corpus
# contains — do not match, which is the point of choosing this signal over "any non-Clay host".
_SERVICE_HOST = re.compile(r"(?i)^api[0-9]*\.")
_CLAY_HOST = re.compile(r"(?i)(^|\.)clay\.com$")


def _declared_input_rows(body: str) -> list[tuple[str, str, int, str]]:
    """Rows of the declared-inputs table as (name, last cell, 1-indexed line, whole row).

    THE WHOLE ROW IS CARRIED BECAUSE THE MIDDLE COLUMN IS WHERE THE VENDOR GETS NAMED, and an
    earlier version of this returned only the first and last cells. The table's shape is
    `| input | what the installer supplies | if it is missing |` — so "ExampleVendor, or your own
    pixel plus an identity vendor" lands in the column that was being discarded, and the coverage
    test in branch (b) then could not see a vendor the author had named perfectly well. It passed an
    ad-hoc check only by accident, because an unrelated row in that fixture happened to mention the
    same brand in its LAST cell. The conformance case built for the good version caught it.

    Branch (a) still reads the first and last cells specifically: the name is what the credential
    vocabulary matches, and the fallback declaration is by contract the final column.

    TOTAL — a malformed or absent table yields no rows rather than raising, because an exception in
    a validator is an accept. The section ends at the next heading of the same or shallower depth;
    the delimiter row and any row with fewer than two cells are skipped.
    """
    m = re.search(r"(?ims)^(#{2,3})\s+declared inputs\b(.*?)(?=^#{2,3}\s|\Z)", body)
    if not m:
        return []
    start = m.start(2)
    out: list[tuple[str, str, int, str]] = []
    for line_m in re.finditer(r"(?m)^[ \t]*\|(?P<row>.*)\|[ \t]*$", m.group(2)):
        raw = line_m.group("row")
        if re.fullmatch(r"[\s:|-]*", raw):  # delimiter row
            continue
        cells = [c.strip() for c in raw.split("|")]
        if len(cells) < 2:
            continue
        out.append((cells[0], cells[-1], _line_of(body, start + line_m.start()), raw))
    return out


def _sentinel(cell: str) -> str:
    """Normalise a table cell for comparison against `_NO_FALLBACK`."""
    s = cell.strip().strip("*_`").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^[—–-]\s*", "", s) if len(s) > 1 else s
    return s.rstrip(".,;:—–-").strip().lower()


def _resolve_third_party_dependency(body: str, fences) -> list[Finding]:
    out: list[Finding] = []
    declared_vendor = bool(_VENDOR_SPECIFIC_AXIS.search(body))
    rows = _declared_input_rows(body)

    # (a) DETERMINISTIC → BLOCK. The author's own table says a credential is required and names no
    # fallback. Both halves are structural; neither is inferred from prose.
    credential_rows = [(n, c, ln) for n, c, ln, _ in rows if _CREDENTIAL_INPUT.search(n)]
    if not declared_vendor:
        for name, cell, line in credential_rows:
            if _sentinel(cell) in _NO_FALLBACK:
                out.append(
                    Finding(
                        resolver="third_party_dependency",
                        severity="block",
                        evidence=f"{name.strip('* ')} | {cell.strip() or '(empty)'}",
                        line=line,
                        # EVERY LITERAL IN THIS MESSAGE IS DOUBLE-QUOTED, deliberately. The
                        # acceptance suite extracts creator-facing messages with a pattern over
                        # runs of adjacent double-quoted literals, and cross-checks the count
                        # against a simpler pattern that only finds where a message starts. A
                        # single-quoted literal spliced in to carry an inner quote ended the run
                        # early, so this message was counted as a site and never scanned for
                        # banned wording: 49 sites, 48 extracted. Escape the inner quotes rather
                        # than reaching for the other quote character.
                        detail="This input is a credential the installer has to hold, and its "
                        "\"if it is missing\" cell says there is no fallback — so for anyone "
                        "without it the skill does nothing, and nothing tells them why. That is "
                        "the same failure as a hardcoded table id, arriving through the inputs "
                        "table instead of a step.",
                        remediation="Say what they get instead, in that cell — a reduced version "
                        "that still runs, or the nearest thing the skill can do without the key. "
                        "If there genuinely is no version without it, declare "
                        "`**Vendor-specific**` in `## What this skill touches`, naming the "
                        "service and what a non-customer gets: the marketplace page renders it, "
                        "so the requirement reaches people before they install rather than after.",
                    )
                )

    # (b) HEURISTIC → REPORT. A service the body appears to call that the inputs table never
    # mentions. Reports because "call or citation?" is a guess about a sentence.
    #
    # THE COVERAGE TEST IS WHY THIS DOES NOT PUNISH THE GOOD VERSION, and it was added because the
    # first draft did exactly that. A control was built to model the shape this whole rule is
    # arguing for — the row renamed from "Delivr API key" to the capability
    # ("person-level visit identity … Delivr, or your own pixel plus identity vendor"), with a real
    # degrade in the last cell. That version cleared the block and then drew this report, telling an
    # author who had just done the right thing to "give it a row" they already had. A check that
    # nags the behaviour it exists to reward teaches the opposite of its rule.
    #
    # So coverage is decided structurally, still with no vendor list: take the registrable label out
    # of the host (`api.delivr.ai` → `delivr`) and ask whether any declared-input row mentions it.
    # Naming the vendor as ONE OPTION inside a capability row is precisely the pattern being asked
    # for, and it is what makes the row match.
    if not declared_vendor and not credential_rows:
        mentioned = " ".join(row for *_, row in rows).lower()
        seen: set[str] = set()
        for m in _URL.finditer(body):
            if _in_fence(m.start(), fences):
                continue
            host = _authority_host(m.group("rest").rstrip(_URL_TRAILING).split("/", 1)[0]).lower()
            if host in seen or _CLAY_HOST.search(host) or not _SERVICE_HOST.search(host):
                continue
            labels = [p for p in host.split(".") if not _SERVICE_HOST.match(p + ".")]
            brand = labels[0] if labels else host
            if len(brand) > 2 and brand in mentioned:
                continue
            seen.add(host)
            out.append(
                Finding(
                    resolver="third_party_dependency",
                    severity="report",
                    evidence=host,
                    line=_line_of(body, m.start()),
                    detail="This reads as a third-party service the skill calls, and "
                    "`## Declared inputs` has no row for the access it needs. An installer "
                    "reaches this step and finds out mid-run that it wants an account they have "
                    "never heard of.",
                    remediation="Give it a row in `## Declared inputs` — the capability as the "
                    "input name, this service as one way to get it, and what happens without it. "
                    "If the skill only works with this one service, declare "
                    "`**Vendor-specific**` in `## What this skill touches` instead.",
                )
            )
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# R4 — stale Clay action / routine key  →  REMAP, never block
# ─────────────────────────────────────────────────────────────────────────────────────────

_ACTION_KEY = re.compile(r"\b(?P<k>[a-z][a-z0-9]*(?:-[a-z0-9]+){2,})\b")


def _resolve_stale_actions(body: str, fences, catalog: dict[str, str] | None) -> list[Finding]:
    """`catalog` maps a known-stale key → its current key. Absent catalog → no findings.

    Deliberately conservative: only keys the catalog explicitly knows are stale produce a
    finding. Guessing that an unrecognized hyphenated token is a Clay action would flood the
    output on ordinary prose.
    """
    if not catalog:
        return []
    # TWO ACCEPTED SHAPES, and the legacy one must keep working: R4 has live callers that pass a
    # flat `{stale: current}` map. The richer catalogue nests its renames under `renames` and its
    # per-pair schemas under `actions`, so a flat map is read as-is and a nested one is read from
    # `renames`. A nested catalogue with no `renames` disables R4 and leaves R5 running, which is
    # correct: no rename knowledge is not the same as no catalogue.
    renames = catalog.get("renames") if isinstance(catalog.get("renames"), dict) else None
    if renames is None:
        renames = {} if ("actions" in catalog or "renames" in catalog) else catalog
    catalog = {k: v for k, v in renames.items() if isinstance(v, str)}
    if not catalog:
        return []
    out: list[Finding] = []
    seen: set[tuple[str, int]] = set()
    for m in _ACTION_KEY.finditer(body):
        key = m.group("k")
        if key not in catalog:
            continue
        line = _line_of(body, m.start())
        if (key, line) in seen:
            continue
        seen.add((key, line))
        out.append(
            Finding(
                resolver="stale_action",
                severity="remap",
                evidence=key,
                line=line,
                detail="References a Clay action/routine key that has since moved. Our surface "
                "drifted, not your skill — so we remap rather than block.",
                remediation=f"Use `{catalog[key]}`.",
                suggested=catalog[key],
            )
        )
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# R5 — the (packageId, actionKey) pair a paid step names: does it resolve, and do its
#      input parameters exist with types that agree?
#
# WHY THIS EXISTS: a skill named a real action and fed `person_identifier` a personal email.
# That parameter is `semanticType: person-linkedin-url`; an email there returns
# `validation_error`, so the step was dead on arrival. It validated `ok`, 0 blocking,
# 0 findings, and a human found it by running the skill.
#
# TWO CHECKS, AND THE SECOND ONE IS NOT THE LOUD ONE. Measured on a real 2024 table:
# 5 of its 15 distinct pairs no longer resolve at all. A retired provider breaks the skill
# for every installer and is mechanically detectable, where a wrong parameter is rare —
# 1 of 59 published skills wires one explicitly. Both block; `action_not_found` will fire
# far more often, and its remediation is different (pick another provider, not rewire a field).
#
# KEYED BY THE PAIR, NEVER THE KEY ALONE: 5 of 777 catalogue keys appear under more than one
# packageId, `enrich-company` among them, so a key-only lookup is a known-ambiguous read.
#
# OFFLINE. This never shells out to `clay`. It reads a catalogue the caller supplies, because
# `validate` exiting 1 means "a check did not run" and a check needing the CLI would make
# every machine without it an exit-1. `scripts/fetch_action_catalog.py` writes the catalogue.
# ─────────────────────────────────────────────────────────────────────────────────────────

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# A pair on one line, in either order, which is the house per-paid-step table format.
_PAIR_LINE = re.compile(
    rf"(?P<pid>{_UUID})(?P<between>.{{0,200}}?)`?(?P<key>[a-z][a-z0-9]*(?:-[a-z0-9]+)+)`?"
    rf"|`?(?P<key2>[a-z][a-z0-9]*(?:-[a-z0-9]+)+)`?(?P<between2>.{{0,200}}?)(?P<pid2>{_UUID})"
)
# Parameters named as JSON keys (`{"person_identifier": …}`) or as a backticked identifier
# followed by an arrow/colon — the two ways the corpus writes an input mapping.
_PARAM_JSON = re.compile(r'"(?P<n>[a-z][a-z0-9_]{2,40})"\s*:\s*(?P<v>"[^"]{0,120}"|[^,}\|]{0,120})')
_PARAM_ARROW = re.compile(r"`(?P<n>[a-z][a-z0-9_]{2,40})`\s*(?:←|<-|:=|:)\s*(?P<v>[^|\n]{0,120})")

# A contradiction is only reported when the TYPE is structured and the VALUE prose is
# unambiguous. The type side is an enum from the schema; the value side is the author's own
# words, so anything less than an outright contradiction is left alone rather than guessed at.
_URLISH = ("linkedin-url", "profile-url", "company-url", "website-url", "url", "domain")


def _semantic_contradiction(semantic_type: str | None, value_prose: str) -> str | None:
    """Return a human reason when a structured type and the stated value plainly disagree."""
    if not semantic_type:
        return None
    v = (value_prose or "").lower()
    st = semantic_type.lower()
    has_email = "email" in v
    has_url = any(w in v for w in ("linkedin", "url", "http", "profile"))
    if any(st.endswith(u) or st == u for u in _URLISH) and has_email and not has_url:
        return f"`{semantic_type}` expects a URL; the value given is an email"
    if st == "work-email" and ("personal" in v or "gmail" in v):
        return f"`{semantic_type}` expects a work address; the value given is a personal one"
    if st in ("email", "work-email") and has_url and not has_email:
        return f"`{semantic_type}` expects an email; the value given is a URL"
    return None


def _actions_index(catalog: dict | None) -> dict:
    """The per-pair half of the catalogue. Absent in the legacy flat rename map → empty."""
    if not isinstance(catalog, dict):
        return {}
    actions = catalog.get("actions")
    return actions if isinstance(actions, dict) else {}


def _resolve_action_pairs(body: str, fences, catalog: dict | None) -> list[Finding]:
    index = _actions_index(catalog)
    if not index:
        # Same contract as R4: no catalogue → no findings. The pairs in this skill are
        # UNVERIFIED rather than passing, which `validate` says in its summary.
        return []
    out: list[Finding] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in body.split("\n"):
        line_no = _line_of(body, body.index(raw)) if raw else 0
        m = _PAIR_LINE.search(raw)
        if not m:
            continue
        pid = m.group("pid") or m.group("pid2")
        key = m.group("key") or m.group("key2")
        if not (pid and key):
            continue
        entry = index.get(f"{pid}/{key}")
        if entry is None:
            continue  # not a pair the catalogue knows; silence beats a guess
        if entry.get("resolves") is False:
            if (pid, key, "nf") not in seen:
                seen.add((pid, key, "nf"))
                out.append(
                    Finding(
                        resolver="action_pair",
                        severity="block",
                        evidence=f"{pid}/{key}",
                        line=line_no,
                        detail="This skill names a Clay action that no longer resolves, so the "
                        "step cannot run for any installer. Measured on a real table of this "
                        "vintage, a third of its actions had been retired.",
                        remediation="Re-resolve the capability against the live catalogue and "
                        "name a provider that still exists, or describe the capability and have "
                        "the skill pick one at install time.",
                    )
                )
            continue
        schema = {p.get("name"): p.get("semanticType")
                  for p in (entry.get("inputs") or []) if isinstance(p, dict)}
        if not schema:
            continue
        for pm in list(_PARAM_JSON.finditer(raw)) + list(_PARAM_ARROW.finditer(raw)):
            name, value = pm.group("n"), pm.group("v")
            if name == key or name in ("packageId", "actionKey"):
                continue
            if name not in schema:
                if (pid, key, name) in seen:
                    continue
                seen.add((pid, key, name))
                out.append(
                    Finding(
                        resolver="action_pair",
                        severity="block",
                        evidence=name,
                        line=line_no,
                        detail=f"`{name}` is not an input parameter of `{key}`. The step will "
                        "reject the call, or silently ignore the value and answer about nobody. "
                        "A table's input binding carries a shotgun of alias names, most of them "
                        "wrong for the action it is bound to — only the schema says which is real.",
                        remediation="Confirm the parameter against "
                        f"`clay workflows actions schema {pid} {key}` and use the name it gives. "
                        f"This action accepts: {', '.join(sorted(schema)) or '(none declared)'}.",
                    )
                )
                continue
            why = _semantic_contradiction(schema.get(name), value)
            if why and (pid, key, name + "/type") not in seen:
                seen.add((pid, key, name + "/type"))
                out.append(
                    Finding(
                        resolver="action_pair",
                        severity="block",
                        evidence=f"{name}={value.strip()[:60]}",
                        line=line_no,
                        detail=f"`{name}` on `{key}`: {why}. The call fails per item, or "
                        "resolves the wrong person — and the step looks configured either way.",
                        remediation="Feed this parameter a value of the type the schema declares, "
                        "or derive that value in an earlier step and reference it here. Confirm "
                        f"with `clay workflows actions schema {pid} {key}`.",
                    )
                )
    return out


# ─────────────────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────────────────


def check_portability(
    skill_md: str,
    package_files: Iterable[str] = (),
    action_catalog: dict[str, str] | None = None,
) -> Result:
    """Run every resolver over a submitted skill body.

    Args:
        skill_md: the submitted body, decoded, exactly as stored.
        package_files: paths present in the package. A single-file submission passes
            ("SKILL.md",) — which is precisely why the canary must block.
        action_catalog: either the legacy flat `{stale-key: current-key}` rename map, or the
            richer shape `{"renames": {...}, "actions": {"<packageId>/<actionKey>":
            {"resolves": bool, "inputs": [{"name", "semanticType", "required"}],
             "or_group": str|None, "credit_cost": float|None, "payment_type": str|None}}}`.
            Keyed by the PAIR because 5 of 777 catalogue keys are shared across packages.
            None disables R4 and R5 both: the pairs are then UNVERIFIED, not passing.
            Written by `scripts/fetch_action_catalog.py`. Never fetched from here.

    Never performs network I/O. Never raises on malformed input: an exception here would
    fail OPEN, which is how the one real escape got accepted with `intake_findings: []`.
    """
    if skill_md is None:
        skill_md = ""
    try:
        fences = _fenced_spans(skill_md)
    except Exception:
        fences = []
    findings: list[Finding] = []

    # FAIL CLOSED. That escape's signature was `intake_findings: []` with `finding_count: 0` — the
    # shape of a swallowed exception, which ACCEPTS the submission. So an internal error in
    # any resolver becomes a BLOCKING finding, never silence. A validator that cannot
    # complete has not cleared anything.
    resolvers = (
        ("missing_file", lambda: _resolve_missing_files(skill_md, package_files, fences)),
        ("workspace_handle", lambda: _structured_handles(skill_md, fences)),
        ("unfilled_marker", lambda: _resolve_unfilled_markers(skill_md, fences)),
        ("what_good_looks_like", lambda: _resolve_what_good_looks_like(skill_md)),
        ("what_this_skill_touches", lambda: _resolve_what_this_skill_touches(skill_md)),
        # Registered beside its sibling and NOT merged into it: that one asks whether the section
        # exists and names its axes, this one asks whether the section agrees with the frontmatter.
        # Different inputs, different remediations, and one finding carrying both would name a fix
        # for whichever half happened to fire.
        ("touches_consistency", lambda: _resolve_touches_consistency(skill_md)),
        ("marketplace_identity", lambda: _resolve_marketplace_identity(skill_md)),
        ("optional_marker", lambda: _resolve_optional_markers(skill_md, fences)),
        ("retired_frontmatter", lambda: _resolve_retired_frontmatter(skill_md)),
        ("taxonomy_value", lambda: _resolve_taxonomy(skill_md)),
        # NO `mechanism` RESOLVER HERE, and the absence is the fix rather than an omission. The
        # resolver is package-scoped — see its own docstring, which already asserted this while this
        # line still contradicted it — and the caller holding the supporting files runs it. Registered
        # here as well, it double-fired on every SINGLE-FILE package: the early-return guard only trips
        # when the body points at files it cannot see, so a skill with no `references/` got the finding
        # twice. `package_skill`'s per-supporting-file pass re-entered here too, which could attribute
        # a spend finding to a reference file that merely quotes a price. Restoring this line
        # reintroduces both. Verified by deleting it: duplicate count 2 -> 1 on a single-file package.
        ("workspace_handle", lambda: _resolve_prose_handles(skill_md, fences)),
        ("endpoint", lambda: _resolve_endpoints(skill_md, fences)),
        ("endpoint", lambda: _resolve_bare_credentials(skill_md, fences)),
        # Registered here and NOT in `package_skill`'s per-supporting-file pass, for the reason the
        # `mechanism` note above records: the declared-inputs table and the vendor axis live in
        # `SKILL.md` only, so running this over a reference file asks a question that file cannot
        # answer — and would fire the report branch on any reference page that quotes an API host.
        ("third_party_dependency", lambda: _resolve_third_party_dependency(skill_md, fences)),
        ("stale_action", lambda: _resolve_stale_actions(skill_md, fences, action_catalog)),
        # Registered AFTER stale_action deliberately: a key the catalogue knows has merely moved
        # is R4's remap, not R5's block. R5 only speaks about pairs the catalogue carries a
        # schema for, so a renamed key reaches it under its current name or not at all.
        ("action_pair", lambda: _resolve_action_pairs(skill_md, fences, action_catalog)),
    )
    system: list[SystemFailure] = []
    if attribution()["fixture_suite_hash"].endswith("UNAVAILABLE"):
        system.append(
            SystemFailure(
                code="fixture_suite_unavailable",
                component="portability",
                detail="The conformance fixture suite could not be read, so this build cannot "
                "be attributed to a verified contract. Intake must stop with a retriable "
                "system disposition and create no rows.",
            )
        )
    for name, run in resolvers:
        try:
            findings += run()
        except Exception as exc:
            system.append(
                SystemFailure(
                    code="resolver_exception",
                    component=f"portability.{name}",
                    detail=f"The {name} resolver raised {type(exc).__name__}, so this submission "
                    "has NOT been cleared. Fails closed — but as OUR failure, not a "
                    "creator finding.",
                )
            )
    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order.get(f.severity, 9), f.line, f.resolver))
    return Result(findings=findings, system_failures=system)


def _structured_handles(body: str, fences) -> list[Finding]:
    """One finding per handle. Patterns overlap by design (a Clay table URL also contains a
    `t_...` id), and reporting the same handle twice would double-count the blocking total —
    which the conformance suite checks exactly, because over-blocking is also a defect."""
    out: list[Finding] = []
    claimed: list[tuple[int, int]] = []
    for rx, label in _STRUCTURED_HANDLE:
        for m in rx.finditer(body):
            if _in_fence(m.start(), fences):
                continue
            if any(m.start() < b and a < m.end() for a, b in claimed):
                continue
            claimed.append((m.start(), m.end()))
            out.append(
                Finding(
                    resolver="workspace_handle",
                    severity="block",
                    evidence=m.group(0).strip(),
                    line=_line_of(body, m.start()),
                    detail=f"Names a workspace-scoped {label}. The handle exists only in your "
                    "own workspace, so the skill is unrunnable for every installer "
                    "and unevaluable by us.",
                    remediation="Replace with a declared input the installer supplies, or a "
                    "portable action reference.",
                )
            )
    return out
