#!/usr/bin/env python3
"""Build and validate the authoritative three-trade T-Box release."""
from __future__ import annotations

import argparse
import json

from multitrade_adversarial_validate import run as run_adversarial
from multitrade_closed_loop import run as run_closed_loop
from multitrade_release_gate import decide
from multitrade_stress_validate import run as run_stress


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress-cycles", type=int, default=10)
    parser.add_argument(
        "--skip-source-audit",
        action="store_true",
        help="Development-only offline run; cannot pass the final release gate.",
    )
    args = parser.parse_args()
    if args.stress_cycles < 2:
        parser.error("--stress-cycles must be at least 2")

    closed = run_closed_loop(max_cycles=3, stable_required=2)
    adversarial = run_adversarial()
    stress = run_stress(
        cycles=args.stress_cycles,
        verify_sources=not args.skip_source_audit,
    )
    if args.skip_source_audit:
        print(json.dumps({
            "status": "DEVELOPMENT_VALIDATION_PASSED",
            "closed_loop": closed["status"],
            "adversarial": adversarial["status"],
            "stress": stress["status"],
            "release_gate": "NOT_RUN_WITHOUT_SOURCE_AUDIT",
        }, ensure_ascii=False, indent=2))
        return
    print(json.dumps(decide(require_stress=True), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
