#!/usr/bin/env python3
"""Submit a finished skill package for review — from a script, never from the model.

WHY THIS IS A SCRIPT AND NOT A REQUEST THE AGENT WRITES
=======================================================
Two things in a submission must come from code. Both break quietly if they come from a model,
which is worse than breaking loudly.

1. THE PACKAGE BYTES. A submission carries the package base64-encoded. Measured against the
   documented limits:

       5 MB ZIP  (the cap)      -> 6.67 MB of base64  -> roughly 1.9-2.7 MILLION tokens
       250 KB SKILL.md (the cap)-> 0.33 MB of base64  -> roughly 95-133 THOUSAND tokens

   A 200k-token context holds about 375 KB of source package. The ZIP ceiling is 13x that, and
   even the MARKDOWN-only ceiling would consume half a context. So inlining is not "fine for
   small files and broken for big ones" — it fails at the contract's own published limits.

   And it fails in the worst available way: the model emits a truncated base64 string, the
   server decodes a short buffer, and the result reads as a MALFORMED ARCHIVE rather than as a
   context limit. The creator is told their zip is corrupt. So the bytes are read from disk,
   encoded here, and never enter the conversation.

2. RETRYSECRET. It is a 64-hex capability token — the bearer proof for a private receipt. A
   model asked for 64 hex characters is sampling a token distribution, not a CSPRNG: the output
   can be predictable and can repeat across sessions, and neither failure is visible. It comes
   from `secrets.token_hex(32)` here. `requestId` is the milder case — a UUID is
   collision-tolerant and the server rejects replays — but it lives in the same place for the
   same reason.

   THE GENERAL RULE: anything that needs exact bytes or real randomness comes from code, never
   from the model.

WHY SENDING REQUIRES A PREVIEW FIRST
====================================
This tool weakens the strongest promise in the kit — that nothing is submitted on the creator's
behalf. The replacement promise is that nothing is submitted WITHOUT THEIR EXPLICIT CONFIRMATION,
and a promise that only exists in prose is enforced nowhere.

So `send` requires a confirm token that only `preview` can mint. The token is **random**, written
to a `0600` file with the package digest and creator identity it is bound to, and **consumed** on
use.

Each of those three properties answers a different attack, and the first one is a correction:

* **Random, not derived.** The first version computed the token as a hash of the package digest and
  the profile — a pure function of inputs the agent already holds, using code the agent can read.
  So `preview` could be skipped and the token derived, which made the token prove *what* would be
  sent and never *that anyone was asked*. The threat is instruction injection: a table
  configuration or a supporting file telling the agent to compute the hash and call `send` defeats
  a derived token entirely, and that is the exact case this rule exists for. Statelessness was a
  convenience; unpredictability is the security property.
* **Bound to the package and identity.** Edit either after the preview and the right token is
  still refused, because what the creator saw is no longer what would be sent.
* **Single-use.** A token captured from a transcript does not stay live.

It is still not proof a human read the screen — nothing over an API can be. What it is now is a
value that cannot be produced by anything which merely controls the request.

WHY AN UNAUTHENTICATED ENDPOINT IS ACCEPTABLE HERE
==================================================
Identity is self-asserted in the payload and consent is a boolean this script sets, so nothing
here proves a human agreed to anything. That is bounded, not ignored: **manual identity
verification gates publication**, and publication is the only irreversible step. The worst case
for a forged submission is a junk row in a review queue. Do not add authentication to the door
without also keeping the gate — the gate is what makes the door safe.

Exit codes match the rest of the kit:
  0  submitted for review
  1  internal error in this tool
  2  invalid invocation, or a missing confirm token
  4  the server rejected the submission (its code and message are reported verbatim)
  5  the server could not be reached; nothing was submitted
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

EXIT_OK, EXIT_INTERNAL, EXIT_VALIDATION, EXIT_REJECTED, EXIT_NETWORK = 0, 1, 2, 4, 5

# Sent on every request. See the note at the request construction: the stdlib default is blocked
# by the WAF, so this is load-bearing rather than cosmetic. Keep it honest and identifiable — it is
# how the receiving side tells our traffic from a scraper's.
USER_AGENT = "clay-skill-author/1 (+https://github.com/clay-run/clay-skill-creator)"

# The server's documented ceilings. Checked HERE, before encoding, for the same reason the
# credential scan runs before transmission: a 5 MB package becomes a 6.67 MB request body, and
# discovering it is one byte over after uploading all of it wastes the upload and returns a
# `package_too_large` a creator has to interpret. Named limits, refused locally, with the actual
# measured size in the message.
#
# The server stays authoritative — these are its numbers, not ours. If it lowers a cap and this
# copy is stale, the server still rejects and the message is still correct about what happened.
MAX_ZIP_BYTES = 5 * 1024 * 1024
MAX_MARKDOWN_BYTES = 250 * 1024

# THE PRODUCTION SUBMISSION ENDPOINT, and it is defaulted rather than required for one reason:
# until now `--endpoint` had no default, so a creator following the published flow reached `send`
# with nowhere to send. Every other step worked and the last one asked them for a URL that appears
# in no document they were given. A flow whose final command cannot be completed from the
# instructions is not a flow.
#
# Overridable, because staging exists and a creator on a self-hosted or preview deployment should
# not have to edit a published script to reach it.
DEFAULT_ENDPOINT = "https://marketplace.clay.com/api/marketplace/submissions"

# The consent version the server records against the submission. This is an IDENTIFIER the server
# recognises, not a date we choose: it must name the consent text below, and the server rejects a
# version it does not know. The previous default was `2026-08-18` — the day the text was written —
# which matched nothing on the server side and would have been sent with every real submission.
# A field the server validates cannot be defaulted to something locally meaningful.
CONSENT_VERSION = "marketplace-v2-collection-1"

# The consent the creator must have seen. Kept here verbatim so the preview cannot show one thing
# while the request asserts another. If this text changes, CONSENT_VERSION changes with it — they
# are one fact recorded in two places, and a mismatch means a creator agreed to different words
# from the ones we filed.
CONSENT = (
    "Clay may publish this skill and your public attribution; may edit it for clarity, house "
    "voice and formatting while the substance stays yours; may publish it in a public repository "
    "under an open licence where others may use and adapt it with attribution; and your "
    "attribution and content may persist in git history and in third-party forks after Clay "
    "removes the current files."
)


def _envelope(code: str, message: str, exit_code: int) -> int:
    print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
    return exit_code


def _referenced_but_absent(blob: bytes) -> list[str]:
    """In-package references a single-file submission cannot satisfy.

    Delegates to `portability.py` when it is importable — it ships beside this file in every
    distribution — and returns [] when it is not, rather than guessing at the rule. A weaker second
    opinion is worse than none: it would refuse valid packages, and the refusal would be unarguable
    because nobody could point at the rule it applied.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, os.path.join(here, "..", "..", "..", "eval", "validators")):
        if os.path.isfile(os.path.join(cand, "portability.py")):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            break
    else:
        return []
    try:
        import portability as _P
        body = blob.decode("utf-8", "replace")
        res = _P.check_portability(body, ["SKILL.md"], None)
        return sorted({f.evidence for f in res.findings if f.resolver == "missing_file"})
    except Exception:
        return []


