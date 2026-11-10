#!/usr/bin/env python3
"""Run the convergent final T-Box release workflow."""
from closed_loop import run_closed_loop
from multitrade_closed_loop import run as run_multitrade_closed_loop
from multitrade_adversarial_validate import run as run_multitrade_adversarial
from prepare_expert_review import prepare
from release_gate import decide
from score_expert_review import score


if __name__ == "__main__":
    prepare()
    expert = score()
    loop = run_closed_loop()
    multitrade = run_multitrade_closed_loop()
    adversarial = run_multitrade_adversarial()
    gate = decide(require_closed_loop=True)
    last = loop["cycles"][-1]["fingerprint"]
    multi_last = multitrade["cycles"][-1]["fingerprint"]
    print(
        f"Final T-Box closed loop: {loop['status']} | cycles={loop['cycles_executed']} | "
        f"classes={last['class_count']} | technical={last['technical_checks']} | "
        f"mutations={last['mutation_controls']} | evidence={last['evidence']} | "
        f"expert={expert['status']} | release={gate['status']} | "
        f"trades={len(multi_last['trade_results'])} | "
        f"trade_candidates={multi_last['candidate_count']} | "
        f"trade_validation={multitrade['status']} | "
        f"adversarial={adversarial['controls_passed']}/{adversarial['adversarial_controls']}"
    )
