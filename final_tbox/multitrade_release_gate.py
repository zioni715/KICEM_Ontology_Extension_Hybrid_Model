#!/usr/bin/env python3
"""Issue one conservative release decision for the three-trade T-Box artifacts."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
OUTPUT = REPORTS / "multitrade_release_gate.json"


def read(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def artifact_hashes() -> dict[str, str]:
    output = HERE / "outputs/multitrade"
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.glob("*.*"))
        if path.suffix in {".ttl", ".owl"}
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decide(require_stress: bool = True) -> dict:
    validation = read("multitrade_validation.json")
    closed_loop = read("multitrade_closed_loop.json")
    adversarial = read("multitrade_adversarial_validation.json")
    unit_tests = read("multitrade_unit_tests.json")
    dependency_audit = read("dependency_audit.json")
    stress = read("multitrade_stress_validation.json") if require_stress else None
    manifest = json.loads((HERE / "outputs/multitrade/manifest.json").read_text(encoding="utf-8"))
    expert_path = REPORTS / "multitrade_expert_score.json"
    expert = json.loads(expert_path.read_text(encoding="utf-8")) if expert_path.exists() else {
        "status": "NOT_PREPARED"
    }

    checks = {
        "three_trades_validated": validation.get("trade_count") == 3,
        "bounded_gold_agreement_passed": validation.get("status") == "PASSED",
        "builder_gold_separated": validation.get("builder_gold_separation_verified") is True,
        "candidate_input_parent_free": validation.get("candidate_input_parent_free") is True,
        "closed_loop_converged": closed_loop.get("converged") is True,
        "all_adversarial_controls_detected": (
            adversarial.get("status") == "PASSED"
            and adversarial.get("controls_failed") == 0
        ),
        "unit_tests_passed": unit_tests.get("status") == "PASSED",
        "dependency_audit_passed": dependency_audit.get("status") == "PASSED",
        "dependency_audit_matches_requirements": (
            dependency_audit.get("requirements_sha256")
            == sha256(HERE.parent / "requirements-validation.txt")
        ),
        "current_builder_matches_validation": (
            validation.get("builder_sha256") == sha256(HERE / "multitrade_build.py")
        ),
        "current_candidate_input_matches_manifest": (
            manifest.get("input_sha256", {}).get("benchmarks/multitrade_candidates.json")
            == sha256(HERE / "benchmarks/multitrade_candidates.json")
        ),
    }
    if require_stress:
        baseline_hashes = (stress.get("baseline_fingerprint") or {}).get("artifact_hashes")
        checks.update({
            "cold_process_stress_passed": stress.get("status") == "PASSED",
            "stress_outputs_deterministic": stress.get("all_cycles_identical") is True,
            "authoritative_urls_reachable": stress.get("all_sources_reachable") is True,
            "current_artifacts_match_stress_baseline": artifact_hashes() == baseline_hashes,
        })
    passed = all(checks.values())
    status = (
        "THREE_TRADE_EXPERT_VALIDATED_RELEASE_READY"
        if passed and expert.get("status") == "COMPLETE"
        else "INTERNAL_RELEASE_READY_EXTERNAL_REVIEW_PENDING"
        if passed
        else "RELEASE_BLOCKED"
    )
    result = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": status,
        "passed": passed,
        "checks": checks,
        "scope": {
            "trades": [item["trade_label"] for item in validation["trades"]],
            "candidate_classes": validation["candidate_count"],
            "benchmark": "bounded internal benchmark with parent-free builder input",
        },
        "metrics": {
            "taxonomy": validation["aggregate_taxonomy"],
            "competency_questions": validation["competency_questions"],
            "adversarial_controls": {
                "passed": adversarial["controls_passed"],
                "total": adversarial["adversarial_controls"],
            },
            "cold_process_cycles": stress.get("cold_process_cycles") if stress else None,
        },
        "claim_boundary": (
            "The artifacts are internally reproducible, structurally valid and consistent with the "
            "fixed three-trade benchmark. This is not independent expert validation and does not "
            "estimate accuracy on an unseen fourth trade."
        ),
        "expert_review": expert,
        "remaining_external_gate": "independent domain-expert adjudication of classes and direct parents",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit("Three-trade release gate failed")
    return result


if __name__ == "__main__":
    print(json.dumps(decide(), ensure_ascii=False, indent=2))
