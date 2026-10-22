"""Synthetic adapter, graph-template and export regressions. No network calls."""
import copy
import json
from pathlib import Path
import unittest
import normalize_account as normalizer
import score_account as scoring
import export_results as exporting
import build_workflow as building

F = json.loads((Path(__file__).resolve().parent.parent/'references/adapter-fixture.json').read_text())


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.f=copy.deepcopy(F)

    def account(self):
        return normalizer.normalize(self.f['context'],self.f['company'],self.f['research'])

    def result(self):
        return scoring.score(self.f['rubric'],self.account())

    def test_full_adapter_score_export(self):
        a=self.account(); r=self.result(); row=exporting.make_row(r,a)
        self.assertEqual(r['account_fit_score'],100)
        self.assertEqual(row['motion_source'],'https://adapter.example/pricing')
        self.assertEqual(row['motion_observed_at'],'2026-01-15')
        self.assertEqual(row['customer_segment'],'b2b')
        self.assertEqual(row['selling_motion'],'hybrid')

    def test_provider_domain_not_input_echo(self):
        self.f['company']['result']['domain']='wrong.example'
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('identity',self.result()['account_fit_reason'])

    def test_missing_provider_domain(self):
        del self.f['company']['result']['domain']
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_explicit_alias(self):
        self.f['company']['result']['domain']='alias.example'
        self.f['context']['approved_domain_aliases']=['alias.example']
        self.assertEqual(self.result()['scoring_status'],'scored')

    def test_unwired_success_not_called_a_miss(self):
        del self.f['company']['success']
        self.assertEqual(self.account()['factors']['size']['status'],'failed')
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_false_success_even_with_numeric_value(self):
        self.f['company']['success']=False
        self.assertEqual(self.account()['factors']['size']['status'],'failed')

    def test_success_no_data(self):
        self.f['company']['result']['employee_count']=None
        self.assertEqual(self.account()['factors']['size']['status'],'none')

    def test_observed_zero(self):
        self.f['company']['result'].update(employee_count=0,size='')
        self.assertEqual(self.result()['scoring_status'],'scored')
        self.assertEqual(self.result()['weighted_coverage'],100)

    def test_invalid_headcounts(self):
        for value in (True,-1,2.5,'NaN','Infinity','501-1000'):
            with self.subTest(value=value):
                self.f['company']['result']['employee_count']=value
                self.assertEqual(self.result()['scoring_status'],'held')

    def test_band_is_not_a_count(self):
        self.f['company']['result']['employee_count']=None
        self.assertIsNone(self.account()['factors']['size']['value'])

    def test_conflicting_count_and_band(self):
        self.f['company']['result']['employee_count']=7211
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('conflicts',self.account()['factors']['size']['evidence'])

    def test_band_conflict_disclosed_only_if_explicit(self):
        self.f['company']['result']['employee_count']=7211
        self.f['context']['evidence_policy']['headcount_band_conflict']='ignore_with_disclosure'
        self.assertEqual(self.result()['scoring_status'],'scored')
        self.assertTrue(any('conflicts' in x for x in self.account()['warnings']))

    def test_missing_refresh(self):
        del self.f['company']['result']['last_refresh']
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_provider_refresh_is_not_observation_date(self):
        a=self.account()
        self.assertEqual(a['factors']['size']['freshness_basis'],'provider_refresh')
        self.assertIn('not an employee-count observation',a['warnings'][0])

    def test_stale_and_future_refresh(self):
        for date in ('2025-01-01','2026-01-16'):
            self.f['company']['result']['last_refresh']=date
            self.assertEqual(self.result()['scoring_status'],'held')

    def test_policy_must_be_explicit(self):
        for k in ('headcount_date_basis','headcount_band_conflict','motion_max_age_days'):
            f=copy.deepcopy(self.f)
            del f['context']['evidence_policy'][k]
            with self.assertRaises(ValueError):normalizer.normalize(f['context'],f['company'],f['research'])

    def test_no_auto_school_business_exclusion(self):
        self.f['research']['entity_type']='institution'
        r=self.result()
        self.assertEqual(r['scoring_status'],'held')
        self.assertIn('approved rubric scope',r['account_fit_reason'])
        self.f['context']['allowed_entity_types'].append('institution')
        # Inclusion still needs valid seller evidence; no hardcoded .edu filter.
        self.assertEqual(self.result()['scoring_status'],'scored')

    def test_buyer_procurement_is_not_seller_motion(self):
        self.f['research']['evidence_perspective']='buyer'
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('procurement',self.account()['factors']['motion']['evidence'])

    def test_no_source_url(self):
        self.f['research']['source_url']=''
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_wrong_company_source(self):
        self.f['research']['source_url']='https://another.example/pricing'
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_missing_date(self):
        self.f['research']['observed_at']=''
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_missing_evidence(self):
        self.f['research']['evidence']=''
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_unknown_category(self):
        self.f['research']['selling_motion']='enterprise'
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_b2b_and_selfserve_are_independent(self):
        self.f['research']['selling_motion']='self_serve'
        a=self.account()
        self.assertEqual(a['factors']['motion']['customer_segment'],'b2b')
        self.assertEqual(self.result()['account_fit_score'],90)

    def test_consumer_conflicts_with_b2b(self):
        self.f['research']['selling_motion']='consumer'
        self.assertEqual(self.result()['scoring_status'],'held')

    def test_structured_wrapper(self):
        self.f['research']={'structuredOutputs':self.f['research']}
        self.assertEqual(self.result()['account_fit_score'],100)

    def test_conflicting_wrapper(self):
        self.f['research']={'structuredOutputs':self.f['research'],'selling_motion':'consumer'}
        with self.assertRaisesRegex(ValueError,'conflicting'):self.account()

    def test_held_has_no_published_evidence(self):
        self.f['research']['source_url']=''
        r=self.result()
        self.assertIsNone(r['account_fit_score'])
        self.assertEqual(r['components'],{})
        self.assertEqual(r['evidence'],{})

    def test_review_reason_cannot_be_silently_ignored(self):
        a=self.account(); a['review_reasons']=['Source conflict needs approval']
        r=scoring.score(self.f['rubric'],a)
        self.assertEqual(r['scoring_status'],'held')
        self.assertIn('Source conflict',r['account_fit_reason'])

    def test_bad_review_reasons(self):
        a=self.account(); a['review_reasons']='string not list'
        self.assertEqual(scoring.score(self.f['rubric'],a)['scoring_status'],'held')

    def test_export_rejects_wrong_account(self):
        a=self.account(); r=self.result(); r['account_id']='wrong'
        with self.assertRaisesRegex(ValueError,'mismatch'):exporting.make_row(r,a)

    def test_export_rejects_false_held_score(self):
        a=self.account(); r=self.result(); r['scoring_status']='held'
        with self.assertRaisesRegex(ValueError,'held'):exporting.make_row(r,a)

    def test_export_does_not_scrape_reason(self):
        a=self.account(); r=self.result(); r['account_fit_reason']='No URL in reason'
        self.assertEqual(exporting.make_row(r,a)['motion_source'],a['factors']['motion']['source'])

    def test_output_envelopes(self):
        self.assertEqual(exporting.step_output({'structuredOutputs':{'x':'a'}},'x'),'a')
        self.assertEqual(exporting.step_output({'x':'a'},'x'),'a')
        with self.assertRaises(ValueError):exporting.step_output({'x':'a','structuredOutputs':{'x':'b'}},'x')
        with self.assertRaises(ValueError):exporting.step_output({},'x')

    def test_flat_handler(self):
        f=self.f
        class C:
            def get_input(self,k):return {'context_json':json.dumps(f['context']),'company_json':json.dumps(f['company']),'research_json':json.dumps(f['research'])}[k]
        o=normalizer.handler(C())
        self.assertTrue(all(isinstance(v,str) for v in o.values()))
        self.assertEqual(o['review_status'],'ready')

    def test_no_input_mutation(self):
        before=copy.deepcopy(self.f); self.account(); self.assertEqual(before,self.f)

    def test_builder_single_trigger_edge_and_flat_outputs(self):
        for mode in ('replay','research'):
            plan=building.graph(self.f['rubric'],mode)
            self.assertEqual(sum(e['sourceNode']=='@trigger' for n in plan['nodes'] for e in n['spec']['incomingEdges']),1)
            for n in plan['nodes']:
                self.assertNotIn('properties',n['spec']['outputSchema'])
                self.assertTrue(all('description' in v for v in n['spec']['outputSchema'].values()))
            normal=next(n['spec'] for n in plan['nodes'] if n['label']=='normalize')
            self.assertEqual(set(normal['inputSchema']['required']),{'context_json','company_json','research_json'})

    def test_research_preflight_derives_one_identity(self):
        c=self.f['context']; company=self.f['company']
        p=normalizer.research_inputs(c,company)
        self.assertEqual(p['domain'],c['domain'])
        self.assertEqual(p['name'],company['result']['name'])
        plan=building.graph(self.f['rubric'],'research')
        research=next(n['spec'] for n in plan['nodes'] if n['label']=='research')
        self.assertEqual(research['incomingEdges'],[{'sourceNode':'@preflight'}])
        self.assertEqual(research['inputSchema']['properties']['domain']['sourceNodeId'],'@preflight')

    def test_research_preflight_stops_mismatch_and_failure(self):
        for change in ('mismatch','failure','missing_date','missing_id'):
            f=copy.deepcopy(self.f)
            if change=='mismatch':f['company']['result']['domain']='wrong.example'
            if change=='failure':f['company']['success']=False
            if change=='missing_date':f['context'].pop('score_as_of')
            if change=='missing_id':f['context']['account_id']=''
            with self.subTest(change=change),self.assertRaises(ValueError):
                normalizer.research_inputs(f['context'],f['company'])

    def test_legacy_seller_phrase_is_exact_alias(self):
        self.f['research']['evidence_perspective']='seller only'
        a=self.account()
        self.assertEqual(a['factors']['motion']['status'],'found')
        self.assertEqual(a['factors']['motion']['evidence_perspective_raw'],'seller only')
        self.assertTrue(any('formatting alias' in x for x in a['warnings']))
        for value in ('not seller','buyer and seller','seller perhaps'):
            self.f['research']['evidence_perspective']=value
            self.assertEqual(self.result()['scoring_status'],'held')

    def test_mixed_without_consumer_sales_is_held(self):
        self.f['research']['customer_segment']='mixed'
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('Consumer sales',self.account()['factors']['motion']['evidence'])

    def test_consumer_sales_need_separate_evidence(self):
        self.f['research'].update(customer_segment='b2c',selling_motion='consumer',business_sales_evidence='')
        self.assertEqual(self.result()['scoring_status'],'held')
        self.f['research']['consumer_sales_evidence']='Fictional retail store sells running shoes directly to consumers.'
        self.assertEqual(self.result()['scoring_status'],'scored')

    def test_builder_selects_exact_tokens(self):
        plan=building.graph(self.f['rubric'],'research')
        spec=next(n['spec'] for n in plan['nodes'] if n['label']=='research')
        for k in ('entity_type','customer_segment','selling_motion','evidence_perspective'):
            self.assertEqual(spec['outputSchema'][k]['type'],'select')
        options=json.loads(spec['outputSchema']['evidence_perspective']['options'])
        self.assertEqual(options,[{'text':'seller'},{'text':'unknown'}])
        self.assertIn('consumer_sales_evidence',spec['outputSchema'])

    def test_export_names_rejected_attempt_evidence(self):
        self.f['company']['result']['employee_count']=7211
        row=exporting.make_row(self.result(),self.account())
        self.assertEqual(row['size_status'],'failed')
        self.assertIn('conflicts',row['headcount_issue'])
        self.assertIsNone(row['score'])

    def test_unreadable_business_route_blocks_consumer(self):
        self.f['research'].update(customer_segment='b2c',selling_motion='consumer',
            business_sales_evidence='',consumer_sales_evidence='Fictional direct shoe checkout.',
            unresolved_sales_routes='Official wholesale terms were found but could not be inspected.')
        a=self.account();r=self.result()
        self.assertEqual(r['scoring_status'],'held')
        self.assertIn('unresolved',a['factors']['motion']['evidence'])
        self.assertIn('wholesale',exporting.make_row(r,a)['unresolved_sales_routes'])

    def test_confirmed_business_sales_block_consumer_only(self):
        self.f['research'].update(customer_segment='b2c',selling_motion='consumer',
            consumer_sales_evidence='Fictional retail checkout.',
            business_sales_evidence='Fictional reseller purchase orders are accepted by sales representatives.')
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('business sales',self.account()['factors']['motion']['evidence'])

    def test_mixed_needs_both_sales_evidence(self):
        self.f['research'].update(customer_segment='mixed',consumer_sales_evidence='Fictional retail checkout.',business_sales_evidence='')
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('business-sales evidence',self.account()['factors']['motion']['evidence'])

    def test_retail_and_wholesale_can_be_hybrid(self):
        self.f['research'].update(customer_segment='mixed',selling_motion='hybrid',
            consumer_sales_evidence='Fictional direct retail checkout.',
            business_sales_evidence='Fictional wholesale purchase orders confirmed by a sales representative.',
            source_urls_json=json.dumps(['https://adapter.example/pricing','https://adapter.example/wholesale']))
        a=self.account();r=self.result();row=exporting.make_row(r,a)
        self.assertEqual(r['scoring_status'],'scored')
        # Demo hybrid points are unchanged. This is not an approved B2B-only ICP.
        self.assertEqual(r['account_fit_score'],100)
        self.assertEqual(json.loads(row['motion_sources_json']),['https://adapter.example/pricing','https://adapter.example/wholesale'])
        self.assertIn('wholesale',row['business_sales_evidence'])

    def test_supporting_sources_are_official(self):
        self.f['research']['source_urls_json']=json.dumps(['https://unrelated.example/wholesale'])
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertIn('official',self.account()['factors']['motion']['evidence'])

    def test_supporting_source_list_malformed(self):
        for urls in ('not JSON','{}','[null]','[""]'):
            with self.subTest(urls=urls):
                self.f['research']['source_urls_json']=urls
                self.assertEqual(self.result()['scoring_status'],'held')
                self.assertIn('malformed',self.account()['factors']['motion']['evidence'])

    def test_supporting_source_deduplication(self):
        self.f['research']['source_urls_json']=json.dumps(['https://adapter.example/pricing']*2)
        self.assertEqual(self.account()['factors']['motion']['source_urls'],['https://adapter.example/pricing'])

    def test_saved_single_source_b2b_remains_usable(self):
        for k in ('source_urls_json','business_sales_evidence','unresolved_sales_routes'):
            self.f['research'].pop(k,None)
        self.assertEqual(self.result()['scoring_status'],'scored')
        self.assertEqual(self.account()['factors']['motion']['source_urls'],['https://adapter.example/pricing'])

    def test_builder_requests_route_checks(self):
        plan=building.graph(self.f['rubric'],'research')
        node=next(n['spec'] for n in plan['nodes'] if n['label']=='research')
        for k in ('business_sales_evidence','unresolved_sales_routes','source_urls_json'):
            self.assertIn(k,node['outputSchema'])
        self.assertIn('failed page read never proves absence',node['agentPrompt'])

    def test_csv_writer_round_trip(self):
        import csv,subprocess,sys,tempfile
        row=exporting.make_row(self.result(),self.account())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'rows.json').write_text(json.dumps([row]))
            subprocess.run([sys.executable,'-B',str(Path(exporting.__file__).resolve()),str(path/'rows.json'),str(path/'results.csv')],check=True,capture_output=True,text=True)
            with (path/'results.csv').open(newline='') as f:parsed=list(csv.reader(f))
            self.assertEqual(len(parsed),2)
            self.assertTrue(all(len(r)==len(exporting.COLUMNS) for r in parsed))
            with (path/'results.csv').open(newline='') as f:values=list(csv.DictReader(f))
            self.assertEqual(json.loads(values[0]['motion_sources_json']),['https://adapter.example/pricing'])

    def test_uninterpretable_review_note_is_not_cleared(self):
        self.f['research']['unresolved_sales_routes']='analysis'
        self.assertEqual(self.result()['scoring_status'],'held')
        self.assertEqual(self.account()['factors']['motion']['unresolved_sales_routes'],'analysis')
        self.assertIn('analysis',self.account()['factors']['motion']['evidence'])

    def test_builder_does_not_implement_all_rubrics(self):
        old=json.loads((Path(__file__).resolve().parent.parent/'references/test-fixtures.json').read_text())['rubric']
        with self.assertRaisesRegex(ValueError,'seller-motion'):building.graph(old)


if __name__=='__main__':unittest.main(verbosity=2)
