import unittest

from backend.api.rate_limit import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_limit(self):
        limiter = RateLimiter(limit=3, window_seconds=10.0)

        self.assertTrue(limiter.allow(1))
        self.assertTrue(limiter.allow(1))
        self.assertTrue(limiter.allow(1))

        self.assertFalse(limiter.allow(1))

    def test_keys_are_independent(self):
        limiter = RateLimiter(limit=2, window_seconds=10.0)

        self.assertTrue(limiter.allow(1))
        self.assertTrue(limiter.allow(1))
        self.assertFalse(limiter.allow(1))

        self.assertTrue(limiter.allow(2))
        self.assertTrue(limiter.allow(2))
        self.assertFalse(limiter.allow(2))


if __name__ == "__main__":
    unittest.main()