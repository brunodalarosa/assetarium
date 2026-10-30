---
tags: [reference]
---
# Upstream

External documentation this project relies on. Trust is `ok <date>`, `partly outdated <date>: <what>`,
`outdated <date>`, or blank when nobody has checked. Pinned versions are in the `pyproject.toml`
and `uv.lock` files and in `docs/*-model.json`; those win over this page. Up: [Home](../Home.md).

## Models

| Page | ID/URL | Use | Trust |
| --- | --- | --- | --- |
| Qwen3-VL-2B-Instruct | https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct | Built-in description engine; pinned revision in `docs/caption-model.json` | |
| Qwen3-VL-2B-Instruct GGUF | https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF | Files checked with the experimental local-server engine | |
| EmbeddingGemma 2 | https://huggingface.co/google/embeddinggemma-2 | Search vectors (`google/embeddinggemma-2`); pinned revision in `docs/embedding-model.json` | |
| llama.cpp server | https://github.com/ggml-org/llama.cpp | Local OpenAI-compatible server checked with the local-server engine | |

## Runtime and tools

| Page | ID/URL | Use | Trust |
| --- | --- | --- | --- |
| Blender Python API | https://docs.blender.org/api/current/ | Inspection, render and repair workers | |
| pywebview installation | https://pywebview.flowrl.com/guide/installation | Desktop window | |
| pywebview usage and threading | https://pywebview.flowrl.com/guide/usage | `js_api` methods run on threads | |
| pywebview web engines | https://pywebview.flowrl.com/guide/web_engine.html | WebView2 is required; no legacy renderer | |
| uv | https://docs.astral.sh/uv/ | All Python environments, behind `scripts/*-runtime.*` | |
| MCP server development | https://modelcontextprotocol.io/docs/develop/build-server | STDIO server | ok 2026-10-11 |
| Online 3D Viewer | https://github.com/kovacsv/Online3DViewer | Vendored 3D preview (`ui/vendor/`) | |
| beUI | https://beui.dev | Component source adapted in `frontend/src/components/beui/` | |

## Agent clients

| Page | ID/URL | Use | Trust |
| --- | --- | --- | --- |
| Codex MCP | https://learn.chatgpt.com/docs/extend/mcp?surface=cli | Client registration snippets | ok 2026-10-11 |
| OpenCode MCP servers | https://opencode.ai/docs/mcp-servers/ | Client registration snippets | ok 2026-10-11 |
| OpenCode configuration precedence | https://opencode.ai/docs/config/ | Where registrations live | ok 2026-10-11 |
