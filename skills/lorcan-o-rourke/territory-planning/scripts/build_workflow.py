"""Render a bounded reference graph, or explicitly create its unpublished draft.

Default: render JSON only. --create needs --receipt and creates no runs, fields,
Audience records, schedules, CRM writes or publication. mode=replay reuses supplied
research; mode=research adds a new Claygent using the shipped prompt. Company
snapshots are supplied evidence in both modes. Fresh company actions and additional
rubric factors need the evidence-plan procedure, not silent changes to this builder.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
import score_account

ROOT = Path(__file__).resolve().parent.parent


def pin(node, path, kind='string'):
    return {'type': kind, 'sourceNodeId': '@' + node, 'sourcePath': path}


def field(description):
    return {'type': 'string', 'description': description}


def select_field(description, values):
    return {'type':'select','description':description,
            'options':json.dumps([{'text':v} for v in values])}


def graph(rubric, mode='replay', model='gpt-5.4-nano'):
    score_account.validate_rubric(rubric)
    active = {f['id'] for f in rubric['factors'] if f['weight'] > 0}
    if active != {'size', 'motion'}:
        raise ValueError('Reference adapter supports size and motion only; build reviewed adapters for other factors.')
    if not set(rubric['factors'][next(i for i,f in enumerate(rubric['factors']) if f['id']=='motion')].get('map', {})).issuperset({'sales_led','self_serve','hybrid','consumer'}):
        raise ValueError('Reference adapter requires the explicit seller-motion rubric; do not reuse synthetic-1 categories.')
    if mode not in ('replay','research'):
        raise ValueError('Unsupported mode')
    props = {'context_json': field('Stable identity, score date and explicit evidence policy as JSON'),
             'company_json': field('Previously captured company action envelope as JSON'),
             'research_json': field('Previously captured motion observation as JSON')}
    required = ['context_json','company_json'] + (['research_json'] if mode=='replay' else [])
    trigger = {'triggerType':'manual','inputSchema':{'type':'object','properties':props,'required':required}}
    nodes = []
    previous = 'trigger'
    if mode == 'research':
        preflight_code = (ROOT/'scripts/normalize_account.py').read_text() + '\ndef handler(context):\n    return research_inputs(context.get_input("context_json"), context.get_input("company_json"))\n'
        nodes.append({'label':'preflight','spec':{
            'name':'Check identity before research', 'nodeType':'code', 'code':preflight_code,
            'inputSchema':{'type':'object','properties':{k:pin('trigger','$.'+k) for k in ('context_json','company_json')},'required':['context_json','company_json']},
            'outputSchema':{k:field('Verified '+k+' from the context and supplied company snapshot') for k in ('name','domain','score_as_of')},
            'incomingEdges':[{'sourceNode':'@trigger'}]}})
        source = (ROOT/'references/motion-research.md').read_text()
        prompt = source.split('```text\n',1)[1].split('\n```',1)[0]
        nodes.append({'label':'research','spec':{
            'name':'Seller motion research', 'nodeType':'agent',
            'agentName':'Account seller-motion evidence', 'agentPrompt':prompt,
            'agentModel':model, 'agentInternetSearchEnabled':True,
            'inputSchema':{'type':'object','properties':{k:pin('preflight','$.'+k) for k in ('name','domain','score_as_of')}},
            'outputSchema':dict({k:select_field(d, values) for k,d,values in (
                ('entity_type','Classify entity scope',('operating_company','institution','unknown')),
                ('customer_segment','Who buys; free personal usage is not consumer sales',('b2b','b2c','mixed','unknown')),
                ('selling_motion','How the target sells its own offering',('sales_led','self_serve','hybrid','consumer','unknown')),
                ('evidence_perspective','Exact seller or unknown token',('seller','unknown'))
            )}, **{k:field(d) for k,d in {
                'evidence':'Concrete observed evidence for the separate classifications',
                'source_url':'Official target-company URL actually inspected, else empty',
                'observed_at':'Actual inspection day YYYY-MM-DD, never the scoring timestamp',
                 'consumer_sales_evidence':'Concrete consumer purchase evidence for b2c/mixed, else empty',
                'business_sales_evidence':'Concrete business purchase, wholesale, reseller or organization-sales evidence, else empty',
                'unresolved_sales_routes':'Material selling route that could not be checked; nonempty means hold',
                'source_urls_json':'JSON array of official URLs actually inspected for the classifications, or []',
                'failure_reason':'Reason for unresolved evidence, else empty'}.items()}),
            'incomingEdges':[{'sourceNode':'@preflight'}]}})
        previous = 'research'
    normalize_props = {'context_json':pin('trigger','$.context_json'),
                       'company_json':pin('trigger','$.company_json'),
                       'research_json':pin('research','$','object') if mode=='research' else pin('trigger','$.research_json')}
    nodes.append({'label':'normalize','spec':{
        'name':'Validate identity and evidence','nodeType':'code',
        'code':(ROOT/'scripts/normalize_account.py').read_text(),
        'inputSchema':{'type':'object','properties':normalize_props,'required':['context_json','company_json','research_json']},
        'outputSchema':{'account_json':field('Normalized account; conflicting inputs remain held'),
                        'raw_evidence_json':field('Separate raw company and research evidence'),
                        'review_status':field('ready or needs_review; not a completed-run status')},
        'incomingEdges':[{'sourceNode':'@'+previous}]}})
    nodes.append({'label':'config','spec':{
        'name':'Versioned rubric','nodeType':'code',
        'code':'import json\nRUBRIC = json.loads('+repr(json.dumps(rubric,sort_keys=True))+')\ndef handler(context):\n    return {"rubric_json": json.dumps(RUBRIC, sort_keys=True)}\n',
        'outputSchema':{'rubric_json':field('Fixed reviewed rubric as JSON text')},
        'incomingEdges':[{'sourceNode':'@normalize'}]}})
    nodes.append({'label':'score','spec':{
        'name':'Deterministic account score','nodeType':'code',
        'code':(ROOT/'scripts/score_account.py').read_text(),
        'inputSchema':{'type':'object','properties':{'rubric_json':pin('config','$.rubric_json'),'account_json':pin('normalize','$.account_json')},'required':['rubric_json','account_json']},
        'outputSchema':{'result_json':field('Full scoring result with nullable nested total'),
                        'scoring_status':field('scored or held'), 'rubric_version':field('Applied rubric version')},
        'incomingEdges':[{'sourceNode':'@config'}]}})
    nodes.append({'label':'export','spec':{
        'name':'Audit result with source fields','nodeType':'code',
        'code':(ROOT/'scripts/export_results.py').read_text(),
        'inputSchema':{'type':'object','properties':{'result_json':pin('score','$.result_json'),'account_json':pin('normalize','$.account_json')},'required':['result_json','account_json']},
        'outputSchema':{'row_json':field('One audit row with structured latest-attempt source fields')},
        'incomingEdges':[{'sourceNode':'@score'}]}})
    return {'scope':'unpublished, manual, run/file output only; no executions or Audience writes',
            'mode':mode,'trigger':trigger,'nodes':nodes}


def resolve(value, ids):
    if isinstance(value, dict):
        return {k:resolve(v,ids) for k,v in value.items()}
    if isinstance(value, list):
        return [resolve(v,ids) for v in value]
    if isinstance(value, str) and value.startswith('@') and value[1:] in ids:
        return ids[value[1:]]
    return value


def call(args):
    p = subprocess.run(['clay']+args, text=True, capture_output=True)
    if p.returncode:
        # Includes approval_required. Never approve, retry or change the request here.
        raise RuntimeError(p.stderr.strip() or p.stdout.strip() or 'Clay command failed')
    return json.loads(p.stdout)


def create(plan, name, receipt_path):
    if receipt_path.exists():
        raise ValueError('Receipt already exists; inspect it instead of creating duplicate resources.')
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt = {'name':name,'mode':plan['mode'],'state':'building','nodes':{},'scope':plan['scope']}
    def save():
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    try:
        # Learn installed command availability before any mutation.
        for args in (['workflows','nodes','create','--help'],['workflows','triggers','create','--help']):
            p=subprocess.run(['clay']+args,text=True,capture_output=True)
            if p.returncode: raise RuntimeError(p.stderr or p.stdout)
        workflow = call(['workflows','create','--name',name])
        receipt.update(workflow_id=workflow['id'],url=workflow.get('url')); save()
        trigger = call(['workflows','triggers','create',workflow['id'],'--input',json.dumps(plan['trigger'])])
        receipt['trigger_id']=trigger['resourceId']
        ids={}
        ids['trigger']=trigger.get('workflowNodeId')
        if not ids['trigger']:
            ids['trigger']=call(['workflows','triggers','get',trigger['resourceId']])['workflowNodeId']
        receipt['nodes']=ids; save()
        for entry in plan['nodes']:
            result=call(['workflows','nodes','create',workflow['id'],'--input',json.dumps(resolve(entry['spec'],ids))])
            ids[entry['label']]=result['nodeId']; save()
        receipt['saved_graph']=call(['workflows','graph','get',workflow['id'],'--mode','full']); save()
        receipt['validation']=call(['workflows','graph','validate',workflow['id']]); save()
        if receipt['validation'].get('valid') is not True or receipt['validation'].get('errors'):
            raise ValueError('Saved graph failed validation; inspect receipt. No runs were started.')
        receipt['state']='draft_created_not_executed'; save()
        return receipt
    except Exception as e:
        receipt['state']='incomplete_or_unconfirmed'; receipt['error']=str(e); save()
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rubric',required=True,type=Path)
    parser.add_argument('--mode',choices=['replay','research'],default='replay')
    parser.add_argument('--model',default='gpt-5.4-nano')
    parser.add_argument('--create',action='store_true')
    parser.add_argument('--name',default='Account fit evidence test')
    parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    plan=graph(json.loads(args.rubric.read_text()),args.mode,args.model)
    if args.create:
        if not args.receipt: parser.error('--create requires a private --receipt path outside the skill package')
        if args.receipt.resolve().is_relative_to(ROOT.resolve()): parser.error('Keep receipts outside the skill package')
        result=create(plan,args.name,args.receipt)
        print(json.dumps({'workflow_id':result['workflow_id'],'url':result.get('url'),'state':result['state'],'receipt':str(args.receipt)},indent=2))
    else:
        print(json.dumps(plan,indent=2))
