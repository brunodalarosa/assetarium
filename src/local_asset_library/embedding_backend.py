"""Pinned SentenceTransformers backend; offline inference with no fallback vectors."""
import importlib.metadata
import json
import os
from pathlib import Path
import time

import numpy as np

from .catalog import digest
from .captions import file_hash
from .config import ConfigError


def normalize(vector, dimensions=768):
    value = np.asarray(vector, dtype=np.float32)
    if value.shape != (dimensions,) or not np.isfinite(value).all():
        raise ConfigError("Embedding has wrong dimensions or nonfinite values")
    norm = float(np.linalg.norm(value.astype(np.float64)))
    if not np.isfinite(norm) or norm <= 1e-12:
        raise ConfigError("Embedding is zero or has invalid norm")
    result = value / norm
    if not np.isfinite(result).all() or not np.isclose(np.linalg.norm(result), 1, atol=1e-5):
        raise ConfigError("Embedding normalization failed")
    return result


def runtime_contract(config):
    contract = json.loads((config.project_root / "docs/embedding-model.json").read_text(encoding="utf-8"))
    expected = {"dimensions": 768, "dtype": "bfloat16", "active_modalities": ["text", "image"],
                "audio_config": None, "query_prompt": "task: search result | query: ",
                "document_prompt": "title: none | text: ", "image_prompt": "", "max_soft_tokens": 280,
                "context_limit": 8192, "normalization": "finite-nonzero-float32-l2-v1",
                "preprocessing": "exif-transpose-rgba-gray82-composite-rgb-native-size-v1"}
    if any(contract.get(k) != v for k, v in expected.items()):
        raise ConfigError("Unsupported embedding contract; explicit revalidation required")
    # Budget and links are not inference semantics.
    contract = {k: v for k, v in contract.items() if k not in {"official_sources", "model_budget_bytes", "generated_budget_bytes", "license"}}
    contract.update(backend="sentence-transformers", device="cuda:0", attention="sdpa",
                    versions={name: importlib.metadata.version(name) for name in
                              ("torch", "torchvision", "sentence-transformers", "transformers", "pillow", "numpy", "huggingface-hub")},
                    runtime_lock_sha256=file_hash(config.project_root / "runtime/embedding/uv.lock"),
                    adapter_sha256=file_hash(Path(__file__)))
    receipt = json.loads(config.output_path("data", "embeddings/model-download.json").read_text(encoding="utf-8"))
    if receipt["revision"] != contract["revision"]:
        raise ConfigError("Model receipt revision mismatch")
    contract["model_files"] = receipt["files"]
    return contract


def prepare_image(path):
    from PIL import Image, ImageOps
    with Image.open(path) as source:
        source.load()
        if source.width < 16 or source.height < 16 or source.width * source.height > 16_000_000:
            raise ConfigError("Invalid image dimensions")
        rgba = ImageOps.exif_transpose(source).convert("RGBA")
        return Image.alpha_composite(Image.new("RGBA", rgba.size, (82, 82, 82, 255)), rgba).convert("RGB")


class EmbeddingBackend:
    def __init__(self, config):
        started = time.perf_counter()
        self.contract = runtime_contract(config)
        self.fingerprint = digest(self.contract)
        import torch
        from sentence_transformers import SentenceTransformer
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise ConfigError("This tested contract requires CUDA BF16; no silent precision/device fallback")
        self.torch = torch
        local = config.output_path("models", "embeddinggemma-2/" + self.contract["revision"])
        for item in self.contract["model_files"]:
            path = config.output_path("models", "embeddinggemma-2/" + self.contract["revision"] + "/" + item["name"])
            if path.stat().st_size != item["size"] or file_hash(path) != item["sha256"]:
                raise ConfigError("Model file changed: " + item["name"])
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
        self.model = SentenceTransformer(str(local), device="cuda:0", local_files_only=True,
                     trust_remote_code=False, config_kwargs={"audio_config": None},
                     model_kwargs={"torch_dtype": torch.bfloat16, "attn_implementation": "sdpa"})
        self.model.eval()
        if self.model.get_embedding_dimension() != 768 or self.model.dtype != torch.bfloat16:
            raise ConfigError("Loaded model violates dimension/precision contract")
        self.load_seconds = time.perf_counter() - started
        self.last_metrics = {}

    def _encode(self, value, modality):
        started = time.perf_counter()
        kwargs = {"processing_kwargs": {"image": {"max_soft_tokens": 280}}} if modality == "image" else {}
        # Inspect the real processor output, including context and consumed pixels.
        tensors = self.model.preprocess([value], **kwargs)
        tokens = tensors.get("input_ids")
        if tokens is None or tokens.shape[-1] > 8192:
            raise ConfigError("Input exceeds the embedding context contract")
        pixel_shapes = {}
        if modality == "image":
            for key, tensor in tensors.items():
                if "pixel" in key and self.torch.is_tensor(tensor):
                    if not tensor.numel() or not bool(self.torch.isfinite(tensor).all()):
                        raise ConfigError("Invalid pixel tensor")
                    pixel_shapes[key] = list(tensor.shape)
            if not pixel_shapes:
                raise ConfigError("Processor did not consume actual image pixels")
        with self.torch.inference_mode():
            vector = self.model.encode(value, prompt="", normalize_embeddings=True,
                       convert_to_numpy=True, show_progress_bar=False, **kwargs)
        self.torch.cuda.synchronize()
        result = normalize(vector)
        self.last_metrics = {"modality": modality, "seconds": time.perf_counter() - started,
                             "input_tokens": int(tensors["attention_mask"].sum().item()),
                             "pixel_tensor_shapes": pixel_shapes, "dimensions": len(result),
                             "norm": float(np.linalg.norm(result)), "finite": True}
        return result

    def text(self, text, role="query"):
        if role not in {"query", "document"} or not isinstance(text, str) or not text.strip():
            raise ConfigError("Invalid text embedding input/role")
        prompt = self.contract["query_prompt" if role == "query" else "document_prompt"]
        # Check the untruncated input; processor defaults can silently truncate.
        if len(self.model.tokenizer.encode(prompt + text)) > 8192:
            raise ConfigError("Text exceeds embedding context limit")
        return self._encode(prompt + text, "text")

    def image(self, path):
        return self._encode({"image": prepare_image(path)}, "image")

    def resources(self):
        import psutil
        return {"load_seconds": self.load_seconds, "rss_bytes": psutil.Process().memory_info().rss,
                "cuda_peak_allocated_bytes": self.torch.cuda.max_memory_allocated(),
                "cuda_peak_reserved_bytes": self.torch.cuda.max_memory_reserved()}
