#!/usr/bin/env python3
"""Prepare a blindable expert-review packet for all three trade T-Boxes."""
from __future__ import annotations

import json
from pathlib import Path

from rdflib import Graph, Namespace


HERE = Path(__file__).resolve().parent
CANDIDATES = HERE / "benchmarks/multitrade_candidates.json"
OUT = HERE / "outputs/multitrade"
PACKET = HERE / "reports/multitrade_expert_review.json"


def prepare() -> dict:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    items = []
    for case in data["cases"]:
        namespace = Namespace(case["namespace"])
        graph = Graph().parse(OUT / f"{case['trade_id']}.ttl")
        for record in case["candidates"]:
            uri = namespace[record["id"]]
            parent = graph.value(uri, namespace.predictedDirectParent)
            method = graph.value(uri, namespace.predictionMethod)
            blank_review = {
                "is_valid_tbox_class": None,
                "evidence_supports_class": None,
                "correct_parent": None,
                "notes": "",
            }
            items.append({
                "trade_id": case["trade_id"],
                "trade_label": case["trade_label"],
                "candidate_id": record["id"],
                "label": record["label"],
                "definition": record["definition"],
                "evidence_source_id": record["source_id"],
                "evidence_section": record["section"],
                "predicted_parent": str(parent).rsplit("#", 1)[-1],
                "prediction_method": str(method),
                "reviewer_1": dict(blank_review),
                "reviewer_2": dict(blank_review),
                "adjudication": dict(blank_review),
            })
    packet = {
        "protocol_version": "1.0",
        "scope": "three-trade independent semantic review",
        "identities": {"reviewer_1": "", "reviewer_2": "", "adjudicator": ""},
        "instructions": (
            "Reviewers work independently. Judge class validity, evidence support, and the most "
            "specific is-a parent. Do not treat part-of as subClassOf. The adjudicator resolves all items."
        ),
        "item_count": len(items),
        "items": items,
    }
    PACKET.parent.mkdir(parents=True, exist_ok=True)
    PACKET.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return packet


if __name__ == "__main__":
    result = prepare()
    print(f"Prepared {result['item_count']} expert-review items: {PACKET}")
