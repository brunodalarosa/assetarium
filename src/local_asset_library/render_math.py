"""Pure framing calculations, shared by the Blender worker and fixture tests."""

import math
from itertools import product

VIEWS = {"front": (0, -1, 0.25), "side": (1, 0, 0.25),
         "three_quarter": (1, -1, 0.9), "top": (0, 0, 1)}


def normalized(vector):
    length = math.sqrt(sum(v * v for v in vector))
    if length <= 1e-12:
        raise ValueError("Zero-length camera direction")
    return tuple(v / length for v in vector)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def framing(minimum, maximum, margin=0.16):
    if not 0.05 <= margin <= 0.4 or any(not math.isfinite(v) for v in (*minimum, *maximum)):
        raise ValueError("Invalid framing bounds or margin")
    extent = tuple(high - low for low, high in zip(minimum, maximum))
    if min(extent) < 0 or max(extent) <= 1e-8:
        raise ValueError("Empty or degenerate model bounds")
    center = tuple((low + high) / 2 for low, high in zip(minimum, maximum))
    radius = math.sqrt(sum(e * e for e in extent)) / 2
    views = ["front", "side", "three_quarter"]
    if extent[2] < max(extent[:2]) * 0.18:
        views.append("top")
    corners = list(product(*zip(minimum, maximum)))
    projected = {}
    for name in views:
        outward = normalized(VIEWS[name])
        forward = tuple(-v for v in outward)
        up_reference = (0, 1, 0) if name == "top" else (0, 0, 1)
        right = normalized(cross(forward, up_reference))
        up = normalized(cross(right, forward))
        points = [(dot(tuple(c[i] - center[i] for i in range(3)), right),
                   dot(tuple(c[i] - center[i] for i in range(3)), up)) for c in corners]
        width = max(p[0] for p in points) - min(p[0] for p in points)
        height = max(p[1] for p in points) - min(p[1] for p in points)
        projected[name] = {"width": width, "height": height, "outward": outward}
    scale = max(max(p["width"], p["height"]) for p in projected.values()) / (1 - 2 * margin)
    return {"center": center, "extent": extent, "radius": radius, "ortho_scale": scale,
            "margin": margin, "views": projected}


def duplicate_faces(vertices, faces):
    """Count extra faces with exactly identical vertex positions, ignoring winding."""
    seen = set()
    count = 0
    for face in faces:
        key = tuple(sorted(tuple(vertices[index]) for index in face))
        if key in seen:
            count += 1
        seen.add(key)
    return count