def _inventory(path: str) -> tuple[bytes, str, list[dict]]:
    """The package bytes, its kind, and a file inventory — read from disk, in sorted order."""
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            blob = fh.read()
        kind = "zip" if path.endswith(".zip") else "markdown"
        if kind == "markdown":
            # THE HOLE THIS CLOSES, found by an installer trying to run a submitted skill. The
            # DIRECTORY branch below already refuses a multi-file package and says to zip it. This
            # branch — a bare path to a SKILL.md — had no such check, so a two-file skill could be
            # sent as one file and arrive looking complete. The installer then hits
            # `references/node-code.md` which is in no package anywhere, and the flow's own warning
            # applies: the agent stalls, or INVENTS the content, which looks like success.
            #
            # Same extractor `package_skill.py validate` uses, deliberately: a second
            # implementation of "what counts as an in-package reference" would drift from the one
            # that decides whether the package is valid, and then the two doors disagree about the
            # same file.
            missing = _referenced_but_absent(blob)
            if missing:
                raise ValueError(
                    f"{path} references {len(missing)} file(s) that this submission would not "
                    f"carry: {', '.join(missing)}. Nothing was sent. A markdown submission is one "
                    f"file, so the reference would arrive pointing at nothing. Zip the package "
                    f"instead — `package_skill.py zip <dir> <slug>.zip` — and submit the zip, or "
                    f"inline what those files say."
                )
        return blob, kind, [{"path": os.path.basename(path), "bytes": len(blob)}]
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    # A directory is submitted as its SKILL.md when that is all there is, and otherwise the
    # caller is expected to have zipped it — this tool does not build archives, because the
    # package tool already does and two implementations would drift.
    files = sorted(os.path.relpath(os.path.join(dp, f), path).replace(os.sep, "/")
                   for dp, _, fn in os.walk(path) for f in fn)
    if files == ["SKILL.md"]:
        with open(os.path.join(path, "SKILL.md"), "rb") as fh:
            blob = fh.read()
        return blob, "markdown", [{"path": "SKILL.md", "bytes": len(blob)}]
    raise ValueError(
        f"{path} holds {len(files)} files. Zip it first with "
        f"`package_skill.py zip {path} <slug>.zip`, then submit the zip — this tool does not "
        f"build archives, so there is only one implementation of the package format."
    )


