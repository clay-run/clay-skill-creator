# Writing a deterministic skill

**The test, and it fits in one sentence: could two competent installers follow this step and end up
calling different things?** If yes, the step describes what *you* did rather than instructing anyone.

"Enrich the author to get an email" fails that test. Every reader resolves it differently: a different
function, different inputs, a different bill.

It does **not** mean reproducible output. A company hires, a domain moves, a page is rewritten: same
input, different answer, and that is correct. It means **the same instruction produces the same calls.**
Determinism lives in the mechanism, never in the data.

## First decide the shape, because the rest of this file assumes one of them

Two shapes. Choosing wrong costs more than any pricing mistake below: a mispriced step ships a wrong
number, the wrong shape ships a skill that cannot run.

**Call the functions.** The agent runs the loop: it calls named functions, compares, judges, and writes
the result. This is the default, it is what most skills are, and everything after this section is about
doing it well.

**Build a workflow.** Nodes, a trigger, edges. Two forcing conditions and no others: something has to
run when no agent is present, or the volume and cadence exceed what one conversation can hold. The cost
is real, and it is below. **Confirm how nodes get built on the installed
version — `clay workflows nodes --help` — and do not write "there is no CLI for this" into a skill.**
As of 0.8.1 `nodes create/update/test` exist; a skill that routes only to plugin tools is a dead end on
a machine with no plugin. **Re-measured on GA 2026-10-07:** an asymmetric merge node completes and
receives both branches (the old "balancer" workaround is obsolete), a pin two hops back resolves, and an
empty or unresolvable pin no longer fails the run. A tool node still does not echo its own inputs, so
trigger fields cannot ride through it — carry them around it. A tool pin of `"$"` resolves to the whole
envelope `{result, success, textPreview}`; `"$.result"` skips the wrapper, and the validator no longer
flags either. `graph validate` does not check merge shape or pin paths, so a draft run is the only real
check.

**Tables are not a third option.** No table-creation command appears anywhere on the surface this kit
touches, and that surface is four commands: `clay whoami`, `tables list`, `columns list`, `columns get`,
all reads, and the reads may be gated by plan. `tables rows` is the installer's data and is never
needed; `tables update` mutates, but only to toggle query sync. **Treat a table as something you read
an existing recipe out of, not something a skill builds** — and note the shape of that claim: an
absence across the commands we call, not a platform measurement.

One absence that reads like a gap and is not: there is no `use-ai` or Claygent action on this surface.
That costs a function-calling skill nothing, because the agent reading the skill **is** the model:
Clay supplies the facts, the agent supplies the judgment. (The workflow palette does have an LLM node,
a different thing. Use it for prose, never for extraction, comparison or routing.)

## The four things any step that spends money must name

| | Why it cannot be left implicit |
|---|---|
| **What runs**, the `(packageId, actionKey)` pair | "enrich" is a category. Several functions do it, at different prices, returning different fields |
| **What goes in**, which fields from which declared input | otherwise field mapping is a guess, and that is where silent misses come from |
| **What to verify in the response** | a call can succeed and return nothing useful. See below |
| **What it costs, and who confirms before it runs** | spend without a stated number is spend without consent |

One row per paid step, in the skill. A reader can then price the run before starting it.

## Name what you expect, confirm it at runtime, fail loudly if it is gone

Three rules, and the third is what makes the first two safe.

1. **Name the function you expect**: the key, its declared cost, and the field you will read out of the
   response. A step that names nothing has a cost gate with nothing to price.
2. **Confirm it against the live catalogue before relying on it**, using the commands below.
3. **Fail loudly when the named function is absent.** Never silently substitute the nearest thing.

Rule 3 is the one people skip, and the cost of skipping it is that **dead and acquired companies enrich
perfectly well on last-known data**. A run that substitutes an enrichment call for an unavailable
liveness probe goes green, fills every row, and asserts that defunct companies are alive. A filled row
is not a live company. The [identity and domains](references/functions/identity-and-domains.md) leaf has
the incident.

**Do not ship a frozen catalogue** — a list of names presented as current with no instruction to
re-check. The two failure modes are not symmetric: a stale name is a wrong hint rule 2 catches, while
**no name at all is a step that spends money and cannot say on what**, which is measurably the more
common failure.

The procedure, which outlives any particular name:

```
clay --version                     keep it current; an outdated CLI refuses to run at all
clay routines list --limit 100     what managed functions this workspace has
clay routines get <id>             its declared cost; the LIST call does not carry costs
clay workflows actions list        the action catalogue, greppable
clay workflows actions schema <packageId> <actionKey>    the real input parameters
```

**Confirm those command names with `--help` against your installed version.** A skill that hardcodes a
subcommand ages the same way one that hardcodes a provider does.

**Which surface answers which question, and what its arms returned, is in
[`references/functions/`](references/functions/README.md): read the index, then the one leaf for the
job.** If the skill *finds* records rather than enriching known ones, that leaf is
[`search-people.md`](references/functions/search-people.md) — **the search row is thinner than its own
filters, so anything judged or linked beyond what was filtered is a per-row bill.** Read
[`NO-FUNCTION-EXISTS.md`](NO-FUNCTION-EXISTS.md) *during* the interview, before you agree to build
something the platform cannot do.

