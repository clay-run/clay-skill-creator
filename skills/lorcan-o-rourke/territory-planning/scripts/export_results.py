"""Build an audit row from explicit step outputs; write CSV with csv.DictWriter.

Clay handler inputs: result_json, account_json. Output: row_json (string).
Local CLI: python3 export_results.py rows.json results.csv
rows.json is an array of row objects or handler outputs containing row_json.
Source columns describe the latest attempt; valid published evidence remains in
result_json only. Held rows never receive a total, grade or published components.
"""
import json

COLUMNS = ['account_id', 'domain', 'scoring_status', 'score', 'grade',
           'weighted_coverage', 'rubric_version', 'score_as_of',
           'employee_count', 'headcount_source', 'headcount_date',
           'headcount_date_basis', 'selling_motion', 'customer_segment',
           'motion_source', 'motion_observed_at', 'size_status', 'motion_status',
           'headcount_issue', 'motion_issue', 'consumer_sales_evidence',
           'business_sales_evidence', 'unresolved_sales_routes', 'motion_sources_json', 'reason', 'warnings']


def obj(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError('expected an object')
    return value


def make_row(result, account):
    result, account = obj(result), obj(account)
    for k in ('account_id', 'domain', 'score_as_of'):
        if result.get(k) != account.get(k):
            raise ValueError('export identity/context mismatch: ' + k)
    if result.get('scoring_status') not in ('scored', 'held'):
        raise ValueError('unrecognized scoring status')
    if result['scoring_status'] == 'held' and (result.get('account_fit_score') is not None or result.get('account_fit_grade') is not None or result.get('components') or result.get('evidence')):
        raise ValueError('held result contains a published score or evidence')
    size = account.get('factors', {}).get('size', {})
    motion = account.get('factors', {}).get('motion', {})
    row = {'account_id': result['account_id'], 'domain': result['domain'],
           'scoring_status': result['scoring_status'], 'score': result.get('account_fit_score'),
           'grade': result.get('account_fit_grade'), 'weighted_coverage': result.get('weighted_coverage'),
           'rubric_version': result.get('rubric_version'), 'score_as_of': result.get('score_as_of'),
           'employee_count': size.get('value'), 'headcount_source': size.get('source'),
           'headcount_date': size.get('observed_at'), 'headcount_date_basis': size.get('freshness_basis'),
           'selling_motion': motion.get('selling_motion'), 'customer_segment': motion.get('customer_segment'),
           'motion_source': motion.get('source'), 'motion_observed_at': motion.get('observed_at'),
           'size_status': size.get('status'), 'motion_status': motion.get('status'),
           'headcount_issue': size.get('evidence') if size.get('status') != 'found' else '',
           'motion_issue': motion.get('evidence') if motion.get('status') != 'found' else '',
           'consumer_sales_evidence': motion.get('consumer_sales_evidence', ''),
           'business_sales_evidence': motion.get('business_sales_evidence', ''),
           'unresolved_sales_routes': motion.get('unresolved_sales_routes', ''),
           'motion_sources_json': json.dumps(motion.get('source_urls', []), allow_nan=False),
           'reason': result.get('account_fit_reason'), 'warnings': '; '.join(account.get('warnings', []))}
    if motion.get('status') == 'found' and (not row['motion_source'] or not row['motion_observed_at']):
        raise ValueError('accepted motion lost its structured provenance')
    return row


def step_output(outputs, field):
    """Explicitly support the observed code/agent envelope, not arbitrary recursion."""
    outputs = obj(outputs)
    nested = outputs.get('structuredOutputs', {})
    if not isinstance(nested, dict):
        raise ValueError('invalid structuredOutputs')
    if field in outputs and field in nested and outputs[field] != nested[field]:
        raise ValueError('conflicting output field: ' + field)
    if field in outputs:
        return outputs[field]
    if field in nested:
        return nested[field]
    raise ValueError('missing output field: ' + field)


def handler(context):
    row = make_row(context.get_input('result_json'), context.get_input('account_json'))
    return {'row_json': json.dumps(row, allow_nan=False, sort_keys=True)}


if __name__ == '__main__':
    import csv
    import sys
    if len(sys.argv) != 3:
        raise SystemExit('usage: export_results.py rows.json results.csv')
    with open(sys.argv[1], encoding='utf-8') as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise SystemExit('rows must be an array')
    rows = [obj(r['row_json']) if isinstance(r, dict) and 'row_json' in r else obj(r) for r in rows]
    if any(set(r) != set(COLUMNS) for r in rows):
        raise SystemExit('row fields do not match the declared export contract')
    with open(sys.argv[2], 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with open(sys.argv[2], encoding='utf-8', newline='') as f:
        parsed = list(csv.reader(f))
    if any(len(r) != len(COLUMNS) for r in parsed):
        raise SystemExit('CSV field-count verification failed')
    print('Wrote and parsed ' + str(len(rows)) + ' audit rows.')
