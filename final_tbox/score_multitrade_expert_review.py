#!/usr/bin/env python3
"""Score completed three-trade expert adjudication without inventing recall."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKET = HERE / "reports/multitrade_expert_review.json"
REPORT = HERE / "reports/multitrade_expert_score.json"


def complete_review(review: dict) -> bool:
    return (
        isinstance(review.get("is_valid_tbox_class"), bool)
        and isinstance(review.get("evidence_supports_class"), bool)
        and (not review["is_valid_tbox_class"] or bool(review.get("correct_parent")))
    )


def score() -> dict:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    identities_complete = all(packet["identities"].values())
    incomplete = []
    for item in packet["items"]:
        if not all(complete_review(item[key]) for key in ("reviewer_1", "reviewer_2", "adjudication")):
            incomplete.append(f"{item['trade_id']}:{item['candidate_id']}")

    if not identities_complete or incomplete:
        result = {
            "status": "PENDING_EXPERT_ADJUDICATION",
            "metrics": None,
            "identities_complete": identities_complete,
            "incomplete_count": len(incomplete),
            "incomplete_items": incomplete,
            "selection_recall": None,
            "selection_recall_reason": "Rejected/non-generated concepts are not included in this packet.",
        }
    else:
        items = packet["items"]
        valid = [item for item in items if item["adjudication"]["is_valid_tbox_class"]]
        evidence = [item for item in items if item["adjudication"]["evidence_supports_class"]]
        parent_correct = [
            item for item in valid
            if item["predicted_parent"] == item["adjudication"]["correct_parent"]
        ]
        reviewer_class_agreement = sum(
            item["reviewer_1"]["is_valid_tbox_class"] == item["reviewer_2"]["is_valid_tbox_class"]
            for item in items
        ) / len(items)
        result = {
            "status": "COMPLETE",
            "metrics": {
                "reviewed_candidates": len(items),
                "expert_valid_class_rate": len(valid) / len(items),
                "expert_evidence_support_rate": len(evidence) / len(items),
                "parent_accuracy_among_valid_classes": (
                    len(parent_correct) / len(valid) if valid else None
                ),
                "reviewer_raw_class_agreement": reviewer_class_agreement,
            },
            "selection_recall": None,
            "selection_recall_reason": "A separate missed-concept sampling study is required.",
        }
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(score(), ensure_ascii=False, indent=2))
