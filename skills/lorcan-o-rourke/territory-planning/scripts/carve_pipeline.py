"""Strict reviewed pool + independent proposal audit. No CRM or owner writes.

build_snapshot(scored_accounts, allocation) requires explicit policy and account
attributes. The fixture-only escape hatch is labeled and unavailable in real mode.
check_and_export(snapshot, proposal) raises before returning rows on ANY violation.
Clay handlers are supplied by build_carve_workflow.py. Standard library only.
"""
import json
import math

ACCOUNT_COLUMNS = ['snapshot_id', 'rules_version', 'fixture_only', 'account_id',
                   'score_provenance', 'allocation_provenance', 'scoring_status',
                   'account_fit_score', 'eligible', 'bucket', 'current_owner_id',
                   'protected', 'excluded', 'protection_source', 'status',
                   'proposed_owner_id', 'reason']
BOOKS_COLUMNS = ['snapshot_id', 'rules_version', 'fixture_only', 'rep_id', 'buckets',
                 'capacity', 'existing_load_outside_snapshot', 'existing_in_snapshot',
                 'total_load', 'proposed', 'over_capacity']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_value(value, name):
    value = json.loads(value) if isinstance(value, str) else value
    require(isinstance(value, dict), name + ' must be an object')
    return value


def text(value, name, empty=False):
    require(isinstance(value, str) and (empty or bool(value.strip())), name + ' must be an explicit string')
    return value


def flag(record, name):
    require(name in record and type(record[name]) is bool, 'explicit boolean required: ' + name)
    return record[name]


def nonnegative_int(value, name):
    require(type(value) is int and value >= 0, name + ' must be a nonnegative integer')
    return value


def fit_number(value, name):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100,
            name + ' must be finite in 0..100')
    return value


def eligible(status, score, cutoff):
    require(status in ('scored', 'held'), 'scoring_status must be scored or held')
    if status == 'held':
        require(score is None, 'held account must not have a score')
        return False
    return fit_number(score, 'account_fit_score') >= cutoff


def unique_rows(rows, name, id_field):
    require(isinstance(rows, list), name + ' must be a list')
    result = {}
    for row in rows:
        require(isinstance(row, dict), name + ' entry must be an object')
        rid = text(row.get(id_field), id_field)
        require(rid not in result, 'duplicate ' + id_field)
        result[rid] = row
    return result


def validate_snapshot(snapshot):
    snapshot = object_value(snapshot, 'snapshot')
    text(snapshot.get('snapshot_id'), 'snapshot_id')
    text(snapshot.get('rules_version'), 'rules_version')
    require(snapshot.get('grain') == 'entity', 'only entity-level preview is supported; no implicit family rollup')
    require(snapshot.get('method') in ('snake', 'round_robin'), 'only snake and round_robin are supported')
    cutoff = fit_number(snapshot.get('min_eligible_score'), 'min_eligible_score')
    fixture = flag(snapshot, 'fixture_only')
    accounts = unique_rows(snapshot.get('accounts'), 'accounts', 'account_id')
    require(len(accounts) <= 2000, 'preview is capped at 2000 entities; do not split the shared ledger')
    reps = unique_rows(snapshot.get('reps'), 'reps', 'rep_id')
    require(bool(reps), 'nonempty reps required')
    for rep in reps.values():
        nonnegative_int(rep.get('capacity'), 'capacity')
        nonnegative_int(rep.get('existing_load_outside_snapshot'), 'existing_load_outside_snapshot')
        buckets = rep.get('buckets')
        require(isinstance(buckets, list) and bool(buckets), 'explicit rep buckets required')
        for bucket in buckets:
            text(bucket, 'rep bucket')
        require(len(buckets) == len(set(buckets)), 'duplicate rep bucket')
    for account in accounts.values():
        aid = account['account_id']
        protection = flag(account, 'protected')
        flag(account, 'excluded')
        flag(account, 'eligible')
        customer = flag(account, 'is_customer')
        opportunity = flag(account, 'has_open_opportunity')
        owner = text(account.get('current_owner_id'), 'current_owner_id', empty=True)
        text(account.get('bucket'), 'bucket', empty=True)
        text(account.get('protection_source'), 'protection_source')
        text(account.get('exclusion_source'), 'exclusion_source')
        require(account.get('allocation_provenance') == ('fictional' if fixture else 'reviewed'),
                'allocation provenance does not match fixture_only')
        require(account.get('score_provenance') in ('saved_evidence', 'synthetic_fixture'),
                'explicit score provenance required')
        require(fixture or account['score_provenance'] != 'synthetic_fixture', 'synthetic scores require fixture_only=true')
        if owner or customer or opportunity:
            require(protection, 'existing owner/customer/open opportunity must be explicitly protected: ' + aid)
        if protection:
            require(bool(owner), 'protected account requires a current owner: ' + aid)
            text(account.get('protection_reason'), 'protection_reason')
        if account['excluded']:
            text(account.get('exclusion_reason'), 'exclusion_reason')
        expected = eligible(account.get('scoring_status'), account.get('account_fit_score'), cutoff)
        require(account['eligible'] == expected, 'eligibility disagrees with reviewed policy: ' + aid)
        if 'requested_rep_id' in account:
            text(account['requested_rep_id'], 'requested_rep_id')
    return snapshot, accounts, reps


