from pathlib import Path
import hashlib,json,subprocess,shutil,os
ROOT=Path(__file__).resolve().parents[2]
T=ROOT/'hybrid_pipeline'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
manifest={}
for folder in ['KO','TaxoPro','MILA','taxoadapt','Papers','documents/Documents_2']:
 for p in sorted((ROOT/folder).rglob('*')):
  if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts:manifest[str(p.relative_to(ROOT))]=sha(p)
for p in ROOT.glob('*타일*.md'):manifest[p.name]=sha(p)
p=T/'reports'/'original_sha256.json'
if not p.exists():p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
else:
 old=json.loads(p.read_text());assert all(manifest.get(k)==v for k,v in old.items()),'Original changed'
for src,dst in [('TaxoPro','module2'),('MILA','module3'),('taxoadapt','module4')]:
 target=T/dst/'source'
 if not target.exists():shutil.copytree(ROOT/src,target,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'))
versions={'python':subprocess.check_output([os.sys.executable,'--version'],text=True).strip(),'pip_freeze':subprocess.check_output([os.sys.executable,'-m','pip','freeze'],text=True).splitlines(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],text=True).strip(),'sources':{}}
for folder in ['TaxoPro','MILA','taxoadapt']:
 versions['sources'][folder]=subprocess.check_output(['git','-C',str(ROOT/folder),'rev-parse','HEAD'],text=True).strip()
(T/'reports'/'environment.json').write_text(json.dumps(versions,ensure_ascii=False,indent=2))
print('Snapshot',len(manifest),'files; copies ready')
