import unittest

from spwin_engine import v270_research as v270


def market(code, selection, opening, closing, movement):
    return {
        "market_code": code,
        "selection": selection,
        "opening_odds": opening,
        "closing_odds": closing,
        "movement_pct": movement,
    }


def argentina_like_record(stage="Quarter Final", status="UPCOMING"):
    return {
        "match_id": "TEST-ARG-SUI",
        "match": "Argentina vs Switzerland",
        "date": "2026-07-12",
        "stage": stage,
        "status": status,
        "markets": [
            market("1X2", "Argentina", 1.67, 1.45, -13.2),
            market("1X2", "Draw", 3.30, 3.70, 12.1),
            market("1X2", "Switzerland", 4.50, 6.00, 33.3),
            market("AH", "Argentina -0.75", 1.91, 1.77, -7.3),
            market("AH", "Switzerland +0.75", 1.91, 2.00, 4.7),
            market("HANDICAP_ALT", "Argentina -1.5", 3.15, 2.45, -22.2),
            market("HANDICAP_ALT", "Switzerland +1.5", 1.28, 1.45, 13.3),
            market("HT_1X2", "Argentina", 2.30, 2.20, -4.3),
            market("HT_1X2", "Draw", 2.03, 2.05, 1.0),
            market("HT_1X2", "Switzerland", 5.20, 5.20, 0.0),
            market("FG", "Argentina", 1.55, 1.45, -6.5),
            market("FG", "Switzerland", 3.00, 3.30, 10.0),
            market("OU", "Over 2.5", 2.25, 2.07, -8.0),
            market("OU", "Under 2.5", 1.55, 1.65, 6.5),
            market("BTTS", "Yes", 2.00, 1.95, -2.5),
            market("BTTS", "No", 1.67, 1.70, 1.8),
        ],
    }


class V270CorrectnessTests(unittest.TestCase):
    def test_primary_ah_does_not_use_alternate_handicap(self):
        record = argentina_like_record()
        primary = v270.primary_favourite_ah(record, "Argentina")
        alternate = v270.alternate_favourite_ah(record, "Argentina")
        self.assertEqual(primary["selection"], "Argentina -0.75")
        self.assertEqual(primary["movement_pct"], -7.3)
        self.assertEqual(alternate["selection"], "Argentina -1.5")
        self.assertEqual(alternate["movement_pct"], -22.2)

    def test_quarter_final_gets_knockout_context(self):
        self.assertEqual(v270.stage_context("Quarter Final"), (3, "knockout caution"))
        self.assertEqual(v270.stage_context("Round of 16"), (3, "knockout caution"))
        self.assertEqual(v270.stage_context("Group Stage"), (5, "group-stage context"))
        self.assertEqual(v270.stage_context("Unknown"), (0, "unknown stage context"))

    def test_ht_partial_confirmation_has_minimum_threshold(self):
        record = argentina_like_record()
        favourite = v270.v260.closing_favourite(record)
        consensus, _ = v270.compute_consensus(record, favourite)
        flags = v270.red_flags(record, favourite)
        cpi, reasons = v270.compute_cpi(record, favourite, consensus, flags)
        self.assertIn("HT partial confirmation", reasons)

        for row in record["markets"]:
            if row["market_code"] == "HT_1X2" and row["selection"] == "Argentina":
                row["movement_pct"] = -0.5
        cpi_without_partial, reasons_without_partial = v270.compute_cpi(
            record, favourite, consensus, flags
        )
        self.assertNotIn("HT partial confirmation", reasons_without_partial)
        self.assertEqual(cpi - cpi_without_partial, 5.0)

    def test_argentina_like_case_is_pass_after_correctness_fixes(self):
        recommendation = v270.make_recommendation(argentina_like_record())
        self.assertEqual(recommendation.consensus_count, 2)
        self.assertEqual(recommendation.cpi, 60.0)
        self.assertEqual(recommendation.selection, "PASS")
        self.assertEqual(recommendation.stake_pct, 0.0)
        self.assertEqual(recommendation.price_type, "current_snapshot")
        self.assertIsNotNone(recommendation.alternate_ah_observation)

    def test_completed_record_labels_price_as_closing(self):
        recommendation = v270.make_recommendation(
            argentina_like_record(status="COMPLETED")
        )
        self.assertEqual(recommendation.price_type, "closing")
        self.assertTrue(hasattr(recommendation, "signal_score"))
        self.assertFalse(hasattr(recommendation, "confidence"))


if __name__ == "__main__":
    unittest.main()