def build_snapshot(scored_accounts, allocation):
    allocation = object_value(allocation, 'allocation')
    # Validate policy BEFORE construction; never replace unsupported policy with a default.
    require(allocation.get('grain') == 'entity', 'only entity-level preview is supported; no implicit family rollup')
    require(allocation.get('method') in ('snake', 'round_robin'), 'only snake and round_robin are supported')
    fixture = flag(allocation, 'fixture_only')
    cutoff = fit_number(allocation.get('min_eligible_score'), 'min_eligible_score')
    scores = unique_rows(scored_accounts, 'scored_accounts', 'account_id')
    synthetic = unique_rows(allocation.get('fixture_accounts', []), 'fixture_accounts', 'account_id')
    require(fixture or not synthetic, 'synthetic scores require fixture_only=true')
    require(not set(scores).intersection(synthetic), 'duplicate account_id across saved and synthetic scores')
    attributes = unique_rows(allocation.get('account_attributes'), 'account_attributes', 'account_id')
    require(set(attributes) == set(scores) | set(synthetic), 'account attributes must match every scored account exactly')
    accounts = []
    for aid in sorted(set(scores) | set(synthetic)):
        score = (scores if aid in scores else synthetic)[aid]
        attrs = attributes[aid]
        # Copy explicit attributes. Do not coerce bools, invent ownership or hide unknown protections.
        row = {'account_id': aid, 'scoring_status': score.get('scoring_status'),
               'account_fit_score': score.get('account_fit_score'),
               'eligible': eligible(score.get('scoring_status'), score.get('account_fit_score'), cutoff),
               'score_provenance': 'saved_evidence' if aid in scores else 'synthetic_fixture',
               'allocation_provenance': 'fictional' if fixture else 'reviewed'}
        for field in ('protected', 'excluded', 'current_owner_id', 'bucket', 'is_customer',
                      'has_open_opportunity', 'protection_source', 'exclusion_source'):
            require(field in attrs, 'missing reviewed account attribute: ' + field + ' for ' + aid)
            row[field] = attrs[field]
        for field in ('protection_reason', 'exclusion_reason', 'requested_rep_id'):
            if field in attrs:
                row[field] = attrs[field]
        accounts.append(row)
    snapshot = {'snapshot_id': allocation.get('snapshot_id'), 'rules_version': allocation.get('rules_version'),
                'grain': allocation['grain'], 'method': allocation['method'], 'fixture_only': fixture,
                'min_eligible_score': cutoff, 'accounts': accounts, 'reps': allocation.get('reps')}
    validate_snapshot(snapshot)
    return snapshot


