# Workflow → skill

**Every number in this file was measured on 97 real workflows, 840 nodes, in one shared workspace on
2026-08-31.** Where it says most or rarely, there is a rate behind it.

A workflow tells you the MECHANISM and usually not the PURPOSE. **57% of workflows carry no agent
prompt anywhere**, and for those the config cannot say what the workflow is for — only what it does.
So reading a workflow replaces the derivation half of the interview and never the judgment half.

## 1. Find the workflow

```
clay whoami
clay workflows list --filter creator.id=<me>     NOT owner.id — see below
```

**The scope field is `creator.id`, not `owner.id`.** Tables use `owner.id` and workflows do not.
Copy the table rule here and you get an unscoped list of a shared workspace's workflows, whose names
encode customers and deals exactly as table names do.

Expect noise. In the measured workspace, of the first 200 workflows **92 were untitled** and 37 more
matched *test*, *scratch*, *copy of* or *demo*. **And a good name proves nothing**: 13 of 110 probed
had a sensible GTM name and zero nodes.

**BUT ONLY THE LIST IS SCOPED. THE READ IS NOT — and that is the common case, not the exception.**
`graph get` works on any workflow the account can see, whoever created it. So a creator who already
knows which workflow they mean **pastes its id or URL and skips the listing entirely**, and that is
the better path: it is faster, it needs no scope decision, and it cannot surface a colleague's
workflow they did not ask for.

Verified rather than assumed: all 97 workflows measured for this file were created by other people
and read cleanly from an account owning none of them.

**SO RUN THE SCOPED LIST, AND ASK IN THE SAME MESSAGE.** `--filter creator.id=<me>` returns their own
workflows and nobody else's, so it costs one call and exposes nothing — the leak this section warns
about is *widening* past the creator, which this never does. One message, not two:

> Which workflow? Paste its id or URL. I also see 12 under your name — I can read them all and pick
> out the strongest instead, if you'd rather.

**This used to say "ask for the workflow before offering to list", and that was wrong for one reason
and half-wrong for another.** The reason: a creator who pastes one id then never learns that several
are possible, so the capability existed and nobody could find it. The half: *the list is 46% junk* is
an argument for RANKING the list, not for refusing to fetch it — §1b is that ranking. What survives
unchanged is the scope: never widen past `creator.id`, and if they want a teammate's workflow, ask
for the id.

**An empty scoped list is a real answer and must not read as a failure.** One account in the measured
workspace had **zero** of 2,403 workflows under its own `creator.id` — they exist, someone else
created them. Say nothing was found under their name and ask for the id.

**Widening the list is the creator's call, taken out loud.** The table route already sets this
precedent: where a workspace has several owners, owner confirmation is the first interview question,
before any read. Same here. If they want a teammate's workflow, ask for the id — never widen the
listing silently, because workflow names encode customers and deals exactly as table names do.

### 1b. Several at once — rank silently, offer the strongest three

**THE DOOR IS §1'S SCOPED SCAN, WHICH ALWAYS RUNS.** The offer is made in the same message as *which
workflow?*, so a creator who has twelve hears about it once, in one turn, without having to know the
feature exists. If they paste one id anyway, that is an answer and this section does not fire.

**RANK, NEVER JUST LIST.** When several come back, offer the strongest rather than handing over the
names: 92 of 200 untitled, 37 more matching *test* or *copy of*, and a good name proving nothing.
Somebody who did not name a workflow is telling you they cannot pick, and a raw list is a poor answer
to that.

The second door is plurality they state themselves: *all my workflows*, *a bunch of these*, or more
than one id pasted at once.

**AND THE FIRST VERSION OF THIS SECTION HAD NO DOOR AT ALL.** It opened *"when a creator arrives with
many workflows rather than one"* — a state nothing detected, while §1 above says in bold to ask for
the workflow first. So the section shipped as prose no path could reach, which is the same defect as a
route offered by a picker that cannot render it. **A capability whose trigger is undefined is not a
capability.**

Then: read and draft the lot, and offer a short start. Do **not** ask whether they want them ranked,
do **not** ask how many they have, and do **not** explain that some parts batch and others do not.
Derive first and ask only what deriving cannot settle — the same rule the rest of this flow runs on.

Score each one off its configuration alone. **Every signal is already measured above:**

