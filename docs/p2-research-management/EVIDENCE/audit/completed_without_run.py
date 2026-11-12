import os, tempfile
from pathlib import Path
from unittest.mock import patch
from server import strategy_workspace as ws
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    with patch.dict(os.environ, {'REX_WORKSPACE_FILE':str(root/'workspace.json'),'REX_RUNS_DIR':str(root/'runs')}, clear=False):
        s008=next(x for x in ws.list_strategies() if x['registry_strategy_id']=='S008')
        d=ws.get_strategy(s008['id']); v=d['variations'][0]
        planned=ws.create_planned_experiment(s008['id'], {'variation_id':v['id'],'dataset_id':'EURUSD/M1/2026','timeframe':'M1','name':'planned'})
        e=planned['experiments'][0]
        completed=ws.update_experiment(s008['id'], e['id'], {'status':'Completed'})
        c=completed['experiments'][0]
        print('completed_without_run', c['status'], c['run_id'], None)
