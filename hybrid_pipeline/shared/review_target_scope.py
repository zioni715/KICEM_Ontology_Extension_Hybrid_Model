"""Read-only audit of seed OWL2 scope; emits review material, not a target ontology."""
from pathlib import Path
import hashlib,json
from rdflib import Graph,RDF,RDFS,OWL,URIRef,Namespace
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'hybrid_pipeline/reports'
source=ROOT/'KO/OWL2/rcpp-owl-final.ttl';g=Graph().parse(source);R=Namespace('https://zioni715.github.io/ontology/rcpp#')
rc={R[x] for x in ['ConcreteCostItem','ConcretePlacementCostItem','FormworkCostItem','ReadyMixedConcreteMaterialCostItem','RebarCostItem','RebarFabricationAssemblyCostItem','RebarMaterialCostItem','ShoringCostItem']}
def term(s):
 return {'iri':str(s),'name':str(s).split('#')[-1],'label':str(g.value(s,RDFS.label) or ''),'comment':str(g.value(s,RDFS.comment) or ''),'domains':[str(o) for o in g.objects(s,RDFS.domain)],'ranges':[str(o) for o in g.objects(s,RDFS.range)]}
classes={s for s in g.subjects(RDF.type,OWL.Class) if isinstance(s,URIRef)};data=set(g.subjects(RDF.type,OWL.DatatypeProperty));objects=set(g.subjects(RDF.type,OWL.ObjectProperty));specific={p for p in data if any(d in rc for d in g.objects(p,RDFS.domain))}
x={'seed_file':str(source.relative_to(ROOT)),'seed_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'status':'scope_review_only; no revised ontology constructed','rc_specific_classes':[term(s) for s in sorted(rc)],'common_structure_candidates':[term(s) for s in sorted(classes-rc)],'rc_scoped_datatype_properties':[term(s) for s in sorted(specific)],'other_datatype_candidates':[term(s) for s in sorted(data-specific)],'object_relation_candidates':[term(s) for s in sorted(objects)],'not_automatic_reuse':['CostItem has the RC-only exhaustive disjointUnionOf axiom.','Generic labels do not establish equivalence; domains, ranges, definitions and restrictions must be reviewed.','Schema availability does not establish actual source documents or evidence instances.','WBS decomposition is not automatically an OWL subclass relation.']}
(OUT/'seed_scope_review.json').write_text(json.dumps(x,ensure_ascii=False,indent=2))
print(json.dumps({'rc_specific_classes':len(rc),'common_structure_candidates':len(classes-rc),'rc_scoped_datatype_properties':len(specific),'other_datatype_candidates':len(data-specific),'object_relation_candidates':len(objects)},ensure_ascii=False))
