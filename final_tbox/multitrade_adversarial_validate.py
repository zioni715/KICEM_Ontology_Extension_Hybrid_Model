#!/usr/bin/env python3
"""Exhaustive candidate-level adversarial controls for multitrade T-Boxes."""
from __future__ import annotations

import datetime
import json
from collections import Counter
from pathlib import Path

import networkx as nx
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS, URIRef


HERE = Path(__file__).resolve().parent
CANDIDATES = HERE / "benchmarks/multitrade_candidates.json"
GOLD = HERE / "benchmarks/multitrade_gold.json"
OUT = HERE / "outputs/multitrade"
REPORT = HERE / "reports/multitrade_adversarial_validation.json"


def local(uri: URIRef) -> str:
    return str(uri).rsplit("#", 1)[-1]


def clone(graph: Graph) -> Graph:
    result = Graph()
    for triple in graph:
        result.add(triple)
    return result


def violations(graph: Graph, ns: Namespace, expected: dict[str, str],
               source_ids: set[str], trade_root: str,
               foreign_namespaces: set[str]) -> set[str]:
    found = set()
    classes = {item for item in graph.subjects(RDF.type, OWL.Class) if isinstance(item, URIRef)}
    ids = {local(item) for item in classes if str(item).startswith(str(ns))}
    characteristic_types = {OWL.FunctionalProperty, OWL.InverseFunctionalProperty,
                            OWL.TransitiveProperty, OWL.SymmetricProperty,
                            OWL.AsymmetricProperty, OWL.ReflexiveProperty,
                            OWL.IrreflexiveProperty}
    schema_types = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
                    OWL.AnnotationProperty, OWL.Ontology} | characteristic_types
    if any(obj not in schema_types for subject, obj in graph.subject_objects(RDF.type)
           if not str(subject).startswith("http://www.w3.org/")):
        found.add("ABOX")
    edges = [(local(child), local(parent)) for child, parent in graph.subject_objects(RDFS.subClassOf)
             if child in classes and parent in classes]
    hierarchy = nx.DiGraph(edges)
    if not nx.is_directed_acyclic_graph(hierarchy):
        found.add("CYCLE")
    for class_id, gold_parent in expected.items():
        uri = ns[class_id]
        if class_id not in ids:
            found.add(f"MISSING_CLASS:{class_id}")
        if graph.value(uri, RDFS.label) is None:
            found.add(f"MISSING_LABEL:{class_id}")
        if graph.value(uri, RDFS.comment) is None:
            found.add(f"MISSING_DEFINITION:{class_id}")
        source_values = {str(item) for item in graph.objects(uri, ns.evidenceSourceId)}
        if not source_values or not source_values <= source_ids:
            found.add(f"BAD_SOURCE:{class_id}")
        if not any(str(item).strip() for item in graph.objects(uri, ns.evidenceSection)):
            found.add(f"MISSING_SECTION:{class_id}")
        parents = [local(item) for item in graph.objects(uri, ns.predictedDirectParent)]
        if parents != [gold_parent]:
            found.add(f"BAD_PARENT:{class_id}")
        if class_id != trade_root and not (class_id in hierarchy and trade_root in hierarchy and
                                           nx.has_path(hierarchy, class_id, trade_root)):
            found.add(f"DETACHED_FROM_ROOT:{class_id}")
    if any(str(term).startswith(tuple(foreign_namespaces))
           for triple in graph for term in triple if isinstance(term, URIRef)):
        found.add("FOREIGN_TRADE_NAMESPACE")
    return found


