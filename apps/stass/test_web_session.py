import unittest
from unittest.mock import patch
from web_session import WebSessions


class WebSessionTests(unittest.TestCase):
    def test_one_time_expiry_and_revocation(self):
        sessions=WebSessions()
        with patch('web_session.time.monotonic',return_value=10):
            code=sessions.issue()
            token=sessions.exchange(code,'local')
            self.assertTrue(sessions.valid(token))
            with self.assertRaises(ValueError): sessions.exchange(code,'local')
            sessions.revoke(token)
            self.assertFalse(sessions.valid(token))
            expiring=sessions.issue()
        with patch('web_session.time.monotonic',return_value=311):
            with self.assertRaises(ValueError): sessions.exchange(expiring,'other')

    def test_failed_pairing_is_rate_limited(self):
        sessions=WebSessions()
        for _ in range(10):
            with self.assertRaises(ValueError):sessions.exchange('wrong','local')
        with self.assertRaisesRegex(ValueError,'Too many'):
            sessions.exchange(sessions.issue(),'local')


if __name__=='__main__':unittest.main()