| Signal | Read from | Why it ranks |
|---|---|---|
| a real decision exists | a conditional in rules **or** code (§4) | a chain with no branch is plumbing, and plumbing productizes into nothing |
| thresholds are written down | numbers in prompts, code, `formulaText` (§6) | a skill can carry a number it can find; it cannot carry one that was never written |
| the graph does work | node count, and the **edges** (§2) | 13 of 110 probed had a sensible GTM name and **zero nodes** |
| not a scratch copy | untitled, or matching *test*, *scratch*, *copy of*, *demo* | 92 of 200 untitled, 37 more matching those words |

**A NAME IS NOT A SIGNAL, AND `#runs` IS NOT ONE EITHER.** They are the two obvious proxies and both
are wrong: the measurement above is a good name proving nothing, and a heavily-run workflow is as
likely to be plumbing somebody depends on as a play worth publishing. Rank on what the config holds.

Then say it in two short paragraphs, and their shape is deliberate:

> All 12 read and drafted. The mechanical half batches fine — the graph, the thresholds, the
> topology, the packaging.
>
> These three look strongest — `account-tiering`, `renewal-risk-radar`, `inbound-router`. Want to
> start with them?

**NO COUNT OF WHAT WAS CUT, NO CRITERION, AND NO TIME ESTIMATE.** Each was drafted and each was
wrong. *"Ranked by how much of a real play is actually in the config"* grades their work and invites
an argument about the ranking before a single skill exists. A duration — *"about 90 seconds each"* —
is a number nobody has measured, which is the exact thing this kit forbids a skill from doing.
**"These three look strongest" already carries everything the creator needs**: that there were more,
that a judgement was made, and that they are free to name a different one.

**Nothing announces the questions that are coming.** An earlier draft opened with *"the insight
doesn't batch — for each one I need two things from you"*, and it was cut for the same reason the
route question enumerates nothing: describing the process is not running it. §9's interview happens
per skill when they say yes, where each question is about a draft in front of them.

**Then run the normal route per skill, one at a time, best first.** Batching removed the reading and
the drafting. It removed nothing from §9. If they ask for all twelve, they get all twelve on the same
terms — a batch is a starting point, not a cap.

**And the answer sheet is what makes the second one fast.** Their product, their CRM, their field
names and their ICP are identical across every skill they own, so skill two onward asks only what the
sheet does not already cover. That is what bulk was really reaching for, and it already exists.

## 2. Read the graph

```
clay workflows graph get <id> --mode summary    shape, triggers, node types, edges
clay workflows graph get <id> --mode full       THE CONFIGURATION. Required.
```

**`clay workflows get` is not the config read.** It returns id, name, url, createdAt, creator, and
nothing else. Two things follow that cost a whole pass if you learn them late:

- **`--mode full` is mandatory, not an optimisation.** In summary mode `routingCriteria` was empty on
  **all 97** workflows while 45 carried conditional nodes. Branch logic is never on the edge.
- Size is about 3.5 kB per node, so a 31-node workflow is one 127 kB read. No pagination needed.

**Read-only allowlist, and it is an allowlist because this surface writes far more than tables do:**
`list`, `graph get`, `graph validate`, `nodes get`, `diagram`. **Never** `runs` (spends), **never
`nodes test`** (executes, and reads like a read), never `code`, never `graph format` (mutates
layout), never any `create` / `update` / `delete` / `publish` / `triggers` write form.

## 3. Evidence precedence — the same rule, renamed

| Order | Read | Evidence of | NOT evidence of |
|---|---|---|---|
| 1 | `agentPrompt`, node `description` | **intent** — why the node exists | the mechanics |
| 2 | `rulesConditionalConfig`, `code`, `tools`, edges, `mapConfig` | **mechanics** — ground truth for every deterministic claim | intent |
| 3 | node names | nothing on their own | anything |

**Intent may be wrong and still be faithfully recorded; mechanics may not.** Measured, not assumed:
a 5-node workflow described its conditional as routing *"high-value, mid-market and lower-tier leads
with different follow-up strategies"* while its code read

```python
if tier == "Tier 1":
    context.transition_to("Notify rep in Slack", "tier1")
```

One tier routed. Two computed, named, and dropped. **A reading that trusted that description would
have shipped a skill confidently wrong about the only thing it does.** So quote a description as the
author's stated purpose and never as behaviour.

