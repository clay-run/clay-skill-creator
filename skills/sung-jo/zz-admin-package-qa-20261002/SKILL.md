---
name: zz-admin-package-qa-20261002
description: Temporary synthetic package test for Marketplace Admin. Returns a supplied test label without using external systems.
license: MIT
---

# Temporary package QA

This is an owner-authorized test fixture, not a production workflow or customer example. It exists only to check package publication and replacement. Version 1 is the baseline.

## Declared inputs

| Input | Installer supplies | If missing |
| --- | --- | --- |
| Test label | A short synthetic label, such as Sample A | Ask for a test label before continuing |

## What this skill touches

- **Reads**: the supplied test label and the packaged reference text.
- **Writes**: a response in the current conversation only.
- **External systems**: none.

## Workflow

1. Read the supplied test label. Ask for it if missing.
2. Read references/unchanged.txt for the fixed QA context.
3. Return the test label and the baseline version marker in the response.

## Outputs

- Test label: the exact label supplied by the user.
- Package revision: baseline-v1.

## Example prompt

Run the temporary package QA with the test label Sample A.

## Representative output

| Test label | Package revision |
| --- | --- |
| Sample A | baseline-v1 |

## Supporting files

scripts/main.py contains a synthetic revision marker only. It is not an executable workflow and does not need to run. references/unchanged.txt must stay byte-identical during the replacement test.

All sample values in this fixture are fictional test data.
