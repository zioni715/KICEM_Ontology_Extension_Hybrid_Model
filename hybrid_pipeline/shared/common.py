from pathlib import Path
import json,hashlib,random,os,time
ROOT=Path(__file__).resolve().parents[2]; TEST=ROOT/'hybrid_pipeline'
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def seed():
 import numpy as np,torch
 random.seed(42);np.random.seed(42);torch.manual_seed(42);torch.cuda.manual_seed_all(42);torch.set_num_threads(4)
def model_path(key):return read(TEST/'runtime/models.lock.json')[key]['path']
def json_extract(s):
 import re
 s=re.sub(r'^```(?:json)?\s*|\s*```$','',s.strip())
 start=s.find('{');end=s.rfind('}')
 if start<0 or end<start:raise ValueError('No JSON object')
 return json.loads(s[start:end+1])
class LocalLLM:
 def __init__(self,module):
  import torch
  from transformers import AutoTokenizer,AutoModelForCausalLM
  seed();self.log=TEST/module/'llm_calls.jsonl';self.tokenizer=AutoTokenizer.from_pretrained(model_path('llm'),local_files_only=True,padding_side='left')
  self.model=AutoModelForCausalLM.from_pretrained(model_path('llm'),local_files_only=True,torch_dtype=torch.bfloat16,device_map={'':'cuda:0'},attn_implementation='sdpa').eval()
 def generate(self,prompts,max_tokens=192,batch=4):
  import torch
  outputs=[]
  for st in range(0,len(prompts),batch):
   ps=prompts[st:st+batch]
   formatted=[self.tokenizer.apply_chat_template(p if isinstance(p,list) else [{'role':'system','content':'You are a careful ontology engineer. Ground every claim in the supplied evidence. Return ONLY the requested JSON object. Never invent quantities, materials or methods.'},{'role':'user','content':p}],tokenize=False,add_generation_prompt=True) for p in ps]
   inp=self.tokenizer(formatted,padding=True,truncation=True,max_length=4096,return_tensors='pt').to('cuda')
   t=time.time()
   with torch.inference_mode():out=self.model.generate(**inp,max_new_tokens=max_tokens,do_sample=False,temperature=None,top_p=None,top_k=None,pad_token_id=self.tokenizer.pad_token_id)
   texts=self.tokenizer.batch_decode(out[:,inp.input_ids.shape[1]:],skip_special_tokens=True)
   with self.log.open('a') as f:
    for p,r in zip(ps,texts):f.write(json.dumps({'prompt':p,'response':r,'max_new_tokens':max_tokens,'do_sample':False,'batch_seconds':time.time()-t},ensure_ascii=False)+'\n')
   outputs.extend(texts);print('LLM',self.log.parent.name,st+len(ps),'/',len(prompts),flush=True)
  return outputs
 def objects(self,prompts,max_tokens=192,batch=4):
  outs=self.generate(prompts,max_tokens,batch);res=[]
  for s in outs:
   try:res.append({'valid':True,'data':json_extract(s),'raw':s})
   except Exception as e:res.append({'valid':False,'error':str(e),'raw':s})
  return res
