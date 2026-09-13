import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import collector as c

class Tests(unittest.TestCase):
    def test_cumulative_duplicate_cache_and_date(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'log.jsonl'
            today = dt.datetime.now().astimezone().replace(hour=12)
            yesterday = today-dt.timedelta(days=1)
            def event(stamp, i, o, cache):
                return {'timestamp': stamp.isoformat(), 'type':'event_msg', 'payload': {'type':'token_count', 'info':{'total_token_usage':dict(input_tokens=i,output_tokens=o,cached_input_tokens=cache)}}}
            p.write_text('\n'.join(map(json.dumps, [event(yesterday,100,20,50),event(today,150,30,70),event(today,150,30,70)])))
            result = c.parse_log(p)['days'][today.date().isoformat()]
            self.assertEqual(result, dict(input_tokens=50,output_tokens=10,cached_input_tokens=20))
            self.assertEqual(result['input_tokens']+result['output_tokens'],60)
    def test_api_failure_keeps_last_value(self):
        with tempfile.TemporaryDirectory() as d, patch.object(c,'CONFIG',Path(d)), patch.object(c,'CACHE',Path(d)):
            key = Path(d)/'admin-key'
            key.write_text('test-only')
            key.chmod(0o600)
            c.save(Path(d)/'api.json',dict(key_id=c.key_id('test-only'),display_usd=12.5,updated=123,attempt=0))
            with patch.object(c,'query',side_effect=urllib.error.HTTPError('',403,'',{},None)):
                result = c.api(True)
            self.assertEqual(result['display_usd'],12.5)
            self.assertEqual(result['updated'],123)
            self.assertEqual(result['error'],'HTTP 403')
    def test_pagination(self):
        import io
        pages = [io.StringIO(json.dumps({'data':[{'results':[{'x':1}]}],'has_more':True,'next_page':'second'})),io.StringIO(json.dumps({'data':[{'results':[{'x':2}]}],'has_more':False}))]
        with patch.object(c.urllib.request,'build_opener') as factory:
            factory.return_value.open.side_effect = pages
            self.assertEqual(c.query('costs','test',1,2),[{'x':1},{'x':2}])
            self.assertIn('page=second',factory.return_value.open.call_args.args[0].full_url)
    def test_missing_key(self):
        with tempfile.TemporaryDirectory() as d, patch.object(c,'CONFIG',Path(d)):
            self.assertEqual(c.api()['status'],'unconfigured')

if __name__ == '__main__': unittest.main()
