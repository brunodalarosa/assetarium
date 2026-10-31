"""Synthetic pack trees for Check my model (decision 0024): names only, made up, safe to publish.

Each family is one layout problem that packs from the internet really have, in several spellings. ``checks`` grade
the outcome (``model_check.score``). ``quick`` marks the first tree of each family, the short check the app runs.
"""


def _names(folder, stems, suffix='.fbx'):
    return [f'{folder}/{stem}{suffix}' for stem in stems]


PROPS = ['Barrel', 'Crate', 'Door', 'Lamp', 'Table', 'Bench']


def engine_copy(name, pack, keep, copy, items):
    paths = [f'{pack}/License.txt'] + _names(f'{pack}/{keep}', items) + _names(f'{pack}/{copy}', items)
    return {'family': 'engine_copy', 'name': name, 'paths': paths,
            'checks': [{'check': 'excluded', 'any_of': [f'{pack}/{copy}']}, {'check': 'kept', 'folder': f'{pack}/{keep}'},
                       {'check': 'cards', 'equals': len(items)}, {'check': 'settled'}]}


def material_folders(name, pack, materials, items):
    paths = [f'{pack}/readme.txt'] + [p for m in materials for p in _names(f'{pack}/{m}', items)]
    return {'family': 'material_folders', 'name': name, 'paths': paths,
            'checks': [{'check': 'kept', 'folder': f'{pack}/{m}'} for m in materials]
            + [{'check': 'cards', 'equals': len(materials) * len(items)}, {'check': 'settled'}]}


def oversized(name, pack, folder, base):
    letters = [f'{base}_{chr(65 + n)}' for n in range(26)]
    return {'family': 'oversized', 'name': name, 'paths': [f'{pack}/License.txt'] + _names(f'{pack}/{folder}', letters),
            'checks': [{'check': 'cards', 'equals': 26}, {'check': 'settled'}]}


def version_folder(name, pack, version, items):
    paths = [f'{pack}/License.txt'] + _names(f'{pack}/{version}/Models', items)
    return {'family': 'version_folder', 'name': name, 'paths': paths,
            'checks': [{'check': 'packs', 'equals': [pack]}, {'check': 'cards', 'equals': len(items)}, {'check': 'settled'}]}


def image_folder(name, pack, folder, stems, kind):
    paths = [f'{pack}/License.txt'] + _names(f'{pack}/Models', PROPS[:3]) + _names(f'{pack}/{folder}', stems, '.png')
    return {'family': 'image_kind_' + kind, 'name': name, 'paths': paths,
            'checks': [{'check': 'image_kind', 'folder': f'{pack}/{folder}', 'equals': kind}, {'check': 'settled'}]}


def colors(name, pack, folder, bases, values):
    stems = [f'{b}_{v}' for b in bases for v in values]
    return {'family': 'fine_variants', 'name': name, 'paths': [f'{pack}/License.txt'] + _names(f'{pack}/{folder}', stems),
            'checks': [{'check': 'cards', 'equals': len(bases)}, {'check': 'settled'}]}


def series(name, pack, folder, base, count):
    stems = [f'{base}_{n:02}' for n in range(1, count + 1)]
    return {'family': 'fine_series', 'name': name, 'paths': [f'{pack}/readme.md'] + _names(f'{pack}/{folder}', stems, '.obj'),
            'checks': [{'check': 'cards', 'equals': count}, {'check': 'settled'}]}


def trees():
    found = [
        engine_copy('unity-subfolder', 'Village Props', 'FBX', 'Unity FBX', PROPS[:4]),
        engine_copy('godot-subfolder', 'Dungeon Kit 2.0', 'Meshes', 'Godot', PROPS[1:5]),
        engine_copy('urp-subfolder', 'Harbor Pack', 'Models', 'URP', PROPS[:5]),
        engine_copy('unity-prefab-meshes', 'Farm Set', 'Source', 'Unity Prefab Meshes', PROPS[2:6]),
        engine_copy('fbx-unity-parens', 'Camp Kit', 'FBX', 'FBX(Unity)', PROPS[:3]),
        engine_copy('unreal-subfolder', 'Market Stalls', 'Models', 'Unreal', PROPS[1:4]),
        material_folders('wood-metal-stone', 'Furniture Pack', ['Wood', 'Metal', 'Stone'], ['Chair', 'Table', 'Stool']),
        material_folders('painted-rusty', 'Fence Kit', ['Painted', 'Rusty'], ['Post', 'Gate', 'Rail', 'Panel']),
        material_folders('day-night', 'Lamp Posts', ['Day', 'Night'], ['Lamp_Tall', 'Lamp_Short', 'Lamp_Wall']),
        material_folders('clean-dirty', 'Kitchen Set', ['Clean', 'Dirty'], ['Pot', 'Pan', 'Kettle']),
        oversized('alphabet-tiles', 'Floor Tiles', 'Tiles', 'Tile'),
        oversized('alphabet-signs', 'Road Signs', 'Signs', 'Sign'),
        oversized('alphabet-letters', 'Block Letters', 'Letters', 'Letter'),
        version_folder('version-subfolder', 'Castle Kit', 'v1.2', ['Wall', 'Tower', 'Gate']),
        version_folder('version-dotted', 'Ruins', 'Ruins_v2.0', ['Arch', 'Pillar', 'Stairs', 'Rubble']),
        version_folder('version-free', 'Space Station', 'Station_FREE', ['Module', 'Panel', 'Antenna']),
        version_folder('version-plain', 'Shipyard', 'v3.1.0', ['Hull', 'Mast', 'Crane']),
        image_folder('ground-maps', 'Terrain Pack', 'Art', [f'Ground_{n:02}' for n in range(1, 13)], 'texture'),
        image_folder('hero-sprites', 'Hero Pack', 'Art', [f'Hero_Run_{n:02}' for n in range(1, 13)], 'image'),
        image_folder('bark-maps', 'Forest Pack', 'Surfaces', [f'Bark_Seamless_{n:02}' for n in range(1, 13)], 'texture'),
        image_folder('menu-art', 'Menu Kit', 'Screens', [f'Menu_Screen_{n:02}' for n in range(1, 13)], 'image'),
        colors('car-colors', 'Car Pack', 'Cars', ['Car_01', 'Car_02', 'Car_03'], ['Red', 'Blue', 'Green']),
        colors('chair-materials', 'Seating', 'Chairs', ['Chair_Office', 'Chair_Dining'], ['Wood', 'Metal']),
        colors('tree-lods', 'Tree Pack', 'Trees', ['Oak', 'Pine', 'Birch'], ['LOD0', 'LOD1', 'LOD2']),
        series('rocks', 'Rock Pack', 'Rocks', 'Rock', 12),
        series('bushes', 'Garden Pack', 'Bushes', 'Bush', 8),
        series('crystals', 'Crystal Pack', 'Crystals', 'Crystal', 10),
    ]
    seen = set()
    for tree in found:
        tree['quick'] = tree['family'] not in seen
        seen.add(tree['family'])
    return found
