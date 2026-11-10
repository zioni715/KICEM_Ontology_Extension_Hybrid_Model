#!/usr/bin/env python3
"""Build the release T-Box directly from the RC seed and reviewed candidates.

No pilot OWL or A-Box is read. The exporter remaps reusable seed axioms into
the release namespace, adds the accepted tile schema, and serializes a pure
T-Box. Existing experiment inputs and outputs are never modified.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from rdflib import BNode, Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef, XSD
from rdflib.compare import to_canonical_graph


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
SEED = ROOT / "KO/OWL2/rcpp-owl-final.ttl"
ELEMENTS = ROOT / "test2/shared/seed_elements.json"
SCHEMA = ROOT / "test2/module1/outputs/initial_schema.json"
DECISIONS = ROOT / "test2/module5/outputs/decisions.json"
GROUNDING = ROOT / "test2/module5/reports/grounding_rules.json"

RC = Namespace("https://zioni715.github.io/ontology/rcpp#")
NEW = Namespace("https://example.org/kicem/tile/final#")
NEW_ONTOLOGY = URIRef("https://example.org/kicem/tile/final")
DCTERMS = Namespace("http://purl.org/dc/terms/")

RC_CLASS_IDS = {
    "ConcreteCostItem", "ConcretePlacementCostItem", "FormworkCostItem",
    "ReadyMixedConcreteMaterialCostItem", "RebarCostItem",
    "RebarFabricationAssemblyCostItem", "RebarMaterialCostItem", "ShoringCostItem",
}
RENAMES = {
    "StoneTileAdhesiveCostItem": "StoneTilePressureBondingCostItem",
    "PorcelainTileAdhesiveCostItem": "PorcelainTilePressureBondingCostItem",
    "CeramicTileAdhesiveCostItem": "CeramicTilePressureBondingCostItem",
    "MosaicTileAdhesiveCostItem": "MosaicTilePressureBondingCostItem",
    "TA_ac621fe07583": "WallTileInstallation",
}
NORMALISED_TEXT = {
    "StoneTilePressureBondingCostItem":
        ("석재타일 압착붙임 비용", "석재타일 압착붙임 작업의 비용대상."),
    "PorcelainTilePressureBondingCostItem":
        ("포세린타일 압착붙임 비용", "포세린타일 압착붙임 작업의 비용대상."),
    "CeramicTilePressureBondingCostItem":
        ("세라믹타일 압착붙임 비용", "세라믹타일 압착붙임 작업의 비용대상."),
    "MosaicTilePressureBondingCostItem":
        ("모자이크타일 압착붙임 비용", "모자이크타일 압착붙임 작업의 비용대상."),
    "WallTileInstallation": ("벽 타일 시공", "벽면에 타일을 설치하는 작업 활동."),
}
PARENT_OVERRIDES = {"WallTileInstallation": "TileInstallation"}
FOUNDATIONS = {
    "WorkTask": ("타일 작업 활동", "타일공사의 작업 활동 유형."),
    "InstallationMethod": ("타일 시공 방법", "타일을 시공하는 방법의 유형."),
    "TileMaterial": ("타일 재료", "타일공사에서 사용하는 재료의 유형."),
    "ApplicationSurface": ("타일 적용 표면", "타일이 적용되는 표면의 유형."),
    "TileMaterialCostItem": ("타일 자재 비용대상", "타일 자재 공급의 비용대상."),
    "TileInstallationCostItem": ("타일 설치 비용대상", "타일 설치 작업의 비용대상."),
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rc_local(term: URIRef) -> str:
    return str(term)[len(str(RC)):]


def remap(term):
    if isinstance(term, URIRef) and str(term).startswith(str(RC)):
        return NEW[rc_local(term)]
    return term


def blank_closure(graph: Graph, node: BNode, seen: set | None = None) -> list[tuple]:
    seen = set() if seen is None else seen
    if node in seen:
        return []
    seen.add(node)
    triples = list(graph.triples((node, None, None)))
    for _, _, obj in list(triples):
        if isinstance(obj, BNode):
            triples.extend(blank_closure(graph, obj, seen))
    return triples


def bundle_is_allowed(triples: list[tuple], allowed: set[str]) -> bool:
    return all(not (isinstance(term, URIRef) and str(term).startswith(str(RC))
                       and rc_local(term) not in allowed)
               for triple in triples for term in triple)


def add_class(graph: Graph, class_id: str, label: str, definition: str,
              parent: str | None, origin: str) -> None:
    uri = NEW[class_id]
    graph.add((uri, RDF.type, OWL.Class))
    graph.add((uri, RDFS.label, Literal(label, lang="ko")))
    graph.add((uri, RDFS.comment, Literal(definition, lang="ko")))
    graph.add((uri, NEW.researchOrigin, Literal(origin)))
    if parent:
        graph.add((uri, RDFS.subClassOf, NEW[parent]))


def canonicalise_rdfxml(path: Path) -> None:
    """Sort RDF/XML descriptions and predicates for byte reproducibility."""
    for prefix, namespace in (("rdf", RDF), ("rdfs", RDFS), ("owl", OWL),
                              ("tile", NEW), ("dcterms", DCTERMS)):
        ET.register_namespace(prefix, str(namespace))
    tree = ET.parse(path)
    root = tree.getroot()
    rdf_about = f"{{{RDF}}}about"
    rdf_node = f"{{{RDF}}}nodeID"

    def child_key(element):
        return (element.tag, element.get(f"{{{RDF}}}resource", ""),
                element.get(rdf_node, ""), element.text or "")

    for description in root:
        description[:] = sorted(list(description), key=child_key)
    root[:] = sorted(list(root), key=lambda element:
                     (element.get(rdf_about, ""), element.get(rdf_node, ""), element.tag))
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build() -> dict:
    inputs = (SEED, ELEMENTS, SCHEMA, DECISIONS, GROUNDING)
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(f"Required release input missing: {path}")
    seed = Graph().parse(SEED)
    elements = load_json(ELEMENTS)
    schema = load_json(SCHEMA)
    decisions = load_json(DECISIONS)
    grounding = load_json(GROUNDING)

    excluded = {item["id"] for item in elements
                if item["id"] in RC_CLASS_IDS or
                set(item.get("domains", [])) & RC_CLASS_IDS}
    common = {item["id"] for item in elements if item["id"] not in excluded}
    allowed = set(common)

    target = Graph()
    for prefix, namespace in {"tile": NEW, "owl": OWL, "rdf": RDF,
                              "rdfs": RDFS, "xsd": XSD,
                              "dcterms": DCTERMS}.items():
        target.bind(prefix, namespace)

    removed_axioms = []
    for entity_id in sorted(allowed):
        root = RC[entity_id]
        for triple in seed.triples((root, None, None)):
            closure = blank_closure(seed, triple[2]) if isinstance(triple[2], BNode) else []
            bundle = [triple, *closure]
            if not bundle_is_allowed(bundle, allowed):
                removed_axioms.append({"subject": entity_id,
                                       "predicate": str(triple[1]),
                                       "reason": "references RC-only or A-Box entity"})
                continue
            for subject, predicate, obj in bundle:
                target.add((remap(subject), remap(predicate), remap(obj)))

    target.add((NEW_ONTOLOGY, RDF.type, OWL.Ontology))

    for prop, label in ((DCTERMS.source, "출처"),
                        (NEW.researchOrigin, "생성 출처"),
                        (NEW.evidenceSourceId, "근거 출처 식별자"),
                        (NEW.releaseCuration, "최종본 교정 내역"),
                        (NEW.validationStatus, "검증 상태")):
        target.add((prop, RDF.type, OWL.AnnotationProperty))
        target.add((prop, RDFS.label, Literal(label, lang="ko")))

    for class_id, (label, definition) in FOUNDATIONS.items():
        parent = "CostItem" if class_id.endswith("CostItem") else None
        add_class(target, class_id, label, definition, parent, "researcher_schema_adapter")

    for left, right in (("CostItem", "WorkTask"), ("CostItem", "TileMaterial"),
                        ("CostItem", "InstallationMethod"),
                        ("CostItem", "ApplicationSurface"),
                        ("CostItem", "DocumentItem")):
        target.add((NEW[left], OWL.disjointWith, NEW[right]))

    accepted = [item for item in decisions if item["status"] == "accepted_provisional"]
    grounded_ids = {item.get("candidate_id") for item in grounding.get("items", [])
                    if item.get("final_status") == "accepted_provisional"}
    for item in accepted:
        old_id = item["query"]["id"]
        class_id = RENAMES.get(old_id, old_id)
        parent = RENAMES.get(item["parent"], item["parent"]) if item.get("parent") else None
        parent = PARENT_OVERRIDES.get(class_id, parent)
        label = item["query"]["label"]
        definition = item["query"]["definition"]
        if class_id in NORMALISED_TEXT:
            label, definition = NORMALISED_TEXT[class_id]
        add_class(target, class_id, label, definition, parent, item["query"]["origin"])
        target.add((NEW[class_id], NEW.validationStatus, Literal("provisional")))
        for quote in item.get("export_verified_quotes", []):
            target.add((NEW[class_id], NEW.evidenceSourceId, Literal(quote["source_id"])))
        if class_id != old_id:
            target.add((NEW[class_id], NEW.releaseCuration,
                        Literal(f"identifier normalised from {old_id}")))
        if class_id in PARENT_OVERRIDES:
            target.add((NEW[class_id], NEW.releaseCuration,
                        Literal(f"parent refined to {PARENT_OVERRIDES[class_id]}")))

    for prop in schema["properties"]:
        uri = NEW[prop["id"]]
        target.add((uri, RDF.type, OWL.DatatypeProperty))
        target.add((uri, RDFS.domain, NEW[prop["domain"]]))
        target.add((uri, RDFS.range, XSD.string))
        target.add((uri, RDFS.label, Literal(prop["label"], lang="ko")))
        target.add((uri, RDFS.comment, Literal(prop["definition"], lang="ko")))
        target.add((uri, NEW.researchOrigin, Literal(prop["origin"])))

    new_object_properties = {
        "partOfWorkTask": ("작업 구성 관계", "세부 작업이 상위 작업에 포함되는 관계.",
                           "WorkTask", "WorkTask"),
        "appliesToWBS": ("관련 작업", "비용대상이 관련된 WBS 작업 활동.",
                         "CostItem", "WorkTask"),
    }
    for prop_id, (label, comment, domain, range_id) in new_object_properties.items():
        uri = NEW[prop_id]
        target.add((uri, RDF.type, OWL.ObjectProperty))
        target.add((uri, RDFS.domain, NEW[domain]))
        target.add((uri, RDFS.range, NEW[range_id]))
        target.add((uri, RDFS.label, Literal(label, lang="ko")))
        target.add((uri, RDFS.comment, Literal(comment, lang="ko")))
        target.add((uri, NEW.researchOrigin, Literal("researcher_relation_adapter")))
    target.add((NEW.partOfWorkTask, RDF.type, OWL.AsymmetricProperty))
    target.add((NEW.partOfWorkTask, RDF.type, OWL.IrreflexiveProperty))

    canonical = Graph()
    for prefix, namespace in target.namespaces():
        canonical.bind(prefix, namespace)
    for triple in to_canonical_graph(target):
        canonical.add(triple)

    OUT.mkdir(parents=True, exist_ok=True)
    turtle = OUT / "tile_tbox_final.ttl"
    rdfxml = OUT / "tile_tbox_final.owl"
    canonical.serialize(turtle, format="turtle")
    turtle.write_text(
        turtle.read_text(encoding="utf-8").rstrip() + "\n",
        encoding="utf-8",
    )
    canonical.serialize(rdfxml, format="xml")
    canonicalise_rdfxml(rdfxml)

    named_classes = {x for x in canonical.subjects(RDF.type, OWL.Class)
                     if isinstance(x, URIRef)}
    manifest = {
        "release": "2.0.0",
        "scope": "direct T-Box only; no A-Box source ontology",
        "namespace": str(NEW),
        "triples": len(canonical),
        "named_classes": len(named_classes),
        "object_properties": len(set(canonical.subjects(RDF.type, OWL.ObjectProperty))),
        "datatype_properties": len(set(canonical.subjects(RDF.type, OWL.DatatypeProperty))),
        "annotation_properties": len(set(canonical.subjects(RDF.type, OWL.AnnotationProperty))),
        "retained_seed_classes": len([x for x in elements
                                      if x["type"] == "Class" and x["id"] not in excluded]),
        "foundation_classes_added": len(FOUNDATIONS),
        "accepted_candidate_classes": len(accepted),
        "held_candidate_classes": len(decisions) - len(accepted),
        "excluded_seed_entities": sorted(excluded),
        "removed_seed_axioms": removed_axioms,
        "identifier_renames": RENAMES,
        "parent_overrides": PARENT_OVERRIDES,
        "grounding_report_accepted_ids_if_available": sorted(x for x in grounded_ids if x),
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in inputs},
        "output_sha256": {turtle.name: sha256(turtle), rdfxml.name: sha256(rdfxml)},
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
