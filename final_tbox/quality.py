"""Reusable fail-closed invariants for a T-Box release graph."""
from __future__ import annotations

from rdflib import BNode, Namespace, OWL, RDF, RDFS, URIRef
import networkx as nx


E = Namespace("https://example.org/kicem/tile/final#")
RENAMES = {
    "StoneTileAdhesiveCostItem": "StoneTilePressureBondingCostItem",
    "PorcelainTileAdhesiveCostItem": "PorcelainTilePressureBondingCostItem",
    "CeramicTileAdhesiveCostItem": "CeramicTilePressureBondingCostItem",
    "MosaicTileAdhesiveCostItem": "MosaicTilePressureBondingCostItem",
    "TA_ac621fe07583": "WallTileInstallation",
}
RC_ONLY = {
    "ConcreteCostItem", "ConcretePlacementCostItem", "FormworkCostItem",
    "ReadyMixedConcreteMaterialCostItem", "RebarCostItem",
    "RebarFabricationAssemblyCostItem", "RebarMaterialCostItem", "ShoringCostItem",
}


def local(uri: URIRef) -> str:
    return str(uri).split("#")[-1]


def inspect_tbox(graph, decisions) -> list[dict]:
    violations = []

    def add(code, **detail):
        violations.append({"code": code, **detail})

    classes = {x for x in graph.subjects(RDF.type, OWL.Class) if isinstance(x, URIRef)}
    characteristic_types = {
        OWL.FunctionalProperty, OWL.InverseFunctionalProperty, OWL.TransitiveProperty,
        OWL.SymmetricProperty, OWL.AsymmetricProperty, OWL.ReflexiveProperty,
        OWL.IrreflexiveProperty,
    }
    declaration_types = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
                         OWL.AnnotationProperty, OWL.Ontology} | characteristic_types
    assertions = [(str(s), str(o)) for s, o in graph.subject_objects(RDF.type)
                  if isinstance(s, URIRef) and o not in declaration_types]
    if assertions:
        add("ABOX_ASSERTION", values=assertions[:20])
    if list(graph.subjects(RDF.type, OWL.NamedIndividual)):
        add("NAMED_INDIVIDUAL")
    if list(graph.triples((None, OWL.hasValue, None))) or list(
            graph.triples((None, OWL.oneOf, None))):
        add("NOMINAL")

    edges = [(child, parent) for child, parent in graph.subject_objects(RDFS.subClassOf)
             if isinstance(child, URIRef) and isinstance(parent, URIRef)]
    if any(child not in classes or parent not in classes for child, parent in edges):
        add("UNDECLARED_SUBCLASS_ENDPOINT")
    hierarchy = nx.DiGraph(edges)
    if not nx.is_directed_acyclic_graph(hierarchy):
        add("CLASS_CYCLE")

    actual_ids = {local(x) for x in classes}
    rc_leaks = sorted(RC_ONLY & actual_ids)
    if rc_leaks:
        add("RC_ONLY_CLASS", values=rc_leaks)
    if any(str(term).startswith("https://example.org/kicem/tile/test2")
           for triple in graph for term in triple if isinstance(term, URIRef)):
        add("PILOT_NAMESPACE")

    accepted = [x for x in decisions if x["status"] == "accepted_provisional"]
    held = [x for x in decisions if x["status"] != "accepted_provisional"]
    accepted_ids = {RENAMES.get(x["query"]["id"], x["query"]["id"]): x
                    for x in accepted}
    held_ids = {RENAMES.get(x["query"]["id"], x["query"]["id"]) for x in held}
    missing = sorted(set(accepted_ids) - actual_ids)
    if missing:
        add("ACCEPTED_CANDIDATE_MISSING", values=missing)
    leaks = sorted(held_ids & actual_ids)
    if leaks:
        add("HELD_CANDIDATE_EXPORTED", values=leaks)
    mismatches = []
    for class_id, decision in accepted_ids.items():
        expected = {q["source_id"] for q in decision.get("export_verified_quotes", [])}
        actual = {str(x) for x in graph.objects(E[class_id], E.evidenceSourceId)}
        if expected != actual:
            mismatches.append({"class": class_id, "expected": sorted(expected),
                               "actual": sorted(actual)})
    if mismatches:
        add("EVIDENCE_MISMATCH", values=mismatches)
    return violations
