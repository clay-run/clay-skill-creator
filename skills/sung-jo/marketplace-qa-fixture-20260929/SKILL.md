---
name: marketplace-qa-fixture-20260929
description: Internal test fixture that counts supplied fictional labels. Use only for controlled Marketplace upload, draft and review checks. Keep unpublished.
license: MIT
category: research
---

# Marketplace QA fixture 20260929

This is a synthetic quality-assurance fixture, not a production Skill or customer recommendation. Keep its Marketplace submission unpublished.

## Declared inputs

- Labels: a short list of fictional labels supplied by the tester. This input is required. If it is missing, ask the tester to supply it before continuing. Do not obtain data from another source.

## Workflow

1. Read the supplied labels as plain text.
2. Count non-empty labels, retaining duplicates and preserving their original order.
3. Return the count and the unchanged labels in the output format below.

## Outputs

- Label count: the number of non-empty labels supplied.
- Labels: the original labels in their original order.

## Example prompt

Count these fictional labels: Fixture A, Fixture B.

## Representative output

Label count: 2
Labels:
- Fixture A
- Fixture B

## Limits

This fixture does not access accounts, read files, contact services, execute scripts or change records. All example labels are fictional. There are no credentials or external dependencies.
