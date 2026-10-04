# Working in this repository

This tree is the kit for authoring a Clay GTM skill and submitting it to the marketplace.
**`START-HERE.md` is the entry point**; this file only carries what an agent cannot infer from the
tree, and points at the pages that say the rest.

## If the `clay-skill-author` skill is already loaded, follow it and stop reading here

That skill IS this kit's procedure. When it is available — installed as a plugin, or invoked by name
— it is the authority on what happens next, and re-deriving the steps from these files instead will
produce a slower and worse version of the same thing. Everything below is for the case where it is
NOT loaded and you are working from the tree directly.

**One exception, and it is about which copy is newer rather than which is better.** An installed copy
is frozen at install time and nothing updates it on its own. Its Step 0a fetches the published version
and switches to it, so normally this resolves itself. But if you are reading this tree AND that skill
is loaded AND it announces an older version than this tree declares, **say both numbers and follow the
tree** — this file is the one you can see is current. And if a clone of this repo is already on disk
from an earlier run, `git pull` it before reading: a stale clone is the same trap wearing different
clothes.

## Three things worth knowing before writing a skill

- **One `SKILL.md` at the package root.** Supporting files go under `references/` or `scripts/`,
  and every one of them must be referenced from the body. `PACKAGE-LAYOUT.md` is the contract.
- **A skill has to run on someone else's machine.** No table ids, column ids, account handles or
  credentials in the body — those belong to whoever wrote it, not whoever installs it. Everything
  the installer supplies goes in a `## Declared inputs` table, with what happens when it is absent.
- **Nothing is sent without an explicit yes.** `tools/submit_skill.py` previews first and refuses to
  send without a token that only the preview mints, so a submission cannot happen as a side effect.

## Checking a package

    python3 tools/package_skill.py validate <package-dir>

**If the package names a Clay action, fetch the catalogue first or nothing checks the actions it
calls** — `tools/fetch_action_catalog.py --package <dir> -o /tmp/catalog.json`, then pass
`--action-catalog /tmp/catalog.json`. Without it, `ok` means the shape is right and says nothing
about whether the action still exists or accepts the parameters named. `VALIDATION.md` has both
commands and what the second one blocks on.

`VALIDATION.md` says what each exit code means and which findings block. `DETERMINISM.md` covers
choosing between Clay functions when more than one would do the job, and
`references/functions/` carries what each surface actually returned — read its index, then the one
leaf for the job.

## Do not edit this tree

Your skill is its own package, written wherever you are working. Nothing you build belongs inside
these files, and an edit here does not travel with your submission.

## Where the worked examples are

`examples/` is a curated set of finished skills — the format demonstrated rather than described —
including a low-yield case: what an honest skill looks like when the source table did not hold
enough to convert. `skills/` holds skills other people have published; read them for reference, and
note they are their authors' work rather than part of this kit.
