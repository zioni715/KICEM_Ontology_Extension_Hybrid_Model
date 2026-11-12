"""OWL consistency plus explicit cell, lineage, relation and arithmetic checks."""
import sys, subprocess, time
from pathlib import Path
from decimal import Decimal
MOD=Path(__file__).resolve().parent
sys.path.insert(0,str(MOD.parent/'shared'))
from common import *
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
import networkx as nx
import xlrd, owlready2
E=Namespace('https://example.org/kicem/tile/test2#')
g=Graph().parse(MOD/'outputs/tile_standalone.ttl')
xml=Graph().parse(MOD/'outputs/tile_standalone.owl')
from rdflib.compare import isomorphic
checks=[]
def check(name,ok,**detail):checks.append({'check':name,'passed':bool(ok),**detail})
check('Turtle and RDF/XML equivalent',isomorphic(g,xml))
rows={r['id']:r for r in read(T/'module1/outputs/extracted_rows.json') if r['extraction']['in_tile_scope']}
exports=read(MOD/'outputs/exported_rows.json')
book=xlrd.open_workbook(str(ROOT/read(T/'configs/experiment.json')['document']))
check('All included tile rows exported exactly once',len(exports)==len(rows) and {x['row_id'] for x in exports}==set(rows))
contract_fields=['contractQuantity','contractUnitPrice','contractAmount']
payment_fields=contract_fields+['previousCumulativeQuantity','previousCumulativeAmount','currentQuantity','currentAmount','cumulativeQuantity','cumulativeAmount','remainingQuantity','remainingAmount']
calc_fields=['materialUnitCost','laborUnitCost','expenseUnitCost']
source_gaps=[]
for e in exports:
    r=rows[e['row_id']];sheet=book.sheet_by_name(r['sheet']);cost=URIRef(e['cost_iri'])
    offset=0 if r['sheet']=='건내' else 2
    check('Source name/specification/unit',all(str(sheet.cell_value(r['row']-1,offset+i)).strip()==r[field] for i,field in enumerate(['name','specification','unit'])),row=r['id'])
    check('Single tile work category',list(g.objects(cost,E.belongsToWorkCategory))==[E.TileWork],row=r['id'])
    for role,fields in [('contract',contract_fields),('payment',payment_fields),('detail',contract_fields),('calculation',calc_fields)]:
        u=URIRef(e[role+'_iri'])
        check('One source document',len(list(g.subjects(E.containsItem,u)))==1,row=r['id'],role=role)
        check('Single cost reference',list(g.objects(u,E.representsCostItem))==[cost],row=r['id'],role=role)
        check('Square-metre unit',list(g.objects(u,E.usesUnit))==[E.SquareMetre],row=r['id'],role=role)
        for field in fields:
            cell=r['cells'][field];raw=sheet.cell_value(cell['row']-1,cell['column']-1);vals=list(g.objects(u,E[field]))
            check('Numeric value matches workbook cell',len(vals)==1 and isinstance(raw,(float,int)) and Decimal(str(vals[0]))==Decimal(str(raw)),row=r['id'],role=role,field=field)
    contract=URIRef(e['contract_iri']);payment=URIRef(e['payment_iri']);detail=URIRef(e['detail_iri']);calc=URIRef(e['calculation_iri'])
    for field in contract_fields:
        suffix=field[len('contract'):]
        check('Unique contract source for payment',list(g.subjects(E['providesContract'+suffix+'ToProgressPaymentItem'],payment))==[contract],row=r['id'],field=field)
        check('Unique contract source for work detail',list(g.subjects(E['providesContract'+suffix+'To'],detail))==[contract],row=r['id'],field=field)
    n={k:Decimal(str(v)) for k,v in r['numbers'].items() if v is not None}
    pairs=[('cumulativeQuantity',n['previousCumulativeQuantity']+n['currentQuantity']),('cumulativeAmount',n['previousCumulativeAmount']+n['currentAmount']),('remainingQuantity',n['contractQuantity']-n['cumulativeQuantity']),('remainingAmount',n['contractAmount']-n['cumulativeAmount'])]
    for field,expected in pairs:
        tolerance=Decimal('0.000001') if 'Quantity' in field else Decimal('1')
        check('Arithmetic reconciliation',abs(n[field]-expected)<=tolerance,row=r['id'],field=field,difference=str(n[field]-expected))
    calculated=sum(n[f] for f in calc_fields)
    check('Derived component unit price',Decimal(str(g.value(calc,E.calculatedUnitPrice)))==calculated,row=r['id'])
    check('Components reconcile contract unit price',abs(calculated-n['contractUnitPrice'])<=Decimal('1'),row=r['id'])
    if not list(g.subjects(E.providesCalculatedQuantityTo,contract)):source_gaps.append({'row':r['id'],'missing':'explicit quantity calculation source (A18)'})
    if n['previousCumulativeQuantity'] or n['previousCumulativeAmount']:
        if not list(g.subjects(E.providesCumulativeValuesTo,payment)):source_gaps.append({'row':r['id'],'missing':'previous-round source item'})
