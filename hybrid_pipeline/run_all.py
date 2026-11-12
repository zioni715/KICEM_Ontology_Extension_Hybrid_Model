"""Sequential replay on the pinned hybrid-v1 environment; large stages never overlap."""
from pathlib import Path
import subprocess,sys,os,json,time
T=Path(__file__).resolve().parent
steps=['shared/bootstrap.py','shared/download_models.py','shared/download_java.py','module1/prepare.py','module1/run.py','module2/run.py','module3/run.py','module4/run.py','module5/rank.py','module5/run.py']
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false')
records=[]
for step in steps:
 p=T/step;log=p.parent/(p.stem+'.log');t=time.time();print('RUN',step,flush=True)
 with log.open('w') as f:r=subprocess.run([sys.executable,str(p)],cwd=T.parent,env=env,stdout=f,stderr=subprocess.STDOUT)
 records.append({'step':step,'returncode':r.returncode,'seconds':time.time()-t,'log':str(log)});(T/'reports/replay_status.json').write_text(json.dumps(records,indent=2))
 if r.returncode:raise SystemExit(f'Failed: {step}; see {log}')
