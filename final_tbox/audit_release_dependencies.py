#!/usr/bin/env python3
"""Audit the minimal release requirements and bind the result to their hash."""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REQUIREMENTS = ROOT / "requirements-validation.txt"
REPORT = HERE / "reports/dependency_audit.json"


def run() -> dict:
    command = [
        sys.executable, "-m", "pip_audit", "-r", str(REQUIREMENTS),
        "--format", "json",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    try:
        audit = json.loads(completed.stdout)
    except json.JSONDecodeError:
        audit = {"dependencies": [], "fixes": [], "parse_error": completed.stdout}
    vulnerabilities = [
        {"package": item.get("name"), "version": item.get("version"), "vulns": item.get("vulns")}
        for item in audit.get("dependencies", []) if item.get("vulns")
    ]
    passed = completed.returncode == 0 and not vulnerabilities and "parse_error" not in audit
    result = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "PASSED" if passed else "FAILED",
        "requirements_sha256": hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest(),
        "auditor": "pip-audit",
        "audited_dependencies": len(audit.get("dependencies", [])),
        "known_vulnerabilities": vulnerabilities,
        "stderr": completed.stderr.strip(),
    }
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not passed:
        raise SystemExit("Release dependency audit failed")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