def _too_large(blob: bytes, kind: str) -> str | None:
    """The refusal message if this package is over the documented cap, else None."""
    cap = MAX_ZIP_BYTES if kind == "zip" else MAX_MARKDOWN_BYTES
    if len(blob) <= cap:
        return None
    return (f"the package is {len(blob) / 1024 / 1024:.2f} MB and the limit for a {kind} "
            f"submission is {cap / 1024 / 1024:.2f} MB. Nothing was sent. Trim it, or split "
            f"supporting material out, and submit again — the encoded request would have been "
            f"{len(blob) * 4 / 3 / 1024 / 1024:.2f} MB.")


def _slug(blob: bytes, kind: str) -> str | None:
    """The slug the package asks for, read from the frontmatter `name:` — for EITHER kind.

    A zip returned `None` here, so every multi-file submission reached the door with no declared
    slug while a single-file one declared its own. That asymmetry lands exactly where it hurts
    most: the existing-`SKILL.md` route and every workflow-derived package are multi-file by
    construction, so the submissions carrying the most files were telling the door the least about
    themselves. Filling a field that was always null is additive — nothing downstream can have
    depended on the absence.

    Bounded and total. The member must be exactly `SKILL.md` at the archive root; only a prefix is
    read, because a member's declared size is controlled by whoever built the archive; and any
    malformed or hostile zip returns None rather than raising, since an exception here would abort
    a submission over a field that is advisory.
    """
    text: str | None = None
    if kind == "markdown":
        text = blob.decode("utf-8", "replace")
    else:
        try:
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                if "SKILL.md" in zf.namelist():
                    with zf.open("SKILL.md") as fh:
                        text = fh.read(8192).decode("utf-8", "replace")
        except Exception:
            return None
    if not text:
        return None
    for i, line in enumerate(text.split("\n")):
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
        # Past the closing frontmatter fence, `name:` is body prose and not the slug.
        if i > 0 and line.startswith("---"):
            break
    return None


def _profile(raw: str) -> dict:
    p = json.loads(raw)
    missing = [k for k in ("fullName", "workEmail") if not p.get(k)]
    if missing:
        raise ValueError(f"creator profile is missing required fields: {missing}")
    return p


