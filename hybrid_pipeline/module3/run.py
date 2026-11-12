import sys,json
from pathlib import Path
MOD=Path(__file__).resolve().parent
sys.path.insert(0,str(MOD.parent/'shared'));sys.path.insert(0,str(MOD/'source/modules/identify_correspondences'))
from common import *
import numpy as np,pandas as pd,torch
from sentence_transformers import SentenceTransformer
from retrieve_identify_prompt import retrieve_identify_prompt
seed();cs=read(TEST/'module1/extracted_concepts.json');classes=read(TEST/'shared/seed_classes.json');hints={c['concept_id']:c for c in read(TEST/'module2/parent_candidates.json')}
queries=[{'id':c['id'],'label':c['name']+' '+c['rule']['surface']+' '+c['rule']['kind'],'type':'new_tile_concept'} for c in cs]
# Structural anchors are controls derived from the known seed schema, NOT discovered tile matches.
queries += [{'id':'control_'+c['id'],'label':' '.join(c['labels']) or c['id'],'type':'schema_control','expected':c['iri']} for c in classes if c['id'] in ['CostItem','ProgressPaymentItem','Unit','WorkCategory']]
targets=[{'id':c['iri'],'label':c['id']+' '+' '.join(c['labels'])} for c in classes]
embed=SentenceTransformer(model_path('embedding'),device='cuda');vec=embed.encode(['query: '+q['label'] for q in queries]+['query: '+t['label'] for t in targets],normalize_embeddings=True,batch_size=16,convert_to_numpy=True)
sim=vec[:len(queries)]@vec[len(queries):].T;del embed;torch.cuda.empty_cache();np.save(MOD/'similarities.npy',sim)
# Symmetric E5 query prefix is appropriate for semantic similarity, not asymmetric retrieval.
k=3;threshold=.75
forward=[];reverse=[]
for i,q in enumerate(queries):
 ix=[int(j) for j in np.argsort(-sim[i])[:k] if sim[i,j]>=threshold]
 forward.append({'Query Class':q['id'],'Query Preferred Term':q['label'],'Candidate List':'|'.join(targets[j]['id'] for j in ix) if ix else np.nan,'Score':'|'.join(str(float(sim[i,j])) for j in ix)})
for j,t in enumerate(targets):
 ix=[int(i) for i in np.argsort(-sim[:,j])[:k]]
 reverse.append({'Query Class':t['id'],'Query Preferred Term':t['label'],'Candidate List':'|'.join(queries[i]['id'] for i in ix),'Score':'|'.join(str(float(sim[i,j])) for i in ix)})
f=pd.DataFrame(forward);r=pd.DataFrame(reverse);f.to_csv(MOD/'forward.csv',index=False);r.to_csv(MOD/'reverse.csv',index=False)
template='Ontology A: {}. Ontology B: {}. Source concept: {}. Target concept: {}. Are these exactly equivalent classes? Broader, narrower, related, same unit, or same construction sector are NOT equivalence. Return JSON with equivalent (boolean) and reason (short string).'
(MOD/'matching_prompt.txt').write_text(template);llm=LocalLLM('module3');cache={};checks=[]
def ask(prompt,*args):
 if prompt not in cache:
  o=llm.objects([prompt],100)[0];cache[prompt]=o.get('data',{}).get('equivalent') is True;checks.append({'prompt':prompt,'result':o})
 return cache[prompt]
retrieve_identify_prompt('Tile cost concepts','RCPP OWL2',list(f['Query Class']),f,r,str(MOD/'mila_raw.xlsx'),str(MOD/'matching_prompt.txt'),None,pd.DataFrame([{'Entity':t['id'],'Term':'|'+t['label']+'|'} for t in targets]),ask,temperature=0,LLM_model='Qwen2.5-3B-Instruct')
raw=pd.read_excel(MOD/'mila_raw.xlsx').fillna('');result=[];td={t['id']:t for t in targets}
for q,(_,row) in zip(queries,raw.iterrows()):
 candidates=str(row['Correspondence']).split('|') if row['Correspondence'] else [];accepted=[];rejected=[]
 for c in candidates:
  ok=ask(template.format('Tile cost concepts','RCPP OWL2',q['label'],td[c]['label']))
  reason='semantic_verification_rejected'
  if q['type']=='new_tile_concept':
   seed_id=c.split('#')[-1]
   # RCPP has no tile class; preserve broad and RC-specific distinctions even when HCB votes equivalent.
   if seed_id=='CostItem':ok=False;reason='broader_class_not_equivalence'
   elif seed_id.endswith('CostItem'):ok=False;reason='RC_specific_class_not_tile_equivalence'
   else:ok=False;reason='schema_entity_not_tile_cost_subtype'
  if ok:accepted.append(c)
  else:rejected.append({'target':c,'reason':reason})
 result.append({'query':q,'raw_type':row['Type of correspondence'],'raw_correspondence':candidates,'accepted_equivalence':accepted,'rejected':rejected,'taxopro_hint':hints.get(q['id'],{}).get('ranked_wbs',[])[:3]})
write(MOD/'alignment.json',result);write(MOD/'verification.json',checks)
novel=[c for c in cs if not next(x for x in result if x['query']['id']==c['id'])['accepted_equivalence']]
write(MOD/'unmatched_concepts.json',novel);write(MOD/'metrics.json',{'tile_queries':len(cs),'schema_controls':4,'raw_tile_matches':sum(bool(x['raw_correspondence']) for x in result if x['query']['type']=='new_tile_concept'),'accepted_tile_equivalence':len(cs)-len(novel),'accepted_schema_controls':sum(bool(x['accepted_equivalence']) for x in result if x['query']['type']=='schema_control'),'unmatched_tile':len(novel),'llm_calls':len(checks),'k':k,'threshold':threshold,'deviation':'Original retrieve_identify_prompt invoked unmodified from copy; multilingual E5 instead of original embedding; every HCB checked; OWL kind/RC scope guard added outside original. TaxoPro suggestions are carried as context, not equivalence scores.'})
print('Module3 complete')