## 4. Branch logic is in two places and you need both

| Where the condition lives | Share of 116 conditional nodes |
|---|---:|
| `rulesConditionalConfig` — machine-readable | 72% |
| `code` — must be read as code | **26%** |
| no description at all | 32% |

**A reader that only parses `rulesConditionalConfig` silently loses a quarter of every decision in
the library.** And the loss is not spread evenly across unimportant branches: in the best-designed
workflow read, the two undocumented code conditionals were **both human approval gates** — the nodes
deciding whether anything got sent at all. Code, so no rules. No description, so no prose.

`endRunOnNoMatch` is the fallthrough policy and it is the difference between a routed lead and a
dropped one. `false` means unmatched continues to whatever node has no rule; `true` means the run
stops. State which, always.

## 5. Iteration, cost, and what a node name promises

**ITERATION IS ON THE NODE, IN `listMode`, AND THAT IS WHERE TO LOOK FIRST.** A tool node that runs
per row sets `listMode: true` and `listEntriesRef: {path, sourceNodeId}` — which names **the exact
list and the node it comes from**, so the fan-out is a pointer and not a guess:

| How iteration is expressed | Workflows | Nodes |
|---|---:|---:|
| `listMode` + `listEntriesRef` | **21 (21%)** | **57**, all 57 with the ref |
| loop language in a node name only | 9 (9%) | — |
| a real `map` node | 1 (1%) | 1 |

**An earlier version of this file said a `map` node was the only place fan-out is quantified. That
was wrong, and it was wrong in the expensive direction** — it sent the reader hunting for the 1%
form, finding none, and calling a priceable run unpriceable. `map` is the rarity; `listMode` is
twenty-one times commoner and strictly more informative. Read `listMode` on every tool node, then
chain the refs: a 16-node workflow read this way prices as *posts × 3 interaction calls, one
enrichment per unique engager, 3 CRM calls per qualified lead* — a shape, exact, from the config.

Node names still matter for the 9% that iterate with `listMode` unset, and there the run is
mis-priced by a factor of the row count. Check both.

**COST: derive the BOUND where the config gives you one, then confirm the number.** Two places carry
a figure, and they are different kinds of thing:

- the **action's own input title** — `"Max number of results (0.5 credits / result)"`. Catalogue
  metadata, machine-readable, in **3 of 97** workflows (also `0.1 credits per person`). Multiply it
  by a `listEntriesRef` length and you have a real upper bound.
- a **prose description**, in **1 of 97**. A freak, and not a source.

So: never state a run's cost as derived, and never claim it is underivable either. Where a unit price
and a fan-out ref are both present, show the bound and say it is a bound — the per-workspace price
and the real list lengths still decide the figure, so the number is asked for regardless.

**A GATE NAMED IN A NODE NAME IS NOT A GATE — COUNT THE CONDITIONAL NODES.** Measured on a 16-node
workflow that creates Salesforce records: one node is called
`SF: Lookup existing Lead/Contact [STUB — gate create on empty result]`, and its edge runs
**unconditionally** into `SF: Create Lead`. The workflow contains **zero** conditional nodes. So it
creates a Lead for every qualified person on every scheduled run, duplicate or not, and the check
that was supposed to prevent it exists only inside the square brackets.

The same workflow tagged four nodes `[STUB — …]` and carried `FILL THESE IN` and *"field paths below
are placeholders"* in its routing code. **An unfinished workflow announces itself in exactly this
register**, and a read that narrates it as working describes a system that does not exist. So: before
stating that anything is gated, deduped, or skipped, find the node that does it. If the only evidence
is a name, the answer is that the workflow does not do it yet — which is a finding, and for a
workflow that writes, the most important one.

**Prompts can grant override authority over deterministic fields.** One classifier prompt told the
agent to *"use the website content to sanity-check or override when the employee count looks stale"* —
a judgment override of a firmographic number, invisible to any structural read and the most
important behavioural fact in that workflow. Read every prompt for permissions, not just for intent.

## 6. Where thresholds come from, and why you cannot inherit them