def _binding(digest: str, profile: dict) -> str:
    """What the confirmation is bound TO: this package, this identity."""
    material = digest + "\n" + json.dumps(profile, sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def _state_dir() -> str:
    """WHERE STATE GOES: a per-user directory, never anywhere near the package.

    `0600` BESIDE THE PACKAGE WAS NOT ENOUGH, and the reasoning that made it look sufficient is
    worth keeping. The mode defends against other users on the machine, and `_issue_confirm` below
    reasons carefully about a token captured from a transcript. Nobody reasoned about `git add`.

    Observed in our own public repo: a stale `.submit-confirm-build-prospect-list.json` was swept
    into a commit beside the package it belonged to and published. That token was inert — bound to
    one digest and one profile, single-use — but it cost two separate creators a detour, because an
    undocumented hidden file with `submit` in its name is exactly what a careful agent stops on, and
    the kit's own guide promises nothing is tucked away for an agent to find.

    THE RECEIPT IS THE SERIOUS CASE, and it shares this directory for that reason: it carries
    `retrySecret`, a real bearer credential, and it landed in the same parent. A creator whose
    package folder sits in a repo — which is most people organising work — had a live secret one
    `git add .` from being public. A parent directory is not ours to reason about; this one is.

    Honours `XDG_STATE_HOME` so a host that relocates state is obeyed rather than second-guessed.
    """
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "state")
    d = os.path.join(base, "clay-skill-author")
    os.makedirs(d, mode=0o700, exist_ok=True)
    # makedirs respects umask on creation and does nothing to an existing directory, so set it
    # explicitly either way — an inherited 0755 would undo the point of moving out of the tree.
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _state_key(package: str) -> str:
    """A filename for one package: its own name, plus a digest of its absolute path.

    The name alone collides — two `inbound-lead-routing` folders in different projects are two
    packages — and the absolute path alone is not a filename. Keeping the readable half means a
    creator who lists the directory can tell which file is which; keeping the digest means they are
    never the same file. This preserves the one-file-per-package property `_pending_path` already
    had, now that the shared parent is a shared directory for everybody rather than one project.

    THE DIGEST IS OF THE ROOT, NOT OF THE ARGUMENT, and the first version got that wrong: hashing
    the path as given meant `preview <pkg>` and `send <pkg>/SKILL.md` keyed to two different files,
    so a submission previewed one way and sent the other was told to run `preview` again. Caught by
    asserting the two forms agree rather than by reading it. Hashing the root also retires the
    collision the old naming worked around — a directory holds one `SKILL.md`, so one package.
    """
    abspath = os.path.abspath(package)
    root = abspath if os.path.isdir(abspath) else os.path.dirname(abspath)
    tag = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(root)) or "package"
    return f"{tag}-{hashlib.sha256(root.encode()).hexdigest()[:12]}"


def _pending_path(package: str) -> str:
    """One state file per package, in the state directory — never beside the package.

    NOT inside: a directory package must contain only `SKILL.md` — `_inventory` refuses anything
    else — so a state file written into it would break the very submission it is confirming, and
    would be a candidate for being submitted.

    ONE PER PACKAGE, because a single fixed name in the shared parent collides: preview A, preview
    B, and A's token is refused. That fails safe but is baffling, and it was found by testing two
    packages in one directory rather than by reading the code.
    """
    abspath = os.path.abspath(package)
    # THE FILE CASE VIOLATED THE RULE IN THE LINE ABOVE. `dirname` of a directory package is its
    # parent, which is correct; `dirname` of `<pkg>/SKILL.md` is the PACKAGE, so a single-file
    # preview wrote its state file inside the very package it was confirming. Demonstrated by
    # accident: previewing a worked example made that example fail validation with two blocking
    # findings — `portable_path` and `unreferenced_file` — so validate → preview → validate did not
    # round-trip on the commonest package shape there is.
    #
    # So resolve the package ROOT first and go beside THAT: the directory itself when given a
    # directory, the containing directory when given a file. The tag keeps the root's name as well
    # as the basename, because two single-file packages in one parent would otherwise both tag as
    # `SKILL.md` and collide — which is the failure the docstring above already records for a fixed
    # name, arriving by a different route.
    # The dirname reasoning above is why `_state_key` resolves the ROOT before naming anything: the
    # file case still has to key on the package, not on `SKILL.md`. What changed is the destination.
    # A preview taken under an older version left its file beside the package and this will not find
    # it — that fails closed, with `_redeem_confirm`'s existing "run `preview` again" message, which
    # is the right outcome for state we can no longer prove the provenance of.
    del abspath
    return os.path.join(_state_dir(), f".submit-confirm-{_state_key(package)}.json")


