"""CPU search embedder (decision 0018): the pinned EmbeddingGemma contract on the CPU in BF16.

Same model files, prompts, preprocessing, precision and normalization as the CUDA backend, with
its own identity (device, adapter and runtime lock), so its vectors never mix with CUDA vectors.
``embedding_backend.py`` stays byte-identical: its hash is part of every CUDA index fingerprint.
Offline, no fallback to another device or precision.
"""
import importlib.metadata
import os
from pathlib import Path
import time

import numpy as np

from .captions import file_hash
from .catalog import digest
from .config import ConfigError
from .embedding_backend import normalize, prepare_image, runtime_contract as cuda_contract

DEVICE = 'cpu'
LOCKS = {'cpu': 'runtime/embedding-cpu/uv.lock', 'cuda': 'runtime/embedding/uv.lock'}
BASE = 'src/local_asset_library/embedding_backend.py'
ADAPTER = 'src/local_asset_library/embedding_cpu.py'


def installed_lock():
    """The runtime lock this environment was synced from: CPU-only Torch wheels carry a +cpu tag."""
    return LOCKS['cpu' if importlib.metadata.version('torch').endswith('+cpu') else 'cuda']


def runtime_contract(config):
    contract = cuda_contract(config)
    lock = installed_lock()
    contract.update(device=DEVICE, base_adapter_sha256=contract['adapter_sha256'],
                    adapter_sha256=file_hash(Path(__file__)), runtime_lock=lock,
                    runtime_lock_sha256=file_hash(config.project_root / lock),
                    # Files whose LF/CRLF forms are equivalent (retrieval.recorded_contract).
                    hashed_files={'adapter_sha256': ADAPTER, 'base_adapter_sha256': BASE, 'runtime_lock_sha256': lock})
    return contract


class EmbeddingCpuBackend:
    def __init__(self, config):
        started = time.perf_counter()
        self.contract = runtime_contract(config)
        self.fingerprint = digest(self.contract)
        import torch
        from sentence_transformers import SentenceTransformer
        self.torch = torch
        local = config.output_path("models", "embeddinggemma-2/" + self.contract["revision"])
        for item in self.contract["model_files"]:
            path = config.output_path("models", "embeddinggemma-2/" + self.contract["revision"] + "/" + item["name"])
            if path.stat().st_size != item["size"] or file_hash(path) != item["sha256"]:
                raise ConfigError("Model file changed: " + item["name"])
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        self.model = SentenceTransformer(str(local), device=DEVICE, local_files_only=True,
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
        # Same processor checks as the CUDA backend: context and actually consumed pixels.
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
        result = normalize(vector)
        self.last_metrics = {"modality": modality, "seconds": time.perf_counter() - started,
                             "input_tokens": int(tensors["attention_mask"].sum().item()),
                             "pixel_tensor_shapes": pixel_shapes, "dimensions": len(result),
                             "norm": float(np.linalg.norm(result)), "finite": True, "device": DEVICE,
                             "threads": self.torch.get_num_threads()}
        return result

    def text(self, text, role="query"):
        if role not in {"query", "document"} or not isinstance(text, str) or not text.strip():
            raise ConfigError("Invalid text embedding input/role")
        prompt = self.contract["query_prompt" if role == "query" else "document_prompt"]
        if len(self.model.tokenizer.encode(prompt + text)) > 8192:
            raise ConfigError("Text exceeds embedding context limit")
        return self._encode(prompt + text, "text")

    def image(self, path):
        return self._encode({"image": prepare_image(path)}, "image")

    def resources(self):
        import psutil
        return {"load_seconds": self.load_seconds, "rss_bytes": psutil.Process().memory_info().rss,
                "device": DEVICE, "threads": self.torch.get_num_threads()}
