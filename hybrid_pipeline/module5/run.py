import sys,json
from pathlib import Path
MOD=Path(__file__).resolve().parent;sys.path.insert(0,str(MOD.parent/'shared'))
from common import *
cs=read(TEST/'module4/proposals.json');rankings={x['concept_id']:x['candidates'] for x in read(MOD/'rankings.json')};nodes=read(MOD/'candidate_nodes.json');llm=LocalLLM('module5');pending={c['id']:c for c in cs if c['rule']['wbs']};traces=[];accepted={};chunk_size=4
# True LOREx order: rank/chunk -> semantic filter -> retrieve -> verify; WBS hard guard after proposal.
for offset in range(0,len(nodes),chunk_size):
 if not pending:break
 ids=list(pending);chunks={cid:rankings[cid][offset:offset+chunk_size] for cid in ids}
 prompts=[]
 for cid in ids:
  c=pending[cid];prompts.append('Semantic filter. Keep candidate parent COST CLASSES that could directly contain this tile cost concept as a subclass. Exclude unrelated RC trades. Material supply and installation are different. WBS is a work constraint, not subclass taxonomy. Return {"keep":["exact parent id"]}. '+json.dumps({'concept':c['name'],'evidence':c['examples'][0],'rule':c['rule'],'taxoadapt':c['taxoadapt'],'candidates':[{'id':x['parent'],'label':nodes[x['parent']]['label']} for x in chunks[cid]]},ensure_ascii=False))
 filtered=llm.objects(prompts,120);retr_ids=[];retr_prompts=[];rounds={}
 for cid,o in zip(ids,filtered):
  legal={x['parent'] for x in chunks[cid]};keep=[p for p in o.get('data',{}).get('keep',[]) if p in legal];t={'concept_id':cid,'offset':offset,'chunk':[x['parent'] for x in chunks[cid]],'filter':o,'kept':keep};rounds[cid]=t
  if keep:
   c=pending[cid];retr_ids.append(cid);retr_prompts.append('Choose the most specific valid direct parent for this tile cost concept. Return {"parent":"exact id or null","reason":"short"}. Only candidates provided are allowed. '+json.dumps({'concept':c['name'],'evidence':c['examples'][0],'rule':c['rule'],'candidate_lineages':{p:next(x['lineage'] for x in chunks[cid] if x['parent']==p) for p in keep}},ensure_ascii=False))
 retrieved=llm.objects(retr_prompts,150) if retr_prompts else [];ver_ids=[];ver_prompts=[]
 for cid,o in zip(retr_ids,retrieved):
  rounds[cid]['retrieval']=o;p=o.get('data',{}).get('parent')
  if p in rounds[cid]['kept']:
   c=pending[cid];rounds[cid]['proposed_parent']=p;ver_ids.append(cid);ver_prompts.append('Verify this subclass insertion independently. Is every instance of the query cost category an instance of proposed parent, with correct surface and material-vs-installation role? Return {"verified":true or false,"reason":"short"}. '+json.dumps({'query':c['name'],'evidence':c['examples'][0],'rule':c['rule'],'proposed_parent':nodes[p],'parent_id':p},ensure_ascii=False))
 verified=llm.objects(ver_prompts,120) if ver_prompts else []
 for cid,o in zip(ver_ids,verified):
  t=rounds[cid];t['verification']=o;c=pending[cid];expected=('Wall' if c['rule']['surface']=='wall' else 'Floor')+'Tile'+('Material' if c['rule']['kind']=='material' else 'Installation')+'CostItem'
  t['rule_allowed_parent']=expected;t['rule_guard_passed']=t['proposed_parent']==expected
  if o.get('data',{}).get('verified') is True and t['rule_guard_passed']:
   accepted[cid]={'concept':c,'parent':expected,'chunk_offset':offset};del pending[cid]
 traces.extend(rounds.values())
write(MOD/'reasoning_trace.json',traces);write(MOD/'accepted_insertions.json',list(accepted.values()));quarantine=[{'concept':c,'reason':'unresolved_WBS_surface' if not c['rule']['wbs'] else 'no_verified_rule_compatible_parent'} for c in cs if c['id'] not in accepted];write(MOD/'quarantine.json',quarantine)
write(MOD/'reasoning_metrics.json',{'candidate_concepts':len(cs),'accepted':len(accepted),'quarantined':len(quarantine),'chunk_size':chunk_size,'chunks_considered':len(traces),'wbs_only_baseline_eligible':sum(bool(c['rule']['wbs']) for c in cs),'independent_gold':False,'deviation':'LOREx-inspired paper reimplementation; local Qwen 3B, frozen-encoder TEMPORA-style ranker, strict WBS guard; original benchmark reproduction not claimed.'})
print('Module5 reasoning complete',len(accepted),'accepted')
