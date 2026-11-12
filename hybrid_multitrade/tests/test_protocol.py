import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hybrid_rerun", ROOT / "hybrid_multitrade/run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


@unittest.skipUnless((runner.PILOT / "module2/source").is_dir(), "Local pilot sources required")
class ProtocolTests(unittest.TestCase):
    def test_changed_input_cannot_resume_stale_run(self):
        case = runner.read(ROOT / "hybrid_multitrade/inputs/trade_candidates.json")["cases"][0]
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "RUNS", Path(folder)):
            runner.prepare(case)
            changed = json.loads(json.dumps(case))
            changed["candidates"][0]["definition"] += " changed"
            with self.assertRaisesRegex(RuntimeError, "Input changed"):
                runner.prepare(changed)

    def test_public_inputs_have_no_prices_or_gold(self):
        cases = runner.read(ROOT / "hybrid_multitrade/inputs/trade_candidates.json")["cases"]
        for case in cases:
            work = runner.prepare(case)
            rows = runner.read(work / "module1/outputs/raw_rows.json")
            self.assertEqual(len(rows), len(case["candidates"]))
            self.assertTrue(all(v is None for row in rows for v in row["numbers"].values()))
            self.assertTrue(all("parent" not in row for row in rows))
            self.assertFalse(any(work.rglob("*gold*.json")))

    def test_model_and_training_conditions_are_preserved(self):
        case = runner.read(ROOT / "hybrid_multitrade/inputs/trade_candidates.json")["cases"][0]
        work = runner.prepare(case)
        source = (runner.PIPELINE / "module2/run.py").read_text()
        for fixed in ["torch.manual_seed(42)", "range(8)", "lr=0.0001", "bce_loss", "CosineEmbeddingLoss"]:
            self.assertIn(fixed, source)
        rank = (runner.PIPELINE / "module5/rank.py").read_text()
        self.assertIn("range(2)", rank)
        self.assertIn("lr=1e-05", rank)
        self.assertEqual(runner.read(work / "configs/experiment.json")["api"]["selected_model"],
                         "gpt-4o-mini-2024-07-18")


if __name__ == "__main__":
    unittest.main()
