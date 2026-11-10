#!/usr/bin/env python3
"""Combine artifact, experiment and expert gates into one release decision."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / "reports" / name).read_text(encoding="utf-8"))


def decide(require_closed_loop: bool = False) -> dict:
    validation = read("validation.json")
    mutation = read("mutation_tests.json")
    evaluation = read("evaluation.json")
    environment = read("environment_audit.json")
    expert = read("expert_score.json")
    internal_semantic = read("internal_semantic_validation.json")
    closed_loop_path = HERE / "reports/closed_loop.json"
    closed_loop = (json.loads(closed_loop_path.read_text(encoding="utf-8"))
                   if require_closed_loop and closed_loop_path.exists() else None)
    closed_loop_ready = bool(closed_loop and closed_loop.get("converged"))
    artifact_ready = all((
        validation["technical_validation_passed"],
        mutation["passed"],
        evaluation["evidence"]["all_exact"],
        evaluation["taxonomy"]["acyclic"],
        evaluation["reproducibility"]["two_consecutive_build_hashes_equal"],
    ))
    semantic_ready = expert["status"] == "COMPLETE"
    internal_semantic_ready = internal_semantic["passed"]
    experiment_rerun_ready = environment["exact_full_pipeline_rerun_ready"]
    if artifact_ready and semantic_ready and experiment_rerun_ready and (
            closed_loop_ready or not require_closed_loop):
        status = "FINAL_RESEARCH_RELEASE_READY"
    elif artifact_ready and internal_semantic_ready and closed_loop_ready:
        status = "FINAL_CLOSED_LOOP_VALIDATION_COMPLETE"
    elif artifact_ready and internal_semantic_ready:
        status = "FINAL_INTERNAL_VALIDATION_COMPLETE"
    elif artifact_ready:
        status = "ARTIFACT_VALIDATED_SEMANTIC_EVALUATION_PENDING"
    else:
        status = "RELEASE_BLOCKED"
    result = {
        "status": status,
        "artifact_release_ready": artifact_ready,
        "internal_semantic_validation_ready": internal_semantic_ready,
        "closed_loop_validation_ready": closed_loop_ready if require_closed_loop else None,
        "semantic_evaluation_ready": semantic_ready,
        "exact_experiment_rerun_ready": experiment_rerun_ready,
        "remaining_gates": [name for name, passed in (
            ("independent external expert adjudication", semantic_ready),
            ("original Module1-5 environment and GPU rerun", experiment_rerun_ready),
        ) if not passed],
        "rule": (
            "FINAL_CLOSED_LOOP_VALIDATION_COMPLETE requires artifact, source-grounded internal "
            "semantic validation and two stable closed-loop cycles. FINAL_RESEARCH_RELEASE_READY "
            "additionally requires independent expert adjudication and exact original-environment "
            "rerun readiness."
        ),
    }
    (HERE / "reports/release_gate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    decide()
