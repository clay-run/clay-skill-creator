# Jev: what this skill relies on

Read from TypeSafe's and OpenRouter's published documentation (docs.typesafe.ai: the API
reference, State, Confidence, the composite-scoring pattern and the Jev 1.13 "jaggedness" page,
last reviewed there 2026-09-17; openrouter.ai: the Jev guide). Re-read them before changing the
questions: the model and OpenRouter's route are both new.

## What Jev is

A decision model, not a chat model. You send a `state` and a map of typed `questions`; it
returns one typed answer per question with probabilities, and writes no text. This skill uses:

| Type | Asks | Answer fields read |
|---|---|---|
| **Noul** | yes or no | `noul`: probability of yes, 0 to 1 |
| **Choice** | one of a set of described options | `choice`, `probabilities` (sum to 1), `confidence` |

`instructions` may be an object: the question in one field, the data it refers to in others,
named in backticks. That is how each question carries only its own role. All questions for one
person go in one request.

## The two routes

| | TypeSafe direct | OpenRouter |
|---|---|---|
| Endpoint | `POST https://api.typesafe.ai/v1/systemone` | `POST https://openrouter.ai/api/alpha/decisions` |
| Auth header | `Authorization: Bearer` and the TypeSafe key | `Authorization: Bearer` and the OpenRouter key |
| Model (pinned) | `jev-1.13.0` | `typesafe/jev-1.13` |
| Key from | console.typesafe.ai/keys | openrouter.ai/settings/keys (no TypeSafe account needed) |
| Env var read here | `TYPESAFE_API_KEY` | `OPENROUTER_API_KEY` |

Versions are pinned, not aliased: an alias moves when a release ships, and the 0.6 and 0.4
thresholds were checked against one version. Every verdict records the model that answered
(`jev_model`).

## Price and limits

- **$0.042 per million input tokens; output is free.** Measured: about 800 to 1,100 input tokens
  for a short invented profile, about 2,200 on average for real ones (more roles, each classified),
  so four to ten cents per thousand people.
- Over TypeSafe's rate limit Jev answers `429`; overloaded, `529`. The verdict is then `failed`
  with the reason, the Audiences workflow writes nothing, and the person can be re-run.
- `401` bad key (rebuild after replacing it), `422` malformed request.

## What Jev is bad at, from its own documentation, and what this skill does about it

| Documented weakness | Here |
|---|---|
| Comparing dates | Every date is compared in code; Jev sees "March 2021" and "no end date", never a comparison to make |
| Counting items in a list | One question per role, combined in code, as TypeSafe's own counting advice says |
| Literal reading | Each question states one condition and describes both answers; the "still held?" wording names the cases (several fractional roles, a founder working elsewhere) |
| Large state full of irrelevant detail | The state is the headline; each question carries only its role |
| Structural invariants not guaranteed | Each decision is asked one way; code enforces the rest (an ended role is never held) |
| Adversarial content | A profile written to argue its own case can move an answer. Say so |
