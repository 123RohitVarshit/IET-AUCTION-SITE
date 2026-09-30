import unittest

from backend.core.config import Config


class ConfigTests(unittest.TestCase):
    def test_default_event_numbers_match_handbook(self):
        cfg = Config()

        self.assertEqual(cfg.roster_size, 4)
        self.assertEqual(cfg.purse, 10_000)

        self.assertEqual(cfg.tier_base[1], 1000)
        self.assertEqual(cfg.tier_base[2], 600)
        self.assertEqual(cfg.tier_base[3], 400)
        self.assertEqual(cfg.tier_base[4], 200)

        self.assertEqual(cfg.inc_low, 100)
        self.assertEqual(cfg.inc_high, 250)
        self.assertEqual(cfg.inc_threshold, 1500)

        self.assertEqual(cfg.floor_price, 100)
        self.assertEqual(cfg.round_drop, 0.5)
        self.assertEqual(cfg.max_rounds, 5)

        self.assertEqual(cfg.preview_seconds, 30)
        self.assertEqual(cfg.bid_seconds, 30)
        self.assertEqual(cfg.result_seconds, 8)
        self.assertEqual(cfg.anti_snipe_seconds, 8)
        self.assertEqual(cfg.undo_extend_seconds, 10)

        self.assertTrue(cfg.auto_advance)


if __name__ == "__main__":
    unittest.main()