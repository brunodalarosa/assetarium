"""MCP policy tests reuse explicit synthetic pilot fixtures, never production assets."""
from copy import deepcopy
import json
import sqlite3

import pytest
from PIL import Image
from test_retrieval import indexed
from local_asset_library.catalog import encoded
from local_asset_library.config import ConfigError
from local_asset_library.mcp_assets import AssetService, validate, bounded


@pytest.mark.parametrize('name,args',[
 ('get_asset',{'asset_id':'../secret'}),('get_asset',{'asset_id':'C:\\secret.glb'}),
 ('get_asset',{'asset_id':'asset_'+'a'*32,'path':'../x'}),
 ('get_asset',{'asset_id':'asset_'+'a'*32,'include_preview':'true'}),
 ('search_assets',{'query':''}),('search_assets',{'query':'x'*1025}),
 ('search_assets',{'query':'chair','limit':True}),('search_assets',{'query':'chair','limit':6}),
 ('search_assets',{'query':'chair','filters':{'color':'red'}}),
 ('search_assets',{'query':'chair','filters':{'format':'../obj'}}),
 ('search_assets',{'query':'chair','filters':{'pack':'../pack'}}),
 ('search_assets',{'query':'chair','filters':{'rigged':1}}),
 ('search_assets',{'mode':'reference','reference_asset_id':'/tmp/image.png'}),
 ('search_assets',{'query':'chair','reference_view':'side'}),
 ('unknown',{}),('search_assets',{'query':'chair','filters':[]}),
 ('get_asset',{'asset_id':'asset_'+'a'*32+'\n'})])
def test_malformed_arguments(name,args):
    with pytest.raises(ConfigError): validate(name,args)


def update(config,record):
    with sqlite3.connect(config.output_path('data','catalog.sqlite')) as db:
        db.execute('UPDATE assets SET record=? WHERE asset_id=?',(encoded(record),record['asset_id']))


def test_compact_search_and_opt_in_detail(indexed):
    config,backend,records=indexed
    service=AssetService(config,backend=backend)
    result,image,evidence=service.execute('search_assets',{'query':'red object'})
    assert len(result['results'])==5 and len(encoded(result))<=6000 and image is None
    assert result['serialized_characters']==len(encoded(result))
    assert str(config.source_root) not in encoded(result)
    selected=result['results'][0]['asset_id']
    detail,_,_=service.execute('get_asset',{'asset_id':selected,'source_format':'obj'})
    assert detail['usable'] and 'metadata' not in detail and detail['preview']['status']=='not_requested'
    assert detail['selected_source']['resolved_path'].startswith(str(config.source_root))


@pytest.mark.parametrize('kind',['stale','missing','root_escape','dependency_escape','dependency_missing'])
def test_unavailable_sources_not_usable(indexed,kind):
    config,backend,records=indexed
    record=deepcopy(records[0])
    if kind=='stale': config.source_file(record['files'][0]['path']).write_bytes(b'changed')
    elif kind=='missing': config.source_file(record['files'][0]['path']).unlink()
    elif kind=='root_escape': record['files'][0]['path']='../outside.obj'
    elif kind=='dependency_escape': record['dependencies']=[{'path':'../secret','status':'available','sha256':'0'*64}]
    else: record['dependencies']=[{'path':'missing.mtl','status':'missing','sha256':None}]
    update(config,record)
    service=AssetService(config,backend=backend)
    with pytest.raises((ConfigError,OSError)): service.execute('get_asset',{'asset_id':record['asset_id']})
    result,_,evidence=service.execute('search_assets',{'query':'item00','mode':'keyword'})
    assert not result['results'] and result['fault_count'] and evidence['excluded']


def test_preview_pixels_and_fault_preserves_detail(indexed):
    config,backend,records=indexed
    record=deepcopy(records[0])
    from local_asset_library.captions import file_hash
    path=config.output_path('data','preview.png')
    Image.new('RGB',(800,600),'red').save(path)
    record['previews']=[{'path':'data/preview.png','view_label':'three_quarter','sha256':file_hash(path)}]
    update(config,record)
    service=AssetService(config)
    response,image,_=service.execute('get_asset',{'asset_id':record['asset_id'],'include_preview':True})
    assert image and response['preview']['dimensions']==[512,384]
    path.write_bytes(b'stale')
    response,image,evidence=service.execute('get_asset',{'asset_id':record['asset_id'],'include_preview':True})
    assert response['usable'] and image is None and response['preview']['status']=='faulty'
    assert evidence['excluded']


def test_unknown_and_nonpilot_ids(indexed):
    config,_,_=indexed
    with pytest.raises(ConfigError): AssetService(config).execute('get_asset',{'asset_id':'asset_'+'f'*32})


def test_response_overflow_fails_closed():
    with pytest.raises(ConfigError): bounded({'dependencies':['x'*17000],'usable':True},16000)


def test_fault_output_bounded_for_arbitrary_malformed_id():
    from local_asset_library.mcp_assets import error_payload
    result=error_payload(ConfigError('bad input'),'x'*100000)
    assert result['asset_id'] is None and len(encoded(result))<=6000


def test_inference_fault_not_retried(indexed):
    config,backend,_=indexed
    backend.failure='explicit synthetic inference failure'
    service=AssetService(config,backend=backend)
    args={'query':'red object'}
    with pytest.raises(RuntimeError): service.execute('search_assets',args)
    before=len(backend.calls)
    with pytest.raises(ConfigError): service.execute('search_assets',args)
    assert len(backend.calls)==before