Extract every number from mechanics, then check it against the prose that mentions it. One workflow
had `foundedYear >= 2011` in its rule and *"founded in 2011 or later (within the last 15 years)"* in
its prompt. **Those agree in 2026 and diverge every year after.** So a threshold read out of a
workflow becomes a **declared input with the read value as its default**, never a constant, and
never the relative phrasing.

## 7. The low-yield boundary

A workflow is too thin to build from when the config gives you names and nothing else. The stub with
`New Enrich Node` and `New Map Node` is the clear case: four nodes, no descriptions, no prompts, one
tool. **A skill assembled from names like that is invention wearing a citation.** Say the workflow is
too thin, say which of the two things is missing — the purpose or the mechanics — and offer the
interview instead. That is a real answer and not a failure.

## 8. Which thresholds earn a question

**The budget is three CLASSES, not three questions** — the flow says *budget by class, not by turn
count*, and *one decision is one question even when it has two moving parts*. So the four thresholds
in a ten-node workflow are one class and one question, shown together with the config's values as
defaults. Do not re-derive that rule here; it already holds.

What this route adds is **which** thresholds belong in that question at all, because a workflow hands
you more numbers than a table does and most of them are not decisions:

| Read from the config | In the question? |
|---|---|
| a size cut-off that switches which path a record takes | **yes** — it changes who gets contacted |
| an activity window deciding what counts as flagged | **yes** |
| a country or segment list that switches routing | **yes** |
| tier values on a score **nothing branches on** | **no** — ask why it is computed, not what it should be |
| retry counts, concurrency, timeouts, page sizes | **no** — declare with the read value as default |

**The test is what changes, not what is unknown.** A number earns its place in the question when
changing it changes who gets contacted or what gets spent. Everything else is a declared input
carrying the read value, shown rather than asked.

**The insight is not one of the three.** It is the Step 1 question, it comes first, and on this route
it is the thing most likely to be missing altogether — 57% of workflows have no prompt to carry it.

## 9. What the interview must still ask

Because the config does not hold it, at these measured rates:

- **The insight and the ICP** — 57% of workflows have no prompt to carry either.
- **What a run costs** — 99% have no figure anywhere.
- **What the unused branches are for** — a workflow that computes a tier it never routes is not a
  spec, it is a question.
- **Who the destinations are** — one router assigned nine owners; 9 of 10 owner nodes had no
  description saying who they are.
- **Which steps halt** — declared by the creator, never inferred. See `## What this skill touches`.
  A workflow gate is usually one step waiting on both the spend and the send, and that is **two
  entries on one step number** — `Step 3 spend-approval, Step 3 send-approval` — never a compound
  word. The vocabulary is closed and the first skill built on this route tried to widen it.

Everything else — topology, tools, thresholds, gates, fallthrough, output shape — comes out of the
graph and does not need asking.

## 10. THE SKILL MUST BUILD THE WORKFLOW, NOT DESCRIBE IT

**This is the route's payoff and the first skill it produced got it wrong.** `inbound-lead-router`
read a real 5-node workflow faithfully, declared `mechanism: workflow`, and its body derived as
**`logic-only`** — because it said *"wire five nodes in dependency order"* and named the node types in
prose, and never once told the installing agent to create one.

Think about what the installing agent does with that. It reads *"score the lead with a deterministic
code step"*, scores the lead in the conversation, and finishes. **Nothing was built.** Building nodes
in someone's workspace is a write, it needs an approval, and it is more work than just doing the task
— so a skill that merely describes the shape gets the shape done once, by hand, and the machine the
workflow existed to be never appears.

Not a one-off: of the six `mechanism: workflow` skills in the library, **four derive as something
else** — only `renewal-risk-radar` and `track-champion-job-changes` carry a build step. Two thirds of
the workflow skills promise a workflow and do not build one. The declaration is free; the build step
is the thing.

So a workflow-route skill carries a **Build** step, and `renewal-risk-radar` is the shape that
passes:

1. **Say why it is a workflow rather than an agent loop** — a signal starts it, and nobody is present.
2. **Confirm node syntax against the installed version first** — `clay workflows nodes --help`.
   **Never hardcode the command form.** This is what keeps a concrete build step portable: the agent
   reads the help on the CLI it actually has instead of trusting a form we pinned months ago.
3. **Name the nodes in dependency order** with type, what feeds each one, and the edges — or point at
   a `references/` file carrying the graph, which is what the passing skill does.
