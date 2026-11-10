from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from rdflib import Graph, OWL, RDF, RDFS, URIRef


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from multitrade_build import BASE_CLASSES, build_all  # noqa: E402
import multitrade_release_gate  # noqa: E402


class MultitradeReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_all()
        cls.candidates = json.loads(
            (HERE / "benchmarks/multitrade_candidates.json").read_text(encoding="utf-8")
        )

    def test_builder_has_no_gold_dependency(self) -> None:
        source = (HERE / "multitrade_build.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("multitrade_gold", source)
        self.assertFalse(self.manifest["builder_reads_validation_gold"])
        self.assertNotIn("multitrade_gold.json", self.manifest["input_sha256"])
        self.assertFalse(self.manifest["candidate_input_contains_parent"])
        expected_fields = {"id", "label", "section", "definition", "source_id"}
        for case in self.candidates["cases"]:
            for record in case["candidates"]:
                self.assertEqual(set(record), expected_fields)

    def test_builder_runs_in_directory_without_gold_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tbox-builder-isolation-") as name:
            isolated = Path(name)
            shutil.copy2(HERE / "multitrade_build.py", isolated / "multitrade_build.py")
            benchmarks = isolated / "benchmarks"
            benchmarks.mkdir()
            (benchmarks / "multitrade_candidates.json").write_text(
                json.dumps(self.candidates, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            run = subprocess.run(
                [sys.executable, str(isolated / "multitrade_build.py")],
                cwd=isolated,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertFalse((benchmarks / "multitrade_gold.json").exists())
            self.assertTrue((isolated / "outputs/multitrade/manifest.json").is_file())

    def test_all_three_cases_are_pure_tboxes_with_expected_counts(self) -> None:
        by_id = {case["trade_id"]: case for case in self.candidates["cases"]}
        self.assertEqual(set(by_id), {"architecture_tile", "civil_stormwater", "fire_exit_guidance"})
        for built in self.manifest["cases"]:
            graph = Graph().parse(HERE / "outputs/multitrade" / f"{built['trade_id']}.ttl")
            classes = {
                term for term in graph.subjects(RDF.type, OWL.Class)
                if isinstance(term, URIRef)
            }
            expected = len(by_id[built["trade_id"]]["candidates"]) + len(BASE_CLASSES)
            self.assertEqual(len(classes), expected)
            self.assertEqual(built["total_classes"], expected)
            self.assertFalse(any(
                obj in classes
                for subject, obj in graph.subject_objects(RDF.type)
                if subject not in classes and obj != OWL.Ontology
            ))

    def test_every_candidate_has_parent_evidence_and_trade_root_path(self) -> None:
        for case in self.candidates["cases"]:
            graph = Graph().parse(HERE / "outputs/multitrade" / f"{case['trade_id']}.ttl")
            namespace = case["namespace"]
            root = URIRef(namespace + case["trade_root_id"])
            edges = {
                child: set(graph.objects(child, RDFS.subClassOf))
                for child in graph.subjects(RDF.type, OWL.Class)
            }
            for row in case["candidates"]:
                uri = URIRef(namespace + row["id"])
                self.assertEqual(len(list(graph.objects(uri, URIRef(namespace + "predictedDirectParent")))), 1)
                self.assertEqual(len(list(graph.objects(uri, URIRef(namespace + "predictionMethod")))), 1)
                self.assertTrue(list(graph.objects(uri, URIRef(namespace + "evidenceSourceId"))))
                seen, frontier = set(), [uri]
                while frontier:
                    node = frontier.pop()
                    if node in seen:
                        continue
                    seen.add(node)
                    frontier.extend(edges.get(node, ()))
                self.assertIn(root, seen)

    def test_stormwater_and_exit_guidance_wbs_sources_are_current_and_documented(self) -> None:
        by_id = {case["trade_id"]: case for case in self.candidates["cases"]}
        civil = by_id["civil_stormwater"]
        fire = by_id["fire_exit_guidance"]
        civil_sources = {source["source_id"]: source for source in civil["sources"]}
        fire_sources = {source["source_id"]: source for source in fire["sources"]}

        self.assertEqual(
            civil_sources["KCS-11-40-25"]["title"],
            "KCS 11 40 25 노면배수",
        )
        self.assertEqual(
            civil_sources["KCS-12-20-10"]["title"],
            "KCS 12 20 10 배수공사 측량",
        )
        self.assertIn("KCS-11-40-15", civil_sources)
        self.assertIn("KCS-11-20-25", civil_sources)
        self.assertEqual(
            fire_sources["NFTC-303"]["url"],
            "https://www.law.go.kr/admRulLsInfoP.do?admRulId=83636&efYd=0",
        )
        fire_candidates = {row["id"]: row for row in fire["candidates"]}
        self.assertEqual(
            fire_candidates["GuidanceEquipmentFunctionalInspection"]["source_id"],
            "FIRE-SELF-INSPECTION-2022",
        )

        evidence = (HERE / "WBS_EVIDENCE.md").read_text(encoding="utf-8")
        for case in (civil, fire):
            for source in case["sources"]:
                self.assertIn(source["url"], evidence)
            for row in case["candidates"]:
                self.assertIn(row["label"], evidence)

    def test_release_gate_rejects_artifact_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tbox-gate-") as name:
            report = Path(name) / "gate.json"
            real_read = multitrade_release_gate.read

            def read_with_running_tests(filename: str) -> dict:
                if filename == "multitrade_unit_tests.json":
                    return {"status": "PASSED"}
                return real_read(filename)

            with patch.object(multitrade_release_gate, "OUTPUT", report), patch.object(
                multitrade_release_gate,
                "artifact_hashes",
                return_value={"tampered.owl": "not-the-stress-baseline"},
            ), patch.object(
                multitrade_release_gate,
                "read",
                side_effect=read_with_running_tests,
            ):
                with self.assertRaises(SystemExit):
                    multitrade_release_gate.decide(require_stress=True)
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "RELEASE_BLOCKED")
            self.assertFalse(result["checks"]["current_artifacts_match_stress_baseline"])


if __name__ == "__main__":
    unittest.main()
