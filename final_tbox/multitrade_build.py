#!/usr/bin/env python3
"""Build three independent, evidence-grounded, pure T-Box extensions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef
from rdflib.compare import to_canonical_graph


HERE = Path(__file__).resolve().parent
INPUT = HERE / "benchmarks/multitrade_candidates.json"
OUT = HERE / "outputs/multitrade"

BASE_CLASSES = {
    "WorkTask": ("건설 작업", "건설 과정에서 수행되는 작업 유형.", None),
    "ConstructionTask": ("공종 작업", "특정 공종을 구성하는 작업 유형.", "WorkTask"),
    "PreparationTask": ("준비 작업", "본 시공 전에 수행되는 준비 작업 유형.", "WorkTask"),
    "InstallationTask": ("설치 작업", "시설 또는 마감재를 설치하는 작업 유형.", "WorkTask"),
    "FinishingTask": ("마무리 작업", "본 시공 이후 수행되는 마무리 작업 유형.", "WorkTask"),
    "InspectionTask": ("검사 작업", "시공 상태나 성능을 확인하는 작업 유형.", "WorkTask"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonicalise_rdfxml(path: Path, namespace: Namespace) -> None:
    for prefix, value in (("rdf", RDF), ("rdfs", RDFS), ("owl", OWL), ("tbox", namespace)):
        ET.register_namespace(prefix, str(value))
    tree = ET.parse(path)
    root = tree.getroot()
    about = f"{{{RDF}}}about"
    node_id = f"{{{RDF}}}nodeID"
    resource = f"{{{RDF}}}resource"
    for description in root:
        description[:] = sorted(description, key=lambda e: (e.tag, e.get(resource, ""), e.text or ""))
    root[:] = sorted(root, key=lambda e: (e.get(about, ""), e.get(node_id, ""), e.tag))
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def add_class(graph: Graph, ns: Namespace, class_id: str, label: str,
              definition: str, parent: str | None, source_id: str,
              section: str) -> None:
    uri = ns[class_id]
    graph.add((uri, RDF.type, OWL.Class))
    graph.add((uri, RDFS.label, Literal(label, lang="ko")))
    graph.add((uri, RDFS.comment, Literal(definition, lang="ko")))
    graph.add((uri, ns.evidenceSourceId, Literal(source_id)))
    graph.add((uri, ns.evidenceSection, Literal(section)))
    graph.add((uri, ns.validationStatus, Literal("candidate")))
    if parent:
        graph.add((uri, RDFS.subClassOf, ns[parent]))


def build_case(case: dict) -> dict:
    ns = Namespace(case["namespace"])
    graph = Graph()
    graph.bind("tbox", ns)
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    ontology_iri = URIRef(case["namespace"].rstrip("#"))
    graph.add((ontology_iri, RDF.type, OWL.Ontology))
    for prop, label in (("evidenceSourceId", "근거 출처 식별자"),
                        ("evidenceSection", "근거 조항"),
                        ("predictedDirectParent", "모델 예측 직접 부모"),
                        ("validationStatus", "검증 상태")):
        graph.add((ns[prop], RDF.type, OWL.AnnotationProperty))
        graph.add((ns[prop], RDFS.label, Literal(label, lang="ko")))

    for class_id, (label, definition, parent) in BASE_CLASSES.items():
        add_class(graph, ns, class_id, label, definition, parent,
                  "SYSTEM-SCHEMA", "common upper T-Box")

    default_source = case["sources"][0]["source_id"]
    trade_root = case["candidates"][0][0]
    candidate_ids = set()
    for record in case["candidates"]:
        class_id, label, parent, section, definition = record[:5]
        source_id = record[5] if len(record) > 5 else default_source
        if class_id in candidate_ids or class_id in BASE_CLASSES:
            raise ValueError(f"Duplicate candidate identifier: {case['trade_id']}:{class_id}")
        candidate_ids.add(class_id)
        add_class(graph, ns, class_id, label, definition, parent, source_id, section)
        graph.add((ns[class_id], ns.predictedDirectParent, ns[parent]))
        # A generic task parent classifies the work type; this second T-Box edge
        # also keeps every domain candidate reachable below its trade root.
        if parent in BASE_CLASSES and class_id != trade_root:
            graph.add((ns[class_id], RDFS.subClassOf, ns[trade_root]))

    known = candidate_ids | set(BASE_CLASSES)
    dangling = [(record[0], record[2]) for record in case["candidates"] if record[2] not in known]
    if dangling:
        raise ValueError(f"Dangling parent(s) in {case['trade_id']}: {dangling}")

    canonical = Graph()
    for prefix, value in graph.namespaces():
        canonical.bind(prefix, value)
    for triple in to_canonical_graph(graph):
        canonical.add(triple)

    OUT.mkdir(parents=True, exist_ok=True)
    ttl = OUT / f"{case['trade_id']}.ttl"
    owl = OUT / f"{case['trade_id']}.owl"
    canonical.serialize(ttl, format="turtle")
    # rdflib emits an extra empty line; normalize it for clean diffs and stable
    # text artifacts across release tooling.
    ttl.write_text(ttl.read_text(encoding="utf-8").rstrip() + "\n", encoding="utf-8")
    canonical.serialize(owl, format="xml")
    canonicalise_rdfxml(owl, ns)
    return {
        "trade_id": case["trade_id"],
        "trade_label": case["trade_label"],
        "namespace": case["namespace"],
        "candidate_classes": len(candidate_ids),
        "total_classes": len(candidate_ids) + len(BASE_CLASSES),
        "source_ids": sorted(source["source_id"] for source in case["sources"]),
        "outputs": {ttl.name: sha256(ttl), owl.name: sha256(owl)},
    }


def build_all() -> dict:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    cases = [build_case(case) for case in data["cases"]]
    manifest = {
        "release": "3.0.0-multitrade",
        "scope": "three independent T-Box-only extension cases",
        "builder_reads_validation_gold": False,
        "input_sha256": {str(INPUT.relative_to(HERE)): sha256(INPUT)},
        "cases": cases,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build_all(), ensure_ascii=False, indent=2))
