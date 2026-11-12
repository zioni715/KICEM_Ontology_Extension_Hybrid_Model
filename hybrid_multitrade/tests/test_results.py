"""Check released files against their recorded experiment outcomes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

from rdflib import Graph, RDF, RDFS, OWL, Namespace
from rdflib.compare import isomorphic

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("release_tbox", HERE / "tbox_export.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class ReleasedResultTests(unittest.TestCase):
    def test_completed_artifacts_match_recorded_results(self):
        found = 0
        cases = {case["trade_id"]: case for case in
                 json.loads((HERE / "inputs/trade_candidates.json").read_text())["cases"]}
        for path in (HERE / "results").glob("*.json"):
            result = json.loads(path.read_text())
            if result.get("status") != "COMPLETED_TBOX" or "trade_id" not in result:
                continue
            found += 1
            with self.subTest(trade=result["trade_id"]):
                owl = HERE / "results" / (result["trade_id"] + ".owl")
                ttl = owl.with_suffix(".ttl")
                first, second = Graph().parse(owl), Graph().parse(ttl)
                self.assertTrue(isomorphic(first, second))
                self.assertTrue(exporter.audit_tbox(first)["passed"])
                self.assertEqual(len(set(first.subjects(RDF.type, OWL.Class))), result["classes"])
                self.assertEqual(len(set(first.subjects(RDF.type, OWL.DatatypeProperty))), result["data_properties"])
                self.assertFalse(list(first.subjects(RDF.type, OWL.NamedIndividual)))
                self.assertTrue(result["checks"]["passed"])
                self.assertFalse(result["expert_validated"])
                self.assertIsNone(result["gold_accuracy"])
                self.assertEqual(result["proposal_count"], result["accepted_provisional"] + result["held"])
                self.assertEqual(sum(x["exported"] for x in result["candidate_outcomes"]), result["exported_accepted"])
                case = cases[result["trade_id"]]
                sources = {"WBS:W000": case["trade_label"]}
                for number, row in enumerate(case["candidates"], 1):
                    sources[f"STD:{number:03d}"] = row["label"] + " " + row["definition"]
                    sources[f"WBS:W{number:03d}"] = f'{row["label"]}: {row["definition"]} [{row["source_id"]} § {row["section"]}]'
                ns = Namespace("https://example.org/kicem/hybrid/" + result["trade_id"] + "#")
                for item in result["candidate_outcomes"]:
                    if item["exported"]:
                        self.assertTrue(item["verified_quotes"], "Exported candidate has no verified evidence")
                        self.assertIn((ns[item["id"]], RDFS.subClassOf, ns[item["selected_parent"]]), first)
                        for quote in item["verified_quotes"]:
                            self.assertIn(quote["source_id"], sources)
                            self.assertTrue(quote["quote"])
                            self.assertIn(quote["quote"], sources[quote["source_id"]])
                for artifact in [owl, ttl]:
                    self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                     result["output_sha256"][artifact.name])
        if not found:
            self.skipTest("No completed hybrid results published yet")
