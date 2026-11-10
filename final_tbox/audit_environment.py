#!/usr/bin/env python3
"""Audit whether the original GPU experiment can be rerun exactly today."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
T = ROOT / "test2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict:
    frozen = json.loads((T / "reports/final_environment.json").read_text())
    completed = json.loads((T / "reports/completed_manifest.json").read_text())
    changed = []
    for relative, expected in completed["files"].items():
        path = T / relative
        actual = sha(path) if path.exists() else None
        if actual != expected:
            changed.append({"path": relative, "expected": expected, "actual": actual})
    package_changes = []
    for package, expected in frozen["packages"].items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        if actual != expected:
            package_changes.append({"package": package, "expected": expected, "actual": actual})
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=10)
    requirements_actual = sha(ROOT / "requirements.txt")
    requirements_expected = frozen["requirements_sha256"]
    report = {
        "exact_full_pipeline_rerun_ready": (
            gpu.returncode == 0 and requirements_actual == requirements_expected and
            not package_changes and not changed),
        "gpu_available": gpu.returncode == 0,
        "gpu_stdout": gpu.stdout.strip(),
        "gpu_stderr": gpu.stderr.strip(),
        "requirements_hash_matches_original_run": requirements_actual == requirements_expected,
        "requirements_expected_sha256": requirements_expected,
        "requirements_actual_sha256": requirements_actual,
        "package_changes": package_changes,
        "completed_artifacts_checked": len(completed["files"]),
        "completed_artifact_changes": changed,
        "interpretation": (
            "Saved artifacts can be evaluated independently. Exact Module1-5 rerun readiness "
            "requires the recorded dependency lock, an operational GPU, and an unchanged pilot manifest."
        ),
    }
    reports = HERE / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "environment_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    audit()
