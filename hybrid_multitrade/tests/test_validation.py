import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from rdflib import Graph, RDF, RDFS, OWL, Namespace

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hybrid_owl_validation", ROOT / "hybrid_multitrade/owl_validation.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class InputTests(unittest.TestCase):
    def test_three_trades_have_unique_parent_free_grounded_inputs(self):
        cases = json.loads((ROOT / "hybrid_multitrade/inputs/trade_candidates.json").read_text())["cases"]
        self.assertEqual({c["trade_id"] for c in cases},
                         {"architecture_tile", "civil_stormwater", "fire_exit_guidance"})
        for case in cases:
            sources = {s["source_id"] for s in case["sources"]}
            rows = case["candidates"]
            self.assertEqual(len(rows), len({r["id"] for r in rows}))
            for row in rows:
                self.assertEqual(set(row), {"id", "label", "definition", "section", "source_id"})
                self.assertIn(row["source_id"], sources)
                self.assertTrue(all(str(v).strip() for v in row.values()))


class OWLValidationTests(unittest.TestCase):
    def test_positive_tbox_and_unsatisfiable_control(self):
        with tempfile.TemporaryDirectory(prefix="hybrid-owl-test-") as name:
            work = Path(name)
            java, jar = validator.compile_validators(work / "classes")
            graph = Graph()
            ns = Namespace("urn:hybrid-test:")
            graph.add((ns.Ontology, RDF.type, OWL.Ontology))
            for node in [ns.Work, ns.Preparation]:
                graph.add((node, RDF.type, OWL.Class))
            graph.add((ns.Preparation, RDFS.subClassOf, ns.Work))
            owl, ttl = work / "positive.owl", work / "positive.ttl"
            graph.serialize(owl, format="xml")
            graph.serialize(ttl, format="turtle")
            result = validator.java_validate(java, jar, work / "classes", owl, ttl, work)
            self.assertTrue(result["profile"]["owl2_dl_profile"]["in_profile"])
            self.assertTrue(result["profile"]["serialization_validation"]["passed"])
            self.assertTrue(result["hermit"]["consistent"])
            self.assertEqual(result["hermit"]["unsatisfiable_named_classes"], [])
            control = work / "negative.json"
            subprocess.run([str(java), "-cp", f'{work / "classes"}:{jar}', "ValidateHermit",
                            "--unsatisfiable-class-control", str(control)], check=True,
                           capture_output=True, timeout=60)
            self.assertTrue(json.loads(control.read_text())["unsatisfiable_named_classes"])


if __name__ == "__main__":
    unittest.main()
