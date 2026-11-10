#!/usr/bin/env python3
"""Fail-closed structural, lineage, profile and reasoner validation."""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import networkx as nx
import owlready2
from rdflib import BNode, Graph, Namespace, OWL, RDF, RDFS, URIRef
from rdflib.compare import isomorphic

from quality import inspect_tbox


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
REPORTS = HERE / "reports"
TTL = OUT / "tile_tbox_final.ttl"
OWL_FILE = OUT / "tile_tbox_final.owl"
MANIFEST = OUT / "manifest.json"
DECISIONS = ROOT / "test2/module5/outputs/decisions.json"
GROUNDING = ROOT / "test2/module5/reports/grounding_rules.json"
HIERARCHY = ROOT / "test2/reports/hierarchy_metrics.json"
E = Namespace("https://example.org/kicem/tile/final#")

RENAMED_ACCEPTED = {
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local(uri: URIRef) -> str:
    return str(uri).split("#")[-1]


def compile_java(java: Path, compiler: Path, jar: Path, classes: Path,
                 sources: list[Path]) -> list[dict]:
    classes.mkdir(parents=True, exist_ok=True)
    command = [str(java), "-jar", str(compiler), "-17", "-proc:none",
               "-cp", str(jar), "-d", str(classes), *(str(x) for x in sources)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    record = {"command": command, "returncode": run.returncode,
              "stdout": run.stdout, "stderr": run.stderr}
    if run.returncode:
        raise RuntimeError(json.dumps(record, ensure_ascii=False))
    return [record]


def java_validations() -> tuple[dict, dict, list[dict]]:
    runtime = ROOT / "test2/runtime/owlapi"
    java = ROOT / "test/runtime/java/jdk-17.0.20.1+1-jre/bin/java"
    compiler = runtime / "ecj-3.37.0.jar"
    jar = Path(owlready2.__file__).parent / "hermit/HermiT.jar"
    validate_ontology = ROOT / "test2/evaluation/owlapi/ValidateOntology.java"
    validate_hermit = ROOT / "test2/evaluation/owlapi/ValidateHermit.java"
    for dependency in (java, compiler, jar, validate_ontology, validate_hermit):
        if not dependency.is_file():
            raise FileNotFoundError(f"Missing local validation dependency: {dependency}")

    classes = runtime / "final_tbox_classes"
    logs = compile_java(java, compiler, jar, classes, [validate_ontology, validate_hermit])
    with tempfile.TemporaryDirectory(prefix="final-tbox-", dir=runtime) as tmp_name:
        tmp = Path(tmp_name)
        profile_json = tmp / "profile.json"
        profile_command = [str(java), "-cp", f"{classes}:{jar}", "ValidateOntology",
                           str(OWL_FILE), str(TTL), str(tmp / "roundtrip.owl"),
                           str(profile_json)]
        profile_run = subprocess.run(profile_command, capture_output=True, text=True,
                                     timeout=120)
        logs.append({"command": profile_command, "returncode": profile_run.returncode,
                     "stdout": profile_run.stdout, "stderr": profile_run.stderr})
        if profile_run.returncode or not profile_json.exists():
            raise RuntimeError("OWLAPI validation failed")
        profile = json.loads(profile_json.read_text(encoding="utf-8"))

        hermit_json = tmp / "hermit.json"
        hermit_command = [str(java), "-Xmx2048M", "-cp", f"{classes}:{jar}",
                          "ValidateHermit", str(OWL_FILE), str(hermit_json)]
        hermit_run = subprocess.run(hermit_command, capture_output=True, text=True,
                                    timeout=180)
        logs.append({"command": hermit_command, "returncode": hermit_run.returncode,
                     "stdout": hermit_run.stdout, "stderr": hermit_run.stderr})
        if hermit_run.returncode or not hermit_json.exists():
            raise RuntimeError("HermiT validation failed")
        hermit = json.loads(hermit_json.read_text(encoding="utf-8"))
    return profile, hermit, logs


def validate() -> dict:
    for path in (TTL, OWL_FILE, MANIFEST, DECISIONS, GROUNDING, HIERARCHY):
        if not path.is_file():
            raise FileNotFoundError(f"Required validation input missing: {path}")
    turtle = Graph().parse(TTL)
    rdfxml = Graph().parse(OWL_FILE)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    hierarchy = json.loads(HIERARCHY.read_text(encoding="utf-8"))
    checks: list[dict] = []

    def check(name: str, passed: bool, **detail) -> None:
        checks.append({"check": name, "passed": bool(passed), **detail})

    check("Turtle and RDF/XML are isomorphic", isomorphic(turtle, rdfxml))
    check("Manifest hashes match release files",
          manifest["output_sha256"] == {TTL.name: sha256(TTL), OWL_FILE.name: sha256(OWL_FILE)})

    classes = {x for x in turtle.subjects(RDF.type, OWL.Class) if isinstance(x, URIRef)}
    object_properties = set(turtle.subjects(RDF.type, OWL.ObjectProperty))
    datatype_properties = set(turtle.subjects(RDF.type, OWL.DatatypeProperty))
    schema_entities = classes | object_properties | datatype_properties | set(
        turtle.subjects(RDF.type, OWL.AnnotationProperty))
    characteristic_types = {
        OWL.FunctionalProperty, OWL.InverseFunctionalProperty, OWL.TransitiveProperty,
        OWL.SymmetricProperty, OWL.AsymmetricProperty, OWL.ReflexiveProperty,
        OWL.IrreflexiveProperty,
    }
    abox_assertions = []
    for subject, obj in turtle.subject_objects(RDF.type):
        if isinstance(subject, BNode):
            continue
        if obj in ({OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty,
                    OWL.AnnotationProperty, OWL.Ontology} | characteristic_types):
            continue
        abox_assertions.append((str(subject), str(obj)))
    check("No named A-Box class assertions", not abox_assertions,
          violations=abox_assertions[:20])
    check("No owl:NamedIndividual declarations",
          not list(turtle.subjects(RDF.type, OWL.NamedIndividual)))
    check("No nominals (hasValue/oneOf)",
          not list(turtle.triples((None, OWL.hasValue, None))) and
          not list(turtle.triples((None, OWL.oneOf, None))))
    check("No pilot namespace remains",
          not any(str(term).startswith("https://example.org/kicem/tile/test2")
                  for triple in turtle for term in triple if isinstance(term, URIRef)))
    check("Expected T-Box cardinalities",
          len(classes) == 40 and len(object_properties) == 20 and len(datatype_properties) == 26,
          classes=len(classes), object_properties=len(object_properties),
          datatype_properties=len(datatype_properties))

    named_edges = [(child, parent) for child, parent in turtle.subject_objects(RDFS.subClassOf)
                   if child in classes and parent in classes]
    hierarchy_graph = nx.DiGraph(named_edges)
    check("Named class hierarchy is acyclic", nx.is_directed_acyclic_graph(hierarchy_graph))
    check("All named subclass endpoints are declared classes",
          all(child in classes and parent in classes for child, parent in named_edges))
    check("Every named class has label and definition",
          all(turtle.value(c, RDFS.label) is not None and
              turtle.value(c, RDFS.comment) is not None for c in classes))
    check("RC-only classes are absent", not (RC_ONLY & {local(x) for x in classes}))

    accepted = [x for x in decisions if x["status"] == "accepted_provisional"]
    held = [x for x in decisions if x["status"] != "accepted_provisional"]
    accepted_ids = {RENAMED_ACCEPTED.get(x["query"]["id"], x["query"]["id"])
                    for x in accepted}
    held_ids = {RENAMED_ACCEPTED.get(x["query"]["id"], x["query"]["id"])
                for x in held}
    actual_ids = {local(x) for x in classes}
    check("All and only accepted candidate classes exported",
          accepted_ids <= actual_ids and not (held_ids & actual_ids),
          accepted=sorted(accepted_ids), held_leaks=sorted(held_ids & actual_ids))
    check("Every accepted candidate has final evidence",
          all(list(turtle.objects(E[cid], E.evidenceSourceId)) for cid in accepted_ids))
    check("Wall tile installation has the specific installation parent",
          (E.WallTileInstallation, RDFS.subClassOf, E.TileInstallation) in turtle)
    check("Pressure-bonding identifiers are semantically aligned",
          not any("AdhesiveCostItem" in cid for cid in actual_ids) and
          len([cid for cid in actual_ids if "PressureBondingCostItem" in cid]) == 4)
    invariant_violations = inspect_tbox(turtle, decisions)
    check("Fail-closed release invariants", not invariant_violations,
          violations=invariant_violations)
    all_properties = object_properties | datatype_properties
    check("Every object/data property has label and definition",
          all(turtle.value(prop, RDFS.label) is not None and
              turtle.value(prop, RDFS.comment) is not None for prop in all_properties))

    before_hashes = {str(p.relative_to(ROOT)): sha256(p) for p in (TTL, OWL_FILE)}
    profile, hermit, execution = java_validations()
    after_hashes = {str(p.relative_to(ROOT)): sha256(p) for p in (TTL, OWL_FILE)}
    check("OWLAPI OWL 2 DL profile", profile["owl2_dl_profile"]["in_profile"],
          violations=profile["owl2_dl_profile"]["violations"])
    check("OWLAPI serialization equivalence",
          profile["serialization_validation"]["rdfxml_vs_turtle"]["passed"])
    check("OWLAPI validation controls pass", profile["controls"]["passed"])
    check("HermiT ontology consistency", hermit.get("consistent") is True,
          error=hermit.get("error"))
    check("HermiT reports no unsatisfiable named class",
          hermit.get("unsatisfiable_named_classes") == [],
          unsatisfiable=hermit.get("unsatisfiable_named_classes"))
    check("Validation did not mutate release inputs", before_hashes == after_hashes)

    failed = [item for item in checks if not item["passed"]]
    technical_pass = not failed
    semantic_reference_available = hierarchy.get("tile_extension_hierarchical_f1") is not None
    release_status = ("VALIDATED" if technical_pass and semantic_reference_available else
                      "TECHNICALLY_VALIDATED_SEMANTICALLY_PROVISIONAL" if technical_pass else
                      "FAILED")
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "release_status": release_status,
        "technical_validation_passed": technical_pass,
        "semantic_validation_passed": semantic_reference_available,
        "tbox_only": not abox_assertions,
        "checks_total": len(checks),
        "checks_failed": len(failed),
        "checks": checks,
        "expansion": {
            "retained_seed_classes": manifest["retained_seed_classes"],
            "foundation_classes_added": manifest["foundation_classes_added"],
            "candidate_classes_accepted": len(accepted),
            "candidate_classes_held": len(held),
            "accepted_with_evidence": sum(bool(list(turtle.objects(E[cid], E.evidenceSourceId)))
                                          for cid in accepted_ids),
            "candidate_acceptance_rate": len(accepted) / len(decisions),
        },
        "model_evaluation": {
            "rc_heldout_sample_count": hierarchy["sample_count"],
            "rc_parent_top1_accuracy": hierarchy["parent_accuracy"],
            "rc_hierarchical_micro_f1": hierarchy["hierarchical_micro"]["f1"],
            "tile_extension_hierarchical_f1": hierarchy["tile_extension_hierarchical_f1"],
            "warning": hierarchy["tile_not_evaluated_reason"],
        },
        "reasoner": hermit,
        "owlapi_summary": {
            "in_owl2_dl_profile": profile["owl2_dl_profile"]["in_profile"],
            "serialization_equivalent": profile["serialization_validation"]["rdfxml_vs_turtle"]["passed"],
            "controls_passed": profile["controls"]["passed"],
        },
        "input_hashes_before": before_hashes,
        "input_hashes_after": after_hashes,
        "execution": execution,
        "interpretation": (
            "T-Box purity, serialization, OWL 2 DL profile, consistency, class satisfiability, "
            "candidate gating and documentary evidence coverage passed. Independent expert-labelled "
            "tile hierarchy evaluation has not been supplied, so semantic quality is provisional."
        ),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not technical_pass:
        raise SystemExit(f"Final T-Box validation failed: {len(failed)} check(s)")
    return report


if __name__ == "__main__":
    result = validate()
    print(json.dumps({key: result[key] for key in (
        "release_status", "technical_validation_passed", "semantic_validation_passed",
        "tbox_only", "checks_total", "checks_failed", "expansion", "model_evaluation")},
        ensure_ascii=False, indent=2))
