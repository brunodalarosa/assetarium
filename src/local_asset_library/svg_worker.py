"""Isolated SVG rasterizer: SVG text on stdin, PNG bytes on stdout; no project imports.

Run with ``python -I`` under a timeout. The caller has already refused external
references; resvg never executes scripts. Arguments: one JSON object with
``width``, ``height``, optional ``view_box`` [x, y, w, h] and ``system_fonts``.
"""
import json
import sys
import xml.etree.ElementTree as ElementTree


def main():
    job = json.loads(sys.argv[1])
    width, height = int(job['width']), int(job['height'])
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise SystemExit('Render size out of bounds')
    text = sys.stdin.buffer.read().decode('utf-8')
    if job.get('view_box'):
        root = ElementTree.fromstring(text)
        root.set('viewBox', ' '.join(repr(float(v)) for v in job['view_box']))
        root.set('width', str(width))
        root.set('height', str(height))
        root.set('preserveAspectRatio', 'none')
        text = ElementTree.tostring(root, encoding='unicode')
    import resvg_py
    blob = resvg_py.svg_to_bytes(svg_string=text, width=width, height=height,
                                 skip_system_fonts=not job.get('system_fonts'), resources_dir=None)
    sys.stdout.buffer.write(bytes(blob))


if __name__ == '__main__':
    main()
