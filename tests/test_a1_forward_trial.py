from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from validate_a1_forward_trial import validate_ledger, validate_rows


LEDGER = ROOT / "data" / "world_cup_2026" / "a1_forward_trial" / "A1_TRIAL_LEDGER.csv"


class A1ForwardTrialTests(unittest.TestCase):
    def test_empty_trial_ledger_is_valid(self) -> None:
        result = validate_ledger(LEDGER)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["rows"], 0)

    def test_valid_locked_bet(self) -> None:
        row = {
            "trial_id": "A1-001",
            "match_id": "TEST-001",
            "match": "Home vs Away",
            "kickoff_sgt": "2026-07-03T03:00:00+08:00",
            "snapshot_time_sgt": "2026-07-03T02:30:00+08:00",
            "locked_time_sgt": "2026-07-03T02:45:00+08:00",
            "data_source": "test",
            "a1_status": "BET",
            "a1_selection": "Home",
            "a1_odds": "1.60",
            "a1_stake_pct": "0.0025",
            "bankroll_before": "1000.00",
            "stake_amount": "2.50",
            "one_x_two_opening": "1.75",
            "one_x_two_final": "1.60",
            "one_x_two_move_pct": "-8.57",
            "ah_opening": "1.90",
            "ah_final": "1.85",
            "ah_move_pct": "-2.63",
            "coverage_signature": "1X2+AH",
            "red_flags": "",
            "decision_reasons": "all A1 gates passed",
            "locked": "TRUE",
            "outcome": "",
        }
        result = validate_rows([row])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["bets"], 1)

    def test_unlocked_decision_fails(self) -> None:
        row = {
            "trial_id": "A1-002",
            "match_id": "TEST-002",
            "match": "Home vs Away",
            "a1_status": "PASS",
            "locked": "FALSE",
            "data_source": "test",
            "decision_reasons": "did not qualify",
            "outcome": "",
        }
        result = validate_rows([row])
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("locked=TRUE" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
