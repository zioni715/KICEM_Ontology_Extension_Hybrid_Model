"""Paper-based TEMPORA-style ranker: Euler lineage, dual paths, dynamic margin."""
import sys,random,re
from pathlib import Path
MOD=Path(__file__).resolve().parent;sys.path.insert(0,str(MOD.parent/'shared'))
from common import *
import torch
from transformers import AutoTokenizer,AutoModel
seed();classes=read(TEST/'shared/seed_classes.json');cs=read(TEST/'module4/proposals.json');nodes={}
for c in classes:
 if c['id']=='CostItem' or c['id'].endswith('CostItem'):
  nodes[c['id']]={'label':c['id']+' '+' '.join(c['labels']),'parent':next((p for p in c['parents'] if p=='CostItem' or p.endswith('CostItem')),None),'origin':'OWL2 seed'}
anchors=[('TileCostItem','타일 비용항목','CostItem'),('TileMaterialCostItem','타일 자재 공급 비용항목','TileCostItem'),('TileInstallationCostItem','타일 붙이기 시공 비용항목','TileCostItem'),('WallTileMaterialCostItem','벽 타일 자재 공급 비용항목','TileMaterialCostItem'),('FloorTileMaterialCostItem','바닥 타일 자재 공급 비용항목','TileMaterialCostItem'),('WallTileInstallationCostItem','벽 타일 붙이기 시공 비용항목','TileInstallationCostItem'),('FloorTileInstallationCostItem','바닥 타일 붙이기 시공 비용항목','TileInstallationCostItem')]
for key,label,parent in anchors:nodes[key]={'label':label,'parent':parent,'origin':'researcher cost-schema bridge from WBS surface and row role, not generated discovery'}
def lineage(anchor,hide=None):
 chain=[anchor]
 while nodes[chain[-1]]['parent']:chain.append(nodes[chain[-1]]['parent'])
 steps=[];seen=set(chain)
 for a,b in zip(chain,chain[1:]):steps.append(nodes[a]['label']+' is child of '+nodes[b]['label'])
 for a,b in zip(chain[::-1],chain[-2::-1]):steps.append(nodes[a]['label']+' is parent of '+nodes[b]['label'])
 parent=nodes[anchor]['parent']
 for n,v in nodes.items():
  if n!=hide and n!=anchor and parent and v['parent']==parent:
   steps.extend([nodes[anchor]['label']+' is child of '+nodes[parent]['label'],nodes[parent]['label']+' is parent of '+v['label'],v['label']+' is child of '+nodes[parent]['label'],nodes[parent]['label']+' is parent of '+nodes[anchor]['label']]);seen.add(n)
 for n,v in nodes.items():
  if n!=hide and v['parent']==anchor:steps.extend([nodes[anchor]['label']+' is parent of '+v['label'],v['label']+' is child of '+nodes[anchor]['label']]);seen.add(n)
 return '; '.join(steps) or nodes[anchor]['label'],seen
# Hide query from each local neighborhood to avoid explicitly revealing its training edge.
examples=[]
for q,v in nodes.items():
 p=v['parent']
 if not p:continue
 negs=[n for n in nodes if n not in [q,p] and nodes[n]['parent']!=q]
 for n in random.sample(negs,min(2,len(negs))):
  pos,ps=lineage(p,q);neg,ns=lineage(n,q);margin=(len(ps|ns)/max(1,len(ps&ns))-1)*.05
  examples.append({'query':q,'positive':p,'negative':n,'texts':[v['label']+' [SEP] '+pos,pos,v['label']+' [SEP] '+neg,neg],'margin':margin})
tok=AutoTokenizer.from_pretrained(model_path('bert'),local_files_only=True);encoder=AutoModel.from_pretrained(model_path('bert'),local_files_only=True,add_pooling_layer=False).cuda();head=torch.nn.Sequential(torch.nn.Linear(768,128),torch.nn.Tanh(),torch.nn.Linear(128,1)).cuda()
# Frozen encoder + trainable MLP is a documented small-data feasibility deviation.
encoder.eval()
for p in encoder.parameters():p.requires_grad=False
def features(texts):
 result=[]
 with torch.inference_mode():
  for st in range(0,len(texts),8):
   inp=tok(texts[st:st+8],padding=True,truncation=True,max_length=384,return_tensors='pt').to('cuda');result.append(encoder(**inp).last_hidden_state[:,0].clone())
 return torch.cat(result).detach().clone()
f=features([t for e in examples for t in e['texts']]).reshape(len(examples),4,768);margins=torch.tensor([e['margin'] for e in examples],device='cuda');opt=torch.optim.AdamW(head.parameters(),lr=1e-3);losses=[]
for epoch in range(60):
 opt.zero_grad();s=head(f).squeeze(-1);a=(s[:,2]-s[:,0]+margins).relu().mean();b=(s[:,0]-s[:,1]).square().mean();c=(s[:,2]-s[:,3]).relu().mean();loss=a+.1*b+.1*c;loss.backward();opt.step();losses.append({'epoch':epoch+1,'total':loss.item(),'margin_loss':a.item(),'positive_dual':b.item(),'negative_dual':c.item()})
head.eval();ranking=[]
for c in cs:
 texts=[c['name']+' '+json.dumps(c['examples'][0],ensure_ascii=False)+' [SEP] '+lineage(p)[0] for p in nodes]
 with torch.no_grad():vals=head(features(texts)).squeeze(-1).cpu().tolist()
 ranking.append({'concept_id':c['id'],'candidates':sorted([{'parent':p,'score':s,'lineage':lineage(p)[0]} for p,s in zip(nodes,vals)],key=lambda x:-x['score'])})
torch.save(head.state_dict(),MOD/'tempora_mlp.pt');write(MOD/'ranker_training.json',{'seed':42,'epochs':60,'lr':1e-3,'lambda1':.1,'lambda2':.1,'margin_d':.05,'max_length':384,'frozen_encoder':True,'supervision':'self-supervised existing OWL2 edges plus explicit researcher bridge edges; no gold tile labels','examples':examples,'losses':losses,'deviation':'Paper-inspired TEMPORA with frozen multilingual BERT CLS encoder, trained MLP; original encoder fine-tuning and benchmark schedule not reproduced.'});write(MOD/'candidate_nodes.json',nodes);write(MOD/'rankings.json',ranking)
print('Module5 ranking complete')
