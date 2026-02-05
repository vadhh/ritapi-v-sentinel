import time
import unittest
from unittest import mock

from minifw_ai.collector_flow import FlowTracker
from minifw_ai.main import evaluate_hard_threat, init_mlp_detector, init_yara_scanner


class TestBaselineHardGates(unittest.TestCase):
    def test_hard_gate_survives_ai_failure(self):
        tracker = FlowTracker()
        flow = tracker.update_flow("192.168.1.10", "8.8.8.8", 443, "tcp", pkt_size=1500)

        flow.first_seen = time.time() - 4.0
        flow.last_seen = time.time()
        flow.pkt_count = 1000

        flows_for_client = tracker.get_flows_for_client("192.168.1.10")

        with mock.patch("minifw_ai.main.MLP_AVAILABLE", True), \
            mock.patch("minifw_ai.main.YARA_AVAILABLE", True), \
            mock.patch("minifw_ai.main.get_mlp_detector", side_effect=RuntimeError("mlp init failed")), \
            mock.patch("minifw_ai.main.get_yara_scanner", side_effect=RuntimeError("yara init failed")):
            mlp_detector, mlp_enabled = init_mlp_detector(True)
            yara_scanner, yara_enabled = init_yara_scanner(True)

        self.assertIsNone(mlp_detector)
        self.assertFalse(mlp_enabled)
        self.assertIsNone(yara_scanner)
        self.assertFalse(yara_enabled)

        hard_threat, reason = evaluate_hard_threat(flows_for_client, flow_freq=0, flow_freq_threshold=200)
        self.assertTrue(hard_threat)
        self.assertEqual(reason, "pps_saturation")


if __name__ == "__main__":
    unittest.main()
