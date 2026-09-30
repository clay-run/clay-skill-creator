# Jev: what this skill relies on

Read from TypeSafe's and OpenRouter's published documentation on 2026-09-28 (docs.typesafe.ai: the
API reference, Models, Confidence, the composite-scoring pattern and the Jev 1.13 "jaggedness" page;
openrouter.ai/docs: the Jev hub and the Jev tutorial). Re-read them before changing anything here:
the model, its limits and OpenRouter's route are all new.

## What Jev is

A decision model, not a chat model. You send a `state` (the record) and a map of typed `questions`;
it returns one typed answer per question with probabilities. It writes no text and gives no
explanations. Three question types: yes/no Nouls, categories (Choice) and scales (Score):

| Type | Asks | Answer fields this skill reads |
|---|---|---|
| **Noul** | a yes/no question | `noul`: probability of yes, 0 to 1. No `confidence` field; this skill uses `abs(2p - 1)` as its own confidence and says so |
| **Choice** | pick one of up to 255 options (each with an optional description) | `choice`, `probabilities` (per option, sum to 1), `confidence` |
| **Score** | place it on an ordered scale of 2 to 10 described levels | `score` (probability-weighted position, level 0 = first), `probabilities`, `legend`, `confidence` |

All questions for one record go in **one request**; Jev reads the state once and answers every
question in parallel.

## The two routes

| | TypeSafe direct | OpenRouter |
|---|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` | `POST https://openrouter.ai/api/alpha/decisions` |
| Auth header | `Authorization: Bearer <TypeSafe key>` | `Authorization: Bearer <OpenRouter key>` |
| Model sent (pinned) | `jev-1.13.0` | `typesafe/jev-1.13` |
| Key from | console.typesafe.ai/keys | openrouter.ai/settings/keys (no TypeSafe account needed) |
| Env var this skill reads | `TYPESAFE_API_KEY` | `OPENROUTER_API_KEY` |
| Request and answer shape | identical | identical, plus `id`, `provider` and `usage.cost` (USD) |
| Context | 64k tokens; 32k for state + longest question | 32k tokens |

OpenRouter also serves the same model at `POST https://openrouter.ai/api/v1/systemone` for
TypeSafe's SDKs. This skill uses the Decisions route because OpenRouter documents it for plain HTTP
calls and published a live response from it. The path carries `alpha`.

Versions are pinned rather than aliased (`jev-latest`, `~typesafe/jev-latest`) because TypeSafe says
an alias moves when a release ships, and tier cut-offs are tuned against one version. Every result
records the model that actually answered (`jev_model`).

## Price and limits

- **$0.042 per million input tokens; output is free** (both routes, as published). A rubric of three
  to eight questions with a few hundred words of record text is roughly 800 to 1,500 tokens, so a
  few cents per thousand records. `rubric_tool.py` prints the estimate for a real rubric.
- TypeSafe's published limits: 250,000 tokens/second and 1,200 requests/minute, "adjusting
  dynamically". Over the limit: `429`. Overloaded: `529`. The Clay step does not retry (Clay's retry
  options broke the step at run time), so a 429 or 529 leaves the record `failed` with "re-run
  later", and nothing is written.
- Errors: `401` bad key, `422` malformed request (the body names the field), `429`, `529`.

## What Jev is bad at, from its own documentation, and what this skill does about it

| Documented weakness | Here |
|---|---|
| Arithmetic, counting, numeric comparison | Headcount, revenue, any number: a `bands` **rule**, computed in code |
| Comparing dates | "How long ago": a `days_since` rule, computed in code |
| Literal reading | Each question states its exact condition and describes every option |
| Large state full of irrelevant detail | Only the fields some asked question `reads` are sent |
| Indirection | Instructions point at the field by name in backticks, e.g. `` `description` `` |
| Score levels are weak for interpolation | A Score's position is only used for points (as in TypeSafe's composite-scoring example), never to reconstruct a number |
| Adversarial content in state | Record text is data; a record written to argue for its own classification can move the answer. Say so to the installer |

## Confidence

Choice and Score answers carry `confidence`, derived from how concentrated the probabilities are.
TypeSafe's guidance is to set thresholds by the cost of each kind of mistake, not a round number.
This skill uses one floor per rubric (0.6 unless changed): answers under it are listed in
`needs_review`, and still contribute their expected points, so an unsure answer moves the score less
than a sure one.
