import unittest

import config
from database import get_connection
from services.rate_limiter import check_rate_limit
from tests.base import SmartBethGTestCase


class TestRateLimiter(SmartBethGTestCase):
    def setUp(self):
        super().setUp()
        self._orig_max = config.AUTH_RATE_LIMIT_MAX_ATTEMPTS
        self._orig_window = config.AUTH_RATE_LIMIT_WINDOW_SECONDS
        config.AUTH_RATE_LIMIT_MAX_ATTEMPTS = 3
        config.AUTH_RATE_LIMIT_WINDOW_SECONDS = 60
        conn = get_connection()
        conn.execute("DELETE FROM auth_rate_limit_events")
        conn.commit()
        conn.close()

    def tearDown(self):
        config.AUTH_RATE_LIMIT_MAX_ATTEMPTS = self._orig_max
        config.AUTH_RATE_LIMIT_WINDOW_SECONDS = self._orig_window
        super().tearDown()

    def test_allows_up_to_the_limit(self):
        key = "login:1.2.3.4"
        results = [check_rate_limit(key) for _ in range(3)]
        self.assertEqual(results, [True, True, True])

    def test_blocks_after_the_limit(self):
        key = "login:1.2.3.4"
        for _ in range(3):
            check_rate_limit(key)
        self.assertFalse(check_rate_limit(key))

    def test_epoch_columns_preserve_rate_limit_window_precision(self):
        conn = get_connection()
        try:
            event_type = conn.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema=current_schema() "
                "AND table_name='auth_rate_limit_events' AND column_name='hit_epoch'"
            ).fetchone()
            lock_type = conn.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema=current_schema() "
                "AND table_name='auth_rate_limit_locks' AND column_name='last_seen_epoch'"
            ).fetchone()
            self.assertIsNotNone(event_type)
            self.assertIsNotNone(lock_type)
            self.assertEqual(event_type["data_type"], "double precision")
            self.assertEqual(lock_type["data_type"], "double precision")
        finally:
            conn.close()

    def test_different_keys_are_independent(self):
        for _ in range(3):
            check_rate_limit("login:1.1.1.1")
        self.assertTrue(check_rate_limit("login:2.2.2.2"))


if __name__ == "__main__":
    unittest.main()
