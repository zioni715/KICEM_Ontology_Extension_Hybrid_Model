#!/usr/bin/env python3
"""Create a two-reviewer/adjudication packet without inventing gold labels."""
from __future__ import annotations

import json
from pathlib import Path

from build import PARENT_OVERRIDES, RENAMES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DECISIONS = ROOT / "test2/module5/outputs/decisions.json"


def prepare() -> dict:
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    items = []
    for decision in decisions:
        old_id = decision["query"]["id"]
        class_id = RENAMES.get(old_id, old_id)
        proposed_parent = decision.get("parent")
        if proposed_parent:
            proposed_parent = RENAMES.get(proposed_parent, proposed_parent)
        proposed_parent = PARENT_OVERRIDES.get(class_id, proposed_parent)
        items.append({
            "candidate_id": class_id,
            "label": decision["query"]["label"],
            "definition": decision["query"]["definition"],
            "proposed_parent": proposed_parent,
            "evidence": decision.get("export_verified_quotes", []),
            "reviewer_1": {"reviewer_id": None, "accept": None,
                           "correct_parent": None, "notes": None},
            "reviewer_2": {"reviewer_id": None, "accept": None,
                           "correct_parent": None, "notes": None},
            "adjudication": {"adjudicator_id": None, "accept": None,
                             "correct_parent": None, "notes": None},
        })
    packet = {
        "protocol": "Two independent construction-domain reviewers, then adjudication",
        "instructions": [
            "Decide whether the candidate is a valid T-Box class supported by the cited source.",
            "If accepted, give its most specific direct named parent; do not score part-of as is-a.",
            "Reviewers fill their own section independently before seeing the other review.",
            "Adjudication is required for every candidate and is the only gold used for metrics.",
        ],
        "candidate_count": len(items),
        "items": items,
    }
    output = HERE / "reports/expert_review.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.exists():
        output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print(f"Expert review packet: {output} ({len(items)} candidates)")
    return packet


if __name__ == "__main__":
    prepare()
