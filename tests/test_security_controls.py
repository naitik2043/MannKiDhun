import unittest
from unittest.mock import patch

import app as mood_app


class LoginAttemptRegistryTests(unittest.TestCase):
    def setUp(self):
        mood_app.login_attempts.clear()

    def tearDown(self):
        mood_app.login_attempts.clear()

    def test_registry_is_bounded_and_evicts_the_least_recently_used_key(self):
        first = ("192.0.2.1", "identifier-a")
        second = ("192.0.2.1", "identifier-b")
        third = ("192.0.2.1", "identifier-c")

        with (
            patch.object(mood_app, "LOGIN_ATTEMPT_MAX_KEYS", 2),
            patch.object(mood_app, "LOGIN_ATTEMPT_LIMIT", 1),
        ):
            mood_app._record_failed_login(first)
            mood_app._record_failed_login(second)

            # A lookup refreshes the key's LRU position.
            self.assertGreater(mood_app._login_retry_after(first), 0)
            mood_app._record_failed_login(third)

        self.assertEqual(list(mood_app.login_attempts), [first, third])
        self.assertEqual(mood_app._login_retry_after(second), 0)

    def test_expired_registry_entries_are_removed_on_the_next_failed_attempt(self):
        first = ("192.0.2.2", "identifier-a")
        second = ("192.0.2.2", "identifier-b")
        clock = [100.0]

        with patch.object(mood_app.time, "monotonic", side_effect=lambda: clock[0]):
            mood_app._record_failed_login(first)
            clock[0] += mood_app.LOGIN_ATTEMPT_WINDOW_SECONDS + 1
            mood_app._record_failed_login(second)

        self.assertNotIn(first, mood_app.login_attempts)
        self.assertIn(second, mood_app.login_attempts)


if __name__ == "__main__":
    unittest.main()
