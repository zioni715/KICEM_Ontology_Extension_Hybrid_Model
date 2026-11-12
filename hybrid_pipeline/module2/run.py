import sys,random
from pathlib import Path
MOD=Path(__file__).resolve().parent
sys.path.insert(0,str(MOD.parent/'shared'));sys.path.insert(0,str(MOD/'source/TaxoPro'))
from common import *
import torch
from transformers import AutoTokenizer,BertModel
from peft import MultitaskLoraConfig,PeftModelForBasic
seed();tok=AutoTokenizer.from_pretrained(model_path('bert'),local_files_only=True)
base=BertModel.from_pretrained(model_path('bert'),local_files_only=True,add_pooling_layer=False)
model=PeftModelForBasic(base,MultitaskLoraConfig(r=4,lora_alpha=8,target_modules=['query','value'],num_tasks=2,num_ranks=4,lora_dropout=0.05)).cuda()
head=torch.nn.Linear(768,1).cuda()
classes=read(TEST/'shared/seed_classes.json');wbs=read(TEST/'shared/wbs.json');cs=read(TEST/'module1/extracted_concepts.json')
source_labels={c['id']:c['id']+' '+ ' '.join(c['labels']) for c in classes};target_labels={c['code']:c['label'] for c in wbs}
source_edges=[(c['id'],p) for c in classes for p in c['parents'] if p in source_labels];target_edges=[(c['code'],c['parent']) for c in wbs if c['parent']]
logs=[];datasets=[]
def textpair(q,p,relation):return f'Relation: {relation}. Query: {q}. Proposed direct parent: {p}.'
def scores(texts):
 inp=tok(texts,padding=True,truncation=True,max_length=128,return_tensors='pt').to('cuda');return head(model(**inp).last_hidden_state[:,0]).squeeze(-1)
for task,edges,labels,rel in [(0,source_edges,source_labels,'OWL subclass'),(1,target_edges,target_labels,'WBS subwork category')]:
 model.set_task_id(task)
 for n,p in model.named_parameters():p.requires_grad=('lora_' in n and (task==0 or ('.lora_A_multitask.default.1.' in n or '.lora_B_multitask.default.1.' in n)))
 trainable=sum(p.numel() for p in model.parameters() if p.requires_grad)
 params=[p for p in model.parameters() if p.requires_grad]+list(head.parameters());opt=torch.optim.AdamW(params,lr=2e-4)
 pairs=[]
 for q,p in edges:
  pairs.append((textpair(labels[q],labels[p],rel),1))
  negs=[n for n in labels if n not in [q,p]]
  for n in random.sample(negs,min(2,len(negs))):pairs.append((textpair(labels[q],labels[n],rel),0))
 datasets.append({'task':task,'relation':rel,'edges':edges,'pairs':pairs,'supervision':'seed OWL explicit edges' if task==0 else 'WBS decomposition proxy, not OWL subclass labels','trainable_encoder_parameters':trainable})
 for epoch in range(8):
  random.shuffle(pairs);model.train();head.train();losses=[]
  for st in range(0,len(pairs),8):
   batch=pairs[st:st+8];opt.zero_grad();pred=scores([p[0] for p in batch]);loss=torch.nn.functional.binary_cross_entropy_with_logits(pred,torch.tensor([p[1] for p in batch],dtype=torch.float32,device='cuda'));loss.backward();torch.nn.utils.clip_grad_norm_(params,1.0);opt.step();losses.append(loss.item())
  logs.append({'task':task,'epoch':epoch+1,'loss':sum(losses)/len(losses)});print(logs[-1],flush=True)
 state={n:p.detach().cpu() for n,p in model.state_dict().items() if 'lora_' in n}
 torch.save({'adapter':state,'head':head.state_dict(),'task':task},MOD/f'task{task}_adapter.pt')
model.eval();head.eval();results=[]
with torch.inference_mode():
 for c in cs:
  ts=[textpair(c['name']+' '+json.dumps(c['examples'][0],ensure_ascii=False),label,'WBS subwork category') for label in target_labels.values()];vals=[]
  for st in range(0,len(ts),8):vals.extend(scores(ts[st:st+8]).cpu().tolist())
  ranked=sorted([{'code':code,'label':target_labels[code],'logit':v} for code,v in zip(target_labels,vals)],key=lambda x:-x['logit'])
  results.append({'concept_id':c['id'],'ranked_wbs':ranked,'rule_wbs':c['rule']['wbs'],'rule_rank':next((i+1 for i,x in enumerate(ranked) if x['code']==c['rule']['wbs']),None)})
write(MOD/'training.json',{'seed':42,'batch':8,'lr':2e-4,'epochs_per_domain':8,'lora_rank':4,'lora_alpha':8,'losses':logs,'datasets':datasets,'peft_module':__import__('peft').__file__,'all_data_used_for_feasibility_training':True,'holdout':False})
write(MOD/'parent_candidates.json',results);write(MOD/'metrics.json',{'trained':True,'source_edges':len(source_edges),'target_proxy_edges':len(target_edges),'ranked_concepts':len(results),'rule_parent_top1_agreement':sum(r['rule_rank']==1 for r in results),'rule_parent_top5_agreement':sum(r['rule_rank'] is not None and r['rule_rank']<=5 for r in results),'not_accuracy':True,'deviation':'Uses original custom shared/domain LoRA component; small direct-parent classifier replaces full TaxoPro taxonomy-completion training; target supervision is WBS decomposition, not is-a.'})
print('Module2 complete')
