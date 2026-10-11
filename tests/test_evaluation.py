import json
import pytest
from local_asset_library.evaluation import (relevance_metrics, ordered_queries, percentile, verify_freeze,
                                            filter_violations, expansion_gate)
from local_asset_library.captions import file_hash
from local_asset_library.config import ConfigError


def test_graded_metrics_and_negative_pool():
    perfect = relevance_metrics(['a','b'],{'a':3,'b':2,'c':0})
    assert perfect['hit5']==1 and perfect['ndcg5']==1 and perfect['reciprocal_rank5']==1
    worse = relevance_metrics(['c','b'],{'a':3,'b':2,'c':0})
    assert worse['hit5']==1 and 0<worse['ndcg5']<1 and worse['reciprocal_rank5']==.5
    negative = relevance_metrics(['a'],{'a':0})
    assert negative['hit5'] is None and negative['ndcg5'] is None
    with pytest.raises(ConfigError):
        relevance_metrics(['a','a'],{'a':3})
    with pytest.raises(ConfigError):
        relevance_metrics(['unjudged'],{'a':3})


def test_held_out_last_and_nearest_rank_p95():
    assert [q['id'] for q in ordered_queries([{'id':'h','split':'held_out'},{'id':'d','split':'development'}])]==['d','h']
    assert percentile(list(range(1,21)))==19
    assert percentile([]) is None


def test_freeze_tamper_rejected(tmp_path):
    (tmp_path/'docs/evaluation').mkdir(parents=True)
    data=tmp_path/'queries.json'
    data.write_text('frozen')
    (tmp_path/'docs/evaluation/freeze.json').write_text(json.dumps({'before_competing_rankings':True,'files':{'queries.json':file_hash(data)}}))
    verify_freeze(tmp_path)
    data.write_text('changed')
    with pytest.raises(ConfigError,match='changed'):
        verify_freeze(tmp_path)


def test_filters_independently_check_evidence():
    records={'a':{'pack_id':'p','files':[{'format':'obj','availability':'available','sha256':'hash'}]}}
    result={'results':[{'asset_id':'a'}]}
    assert not filter_violations(result,{'filters':{'pack':'p','format':'obj'}},records)
    assert len(filter_violations(result,{'filters':{'pack':'wrong','format':'fbx'}},records))==2
    records['a']['files'][0]['availability']='missing'
    assert filter_violations(result,{'filters':{'format':'obj'}},records)


def test_provisional_gate_cannot_authorize_expansion():
    natural=lambda h:{'queries':10,'successful_evaluations':10,'hit5':h}
    baseline={'natural':natural(.5),'exact_success_ids':['E1','E2']}
    combined={'natural':natural(.8),'exact_success_ids':['E1'],'filter_violations':0,'failures':0,'warm_p95_seconds':1.5}
    protocol={'acceptance':{'natural_language_hit5_improvement_percentage_points':10,'maximum_exact_name_successes_lost':1,
                           'verified_filter_violations_allowed':0,'warm_combined_p95_seconds_strictly_below':2}}
    value=expansion_gate({'keyword':baseline,'combined':combined},protocol,'provisional_model_generated')
    assert value['status']=='provisional' and value['conditional_arithmetic']=='pass' and not value['step7_authorized']
    combined['warm_p95_seconds']=2
    assert expansion_gate({'keyword':baseline,'combined':combined},protocol,'owner_reviewed')['conditional_arithmetic']=='fail'
