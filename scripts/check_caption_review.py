"""Validate all local review links and visible faults against the real pilot."""
from html.parser import HTMLParser
from pathlib import Path
from local_asset_library.catalog import save_json
from local_asset_library.captions import file_hash

root = Path(__file__).resolve().parents[1]
path = root / "data/captions/review/pilot-v2.html"
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
assert len(images) == 124 and len(set(images)) == 124
assert len(refs) == 288
for reference in refs:
    resolved = (path.parent / reference).resolve()
    assert resolved.is_relative_to(root / "data") and resolved.is_file()
assert page.count("Caption visual claims: faulty") == 30
result = {"html_sha256": file_hash(path), "input_images": len(images),
          "local_references": len(refs), "visible_fault_banners": 30, "all_links_valid": True}
save_json(root / "data/evidence/step4-review-check.json", result)
print(result)