4. **Carry the node traps**, because they are what makes a build fail halfway and leave a broken
   workflow. Re-measured on GA 2026-10-07: a tool node does not echo its own inputs, so trigger fields
   cannot ride through it, and `graph validate` checks neither merge shape nor pin paths. Retired by GA:
   asymmetric merges complete, deep pins resolve, empty pins no longer fail a run, and a tool pin of
   `"$"` returns the envelope rather than erroring.
5. **A `MUST` on where judgment lives** — a code node, never an LLM node. The LLM node is for prose,
   never for comparison or routing.
6. **State the topology, read off the EDGES.** See the three rules below — this is where a build
   hangs.
7. **The write gate**, then set it live.

### Topology: three rules, and none of them is a question for the creator

**A creator should never be asked about graph mechanics.** Most will not know, the route knows more
about node behaviour than they do, and asking buys nothing. These are judgments the route makes and
*writes down* — the failure mode is not asking too little, it is deviating invisibly.

**1. TOPOLOGY IS IN THE EDGES, NEVER IN THE NODE LIST.** Read `incomingEdges` / `outgoingEdges` per
node. A list of four tool nodes after one code node looks like a fan and can be a chain; the list
cannot tell you. Measured: a 10-node workflow whose four enrichments read as parallel from the node
list is wired **strictly serially** — every node `in=1, out=1`. This page previously asserted the
opposite, from the list rather than the edges, and was wrong.

**2. REPRODUCE THE SOURCE'S SHAPE. DEVIATE ONLY WHEN YOU CAN NAME WHAT THE DEVIATION NEEDS — AND
WRITE THE DEVIATION INTO THE SKILL.** Four independent enrichments *could* run in parallel: same
credits, lower latency. But parallel means four branches converge before the next node, a
convergence needs a **merge node the serial shape never needed**. That merge no longer hangs on GA, but
it is still a component the serial shape did not have, with its own config to get wrong. So a
"simplification" that adds one needs to buy something real.

Two tests before changing a shape:

- **What does it need that the source did not have?** If you cannot specify that component, build the
  source's shape.
- **Who feels the benefit?** Latency matters when a human waits. On a per-account unattended trigger
  nobody waits, so the gain is zero and the risk is not. Same credits either way.

When you do deviate, the skill says so and why — *"the source wires these serially; built parallel
here because every dependency is on the trigger record"* — so an installer debugging a hang can see
the change existed. A deviation nobody recorded is indistinguishable from a mistake.

**3. A CHAIN IS NOT A WATERFALL UNLESS A GATE SITS BETWEEN ITS STEPS.** This is a cost-claim check,
not a topology one, and it is the cheapest mistake to make. A waterfall tests after each step and
stops on a hit, so ordering it cheap-first genuinely saves money. A plain chain runs every step every
time, so ordering saves **nothing**. Both look like `A → B → C → D`.

The difference is whether a `conditional` node sits between them, which is a fact in the config.
**So before writing that an order saves anything, look for the gate.** A real skill shipped
*"in cost-ascending order where the installer's prices differ"* over four enrichments that always all
run — waterfall language on a chain, which tells the installer they are saving money they are not.

**AND THE CODE SAMPLES CARRY PLACEHOLDERS, NOT THE SOURCE WORKFLOW'S VALUES.** This is where a
faithful read turns into a portability leak, and it happened on the first skill that passed every
other check on this page. Three instances, all the same mistake:

- the write node's field names came through as `clay_fit_score`, `clay_account_tier` — so every
  installer's audience would get fields named after **someone else's** workflow
- a plan name appeared as `EXPANSION_PLAN = "Pro"` in a code node, marked `# DECLARED INPUT` and
  still a literal
- the enrichments were listed in order, when the source runs them in parallel

**A value marked as a declared input in the table and hardcoded in the sample is still hardcoded**,
because the sample is what gets copied into the node. So the declared-inputs table names it, and the
code sample reads it — `EXPANSION_PLAN = context.get_input("expansion_plan")`, field names from the
installer's mapping. The source's values belong in prose, labelled as what the source used, never in
a line someone will paste.

A skill declaring `mechanism: workflow` whose body carries no build step **blocks** in validation. The
finding names the missing step rather than the vocabulary, because the fix is a build step and not a
sprinkle of the words `code node`.
