"""CPU threads for search data (decision 0022): a short speed test, the owner's setting, the count used.

The test embeds six synthetic images (never library previews; the model's fixed image token budget
makes cost independent of content) with the already loaded CPU embedder at the physical core count,
about 1.5× it and every logical thread, in two passes of alternating order. It keeps the fewest
threads within 3% of the fastest, so equal speed leaves threads free. Thread counts never change
vectors (bit-identical, October 26, 2026), so nothing here re-queues work.
"""
from datetime import datetime, timezone
import hashlib
import shutil
import time

from .config import ConfigError
from .publication import atomic_json, read_json

IMAGES = 6
PASSES = 2
TOLERANCE = 0.03  # Fewer threads win when they are within this share of the fastest.


def probe_path(config):
    return config.storage_root("data") / "library/search-test.json"


def identity(config):
    """What the result depends on, readable from every runtime: CPU threads, CPU search runtime, model."""
    from .engines import cpu_threads
    lock = config.project_root / "runtime/embedding-cpu/uv.lock"
    model = config.project_root / "docs/embedding-model.json"
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return {"logical_threads": cpu_threads(), "runtime_lock_sha256": sha(lock), "model_sha256": sha(model)}


def saved(config):
    """The last search speed test when it matches this machine and runtime, else None."""
    path = probe_path(config)
    if not path.exists():
        return None
    try:
        value = read_json(path)
    except (OSError, ValueError):
        return None
    return value if value.get("schema_version") == 1 and value.get("identity") == identity(config) else None


def threads(config):
    """(count, reason): the owner's setting, else the tested best, else every logical thread; never more than exist."""
    from .engines import cpu_threads
    from .settings import search_threads
    available = cpu_threads()
    chosen = search_threads(config)
    if chosen:
        return min(chosen, available), "your setting"
    test = saved(config)
    if test:
        return min(test["chosen"], available), "fastest in the speed test"
    return available, "every logical thread (not speed-tested yet)"


def synthetic(folder):
    """Six 640 px renders' worth of flat shapes on transparency, like the previews being embedded."""
    from PIL import Image, ImageDraw
    import random
    folder.mkdir(parents=True, exist_ok=True)
    generator, paths = random.Random(22), []
    for index in range(IMAGES):
        image = Image.new("RGBA", (640, 640), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for _ in range(12):
            box = sorted(generator.sample(range(60, 580), 2)), sorted(generator.sample(range(60, 580), 2))
            color = tuple(generator.randrange(40, 230) for _ in range(3)) + (255,)
            (draw.ellipse if generator.random() < .5 else draw.rectangle)((box[0][0], box[1][0], box[0][1], box[1][1]), fill=color)
        paths.append(folder / f"shape-{index}.png")
        image.save(paths[-1])
    return paths


def counts():
    from .engines import cpu_threads
    import psutil
    logical = cpu_threads()
    physical = min(logical, psutil.cpu_count(logical=False) or max(1, logical // 2))
    return sorted({physical, min(logical, round(physical * 1.5)), logical})


def run(config, backend, progress=None, cancelled=None):
    """Time the loaded CPU embedder at each count; save and return the result (nothing saved if cancelled)."""
    started = time.monotonic()
    folder = config.output_path("scratch", "search-test")
    shutil.rmtree(folder, ignore_errors=True)  # Disposable images of the previous test only.
    try:
        images = synthetic(folder)
        backend.image(str(images[0]))  # Untimed warm-up.
        tested = counts()
        seconds = {count: [] for count in tested}
        for number in range(PASSES):
            for count in (tested if number % 2 == 0 else tested[::-1]):
                if cancelled and cancelled():
                    return {"cancelled": True}
                if progress:
                    progress(f"Testing search speed: {count} CPU threads")
                backend.torch.set_num_threads(count)
                begin = time.perf_counter()
                for image in images:
                    backend.image(str(image))
                seconds[count].append(round((time.perf_counter() - begin) / len(images), 3))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    results = [{"threads": count, "seconds_per_image": round(sum(values) / len(values), 3), "passes": values}
               for count, values in seconds.items()]
    fastest = min(r["seconds_per_image"] for r in results)
    chosen = min(r["threads"] for r in results if r["seconds_per_image"] <= fastest * (1 + TOLERANCE))
    value = {"schema_version": 1, "identity": identity(config), "results": results, "chosen": chosen,
             "cancelled": False, "elapsed_seconds": round(time.monotonic() - started, 1),
             "utc": datetime.now(timezone.utc).isoformat()}
    atomic_json(probe_path(config), value)
    return value


def ensure(config, backend, progress=None, cancelled=None):
    """Before CPU search data: run the test when none matches this machine, then use the count chosen."""
    from .settings import search_device
    if search_device(config) != "cpu":
        return None
    if saved(config) is None:
        if progress:
            progress("Testing search speed on this computer")
        run(config, backend, progress, cancelled)
    backend.torch.set_num_threads(threads(config)[0])
    return saved(config)


def standalone(config, token):
    """The search part of Test again, in the CPU search runtime (the coordinator has no Torch)."""
    from . import engines
    from .source_operations import cancelled, state
    if engines.search_device(config) != "cpu":
        raise ConfigError("Search runs on the GPU; CPU threads are not tested")
    backend = engines.embedder(config)
    result = run(config, backend, lambda phase: state(config, status="processing", phase=phase, progress=.9),
                 cancelled=lambda: cancelled(config, token))
    return result


def summary(config):
    """The Search card's thread choice and the last test, without running anything."""
    from .engines import cpu_threads
    from .settings import search_device, search_threads
    count, reason = threads(config)
    test = saved(config)
    return {"device": search_device(config), "threads": count, "reason": reason, "cpu_threads": cpu_threads(),
            "setting": search_threads(config),
            "test": test and {"utc": test["utc"], "chosen": test["chosen"], "elapsed_seconds": test["elapsed_seconds"],
                              "results": [{k: r[k] for k in ("threads", "seconds_per_image")} for r in test["results"]]}}
