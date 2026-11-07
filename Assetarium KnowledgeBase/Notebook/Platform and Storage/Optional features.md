---
area: Platform and Storage
tags: [system]
code: [settings.descriptions_enabled, description_engines, setup_core.save_setup]
verified: 2026-11-01
branch: feature/library-view
---
# Optional features

Hub: [Platform and Storage](Platform%20and%20Storage.md). Features the user may turn off or leave unset; Assetarium
works fully without them. Core features are in [Core features](Core%20features.md).

## How it works

| Optional feature | Off means | When turned on, setup must… |
| --- | --- | --- |
| Asset descriptions (Qwen3-VL or a local model server) | Names, filters, keyword and image search still work ([decision 0033](../../Decisions/0033-descriptions-and-engines.md)) | finish its setup: engine, batch size, runtime and weights listed with Copy, or a checked loopback server |
| Sample assets | The Library starts empty | add `samples/Sample assets` and scan it |

## Rules

- **Turned on means working**: an optional feature the user enables during setup is held to the core rule
  ([decision 0031](../../Decisions/0031-setup.md)): no hidden step afterwards.
- Turning an optional feature off never deletes its results.

## Related

[Core features](Core%20features.md) · [Formats](Formats.md).
