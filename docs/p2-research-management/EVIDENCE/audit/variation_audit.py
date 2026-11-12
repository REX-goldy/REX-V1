import json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'tests')
from test_p2_experiments import _run, RUN_ID
from server import strategy_workspace as ws
with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'runs').mkdir()
    run=_run(); run['id']=RUN_ID
    (root/'runs'/f'{RUN_ID}.json').write_text(json.dumps(run))
    with patch.dict(os.environ, {'REX_WORKSPACE_FILE':str(root/'workspace.json'),'REX_RUNS_DIR':str(root/'runs')}, clear=False):
        s008=next(x for x in ws.list_strategies() if x['registry_strategy_id']=='S008')
        detail=ws.get_strategy(s008['id'])
        created=ws.create_variation(s008['id'], {'title':'V-audit','parameter_config':{'lookback':11},'instruments':['EURUSD'],'timeframes':['M1']})
        variation=created['variations'][-1]
        detail=ws.record_experiment(s008['id'], {'variation_id':variation['id'],'run_id':RUN_ID})
        before=json.dumps(detail['experiments'][0]['configuration'],sort_keys=True)
        after=ws.update_variation(s008['id'], variation['id'], {'parameter_config':{'lookback':12}})
        config_after=json.dumps(after['experiments'][0]['configuration'],sort_keys=True)
        print('variation_edit_mutated_experiment', before != config_after)
        print('variation_version_after', next(v for v in after['variations'] if v['id']==variation['id'])['configuration_version'])
        archived=ws.archive_variation(s008['id'], variation['id'])
        print('archive_preserves_experiment', len(archived['experiments'])==1, archived['experiments'][0]['run_id'])
