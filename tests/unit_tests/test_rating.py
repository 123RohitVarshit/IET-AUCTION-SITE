import unittest

from backend.core.rating import build, elo_rating, percentile_scores, tier_for


class PercentileTests(unittest.TestCase):
    def test_single_candidate_gets_half(self):
        self.assertEqual(percentile_scores([10]), [0.5])

    def test_low_middle_high(self):
        values = [1, 2, 3]

        scores = percentile_scores(values)

        self.assertAlmostEqual(scores[0], 0.0)
        self.assertAlmostEqual(scores[1], 0.5)
        self.assertAlmostEqual(scores[2], 1.0)

    def test_ties_count_half(self):
        values = [5, 5, 5]

        scores = percentile_scores(values)

        for score in scores:
            self.assertAlmostEqual(score, 0.5)


class EloTests(unittest.TestCase):
    def test_middle_percentile_is_1500(self):
        self.assertEqual(elo_rating(0.5), 1500)

    def test_clamps_low(self):
        low = elo_rating(0.0)
        self.assertEqual(low, elo_rating(0.02))

    def test_clamps_high(self):
        high = elo_rating(1.0)
        self.assertEqual(high, elo_rating(0.98))

    def test_higher_percentile_gives_higher_rating(self):
        self.assertGreater(elo_rating(0.8), elo_rating(0.6))


class TierTests(unittest.TestCase):
    def test_top_ten_percent(self):
        self.assertEqual(tier_for(0, 100), 1)
        self.assertEqual(tier_for(9, 100), 1)

    def test_next_twenty_percent(self):
        self.assertEqual(tier_for(10, 100), 2)
        self.assertEqual(tier_for(29, 100), 2)

    def test_next_thirty_percent(self):
        self.assertEqual(tier_for(30, 100), 3)
        self.assertEqual(tier_for(59, 100), 3)

    def test_rest_is_tier_four(self):
        self.assertEqual(tier_for(60, 100), 4)
        self.assertEqual(tier_for(99, 100), 4)


class BuildTests(unittest.TestCase):
    def _make_rows(self, n=30):
        return [
            {
                "id": i,
                "name": f"Player {i}",
                "aptitude": i * 3,
                "gd": i * 2,
                "profile": i * 4,
            }
            for i in range(1, n + 1)
        ]

    def test_empty_rows_returns_empty(self):
        self.assertEqual(build([]), [])

    def test_missing_columns_raises(self):
        bad_rows = [
            {
                "id": 1,
                "name": "Broken",
            }
        ]

        with self.assertRaises(ValueError):
            build(bad_rows)

    def test_duplicate_ids_raise(self):
        rows = [
            {
                "id": 1,
                "name": "A",
                "aptitude": 10,
                "gd": 10,
                "profile": 10,
            },
            {
                "id": 1,
                "name": "B",
                "aptitude": 20,
                "gd": 20,
                "profile": 20,
            },
        ]

        with self.assertRaises(ValueError):
            build(rows)

    def test_build_adds_rating_tier_base_price(self):
        rows = self._make_rows(30)
        out = build(rows)

        self.assertEqual(len(out), 30)

        for row in out:
            self.assertIn("rating", row)
            self.assertIn("tier", row)
            self.assertIn("base_price", row)
            self.assertIn(row["tier"], {1, 2, 3, 4})

    def test_top_player_is_tier_one(self):
        rows = self._make_rows(30)
        out = build(rows)

        top = max(out, key=lambda r: r["rating"])

        self.assertEqual(top["tier"], 1)
        self.assertEqual(top["base_price"], 1000)

    def test_ratings_are_ordered(self):
        rows = self._make_rows(30)
        out = build(rows)

        ratings = [row["rating"] for row in out]

        self.assertGreater(max(ratings), min(ratings))


if __name__ == "__main__":
    unittest.main()