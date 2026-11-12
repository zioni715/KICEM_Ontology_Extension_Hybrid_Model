import sys,time,subprocess
from pathlib import Path
MOD=Path(__file__).resolve().parent;sys.path.insert(0,str(MOD.parent/'shared'))
from common import *
import owlready2 as ow
from rdflib import Graph,RDF,RDFS,OWL,Namespace,URIRef
import networkx as nx
ow.JAVA_EXE=str(next((TEST/'runtime/java').glob('*/bin/java')));ow.reasoning.JAVA_MEMORY=4096
results=[]
jar=str(Path(ow.__file__).parent/'hermit/HermiT.jar')
for name,expected in [('seed_for_reasoner.owl',True),('negative_control_unadapted.owl',False),('tile_extension.owl',True)]:
 t=time.time();consistent=None;error=None;unsat=[]
 cmd=[ow.JAVA_EXE,'-Xmx4096M','-cp',jar,'org.semanticweb.HermiT.cli.CommandLine','-k']
 if expected:cmd.append('-U')
 cmd.append((MOD/name).as_uri())
 try:
  result=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
  if 'org.semanticweb.owlapi.reasoner.InconsistentOntologyException: Inconsistent ontology' in result.stderr:consistent=False
  elif 'is not satisfiable.' in result.stdout:consistent=False
  elif 'is satisfiable.' in result.stdout:consistent=True
  if expected and "Classes equivalent to 'owl:Nothing':" in result.stdout:
   tail=result.stdout.split("Classes equivalent to 'owl:Nothing':",1)[1]
   unsat=[line.strip() for line in tail.splitlines() if line.strip() and line.strip() not in ['owl:Nothing','<http://www.w3.org/2002/07/owl#Nothing>']]
  if (result.returncode and consistent is not False) or consistent is None:error=result.stderr or 'unrecognized HermiT response'
  if expected and consistent is True and "Classes equivalent to 'owl:Nothing':" not in result.stdout:error='Missing unsatisfiable-class result'
  raw={'stdout':result.stdout,'stderr':result.stderr,'returncode':result.returncode}
 except Exception as e:error=repr(e);raw={}
 results.append({'file':name,'consistent':consistent,'expected_consistent':expected,'unsatisfiable_named_classes':unsat,'error':error,'seconds':time.time()-t,'passed':consistent==expected and not unsat and error is None,'command':cmd,'raw':raw})
 print(results[-1],flush=True)
g=Graph().parse(MOD/'tile_extension.ttl');R=Namespace('https://zioni715.github.io/ontology/rcpp#');E=Namespace('https://example.org/kicem/tile/v1#')
exported=read(MOD/'exported_rows.json');rows={r['id']:r for r in read(TEST/'module1/rows.json')};checks=[]
for e in exported:
 r=rows[e['row_id']];p=URIRef(e['payment_iri']);c=URIRef(e['cost_iri'])
 for key,value in r['numbers'].items():
  vals=list(g.objects(p,R[key]));checks.append({'row':r['id'],'field':key,'passed':len(vals)==1 and value is not None and float(vals[0])==value})
 for prop in [R.representsCostItem,R.usesUnit]:checks.append({'row':r['id'],'field':str(prop),'passed':len(list(g.objects(p,prop)))==1})
 checks.append({'row':r['id'],'field':'belongsToWorkCategory','passed':list(g.objects(c,R.belongsToWorkCategory))==[E.TileWork]})
dag=nx.DiGraph((str(s),str(o)) for s,o in g.subject_objects(RDFS.subClassOf) if isinstance(s,URIRef) and isinstance(o,URIRef))
wbscycle=nx.DiGraph((str(s),str(o)) for s,o in g.subject_objects(R.subWorkCategoryOf))
checks.extend([{'field':'class_DAG','passed':nx.is_directed_acyclic_graph(dag)},{'field':'WBS_DAG','passed':nx.is_directed_acyclic_graph(wbscycle)},{'field':'no_WBS_as_OWL_class','passed':not any(str(s).startswith(str(E)+'WBS_') for s in g.subjects(RDF.type,OWL.Class))}])
orig=read(TEST/'reports/original_sha256.json');changed=[p for p,h in orig.items() if digest(ROOT/p)!=h]
write(MOD/'validation.json',{'reasoner':'HermiT bundled with Owlready2 0.48; CLI -k/-U, no full individual realization','java':subprocess.check_output([ow.JAVA_EXE,'-version'],stderr=subprocess.STDOUT,text=True),'reasoner_cases':results,'data_checks':len(checks),'data_checks_failed':[x for x in checks if not x['passed']],'original_files_checked':len(orig),'original_files_changed':changed,'passed':all(x['passed'] for x in results) and all(x['passed'] for x in checks) and not changed,'limitations':'OWL consistency does not prove factual correctness; explicit cardinality and cell checks cover only exported slice, no expert gold/CBS/full financial reconciliation.'})
print(read(MOD/'validation.json'))

if not read(MOD/'validation.json')['passed']:
 raise SystemExit(1)
