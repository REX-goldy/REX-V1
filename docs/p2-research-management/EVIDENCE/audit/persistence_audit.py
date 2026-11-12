import json, os, stat, tempfile, threading
from pathlib import Path
from unittest.mock import patch
from server import zone_store
from server import strategy_workspace as ws
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    with patch.dict(os.environ, {'REX_ZONES_FILE':str(root/'zones.json'),'REX_WORKSPACE_FILE':str(root/'workspace.json')}, clear=False):
        z=zone_store.create_zone({'dataset_id':'EURUSD/M1/2026','source_timeframe':'H1','zone_type':'demand','low':1.10,'high':1.11,'effective_timestamp':'2026-01-01T00:00:00Z','strength':7})
        print('zone_mode', oct(stat.S_IMODE((root/'zones.json').stat().st_mode)))
        errors=[]
        def update(i):
            try: zone_store.update_zone(z['id'], {'notes':f'thread-{i}','low':1.10+i/10000,'high':1.11+i/10000})
            except Exception as e: errors.append(repr(e))
        threads=[threading.Thread(target=update,args=(i,)) for i in range(8)]
        [t.start() for t in threads]; [t.join() for t in threads]
        data=json.loads((root/'zones.json').read_text()); print('thread_errors',len(errors),'valid_json',isinstance(data.get('zones'),list),'records',len(data.get('zones',[])))
        print('workspace_missing_fails_closed', end=' ')
        root.joinpath('workspace.json').write_text('{broken')
        try: ws.list_strategies(); print(False)
        except Exception as e: print(True,type(e).__name__)
        # referential missing zone snapshot is silently skipped in the helper
        print('missing_zone_snapshot_result', ws._zone_snapshots(['missing-zone']))