def run() -> dict:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["cases"]
    namespaces = {case["trade_id"]: case["namespace"] for case in data["cases"]}
    controls = []
    positive = []

    def record(trade_id: str, mutation: str, target: str, expected_code: str,
               detected: set[str]) -> None:
        controls.append({"trade_id": trade_id, "mutation": mutation, "target": target,
                         "expected_violation": expected_code,
                         "passed": expected_code in detected})

    for case in data["cases"]:
        trade_id = case["trade_id"]
        ns = Namespace(case["namespace"])
        graph = Graph().parse(OUT / f"{trade_id}.ttl")
        expected = gold[trade_id]["expected"]
        root = case["trade_root_id"]
        sources = {source["source_id"] for source in case["sources"]}
        foreign = {value for key, value in namespaces.items() if key != trade_id}
        baseline = violations(graph, ns, expected, sources, root, foreign)
        positive.append({"trade_id": trade_id, "passed": not baseline,
                         "unexpected_violations": sorted(baseline)})

        for class_id, correct_parent in sorted(expected.items()):
            uri = ns[class_id]
            mutations = []

            missing_source = clone(graph)
            missing_source.remove((uri, ns.evidenceSourceId, None))
            mutations.append(("remove_evidence_source", f"BAD_SOURCE:{class_id}", missing_source))

            missing_section = clone(graph)
            missing_section.remove((uri, ns.evidenceSection, None))
            mutations.append(("remove_evidence_section", f"MISSING_SECTION:{class_id}", missing_section))

            missing_label = clone(graph)
            missing_label.remove((uri, RDFS.label, None))
            mutations.append(("remove_label", f"MISSING_LABEL:{class_id}", missing_label))

            missing_definition = clone(graph)
            missing_definition.remove((uri, RDFS.comment, None))
            mutations.append(("remove_definition", f"MISSING_DEFINITION:{class_id}", missing_definition))

            wrong_parent = clone(graph)
            wrong_parent.remove((uri, ns.predictedDirectParent, None))
            replacement = "WorkTask" if correct_parent != "WorkTask" else "InspectionTask"
            wrong_parent.add((uri, ns.predictedDirectParent, ns[replacement]))
            mutations.append(("replace_direct_parent", f"BAD_PARENT:{class_id}", wrong_parent))

            if class_id != root:
                detached = clone(graph)
                detached.remove((uri, RDFS.subClassOf, None))
                mutations.append(("detach_from_trade_root", f"DETACHED_FROM_ROOT:{class_id}", detached))

            for mutation_name, code, mutated in mutations:
                detected = violations(mutated, ns, expected, sources, root, foreign)
                record(trade_id, mutation_name, class_id, code, detected)

        first_id = sorted(expected)[0]
        abox = clone(graph)
        abox.add((ns.AdversarialIndividual, RDF.type, ns[first_id]))
        record(trade_id, "inject_abox", first_id, "ABOX",
               violations(abox, ns, expected, sources, root, foreign))

        cycle = clone(graph)
        child = first_id
        parent = expected[child]
        cycle.add((ns[parent], RDFS.subClassOf, ns[child]))
        record(trade_id, "inject_cycle", child, "CYCLE",
               violations(cycle, ns, expected, sources, root, foreign))

        foreign_graph = clone(graph)
        foreign_ns = Namespace(sorted(foreign)[0])
        foreign_graph.add((foreign_ns.ForeignLeak, RDF.type, OWL.Class))
        record(trade_id, "inject_foreign_trade_class", "ForeignLeak", "FOREIGN_TRADE_NAMESPACE",
               violations(foreign_graph, ns, expected, sources, root, foreign))

    failed = [item for item in controls if not item["passed"]]
    counts = Counter(item["mutation"] for item in controls)
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "PASSED" if not failed and all(item["passed"] for item in positive) else "FAILED",
        "positive_baselines": positive,
        "candidate_count": sum(len(case["expected"]) for case in gold.values()),
        "adversarial_controls": len(controls),
        "controls_passed": len(controls) - len(failed),
        "controls_failed": len(failed),
        "mutation_counts": dict(sorted(counts.items())),
        "failed_controls": failed,
        "coverage": [
            "every candidate evidence source", "every candidate evidence section",
            "every candidate label", "every candidate definition",
            "every candidate predicted direct parent", "every non-root candidate trade-root path",
            "A-Box injection per trade", "cycle injection per trade",
            "foreign-trade namespace injection per trade"
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "PASSED":
        raise SystemExit(f"Adversarial validation failed: {len(failed)} controls")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