def check_and_export(snapshot, proposal):
    """Independent safety checks: recompute from INPUT accounts and reps, not reported totals.

    This checks policy compliance and accounting, not globally optimal value balance.
    Any failure raises before checks/rows can be emitted by the saved export handler.
    """
    snapshot, accounts, reps = validate_snapshot(snapshot)
    proposal = object_value(proposal, 'proposal')
    for key in ('snapshot_id', 'rules_version', 'grain'):
        require(proposal.get(key) == snapshot[key], 'proposal context mismatch: ' + key)
    require(proposal.get('proposal_only') is True, 'proposal_only must be true')
    outputs = unique_rows(proposal.get('accounts'), 'proposal accounts', 'account_id')
    books = unique_rows(proposal.get('books'), 'proposal books', 'rep_id')
    require(set(outputs) == set(accounts), 'proposal must account for every input exactly once')
    require(set(books) == set(reps), 'proposal books must match every input rep exactly once')
    additions = {rid: 0 for rid in reps}
    existing = {rid: 0 for rid in reps}
    for aid, account in accounts.items():
        row = outputs[aid]
        owner = account['current_owner_id']
        if owner in existing:
            existing[owner] += 1
        require(row.get('current_owner_id') == owner, 'current owner changed: ' + aid)
        require(row.get('bucket') == account['bucket'], 'bucket changed: ' + aid)
        text(row.get('reason'), 'proposal reason')
        picked = text(row.get('proposed_owner_id'), 'proposed_owner_id', empty=True)
        status = row.get('status')
        if account['protected'] or owner:
            expected_status = 'protected'
        elif account['excluded']:
            expected_status = 'excluded'
        elif not eligible(account['scoring_status'], account['account_fit_score'], snapshot['min_eligible_score']):
            expected_status = 'not_eligible'
        else:
            expected_status = None
        if expected_status:
            require(status == expected_status and not picked, 'ineligible or protected account assigned: ' + aid)
        elif status == 'proposed':
            require(picked in reps, 'proposed rep is not in reviewed population: ' + aid)
            require(account['bucket'] in reps[picked]['buckets'], 'proposed rep cannot serve bucket: ' + aid)
            require(not account.get('requested_rep_id') or picked == account['requested_rep_id'],
                    'named rep request changed: ' + aid)
            additions[picked] += 1
        else:
            require(status == 'unowned' and not picked, 'invalid eligible disposition: ' + aid)
    for rid, rep in reps.items():
        book = books[rid]
        before = rep['existing_load_outside_snapshot'] + existing[rid]
        added = additions[rid]
        require(added <= max(0, rep['capacity'] - before), 'proposal exceeds reviewed remaining capacity: ' + rid)
        expected = {'capacity': rep['capacity'], 'total_load': before + added,
                    'proposed': added, 'over_capacity': max(0, before + added - rep['capacity'])}
        for field, value in expected.items():
            nonnegative_int(book.get(field), 'book ' + field)
            require(book[field] == value, 'book disagrees with input ledger: ' + rid + ' ' + field)
    checks = [{'check': name, 'pass': True} for name in (
        'explicit_reviewed_policy', 'every_account_once', 'every_rep_once',
        'protected_and_ineligible_not_assigned', 'owner_and_bucket_unchanged',
        'rep_bucket_and_named_request', 'capacity_from_input_ledger',
        'book_totals_from_assignments', 'existing_overflow_disclosed', 'reasons_retained')]
    arows, brows = [], []
    common = {k: snapshot[k] for k in ('snapshot_id', 'rules_version', 'fixture_only')}
    for aid in sorted(accounts):
        account, result = accounts[aid], outputs[aid]
        row = dict(common)
        for key in ('account_id', 'score_provenance', 'allocation_provenance', 'scoring_status',
                    'account_fit_score', 'eligible', 'bucket', 'current_owner_id', 'protected',
                    'excluded', 'protection_source'):
            row[key] = account[key]
        row.update({key: result[key] for key in ('status', 'proposed_owner_id', 'reason')})
        arows.append(row)
    for rid in sorted(reps):
        row = dict(common)
        row.update(rep_id=rid, buckets='|'.join(sorted(reps[rid]['buckets'])),
                   existing_load_outside_snapshot=reps[rid]['existing_load_outside_snapshot'],
                   existing_in_snapshot=existing[rid])
        row.update({key: books[rid][key] for key in ('capacity', 'total_load', 'proposed', 'over_capacity')})
        brows.append(row)
    return {'checks': checks, 'account_rows': arows, 'books_rows': brows}


def pool_handler(context):
    scored = json.loads(context.get_input('scored_accounts_json'))
    snapshot = build_snapshot(scored, context.get_input('allocation_json'))
    return {'snapshot_json': json.dumps(snapshot, allow_nan=False, sort_keys=True)}


def export_handler(context):
    result = check_and_export(context.get_input('snapshot_json'), context.get_input('proposal_json'))
    return {field + '_json': json.dumps(result[field], allow_nan=False, sort_keys=True)
            for field in ('checks', 'account_rows', 'books_rows')}


if __name__ == '__main__':
    import csv
    import sys
    if len(sys.argv) != 5:
        raise SystemExit('usage: carve_pipeline.py snapshot.json proposal.json accounts.csv books.csv')
    with open(sys.argv[1], encoding='utf-8') as f:
        snapshot = json.load(f)
    with open(sys.argv[2], encoding='utf-8') as f:
        proposal = json.load(f)
    result = check_and_export(snapshot, proposal)  # Before opening either output file.
    for path, fields, rows in ((sys.argv[3], ACCOUNT_COLUMNS, result['account_rows']),
                               (sys.argv[4], BOOKS_COLUMNS, result['books_rows'])):
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        with open(path, encoding='utf-8', newline='') as f:
            parsed = list(csv.reader(f))
        require(len(parsed) == len(rows) + 1 and all(len(row) == len(fields) for row in parsed),
                'CSV readback failed')
    print('Wrote and checked account and books CSVs; proposal only.')
