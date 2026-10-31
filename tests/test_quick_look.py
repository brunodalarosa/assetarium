"""Quick look for the Add library folder wizard: names only, verdicts, and a snapshot agents can use before the scan."""
from pathlib import Path
import time

import pytest

from test_sources import managed  # noqa: F401 -- fixtures
from local_asset_library import pack_agent, quick_look, sources
from local_asset_library.sources import Covered


def test_names_alone_give_packs_variants_series_and_export_pairs():
    paths = (['Kit_1.0/License.txt'] + [f'Kit_1.0/Cars/Car_11_{c}.fbx' for c in 'RGB'] + [f'Kit_1.0/Rocks/Rock_{n:02}.fbx' for n in range(1, 6)]
             + [f'Kit_1.0/{d}/{m}.fbx' for d in ('FBX', 'Unity FBX') for m in ('Barrel', 'Crate', 'Door')]
             + ['Loose/icon.png'])
    found = quick_look.summarize(paths, 'Library')
    kit = next(p for p in found['packs'] if p['pack'] == 'Kit_1.0')
    assert kit['models'] == 14 and kit['groups'] == 1 and kit['cards'] == 12 and kit['evidence'] == ['License.txt', 'Kit_1.0']
    assert kit['status'] == 'needs_structure' and 'names repeat in several folders' in kit['needs'][0]
    assert found['why'][0] == '“Kit_1.0” is a pack because of License.txt'
    assert 'Car_11_{B,G,R} became one card with 3 variants' in found['why']
    assert 'Rock_01…05 stay 5 separate assets (a numbered series)' in found['why']
    assert any('FBX and Unity FBX look like exports of the same models' in line for line in found['why'])


def wait_done(job):
    for _ in range(200):
        state = quick_look.status(job)
        if state['status'] != 'running':
            return state
        time.sleep(0.05)
    raise AssertionError('quick look did not finish')


def test_a_quick_look_reads_names_live_and_its_snapshot_serves_agents_before_the_scan(managed, tmp_path):
    config, _, one, _ = managed
    root = tmp_path / 'New Library'
    for name in ('Kit_1.0/License.txt', 'Kit_1.0/Cars/Car_A.obj', 'Kit_1.0/Cars/Car_B.obj', 'Other/Tree.obj'):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text('v 0 0 0\n')
    state = wait_done(quick_look.start(config, str(root))['job'])
    assert state['status'] == 'done' and state['files'] == 4 and [t['name'] for t in state['top']] == ['Kit_1.0', 'Other']
    assert state['top'][0]['markers'] == ['license', 'versioned_name'] and state['result']['counts']['fine'] == 2
    added = sources.add(config, str(root))
    job = next(k for k, v in quick_look._jobs.items() if v['path'] == added['path'])
    assert Path(quick_look.save(config, added, job)).exists()
    outline = pack_agent.outline(config, {'library_folder': added['key'], 'path': 'Kit_1.0/Cars'})
    assert outline['file_patterns'] == ['Car_{A,B}.obj (2)']
    assert pack_agent.counts(config, added['key']) == {'status': 'ready', 'total': 2, 'needs_structure': 0, 'suggestions': 0,
                                                             'waiting': 0, 'scanning': True}
    with pytest.raises(Covered):
        quick_look.start(config, str(Path(one['path'])))
