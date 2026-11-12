import os, tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from server import zone_store
with tempfile.TemporaryDirectory() as td:
    with patch.dict(os.environ, {'REX_ZONES_FILE':str(Path(td)/'zones.json')}, clear=False):
        z=zone_store.create_zone({'dataset_id':'EURUSD/M1/2026','source_timeframe':'H1','zone_type':'demand','low':1.10,'high':1.11,'effective_timestamp':'2026-01-01T00:00:00Z','invalidation_timestamp':'2026-01-18T00:00:00Z','strength':7})
        b=zone_store.build_zone_books(start=datetime(2026,1,15),end=datetime(2026,1,20))
        print('invalidated_during_run_excluded', 'EURUSD' not in b or not [x for x in b['EURUSD'].zones if x.low==1.10])
        b2=zone_store.build_zone_books(start=datetime(2026,1,15),end=datetime(2026,1,20),zone_ids=[z['id']])
        print('selected_invalidated_during_run_excluded', 'EURUSD' not in b2 or not [x for x in b2['EURUSD'].zones if x.low==1.10])
        # legacy static
        b3=zone_store.build_zone_books(start=datetime(2026,1,15),end=datetime(2026,1,20))
        print('legacy_present', any(x.source.value=='manual' and x.low==1.14 for x in b3['EURUSD'].zones))
