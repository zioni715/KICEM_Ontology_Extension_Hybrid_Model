#!/usr/bin/env python3
"""Build three independent, evidence-grounded, pure T-Box extensions."""
from __future__ import annotations

import hashlib
import json
import re
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

PREDICTOR_VERSION = "lexical-taxonomic-v1"
RELEASE_VERSION = "3.1.0"


def identifier_tokens(identifier: str) -> list[str]:
    return re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|[0-9]+", identifier)


def compact(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def infer_direct_parent(record: dict, case: dict) -> tuple[str, str]:
    """Predict one is-a parent without reading the validation gold.

    Rules are trade-agnostic: prefer the most specific lexical candidate parent,
    then a lifecycle anchor, and finally one of the common upper T-Box classes.
    """
    class_id = record["id"]
    root_id = case["trade_root_id"]
    candidates = case["candidates"]
    if class_id == root_id:
        return "ConstructionTask", "trade-root"

    other = [item for item in candidates if item["id"] != class_id]
    suffix = [item for item in other if class_id.endswith(item["id"])]
    if class_id.startswith("Improved"):
        # Improved method variants and their base method are siblings under the
        # location/activity parent, not an automatic is-a chain.
        suffix = [item for item in suffix if "Improved" + item["id"] != class_id]
    if suffix:
        parent = max(suffix, key=lambda item: len(item["id"]))
        return parent["id"], "identifier-suffix"

    label = compact(record["label"])
    label_parents = [
        item for item in other
        if "And" not in identifier_tokens(class_id)
        and len(compact(item["label"])) >= 4
        and compact(item["label"]) in label
    ]
    if label_parents:
        parent = max(label_parents, key=lambda item: len(compact(item["label"])))
        return parent["id"], "label-containment"

    if class_id.endswith("Mounting"):
        installation = class_id.removesuffix("Mounting") + "Installation"
        if any(item["id"] == installation for item in other):
            return installation, "lifecycle-rewrite"

    tokens = set(identifier_tokens(class_id)) - {"And"}
    composites = []
    for item in other:
        item_tokens = set(identifier_tokens(item["id"])) - {"And"}
        if "And" in identifier_tokens(item["id"]) and tokens < item_tokens:
            composites.append(item)
    if composites:
        parent = min(composites, key=lambda item: len(identifier_tokens(item["id"])))
        return parent["id"], "composite-lifecycle-parent"

    content = class_id + " " + record["label"] + " " + record["definition"]
    if any(term in class_id + " " + record["label"] for term in (
        "Preparation", "Survey", "측량", "준비",
    )):
        return "PreparationTask", "upper-tbox-lifecycle"

    inspection_terms = ("Inspection", "Test", "Control", "검사", "시험", "관리", "확인")
    if any(term in content for term in inspection_terms):
        root_prefix = root_id.removesuffix("Work")
        anchors = [
            item for item in other
            if item["id"].endswith("Inspection")
            and (set(identifier_tokens(item["id"])) & tokens)
        ]
        if anchors and class_id != root_prefix + "Inspection":
            return min(anchors, key=lambda item: len(item["id"]))["id"], "inspection-anchor"
        return "InspectionTask", "upper-tbox-lifecycle"

    root_prefix = root_id.removesuffix("Work")
    if class_id == root_prefix + "Installation":
        return root_id, "trade-operation-anchor"

    if any(term in content for term in (
        "Protection", "Cleaning", "Backfilling", "Compaction",
        "보양", "청소", "되메우", "다짐",
    )):
        return "FinishingTask", "upper-tbox-lifecycle"
    if any(term in content for term in (
        "Installation", "Construction", "Mounting", "Wiring",
        "설치", "시공", "부착", "붙이기", "접합", "전원", "배선",
    )):
        return "InstallationTask", "upper-tbox-lifecycle"
    return "ConstructionTask", "upper-tbox-fallback"


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
    graph.add((ontology_iri, OWL.versionInfo, Literal(RELEASE_VERSION)))
    for prop, label in (("evidenceSourceId", "근거 출처 식별자"),
                        ("evidenceSection", "근거 조항"),
                        ("predictedDirectParent", "모델 예측 직접 부모"),
                        ("predictionMethod", "부모 예측 방법"),
                        ("validationStatus", "검증 상태")):
        graph.add((ns[prop], RDF.type, OWL.AnnotationProperty))
        graph.add((ns[prop], RDFS.label, Literal(label, lang="ko")))

    for class_id, (label, definition, parent) in BASE_CLASSES.items():
        add_class(graph, ns, class_id, label, definition, parent,
                  "SYSTEM-SCHEMA", "common upper T-Box")

    trade_root = case["trade_root_id"]
    candidate_ids = set()
    for record in case["candidates"]:
        class_id = record["id"]
        if class_id in candidate_ids or class_id in BASE_CLASSES:
            raise ValueError(f"Duplicate candidate identifier: {case['trade_id']}:{class_id}")
        candidate_ids.add(class_id)
        parent, rule = infer_direct_parent(record, case)
        add_class(graph, ns, class_id, record["label"], record["definition"], parent,
                  record["source_id"], record["section"])
        graph.add((ns[class_id], ns.predictedDirectParent, ns[parent]))
        graph.add((ns[class_id], ns.predictionMethod, Literal(f"{PREDICTOR_VERSION}:{rule}")))
        # A generic task parent classifies the work type; this second T-Box edge
        # also keeps every domain candidate reachable below its trade root.
        if parent in BASE_CLASSES and class_id != trade_root:
            graph.add((ns[class_id], RDFS.subClassOf, ns[trade_root]))

    known = candidate_ids | set(BASE_CLASSES)
    predictions = {
        record["id"]: infer_direct_parent(record, case)[0]
        for record in case["candidates"]
    }
    dangling = [(class_id, parent) for class_id, parent in predictions.items() if parent not in known]
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
        "predictor_version": PREDICTOR_VERSION,
        "candidate_input_contains_parent": False,
        "outputs": {ttl.name: sha256(ttl), owl.name: sha256(owl)},
    }


def build_all() -> dict:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    cases = [build_case(case) for case in data["cases"]]
    manifest = {
        "release": RELEASE_VERSION,
        "scope": "three independent T-Box-only extension cases",
        "builder_reads_validation_gold": False,
        "candidate_input_contains_parent": False,
        "predictor_version": PREDICTOR_VERSION,
        "input_sha256": {str(INPUT.relative_to(HERE)): sha256(INPUT)},
        "cases": cases,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build_all(), ensure_ascii=False, indent=2))
