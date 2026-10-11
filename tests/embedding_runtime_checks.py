"""Standalone checks inside the pinned multimodal environment, using real Pillow and model objects."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from local_asset_library.config import load_config, ConfigError
from local_asset_library.catalog import save_json
from local_asset_library.embedding_backend import EmbeddingBackend, prepare_image

root = Path(__file__).resolve().parents[1]
config = load_config(root / "config.example.toml", root)
work = config.output_path("scratch", "embedding-runtime-checks")
work.mkdir(parents=True, exist_ok=True)
for mode, color in (("RGBA", (255, 0, 0, 0)), ("RGB", (255, 0, 0)), ("L", 120)):
    path = work / (mode + ".png")
    Image.new(mode, (40, 32), color).save(path)
    actual = prepare_image(path)
    assert actual.mode == "RGB" and actual.size == (40, 32)
    if mode == "RGBA":
        assert actual.getpixel((0, 0)) == (82, 82, 82)
corrupt = work / "corrupt.png"
corrupt.write_bytes(b"invalid pixels")
try:
    prepare_image(corrupt)
except OSError:
    pass
else:
    raise AssertionError("Corrupt image accepted")
backend = EmbeddingBackend(config)
model_config = backend.model[0].model.config
assert model_config.audio_config is None and model_config.vision_config is not None
parameters = sum(p.numel() for p in backend.model.parameters())
assert parameters < 500_000_000
try:
    backend.text("apple " * 10000)
except ConfigError as exc:
    assert "context limit" in str(exc)
else:
    raise AssertionError("Over-context input silently truncated")
red = backend.image(work / "RGB.png")
gray = backend.image(work / "L.png")
assert np.isfinite(red).all() and not np.allclose(red, gray)
report = {"contract_fingerprint": backend.fingerprint, "actual_parameters": parameters,
          "audio_disabled": True, "vision_enabled": True, "rgba_composite_rgb_gray_checks": "passed",
          "corrupt_image_rejected": True, "over_context_input_rejected": True,
          "different_pixels_different_vectors": True, "resources": backend.resources()}
save_json(config.output_path("data", "embeddings/runtime-checks.json"), report)
print(json.dumps(report))
