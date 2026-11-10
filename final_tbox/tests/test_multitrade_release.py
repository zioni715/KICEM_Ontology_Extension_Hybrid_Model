from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from rdflib import Graph, OWL, RDF, RDFS, URIRef


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from multitrade_build import BASE_CLASSES, build_all  # noqa: E402


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
            root = URIRef(namespace + case["candidates"][0][0])
            edges = {
                child: set(graph.objects(child, RDFS.subClassOf))
                for child in graph.subjects(RDF.type, OWL.Class)
            }
            for row in case["candidates"]:
                uri = URIRef(namespace + row[0])
                self.assertEqual(len(list(graph.objects(uri, URIRef(namespace + "predictedDirectParent")))), 1)
                self.assertTrue(list(graph.objects(uri, URIRef(namespace + "evidenceSourceId"))))
                seen, frontier = set(), [uri]
                while frontier:
                    node = frontier.pop()
                    if node in seen:
                        continue
                    seen.add(node)
                    frontier.extend(edges.get(node, ()))
                self.assertIn(root, seen)


if __name__ == "__main__":
    unittest.main()
