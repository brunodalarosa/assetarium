---
tags: [architecture]
level: system
parent: "[Architecture](../Architecture.md)"
status: draft
code: []
verified:
branch:
---
# {{title}}

> One paragraph: what this is, the problem it solves, and the one idea to keep in mind about it.

Up: [<parent doc>](...) · Down: [<child doc>](...) · Where in code: [<Notebook note>](../../Notebook/<Area>/<note>.md)

## Context and constraints
Why it exists. What it must guarantee: read-only originals, offline inference with no fallbacks, stable fingerprints and asset IDs, immutable publications, bounded agent responses.

## Concepts
The mental model: the few key concepts and how they relate. One Mermaid diagram if it helps.

## How it works
Structure, then the main flows and lifecycle. Sequence diagrams for flows that cross processes (app, MCP server, embedding worker, Blender) or leases.

## Extending it
How to add a new X the intended way (a format, an engine, a bridge method, an MCP tool), and the mistakes people make.

## Decisions and history
Why it's shaped this way, what was tried, what changed (link decisions, PRs and commits).

## Known debt and direction
What's legacy, what's migrating where.
