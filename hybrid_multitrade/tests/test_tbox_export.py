import importlib.util
from pathlib import Path
import unittest

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hybrid_tbox_export", ROOT / "hybrid_multitrade/tbox_export.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


class TBoxOnlyTests(unittest.TestCase):
    def schema(self):
        graph = Graph()
        ns = Namespace("urn:tbox-only:")
        graph.add((ns.Task, RDF.type, OWL.Class))
        graph.add((ns.installation, RDF.type, OWL.ObjectProperty))
        graph.add((ns.price, RDF.type, OWL.DatatypeProperty))
        return graph, ns

    def test_schema_declarations_are_allowed(self):
        graph, ns = self.schema()
        graph.add((ns.installation, RDFS.domain, ns.Task))
        graph.add((ns.Task, RDFS.label, Literal("작업")))
        self.assertTrue(exporter.audit_tbox(graph)["passed"])

    def test_explicit_individual_is_blocked(self):
        graph, ns = self.schema()
        graph.add((ns.site1, RDF.type, OWL.NamedIndividual))
        self.assertFalse(exporter.audit_tbox(graph)["passed"])

    def test_implicit_individual_without_namedindividual_is_blocked(self):
        graph, ns = self.schema()
        graph.add((ns.site1, RDF.type, ns.Task))
        self.assertFalse(exporter.audit_tbox(graph)["passed"])

    def test_object_fact_is_blocked(self):
        graph, ns = self.schema()
        graph.add((ns.site1, ns.installation, ns.site2))
        self.assertFalse(exporter.audit_tbox(graph)["passed"])

    def test_price_fact_is_blocked_even_on_a_class(self):
        graph, ns = self.schema()
        graph.add((ns.Task, ns.price, Literal(50000)))
        self.assertFalse(exporter.audit_tbox(graph)["passed"])

    def test_unresolved_parents_are_pruned_and_no_wbs_instances_are_created(self):
        base = {"WorkTask": {"label": "작업", "origin": "researcher_anchor", "parents": ["OntologyEntity"]}}
        decisions = [
            {"status": "accepted_provisional", "query": {"id": "Installation", "label": "설치"}, "parent": "WorkTask"},
            {"status": "accepted_provisional", "query": {"id": "Unsupported"}, "parent": "Rejected"},
        ]
        graph, counts = exporter.build_tbox("fixture", base, decisions, [])
        self.assertEqual(counts["classes"], 2)
        self.assertEqual(counts["exported_accepted"], 1)
        self.assertEqual(counts["dropped_classes"], ["Unsupported"])
        self.assertTrue(exporter.audit_tbox(graph)["passed"])

    def test_hybrid_stages_do_not_execute_original_abox_exporter(self):
        source = (ROOT / "hybrid_multitrade/run.py").read_text()
        self.assertNotIn('"module5/export.py"', source)

    def test_original_cost_role_bridge_is_preserved_not_counted_as_prediction(self):
        base = {
            "CostItem": {"label": "비용", "origin": "seed", "parents": []},
            "MaterialCost": {"label": "자재 비용", "origin": "researcher_cost_role_bridge", "parents": ["CostItem"]},
        }
        decisions = [{"status": "accepted_provisional", "query": {"id": "PipeCost", "label": "관 비용"},
                      "parent": "MaterialCost"}]
        graph, counts = exporter.build_tbox("fixture", base, decisions, [])
        self.assertEqual(counts["classes"], 3)
        self.assertEqual(counts["exported_accepted"], 1)
        self.assertEqual(counts["retained_seed_classes"], 1)
        self.assertEqual(counts["researcher_anchor_classes"], 1)


if __name__ == "__main__":
    unittest.main()
