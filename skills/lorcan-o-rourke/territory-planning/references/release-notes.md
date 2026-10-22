# 2.0-rc4 scope and measured evidence

This skill interviews a team and builds explainable account-fit scoring. A frozen entity-level carve
proposal is optional. It is not v1.9 feature parity, a production certification or a general CRM writer.

## RC4 changes

The external pool/check/export wrappers used during RC3 testing had unsafe behavior: missing/null
protection could become false, unsupported family policy could become entity policy, and a checker
could trust a proposal's fabricated capacities. RC4 moves strict wrappers into the portable package:
- scripts/carve_pipeline.py validates explicit policy and complete account attributes before freezing;
- scripts/build_carve_workflow.py renders/creates a manual replay-only scoring-to-proposal draft;
- scripts/test_carve_pipeline.py tests guards, provenance, ledger reconciliation and export refusal;
- references/carve-fixture.json supplies six explicitly synthetic, fictional local cases.

The carve engine is unchanged. The independent checker derives capacities and loads from the original
snapshot, not the proposal. A held/protected/excluded account assignment or falsified book total
raises before usable output rows. Missing protection/exclusion and unsupported policy stop before
freezing a pool. The built-in example now routes all its made-up scores through fixture_accounts so
exports identify them as synthetic_fixture rather than saved research.

The workflow replay bound is 1..50 saved evidence cases and 50 total accounts including synthetic
fixtures. All accounts share one capacity ledger. The local engine/checker has a separate 2,000-entity
implementation bound. Neither is a product limit or authorization to split a population.

## Measured technical acceptance

- 146 offline tests cover arithmetic, missingness/coverage, identity, normalization, research preflight,
  source/freshness handling, graph construction, the unchanged carve engine, strict pool/check/export
  logic and parsed CSV readback. One additional RC4 packaging check ensures the built-in fixture's
  exported score provenance is explicitly synthetic. Offline fixtures do not establish business fit.
- The prior independent five-case scoring workflow replay matched local normalization, deterministic
  results and every exported CSV cell. It reused saved evidence, not fresh research.
- Nine whole-population live carve cases exercised the strict wrappers on a 12-account/five-rep
  fixture. The baseline and reordered cases completed. Seven unsafe-input cases stopped at the
  intended pool guard with no frozen pool, proposal or export. Reordering preserved proposals, books,
  checks and export rows; the frozen snapshot itself retained supplied rep-list order.
- Deliberately corrupted proposals (held assignment, fabricated capacity, and both) were rejected by
  the export code in Clay's runtime. The live valid fixture was independently reconciled against its
  original accounts, protections, buckets, existing loads and capacities.
- Saved live code/wiring were read back and the tested draft passed graph validation. These bounded
  tests do not prove globally optimal books, production scale or arbitrary territory policies.

The creator's exact-archive validation and any fresh-agent acceptance are recorded separately from
this package. Do not infer fresh-agent discovery from unit tests, a clean terminal or this note.

## Evidence retained from RC3

Five named live seller-motion cases retained sources and inspection dates through export and were
reproduced locally. Two produced totals under the demo rubric; two held on headcount count/band
conflicts; one institution held at an explicitly configured company-only scope check. No expected
business grades were invented.

Retail checkout plus confirmed sales-assisted wholesale can support hybrid selling and mixed buyers.
Generic bulk quantity or a support email does not establish business buyers. Unreadable material
routes and nonempty unresolved research notes hold. Sources must be inspected official target or
approved-alias URLs. Procurement describes buying, not selling. Seller motion and customer segment
are separate criteria; the demo is not a B2B-only buying-propensity model.

Earlier research attempts, including an unsupported unresolved note that held safely, remain in the
creator's private audit. A completed research step alone was never counted as a correct verdict.

## Explicit limits

The reusable scoring builder implements size + seller motion using supplied company snapshots,
either replaying saved research or adding bounded seller research. Other factor/provider paths need
reviewed adapters. The scoring-to-carve builder only replays saved evidence. Both render by default;
explicit creation produces an unpublished manual draft and starts no run.

No Audience or Salesforce score writer ships. A separate one-Account, five-field Salesforce plumbing
experiment verified a supplied test fixture by readback. Its final checker needed a tracking-timestamp
correction and was checked against the saved response. It did not recompute a business rubric, deliver
all score components, test held-attempt preservation or establish integrated CRM acceptance. Its
private credentials, IDs, test data and helper code are not part of this package.

No real business-owner calibration, predictive lift, general classifier accuracy, real-population
carve, automatic refresh, full-population execution or production use is certified. An interview-led
installation must obtain its own approved rubric and five-account calibration before scale-up.
No provisioning/reset, record deletion, family rollup, manager/draft/dynamic allocation, revenue
optimization, existing-book rebalancing or owner execution is implemented. Unsupported requests stop.

## Release and submission

Run the complete suite against the exact extracted archive, validate its layout/action references and
verify its content manifest. A genuinely fresh agent should discover this exact installed skill and
check the documented local paths without prior conversation or private receipts. Record anything it
could not check as unconfirmed rather than passing.

Answer sheets, raw customer evidence, live receipts, test kits, audit reports and approval records
stay outside the installable/submitted ZIP. Submission requires review of the exact package, the
submitter's confirmed details/rights and explicit consent after preview. It enters human review and
does not publish a listing or activate any workflow.
