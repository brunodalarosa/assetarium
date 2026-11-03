"""Generate tiny, valid practice packs from scratch, without Blender or downloads."""
from pathlib import Path
import struct
import zlib


def generate(folder):
    """Write only into a new empty destination; return the generated relative file names."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    paths = []

    def put(name, content):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode('utf-8') if isinstance(content, str) else content)
        paths.append(name)

    mesh = 'o {name}\nv 0 0 0\nv {size} 0 0\nv 0 1 0\nf 1 2 3\n'
    for pack in ('Village Props', 'Castle Kit', 'Terrain Pack', 'Hero Pack', 'Rock Pack'):
        put(pack + '/License.txt', 'Assetarium generated practice assets. CC0 1.0.\n')
    for i, name in enumerate(('Barrel', 'Crate', 'Lamp')):
        obj = mesh.format(name=name, size=i + 1)
        for target in ('Models', 'Unity Models'):
            put(f'Village Props/{target}/{name}.obj', obj)
        put(f'Castle Kit/v1.2/Models/{name}.obj', obj)
    for i in range(1, 7):
        put(f'Rock Pack/Rocks/Rock_{i:02}.obj', mesh.format(name=f'Rock_{i:02}', size=i + 4))
    # Valid RGB PNGs. Generic Art folders leave the classification for the agent to review.
    def png(color):
        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
        pixels = b''.join(b'\0' + bytes(color) * 4 for _ in range(4))
        return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')
    for pack, stem, color in (('Terrain Pack', 'Ground', (80, 120, 60)), ('Hero Pack', 'Hero_Run', (40, 100, 200))):
        for i in range(1, 13):
            put(f'{pack}/Art/{stem}_{i:02}.png', png(tuple(min(255, c + i) for c in color)))
        put(f'{pack}/Models/Prop.obj', mesh.format(name=pack.replace(' ', '_'), size=20 if stem == 'Ground' else 21))
    return paths
