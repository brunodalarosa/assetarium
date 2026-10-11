"""Pinned offline Qwen3-VL backend. No agent runtime or cloud API."""

import importlib.metadata
import json
import os
import threading
import time

from .captions import file_hash
from .config import ConfigError


def prepare_images(config, inputs):
    from PIL import Image
    images, processed = [], []
    for item in inputs:
        if not item["path"].startswith("data/"):
            raise ConfigError("Only project-rendered input accepted")
        path = config.output_path("data", item["path"][5:])
        if file_hash(path) != item["sha256"]:
            raise ConfigError("Input hash changed")
        with Image.open(path) as source:
            source.load()
            if source.width < 32 or source.height < 32 or source.width * source.height > 16_000_000:
                raise ConfigError("Invalid image dimensions")
            rgba = source.convert("RGBA")
            backdrop = Image.new("RGBA", rgba.size, (82, 82, 82, 255))
            image = Image.alpha_composite(backdrop, rgba).convert("RGB")
            image.thumbnail((448, 448), Image.Resampling.LANCZOS)
            images.append(image)
            processed.append({"view_label": item["view_label"], "original_size": list(source.size),
                              "processed_size": list(image.size), "mode": image.mode})
    if not images:
        raise ConfigError("No actual images supplied")
    return images, processed


class QwenBackend:
    settings = {"device": "cuda:0", "dtype": "bfloat16", "attention": "sdpa",
                "do_sample": True, "temperature": 0.7, "top_p": 0.8, "top_k": 20,
                "repetition_penalty": 1.1, "num_beams": 1, "seed": 0,
                "max_new_tokens": 1100, "corrective_max_new_tokens": 1500,
                "max_time_seconds": 120, "image_edge": 448,
                "preprocessing": "rgba-gray-composite-rgb-lanczos-448-v1"}

    def __init__(self, config, contract):
        import torch
        import psutil
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        self.config = config
        self.torch = torch
        self.process = psutil.Process()
        self.peak_rss = self.process.memory_info().rss
        self.stop = threading.Event()
        self.sampler = threading.Thread(target=self._sample, daemon=True)
        self.sampler.start()
        self.contract = {"model_id": contract["model_id"], "revision": contract["revision"],
                         "license": contract["license"], "backend": "transformers",
                         "versions": {name: importlib.metadata.version(name) for name in ("torch", "torchvision", "transformers", "pillow", "huggingface-hub")},
                         "device": torch.cuda.get_device_name(0), "cuda": torch.version.cuda,
                         "capability": list(torch.cuda.get_device_capability(0)),
                         "runtime_lock_sha256": file_hash(config.project_root / "runtime/caption/uv.lock")}
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ConfigError("Verified CUDA BF16 device required; no silent device fallback")
        local = config.output_path("models", "qwen3-vl-2b/" + contract["revision"])
        verified = json.loads(config.output_path("data", "captions/model-download.json").read_text())
        if verified["revision"] != contract["revision"]:
            raise ConfigError("Local weights have a different revision")
        for item in verified["files"]:
            path = config.output_path("models", "qwen3-vl-2b/" + contract["revision"] + "/" + item["name"])
            if path.stat().st_size != item["size"] or file_hash(path) != item["sha256"]:
                raise ConfigError("Local model file changed: " + item["name"])
        self.contract["model_files"] = verified["files"]
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        torch.manual_seed(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        self.processor = AutoProcessor.from_pretrained(local, local_files_only=True, trust_remote_code=False, use_fast=True)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(local, local_files_only=True,
                    trust_remote_code=False, dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda:0").eval()
        self.model.generation_config.do_sample = True
        self.model.generation_config.temperature = 0.7
        self.model.generation_config.top_p = 0.8
        self.model.generation_config.top_k = 20
        self.model.generation_config.repetition_penalty = 1.1
        self.contract["generation_config"] = self.model.generation_config.to_dict()
        self.load_seconds = time.perf_counter() - started

    def _sample(self):
        while not self.stop.wait(0.25):
            self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)

    def resources(self):
        return {"load_seconds": self.load_seconds, "process_peak_rss_bytes_sampled": self.peak_rss,
                "rss_sample_interval_seconds": 0.25,
                "cuda_peak_allocated_bytes": self.torch.cuda.max_memory_allocated(),
                "cuda_peak_reserved_bytes": self.torch.cuda.max_memory_reserved(),
                "cuda_free_total_bytes": list(self.torch.cuda.mem_get_info())}

    def close(self):
        self.stop.set()
        self.sampler.join(timeout=1)

    def generate(self, inputs, prompt, max_new_tokens=1100):
        images, processed = prepare_images(self.config, inputs)
        content = []
        for item, image in zip(inputs, images):
            content.extend([{"type": "text", "text": "View: " + item["view_label"]}, {"type": "image", "image": image}])
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        started = time.perf_counter()
        tensors = self.processor.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,
                                                     return_dict=True, return_tensors="pt").to("cuda:0")
        grid = tensors.get("image_grid_thw")
        if grid is None or len(grid) != len(images) or "pixel_values" not in tensors:
            raise ConfigError("Processor did not consume every actual input image")
        image_token_id = self.model.config.image_token_id
        image_tokens = int((tensors["input_ids"] == image_token_id).sum().item())
        if image_tokens == 0 or not bool(self.torch.isfinite(tensors["pixel_values"]).all()):
            raise ConfigError("Invalid/empty pixel tensor")
        self.torch.manual_seed(self.settings["seed"])
        with self.torch.inference_mode():
            outputs = self.model.generate(**tensors, do_sample=True, num_beams=1,
                                          temperature=0.7, top_p=0.8, top_k=20, repetition_penalty=1.1,
                                          max_new_tokens=max_new_tokens, max_time=120,
                                          use_cache=True)
        self.torch.cuda.synchronize()
        trimmed = outputs[0, tensors["input_ids"].shape[1]:]
        text = self.processor.decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        elapsed = time.perf_counter() - started
        metrics = {"elapsed_seconds": elapsed, "input_tokens": tensors["input_ids"].shape[1],
                   "generated_tokens": len(trimmed), "image_tokens": image_tokens,
                   "image_grid_thw": grid.tolist(), "pixel_tensor_shape": list(tensors["pixel_values"].shape),
                   "processed_images": processed, "max_new_tokens": max_new_tokens, **self.resources()}
        if elapsed > 125 or len(trimmed) == max_new_tokens:
            raise RuntimeError("Generation timed out or exhausted output token limit")
        return text, metrics
