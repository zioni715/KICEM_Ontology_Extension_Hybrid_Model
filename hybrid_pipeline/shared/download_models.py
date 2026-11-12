from huggingface_hub import HfApi,snapshot_download
from pathlib import Path
import json,time
root=Path(__file__).resolve().parents[1]/'runtime'
lock=json.loads((root/'models.lock.json').read_text()) if (root/'models.lock.json').exists() else {}
for key,repo in [('llm','Qwen/Qwen2.5-3B-Instruct'),('embedding','intfloat/multilingual-e5-small'),('bert','google-bert/bert-base-multilingual-cased')]:
 info=HfApi().model_info(repo,revision=lock.get(key,{}).get('revision'))
 print(key,info.sha,flush=True)
 path=snapshot_download(repo,revision=info.sha,local_dir=str(root/'models'/key),allow_patterns=['*.json','*.safetensors','tokenizer*','vocab.txt','merges.txt','*.model','1_Pooling/*','README.md'],max_workers=3)
 lock[key]={'repo':repo,'revision':info.sha,'path':str(Path(path).resolve()),'license':getattr(info.card_data,'license',None)}
 (root/'models.lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2))
 print('DONE',key,flush=True)
