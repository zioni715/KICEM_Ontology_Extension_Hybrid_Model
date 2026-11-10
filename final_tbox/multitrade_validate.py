#!/usr/bin/env python3
"""Independent gold, structural, OWLAPI, HermiT and mutation validation."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import networkx as nx
import owlready2
from rdflib import Graph, Namespace, OWL, RDF, RDFS, URIRef
from rdflib.compare import isomorphic

from multitrade_build import BASE_CLASSES


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
CANDIDATES = HERE / "benchmarks/multitrade_candidates.json"
GOLD = HERE / "benchmarks/multitrade_gold.json"
OUT = HERE / "outputs/multitrade"
REPORT = HERE / "reports/multitrade_validation.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_validators(classes: Path) -> tuple[Path, Path]:
    runtime = HERE / ".runtime"
    java_override = os.environ.get("TBOX_JAVA")
    java_candidate = shutil.which("java")
    legacy_java = ROOT / "test/runtime/java/jdk-17.0.20.1+1-jre/bin/java"
    java = Path(java_override or java_candidate or legacy_java)
    javac_override = os.environ.get("TBOX_JAVAC")
    javac_candidate = shutil.which("javac")
    legacy_compiler = ROOT / "test2/runtime/owlapi/ecj-3.37.0.jar"
    jar = Path(owlready2.__file__).parent / "hermit/HermiT.jar"
    sources = [HERE / "validators/java/ValidateOntology.java",
               HERE / "validators/java/ValidateHermit.java"]
    for dependency in (java, jar, *sources):
        if not dependency.is_file():
            raise FileNotFoundError(f"Missing validation dependency: {dependency}")
    classes.mkdir(parents=True, exist_ok=True)
    if javac_override or javac_candidate:
        javac = Path(javac_override or javac_candidate)
        if not javac.is_file():
            raise FileNotFoundError(f"Missing Java compiler: {javac}")
        command = [str(javac), "-encoding", "UTF-8", "-source", "17", "-target", "17",
                   "-proc:none", "-cp", str(jar), "-d", str(classes),
                   *(str(source) for source in sources)]
    elif legacy_compiler.is_file():
        # Compatibility fallback for the original workstation. A fresh clone uses
        # the OpenJDK compiler declared in environment.yml.
        command = [str(java), "-jar", str(legacy_compiler), "-17", "-proc:none",
                   "-cp", str(jar), "-d", str(classes), *(str(source) for source in sources)]
    else:
        raise FileNotFoundError(
            "No Java 17 compiler found. Create the Conda environment from environment.yml "
            "or set TBOX_JAVAC and TBOX_JAVA."
        )
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if run.returncode:
        raise RuntimeError(run.stderr)
    return java, jar


def java_validate(java: Path, jar: Path, classes: Path, owl: Path, ttl: Path,
                  tmp: Path) -> dict:
    profile_path = tmp / f"{ttl.stem}-profile.json"
    hermit_path = tmp / f"{ttl.stem}-hermit.json"
    profile_cmd = [str(java), "-cp", f"{classes}:{jar}", "ValidateOntology",
                   str(owl), str(ttl), str(tmp / f"{ttl.stem}-roundtrip.owl"), str(profile_path)]
    profile_run = subprocess.run(profile_cmd, capture_output=True, text=True, timeout=120)
    if profile_run.returncode:
        raise RuntimeError(profile_run.stderr)
    hermit_cmd = [str(java), "-Xmx2048M", "-cp", f"{classes}:{jar}", "ValidateHermit",
                  str(owl), str(hermit_path)]
    hermit_run = subprocess.run(hermit_cmd, capture_output=True, text=True, timeout=180)
    if hermit_run.returncode:
        raise RuntimeError(hermit_run.stderr)
    return {
        "profile": json.loads(profile_path.read_text(encoding="utf-8")),
        "hermit": json.loads(hermit_path.read_text(encoding="utf-8")),
    }


def local(uri: URIRef) -> str:
    return str(uri).rsplit("#", 1)[-1]


def detect_violations(graph: Graph, ns: Namespace, expected_ids: set[str]) -> list[str]:
    violations = []
    classes = {item for item in graph.subjects(RDF.type, OWL.Class) if isinstance(item, URIRef)}
    characteristic_types = {OWL.FunctionalProperty, OWL.InverseFunctionalProperty,
                            OWL.TransitiveProperty, OWL.SymmetricProperty,
                            OWL.AsymmetricProperty, OWL.ReflexiveProperty,
                            OWL.IrreflexiveProperty}
    schema_types = {OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
                    OWL.AnnotationProperty, OWL.Ontology} | characteristic_types
    if any(obj not in schema_types for subject, obj in graph.subject_objects(RDF.type)
           if not str(subject).startswith("http://www.w3.org/")):
        violations.append("abox")
    edges = [(local(child), local(parent)) for child, parent in graph.subject_objects(RDFS.subClassOf)
             if child in classes and parent in classes]
    if not nx.is_directed_acyclic_graph(nx.DiGraph(edges)):
        violations.append("cycle")
    for class_id in expected_ids:
        uri = ns[class_id]
        if not list(graph.objects(uri, ns.evidenceSourceId)) or not list(graph.objects(uri, ns.evidenceSection)):
            violations.append(f"missing_evidence:{class_id}")
    return violations


def validate_all() -> dict:
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    builder_source = (HERE / "multitrade_build.py").read_text(encoding="utf-8").lower()
    builder_gold_separated = (
        manifest["builder_reads_validation_gold"] is False
        and "multitrade_gold.json" not in manifest["input_sha256"]
        and "multitrade_gold" not in builder_source
    )
    classes_dir = HERE / ".runtime/owlapi_classes"
    java, jar = compile_validators(classes_dir)
    results = []
    total_tp = total_fp = total_fn = 0
    mutation_results = []
    runtime_tmp = HERE / ".runtime"
    runtime_tmp.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="multitrade-", dir=runtime_tmp) as tmp_name:
        tmp = Path(tmp_name)
        for case in candidates["cases"]:
            trade_id = case["trade_id"]
            ns = Namespace(case["namespace"])
            ttl = OUT / f"{trade_id}.ttl"
            owl = OUT / f"{trade_id}.owl"
            turtle = Graph().parse(ttl)
            rdfxml = Graph().parse(owl)
            expected = gold["cases"][trade_id]["expected"]
            expected_edges = set(expected.items())
            actual_edges = {(local(child), local(parent))
                            for child, parent in turtle.subject_objects(ns.predictedDirectParent)
                            if local(child) in expected}
            tp = len(actual_edges & expected_edges)
            fp = len(actual_edges - expected_edges)
            fn = len(expected_edges - actual_edges)
            total_tp += tp
            total_fp += fp
            total_fn += fn
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            candidate_ids = set(expected)
            trade_root = case["candidates"][0][0]
            hierarchy_edges = [(local(child), local(parent))
                               for child, parent in turtle.subject_objects(RDFS.subClassOf)
                               if isinstance(child, URIRef) and isinstance(parent, URIRef)]
            hierarchy = nx.DiGraph(hierarchy_edges)
            all_reachable = all(class_id == trade_root or
                                (class_id in hierarchy and trade_root in hierarchy and
                                 nx.has_path(hierarchy, class_id, trade_root))
                                for class_id in candidate_ids)
            one_predicted_parent = all(
                len(list(turtle.objects(ns[class_id], ns.predictedDirectParent))) == 1
                for class_id in candidate_ids)
            sources = {source["source_id"] for source in case["sources"]}
            evidence_exact = all(
                str(turtle.value(ns[class_id], ns.evidenceSourceId)) in sources and
                bool(str(turtle.value(ns[class_id], ns.evidenceSection) or "").strip())
                for class_id in candidate_ids)
            violations = detect_violations(turtle, ns, candidate_ids)
            class_uris = {item for item in turtle.subjects(RDF.type, OWL.Class)
                          if isinstance(item, URIRef)}
            labels_complete = all(turtle.value(item, RDFS.label) is not None and
                                  turtle.value(item, RDFS.comment) is not None for item in class_uris)
            java_result = java_validate(java, jar, classes_dir, owl, ttl, tmp)
            profile = java_result["profile"]
            hermit = java_result["hermit"]
            checks = {
                "serializations_isomorphic": isomorphic(turtle, rdfxml),
                "manifest_hashes_match": next(x for x in manifest["cases"] if x["trade_id"] == trade_id)["outputs"] == {
                    ttl.name: sha256(ttl), owl.name: sha256(owl)},
                "pure_tbox_acyclic_and_grounded": not violations,
                "labels_and_definitions_complete": labels_complete,
                "evidence_sources_exact": evidence_exact,
                "gold_candidate_set_exact": set(local(item) for item in class_uris) == candidate_ids | set(BASE_CLASSES),
                "gold_parent_edges_exact": fp == 0 and fn == 0,
                "exactly_one_predicted_direct_parent": one_predicted_parent,
                "all_candidates_reachable_from_trade_root": all_reachable,
                "owl2_dl_profile": profile["owl2_dl_profile"]["in_profile"],
                "owlapi_serialization_equivalence": profile["serialization_validation"]["rdfxml_vs_turtle"]["passed"],
                "hermit_consistent": hermit["consistent"] is True,
                "hermit_all_named_classes_satisfiable": hermit["unsatisfiable_named_classes"] == [],
            }

            # Three negative controls per trade: each defect must be detected.
            abox = Graph()
            for triple in turtle:
                abox.add(triple)
            abox.add((ns.MutationIndividual, RDF.type, ns[sorted(candidate_ids)[0]]))
            cycle = Graph()
            for triple in turtle:
                cycle.add(triple)
            first_child, first_parent = sorted(expected_edges)[0]
            cycle.add((ns[first_parent], RDFS.subClassOf, ns[first_child]))
            missing = Graph()
            for triple in turtle:
                missing.add(triple)
            missing.remove((ns[first_child], ns.evidenceSourceId, None))
            for mutation, graph, expected_code in (("abox_injection", abox, "abox"),
                                                   ("hierarchy_cycle", cycle, "cycle"),
                                                   ("evidence_removal", missing, f"missing_evidence:{first_child}")):
                found = detect_violations(graph, ns, candidate_ids)
                mutation_results.append({"trade_id": trade_id, "mutation": mutation,
                                         "passed": expected_code in found, "detected": found})
            results.append({
                "trade_id": trade_id,
                "trade_label": case["trade_label"],
                "candidate_count": len(candidate_ids),
                "total_class_count": len(class_uris),
                "taxonomy": {"tp": tp, "fp": fp, "fn": fn,
                             "precision": precision, "recall": recall, "f1": f1},
                "competency_questions": {"passed": tp, "total": len(expected_edges)},
                "checks": checks,
                "passed": all(checks.values()),
                "reasoner": {"name": hermit.get("reasoner_name"),
                             "consistent": hermit["consistent"],
                             "unsatisfiable_named_classes": hermit["unsatisfiable_named_classes"]},
            })
    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = (2 * micro_precision * micro_recall / (micro_precision + micro_recall)
                if micro_precision + micro_recall else 0.0)
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "PASSED" if all(item["passed"] for item in results) and
                  all(item["passed"] for item in mutation_results) else "FAILED",
        "builder_gold_separation_verified": builder_gold_separated,
        "builder_sha256": sha256(HERE / "multitrade_build.py"),
        "trade_count": len(results),
        "candidate_count": sum(item["candidate_count"] for item in results),
        "aggregate_taxonomy": {"tp": total_tp, "fp": total_fp, "fn": total_fn,
                               "precision": micro_precision, "recall": micro_recall, "micro_f1": micro_f1},
        "competency_questions": {"passed": total_tp, "total": total_tp + total_fn},
        "mutation_controls": {"passed": sum(item["passed"] for item in mutation_results),
                              "total": len(mutation_results), "cases": mutation_results},
        "trades": results,
        "interpretation": (
            "This validates T-Box export, evidence grounding and benchmark parent placement on three "
            "bounded cases. Gold agreement is not an estimate of unseen-domain generalization."
        ),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "PASSED" or not report["builder_gold_separation_verified"]:
        raise SystemExit("Multitrade validation failed")
    return report


if __name__ == "__main__":
    print(json.dumps(validate_all(), ensure_ascii=False, indent=2))
