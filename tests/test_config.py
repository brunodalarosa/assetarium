from pathlib import Path
import os
import subprocess

import pytest

from local_asset_library.config import ConfigError, STORAGE_NAMES, load_config


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "project"
    source = tmp_path / "source"
    root.mkdir()
    source.mkdir()
    (source / "chair.glb").write_bytes(b"synthetic fixture")
    path = root / "config.toml"
    text = "schema_version = 1\n[source]\nroot = '" + str(source) + "'\nread_only = true\n[storage]\n"
    text += "\n".join(f"{key} = '{value}'" for key, value in STORAGE_NAMES.items())
    path.write_text(text, encoding="utf-8")
    return root, source, path


def test_read_only_and_internal_output(setup):
    root, source, path = setup
    config = load_config(path, root)
    with config.open_source("chair.glb") as stream:
        assert stream.read() == b"synthetic fixture"
        assert not stream.writable()
    assert config.output_path("data", "previews/chair.png") == root / "data/previews/chair.png"
    assert not (root / "data").exists()  # Validation does not create output.


@pytest.mark.parametrize("relative", ["../escape", "nested/../../escape", "C:\\escape", "C:escape", "\\\\server\\share\\file", "/escape", "", ".", "file:stream", "file.", "file ", "CON"])
def test_reject_boundary_escapes(setup, relative):
    root, _, path = setup
    config = load_config(path, root)
    with pytest.raises(ConfigError):
        config.output_path("data", relative)
    with pytest.raises(ConfigError):
        config.source_file(relative)


@pytest.mark.parametrize("old,new", [
    ("read_only = true", "read_only = false"),
    ("schema_version = 1", "schema_version = 2"),
    ("data = 'data'", "data = '../outside'"),
])
def test_invalid_configuration(setup, old, new):
    root, _, path = setup
    path.write_text(path.read_text().replace(old, new))
    with pytest.raises(ConfigError):
        load_config(path, root)


def test_overlap_and_missing_source(setup):
    root, source, path = setup
    original = path.read_text()
    for replacement in (root, root.parent, source / "missing"):
        path.write_text(original.replace(str(source), str(replacement)))
        with pytest.raises(ConfigError):
            load_config(path, root)


def test_unknown_area_and_missing_file(setup):
    root, _, path = setup
    config = load_config(path, root)
    with pytest.raises(ConfigError):
        config.output_path("docs", "overwrite.md")
    with pytest.raises(ConfigError):
        config.source_file("missing.glb")


def test_link_escape_when_supported(setup):
    root, source, path = setup
    config = load_config(path, root)
    outside = root.parent / "outside"
    outside.mkdir()
    (outside / "file").write_bytes(b"outside")
    try:
        (source / "linked").symlink_to(outside, target_is_directory=True)
        (root / "data").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"Symlink creation unavailable: {exc}")
        # Windows junctions exercise resolve() without the symlink privilege.
        for link in (source / "linked", root / "data"):
            if not link.exists():
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
                assert result.returncode == 0, result.stderr.decode(errors="replace")
    with pytest.raises(ConfigError):
        config.source_file("linked/file")
    with pytest.raises(ConfigError):
        config.output_path("data", "file")
    with pytest.raises(ConfigError):
        load_config(path, root)
