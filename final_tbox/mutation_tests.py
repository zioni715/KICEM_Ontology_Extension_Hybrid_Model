#!/usr/bin/env python3
"""Verify that release gates reject representative bad ontologies."""
from __future__ import annotations

import json
from pathlib import Path

from rdflib import BNode, Graph, Literal, OWL, RDF, RDFS

from quality import E, inspect_tbox


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = HERE / "outputs/tile_tbox_final.ttl"
DECISIONS = ROOT / "test2/module5/outputs/decisions.json"


def clone(graph: Graph) -> Graph:
    copy = Graph()
    for triple in graph:
        copy.add(triple)
    return copy


def run() -> dict:
    graph = Graph().parse(SOURCE)
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    if inspect_tbox(graph, decisions):
        raise AssertionError("Baseline release already violates quality invariants")

    cases = []

    def case(name, expected_code, mutate):
        candidate = clone(graph)
        mutate(candidate)
        found = {x["code"] for x in inspect_tbox(candidate, decisions)}
        cases.append({"case": name, "expected_violation": expected_code,
                      "detected": expected_code in found,
                      "all_detected_violations": sorted(found)})

    case("A-Box class assertion", "ABOX_ASSERTION",
         lambda g: g.add((E.badIndividual, RDF.type, E.WorkTask)))
    case("Named class cycle", "CLASS_CYCLE",
         lambda g: g.add((E.CostItem, RDFS.subClassOf, E.TileMaterialCostItem)))
    case("Held candidate leak", "HELD_CANDIDATE_EXPORTED",
         lambda g: g.add((E.TilePreparation, RDF.type, OWL.Class)))
    case("Accepted evidence removed", "EVIDENCE_MISMATCH",
         lambda g: g.remove((E.CeramicTileCostItem, E.evidenceSourceId, None)))
    case("RC-only class leak", "RC_ONLY_CLASS",
         lambda g: g.add((E.RebarCostItem, RDF.type, OWL.Class)))

    def add_nominal(g):
        restriction = BNode()
        g.add((E.CostItem, RDFS.subClassOf, restriction))
        g.add((restriction, RDF.type, OWL.Restriction))
        g.add((restriction, OWL.onProperty, E.belongsToWorkCategory))
        g.add((restriction, OWL.hasValue, E.TileWork))

    case("Nominal/A-Box dependency", "NOMINAL", add_nominal)
    result = {"passed": all(x["detected"] for x in cases),
              "cases": cases, "case_count": len(cases)}
    reports = HERE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "mutation_tests.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit("At least one mutation escaped the release gate")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
