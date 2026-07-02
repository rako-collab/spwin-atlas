from copy import deepcopy
from pathlib import Path
import unittest

from spwin_engine import observation_labels, v260, v261, v261_a1


ROOT = Path(__file__).resolve().parents[1]
GOLD_DIR = ROOT / "data" / "world_cup_2026" / "gold"


class ObservationLabelTests(unittest.TestCase):
    def test_label_boundaries(self) -> None:
        labels = observation_labels.derive_from_values(
            favourite_odds=1.20,
            one_x_two_move_pct=-6.0,
            ah_move_pct=-12.0,
            draw_move_pct=-10.0,
        )
        self.assertEqual(labels.price_zone, "PRICE_ZONE_1.20_1.39")
        self.assertEqual(labels.controlled_steam, "CONTROLLED_BOTH")
        self.assertEqual(labels.draw_structure, "STRONG_DRAW_COMPRESSION")

        labels = observation_labels.derive_from_values(
            favourite_odds=1.40,
            one_x_two_move_pct=-12.01,
            ah_move_pct=-5.99,
            draw_move_pct=-9.99,
        )
        self.assertEqual(labels.price_zone, "OUTSIDE_PRICE_ZONE")
        self.assertEqual(labels.controlled_steam, "NO_CONTROLLED_STEAM")
        self.assertEqual(labels.draw_structure, "MILD_DRAW_SHORTENING")

    def test_unavailable_labels_are_explicit(self) -> None:
        labels = observation_labels.derive_from_values(
            favourite_odds=None,
            one_x_two_move_pct=None,
            ah_move_pct=None,
            draw_move_pct=None,
        )
        self.assertEqual(labels.price_zone, "PRICE_UNAVAILABLE")
        self.assertEqual(labels.controlled_steam, "STEAM_UNAVAILABLE")
        self.assertEqual(labels.draw_structure, "DRAW_UNAVAILABLE")

    def test_label_generation_does_not_mutate_record_or_engine_outputs(self) -> None:
        record = v260.load_gold_records(GOLD_DIR)[0]
        original = deepcopy(record)
        production_before = v261.make_recommendation(record)
        a1_before = v261_a1.evaluate(record)

        observation_labels.derive_from_record(record)

        production_after = v261.make_recommendation(record)
        a1_after = v261_a1.evaluate(record)
        self.assertEqual(record, original)
        self.assertEqual(production_before, production_after)
        self.assertEqual(a1_before, a1_after)


if __name__ == "__main__":
    unittest.main()
