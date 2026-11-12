import json, os, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, 'tests')
from test_p2_experiments import _run, RUN_ID
from server import strategy_workspace as ws
from server import zone_store

with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'runs').mkdir()
    (root/'runs'/f'{RUN_ID}.json').write_text(json.dumps(_run()))
    with patch.dict(os.environ, {
        'REX_WORKSPACE_FILE': str(root/'workspace.json'),
        'REX_RUNS_DIR': str(root/'runs'),
        'REX_ZONES_FILE': str(root/'zones.json'),
    }, clear=False):
        zone=zone_store.create_zone({
            'dataset_id':'EURUSD/M1/2026','source_timeframe':'H1','zone_type':'demand',
            'low':1.10,'high':1.11,'effective_timestamp':'2026-01-01T00:00:00Z','strength':7,
        })
        run=_run(); run['zone_ids']=[zone['id']]
        (root/'runs'/f'{RUN_ID}.json').write_text(json.dumps(run))
        s008=next(x for x in ws.list_strategies() if x['registry_strategy_id']=='S008')
        detail=ws.get_strategy(s008['id']); baseline=detail['variations'][0]
        detail=ws.record_experiment(s008['id'], {'variation_id':baseline['id'],'run_id':RUN_ID})
        exp=detail['experiments'][0]
        print('EXPERIMENT_SNAPSHOT_KEYS', json.dumps({k:exp[k] for k in ['status','dataset_hash','validation_status','cost_profile','gross_results','net_results']}, default=str)[:800])
        print('ZONE_SNAPSHOTS', json.dumps(exp['configuration'].get('zone_snapshots'), default=str))
        # update zone version
        updated=zone_store.update_zone(zone['id'], {'low':1.12,'high':1.13})
        print('ZONE_VERSION_AFTER_EDIT', updated['version'], updated['low'], updated['high'])
        # experiment stays at old snapshot
        detail2=ws.get_strategy(s008['id'])
        print('EXPERIMENT_ZONE_AFTER_EDIT', json.dumps(detail2['experiments'][0]['configuration'].get('zone_snapshots'), default=str))
        # completed experiment narrative mutation
        ws.update_experiment(s008['id'], exp['id'], {
            'notes':'AUDIT mutation', 'actual_outcome':'AUDIT outcome', 'hypothesis_supported':True,
        })
        changed=ws.get_strategy(s008['id'])['experiments'][0]
        print('COMPLETED_MUTABLE_FIELDS', changed['notes'], changed['actual_outcome'], changed['hypothesis_supported'])
        # baseline lock
        try:
            ws.update_variation(s008['id'], baseline['id'], {'title':'AUDIT baseline change'})
            print('BASELINE_UPDATE_ALLOWED', True)
        except Exception as e:
            print('BASELINE_UPDATE_ALLOWED', False, type(e).__name__, str(e))
        # strategy edit does not mutate experiment configuration
        before=json.dumps(ws.get_strategy(s008['id'])['experiments'][0]['configuration'], sort_keys=True)
        ws.update_strategy(s008['id'], {'hypothesis':'AUDIT strategy edit'})
        after=json.dumps(ws.get_strategy(s008['id'])['experiments'][0]['configuration'], sort_keys=True)
        print('STRATEGY_EDIT_MUTATED_EXPERIMENT_CONFIG', before != after)
        # reproduction surface
        print('HAS_REPRODUCE_ENDPOINT', False)
        print('ZONE_SNAPSHOT_USED_BY_RUN', 'zone_snapshots' in open('server/research_service.py').read())
