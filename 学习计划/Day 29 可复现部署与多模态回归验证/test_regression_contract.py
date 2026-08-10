"""Offline unit tests for Day 29 regression assessments."""

import unittest

from regression_contract import assess_combined, assess_health, assess_invalid_request, assess_safe_transfer, assess_text_command, assess_visual_only


FOLLOW = {"command": {"status": "verified_command", "command": '!followPlayer("robot", 3)'}, "observation": {"status": "not_requested"}}
VISION = {"command": {"status": "not_requested"}, "observation": {"status": "verified_observation", "entity": "sheep"}}


class RegressionContractTests(unittest.TestCase):
    def test_health_requires_both_upstreams(self):
        self.assertTrue(assess_health(200, {"ok": True, "command_upstream": {"reachable": True}, "vision_upstream": {"reachable": True}})[0])
        self.assertFalse(assess_health(200, {"ok": True, "command_upstream": {"reachable": True}, "vision_upstream": {"reachable": False}})[0])

    def test_follow_requires_exact_verified_command(self):
        self.assertTrue(assess_text_command(200, FOLLOW)[0])
        self.assertFalse(assess_text_command(200, {"command": {"status": "verified_command", "command": "!stop"}})[0])

    def test_safety_and_invalid_payload(self):
        self.assertTrue(assess_safe_transfer(200, {"command": {"status": "no_command", "command": None}})[0])
        self.assertTrue(assess_invalid_request(400, {"ok": False, "reason": "invalid_request"})[0])

    def test_visual_and_combined_boundaries(self):
        self.assertTrue(assess_visual_only(200, VISION, "sheep")[0])
        combined = {"command": FOLLOW["command"], "observation": {"status": "verified_observation", "entity": "sheep"}}
        self.assertTrue(assess_combined(200, combined, "sheep")[0])
        self.assertFalse(assess_combined(200, combined, "pig")[0])


if __name__ == "__main__":
    unittest.main()
