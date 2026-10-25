"""Built-in description engine adapter: the pinned Qwen3-VL Transformers backend on CUDA.

``caption_backend.py`` and ``caption_batching.py`` stay byte-identical: their hashes
are fingerprint inputs of every finished description (decision 0007). This adapter
only maps them onto the DescriptionEngine port; batching, which needs the model's
processor and tensors, is internal to it.
"""
import json

from .caption_batching import MODE, GpuMemoryError, generate_batch
from .description_engines import MemoryLimitError


class TransformersQwenEngine:
    generation_mode = MODE

    def __init__(self, config):
        from .caption_backend import QwenBackend
        contract = json.loads((config.project_root / 'docs/caption-model.json').read_text(encoding='utf-8'))
        self.backend = QwenBackend(config, contract)
        # The same objects as before, so provenance stays byte-identical.
        self.contract, self.settings = self.backend.contract, self.backend.settings

    def generate_batch(self, inputs_list, prompt, max_new_tokens):
        try:
            return generate_batch(self.backend, inputs_list, prompt, max_new_tokens)
        except GpuMemoryError as exc:
            raise MemoryLimitError(str(exc)) from None

    def resources(self):
        return self.backend.resources()

    def close(self):
        self.backend.close()
