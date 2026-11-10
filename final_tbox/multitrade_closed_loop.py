#!/usr/bin/env python3
"""Run complete three-trade build and validation twice to prove convergence."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from multitrade_build import build_all
from multitrade_validate import validate_all


HERE = Path(__file__).resolve().parent
REPORT = HERE / "reports/multitrade_closed_loop.json"


def fingerprint(manifest: dict, validation: dict) -> dict:
    return {
        "output_hashes": {case["trade_id"]: case["outputs"] for case in manifest["cases"]},
        "candidate_count": validation["candidate_count"],
        "aggregate_taxonomy": validation["aggregate_taxonomy"],
        "competency_questions": validation["competency_questions"],
        "mutation_controls": {key: validation["mutation_controls"][key] for key in ("passed", "total")},
        "trade_results": {case["trade_id"]: case["passed"] for case in validation["trades"]},
    }


def run(max_cycles: int = 3, stable_required: int = 2) -> dict:
    cycles = []
    previous = None
    stable = 0
    for number in range(1, max_cycles + 1):
        manifest = build_all()
        validation = validate_all()
        current = fingerprint(manifest, validation)
        passed = validation["status"] == "PASSED" and validation["builder_gold_separation_verified"]
        same = passed and previous == current
        stable = stable + 1 if same else 1 if passed else 0
        cycles.append({"cycle": number, "passed": passed, "stable_with_previous": same,
                       "stable_run_length": stable, "fingerprint": current})
        print(f"multitrade closed-loop cycle={number} passed={passed} stable={stable}/{stable_required}",
              flush=True)
        previous = current
        if stable >= stable_required:
            break
    converged = stable >= stable_required
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "CONVERGED" if converged else "NOT_CONVERGED",
        "converged": converged,
        "cycles_executed": len(cycles),
        "stable_cycles_required": stable_required,
        "cycles": cycles,
        "scope": "closed-loop release validation of three T-Box cases; not an online learning loop",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not converged:
        raise SystemExit("Multitrade closed loop did not converge")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
