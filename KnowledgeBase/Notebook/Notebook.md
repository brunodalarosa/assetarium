---
tags: [hub]
---
# Notebook

Working notes for agents and contributors. Read the hub for your area and the notes for the systems
you touch before a task. Up: [Home](../Home.md).

## Areas

| Area | Covers |
| --- | --- |
| [Sources and Catalog](Sources%20and%20Catalog/Sources%20and%20Catalog.md) | Registered sources, scans, inventory and logical assets, membership, publication |
| [Processing](Processing/Processing.md) | The stage ledger, Blender inspection and renders, texture repairs, descriptions, search vectors, the GPU lease |
| [Search](Search/Search.md) | Keyword, description, image and combined ranking, hash reuse and read caches |
| [MCP](MCP/MCP.md) | The STDIO server, its embedding worker, agent tools, agent setup sessions |
| [Desktop App](Desktop%20App/Desktop%20App.md) | The pywebview bridge, the React frontend and its build, the 3D preview, the WebView2 verify harness |
| [Setup and Engines](Setup%20and%20Engines/Setup%20and%20Engines.md) | First-run setup (app, CLI, agents), Blender discovery, inference ports and adapters |
| [Platform and Storage](Platform%20and%20Storage/Platform%20and%20Storage.md) | Runtimes and wrappers, Linux, storage discipline, retention, `scratch/` |

Cross-cutting: [Codebase](Codebase.md) (module map, third-party code, misleading names) and
[Improvements](Improvements.md) (friction that isn't specific to one system).

## Note conventions

- One note per system, in its area folder, linked from the area hub. Start new notes from
  [System Note](../_Templates/System%20Note.md).
- Write what cost real effort to find, what a reader would get wrong after reading the code, and
  knowledge people share but nothing records. Point to where to start reading instead of
  describing what the code does.
- Terse and factual. **Bold the rules that cause bugs when ignored.**
- Friction goes in the note's `## Friction and improvements` section, or in
  [Improvements](Improvements.md) when it isn't specific to one system. A recurring item gets
  another `Seen:` date, not a duplicate.
- When an Architecture doc or a decision covers the system, link it instead of re-explaining it.
- A note nobody has checked against the code yet is tagged `stub` with an empty `verified`.
