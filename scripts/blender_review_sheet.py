"""Combine only generated project PNGs for technical image review; no model load."""

import json
from pathlib import Path
import sys

import bpy
import numpy as np

root = Path(__file__).resolve().parents[1]
phase = sys.argv[sys.argv.index("--") + 1]
if phase not in {"representatives", "pilot"}:
    raise ValueError("Invalid review phase")
report_path = (root / "data/inspection" / (phase + "-report.json")).resolve()
if not report_path.is_relative_to(root / "data"):
    raise ValueError("Escaping review report")
report = json.loads(report_path.read_text(encoding="utf-8"))
entries = []
for outcome in report["outcomes"]:
    if outcome["status"] != "complete":
        continue
    result_path = (root / outcome["result_path"]).resolve()
    if not result_path.is_relative_to(root / "data"):
        raise ValueError("Escaping result record")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    for view in result["previews"]:
        if phase == "pilot" and view["view_label"] != "three_quarter":
            continue
        image_path = (result_path.parent / view["filename"]).resolve()
        if not image_path.is_relative_to(root / "data"):
            raise ValueError("Escaping generated image")
        entries.append({"asset_id": outcome["asset_id"], "name": outcome["name"], "pack": outcome["pack"],
                        "view": view["view_label"], "path": image_path.relative_to(root).as_posix()})
columns = 3 if phase == "representatives" else 8
rows = (len(entries) + columns - 1) // columns
size = 320
pixels = np.full((rows * size, columns * size, 4), 0.32, dtype=np.float32)
pixels[:, :, 3] = 1
for index, entry in enumerate(entries):
    image = bpy.data.images.load(str(root / entry["path"]), check_existing=False)
    image.scale(size, size)
    buffer = np.empty(size * size * 4, dtype=np.float32)
    image.pixels.foreach_get(buffer)
    y, x = divmod(index, columns)
    entry.update(row_from_top=y + 1, column_from_left=x + 1)
    bottom = (rows - y - 1) * size
    pixels[bottom:bottom + size, x * size:(x + 1) * size] = buffer.reshape(size, size, 4)
    bpy.data.images.remove(image)
scene = bpy.context.scene
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.view_settings.exposure = 0
scene.view_settings.gamma = 1
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
target = (root / "data/inspection/review").resolve()
if not target.is_relative_to(root / "data"):
    raise ValueError("Escaping sheet destination")
target.mkdir(parents=True, exist_ok=True)
sheet = bpy.data.images.new("ReviewSheet", width=columns * size, height=rows * size, float_buffer=False)
sheet.pixels.foreach_set(pixels.ravel())
sheet.save_render(str(target / (phase + ".png")), scene=scene)
(target / (phase + "-grid-map.json")).write_text(json.dumps({"columns": columns, "rows": rows, "entries": entries}, indent=2), encoding="utf-8")
print("REVIEW_SHEET=" + str(target / (phase + ".png")))
