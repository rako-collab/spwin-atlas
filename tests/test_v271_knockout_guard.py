import unittest

from spwin_engine import v271_knockout_guard as v271


def market(code, selection, opening, closing, movement, **extra):
    row = {
        "market_code": code,
        "selection": selection,
        "opening_odds": opening,
        "closing_odds": closing,
        "movement_pct": movement,
    }
    row.update(extra)
    return row


def admitted_short_knockout(include_qualify=False, fair_probability=None):
    markets = [
        market("1X2", "Argentina", 1.67, 1.37, -18.0),
        market("1X2", "Draw", 3.30, 3.90, 18.2),
        market("1X2", "Switzerland", 4.50, 7.00, 55.6),
        market("AH", "Argentina -0.75", 2.00, 1.80, -10.0),
        market("AH", "Switzerland +0.75", 1.72, 1.92, 11.6),
        market("HT_1X2", "Argentina", 2.30, 2.16, -6.1),
        market("HT_1X2", "Draw", 2.03, 2.08, 2.5),
        market("HT_1X2", "Switzerland", 5.20, 5.60, 7.7),
        market("FG", "Argentina", 1.55, 1.47, -5.2),
        market("FG", "Switzerland", 3.00, 3.30, 10.0),
        market("OU", "Under 3.5", 1.70, 1.55, -8.8),
        market("BTTS", "No", 1.80, 1.70, -5.6),
    ]
    if include_qualify:
        extra = {}
        if fair_probability is not None:
            extra["fair_probability"] = fair_probability
        markets.append(market("QUALIFY", "Argentina", 1.25, 1.20, -4.0, **extra))

    return {
        "match_id": "TEST-QF-ARG-SUI",
        "match": "Argentina vs Switzerland",
        "date": "2026-07-12",
        "stage": "Quarter Final",
        "status": "COMPLETED",
        "quality_grade": "Gold",
        "score": {"ht": "0-0", "ft_90": "1-1", "aet": "3-1"},
        "qualifier": "Argentina",
        "markets": markets,
    }


class V271KnockoutGuardTests(unittest.TestCase):
    def test_normalized_draw_probability_is_no_vig(self):
        probability = v271.normalized_draw_probability(admitted_short_knockout())
        self.assertAlmostEqual(probability, 0.227074, places=6)
        self.assertEqual(v271.draw_risk_band(probability), "high")

    def test_knockout_guard_blocks_regulation_1x2_without_qualify_market(self):
        record = admitted_short_knockout()
        base = v271.v270.make_recommendation(record)
        self.assertGreater(base.stake_pct, 0.0)
        self.assertEqual(base.market, "1X2")

        recommendation = v271.make_recommendation(record)
        self.assertTrue(recommendation.knockout_guard_triggered)
        self.assertEqual(recommendation.decision_code, "PASS_MARKET_MISMATCH")
        self.assertEqual(recommendation.market, "PASS")
        self.assertEqual(recommendation.selection, "PASS")
        self.assertEqual(recommendation.stake_pct, 0.0)

    def test_qualification_market_requires_explicit_positive_value(self):
        no_value = v271.make_recommendation(
            admitted_short_knockout(include_qualify=True)
        )
        self.assertEqual(no_value.decision_code, "PASS_NO_VALUE")
        self.assertEqual(no_value.market, "PASS")

        positive_value = v271.make_recommendation(
            admitted_short_knockout(include_qualify=True, fair_probability=0.88)
        )
        self.assertEqual(positive_value.decision_code, "RESEARCH_BET_QUALIFY")
        self.assertEqual(positive_value.market, "QUALIFY")
        self.assertEqual(positive_value.selection, "Argentina")
        self.assertAlmostEqual(positive_value.expected_value, 0.056, places=6)
        self.assertLessEqual(positive_value.stake_pct, v271.KNOCKOUT_STAKE_CAP)

    def test_group_stage_does_not_trigger_knockout_guard(self):
        record = admitted_short_knockout()
        record["stage"] = "Group Stage"
        recommendation = v271.make_recommendation(record)
        self.assertFalse(recommendation.knockout_guard_triggered)
        self.assertEqual(recommendation.market, "1X2")
        self.assertEqual(recommendation.selection, "Argentina")

    def test_settlement_distinguishes_regulation_from_qualification(self):
        record = admitted_short_knockout(
            include_qualify=True, fair_probability=0.88
        )
        self.assertEqual(
            v271.require_research_settled(record, "1X2", "Argentina"),
            "Loss",
        )
        self.assertEqual(
            v271.require_research_settled(record, "QUALIFY", "Argentina"),
            "Win",
        )

    def test_replay_records_guard_pass_and_uses_chronological_contract(self):
        result = v271.replay([admitted_short_knockout()])
        self.assertEqual(result["chronological_order"], "date_asc,match_id_asc")
        self.assertEqual(result["bets"], 0)
        self.assertEqual(result["passes"], 1)
        self.assertEqual(result["knockout_guard_trigger_count"], 1)
        self.assertEqual(result["knockout_guard_pass_count"], 1)
        self.assertEqual(
            result["rows"][0]["decision_status"], "PASS_MARKET_MISMATCH"
        )
        self.assertEqual(result["rows"][0]["score_ft_90"], "1-1")


if __name__ == "__main__":
    unittest.main()
