---
tags: [hub]
---
# Assetarium knowledge base

What the code doesn't say: where things are, rules, gotchas, legacy vs current, design intent,
decisions and history. It lives next to the code, so it branches and merges with it. Agents and
contributors read it before a task and add to it after one. Open this folder as a vault in
[Obsidian](https://obsidian.md), or read it on GitHub: links are plain relative Markdown links.

**Start here:** [Status](Status.md) (what works, open work) · [Notebook](Notebook/Notebook.md)
(working notes per area) · [Architecture](Architecture/Architecture.md) (how and why) ·
[Decisions](Decisions/Decisions.md) (binding owner decisions) · [Codebase](Notebook/Codebase.md)
(module map) · [Improvements](Notebook/Improvements.md) (known friction).

## Sections

- **Notebook**: working notes, agents first. Short and dense, read on almost every task: where
  things are, rules, gotchas, legacy vs current. One hub per area, one note per system.
- **Architecture**: explanatory docs, humans first. How systems are meant to work and why:
  contracts, mental models, flows, the roadmap.
- **Decisions**: owner-approved decisions that bind later changes. Change one only after asking
  the owner, and update the record together with the code.
- **Reference**: external docs with how far each can be trusted.

## User manual (outside the vault)

Install, use and operate the app: [README](../README.md) ·
[Asset sources](../docs/asset-sources.md) · [Command line](../docs/cli.md) ·
[Desktop app](../docs/gui/README.md) · [Interactive 3D preview](../docs/gui/3d-preview.md) ·
[Agents (MCP)](../docs/mcp/README.md) · [Description engines](../docs/description-engines.md) ·
[Overnight descriptions](../docs/overnight-descriptions.md) ·
[Shared texture dependencies](../docs/dependency-path-overrides.md) ·
[Shared model storage](../docs/model-storage.md) · [Linux](../docs/linux.md).
Evidence and contracts that code reads stay in `docs/` as well: the `*.json` manifests,
`docs/caption-contract.md`, `docs/evaluation/` and `docs/mcp/*.json` (hash-bound).
History: [docs/history](../docs/history/README.md), including the frozen
[progress journal](../docs/history/progress-2026-10.md).

## Conventions

- **What stays out:** what the code states plainly (signatures, class lists, call graphs); logs of
  what was done on a task (git history, pull requests and the CHANGELOG hold those); personal
  preferences and anything machine-specific (drive letters, absolute paths, user names, one
  computer's hardware).
- **Stale is worse than missing: when the code disagrees with a page, the code wins.** Fix the page
  in the same change as the code.
- **Page names are unique across the vault**, so a name always means one page. Link liberally with
  relative Markdown links (`[Retrieval](../Search/Retrieval.md)`); a link to a page that doesn't
  exist yet marks a gap worth writing.
- **Frontmatter:**
  - `tags`: one of `hub`, `system`, `architecture`, `reference`, `decision`, `stub`.
  - Notebook notes have `area`. Architecture docs have `level` (`macro` / `system` /
    `implementation`), `parent` and `status` (`draft` / `reviewed`). Decisions have `decided`.
  - `code`: the main symbols or paths the page relies on, spelled exactly as in the code
    (`module.function`, `ClassName`, `path/to/file`). These anchors let a staleness check find
    pages to re-verify.
  - `verified`: the date the page was last checked against the code; `branch`: where. Leave both
    empty (and tag `stub`) until someone actually checks.
- Code references in backticks, by symbol, not line number (line numbers drift).
- Diagrams in Mermaid (rendered by Obsidian and GitHub, readable as text).
- Related external pages: a `## <Source>` section at the end of a page with links, also added to
  [Upstream](Reference/Upstream.md).
- New pages start from `_Templates/` (Obsidian: *Insert template*).
