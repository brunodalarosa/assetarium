---
tags: [decision]
decided: 2026-11-07
area: MCP
replaces: [0012, 0016, 0023, 0024]
code: [mcp_server.py, mcp_server.DESCRIPTIONS, pack_agent.propose, pack_agent.decide, setup_agent.py, agent_activity.py, agent_activity.sentence]
---
# 0029 — Agent trust: agents act freely, in the open

> **Approved by the owner on November 7, 2026** (decision review, round two). Parts marked *not built yet* are decided but need code: see [Today and target](#today-and-target).

**Decision.** Assetarium is **agent-first**. A connected agent is a co-operator with the owner's powers, not a
guest that asks permission. It may change structure, metadata and settings and start any work, at once.
Safety comes from **being in the open**, not from approval gates: everything an agent does is shown as it
happens, any job can be stopped, agents can be paused, and an agent session's changes can be undone together.
A short list of actions stays owner-only.

## What a connected agent may do

| Area | The agent may | Owner-only |
| --- | --- | --- |
| Reading | Search, assets, packs, profiles, collections, setup status (bounded responses) | — |
| Organization | Create and edit collections, labels, notes; add and remove owner tags | Deleting a collection |
| Pack structure | Apply any pack profile, including rules that rescan a library folder: excluded folders, export-folder groups ([decision 0019](0019-source-folders-and-export-variants.md)), the texture folder ([decision 0021](0021-texture-folder-choice.md)) | — |
| Processing | Start Make previews and Generate descriptions on a pack, folder or selection; they join the same queue as the owner's jobs | Releasing recorded failures for a recheck ([decision 0020](0020-alternate-file-faults-and-recheck.md)) |
| Setup | Apply settings (budget, formats, engines, batch size, descriptions on/off, model server); verify weights | Saving a Blender executable (the agent proposes it) |
| Anything destructive | — | Deletions, Forget missing, removing results or old folders (interactive owner only, [decision 0013](0013-platform-support.md)) |
| Control | — | **Pause agents**, Undo, Stop |

Why recheck stays owner-only: failures are retried only on the owner's explicit request (`AGENTS.md` → Fault
handling); an agent may suggest a recheck. Why the Blender path stays owner-only: it decides which program Assetarium runs, and a change re-renders every
3D asset until it is keyed by version ([decision 0028](0028-result-identity.md)). Installs and
downloads never happen inside Assetarium; an agent with its own shell runs them with the user's approval there.

## In the open: what the owner always has

1. **Told before connecting.** The Connect your agent step, the Welcome page and the MCP guide say plainly:
   *"Your agent can reorganize packs, edit tags and collections, change settings and start processing on its
   own. Everything it does appears in Agent activity, where you can stop it, pause agents or undo a session."*
2. **Seen as it happens.** Every MCP call becomes a sentence in **Agent activity** (`agent_activity.py`, from
   the server's `calls.jsonl`), marked with the `Bot` icon (Design language P2). A job an agent started says so
   in Asset processing and in its notice.
3. **Stop any job.** An agent's job stops like the owner's; finished results are kept.
4. **Pause agents.** One switch refuses every agent write with "Paused by the owner"; reads and search keep
   working. Only the owner turns it back on.
5. **Undo a session.** Activity groups changes by agent session (one connected client run) with **Undo all**.
   Undo of a pack profile is refused once the pack changed after it, and says so ([decision 0035](0035-packs-and-variant-groups.md)).
   Processing time already spent cannot be undone; its results are simply kept.

## The risk the owner accepts

A **manipulated agent** is the main risk: text an agent reads (file and folder names, readmes, license text,
collection notes) can carry instructions, and a cloud model may follow them. With these rules such an agent can
restructure packs, hide assets through exclusions and keep the GPU busy before the owner notices. The owner
accepts this for an agent-first product. Defences are detection and recovery (activity, Stop, Pause, Undo),
not prevention. Tool descriptions keep telling agents that names and record text are data, never instructions.
Considered and not chosen (November 7, 2026): a guard that holds changes hiding many assets, and marking names
as untrusted in every tool response.

Not covered by Assetarium at all: an agent the user gave shell access can edit `config.local.toml` or files
directly. Say so rather than claiming more.

## Guards that stay (they limit damage, not freedom)

- Responses are bounded (16,000 characters); folders are paged.
- Pack rules come from a closed, validated vocabulary (`pack_profiles.KINDS`); agents choose rules, never
  patterns. Nothing is ever written into a pack or an original file.
- The local model server is loopback only. `validate_blender` runs only files named `blender.exe` / `blender`.
- Setup status reveals only its fixed list: never user names, environment variables, directory listings, the
  project path or asset records. A cloud model receives what tools return, and the tool descriptions say so.
- Degraded mode: when the configuration does not load, only `get_setup_status` answers.

## Today and target

| Rule | Today (2026-11-07) |
| --- | --- |
| Tags, collections, setup values apply at once | Built |
| Profiles that need no scan apply at once, with Undo | Built (`pack_agent.propose`) |
| Profiles that rescan apply at once | *Not built yet:* they wait in Agent activity for the owner |
| Agents start processing | *Not built yet:* no MCP tool starts a job |
| Pause agents | *Not built yet* |
| Undo all for an agent session | *Not built yet:* Undo is per proposal |
| Told before connecting | *Partly:* the Welcome panel says a cloud model receives tool output; it does not list what agents may change |

## Keep true

- New agent capabilities are added to the table above. An owner-only action needs a reason written here.
- Every agent write is in the call log and Agent activity, with `Bot`. No silent agent action.
- Pause, Stop and Undo stay owner-only and stay reachable from the app (and the CLI on Linux).
- Destructive actions stay interactive and owner-only; no flag or tool argument bypasses that.

## Changes

- 2026-11-07: named the export-folder groups and the texture folder as agent-applicable pack rules (0019, 0021 updated to match), and made recheck owner-only (PR review).