for typ,rel,field in [('ContractSummaryItem','contributesContractAmountTo','contractAmount'),('ProgressPaymentSummaryItem','contributesCurrentAmountTo','currentAmount')]:
    for u in g.subjects(RDF.type,E[typ]):
        members=list(g.subjects(E[rel],u));total=sum(Decimal(str(g.value(m,E[field]))) for m in members)
        check('Summary equals exported source slice',bool(members) and Decimal(str(g.value(u,E[field])))==total,summary=str(u))
classes=set(g.subjects(RDF.type,OWL.Class));named={u for u in classes if isinstance(u,URIRef)}
edges=[(s,o) for s,o in g.subject_objects(RDFS.subClassOf) if isinstance(s,URIRef) and isinstance(o,URIRef)]
check('Class hierarchy acyclic',nx.is_directed_acyclic_graph(nx.DiGraph(edges)))
check('No undefined class parent',all(o in named or o==OWL.Thing for s,o in edges))
check('No RC namespace logical terms',not any(isinstance(v,URIRef) and str(v).startswith('https://zioni715.github.io/ontology/rcpp') for triple in g for v in triple))
check('No ontology imports',not list(g.objects(None,OWL.imports)))
check('WBS represented only as individuals',not any(str(u).split('#')[-1].startswith('WBS_') for u in named))
check('WBS part-of acyclic',nx.is_directed_acyclic_graph(nx.DiGraph(g.subject_objects(E.partOfWorkTask))))
check('All WBS nodes represented',len(list(g.subjects(E.wbsCode,None)))==len(read(T/'shared/wbs.json')))
for s,o in g.subject_objects(E.appliesToWBS):check('WBS link has activity target',(o,RDF.type,E.WorkTask) in g,source=str(s))
for p in read(T/'module1/outputs/initial_schema.json')['properties']:
    for e in exports:
        vals={str(v) for v in g.objects(URIRef(e['cost_iri']),E[p['id']])};r=rows[e['row_id']]
        sourced={a['value'] for a in r['extraction']['attributes'] if a['name']==p['extracted_attribute'] and a.get('quote') and a['quote'] in r['name']+' '+r['specification']}
        check('Tile attribute has source quote',vals==sourced,row=r['id'],field=p['id'])
# Ensure accepted/rejected proposals are not silently bypassed at export.
decisions=read(MOD/'outputs/decisions.json')
for d in decisions:
    check('Candidate decision respected',(E[d['query']['id']] in named)==(d['status']=='accepted_provisional'),candidate=d['query']['id'])
