# Rubric and evidence contract

The authoritative executable rubric is one JSON object. Generate the human-readable table from it;
do not maintain two independently editable copies. Use a new version for each approved change.

Required rubric keys: version, factors, grades, missing_policy, min_weighted_coverage. Weight sum is
100 without rounding or renormalization. Factor IDs are unique lowercase identifiers. Points are
0..100; numeric inputs are finite. The scale and missing-data rule are business decisions.

Each factor has id, name, weight, kind and none_score. Supported kinds:
- map: explicit lowercase string keys to points, including 'false' or '0' when those are valid categories.
- bands: inclusive [minimum, points] pairs; highest matching minimum wins. Values below the lowest
  minimum are invalid. Duplicate minima are invalid; nonmonotonic bands are allowed but cannot prove
  saturation when capped.
- linear: explicit from and to; points are clamped to 0..100. The to value must exceed from.

Optional modifiers are keyed deltas applied once per distinct approved flag, then clamped. Unknown
flags are invalid. No modifier is applied to a missing observation. Zero-weight factors do not run,
do not contribute coverage and do not block. They still need a valid definition.

Grades are explicit {min, label} entries with unique nonempty labels and minima including zero.
The unrounded total selects the grade; the displayed score is rounded to two decimals afterward.
No score has the meaning of a probability.

missing_policy is 'hold' or 'score_none'. score_none is allowed only when the installer approves
explicit none_score values. None means a successful search without a usable observation, not proved
absence. Weighted coverage is the sum of weights whose values were observed and usable. None and
imputed values contribute no coverage; observed zero and false do. The fixed 100-point denominator
never shrinks. min_weighted_coverage is explicit. The hold policy blocks none even at a low threshold.

An account has account_id, domain, matched_domain, identity_status='matched', fixed score_as_of,
optional approved_domain_aliases, optional review_reasons, and factors keyed by factor ID.
review_reasons must be a list of nonempty strings; any reason blocks the whole account before
factor coverage. Use explicit configured scope, not an implicit education or industry override. Domain normalization strips scheme,
www and path; it does not collapse subsidiaries or infer public suffixes. Mismatches hold unless the
alias is explicitly approved. Do not declare a match just because the provider run completed.

Each observation is {value, status, evidence, source, flags?}. status is found, none, failed or capped.
Unknown/unwired status holds. Source and nonempty evidence are required even on none. Preserve
observed_at, source record ID/URL and retrieval metadata when available. Stale or conflicting evidence
is normalized to failed with the reason before scoring. The scorer does not invent freshness rules.

Capped map data always holds. Numeric capped data can score only when allow_saturated_count=true
and monotonic bands prove the observed lower bound is already in the top band. A page of 12 CRM
products cannot prove a warehouse or competitor is present. If all required technology categories
were individually observed, emit found for the proven category value and retain the cap in metadata.
A clean provider miss is none, never proof of tool absence.

A scored result has total, grade, components (points, weight, contribution, status), accepted evidence,
weighted coverage, version, identity and reason. Reasons name the strongest and weakest weighted
contributions using the same accepted evidence. A held result has null total/grade, empty components
and evidence, blocking_inputs and latest-attempt metadata. Raw upstream evidence is retained separately
for debugging and re-scoring, not published as a valid held-account enrichment.

No entity-type exclusion, grade lift, size override or fit-to-eligibility rule is implicit. This
candidate scorer deliberately rejects a hidden default instead of copying the original author's ICP.
Complex overrides need a separately reviewed deterministic extension and corresponding boundary tests.
The synthetic fixture is executable format documentation, not a suggested production rubric.
