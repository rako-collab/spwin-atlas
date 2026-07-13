from pathlib import Path
import unittest

from spwin_engine import v260, v261_a1


ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "world_cup_2026" / "gold"


class A1MicroLaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = v260.load_gold_records(GOLD_DIR)

    def test_a1_historical_selection_set(self) -> None:
        selected = [
            v261_a1.evaluate(record).match_id
            for record in self.records
            if v261_a1.evaluate(record).qualified
        ]
        self.assertEqual(
            selected,
            [
                "WC2026-GRP-MEX-RSA",
                "WC2026-GRP-SWE-TUN",
                "WC2026-GRP-IRN-NZL",
                "WC2026-GRP-GER-CIV",
                "WC2026-GRP-TUN-JPN",
                "WC2026-GRP-NZL-EGY",
                "WC2026-GRP-NOR-SEN",
            ],
        )

    def test_a1_historical_replay(self) -> None:
        result = v261_a1.replay(self.records)
        self.assertEqual(result["bets"], 7)
        self.assertEqual(result["wins"], 6)
        self.assertEqual(result["losses"], 1)
        self.assertEqual(result["final_bankroll"], 1004.62)
        self.assertEqual(result["net_profit"], 4.62)
        self.assertEqual(result["return_on_stakes_pct"], 26.37)
        self.assertEqual(result["max_drawdown_pct"], 0.25)

    def test_combined_historical_replay(self) -> None:
        result = v261_a1.combined_replay(self.records)
        self.assertEqual(result["bets"], 13)
        self.assertEqual(result["wins"], 11)
        self.assertEqual(result["losses"], 2)
        self.assertEqual(result["final_bankroll"], 1006.12)
        self.assertEqual(result["net_profit"], 6.12)
        self.assertEqual(result["return_on_stakes_pct"], 8.37)
        self.assertEqual(result["max_drawdown_pct"], 1.25)


if __name__ == "__main__":
    unittest.main()
