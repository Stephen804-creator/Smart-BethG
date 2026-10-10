import unittest

import config
from services.rate_limiter import check_rate_limit, _hits


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self._orig_max = config.AUTH_RATE_LIMIT_MAX_ATTEMPTS
        self._orig_window = config.AUTH_RATE_LIMIT_WINDOW_SECONDS
        config.AUTH_RATE_LIMIT_MAX_ATTEMPTS = 3
        config.AUTH_RATE_LIMIT_WINDOW_SECONDS = 60
        _hits.clear()

    def tearDown(self):
        config.AUTH_RATE_LIMIT_MAX_ATTEMPTS = self._orig_max
        config.AUTH_RATE_LIMIT_WINDOW_SECONDS = self._orig_window
        _hits.clear()

    def test_allows_up_to_the_limit(self):
        key = "login:1.2.3.4"
        results = [check_rate_limit(key) for _ in range(3)]
        self.assertEqual(results, [True, True, True])

    def test_blocks_after_the_limit(self):
        key = "login:1.2.3.4"
        for _ in range(3):
            check_rate_limit(key)
        self.assertFalse(check_rate_limit(key))

    def test_different_keys_are_independent(self):
        for _ in range(3):
            check_rate_limit("login:1.1.1.1")
        # A different IP must not be affected by the first one's limit.
        self.assertTrue(check_rate_limit("login:2.2.2.2"))
