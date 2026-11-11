import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import claude_status


class ClaudeStatusTest(unittest.TestCase):
    def test_normalizes_subscription_windows(self):
        data = {'rate_limits': {'five_hour': {'used_percentage': 23.5, 'resets_at': 3000},
                                'seven_day': {'used_percentage': 41.2, 'resets_at': 9000}}}
        windows = claude_status.normalize(data, 1000)['buckets'][0]['windows']
        self.assertEqual([w['remaining'] for w in windows], [76.5, 58.8])
        self.assertEqual([w['minutes'] for w in windows], [300, 10080])

    def test_missing_expired_and_invalid_windows_are_not_fabricated(self):
        self.assertIsNone(claude_status.normalize({}, 1000))
        for value, reset in [(5, 1000), (True, 3000), (float('nan'), 3000), (10, None)]:
            self.assertIsNone(claude_status.normalize({'rate_limits': {'five_hour': {
                'used_percentage': value, 'resets_at': reset}}}, 1000))
        self.assertEqual(claude_status.normalize({'rate_limits': {'seven_day': {
            'used_percentage': 105, 'resets_at': 3000}}}, 1000)['buckets'][0]['windows'][0]['remaining'], 0)

    def test_script_stores_only_aggregate_limits_and_keeps_previous_on_missing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, XDG_CACHE_HOME=tmp)
            payload = {'prompt': 'private', 'rate_limits': {'five_hour': {
                'used_percentage': 45, 'resets_at': 4000000000}}}
            result = subprocess.run([sys.executable, claude_status.__file__], input=json.dumps(payload),
                                    text=True, capture_output=True, env=env, check=True)
            self.assertIn('55%', result.stdout)
            path = Path(tmp)/'ai-usage-panel/claude.json'
            before = path.read_text()
            self.assertNotIn('private', before)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            subprocess.run([sys.executable, claude_status.__file__], input='{}', text=True,
                           capture_output=True, env=env, check=True)
            self.assertEqual(path.read_text(), before)


if __name__ == '__main__':
    unittest.main()
