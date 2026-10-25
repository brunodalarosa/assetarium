"""Execute with isolated vision Python; does not load a model."""
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image

from local_asset_library.config import Config, ConfigError
from local_asset_library.captions import file_hash
from local_asset_library.caption_backend import prepare_images

root = Path(__file__).resolve().parents[1]
(root / "scratch/runtime-image-tests").mkdir(parents=True, exist_ok=True)
with TemporaryDirectory(dir=root / "scratch/runtime-image-tests") as directory:
    project = Path(directory) / "project"
    source = Path(directory) / "source"
    project.mkdir(); source.mkdir()
    config = Config(project, source, None)
    path = config.output_path("data", "alpha.png")
    path.parent.mkdir()
    rgba = Image.new("RGBA", (640, 640), (255, 0, 0, 0))
    rgba.paste((0, 255, 0, 255), (200, 200, 440, 440))
    rgba.save(path)
    inputs = [{"path": "data/alpha.png", "sha256": file_hash(path), "view_label": "front"}]
    images, metrics = prepare_images(config, inputs)
    assert images[0].mode == "RGB" and images[0].size == (448, 448)
    assert images[0].getpixel((0, 0)) == (82, 82, 82)
    assert images[0].getpixel((224, 224)) == (0, 255, 0)
    assert metrics[0]["original_size"] == [640, 640]
    for invalid in ([], [{**inputs[0], "path": "data/../../escape.png"}], [{**inputs[0], "sha256": "wrong"}]):
        try:
            prepare_images(config, invalid)
        except (ConfigError, OSError):
            pass
        else:
            raise AssertionError("Invalid input accepted")
    path.write_bytes(b"not an image")
    try:
        prepare_images(config, [{**inputs[0], "sha256": file_hash(path)}])
    except OSError:
        pass
    else:
        raise AssertionError("Corrupt image accepted")
print("PASS: real RGB/alpha/resize handling; empty, escape, hash mismatch and corrupt image rejected")
