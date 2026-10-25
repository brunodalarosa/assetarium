"""Ports for model inference: description engines and embedders (decision 0015).

The core (caption stage, overnight runs, indexing, search) depends only on these
contracts. Adapters live in their own modules and are chosen in one place,
``engines.py``; nothing in the core constructs one.

DescriptionEngine contract
    ``contract``  JSON-able identity saved in every description's provenance.
    ``settings``  JSON-able inference settings saved alongside it.
    ``generation_mode``  provenance mode; it selects the fingerprint rule that
        keeps finished descriptions valid (``incremental.caption_input``).
    ``generate_batch(inputs_list, prompt, max_new_tokens)``  one entry per asset,
        in order: ``(raw_text, metrics)`` or the exception that failed that asset.
        Inputs are project-rendered views (``path`` under ``data/`` plus
        ``sha256``); an engine verifies them before use. Raw text is parsed and
        validated by the core, so every engine meets the same description rules.
    Errors  An exception returned for one asset fails only that asset. Raising
        ``EngineStop`` (``MemoryLimitError``, ``EngineUnavailableError``) stops the
        run as a machine limit: nothing is recorded as failed and the assets stay
        pending. Any other exception fails every asset of that batch, without retry.
    Invariants  Local only, no silent fallback to another device, model or engine,
        and no retry of recorded failures. ``resources()`` returns JSON-able
        measurements; ``close()`` releases the engine.

Embedder contract
    ``contract``  identity of the vectors; it is part of the index fingerprint, so
        vectors from different embedders are never mixed.
    ``text(text, role='query'|'document')`` and ``image(path)`` return one
        normalized vector of the contract's dimensions; ``last_metrics`` and
        ``resources()`` describe the last call. Faults raise; they are never
        replaced by another vector.
"""
from typing import Protocol, runtime_checkable


class EngineStop(Exception):
    """A machine limit that stops the run; its assets stay pending (never an asset fault)."""


class MemoryLimitError(EngineStop):
    """Not enough memory for the configured batch size."""


class EngineUnavailableError(EngineStop):
    """The engine or its server cannot be used right now (not reachable, wrong model, refused request)."""


@runtime_checkable
class DescriptionEngine(Protocol):
    contract: dict
    settings: dict
    generation_mode: str

    def generate_batch(self, inputs_list, prompt, max_new_tokens): ...
    def resources(self) -> dict: ...
    def close(self) -> None: ...


@runtime_checkable
class Embedder(Protocol):
    contract: dict

    def text(self, text, role='query'): ...
    def image(self, path): ...
