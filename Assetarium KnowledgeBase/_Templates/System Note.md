---
area:
tags: [system]
code: []
verified:
branch:
---
# {{title}}

Hub: [<Area>](<Area>.md). One or two lines: what this system is for and where to start reading (`module.function`, `path/to/folder`).

## How it works
Only what isn't obvious from the code: flow across modules and processes, ownership/lifetime, threads and leases, data and config dependencies, what lives in `data/` vs a source's `metadata-lal/`.

## Rules
Invariants and must-dos. **Bold** the ones that cause bugs when ignored (fingerprints, read-only originals, no fallbacks).

## Gotchas
Legacy vs current, look-alike names, traps found the hard way (link the issue or PR when there is one).

## Friction and improvements
`- **<what>**: why, improvement. Seen: YYYY-MM-DD` (see [Improvements](../Improvements.md)).

## Related
[...](...). Architecture: [<doc>](../../Architecture/<Area>/<doc>.md) (when one exists). Decisions: [00xx](../../Decisions/00xx-name.md).
