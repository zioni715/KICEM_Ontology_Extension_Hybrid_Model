import sys,json
from pathlib import Path
from types import SimpleNamespace
MOD=Path(__file__).resolve().parent
sys.path.insert(0,str(MOD.parent/'shared'));sys.path.insert(0,str(MOD/'source'))
from common import *
from taxonomy import Node
from paper import Paper
from expansion import expandNodeWidth,expandNodeDepth
import model_definitions
seed();cs=read(TEST/'module3/unmatched_concepts.json');hints={c['concept_id']:c for c in read(TEST/'module2/parent_candidates.json')};wbs=read(TEST/'shared/wbs.json')
args=SimpleNamespace(llm='local',max_density=1);root=Node(0,'tile_cost','cost','타일공사의 비용항목. Supplied WBS: '+json.dumps(wbs,ensure_ascii=False))
id2node={0:root};label2node={'tile_cost_cost':root}
for label,desc in [('material','타일 자재 공급 비용. Tile material supply; no installation labor.'),('installation','타일 붙이기 시공 비용. Tile installation labor; not tile supply.')]:
 n=Node(len(id2node),label,'cost',desc,parents=[root]);root.add_child(label,n);id2node[n.id]=n;label2node[label+'_cost']=n
for c in cs:
 ev={'rows':c['examples'],'rule':c['rule'],'taxopro_top3':hints[c['id']]['ranked_wbs'][:3]}
 root.papers[c['id']]=Paper(c['id'],c['name'],json.dumps(ev,ensure_ascii=False),['cost'])
root.classify_node(args,label2node,set())
width=expandNodeWidth(args,root,id2node,label2node)
if width:root.classify_node(args,label2node,set())
depth=[]
# Bounded experiment: one width pass, one depth pass for the two design anchors.
for key in ['material','installation']:
 node=root.children[key]
 if node.papers:
  added,ok=expandNodeDepth(args,node,id2node,label2node);depth.append({'parent':key,'added':added,'success':ok})
  if added:node.classify_node(args,label2node,set())
proposals=[]
for c in cs:
 placements=[n for n in id2node.values() if c['id'] in n.papers and n is not root]
 group=[n for n in placements if n.source in ['depth','width']]
 matches=[n for n in group if c['rule']['kind'] in [a.label for a in n.get_ancestors()]]
 c['taxoadapt']={'initial_anchor':c['rule']['kind'],'ancestor_contexts':[[a.label for a in reversed(n.get_ancestors())]+[n.label] for n in group],'accepted_group':matches[0].label if matches else None,'group_description':matches[0].description if matches else None,'rule_check':'kind-compatible ancestor context only; not factual validation','rule_wbs':c['rule']['wbs']}
 proposals.append(c)
tree=[{'id':n.id,'label':n.label,'description':n.description,'parents':[p.id for p in n.parents],'source':n.source,'concept_ids':list(n.papers)} for n in id2node.values()]
write(MOD/'taxonomy.json',tree);write(MOD/'proposals.json',proposals);write(MOD/'schema_errors.json',model_definitions._ERRORS)
write(MOD/'metrics.json',{'input_concepts':len(cs),'width_added':width,'depth':depth,'generated_groups':sum(n.source in ['depth','width'] for n in id2node.values()),'concepts_with_role_compatible_group':sum(c['taxoadapt']['accepted_group'] is not None for c in proposals),'schema_failures':len(model_definitions._ERRORS),'deviation':'Copied original Node/classify_node/expandNodeWidth/expandNodeDepth executed. Construction prompts and local deterministic Qwen backend replace research-paper prompts, Llama/OpenAI backend. One width pass and depth 2; two cost anchors are researcher design, not model discoveries.'})
print('Module4 complete')
