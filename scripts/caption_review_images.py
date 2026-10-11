"""Local review mosaics of actual caption inputs, never model prompt images."""
from pathlib import Path
import json
import sys
from PIL import Image, ImageDraw
from local_asset_library.config import load_config
from local_asset_library.catalog import detail

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
phase = sys.argv[1]
report = json.loads((root / f"data/captions/{phase}-report.json").read_text(encoding="utf-8"))
target = root / "data/captions/review"
target.mkdir(parents=True, exist_ok=True)
for offset in range(0, len(report["outcomes"]), 4):
    outcomes = report["outcomes"][offset:offset+4]
    sheet = Image.new("RGB", (1280, len(outcomes)*348), (235,235,235))
    draw = ImageDraw.Draw(sheet)
    for row, outcome in enumerate(outcomes):
        result_path = root / f"data/captions/{phase}/{outcome['asset_id']}.json"
        if not result_path.exists():
            result_path = root / detail(config, outcome["asset_id"])["caption_provenance"]["result_path"]
        result = json.loads(result_path.read_text(encoding="utf-8"))
        for col, view in enumerate(result["provenance"]["input_views"]):
            if col >= 4:
                raise AssertionError("Add mosaic columns for new extra views")
            with Image.open(root / view["path"]) as source:
                rgba = source.convert("RGBA")
                bg = Image.new("RGBA", rgba.size, (82,82,82,255))
                actual = Image.alpha_composite(bg, rgba).convert("RGB")
                actual.thumbnail((320,320), Image.Resampling.LANCZOS)
                sheet.paste(actual, (col*320, row*348+28))
            draw.text((col*320+4, row*348+8), f"{offset+row+1} {outcome['name']} / {view['view_label']}", fill="black")
    path = target / f"{phase}-views-{offset//4+1}.jpg"
    sheet.save(path, quality=92)
    print(path)
