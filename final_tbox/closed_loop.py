#!/usr/bin/env python3
"""Iterate build/evaluate/validate until two complete cycles are stable.

This is a release-time closed loop, not a new learning model. Each cycle
rebuilds from trusted inputs, runs independent validators and compares the
resulting artifact/decision fingerprint with the previous passing cycle.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from audit_environment import audit
from build import build
from evaluate import evaluate
from mutation_tests import run as run_mutation_tests
from release_gate import decide
from semantic_validate import validate_semantics
from validate import validate


HERE = Path(__file__).resolve().parent
REFERENCE = HERE / "internal_semantic_reference.json"


def fingerprint(manifest, validation, mutation, evaluation, semantic) -> dict:
    return {
        "output_sha256": manifest["output_sha256"],
        "class_count": manifest["named_classes"],
        "technical_checks": [validation["checks_total"], validation["checks_failed"]],
        "mutation_controls": [mutation["case_count"], mutation["passed"]],
        "candidate_confusion": semantic["candidate_metrics"],
        "competency_questions": [semantic["competency_questions"]["passed"],
                                 semantic["competency_questions"]["total"]],
        "evidence": [evaluation["evidence"]["exact_source_matches"],
                     evaluation["evidence"]["citations"]],
        "taxonomy": evaluation["taxonomy"],
    }


def run_closed_loop(max_cycles: int = 3, stable_cycles_required: int = 2) -> dict:
    if max_cycles < stable_cycles_required or stable_cycles_required < 2:
        raise ValueError("Closed loop requires at least two stable cycles")
    cycles = []
    previous = None
    stable_count = 0
    converged = False
    for number in range(1, max_cycles + 1):
        manifest = build()
        validation = validate()
        mutation = run_mutation_tests()
        evaluation = evaluate()
        semantic = validate_semantics()
        environment = audit()
        gate = decide()

        reference_not_builder_input = all(
            not path.endswith(REFERENCE.name) for path in manifest["input_sha256"])
        passed = all((
            validation["technical_validation_passed"], mutation["passed"],
            evaluation["evidence"]["all_exact"],
            evaluation["reproducibility"]["two_consecutive_build_hashes_equal"],
            semantic["passed"], reference_not_builder_input,
        ))
        current = fingerprint(manifest, validation, mutation, evaluation, semantic)
        stable_with_previous = passed and previous == current
        stable_count = stable_count + 1 if stable_with_previous else 1 if passed else 0
        cycle = {
            "cycle": number,
            "passed": passed,
            "stable_with_previous": stable_with_previous,
            "stable_run_length": stable_count,
            "reference_not_builder_input": reference_not_builder_input,
            "fingerprint": current,
            "release_status": gate["status"],
            "external_environment_ready": environment["exact_full_pipeline_rerun_ready"],
            "deterministic_transformations": {
                "identifier_renames": manifest["identifier_renames"],
                "parent_overrides": manifest["parent_overrides"],
                "excluded_seed_entities": len(manifest["excluded_seed_entities"]),
                "removed_seed_axioms": len(manifest["removed_seed_axioms"]),
            },
        }
        cycles.append(cycle)
        previous = current
        print(f"closed-loop cycle={number} passed={passed} stable={stable_count}/"
              f"{stable_cycles_required}", flush=True)
        if stable_count >= stable_cycles_required:
            converged = True
            break

    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "CONVERGED" if converged else "NOT_CONVERGED",
        "converged": converged,
        "cycles_executed": len(cycles),
        "stable_cycles_required": stable_cycles_required,
        "cycles": cycles,
        "scope": "release-time iterative self-validation; no online model self-training",
        "external_gates_are_not_auto_repaired": [
            "independent external expert adjudication",
            "GPU/locked-environment full Module1-5 rerun",
        ],
    }
    reports = HERE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "closed_loop.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not converged:
        raise SystemExit("Closed-loop validation did not converge")
    return report


if __name__ == "__main__":
    result = run_closed_loop()
    print(json.dumps({"status": result["status"],
                      "cycles_executed": result["cycles_executed"],
                      "stable_cycles_required": result["stable_cycles_required"]},
                     ensure_ascii=False, indent=2))