### Seven ways a reasonable reading of the catalogue is wrong

Each one has been hit.

- **`actionKey` is not an identifier. The pair `(packageId, actionKey)` is.** Five keys were found
  colliding across packages on one read: `enrich-company` is one vendor at 10 credits *or* another at 8,
  different data behind the same key, and `update-lead` spans three different CRMs. Display names collide
  in the other direction too, the same underlying action appearing under different labels. Match on the
  pair and the schema, never on the label, and record the `packageId` you resolved.
- **A default list is not the whole list.** Listing returns a page, and a null cursor at exactly the
  default page size is *not* proof of completeness. Page through, or fetch by id. Never conclude a
  function does not exist from one list call.
- **Present does not mean callable.** A function can sit in the catalogue and still be unavailable to
  the CLI, because it has not been registered as a routine. Check, rather than assuming availability
  follows from existence.
- **A plural name does not mean batch.** Actions named for verifying *emails* accept exactly one email.
  Read the schema, not the name.
- **The description can be wrong where the schema is right.** A function described as working from a
  name and company may require a profile URL or an email address, and fail per item without one. **A
  schema's description is a claim, not a contract**, and that goes for documented workarounds too:
  "pass the domain in both fields and the URL arm falls back" was written from an action's own prose and
  hard-fails live with `ERROR_INVALID_INPUT`.
- **Undeclared inputs pass silently.** A run that *starts* proves nothing about whether your inputs were
  understood: extra keys are sometimes ignored and sometimes fail per item at run time. Trust the
  declared schema and the per-item result, never the fact that a run began.
- **`outputParameters` is a floor, never a ceiling, and sometimes it is absent entirely.** It was
  declared on **none** of nine company arms checked, and returned as `null` on a news arm. One action
  delivered eight fields against seven promised, and the undeclared extra was the most useful field in
  the payload. Read the whole response, and use an undeclared field if you say it is undeclared.

### Cost: two meters, neither on the list call, and one of them multiplies

- **Fetch by id for the declared cost.** The list call omits it.
- **Read `paymentType` before `creditCost`, because some actions have no credit price at all.** A row
  carrying `paymentType: Bring Your Own Account` runs on the installer's own connected account: Clay bills
  nothing, the vendor bills them. A gate written as *"state the `creditCost`"* is unsatisfiable there and
  the skill stalls waiting for a number that does not exist. The honest gate is *"no Clay credits, it runs
  on your own connected account"* — still a cost disclosure, just not numeric.
- **Read the action's own reported cost, never the workspace balance delta.** Responses carry
  `metadata.upfrontCreditUsage.totalCost` and `actionExecutionsUsed`. Balance movement is not a valid
  per-call measurement: in one build nine calls reported **11.8** credits while the balance moved
  **15.4**, because a parallel session was spending in the same workspace. Note also that the field is
  named *upfront*, which is what it is: upfront, not settled.
- **Credits and action executions are different currencies, and some steps consume only the second.**
  Observed: a classifier at 0 credits and 0 executions; managed person and company enrichment at 0
  credits and 1 execution each; a tier-2 email validator at 0 credits and 1 execution against a nominal
  0.1-credit catalogue price. Declared and billed cost also differ by plan, so **say which unit you are
  quoting and report what was actually charged**, never the catalogue figure.
- **Some `creditCost` values are PER-UNIT rates, and the basis lives in a parameter description rather
  than in the cost field.** This is the most expensive trap on the surface: a build priced from the cost
  field alone can understate by **up to 100×**. Two measured instances: a family in the
  [jobs signals](references/functions/signals-jobs.md) leaf where three of four arms reporting
  `creditCost: 8` bill per result found, and an address action billing **0.8 per operating location**, so
  its real call cost was 8 at the default and 80 at the cap. Read the parameter descriptions before pricing anything, and pass a
  cap where one exists. Where a description states no basis at all, the billing is **unknown**, not flat.
  Of 20 priced arms scanned, 4 were per-unit.
- **A miss can bill.** Four outcomes, and they price differently:

  | Outcome | Shape | Billed |
  |---|---|---|
  | Hit | values present | yes |
  | Miss, billed | `success: true`, `result: {}`, a "not found" preview string | **yes, 1 credit measured** |
  | Miss, refunded | `SUCCESS_NO_DATA` with `isRefunded: true` | net zero |
  | Rejected pre-execution | `success: false`, `status: ERROR_MISSING_INPUT`, e.g. a wrong parameter name | **no, free** |

  At least one phone-waterfall arm documents that it charges even when no number is found. Budget for
  misses, and report them as spend.
- **Probing is finite.** Test-run capacity is capped per workspace per day, so verify the calls that
  matter and note the ones you could not reach rather than planning on unlimited probes.

## The waterfall is the deterministic shape for enrichment