def _issue_confirm(package: str, digest: str, profile: dict) -> str:
    """Mint an UNPREDICTABLE confirmation token and record what it is bound to.

    THE TOKEN USED TO BE DERIVED, AND THAT WAS A DEFECT. It was
    `sha256(digest + sorted-profile)[:16]` — a pure function of inputs the agent already holds,
    computed by code the agent can read. So `send` could recompute it and `preview` could be
    skipped entirely, which means the token proved *what* would be sent and never *that anyone was
    asked*. The docstring claimed the stronger property; only the weaker one was true.

    That gap is the whole point, because the threat is instruction injection. A table
    configuration or a supporting file that tells the agent to compute the hash and call `send`
    defeats a derived token completely — and defeating exactly that is why the
    never-submit-without-an-explicit-yes rule exists.

    So the token is now random. Statelessness was a convenience; **unpredictability is the
    security property**, and a value that cannot be derived from the request cannot be minted by
    something that only controls the request.

    Both properties the derived version had are kept, because the binding is stored alongside:
    edit the package after the preview and the digest no longer matches, so the token is refused
    even though it is the right token.

    The file is `0600` and single-use — `send` consumes it. A replayed token fails on the second
    attempt, so a token captured from a transcript does not stay live.
    """
    token = secrets.token_hex(16)
    path = _pending_path(package)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"confirm_token": token, "binding": _binding(digest, profile)}, fh)
    os.chmod(path, 0o600)
    return token


def _redeem_confirm(package: str, token: str, digest: str, profile: dict) -> str | None:
    """Consume the pending confirmation. Returns None on success, else the reason it failed."""
    path = _pending_path(package)
    try:
        with open(path, encoding="utf-8") as fh:
            pending = json.load(fh)
    except (OSError, ValueError):
        return ("No pending confirmation for this package. `send` requires a token that `preview` "
                "minted — it cannot be computed from the package, deliberately, so that nothing "
                "which merely controls the request can produce one. Run `preview`, show the "
                "creator what it prints, and use the token from that run.")
    if not secrets.compare_digest(str(pending.get("confirm_token", "")), token):
        return ("That confirm token does not match the pending confirmation for this package. Run "
                "`preview` again and use the token it prints.")
    if pending.get("binding") != _binding(digest, profile):
        return ("The package or the creator details changed after the preview, so what the creator "
                "was shown is not what would be sent. Run `preview` again and show them the new "
                "version.")
    # Single-use: consumed on success, so a token seen once cannot be replayed.
    try:
        os.remove(path)
    except OSError:
        pass
    return None


