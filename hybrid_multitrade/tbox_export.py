"""Build schema-only graphs; reject individual assertions before publication."""
from __future__ import annotations

import json

import networkx as nx
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef, XSD


SCHEMA_TYPES = {
    OWL.Class, OWL.Ontology, OWL.ObjectProperty, OWL.DatatypeProperty,
    OWL.AnnotationProperty, OWL.Restriction, OWL.Axiom,
    OWL.AllDisjointClasses, OWL.AllDisjointProperties,
    OWL.FunctionalProperty, OWL.InverseFunctionalProperty, OWL.TransitiveProperty,
    OWL.SymmetricProperty, OWL.AsymmetricProperty, OWL.ReflexiveProperty,
    OWL.IrreflexiveProperty, RDFS.Datatype, RDF.List,
}
SCHEMA_PREDICATES = {
    RDF.type, RDF.first, RDF.rest, RDFS.subClassOf, RDFS.subPropertyOf,
    RDFS.domain, RDFS.range, OWL.equivalentClass, OWL.equivalentProperty,
    OWL.disjointWith, OWL.propertyDisjointWith, OWL.disjointUnionOf,
    OWL.complementOf, OWL.unionOf, OWL.intersectionOf, OWL.inverseOf,
    OWL.onProperty, OWL.someValuesFrom, OWL.allValuesFrom,
    OWL.cardinality, OWL.minCardinality, OWL.maxCardinality,
    OWL.qualifiedCardinality, OWL.minQualifiedCardinality, OWL.maxQualifiedCardinality,
    OWL.onClass, OWL.onDataRange, OWL.hasSelf, OWL.hasKey, OWL.propertyChainAxiom,
    OWL.members, OWL.distinctMembers, OWL.annotatedSource, OWL.annotatedProperty,
    OWL.annotatedTarget, OWL.onDatatype, OWL.withRestrictions,
}
ANNOTATIONS = {
    RDFS.label, RDFS.comment, RDFS.seeAlso, RDFS.isDefinedBy,
    OWL.versionInfo, OWL.versionIRI, OWL.priorVersion, OWL.backwardCompatibleWith,
    OWL.incompatibleWith, OWL.deprecated,
}


def audit_tbox(graph: Graph) -> dict:
    """Strict pure T-Box policy: no named/implicit individuals or fact assertions."""
    annotations = ANNOTATIONS | set(graph.subjects(RDF.type, OWL.AnnotationProperty))
    errors = []
    for subject, predicate, value in graph:
        if predicate == RDF.type and value not in SCHEMA_TYPES:
            errors.append(f"individual_or_class_assertion:{subject}:{value}")
        if predicate in {OWL.sameAs, OWL.differentFrom, OWL.oneOf}:
            errors.append(f"individual_construct:{predicate}")
        elif predicate == OWL.hasValue:
            if not isinstance(value, Literal):
                errors.append(f"individual_value:{subject}")
        elif predicate not in SCHEMA_PREDICATES | annotations:
            # A declared ObjectProperty/DatatypeProperty used as a predicate is
            # an assertion, even when the subject is also declared as a class.
            errors.append(f"non_schema_assertion:{subject}:{predicate}")
    return {"passed": not errors, "violations": sorted(set(errors))}


def build_tbox(trade_id: str, base: dict, decisions: list, properties: list) -> tuple[Graph, dict]:
    accepted = [d for d in decisions if d["status"] == "accepted_provisional"]
    nodes = {k: {**v, "parents": [p for p in v.get("parents", []) if p != "OntologyEntity"]}
             for k, v in base.items() if v.get("origin") in {
                 "seed", "researcher_anchor", "researcher_cost_role_bridge"}}
    for decision in accepted:
        query = decision["query"]
        nodes[query["id"]] = {**query, "parents": [decision["parent"]]}
    dropped = []
    while True:
        bad = [k for k, value in nodes.items() if any(p not in nodes for p in value.get("parents", []))]
        if not bad:
            break
        dropped.extend(bad)
        for key in bad:
            del nodes[key]
    hierarchy = nx.DiGraph()
    hierarchy.add_nodes_from(nodes)
    ns = Namespace("https://example.org/kicem/hybrid/" + trade_id + "#")
    graph = Graph()
    graph.bind("tbox", ns)
    graph.add((URIRef(str(ns).rstrip("#")), RDF.type, OWL.Ontology))
    graph.add((URIRef(str(ns).rstrip("#")), OWL.versionInfo,
               Literal("Provisional hybrid T-Box; no independent expert gold validation")))
    graph.add((ns.evidence, RDF.type, OWL.AnnotationProperty))
    graph.add((ns.origin, RDF.type, OWL.AnnotationProperty))
    for key, value in nodes.items():
        graph.add((ns[key], RDF.type, OWL.Class))
        graph.add((ns[key], RDFS.label, Literal(value.get("label", key))))
        graph.add((ns[key], RDFS.comment, Literal(value.get("definition", ""))))
        graph.add((ns[key], ns.origin, Literal(value.get("origin", "unspecified"))))
        for parent in value.get("parents", []):
            graph.add((ns[key], RDFS.subClassOf, ns[parent]))
            hierarchy.add_edge(key, parent)
    for decision in accepted:
        if decision["query"]["id"] in nodes:
            graph.add((ns[decision["query"]["id"]], ns.evidence,
                       Literal(json.dumps(decision.get("export_verified_quotes", []), ensure_ascii=False))))
    ranges = {"string": XSD.string, "decimal": XSD.decimal, "integer": XSD.integer,
              "boolean": XSD.boolean, "float": XSD.float, "double": XSD.double}
    excluded_properties = []
    for prop in properties:
        if prop.get("domain") not in nodes:
            excluded_properties.append({"id": prop["id"], "reason": "domain_not_retained"})
            continue
        if prop.get("kind") != "data" or prop.get("range") not in ranges:
            raise ValueError(f"Unsupported property schema: {prop['id']}")
        uri = ns[prop["id"]]
        graph.add((uri, RDF.type, OWL.DatatypeProperty))
        graph.add((uri, RDFS.domain, ns[prop["domain"]]))
        graph.add((uri, RDFS.range, ranges[prop["range"]]))
        graph.add((uri, RDFS.label, Literal(prop["label"])))
        graph.add((uri, RDFS.comment, Literal(prop["definition"])))
    audit = audit_tbox(graph)
    if not nx.is_directed_acyclic_graph(hierarchy):
        raise ValueError("T-Box hierarchy contains a cycle")
    if not audit["passed"]:
        raise ValueError(f"A-Box content rejected: {audit['violations']}")
    return graph, {
        "classes": len(nodes), "data_properties": len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))),
        "subclass_axioms": len(set(graph.triples((None, RDFS.subClassOf, None)))),
        "object_properties": len(set(graph.subjects(RDF.type, OWL.ObjectProperty))),
        "retained_seed_classes": sum(v.get("origin") == "seed" for v in nodes.values()),
        "researcher_anchor_classes": sum(v.get("origin") in {"researcher_anchor", "researcher_cost_role_bridge"}
                                        for v in nodes.values()),
        "exported_accepted": sum(d["query"]["id"] in nodes for d in accepted),
        "dropped_classes": sorted(set(dropped)), "excluded_properties": excluded_properties,
        "pure_tbox": audit, "acyclic": True,
    }
