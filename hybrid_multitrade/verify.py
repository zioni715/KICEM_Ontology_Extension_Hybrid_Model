"""Run implementation/artifact checks and save their actual outcome."""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def main():
    suite = unittest.defaultTestLoader.discover(str(HERE / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "passed": result.wasSuccessful(),
        "scope": "Implementation, recorded artifacts, exact evidence quotes, OWL validator controls; not independent semantic accuracy",
        "skipped_tests": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "failed_tests": [test.id() for test, _ in result.failures + result.errors],
    }
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results/verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
