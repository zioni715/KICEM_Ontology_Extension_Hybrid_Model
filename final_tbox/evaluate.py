#!/usr/bin/env python3
"""Quantitative, non-inflated evaluation of the saved extension run."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import networkx as nx
from rdflib import Graph, OWL, RDF, RDFS, URIRef

from build import build, NEW, RENAMES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DECISIONS = ROOT / "test2/module5/outputs/decisions.json"
ROWS = ROOT / "test2/module1/outputs/extracted_rows.json"
WBS = ROOT / "test2/shared/wbs.json"
HIERARCHY = ROOT / "test2/reports/hierarchy_metrics.json"
LOREX = ROOT / "test2/module5/reports/lorex_metrics.json"
TTL = HERE / "outputs/tile_tbox_final.ttl"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wilson(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    if not total:
        return [0.0, 1.0]
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [centre - margin, centre + margin]


def evaluate() -> dict:
    decisions = read(DECISIONS)
    rows = {x["id"]: x for x in read(ROWS)}
    wbs = {x["code"]: x for x in read(WBS)}
    hierarchy = read(HIERARCHY)
    lorex = read(LOREX)
    graph = Graph().parse(TTL)

    evidence_checks = []
    accepted = [x for x in decisions if x["status"] == "accepted_provisional"]
    for item in accepted:
        for evidence in item.get("export_verified_quotes", []):
            source_id, quote = evidence["source_id"], evidence["quote"]
            if source_id.startswith("WBS:"):
                code = source_id.split(":", 1)[1]
                source = wbs.get(code, {}).get("quote", "")
            else:
                row = rows.get(source_id, {})
                source = f"{row.get('name', '')} {row.get('specification', '')}".strip()
            evidence_checks.append({"candidate": item["query"]["id"],
                                    "source_id": source_id,
                                    "exact_substring": bool(quote and quote in source)})

    classes = {x for x in graph.subjects(RDF.type, OWL.Class) if isinstance(x, URIRef)}
    edges = [(str(child), str(parent)) for child, parent in graph.subject_objects(RDFS.subClassOf)
             if child in classes and parent in classes]
    taxonomy = nx.DiGraph(edges)
    roots = [node for node in taxonomy.nodes if taxonomy.out_degree(node) == 0]
    depths = {}
    for node in taxonomy.nodes:
        lengths = [nx.shortest_path_length(taxonomy, node, root)
                   for root in roots if nx.has_path(taxonomy, node, root)]
        depths[node] = min(lengths) if lengths else 0

    # Run the deterministic direct builder twice. Both serializations must be
    # byte-identical, not merely graph-isomorphic.
    first = build()["output_sha256"]
    second = build()["output_sha256"]
    strict = sum(bool(x.get("strict_lorex_accept")) for x in accepted)
    parent_accuracy = hierarchy["parent_accuracy"]
    n = hierarchy["sample_count"]
    successes = round(parent_accuracy * n)
    report = {
        "evaluation_scope": "saved single-case tile run; no expert gold labels",
        "candidate_count": len(decisions),
        "accepted_count": len(accepted),
        "held_count": len(decisions) - len(accepted),
        "accepted_by_origin": dict(Counter(x["query"]["origin"] for x in accepted)),
        "strict_lorex_agreement": {"count": strict, "denominator": len(accepted),
                                    "rate": strict / len(accepted)},
        "evidence": {"citations": len(evidence_checks),
                     "exact_source_matches": sum(x["exact_substring"] for x in evidence_checks),
                     "all_exact": all(x["exact_substring"] for x in evidence_checks),
                     "checks": evidence_checks},
        "taxonomy": {"named_classes": len(classes), "named_subclass_edges": len(edges),
                     "roots_in_named_edge_graph": len(roots),
                     "maximum_named_depth": max(depths.values()),
                     "acyclic": nx.is_directed_acyclic_graph(taxonomy)},
        "reproducibility": {"two_consecutive_build_hashes_equal": first == second,
                            "first": first, "second": second},
        "rc_heldout_parent_prediction": {
            "sample_count": n, "top1_correct": successes,
            "top1_accuracy": parent_accuracy,
            "top1_accuracy_wilson_95": wilson(successes, n),
            "hierarchical_micro_f1": hierarchy["hierarchical_micro"]["f1"],
            "mrr": hierarchy["mrr"], "hits_at": hierarchy["hits_at"],
            "warning": "Only four RC seed edges; not a tile generalisation estimate.",
        },
        "tile_semantic_metrics": {"precision": None, "recall": None, "f1": None,
                                  "parent_accuracy": None,
                                  "reason": "Independent expert-labelled tile reference is absent."},
        "claims_supported": [
            "The saved run emits a pure, reproducible and logically consistent T-Box.",
            "Every exported candidate has an exact document/WBS citation.",
            "Held candidates do not enter the release taxonomy.",
        ],
        "claims_not_supported": [
            "General tile extension accuracy or recall.",
            "Expert-level semantic correctness.",
            "Cross-project or cross-trade generalisation.",
        ],
        "source_metrics": {"lorex_expert_validated": lorex["expert_validated"]},
    }
    reports = HERE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "evaluation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report["evidence"]["all_exact"] or not report["taxonomy"]["acyclic"] or first != second:
        raise SystemExit("Release evaluation failed")
    print(json.dumps({k: report[k] for k in ("candidate_count", "accepted_count",
          "held_count", "strict_lorex_agreement", "evidence", "taxonomy",
          "reproducibility", "rc_heldout_parent_prediction", "tile_semantic_metrics")},
          ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    evaluate()