When several providers can answer the same question, the pattern that is both cheap and reproducible is
an **ordered set of calls where each one's run condition tests the specific output path of the one
before it**.

```
call A                          always runs, cheapest of the set
call B    runs only if   A's <named output field> is empty
call C    runs only if   A's and B's named fields are both empty
coalesce  first non-empty of A → B → C, as a typed waterfall column
```

Three details carry the whole pattern:

1. **The gate names a field, not a status.** `A ran` is not the condition; `A returned nothing at this
   path` is. Gating on completion buys every later call for nothing, and completion status is never
   data. See the next section.
2. **Order by cost, ascending, and the spread is worth ordering for.** Measured on one day, five
   observables each priced **1 to 10× apart** across providers: job postings 1 to 10, employee growth 1
   to 10, news 1 to 8, tech stack 4 to 8, funding 10 to 16. A four-proxy question is 3 credits per
   account on the cheap arms and about 30 on the dear ones: **900 versus 9,000 credits across 300
   accounts**, for identical output. Read the real costs at authoring time and say what order you chose
   and why.
3. **Cheapest is not cheapest when the cheap arm cannot answer the question.** Two forms, both measured.
   *Reachability*, where an arm at 0.5 credits that requires a profile URL costs 0.5 *plus a resolution
   call* from a domain-anchored list, dearer than the 1-credit arms that accept a bare domain and with
   one more failure point. *Filterability*, where the cheapest arm in a family may not filter on the
   dimension you need, and reading that dimension off an unfiltered page returns a confident zero. Route
   by whether the dimension is filterable at the source, and pay the difference.

**A waterfall is right for a fact and wrong for a metric.** It maximises coverage of something with one
true value. Where the arms do not share a scale, a column filled by whichever arm resolved first cannot
be ranked, thresholded, or diffed over time, which is every use a metric has. Waterfall the boolean and
the evidence, never the count.

## Reading a result: five things that are not what they look like

These are surface-wide. The per-family versions are in the leaves.

1. **Completion status is not data.** Run status came back SUCCESS or `complete` for *every* verdict, on
   every surface, in more than four independent builds. Gate on payload values, always. And the miss has
   at least five distinct shapes: `complete` + `{}`; `complete` wrapping an item-level `failed` with an
   upstream error; `complete` with `result: null`; `SUCCESS_NO_DATA`, sometimes refunded; and `complete`
   with the output field **present but empty-string valued**. The field existing is not data either, so
   gate on non-empty content.
2. **A null is not a zero.** One arm returned nine time horizons with the most recent one null and the
   others populated. Read as 0%, that null becomes a negative verdict assembled from a data gap, and the
   most recent horizon is the one a freshness-minded author reaches for first.
3. **Compare band strings as bands, but make the rule per field.** Size and revenue arrive as
   `"1,001-5,000 employees"`, and a naive `parseInt` yields **1**, silently fails the band, and demotes
   the row. The refinement a blanket rule gets wrong: the same payload often carries an *exact* integer
   headcount beside the band. In order, then: use the exact count where it exists and name the field you
   used; never invent a number from a band; never discard an exact count because a sibling field is a
   band.
4. **`0` and `false` are observed values, not absences.** Never test presence by truthiness, and coerce
   only after the presence test. In one scoring build a truthiness test promoted a failing row to a
   perfect top tier.
5. **Count the right unit.** One arm returned 10 rows that were **4 distinct titles across 6 locations**,
   with `jobCount: 33` also available. "33 openings", "10 postings" and "4 roles" are all true, answer
   different questions, and the raw row count overstates distinct roles about 8×.

And one that decides whether any of the above matters: **a wrong-entity hit is shaped exactly like a
right one.** Where a response echoes the entity it matched, that echo is the *only* detector, and an
echo comparator must exclude the TLD, because `com` substring-matches "company" in every profile URL and
washes the check out entirely.

## Four more traps that cost real debugging

- **A wrong-workspace id can return not-found at a success exit code.** Absent and inaccessible look
  identical unless you distinguish them.
- **Concurrency has a ceiling that is not yours.** Providers rate-limit, and a fan-out that works on ten
  rows fails on a real list. State the cap you used.
- **Silent truncation exists and does not announce itself.** One string output ended mid-name at exactly
  8,192 characters with no flag. Treat an exact-8,192 result as incomplete.
- **A field's name is not evidence of its content.** A production build carries a field named for
  revenue that actually holds an employee count. Read the formula or the payload, never the label.

## Provenance, and how this file goes wrong

**This file carries what applies to every skill. The names, prices and field shapes live in
[`references/functions/`](references/functions/README.md), each leaf dated.**

**Observed 2026-08-07 – 2026-08-14**, one workspace, one plan, by builds that spent the credits.
**Report what you read; never quote a figure here to a user as their price.** Structural facts do not rot
the way prices do. If a rule here contradicts the live catalogue, **the catalogue wins and this file is
wrong.** Say so in the skill you are writing.

## Before you ship a step, ask it out loud

> Could two competent installers read this and call different things?

If yes, the step is not finished. The fix is never longer prose. It is naming the four things above.
