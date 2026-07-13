import unittest

from tools import validate_gold_snapshot_integrity as validator


class GoldSnapshotLockWindowTests(unittest.TestCase):
    def test_explicit_t_minus_10_lock_is_valid_at_ten(self):
        errors = []
        validator._validate_locked_window(
            {"snapshot_role": "T_MINUS_10_CLOSING_LOCK"},
            10,
            errors,
            "TEST-T10",
        )
        self.assertEqual(errors, [])

    def test_explicit_t_minus_10_lock_rejects_other_windows(self):
        errors = []
        validator._validate_locked_window(
            {"snapshot_role": "T_MINUS_10_CLOSING_LOCK"},
            15,
            errors,
            "TEST-T15",
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("T_MINUS_10_CLOSING_LOCK", errors[0])

    def test_ordinary_lock_still_requires_t_minus_30_to_t_minus_15(self):
        errors = []
        validator._validate_locked_window(
            {"snapshot_role": "FORWARD_DECISION_LOCK"},
            10,
            errors,
            "TEST-ORDINARY",
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("T-30 to T-15", errors[0])


if __name__ == "__main__":
    unittest.main()
