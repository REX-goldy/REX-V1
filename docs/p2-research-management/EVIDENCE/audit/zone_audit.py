import json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from server import zone_store

def out(label, **kwargs):
    print(label, json.dumps(kwargs, default=str, sort_keys=True))

with tempfile.TemporaryDirectory() as td:
    path = Path(td)/'zones.json'
    with patch.dict(os.environ, {'REX_ZONES_FILE': str(path)}, clear=False):
        # created now, effective inside a past period
        past = zone_store.create_zone({
            'dataset_id':'EURUSD/M1/2026','source_timeframe':'H1','zone_type':'demand',
            'low':1.1000,'high':1.1050,'effective_timestamp':'2026-01-01T00:00:00Z',
            'invalidation_timestamp':None,'strength':7,'notes':'created after the historical period',
        })
        future = zone_store.create_zone({
            'dataset_id':'EURUSD/M1/2026','source_timeframe':'H1','zone_type':'supply',
            'low':1.2000,'high':1.2050,'effective_timestamp':'2026-06-01T00:00:00Z',
            'strength':7,
        })
        invalidated = zone_store.create_zone({
            'dataset_id':'EURUSD/M1/2026','source_timeframe':'H1','zone_type':'demand',
            'low':1.3000,'high':1.3050,'effective_timestamp':'2026-01-01T00:00:00Z',
            'invalidation_timestamp':'2026-02-01T00:00:00Z','strength':7,
        })
        books = zone_store.build_zone_books(start=datetime(2026,1,15), end=datetime(2026,1,20))
        manual = [z for z in books['EURUSD'].zones if z.low >= 1.1 and z.low < 1.5]
        out('created_after_period_included', zone_ids=[z.name for z in manual], current_created=past['created_at'], run_start='2026-01-15')
        books2 = zone_store.build_zone_books(start=datetime(2026,1,15), end=datetime(2026,1,20), zone_ids=[future['id']])
        out('selected_future_zone_excluded', has_eurusd='EURUSD' in books2, zones=len(books2.get('EURUSD', zone_store.ZoneBook('EURUSD',())).zones))
        books3 = zone_store.build_zone_books(start=datetime(2026,1,15), end=datetime(2026,1,20), zone_ids=[invalidated['id']])
        out('selected_invalidated_during_run_excluded', has_eurusd='EURUSD' in books3, zones=len(books3.get('EURUSD', zone_store.ZoneBook('EURUSD',())).zones))
        # version behavior
        updated = zone_store.update_zone(past['id'], {'low':1.1100,'high':1.1150})
        before_version = updated['versions'][0]
        out('version_history', version=updated['version'], versions=len(updated['versions']), previous_low=before_version['low'], current_low=updated['low'])
        # timezone comparison aware start
        books4 = zone_store.build_zone_books(start=datetime(2026,1,15,tzinfo=timezone.utc), end=datetime(2026,1,20,tzinfo=timezone.utc))
        out('timezone_aware_comparison', has_eurusd='EURUSD' in books4, zones=len(books4.get('EURUSD', zone_store.ZoneBook('EURUSD',())).zones))
