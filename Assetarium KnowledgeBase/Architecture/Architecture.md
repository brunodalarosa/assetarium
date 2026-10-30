---
tags: [hub]
---
# Architecture

Explanatory docs, humans first: how systems are meant to work and why. Up: [Home](../Home.md).
Where things are in code is in the [Notebook](../Notebook/Notebook.md); binding rules are in
[Decisions](../Decisions/Decisions.md).

## Levels

- **macro**: a flow across systems (scan → process → publish → search).
- **system**: one system and its extension points.
- **implementation**: one concrete thing built on the systems.

Each doc links one level up (`parent`) and down. Folders are `Architecture/<Area>/`, created with
their first doc. Start a doc from [Architecture Doc](../_Templates/Architecture%20Doc.md).

## Writing a doc

- Agent-written docs stay `status: draft` until someone who knows the system reviews them, and
  claims nobody could verify are marked *(unverified)*.
- The "why" (constraints, decisions, history, what was tried) is the most valuable part, and mostly
  comes from people and history: capture it, and link the decision that made it binding.
- Docs moved from `docs/` on 2026-10-28 keep their original text and are `draft` until reviewed.

## Docs

| Doc | Area | Level | Status |
| --- | --- | --- | --- |
| [Catalog contract](Sources%20and%20Catalog/Catalog%20contract.md) | Sources and Catalog | system | draft |
| [Library updates](Processing/Library%20updates.md) | Processing | macro | draft |
| [Caption severity](Processing/Caption%20severity.md) | Processing | system | draft |
| [Embedding contract](Search/Embedding%20contract.md) | Search | system | draft |
| [MCP server](MCP/MCP%20server.md) | MCP | system | draft |
| [Desktop app design](Desktop%20App/Desktop%20app%20design.md) | Desktop App | system | draft |
| [Inference ports](Setup%20and%20Engines/Inference%20ports.md) | Setup and Engines | system | draft |
| [Expansion plan](Roadmap/Expansion%20plan.md) and its [prompts](Roadmap/Prompts/01-asset-foundation.md) | Roadmap | macro | owner plan |

`docs/caption-contract.md` (the caption contract) stays in `docs/`, because
`scripts/check-caption-classification.py` hashes that exact path.

## Candidates

Roughly by how long the system takes to understand, longest first:

1. [Processing pipeline](Processing/Processing%20pipeline.md): scan → stage ledger → inspection,
   descriptions, vectors → publication, with fingerprints and what re-queues work (macro).
2. [Publication and generations](Sources%20and%20Catalog/Publication%20and%20generations.md): per-source
   publications, the combined catalog and index, pinned generations, retention (system).
3. [Parallel rendering](Processing/Parallel%20rendering.md): kept-open Blender hosts, devices,
   the speed test (system; decision 0022 holds most of it today).
4. [Search ranking](Search/Search%20ranking.md): channels, weighted RRF, bounded shortlists and
   response caps (system).
5. [Setup](Setup%20and%20Engines/Setup.md): `setup_core` shared by the wizard, the CLI and the
   agent session (system; decisions 0014 and 0016).
6. [Collections and tags](Desktop%20App/Collections%20and%20tags.md): owner data, leases, agent
   writes, exports (system; decision 0012).
