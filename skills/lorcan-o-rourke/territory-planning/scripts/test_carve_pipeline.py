"""Fictional pool, tampered-proposal, builder and export regressions. No network."""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import carve_pipeline as pool
import carve_preview as engine
import build_carve_workflow as builder

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = json.loads((ROOT / 'references/carve-fixture.json').read_text())


class CarvePipelineTests(unittest.TestCase):
    def setUp(self):
        self.scores = copy.deepcopy(FIXTURE['allocation']['fixture_accounts'])
        self.policy = copy.deepcopy(FIXTURE['allocation'])
        self.policy['fixture_accounts'] = []

    def snapshot(self):
        return pool.build_snapshot(self.scores, self.policy)

    def result(self):
        s = self.snapshot()
        return s, engine.carve(s)

    def test_shipped_fixture_marks_every_score_synthetic(self):
        snapshot = pool.build_snapshot(FIXTURE['scored_accounts'], FIXTURE['allocation'])
        checked = pool.check_and_export(snapshot, engine.carve(snapshot))
        self.assertEqual(len(checked['account_rows']), 6)
        self.assertTrue(all(row['score_provenance'] == 'synthetic_fixture'
                            and row['fixture_only'] is True for row in checked['account_rows']))

    def test_fictional_happy_path(self):
        s, p = self.result()
        r = pool.check_and_export(s, p)
        self.assertTrue(all(c['pass'] for c in r['checks']))
        rows = {a['account_id']: a for a in p['accounts']}
        self.assertEqual(rows['good']['proposed_owner_id'], 'rep-a')
        self.assertEqual(rows['held']['status'], 'not_eligible')
        self.assertEqual(rows['protected']['status'], 'protected')
        self.assertEqual(rows['excluded']['status'], 'excluded')
        self.assertEqual(next(b for b in p['books'] if b['rep_id'] == 'rep-b')['over_capacity'], 1)

    def test_missing_protected_on_unowned_account(self):
        del self.policy['account_attributes'][0]['protected']
        with self.assertRaisesRegex(ValueError, 'protected'):
            self.snapshot()

    def test_null_protection(self):
        self.policy['account_attributes'][0]['protected'] = None
        with self.assertRaisesRegex(ValueError, 'explicit boolean'):
            self.snapshot()

    def test_string_and_numeric_booleans(self):
        for field in ('protected', 'excluded', 'is_customer', 'has_open_opportunity'):
            for bad in ('false', 'true', 0, 1, None, []):
                with self.subTest(field=field, bad=bad):
                    self.setUp()
                    self.policy['account_attributes'][0][field] = bad
                    with self.assertRaisesRegex(ValueError, 'explicit boolean'):
                        self.snapshot()

    def test_missing_exclusion(self):
        del self.policy['account_attributes'][0]['excluded']
        with self.assertRaisesRegex(ValueError, 'excluded'):
            self.snapshot()

    def test_missing_owner_never_means_unowned(self):
        del self.policy['account_attributes'][0]['current_owner_id']
        with self.assertRaisesRegex(ValueError, 'current_owner_id'):
            self.snapshot()

    def test_missing_protection_source(self):
        self.policy['account_attributes'][0]['protection_source'] = ''
        with self.assertRaisesRegex(ValueError, 'protection_source'):
            self.snapshot()

    def test_customer_and_opportunity_require_protection(self):
        for field in ('is_customer', 'has_open_opportunity'):
            with self.subTest(field=field):
                self.setUp()
                self.policy['account_attributes'][0][field] = True
                with self.assertRaisesRegex(ValueError, 'must be explicitly protected'):
                    self.snapshot()

    def test_existing_owner_requires_explicit_protection(self):
        self.policy['account_attributes'][0]['current_owner_id'] = 'rep-a'
        with self.assertRaisesRegex(ValueError, 'must be explicitly protected'):
            self.snapshot()

    def test_protected_without_owner(self):
        self.policy['account_attributes'][0].update(protected=True, protection_reason='fixture')
        with self.assertRaisesRegex(ValueError, 'requires a current owner'):
            self.snapshot()

    def test_family_is_not_silently_replaced(self):
        self.policy['grain'] = 'family'
        with self.assertRaisesRegex(ValueError, 'entity-level'):
            self.snapshot()

    def test_unsupported_method(self):
        self.policy['method'] = 'dynamic'
        with self.assertRaisesRegex(ValueError, 'snake and round_robin'):
            self.snapshot()

    def test_missing_policy_is_not_defaulted(self):
        for field in ('grain', 'method', 'min_eligible_score', 'fixture_only'):
            with self.subTest(field=field):
                self.setUp()
                del self.policy[field]
                with self.assertRaises(ValueError):
                    self.snapshot()

    def test_invalid_cutoff(self):
        for value in (True, '80', -1, 101, float('nan'), float('inf')):
            with self.subTest(value=value):
                self.policy['min_eligible_score'] = value
                with self.assertRaisesRegex(ValueError, 'finite'):
                    self.snapshot()

    def test_observed_zero_at_zero_cutoff(self):
        self.scores[0]['account_fit_score'] = 0
        self.policy['min_eligible_score'] = 0
        self.assertTrue(self.snapshot()['accounts'][1]['account_id'])
        self.assertTrue(next(a for a in self.snapshot()['accounts'] if a['account_id'] == 'good')['eligible'])

    def test_held_never_has_score(self):
        self.scores[1]['account_fit_score'] = 95
        with self.assertRaisesRegex(ValueError, 'held account'):
            self.snapshot()

    def test_exact_population_metadata_match(self):
        self.policy['account_attributes'].pop()
        with self.assertRaisesRegex(ValueError, 'match every scored account'):
            self.snapshot()

    def test_duplicate_ids(self):
        self.scores.append(copy.deepcopy(self.scores[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.snapshot()

    def test_synthetic_mode_requires_explicit_flag(self):
        self.policy['fixture_accounts'] = [self.scores.pop()]
        self.policy['fixture_only'] = False
        with self.assertRaisesRegex(ValueError, 'synthetic scores require'):
            self.snapshot()

    def test_fixture_provenance_survives_rows(self):
        self.policy['fixture_accounts'] = [self.scores.pop()]
        s, p = self.result()
        r = pool.check_and_export(s, p)
        self.assertEqual(next(a for a in r['account_rows'] if a['account_id'] == 'unmatched')['score_provenance'], 'synthetic_fixture')
        self.assertTrue(all(a['allocation_provenance'] == 'fictional' and a['fixture_only'] for a in r['account_rows']))

    def test_real_mode_provenance(self):
        self.policy['fixture_only'] = False
        self.assertTrue(all(a['allocation_provenance'] == 'reviewed' for a in self.snapshot()['accounts']))

    def test_order_invariance(self):
        s, p = self.result()
        self.scores.reverse()
        self.policy['account_attributes'].reverse()
        self.policy['reps'].reverse()
        s2 = self.snapshot()
        self.assertEqual(engine.carve(s2), p)
        self.assertEqual(pool.check_and_export(s2, p), pool.check_and_export(s, p))

    def test_tampered_held_assignment_is_rejected(self):
        s, p = self.result()
        row = next(a for a in p['accounts'] if a['account_id'] == 'held')
        row.update(status='proposed', proposed_owner_id='rep-a')
        with self.assertRaisesRegex(ValueError, 'ineligible or protected'):
            pool.check_and_export(s, p)

    def test_tampered_excluded_and_protected_assignments(self):
        for aid in ('excluded', 'protected', 'low'):
            with self.subTest(aid=aid):
                s, p = self.result()
                next(a for a in p['accounts'] if a['account_id'] == aid).update(status='proposed', proposed_owner_id='rep-a')
                with self.assertRaisesRegex(ValueError, 'ineligible or protected'):
                    pool.check_and_export(s, p)

    def test_capacity_is_from_inputs_not_output(self):
        s, p = self.result()
        p['books'][0]['capacity'] += 1
        with self.assertRaisesRegex(ValueError, 'book disagrees'):
            pool.check_and_export(s, p)

    def test_book_totals_recomputed(self):
        for field in ('total_load', 'proposed', 'over_capacity'):
            with self.subTest(field=field):
                s, p = self.result()
                p['books'][0][field] += 1
                with self.assertRaisesRegex(ValueError, 'book disagrees'):
                    pool.check_and_export(s, p)

    def test_output_book_booleans_not_integers(self):
        s, p = self.result()
        p['books'][0]['proposed'] = True
        with self.assertRaisesRegex(ValueError, 'nonnegative integer'):
            pool.check_and_export(s, p)

    def test_unknown_rep_and_wrong_bucket(self):
        for rep in ('unknown', 'rep-b'):
            with self.subTest(rep=rep):
                s, p = self.result()
                next(a for a in p['accounts'] if a['account_id'] == 'unmatched').update(status='proposed', proposed_owner_id=rep)
                with self.assertRaisesRegex(ValueError, 'rep'):
                    pool.check_and_export(s, p)

    def test_owner_bucket_reason_not_changed_or_lost(self):
        for field, value in (('current_owner_id', 'wrong'), ('bucket', 'wrong'), ('reason', '')):
            with self.subTest(field=field):
                s, p = self.result()
                p['accounts'][0][field] = value
                with self.assertRaises(ValueError):
                    pool.check_and_export(s, p)

    def test_population_and_rep_accounting(self):
        for field in ('accounts', 'books'):
            with self.subTest(field=field):
                s, p = self.result()
                p[field].pop()
                with self.assertRaises(ValueError):
                    pool.check_and_export(s, p)

    def test_proposal_context(self):
        s, p = self.result()
        p['rules_version'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'context mismatch'):
            pool.check_and_export(s, p)

    def test_export_handler_emits_nothing_on_failure(self):
        s, p = self.result()
        p['books'][0]['capacity'] = 999
        class C:
            def get_input(self, key):
                return json.dumps(s if key == 'snapshot_json' else p)
        with self.assertRaises(ValueError):
            pool.export_handler(C())

    def test_csv_readback_and_failure_before_overwrite(self):
        s, p = self.result()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d/'s.json').write_text(json.dumps(s)); (d/'p.json').write_text(json.dumps(p))
            cmd = [sys.executable, '-B', str(ROOT/'scripts/carve_pipeline.py'), str(d/'s.json'), str(d/'p.json'), str(d/'a.csv'), str(d/'b.csv')]
            result = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name, count, fields in [('a.csv', len(s['accounts']), pool.ACCOUNT_COLUMNS), ('b.csv', len(s['reps']), pool.BOOKS_COLUMNS)]:
                with (d/name).open(newline='') as f:
                    rows = list(csv.reader(f))
                self.assertEqual(rows[0], fields)
                self.assertEqual(len(rows), count + 1)
                self.assertTrue(all(len(row) == len(fields) for row in rows))
            before = (d/'a.csv').read_bytes()
            p['books'][0]['capacity'] = 999
            (d/'p.json').write_text(json.dumps(p))
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertEqual((d/'a.csv').read_bytes(), before)

    def test_builder_is_replay_only_with_unchanged_engine(self):
        rubric = json.loads((ROOT/'references/adapter-fixture.json').read_text())['rubric']
        graph = builder.graph(rubric)
        self.assertEqual(graph['trigger']['triggerType'], 'manual')
        self.assertEqual(len(graph['nodes']), 4)
        self.assertTrue(all(n['spec']['nodeType'] == 'code' for n in graph['nodes']))
        self.assertEqual(graph['nodes'][2]['spec']['code'], (ROOT/'scripts/carve_preview.py').read_text())
        for entry in graph['nodes']:
            spec = entry['spec']
            self.assertEqual(len(spec['incomingEdges']), 1)
            self.assertTrue(all(v['type'] == 'string' and v['description'] for v in spec['outputSchema'].values()))
        self.assertEqual(graph['nodes'][-1]['spec']['inputSchema']['properties']['snapshot_json']['sourcePath'], '$.snapshot_json')


if __name__ == '__main__':
    unittest.main(verbosity=2)
