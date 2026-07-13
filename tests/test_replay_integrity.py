from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import unittest

from spwin_engine import integrity, v260, v261


ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "world_cup_2026" / "gold"


class ReplayIntegrityTests(unittest.TestCase):
    def test_lose_alias_is_normalized(self) -> None:
        self.assertEqual(integrity.normalize_result("Lose"), "Loss")
        self.assertEqual(integrity.normalize_result("Loss"), "Loss")

    def test_archived_1x2_falls_back_to_score(self) -> None:
        record = {
            "match_id": "TEST-H-A",
            "match": "Home vs Away",
            "score": {"ht": "0-0", "ft": "2-1"},
            "markets": [
                {"market_code": "1X2", "selection": "Home", "result": "Archived"},
                {"market_code": "1X2", "selection": "Draw", "result": "Archived"},
                {"market_code": "1X2", "selection": "Away", "result": "Archived"},
            ],
        }
        self.assertEqual(integrity.settle(record, "1X2", "Home"), "Win")
        self.assertEqual(integrity.settle(record, "1X2", "Draw"), "Loss")
        self.assertEqual(integrity.settle(record, "1X2", "Away"), "Loss")

    def test_unresolved_staked_bet_fails_closed(self) -> None:
        record = {"match_id": "BAD", "match": "Home vs Away", "score": {}, "markets": []}
        with self.assertRaises(ValueError):
            integrity.require_settled(record, "1X2", "Home")

    def test_frozen_ultra_short_threshold_is_restored(self) -> None:
        record = {
            "match": "Home vs Away",
            "markets": [
                {"market_code": "1X2", "selection": "Home", "closing_odds": 1.18, "movement_pct": -10},
                {"market_code": "1X2", "selection": "Draw", "closing_odds": 5.0, "movement_pct": 0},
                {"market_code": "1X2", "selection": "Away", "closing_odds": 10.0, "movement_pct": 0},
            ],
        }
        fav = v260.closing_favourite(record)
        self.assertIn("ultra-short price risk", v260.red_flags(record, fav))

    def test_gold_loader_follows_match_index(self) -> None:
        index = json.loads((GOLD_DIR / "MATCH_INDEX.json").read_text(encoding="utf-8"))
        records = v260.load_gold_records(GOLD_DIR)

        self.assertEqual(len(records), index["total_records"])
        self.assertEqual(len(records), 99)
        self.assertEqual(len({record["match_id"] for record in records}), 99)

        loaded_files = {record["_file"] for record in records}
        indexed_files = {entry["file"] for entry in index["records"]}
        self.assertEqual(loaded_files, indexed_files)

        active_ids = {record["match_id"] for record in records}
        self.assertIn("WC2026-GRP-ALG-AUT", active_ids)
        self.assertIn("WC2026-GRP-COD-UZB", active_ids)
        self.assertIn("WC2026-GRP-COL-POR", active_ids)
        self.assertIn("WC2026-GRP-JOR-ARG", active_ids)
        self.assertIn("WC2026-QF-ARG-SUI", active_ids)
        self.assertNotIn("WC2026-R32-ALG-AUT", active_ids)
        self.assertNotIn("WC2026-R32-COD-UZB", active_ids)
        self.assertNotIn("WC2026-R32-COL-POR", active_ids)
        self.assertNotIn("WC2026-R32-JOR-ARG", active_ids)

    def test_v261_baseline_replay_tracks_99_record_dataset(self) -> None:
        records = v260.load_gold_records(GOLD_DIR)
        result = v261.replay(records)
        self.assertEqual(result["records"], 99)
        self.assertEqual(result["bets"], 6)
        self.assertEqual(result["wins"], 5)
        self.assertEqual(result["losses"], 1)
        self.assertEqual(result["final_bankroll"], 1001.50)
        self.assertEqual(result["max_drawdown_pct"], 1.25)

    def test_recommendations_are_blind_to_results_and_scores(self) -> None:
        for record in v260.load_gold_records(GOLD_DIR):
            original = v261.make_recommendation(record)
            stripped = deepcopy(record)
            stripped.pop("score", None)
            for row in stripped.get("markets", []):
                row.pop("result", None)
            blind = v261.make_recommendation(stripped)
            self.assertEqual(
                (original.market, original.selection, original.cpi, original.consensus_count, original.red_flags),
                (blind.market, blind.selection, blind.cpi, blind.consensus_count, blind.red_flags),
                record.get("match_id"),
            )


if __name__ == "__main__":
    unittest.main()
