---
tags: [roadmap]
id: ASSETRM-0001
type: bug
status: done
created: 2026-10-29
resolved: 2026-10-29
---
# ASSETRM-0001

Make `CLAUDE.md` hardware agnostic.

## Problem

`CLAUDE.md` is checked in and read by every contributor's agent, but it describes one machine.
Many developers with different setups will work on the project, so it should hold nothing that
only applies to the owner's computer. The vault already says so: machine-specific content
(drive letters, absolute paths, user names, one computer's hardware) stays out
([Home](../../../Home.md#conventions)).

Known offenders (the list may be incomplete, review the whole file):

- The **Hardware** bullet: the original RTX 5070 setup and the current Ryzen 9 9950X3D with a
  Radeon RX 6800 (HIP, no CUDA).
- The **Blender** line with a fixed `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.
- The **Linux check environment** bullet: a specific WSL2 distro, clone location and Blender
  folder.
- Mentions of the owner's own `config.local.toml` contents ("the owner's machine paths live
  in...").
- Stale paths: the vault folder is now `Assetarium KnowledgeBase/`, but `CLAUDE.md` (and
  possibly `AGENTS.md`) still say `KnowledgeBase/`. Check every reference while in there.

## Done when

- `CLAUDE.md` names no specific CPU, GPU, drive, user, distro or install path.
- Anything contributors need from those bullets (how hardware is detected and configured, where
  Blender comes from, how to run the Linux suite) points at the existing docs or config
  (`config.example.toml`, `docs/linux.md`, `docs/model-storage.md`) instead of one machine.
- The owner's machine-specific notes are kept somewhere private to the owner, not lost
  (for example the ignored `config.local.toml` or a personal memory file).
- `AGENTS.md` and the vault notes that repeat the same details are checked and fixed in the
  same change.

## Working on it

**When an agent picks this up, it must first ask the owner questions to settle the solution
strategy before editing anything.** Do not decide these alone. Questions to start from:

- Where should the owner's own hardware and path notes live now (ignored local file, personal
  agent memory, nowhere)?
- Should the hardware guidance become a short generic section (for example "GPU: CUDA or HIP,
  one GPU job at a time via `gpu_queue`") or move entirely into the vault and docs?
- Should the Linux/WSL verification recipe be generalized in `CLAUDE.md` or only referenced
  from `docs/linux.md`?
- Do `AGENTS.md` and the Notebook notes get the same cleanup in this change, or is the scope
  `CLAUDE.md` only?
- Is the stale `KnowledgeBase/` path fixed here or tracked as its own task?

This goes through the usual scope-and-plan checkpoint in `AGENTS.md` before implementation.

## Resolution

Machine details moved to the ignored `MACHINE.local.md`, which agents create by probing the
machine when it is missing and read before machine-dependent decisions (`AGENTS.md` → Local
machine). `CLAUDE.md` keeps only generic GPU, Blender and Linux guidance pointing at
`config.example.toml`, `docs/linux.md` and `docs/model-storage.md`. Live `KnowledgeBase/` paths now
say `Assetarium KnowledgeBase/`; the frozen journal and the hashed `docs/caption-contract.md` keep
the old path. Measurements in Decision 0018, Decision 0022, `Embedding contract.md` and `Status.md`
stay as records of what was tested.
