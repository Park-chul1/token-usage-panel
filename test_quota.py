import decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import collector as c
import quota

class Tests(unittest.TestCase):
    def test_remaining_and_model_specific_buckets(self):
        w = {'usedPercent':25, 'windowDurationMins':300, 'resetsAt':2000000000}
        data = quota.normalize({'rateLimitsByLimitId': {
            'spark': {'primary':w}, 'codex': {'primary':w,'secondary':{**w,'usedPercent':100,'windowDurationMins':10080}}}})
        self.assertEqual(data[0]['id'],'codex')
        self.assertEqual(data[0]['windows'][0]['remaining'],75)
        self.assertEqual(data[0]['windows'][1]['remaining'],0)
    def test_missing_percentage_is_not_zero(self):
        with self.assertRaises(ValueError):
            quota.normalize({'rateLimits':{'primary':{'resetsAt':2000}}})
    def test_protocol_handshake_no_model_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'fake-codex'
            p.write_text('''#!/usr/bin/env python3
import sys,json
for line in sys.stdin:
 m=json.loads(line)
 with open('calls','a') as f: f.write(m['method']+'\\n')
 if m['method']=='initialize': print(json.dumps({'id':m['id'],'result':{}}),flush=True)
 elif m['method']=='account/rateLimits/read': print(json.dumps({'id':m['id'],'result':{'rateLimits':{'primary':{'usedPercent':22,'resetsAt':2000000000,'windowDurationMins':300}}}}),flush=True)
''')
            p.chmod(0o755)
            data = quota.fetch_limits(str(p),directory,timeout=3)
            self.assertEqual(quota.normalize(data)[0]['windows'][0]['remaining'],78)
            self.assertEqual((Path(directory)/'calls').read_text().splitlines(),['initialize','initialized','account/rateLimits/read'])
    def test_protocol_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'fake-codex'
            p.write_text('#!/usr/bin/env python3\nimport time\ntime.sleep(10)\n')
            p.chmod(0o755)
            with self.assertRaises(TimeoutError): quota.fetch_limits(str(p),directory,timeout=0.05)
    def test_reset_and_monthly_spend_stay_separate(self):
        with tempfile.TemporaryDirectory() as d, patch.object(c,'CONFIG',Path(d)), patch.object(c,'CACHE',Path(d)):
            key = Path(d)/'admin-key'; key.write_text('test'); key.chmod(0o600)
            with patch.object(c,'cost_sum', return_value=decimal.Decimal('2.10')):
                self.assertTrue(c.reset_api()['ok'])
            with patch.object(c,'cost_sum', side_effect=map(decimal.Decimal,['15','5','5.30'])), patch.object(c,'query',return_value=[]):
                result = c.api(True)
            self.assertEqual(result['month_usd'],15)
            self.assertEqual(result['display_usd'],3.2)
            self.assertEqual(result['display_period'],'since_reset')
    def test_failed_reset_preserves_previous_baseline(self):
        with tempfile.TemporaryDirectory() as d, patch.object(c,'CONFIG',Path(d)), patch.object(c,'CACHE',Path(d)):
            key = Path(d)/'admin-key'; key.write_text('test'); key.chmod(0o600)
            c.save(Path(d)/'api-reset.json', {'id':'original'})
            with patch.object(c,'cost_sum', side_effect=RuntimeError()):
                self.assertFalse(c.reset_api()['ok'])
            self.assertEqual(c.read(Path(d)/'api-reset.json',{}),{'id':'original'})
    def test_key_change_ignores_old_reset(self):
        with tempfile.TemporaryDirectory() as d, patch.object(c,'CONFIG',Path(d)), patch.object(c,'CACHE',Path(d)):
            key = Path(d)/'admin-key'; key.write_text('new'); key.chmod(0o600)
            c.save(Path(d)/'api-reset.json',dict(id='old',key_id=c.key_id('old')))
            with patch.object(c,'cost_sum',return_value=decimal.Decimal('9')), patch.object(c,'query',return_value=[]):
                result=c.api(True)
            self.assertEqual(result['display_period'],'month')
            self.assertEqual(result['display_usd'],9)

if __name__ == '__main__': unittest.main()
