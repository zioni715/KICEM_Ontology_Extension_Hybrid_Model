#!/usr/bin/env python3
"""Cold-process repeated validation for the three-trade T-Box release."""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "outputs/multitrade"
REPORT = HERE / "reports/multitrade_stress_validation.json"
CANDIDATES = HERE / "benchmarks/multitrade_candidates.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_script(name: str) -> None:
    run = subprocess.run([sys.executable, str(HERE / name)], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    if run.returncode:
        raise RuntimeError(f"{name} failed\nSTDOUT:\n{run.stdout}\nSTDERR:\n{run.stderr}")


def artifact_hashes() -> dict:
    return {path.name: sha256(path) for path in sorted(OUT.glob("*.*"))
            if path.suffix in {".ttl", ".owl"}}


def validation_fingerprint() -> dict:
    result = json.loads((HERE / "reports/multitrade_validation.json").read_text(encoding="utf-8"))
    return {
        "status": result["status"],
        "candidate_count": result["candidate_count"],
        "taxonomy": result["aggregate_taxonomy"],
        "competency_questions": result["competency_questions"],
        "mutation_controls": {key: result["mutation_controls"][key] for key in ("passed", "total")},
        "gold_separated": result["builder_gold_separation_verified"],
        "trade_checks": {trade["trade_id"]: trade["checks"] for trade in result["trades"]},
    }


def audit_sources() -> list[dict]:
    data = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    unique = {source["source_id"]: source for case in data["cases"] for source in case["sources"]}
    results = []
    for source_id, source in sorted(unique.items()):
        request = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
                final_url = response.geturl()
            error = None
        except Exception as exc:
            status = None
            final_url = None
            error = f"{type(exc).__name__}: {exc}"
        results.append({"source_id": source_id, "url": source["url"],
                        "http_status": status, "final_url": final_url,
                        "reachable": status == 200, "error": error})
    return results


def run(cycles: int = 10, verify_sources: bool = True) -> dict:
    records = []
    baseline = None
    for number in range(1, cycles + 1):
        run_script("multitrade_build.py")
        run_script("multitrade_validate.py")
        current = {"artifact_hashes": artifact_hashes(),
                   "validation": validation_fingerprint()}
        if baseline is None:
            baseline = current
        records.append({"cycle": number, "passed": current["validation"]["status"] == "PASSED",
                        "identical_to_cycle_1": current == baseline})
        print(f"stress cycle={number}/{cycles} passed={records[-1]['passed']} "
              f"identical={records[-1]['identical_to_cycle_1']}", flush=True)
    sources = audit_sources() if verify_sources else []
    passed = (all(item["passed"] and item["identical_to_cycle_1"] for item in records) and
              (not verify_sources or all(item["reachable"] for item in sources)))
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "PASSED" if passed else "FAILED",
        "cold_process_cycles": cycles,
        "all_cycles_identical": all(item["identical_to_cycle_1"] for item in records),
        "all_cycles_passed": all(item["passed"] for item in records),
        "baseline_fingerprint": baseline,
        "cycles": records,
        "authoritative_source_audit": sources,
        "source_audit_performed": verify_sources,
        "all_sources_reachable": all(item["reachable"] for item in sources) if verify_sources else None,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit("Multitrade stress validation failed")
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({key: result[key] for key in
                      ("status", "cold_process_cycles", "all_cycles_identical",
                       "all_cycles_passed", "all_sources_reachable")},
                     ensure_ascii=False, indent=2))
