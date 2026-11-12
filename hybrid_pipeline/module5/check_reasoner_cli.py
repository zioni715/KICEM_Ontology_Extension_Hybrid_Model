from pathlib import Path
import subprocess,json,time
T=Path(__file__).resolve().parents[1]
java=str(next((T/'runtime/java').glob('*/bin/java')))
jar='/home/sil-jiwon/anaconda3/envs/hybrid-v1/lib/python3.11/site-packages/owlready2/hermit/HermiT.jar'
cmd=[java,'-Xmx4096M','-cp',jar,'org.semanticweb.HermiT.cli.CommandLine','-k','-U',(T/'module5/tile_extension.owl').as_uri()]
t=time.time()
try:
 r=subprocess.run(cmd,text=True,capture_output=True,timeout=180);data={'command':cmd,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'seconds':time.time()-t}
except subprocess.TimeoutExpired as e:data={'command':cmd,'timeout':180,'stdout':str(e.stdout),'stderr':str(e.stderr),'seconds':time.time()-t}
(T/'module5/cli_probe.json').write_text(json.dumps(data,indent=2));print(data)
