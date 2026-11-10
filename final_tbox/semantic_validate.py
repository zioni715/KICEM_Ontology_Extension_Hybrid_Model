#!/usr/bin/env python3
"""Validate all candidates and competency questions against internal reference."""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from rdflib import Graph, OWL, RDF, RDFS, XSD

from build import PARENT_OVERRIDES, RENAMES
from quality import E


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_semantics() -> dict:
    reference = read(HERE / "internal_semantic_reference.json")
    decisions = read(ROOT / "test2/module5/outputs/decisions.json")
    graph = Graph().parse(HERE / "outputs/tile_tbox_final.ttl")
    predictions = {}
    for decision in decisions:
        class_id = RENAMES.get(decision["query"]["id"], decision["query"]["id"])
        parent = decision.get("parent")
        if parent:
            parent = RENAMES.get(parent, parent)
        predictions[class_id] = {
            "accept": decision["status"] == "accepted_provisional",
            "parent": PARENT_OVERRIDES.get(class_id, parent),
        }

    tp = fp = fn = tn = parent_correct = 0
    candidate_results = []
    for gold in reference["items"]:
        pred = predictions[gold["candidate_id"]]
        if pred["accept"] and gold["accept"]:
            tp += 1
            parent_match = pred["parent"] == gold["parent"]
            parent_correct += parent_match
        elif pred["accept"]:
            fp += 1
            parent_match = None
        elif gold["accept"]:
            fn += 1
            parent_match = None
        else:
            tn += 1
            parent_match = None
        candidate_results.append({"candidate_id": gold["candidate_id"],
                                  "gold_accept": gold["accept"],
                                  "predicted_accept": pred["accept"],
                                  "gold_parent": gold["parent"],
                                  "predicted_parent": pred["parent"],
                                  "acceptance_match": pred["accept"] == gold["accept"],
                                  "parent_match": parent_match,
                                  "reason": gold["reason"]})
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    named_classes = set(graph.subjects(RDF.type, OWL.Class))
    edges = [(child, parent) for child, parent in graph.subject_objects(RDFS.subClassOf)
             if child in named_classes and parent in named_classes]
    hierarchy = nx.DiGraph(edges)
    data_properties = set(graph.subjects(RDF.type, OWL.DatatypeProperty))
    object_properties = set(graph.subjects(RDF.type, OWL.ObjectProperty))

    competency_questions = []

    def cq(identifier, question, passed):
        competency_questions.append({"id": identifier, "question": question,
                                     "passed": bool(passed)})

    cq("CQ01", "Material-specific tile costs are material cost items",
       all(nx.has_path(hierarchy, E[x], E.TileMaterialCostItem) for x in
           ("CeramicTileCostItem", "PorcelainTileCostItem", "MosaicTileCostItem",
            "NonSlipTileCostItem")))
    cq("CQ02", "Pressure-bonding costs are installation cost items",
       all(nx.has_path(hierarchy, E[x], E.TileInstallationCostItem) for x in
           ("StoneTilePressureBondingCostItem", "PorcelainTilePressureBondingCostItem",
            "CeramicTilePressureBondingCostItem", "MosaicTilePressureBondingCostItem")))
    cq("CQ03", "Wall tile installation is a tile installation and work task",
       nx.has_path(hierarchy, E.WallTileInstallation, E.TileInstallation) and
       nx.has_path(hierarchy, E.WallTileInstallation, E.WorkTask))
    cq("CQ04", "Cost objects and work activities are disjoint",
       (E.CostItem, OWL.disjointWith, E.WorkTask) in graph or
       (E.WorkTask, OWL.disjointWith, E.CostItem) in graph)
    cq("CQ05", "Five tile observation text properties target CostItem/string",
       all(prop in data_properties and (prop, RDFS.domain, E.CostItem) in graph and
           (prop, RDFS.range, XSD.string) in graph for prop in
           (E.tileMaterialText, E.tileSurfaceText, E.tileDimensionsText,
            E.tileThicknessText, E.tileMethodText)))
    cq("CQ06", "Work decomposition remains a WorkTask-to-WorkTask relation",
       E.partOfWorkTask in object_properties and
       (E.partOfWorkTask, RDFS.domain, E.WorkTask) in graph and
       (E.partOfWorkTask, RDFS.range, E.WorkTask) in graph and
       (E.partOfWorkTask, RDF.type, OWL.AsymmetricProperty) in graph and
       (E.partOfWorkTask, RDF.type, OWL.IrreflexiveProperty) in graph)
    cq("CQ07", "Cost-to-WBS linkage has CostItem/WorkTask signature",
       E.appliesToWBS in object_properties and
       (E.appliesToWBS, RDFS.domain, E.CostItem) in graph and
       (E.appliesToWBS, RDFS.range, E.WorkTask) in graph)
    cq("CQ08", "No rejected candidate is exported",
       all(E[x["candidate_id"]] not in named_classes for x in reference["items"]
           if not x["accept"]))
    cq("CQ09", "Every accepted candidate is exported with evidence",
       all(E[x["candidate_id"]] in named_classes and
           bool(list(graph.objects(E[x["candidate_id"]], E.evidenceSourceId)))
           for x in reference["items"] if x["accept"]))
    cq("CQ10", "Named hierarchy is acyclic", nx.is_directed_acyclic_graph(hierarchy))

    result = {
        "status": "INTERNAL_SEMANTIC_VALIDATION_COMPLETE",
        "passed": (fp == 0 and fn == 0 and parent_correct == tp and
                   all(x["passed"] for x in competency_questions)),
        "reference_kind": "source-grounded internal adjudication; not independent expert gold",
        "candidate_metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                              "precision": precision, "recall": recall,
                              "f1": 2 * precision * recall / (precision + recall)
                                    if precision + recall else 0.0,
                              "accepted_parent_accuracy": parent_correct / tp if tp else 0.0},
        "candidate_results": candidate_results,
        "competency_questions": {"passed": sum(x["passed"] for x in competency_questions),
                                 "total": len(competency_questions),
                                 "items": competency_questions},
        "limitations": [
            "Reference was created from the same supplied sources and is not independent.",
            "Perfect agreement measures conformance to explicit final rules, not generalisation.",
            "External domain-expert adjudication remains required for an independent accuracy claim."
        ]
    }
    output = HERE / "reports/internal_semantic_validation.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    if not result["passed"]:
        raise SystemExit("Internal semantic validation failed")
    print(json.dumps({"status": result["status"], "passed": result["passed"],
                      "candidate_metrics": result["candidate_metrics"],
                      "competency_questions": result["competency_questions"]},
                     ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    validate_semantics()
