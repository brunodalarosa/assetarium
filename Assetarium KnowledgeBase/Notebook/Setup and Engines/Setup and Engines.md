---
area: Setup and Engines
tags: [hub]
code: [setup_core.py, setup_agent.py, description_engines.py, engines.py, engine_transformers.py, engine_server.py]
---
# Setup and Engines

First-run setup for every entry point (desktop wizard, `local-assets setup`, agents), Blender
discovery, and how model inference is plugged in. Up: [Notebook](../Notebook.md).

## Systems

- [Setup core](Setup%20core.md): the GUI-free rules behind every setup surface.
- [Agent setup sessions](../MCP/Agent%20setup%20sessions.md) (in MCP): the agent-facing wrapper.
- [Inference ports](../../Architecture/Setup%20and%20Engines/Inference%20ports.md) (Architecture):
  description engines and embedders, the one composition root.

## Read first

- Decisions: [0031](../../Decisions/0031-setup.md), [0033](../../Decisions/0033-descriptions-and-engines.md),
  [0018](../../Decisions/0018-cpu-search-embedder.md).
- User guide: [Description engines and search device](../../../docs/description-engines.md).

## Rules

- **Never construct `QwenBackend` or `EmbeddingBackend` in core code**; go through
  `engines.description_engine` / `engines.embedder`.
- **Setup never downloads, installs, processes or starts a model.**
