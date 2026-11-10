#!/usr/bin/env python3
"""Score the model only after all expert adjudications are complete."""
from __future__ import annotations

import json
from pathlib import Path

from build import PARENT_OVERRIDES, RENAMES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACKET = HERE / "reports/expert_review.json"
DECISIONS = ROOT / "test2/module5/outputs/decisions.json"


def score() -> dict:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    predicted = {}
    for decision in decisions:
        class_id = RENAMES.get(decision["query"]["id"], decision["query"]["id"])
        parent = decision.get("parent")
        if parent:
            parent = RENAMES.get(parent, parent)
        predicted[class_id] = {
            "accept": decision["status"] == "accepted_provisional",
            "parent": PARENT_OVERRIDES.get(class_id, parent),
        }
    incomplete = [x["candidate_id"] for x in packet["items"]
                  if not isinstance(x["adjudication"].get("accept"), bool) or
                  (x["adjudication"].get("accept") and
                   not x["adjudication"].get("correct_parent"))]
    if incomplete:
        result = {"status": "PENDING_EXPERT_ADJUDICATION", "metrics": None,
                  "incomplete_count": len(incomplete), "incomplete_candidates": incomplete}
    else:
        tp = fp = fn = tn = parent_correct = 0
        for item in packet["items"]:
            gold = item["adjudication"]
            pred = predicted[item["candidate_id"]]
            if pred["accept"] and gold["accept"]:
                tp += 1
                parent_correct += pred["parent"] == gold["correct_parent"]
            elif pred["accept"]:
                fp += 1
            elif gold["accept"]:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        result = {
            "status": "COMPLETE",
            "metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                        "precision": precision, "recall": recall,
                        "f1": 2 * precision * recall / (precision + recall)
                              if precision + recall else 0.0,
                        "accepted_parent_accuracy": parent_correct / tp if tp else 0.0},
        }
    output = HERE / "reports/expert_score.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    score()
