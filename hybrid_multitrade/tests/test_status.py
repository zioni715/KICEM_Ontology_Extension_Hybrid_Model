import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("status_runner", ROOT / "hybrid_multitrade/run.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class StatusTests(unittest.TestCase):
    def test_running_does_not_reuse_historical_failure_or_claim_completion(self):
        cases = [{"trade_id": "a"}, {"trade_id": "b"}]
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "RESULTS", Path(folder)):
            runner.write(Path(folder) / "a.json", {"status": "BLOCKED_AUTHENTICATION"})
            runner.update_status(cases, active="a")
            status = runner.read(Path(folder) / "STATUS.json")
            self.assertEqual(status["trades"]["a"], "RUNNING")
            self.assertEqual(status["completed_trades"], 0)
            self.assertFalse(status["hybrid_experiment_complete"])

    def test_complete_requires_every_trade_and_never_claims_expert_accuracy(self):
        cases = [{"trade_id": "a"}, {"trade_id": "b"}]
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "RESULTS", Path(folder)):
            for case in cases:
                runner.write(Path(folder) / (case["trade_id"] + ".json"), {"status": "COMPLETED_TBOX"})
            runner.update_status(cases)
            status = runner.read(Path(folder) / "STATUS.json")
            self.assertTrue(status["hybrid_experiment_complete"])
            self.assertIsNone(status["accuracy"])
            self.assertFalse(status["expert_validated"])