wbs_byid={w['code']:w for w in read(T/'shared/wbs.json')}
for d in decisions:
    if d['status']!='accepted_provisional':continue
    q=d['query'];allowed_sources={z['source_id'] for z in d['export_verified_quotes']}
    for entity in g.subjects(RDF.type,E[q['id']]):
        code=g.value(entity,E.wbsCode)
        if code is not None:
            check('WBS class assignment has final source support','WBS:'+str(code) in allowed_sources,entity=str(entity),candidate=q['id'])
            if 'wall' in q['label'].lower() or '벽' in q['definition'] and q['origin']=='TaxoAdapt':
                w=wbs_byid[str(code)];context=w['quote'];parent=w['parent']
                while parent:context+=' '+wbs_byid[parent]['quote'];parent=wbs_byid[parent]['parent']
                check('Wall class has wall WBS context','벽' in context,entity=str(entity))
        else:
            matched=next((e for e in exports if e['cost_iri']==str(entity)),None)
            if matched:check('Cost subtype assignment has final source support',matched['row_id'] in allowed_sources,entity=str(entity),candidate=q['id'])
java=next((ROOT/'hybrid_pipeline/runtime/java').glob('*/bin/java'))
jar=Path(owlready2.__file__).parent/'hermit/HermiT.jar'
reasoner=[]
for file,expected in [('seed_for_reasoner.owl',True),('tile_standalone.owl',True),('negative_control.owl',False)]:
    cmd=[str(java),'-Xmx2048M','-cp',str(jar),'org.semanticweb.HermiT.cli.CommandLine','-k']
    if expected:cmd.append('-U')
    cmd.append((MOD/'outputs'/file).as_uri());start=time.time();consistent=None;unsat=[];error=None
    try:
        result=subprocess.run(cmd,text=True,capture_output=True,timeout=180)
        if 'is not satisfiable.' in result.stdout or 'InconsistentOntologyException' in result.stderr:consistent=False
        elif 'is satisfiable.' in result.stdout:consistent=True
        marker="Classes equivalent to 'owl:Nothing':"
        if expected and marker in result.stdout:unsat=[l.strip() for l in result.stdout.split(marker,1)[1].splitlines() if l.strip() and l.strip() not in ['owl:Nothing','<http://www.w3.org/2002/07/owl#Nothing>']]
        if consistent is None or (result.returncode and consistent is not False):error='Unrecognized response or reasoner failure'
        if expected and consistent and marker not in result.stdout:error='Missing class satisfiability result'
        raw={'stdout':result.stdout,'stderr':result.stderr,'returncode':result.returncode}
    except subprocess.TimeoutExpired:
        error='Reasoner timeout';raw={}
    case={'file':file,'expected_consistent':expected,'consistent':consistent,'unsatisfiable_classes':unsat,'error':error,'seconds':time.time()-start,'command':cmd,'raw':raw,'passed':consistent==expected and not unsat and error is None}
    reasoner.append(case);print('Reasoner',file,case['passed'],flush=True)
protected=read(T/'reports/protected_sha256.json')['files'];changed=[p for p,h in protected.items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
# .gitignore change was already recorded for excluding credentials before this run.
original_changes=[p for p in changed if p!='.gitignore']
check('Original sources and seed unchanged',not original_changes,changes=original_changes)
report={'passed':all(c['passed'] for c in checks) and all(c['passed'] for c in reasoner),'custom_data_checks':len(checks),'failed_checks':[c for c in checks if not c['passed']],
        'reasoner_cases':reasoner,'source_gaps':source_gaps,'complete_source_coverage':not source_gaps,'original_files_checked':len(protected),'original_changes':original_changes,'other_baseline_changes':changed,
        'limitations':['OWL open-world consistency does not prove source completeness or semantic correctness','No CBS, independent quantity sheet or previous-round source supplied','Workbook numeric cells are saved/cached values; source workbook is not recalculated','Custom explicit data checks, not a claim of SHACL conformance','No expert-labelled accuracy evaluation']}
write(MOD/'reports/validation.json',report);write(MOD/'reports/data_checks.json',checks)
print('Validation:',report['passed'],'checks',len(checks),'failures',len(report['failed_checks']),'source gaps',len(source_gaps),flush=True)
if not report['passed']:raise SystemExit(1)