def _blocking_findings(package: str) -> list[str]:
    """Run the local validator and return the names of its BLOCKING findings, if it can run.

    FOUND BY A LAUNCH-DAY CANARY, and it is the gap a canary exists to find. A package with a
    blocking finding previewed cleanly and minted a token: `validate` said `blocked`, and this tool
    never asked it. So the two halves of the same kit disagreed about whether a package was
    submittable, and the creator learned which one was right after review rather than before.

    Advisory by construction. Returning `[]` on any failure to run is deliberate: the server owns
    authoritative validation, and a submission tool that cannot send because a sibling script threw
    is worse than one that sends something a reviewer bounces. The check adds a warning and a
    stronger `next`, and it never blocks the send path itself.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in ("package_skill.py",):
        tool = os.path.join(here, candidate)
        if not os.path.exists(tool):
            continue
        try:
            r = subprocess.run([sys.executable, tool, "validate", package],
                               capture_output=True, text=True, timeout=60)
            return [b.get("check", "?") for b in json.loads(r.stdout).get("blocking", [])]
        except Exception:
            return []
    return []


def preview(args) -> int:
    blob, kind, inventory = _inventory(args.package)
    digest = hashlib.sha256(blob).hexdigest()
    profile = _profile(args.profile)
    blocking = _blocking_findings(args.package)
    out = {
        "will_send": {
            "endpoint": args.endpoint or "<not set — pass --endpoint>",
            "sourceInputMethod": "agent_api",
            "packageKind": kind,
            "packageBytes": len(blob),
            "withinDocumentedLimit": _too_large(blob, kind) is None,
            "packageSha256": digest,
            "fileInventory": inventory,
            "skillSlugRequested": _slug(blob, kind),
            "creator": profile,
            # The version filed against the submission, shown because it IS part of the request.
            # The preview's whole claim is that it cannot show one thing while the request asserts
            # another, and a field the server records about what the creator agreed to is exactly
            # the field that claim has to cover.
            "consentVersion": args.consent_version,
        },
        "consent_the_creator_must_have_seen": CONSENT,
        "not_sent": "Nothing has been submitted. This printed what WOULD be sent.",
        "confirm_token": _issue_confirm(args.package, digest, profile),
        "next": ("Show the creator the block above, including the consent text, and ask whether to "
                 "submit. Only if they say yes: re-run with `send --confirm <confirm_token>`."),
    }
    if blocking:
        # Surfaced ABOVE the token in reading order, and worded as the creator's decision rather
        # than as a refusal, because this tool is not the authority on validity. The point is that
        # they find out now instead of after a reviewer reads it.
        out["local_validation_blocking"] = blocking
        out["next"] = (
            f"STOP AND SAY THIS FIRST: `package_skill.py validate` blocks this package on "
            f"{', '.join(blocking)}. Submitting it anyway is allowed and a reviewer will probably "
            "bounce it, so fix those findings and re-run `preview`. If the creator wants to submit "
            "as-is, tell them what is blocking and get an explicit yes to that, then "
            "`send --confirm <confirm_token>`."
        )
    print(json.dumps(out, indent=1))
    return EXIT_OK


def send(args) -> int:
    blob, kind, inventory = _inventory(args.package)
    digest = hashlib.sha256(blob).hexdigest()
    profile = _profile(args.profile)
    refused = _redeem_confirm(args.package, args.confirm, digest, profile)
    if refused:
        return _envelope("confirmation_required", refused, EXIT_VALIDATION)
    oversize = _too_large(blob, kind)
    if oversize:
        return _envelope("package_too_large", oversize, EXIT_VALIDATION)
    if not args.rights_confirmed:
        return _envelope(
            "consent_not_confirmed",
            "Pass --rights-confirmed only after the creator has seen the consent text that "
            "`preview` printed and agreed to it.",
            EXIT_VALIDATION)

    # THE PAYLOAD FIELD NAME DEPENDS ON THE KIND, and getting it wrong fails obscurely.
    # The server takes `packageBase64` for a zip and `skillMdBase64` for a bare SKILL.md. It
    # validates that field conditionally on `packageKind`, so the wrong key presents as a
    # malformed envelope rather than as "you named the field wrong" — worth knowing if you are
    # ever debugging a rejection that names the whole request instead of one field.
    payload_field = "packageBase64" if kind == "zip" else "skillMdBase64"
    body = {
        "sourceInputMethod": "agent_api",
        "requestId": str(uuid.uuid4()),          # from code: replay identity
        "retrySecret": secrets.token_hex(32),    # from code: a capability token, never sampled
        "packageKind": kind,
        # `sourceFilename` is REQUIRED and was absent. The server's field errors name it, but only
        # once the rest of the envelope parses, so it was invisible behind the payload-field bug.
        "sourceFilename": inventory[0]["path"] if kind != "zip" else os.path.basename(args.package),
        payload_field: base64.b64encode(blob).decode(),     # never passes through a context
        "creator": profile,
        "rightsConfirmed": True,
        "consentVersion": args.consent_version,
        # The server computes the digest and inventory itself, so these are advisory. They are sent
        # anyway, deliberately: if the server's digest ever disagrees with the bytes we read off
        # disk, that is the single most important thing this tool could discover, and it can only
        # discover it by stating its own answer.
        "packageSha256": digest,
        "fileInventory": inventory,
    }
    req = urllib.request.Request(
        args.endpoint, data=json.dumps(body).encode(),
        # A User-Agent IS NOT OPTIONAL, and this is the defect that would have hit every creator.
        # The default `Python-urllib/3.x` is blocked outright by the WAF in front of the submission
        # route — Cloudflare error 1010, a client-fingerprint ban — so a submission failed with a
        # 403 before it was ever read. Measured: default UA 403, any other UA passes to real
        # validation. A named, honest UA is also the cooperative choice: it lets the other side
        # allowlist, rate-limit or debug this client deliberately instead of guessing at traffic.
        headers={"content-type": "application/json", "user-agent": USER_AGENT},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode()
            parsed = json.loads(raw or "{}")
            err = parsed.get("error", {}) or {}
            # The route answers rejections at the TOP level (`ok`/`code`/`message`/`issues`), not
            # nested under `error`. Reading only `error` discarded every field error the server
            # sent, so a precise message — which field, what was wrong — was thrown away and
            # replaced with "the server rejected the submission". Read both shapes.
            if not err and parsed.get("code"):
                err = {"code": parsed["code"], "message": parsed.get("message"),
                       "issues": parsed.get("issues"), "remediation": parsed.get("remediation")}
        except Exception:
            err = {}
        # A 403 with no parseable body is almost never a submission verdict. It is the layer in
        # FRONT of the submission route — a WAF or bot filter — refusing the client before anything
        # read the package. Saying "the server rejected the submission" sends the creator to edit a
        # skill that was never looked at, which is the worst possible direction to send them.
        if e.code == 403 and not err.get("code"):
            return _envelope(
                "blocked_before_review",
                "A gateway in front of the submission endpoint refused this client with 403 "
                "before the package was read. Nothing about the skill was evaluated, so do not "
                "change it. This is a transport problem: check that the request carries a "
                "User-Agent, and report the endpoint and time to whoever operates it.",
                EXIT_NETWORK)
        # A 5xx IS NOT A VERDICT ON THE PACKAGE, AND IT IS NOT AUTOMATICALLY TRANSIENT. This branch
        # exists because its absence was worse than a wrong message: with no 5xx handling, the agent
        # relaying the failure filled the gap with a guess — "a transient service unavailable" — and
        # advised retrying. The creator retried three times against a failure that was deterministic
        # for their package, spending a fresh consent token on each attempt.
        #
        # What was actually happening, confirmed server-side: the route runs an LLM projection step
        # BEFORE it persists anything, and that step failed. No row was written, so "nothing was
        # published" is true — but the same package fails the same way every time, so "transient" is
        # false. A minimal canary submitted successfully in the same window, which is exactly why the
        # outage reading was tempting and wrong.
        #
        # So: say what is known and bound the retry at one. A second identical failure is evidence,
        # not noise.
        #
        # AND DO NOT SEND THEM TO THE FORM. The first version of this branch did, which was the
        # obvious advice and wrong: the marketplace team confirmed the form posts to this same route
        # and awaits the same pre-persistence step, so it fails identically on the same package. An
        # escape hatch that is the same door is worse than no escape hatch, because the creator spends
        # another attempt learning that.
        if 500 <= e.code < 600:
            return _envelope(
                "server_error",
                f"The endpoint returned {e.code} and stored nothing, so this is not a verdict on "
                "your package and there is no partial submission to clean up. It may or may not be "
                "transient: retry ONCE. If the second attempt fails the same way, it is not an "
                "outage — something about this package is failing a step on the server, and further "
                "retries only spend another consent token each time. STOP THERE: the upload form "
                "posts to this same route and awaits the same step, so it is not an alternative. "
                "Send the endpoint, the time, this code and your package size to whoever operates "
                "the marketplace, and wait for them rather than retrying.",
                EXIT_NETWORK)
        detail = err.get("message") or "The server rejected the submission."
        if err.get("issues"):
            detail += f" Field errors: {json.dumps(err['issues'])}"
        if err.get("remediation"):
            detail += f" {err['remediation']}"
        return _envelope(err.get("code") or f"http_{e.code}", detail, EXIT_REJECTED)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return _envelope("unreachable",
                         f"Could not reach the submission endpoint ({e}). Nothing was submitted.",
                         EXIT_NETWORK)

    # The receipt carries the retry secret, so it is written to disk and its VALUE is never
    # printed — same rule as any other credential. The agent reports the path.
    receipt = {"receipt": payload, "retrySecret": body["retrySecret"],
               "requestId": body["requestId"], "packageSha256": digest}
    # RESOLVE THE PACKAGE ROOT BEFORE GOING BESIDE IT. This is the same defect the confirm-token
    # file already carries a fix for, in the same file, and the receipt never got it: `dirname` of a
    # directory package is its parent, which is right, but `dirname` of `<pkg>/SKILL.md` is the
    # PACKAGE, so submitting by file path wrote the receipt INSIDE the package it had just sent.
    #
    # Worse here than for the confirm file, because the receipt holds the retry secret. Observed on
    # a real submission: the package then failed validation with `portable_path` and
    # `unreferenced_file`, and `zip` produced an archive containing the secret — a credential
    # packaged for upload by the tool whose entire job is not to leak one.
    # AND NOT BESIDE THE PACKAGE EITHER — see `_state_dir`. The comment above records the fix for
    # writing this INSIDE the package; going beside it was the remaining half of the same defect,
    # and it is the worse half, because this file holds `retrySecret` and the parent directory is
    # very often a git repo the creator is about to commit. The path is reported in the output
    # below, so a creator can still find it; that line is now the only way to, which is the point.
    slug = _slug(blob, kind) or "submission"
    path = os.path.join(_state_dir(), f"{slug}-{_state_key(args.package)}.receipt.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=1)
    os.chmod(path, 0o600)
    out = {
        "state": payload.get("status") or "submitted_for_review",
        "submitted": True,
        "published": False,
        # The reference the submitter can quote. None of these are secret — the server minted
        # them and shows them on the review side — so withholding them would only mean opening a
        # 0600 file to read your own receipt. The retry secret stays unprinted; that rule holds.
        "submission_id": payload.get("submissionId"),
        "version_id": payload.get("versionId"),
        "skill_slug": payload.get("skillSlug"),
        "creator_slug": payload.get("creatorSlug"),
        # The server computes its own digest. Reporting BOTH sides of the comparison is the point:
        # if they ever differ, the bytes that arrived are not the bytes that were read from disk,
        # and that is worth more than any other line in this output.
        "package_sha256_local": digest,
        "package_sha256_server": payload.get("packageSha256"),
        "digests_agree": payload.get("packageSha256") == digest,
        "idempotent_replay": bool(payload.get("idempotentReplay")),
        "receipt_written_to": path,
        "note": ("Submitted for review — not published. The receipt file holds a private retry "
                 "secret; its value is deliberately not printed here. A person reviews the "
                 "submission and verifies identity before anything is published."),
    }
    print(json.dumps({k: v for k, v in out.items() if v is not None}, indent=1))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    for name, fn in (("preview", preview), ("send", send)):
        p = sub.add_parser(name)
        p.add_argument("package", help="the finished package: a .zip, or a directory holding only SKILL.md")
        # THE HELP STRING IS WHAT AN AGENT READS, so it carries the required/derived split rather
        # than a flat list of keys. It listed all five with no marking, and a real run asked the
        # creator for three of them "as optional" — reasonable, and three questions nobody needed.
        # `company` is free off the email domain; LinkedIn, byline, title and avatar are enriched on
        # our side and confirmed by a person before publication. Optional is not the same as ours.
        p.add_argument("--profile", required=True,
                       help='creator profile as JSON. ASK FOR: {"fullName":…}. You already have '
                            '"workEmail", and "company" comes off its domain. Do NOT ask for '
                            'linkedinUrl, byline, title or avatar — those are derived on our side '
                            'and confirmed by a person before anything publishes.')
        p.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                       help=f"the submission endpoint URL (default: {DEFAULT_ENDPOINT})")
        p.add_argument("--consent-version", default=CONSENT_VERSION)
        p.add_argument("--timeout", type=float, default=120.0)
        if name == "send":
            p.add_argument("--confirm", required=True, help="the confirm_token printed by `preview`")
            p.add_argument("--rights-confirmed", action="store_true",
                           help="set only after the creator agreed to the consent text")
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    # Reachable only via an explicitly emptied `--endpoint ""`, now that there is a default. Kept
    # because an empty string would otherwise be sent to urllib as a URL and fail somewhere far from
    # the cause.
    if args.mode == "send" and not args.endpoint:
        return _envelope("invalid_invocation",
                         "--endpoint was given as an empty value. Omit it to use the default "
                         f"({DEFAULT_ENDPOINT}), or pass a URL.", EXIT_VALIDATION)
    try:
        return args.fn(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        return _envelope("invalid_invocation", str(e), EXIT_VALIDATION)
    except Exception as e:                                    # noqa: BLE001
        return _envelope("internal_error", f"{type(e).__name__}: {e}", EXIT_INTERNAL)


if __name__ == "__main__":
    sys.exit(main())
