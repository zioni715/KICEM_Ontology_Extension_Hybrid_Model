import ast
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("unified_runner", HERE / "run.py")
domain = load("unified_domain", HERE / "pipeline/shared/domain.py")


class UnifiedPipelineTests(unittest.TestCase):
    def test_completed_unified_runs_share_sources_and_preserve_previous_outputs(self):
        from rdflib import Graph
        from rdflib.compare import isomorphic
        baseline = HERE / ".runs/pre-unification-results"
        records = []
        for trade in runner.CONTEXT:
            current = runner.read(HERE / "results" / (trade + ".json"))
            if current.get("provenance", {}).get("architecture") != "single shared parameterized pipeline":
                self.skipTest("Unified end-to-end execution not complete for every trade")
            records.append(current)
        self.assertTrue(all(record["provenance"]["source_files"] == records[0]["provenance"]["source_files"]
                            for record in records))
        actual = [{"path": str(path.relative_to(runner.PIPELINE)), "sha256": runner.digest(path)}
                  for path in sorted(runner.PIPELINE.rglob("*.py"))]
        self.assertEqual(records[0]["provenance"]["source_files"], actual)
        if not baseline.is_dir():
            self.skipTest("Local pre-unification snapshots are not distributed")
        for record in records:
            trade = record["trade_id"]
            old = runner.read(baseline / (trade + ".json"))
            with self.subTest(trade=trade):
                self.assertEqual(record["classes"], old["classes"])
                self.assertEqual(record["candidate_outcomes"], old["candidate_outcomes"])
                self.assertTrue(isomorphic(Graph().parse(HERE / "results" / (trade + ".ttl")),
                                           Graph().parse(baseline / (trade + ".ttl"))))

    def test_every_trade_uses_identical_algorithm_sources_without_code_copies(self):
        cases = runner.read(HERE / "inputs/trade_candidates.json")["cases"]
        manifests = []
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "RUNS", Path(folder)):
            for case in cases:
                work = runner.prepare(case)
                manifests.append(runner.read(work / "provenance.json")["source_files"])
                for stage in runner.STAGES:
                    self.assertFalse((work / stage).exists())
                    ast.parse((runner.PIPELINE / stage).read_text())
            self.assertTrue(all(manifest == manifests[0] for manifest in manifests))

    def test_trade_changes_are_runtime_data_not_generated_python(self):
        cases = runner.read(HERE / "inputs/trade_candidates.json")["cases"]
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "RUNS", Path(folder)):
            for case in cases:
                work = runner.prepare(case)
                title, lower, ko = runner.CONTEXT[case["trade_id"]]
                with patch.dict(os.environ, {"HYBRID_CASE_ROOT": str(work)}):
                    self.assertEqual(domain.domain_text("TileMaterialCostItem"), title + "MaterialCostItem")
                    self.assertEqual(domain.domain_text("in_tile_scope"), "in_" + lower + "_scope")
                    self.assertEqual(domain.domain_text("타일 설치"), ko + " 설치")
                self.assertEqual(runner.read(work / "configs/trade.json")["trade_id"], case["trade_id"])

    def test_shared_sources_are_syntactically_valid_and_runner_never_executes_case_code(self):
        for source in runner.PIPELINE.rglob("*.py"):
            ast.parse(source.read_text(), filename=str(source))
        source = (HERE / "run.py").read_text()
        self.assertIn('str(PIPELINE / name)', source)
        self.assertNotIn('str(work / name)', source)
