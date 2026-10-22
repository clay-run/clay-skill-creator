"""Offline regression suite. All accounts are fictional. No Clay/Salesforce calls."""
import copy
import json
import random
import unittest
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import score_account as scoring
import carve_preview as carving

FIXTURE = json.loads((Path(__file__).resolve().parent.parent / 'references' / 'test-fixtures.json').read_text())


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.r = copy.deepcopy(FIXTURE['rubric'])
        self.a = copy.deepcopy(FIXTURE['accounts'][0])

    def s(self):
        return scoring.score(self.r, self.a)

    def held(self, text):
        o = self.s()
        self.assertEqual(o['scoring_status'], 'held')
        self.assertIsNone(o['account_fit_score'])
        self.assertIsNone(o['account_fit_grade'])
        self.assertEqual(o['components'], {})
        self.assertEqual(o['evidence'], {})
        self.assertIn(text, o['account_fit_reason'])
        return o

    def test_five_golden_accounts(self):
        for a in FIXTURE['accounts']:
            with self.subTest(account=a['account_id']):
                o = scoring.score(self.r, a)
                self.assertEqual(o['account_fit_score'], a['expected_score'])
                self.assertEqual(o['account_fit_grade'], a['expected_grade'])

    def test_evidence_is_preserved(self):
        self.assertEqual(self.s()['evidence']['size'], self.a['factors']['size'])

    def test_no_default_entity_exclusion(self):
        self.a['entity_type'] = 'education'
        self.assertEqual(self.s()['account_fit_score'], 100)

    def test_bad_weight_total(self):
        self.r['factors'][0]['weight'] = 59.6
        with self.assertRaisesRegex(ValueError, 'sum to 100'):
            self.s()

    def test_negative_weight(self):
        self.r['factors'][0]['weight'] = -1
        self.r['factors'][1]['weight'] = 101
        with self.assertRaisesRegex(ValueError, 'weight'):
            self.s()

    def test_nan_weight(self):
        self.r['factors'][0]['weight'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            self.s()

    def test_duplicate_factor(self):
        self.r['factors'][1]['id'] = 'size'
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.s()

    def test_unknown_category(self):
        self.a['factors']['motion']['value'] = 'made_up'
        self.held('unrecognized category')

    def test_found_null(self):
        self.a['factors']['size']['value'] = None
        self.held('without a value')

    def test_found_nan_and_infinity(self):
        for v in ('NaN', 'Infinity', float('nan'), float('inf')):
            self.a['factors']['size']['value'] = v
            self.held('finite')

    def test_observed_zero_coverage(self):
        self.a['factors']['size']['value'] = 0
        o = self.s()
        self.assertEqual(o['scoring_status'], 'scored')
        self.assertEqual(o['components']['size']['points'], 0)
        self.assertEqual(o['weighted_coverage'], 100)

    def test_false_is_category(self):
        self.r['factors'][1]['map'] = {'false': 0, 'true': 100}
        self.a['factors']['motion']['value'] = False
        self.assertEqual(self.s()['components']['motion']['points'], 0)
        self.assertEqual(self.s()['weighted_coverage'], 100)

    def test_status_unwired(self):
        del self.a['factors']['size']['status']
        self.held('not wired')

    def test_source_failed(self):
        self.a['factors']['size']['status'] = 'failed'
        self.assertEqual(self.held('failed')['weighted_coverage'], 40)

    def test_none_default_hold(self):
        self.a['factors']['size']['status'] = 'none'
        self.held('no observation')

    def test_none_explicit_points_coverage(self):
        self.r['missing_policy'] = 'score_none'
        self.r['min_weighted_coverage'] = 40
        self.a['factors']['size']['status'] = 'none'
        o = self.s()
        self.assertEqual(o['account_fit_score'], 40)
        self.assertEqual(o['weighted_coverage'], 40)

    def test_none_cannot_reweight(self):
        self.r['missing_policy'] = 'score_none'
        self.r['min_weighted_coverage'] = 0
        self.a['factors']['size']['status'] = 'none'
        self.assertEqual(self.s()['account_fit_score'], 40)

    def test_minimum_coverage(self):
        self.r['missing_policy'] = 'score_none'
        self.a['factors']['size']['status'] = 'none'
        self.held('coverage threshold')

    def test_no_evidence(self):
        self.a['factors']['size']['evidence'] = ''
        self.held('source and evidence')

    def test_no_source(self):
        self.a['factors']['motion']['source'] = ''
        self.held('source and evidence')

    def test_mismatched_identity(self):
        self.a['matched_domain'] = 'another.example'
        self.held('identity')

    def test_alias_explicit(self):
        self.a['matched_domain'] = 'approved.example'
        self.a['approved_domain_aliases'] = ['approved.example']
        self.assertEqual(self.s()['scoring_status'], 'scored')

    def test_normalized_domain(self):
        self.a['matched_domain'] = 'https://www.NORTHWIND.example/about'
        self.assertEqual(self.s()['scoring_status'], 'scored')

    def test_missing_identity(self):
        self.a['identity_status'] = 'unknown'
        self.held('identity')

    def test_missing_asof(self):
        del self.a['score_as_of']
        self.held('score_as_of')

    def test_map_cap_cannot_promote(self):
        self.a['factors']['motion']['status'] = 'capped'
        self.held('incomplete')

    def test_numeric_cap_needs_proof(self):
        self.a['factors']['size']['status'] = 'capped'
        self.held('incomplete')

    def test_numeric_cap_saturated(self):
        self.r['factors'][0]['allow_saturated_count'] = True
        self.a['factors']['size']['status'] = 'capped'
        self.assertEqual(self.s()['account_fit_score'], 100)
        self.a['factors']['size']['value'] = 50
        self.held('incomplete')

    def test_nonmonotonic_cap(self):
        self.r['factors'][0].update(allow_saturated_count=True, bands=[[0,100],[50,60],[200,0]])
        self.a['factors']['size']['status'] = 'capped'
        self.held('incomplete')

    def test_retired_factor_does_not_block(self):
        self.r['factors'].append({'id':'retired','name':'Retired','weight':0,'kind':'map','map':{'x':0},'none_score':0})
        self.assertEqual(self.s()['scoring_status'], 'scored')

    def test_modifiers_unique(self):
        self.r['factors'][1]['modifiers'] = {'bonus': 10}
        self.a['factors']['motion'].update(value='mixed', flags=['bonus','bonus'])
        self.assertEqual(self.s()['components']['motion']['points'], 70)

    def test_unknown_modifier(self):
        self.a['factors']['motion']['flags'] = ['oops']
        o=self.held('unrecognized modifier')
        self.assertEqual(o['weighted_coverage'],60)

    def test_grade_boundary_not_promoted_by_rounding(self):
        self.r['factors'] = [{'id':'size','name':'Size','weight':100,'kind':'linear','from':0,'to':100,'none_score':0}]
        self.a['factors']['size']['value'] = 79.999
        o=self.s()
        self.assertEqual(o['account_fit_score'],80)
        self.assertEqual(o['account_fit_grade'],'Good Fit')
        self.a['factors']['size']['value'] = 80
        self.assertEqual(self.s()['account_fit_grade'],'Best Fit')

    def test_grade_boundaries(self):
        self.r['factors'] = [{'id':'size','name':'Size','weight':100,'kind':'linear','from':0,'to':100,'none_score':0}]
        for n,g in [(0,'Low Fit'),(49.99,'Low Fit'),(50,'Moderate Fit'),(64.99,'Moderate Fit'),(65,'Good Fit'),(79.99,'Good Fit'),(80,'Best Fit'),(100,'Best Fit')]:
            self.a['factors']['size']['value']=n
            self.assertEqual(self.s()['account_fit_grade'],g)

    def test_weight_only_rescore(self):
        a=FIXTURE['accounts'][1]
        self.assertEqual(scoring.score(self.r,a)['account_fit_score'],76)
        self.r['version']='synthetic-2'
        self.r['factors'][0]['weight']=40
        self.r['factors'][1]['weight']=60
        o=scoring.score(self.r,a)
        self.assertEqual(o['account_fit_score'],84)
        self.assertEqual(o['rubric_version'],'synthetic-2')

    def test_linear_zero_range(self):
        self.r['factors'][0].update(kind='linear', **{'from':1,'to':1})
        with self.assertRaisesRegex(ValueError,'to must exceed'):
            self.s()

    def test_points_out_of_range(self):
        self.r['factors'][1]['map']['enterprise']=101
        with self.assertRaisesRegex(ValueError,'0..100'):
            self.s()

    def test_flat_handler_contract(self):
        class C:
            def __init__(self,r,a): self.x={'rubric_json':json.dumps(r),'account_json':json.dumps(a)}
            def get_input(self,k): return self.x[k]
        o=scoring.handler(C(self.r,self.a))
        self.assertTrue(all(isinstance(v,str) and v for v in o.values()))
        self.assertEqual(json.loads(o['result_json'])['account_fit_score'],100)
        self.a['factors']['size']['status']='failed'
        o=scoring.handler(C(self.r,self.a))
        self.assertIsNone(json.loads(o['result_json'])['account_fit_score'])


class CarveTests(unittest.TestCase):
    def setUp(self):
        self.x={'snapshot_id':'synthetic-snapshot','rules_version':'synthetic-1','grain':'entity','method':'snake',
                'reps':[{'rep_id':r,'capacity':3,'existing_load_outside_snapshot':0,'buckets':['a','b']} for r in ('r1','r2')],
                'accounts':[{'account_id':'a'+str(i),'eligible':True,'protected':False,'excluded':False,
                             'current_owner_id':'','bucket':'a','scoring_status':'scored','account_fit_score':90-i} for i in range(6)]}

    def c(self): return carving.carve(self.x)

    def test_balance_and_every_account(self):
        o=self.c()
        self.assertEqual(len(o['accounts']),6)
        self.assertEqual([b['proposed'] for b in o['books']],[3,3])

    def test_stable_order(self):
        want=self.c()
        random.Random(42).shuffle(self.x['accounts'])
        self.x['reps'].reverse()
        self.assertEqual(self.c(),want)

    def test_overflow(self):
        for r in self.x['reps']: r['capacity']=1
        o=self.c()
        self.assertEqual(sum(a['status']=='proposed' for a in o['accounts']),2)
        self.assertEqual(sum(a['status']=='unowned' for a in o['accounts']),4)

    def test_shared_ledger_across_buckets(self):
        for a in self.x['accounts'][3:]: a['bucket']='b'
        for r in self.x['reps']: r['capacity']=2
        self.assertEqual(sum(b['proposed'] for b in self.c()['books']),4)

    def test_existing_owner_protection_capacity(self):
        self.x['accounts'][0].update(protected=True,current_owner_id='r1')
        o=self.c()
        self.assertEqual(o['accounts'][0]['status'],'protected')
        self.assertEqual(o['accounts'][0]['proposed_owner_id'],'')
        self.assertEqual(next(b for b in o['books'] if b['rep_id']=='r1')['proposed'],2)

    def test_existing_owner_requires_explicit_protection(self):
        self.x['accounts'][0]['current_owner_id']='r1'
        with self.assertRaisesRegex(ValueError,'explicitly protected'): self.c()

    def test_excluded_and_held(self):
        self.x['accounts'][0]['excluded']=True
        self.x['accounts'][1]['scoring_status']='held'
        o=self.c()
        self.assertEqual(o['accounts'][0]['status'],'excluded')
        self.assertEqual(o['accounts'][1]['status'],'not_eligible')

    def test_zero_capacity(self):
        for r in self.x['reps']: r['capacity']=0
        self.assertTrue(all(a['status']=='unowned' for a in self.c()['accounts']))

    def test_unknown_protection(self):
        del self.x['accounts'][0]['protected']
        with self.assertRaisesRegex(ValueError,'boolean'): self.c()

    def test_duplicate_id(self):
        self.x['accounts'].append(copy.deepcopy(self.x['accounts'][0]))
        with self.assertRaisesRegex(ValueError,'unique account_id'): self.c()

    def test_requested_rep_capacity(self):
        self.x['reps'][0]['capacity']=0
        self.x['accounts'][0]['requested_rep_id']='r1'
        self.assertEqual(self.c()['accounts'][0]['status'],'unowned')

    def test_missing_bucket(self):
        self.x['accounts'][0]['bucket']=''
        self.assertEqual(self.c()['accounts'][0]['status'],'unowned')

    def test_unsupported_family(self):
        self.x['grain']='family'
        with self.assertRaisesRegex(ValueError,'entity-level'): self.c()

    def test_unsupported_method(self):
        self.x['method']='dynamic'
        with self.assertRaisesRegex(ValueError,'only snake'): self.c()

    def test_round_robin(self):
        self.x['method']='round_robin'
        self.assertEqual([a['proposed_owner_id'] for a in self.c()['accounts']],['r1','r2','r1','r2','r1','r2'])

    def test_existing_excess_reported(self):
        self.x['reps'][0].update(existing_load_outside_snapshot=5,capacity=3)
        b=self.c()['books'][0]
        self.assertEqual(b['over_capacity'],2)
        self.assertEqual(b['proposed'],0)

    def test_no_input_mutation(self):
        before=copy.deepcopy(self.x)
        self.c()
        self.assertEqual(before,self.x)


from test_evidence import EvidenceTests
from test_carve_pipeline import CarvePipelineTests


if __name__ == '__main__':
    unittest.main(verbosity=2)
