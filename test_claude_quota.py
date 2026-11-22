import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import claude_quota
import collector


class ClaudeQuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name)
        self.clock = patch('claude_quota.time.time', return_value=1800000000)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.auth = patch('claude_quota.credentials', return_value='secret-test-token')
        self.token = self.auth.start()
        self.addCleanup(self.auth.stop)
        self.fetcher = patch('claude_quota.fetch', return_value={
            'five_hour': {'utilization': 23.5, 'resets_at': '2030-01-16T00:00:00Z'},
            'seven_day': {'utilization': 41.2, 'resets_at': '2030-01-20T00:00:00Z'}})
        self.fetch = self.fetcher.start()
        self.addCleanup(self.fetcher.stop)

    def poll(self, force=False):
        return claude_quota.poll(self.cache, collector.read, collector.save, force)

    def test_six_hour_interval_and_manual_refresh(self):
        first = self.poll()
        self.assertEqual(first['buckets'][0]['windows'][0]['remaining'], 76.5)
        self.now.return_value += 21599
        self.poll()
        self.assertEqual(self.fetch.call_count, 1)
        self.poll(force=True)
        self.assertEqual(self.fetch.call_count, 2)
        self.now.return_value += 21600
        self.poll()
        self.assertEqual(self.fetch.call_count, 3)
        self.assertNotIn('secret-test-token', (self.cache/'claude-poll.json').read_text())

    def test_429_blocks_manual_refresh_and_preserves_last_good_value(self):
        self.poll()
        self.now.return_value += 10
        self.fetch.side_effect = HTTPError('https://api.anthropic.com', 429, 'limit', {'Retry-After': '7200'}, None)
        error = self.poll(force=True)
        self.assertEqual(error['status'], 'error')
        self.assertEqual(error['buckets'][0]['windows'][0]['remaining'], 76.5)
        self.assertEqual(error['updated'], 1800000000)
        self.now.return_value += 3600
        self.poll(force=True)
        self.assertEqual(self.fetch.call_count, 2)
        self.now.return_value += 3600
        self.poll(force=True)
        self.assertEqual(self.fetch.call_count, 3)

    def test_switch_login_does_not_show_previous_account_or_force_poll(self):
        self.poll()
        self.now.return_value += 60
        self.token.return_value = 'different-token'
        current = self.poll()
        self.assertNotIn('buckets', current)
        self.assertEqual(self.fetch.call_count, 1)
        self.poll(force=True)
        self.assertEqual(self.fetch.call_count, 2)

    def test_invalid_data_does_not_invent_remaining_quota(self):
        for used, reset in [(True, '2030-01-16T00:00:00Z'), (None, None), (3, '2000-01-01T00:00:00Z')]:
            with self.assertRaises(ValueError):
                claude_quota.normalize({'five_hour': {'utilization': used, 'resets_at': reset}}, 1800000000)


if __name__ == '__main__':
    unittest.main()
