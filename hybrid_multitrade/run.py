"""Run one parameterized hybrid T-Box pipeline on configured trade inputs.

Never loads private workbooks or evaluation gold. All changes to the pilot are
recorded in a source manifest. Per-trade prompts, outputs and weights stay local.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PILOT = ROOT / "tile_case_study"
PIPELINE = HERE / "pipeline"
RUNS = HERE / ".runs/unified"
RESULTS = HERE / "results"
STAGES = ["module1/run.py", "module2/run.py", "module3/run.py",
          "module4/run.py", "module5/rank.py", "module5/run.py", "module5/audit.py",
          "module5/grounding_rules.py"]
CONTEXT = {key: (value["class_prefix"], value["identifier"], value["term_ko"])
           for key, value in json.loads((PIPELINE / "configs/trades.json").read_text()).items()}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def update_status(cases, active=None, error=None):
    """Publish observed progress, never infer success from old ontology files."""
    trades = {}
    for case in cases:
        trade = case["trade_id"]
        path = RESULTS / (trade + ".json")
        trades[trade] = read(path).get("status", "UNKNOWN") if path.exists() else "NOT_EXECUTED"
    if active:
        trades[active] = "RUNNING" if error is None else "FAILED"
    completed = sum(value == "COMPLETED_TBOX" for value in trades.values())
    write(RESULTS / "STATUS.json", {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "COMPLETED_TBOX" if completed == len(cases) else (
            "FAILED" if error else "RUNNING"),
        "hybrid_experiment_complete": completed == len(cases),
        "output_scope": "TBOX_ONLY", "completed_trades": completed,
        "architecture": "single shared parameterized pipeline",
        "trades": trades, "active_trade": active if error is None else None,
        "error_type": type(error).__name__ if error else None,
        "accuracy": None, "expert_validated": False,
        "scope": "Frozen hybrid algorithms on public standards-derived descriptions; no independent expert gold scores",
    })


def prepare(case):
    work = RUNS / case["trade_id"]
    work.mkdir(parents=True, exist_ok=True)
    input_hash = hashlib.sha256(json.dumps(case, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    previous = work / "provenance.json"
    new_run = not previous.exists()
    if previous.exists() and read(previous).get("input_sha256") != input_hash:
        raise RuntimeError("Input changed in an existing run; use a separate run directory rather than stale caches")
    title, lower, ko = CONTEXT[case["trade_id"]]
    manifest = [{"path": str(path.relative_to(PIPELINE)), "sha256": digest(path)}
                for path in sorted(PIPELINE.rglob("*.py"))]
    for module in ["module1", "module2", "module3", "module4", "module5"]:
        for folder in ["outputs", "reports", "adapters"]:
            (work / module / folder).mkdir(parents=True, exist_ok=True)
    (work / "reports").mkdir(exist_ok=True)
    for module in ["module2", "module3", "module4"]:
        link = work / module / "source"
        if not link.exists():
            link.symlink_to(PILOT / module / "source", target_is_directory=True)
    (work / "configs").mkdir(exist_ok=True)
    for name in ["llama_model.json", "llama_runtime.json", "llama_scoring_runtime.json"]:
        destination = work / "configs" / name
        if destination.exists() and digest(destination) != digest(PIPELINE / "configs" / name):
            raise RuntimeError(f"Frozen configuration changed: {name}")
        shutil.copy2(PIPELINE / "configs" / name, work / "configs" / name)
    profile = {"trade_id": case["trade_id"], "class_prefix": title, "identifier": lower, "term_ko": ko}
    profile_path = work / "configs/trade.json"
    if profile_path.exists() and read(profile_path) != profile:
        raise RuntimeError("Trade configuration changed in an existing run")
    write(profile_path, profile)
    write(work / "configs/experiment.json", {"api": {"selected_model": "gpt-4o-mini-2024-07-18"}})
    seed = read(PIPELINE / "shared/seed_elements.json")
    if previous.exists() and read(previous).get("seed_sha256"):
        if read(previous)["seed_sha256"] != digest(PIPELINE / "shared/seed_elements.json"):
            raise RuntimeError("Seed changed in an existing run")
    write(work / "shared/seed_elements.json", seed)
    # WBS ancestry is deliberately flat; no direct-parent gold is supplied.
    wbs, rows = [], []
    root_code = "W000"
    wbs.append({"code": root_code, "label": case["trade_label"], "parent": None,
                "quote": case["trade_label"]})
    for i, item in enumerate(case["candidates"]):
        code = f"W{i+1:03d}"
        text = f'{item["label"]}: {item["definition"]} [{item["source_id"]} § {item["section"]}]'
        wbs.append({"code": code, "label": item["label"], "parent": root_code, "quote": text})
        rows.append({"id": f"STD:{i+1:03d}", "section": case["trade_label"],
                     "name": item["label"], "specification": item["definition"], "unit": "",
                     "mentions_" + lower: True,
                     "numbers": {key: None for key in ["materialUnitCost", "laborUnitCost", "expenseUnitCost", "contractUnitPrice", "contractAmount"]},
                     "cells": {}, "source_id": item["source_id"], "source_section": item["section"]})
    write(work / "shared/wbs.json", wbs)
    write(work / "module1/outputs/raw_rows.json", rows)
    write(work / "provenance.json", {
        "trade_id": case["trade_id"], "source_files": manifest,
        "architecture": "single shared parameterized pipeline",
        "input_kind": "public standard-derived normalized descriptions; not private workbook rows",
        "input_sha256": input_hash,
        "model_parameters_changed": False,
        "seed_sha256": digest(work / "shared/seed_elements.json"),
        "configuration_sha256": {p.name: digest(p) for p in sorted((work / "configs").glob("*.json"))},
        "adaptations": ["runtime trade configuration", "public WBS input adapter", "T-Box-only export"],
        "gold_used": False, "source_count": len(case["sources"]), "input_rows": len(rows),
    })
    # Reuse identical model requests, not previous decisions/checkpoints/results.
    legacy = HERE / ".runs" / case["trade_id"]
    if new_run and legacy.is_dir():
        caches = [*legacy.glob("*/outputs/api_cache"), legacy / "module4/outputs/local_cache",
                  legacy / "module5/outputs/lineage_cache"]
        for cache in caches:
            if cache.is_dir():
                shutil.copytree(cache, work / cache.relative_to(legacy), dirs_exist_ok=True)
    return work


def run_case(case):
    work = prepare(case)
    env = dict(os.environ, HYBRID_REPOSITORY_ROOT=str(ROOT), HYBRID_CASE_ROOT=str(work),
               PYTHONDONTWRITEBYTECODE="1", TOKENIZERS_PARALLELISM="false",
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    state_path = work / "state.json"
    state = read(state_path) if state_path.exists() else {"trade_id": case["trade_id"], "stages": {}}
    pipeline_hash = hashlib.sha256(json.dumps(read(work / "provenance.json")["source_files"],
                                            sort_keys=True).encode()).hexdigest()
    for name in STAGES:
        if (state["stages"].get(name, {}).get("returncode") == 0 and
                state["stages"][name].get("pipeline_sha256") == pipeline_hash):
            continue
        started = time.time()
        log_path = work / "reports" / (name.replace("/", "_") + ".log")
        print(f'{case["trade_id"]}: {name}', flush=True)
        with log_path.open("w") as log:
            completed = subprocess.run([sys.executable, "-u", str(PIPELINE / name)], cwd=ROOT,
                                       env=env, stdout=log, stderr=subprocess.STDOUT)
        state["stages"][name] = {"returncode": completed.returncode, "seconds": round(time.time()-started, 2),
                                  "source_sha256": digest(PIPELINE / name), "pipeline_sha256": pipeline_hash}
        write(state_path, state)
        if completed.returncode:
            failure = {"status": "FAILED", "trade_id": case["trade_id"], "stage": name,
                       "returncode": completed.returncode, "completed_stages": [
                           s for s, v in state["stages"].items() if v["returncode"] == 0],
                       "hybrid_experiment_complete": False}
            api_log = work / "reports/api_calls.jsonl"
            if api_log.exists():
                last = json.loads(api_log.read_text().splitlines()[-1])
                failure["api_error"] = {k: last.get(k) for k in ["error_type", "status_code", "code"]}
                if last.get("error_type") == "AuthenticationError":
                    failure["status"] = "BLOCKED_AUTHENTICATION"
            write(RESULTS / (case["trade_id"] + ".json"), failure)
            print(log_path.read_text()[-4500:], flush=True)
            raise RuntimeError(f"Stage failed: {case['trade_id']} {name}; inspect local log")
    return export(case, work, state)


def export(case, work, state):
    from rdflib import Graph
    from rdflib.compare import isomorphic
    from owl_validation import compile_validators, java_validate
    from tbox_export import build_tbox

    decisions = read(work / "module5/outputs/decisions.json")
    schema = read(work / "module1/outputs/initial_schema.json")
    graph, counts = build_tbox(
        case["trade_id"], read(work / "module5/outputs/base_nodes.json"),
        decisions, schema.get("properties", []))
    # Validate staging files before publishing any final ontology.
    scratch = work / "reasoner"
    scratch.mkdir(exist_ok=True)
    owl = scratch / (case["trade_id"] + ".owl")
    ttl = scratch / (case["trade_id"] + ".ttl")
    graph.serialize(ttl, format="turtle")
    graph.serialize(owl, format="xml")
    java, jar = compile_validators(scratch / "classes")
    semantic = java_validate(java, jar, scratch / "classes", owl, ttl, scratch)
    checks = {
        "pure_tbox": counts["pure_tbox"],
        "acyclic": counts["acyclic"],
        "serializations_equal": isomorphic(Graph().parse(ttl), Graph().parse(owl)),
        "owlapi_hermit": semantic,
    }
    checks["passed"] = bool(
        checks["pure_tbox"]["passed"] and checks["acyclic"] and
        checks["serializations_equal"] and
        semantic["profile"].get("owl2_dl_profile", {}).get("in_profile", False) and
        semantic["profile"].get("serialization_validation", {}).get("passed", False) and
        semantic["hermit"].get("consistent", False) and
        not semantic["hermit"].get("unsatisfiable_named_classes", []))
    write(scratch / "validation.json", checks)
    if not checks["passed"]:
        raise RuntimeError("T-Box validation failed; final output was not published")
    RESULTS.mkdir(exist_ok=True)
    for path in [owl, ttl]:
        shutil.copy2(path, RESULTS / path.name)
    accepted = [d for d in decisions if d["status"] == "accepted_provisional"]
    calls = [json.loads(line) for line in (work / "reports/api_calls.jsonl").read_text().splitlines()]
    covered = set()
    for decision in accepted:
        if decision["query"]["id"] in counts["dropped_classes"]:
            continue
        for quote in decision.get("export_verified_quotes", []):
            source = quote["source_id"]
            number = source.removeprefix("STD:") if source.startswith("STD:") else (
                source.removeprefix("WBS:W") if source.startswith("WBS:W") else "")
            if number.isdigit() and 1 <= int(number) <= len(case["candidates"]):
                covered.add(int(number))
    return {
        "status": "COMPLETED_TBOX", "output_scope": "TBOX_ONLY",
        "trade_id": case["trade_id"], "stages": state["stages"],
        "runtime_versions": {"python": platform.python_version(), **{
            name: importlib.metadata.version(name) for name in
            ["torch", "transformers", "vllm", "sentence-transformers", "peft", "numpy",
             "openai", "httpx", "rdflib", "owlready2", "networkx"]}},
        "input_rows": len(case["candidates"]), "proposal_count": len(decisions),
        "evidence_input_coverage_count": len(covered),
        "evidence_input_coverage_note": "Unique input descriptions cited by final candidates; not semantic recall or accuracy",
        "accepted_provisional": len(accepted), "held": len(decisions)-len(accepted),
        **counts, "checks": checks, "gold_accuracy": None, "expert_validated": False,
        "input_kind": "standards-derived normalized descriptions",
        "module2": {k: read(work / "module2/reports/training.json")[k]
                    for k in ["heldout_top1", "heldout_count", "target_supervision"]},
        "module3": read(work / "module3/reports/metrics.json"),
        "module4": {"generated_candidates": read(work / "module4/reports/metrics.json")["generated_candidates"]},
        "module5": {k: read(work / "module5/reports/lorex_metrics.json").get(k)
                    for k in ["strict_lorex_accepted", "taxoadapt_generated", "taxoadapt_accepted",
                              "before_final_evidence_gate", "before_grounding_rules", "deviations"]},
        "api_calls": len(calls),
        "api_successful_calls": sum("error_type" not in call and not call.get("cache_hit") for call in calls),
        "api_cache_hits": sum(bool(call.get("cache_hit")) for call in calls),
        "api_failed_calls": sum("error_type" in call for call in calls),
        "api_total_tokens": sum(call.get("usage", {}).get("total_tokens", 0) for call in calls),
        "provenance": read(work / "provenance.json"),
        "candidate_outcomes": [{
            "id": d["query"]["id"], "label": d["query"]["label"],
            "origin": d["query"].get("origin"), "status": d["status"],
            "selected_parent": d.get("parent"), "reason": d.get("reason"),
            "verified_quotes": d.get("export_verified_quotes", []),
            "exported": d["status"] == "accepted_provisional" and
                        d["query"]["id"] not in counts["dropped_classes"],
        } for d in decisions],
        "output_sha256": {p.name: digest(p) for p in [owl, ttl]},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade", choices=list(CONTEXT))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    cases = read(HERE / "inputs/trade_candidates.json")["cases"]
    results = []
    for case in cases:
        if args.trade and case["trade_id"] != args.trade:
            continue
        if args.prepare_only:
            print(prepare(case), flush=True)
        else:
            update_status(cases, active=case["trade_id"])
            try:
                results.append(run_case(case))
            except Exception as exc:
                update_status(cases, active=case["trade_id"], error=exc)
                raise
            write(RESULTS / (case["trade_id"] + ".json"), results[-1])
            update_status(cases)
    if results:
        write(RESULTS / "summary.json", {"timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
              "architecture": "single shared parameterized pipeline",
              "scope": "Frozen pilot algorithms with domain/input adapters; no independent expert gold scores",
              "trades": results})
        from report import render
        render()


if __name__ == "__main__":
    main()
