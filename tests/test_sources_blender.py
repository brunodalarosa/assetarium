"""Actual Blender boundary/render verification with tiny synthetic originals."""
import hashlib
import json
from pathlib import Path

from test_blender_integration import small_fixture, WORKER
from local_asset_library.inspection import blender_command,environment,run_process


def test_blender_renders_into_source_metadata_and_preserves_original(small_fixture):
    config=small_fixture
    source=config.source_root/'cube.obj'
    source.write_text('v -1 -1 -1\nv 1 -1 -1\nv 1 1 -1\nv -1 1 -1\nv -1 -1 1\nv 1 -1 1\nv 1 1 1\nv -1 1 1\nf 1 4 3 2\nf 5 6 7 8\nf 1 2 6 5\nf 2 3 7 6\nf 3 4 8 7\nf 4 1 5 8\n')
    before=source.read_bytes()
    metadata=config.source_root/'metadata-lal';output=metadata/'inspection/fixture';output.mkdir(parents=True)
    job={'asset_id':'fixture','project_root':str(config.project_root),'source_root':str(config.source_root),
         'source_prefix':'source-key','metadata_root':str(metadata),'source_path':'source-key/cube.obj',
         'source_sha256':hashlib.sha256(before).hexdigest(),'format':'obj','output':str(output),'resolution':320}
    task=output/'job.json';task.write_text(json.dumps(job),encoding='utf-8')
    completed=run_process(blender_command(config.blender,'--python-exit-code','5','--python',str(WORKER),'--',str(task)),
        config.project_root,environment(config),90)
    assert completed['returncode']==0,completed['output']
    result=json.loads((output/'result.json').read_text())
    assert result['status']=='complete' and len(result['previews'])>=3
    assert result['source_path']=='source-key/cube.obj'
    assert source.read_bytes()==before
