"""Portable scoring-to-carve REPLAY draft. Render only unless --create.

No provider/research node, CRM writer, field creation, execution or publication.
One complete frozen population per run, one shared allocation ledger. Bound: 50
accounts including explicit synthetic fixture rows; never silently split a ledger.
Input evidence_json is a list of context/company/research snapshots. allocation_json
uses the strict contract in references/pool-and-carve.md. Rubric is fixed in code.
"""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import build_workflow as scoring_builder

ROOT = Path(__file__).resolve().parent.parent


def graph(rubric):
    # Reuse the reviewed adapter's size + seller-motion rubric validation.
    scoring_builder.graph(rubric, 'replay')
    field, pin = scoring_builder.field, scoring_builder.pin
    pipeline = (ROOT / 'scripts/carve_pipeline.py').read_text()
    replay = ((ROOT / 'scripts/normalize_account.py').read_text() + '\n' +
              (ROOT / 'scripts/score_account.py').read_text() + '\nRUBRIC = ' + repr(rubric) + '''

def handler(context):
    evidence = json.loads(context.get_input('evidence_json'))
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 50:
        raise ValueError('evidence_json requires 1..50 saved cases; do not split a shared ledger')
    scored, audit = [], []
    for case in evidence:
        account = normalize(case['context_json'], case['company_json'], case['research_json'])
        result = score(RUBRIC, account)
        scored.append(result)
        audit.append({'account': account, 'result': result})
    return {'scored_accounts_json': json.dumps(scored, allow_nan=False, sort_keys=True),
            'scoring_audit_json': json.dumps(audit, allow_nan=False, sort_keys=True)}
''')
    def spec(label, name, code, inputs, outputs, previous):
        return {'label': label, 'spec': {'name': name, 'nodeType': 'code', 'code': code,
                'inputSchema': {'type': 'object', 'properties': inputs, 'required': list(inputs)},
                'outputSchema': {key: field(description) for key, description in outputs.items()},
                'incomingEdges': [{'sourceNode': '@' + previous}]}}
    pool_code = pipeline + '''

def handler(context):
    result = pool_handler(context)
    if len(json.loads(result['snapshot_json'])['accounts']) > 50:
        raise ValueError('controlled replay workflow is capped at 50 total accounts; do not split the ledger')
    return result
'''
    return {'scope': 'unpublished manual replay; scoring and proposal files only; no CRM or owner writes',
            'mode': 'carve-replay',
            'trigger': {'triggerType': 'manual', 'inputSchema': {
                'type': 'object', 'properties': {
                    'evidence_json': field('JSON list of saved company and research cases'),
                    'allocation_json': field('Explicit reviewed policy, account protections and rep ledger as JSON')},
                'required': ['evidence_json', 'allocation_json']}},
            'nodes': [
                spec('score', 'Replay scoring with evidence audit', replay,
                     {'evidence_json': pin('trigger', '$.evidence_json')},
                     {'scored_accounts_json': 'Complete deterministic results for saved evidence',
                      'scoring_audit_json': 'Normalized accounts and full scoring provenance'}, 'trigger'),
                spec('pool', 'Validate policy and freeze pool', pool_code,
                     {'scored_accounts_json': pin('score', '$.scored_accounts_json'),
                      'allocation_json': pin('trigger', '$.allocation_json')},
                     {'snapshot_json': 'Strict frozen pool; missing protections and unsupported policy are errors'}, 'score'),
                spec('carve', 'Carve proposal only', (ROOT / 'scripts/carve_preview.py').read_text(),
                     {'snapshot_json': pin('pool', '$.snapshot_json')},
                     {'proposal_json': 'Proposed owners and books; no assignments are written'}, 'pool'),
                spec('export', 'Check input ledger before export', pipeline + '\ndef handler(context):\n    return export_handler(context)\n',
                     {'snapshot_json': pin('pool', '$.snapshot_json'),
                      'proposal_json': pin('carve', '$.proposal_json')},
                     {'checks_json': 'Independent safety checks; any failure stops before export',
                      'account_rows_json': 'Reviewed account proposal rows with fixture labels',
                      'books_rows_json': 'Books independently reconciled to the input capacity ledger'}, 'carve')]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rubric', required=True, type=Path)
    parser.add_argument('--create', action='store_true')
    parser.add_argument('--name', default='Account fit and carve proposal')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    plan = graph(json.loads(args.rubric.read_text()))
    if args.create:
        if not args.receipt or args.receipt.resolve().is_relative_to(ROOT.resolve()):
            parser.error('--create requires a private --receipt outside the package')
        result = scoring_builder.create(plan, args.name, args.receipt)
        print(json.dumps({key: result.get(key) for key in ('workflow_id', 'url', 'state')}, indent=2))
    else:
        print(json.dumps(plan, indent=2))
