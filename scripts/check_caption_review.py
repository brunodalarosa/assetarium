"""Validate all local review links and visible faults against the real pilot."""
from html.parser import HTMLParser
from pathlib import Path
import uuid
from local_asset_library.catalog import save_json
from local_asset_library.captions import file_hash
from local_asset_library.config import load_config
from local_asset_library.retrieval import pilot_records
from local_asset_library.caption_review import check_severity_banners

root = Path(__file__).resolve().parents[1]
path = root / "data/captions/review/pilot-v2.html"
config = load_config(root / "config.example.toml", root)
records = pilot_records(config)
refs = []
images = []
class ReviewParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"}:
                refs.append(value)
            if tag == "img" and key == "src":
                images.append(value)
page = path.read_text(encoding="utf-8")
ReviewParser().feed(page)
expected_images = sum(len((r.get("caption_provenance") or {}).get("input_views", [])) for r in records)
assert len(images) == expected_images and len(set(images)) == expected_images
assert len(refs) == 2 * expected_images + len(records)
for reference in refs:
    resolved = (path.parent / reference).resolve()
    assert resolved.is_relative_to(root / "data") and resolved.is_file()
result = {"html_sha256": file_hash(path), "input_images": len(images),
          "local_references": len(refs), "all_links_valid": True,
          **check_severity_banners(config, page, records)}
save_json(root / "data/evidence" / ("caption-review-check-" + uuid.uuid4().hex + ".json"), result)
print(result)
