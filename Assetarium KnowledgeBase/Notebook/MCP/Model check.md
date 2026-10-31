---
area: MCP
tags: [system]
code: [model_check.py, model_check.run, model_check.run_tree, model_check.outcome, model_check.score, model_check.trimmed, model_check_trees.py, desktop.DesktopBridge.model_check_start, frontend/src/ui/ModelCheck.tsx]
verified: 2026-10-31
branch: feature/library-view
---
# Model check

Hub: [MCP](MCP.md). "Check my model": can a local model structure packs through the pack tools? Start at
`model_check.run`. Decision: [0024](../../Decisions/0024-pack-profiles-and-variant-groups.md).

## How it works

- Each tree in `model_check_trees.trees()` (made-up names, stub files) becomes a library folder in a disposable
  project under `scratch/model-check/<run>/` (`model_check.project`): quick look, add, `quick_look.save`. No scan
  runs; the pack tools read the names snapshot.
- The model gets `SYSTEM` (with `/no_think` for Qwen3), the wizard's copy-paste prompt (`pack_agent.prompt`) and
  only the six pack tools. Calls go straight to `pack_agent.execute` (validated with `mcp_assets.validate`), not
  through a gateway. A `pending` proposal is applied as the owner would, then the snapshot is saved again so the
  model sees its effect.
- `trimmed` keeps the system and task messages plus whole recent rounds under `BUDGET` (~3,200 tokens); older
  tool results become a one-line placeholder, so a 4,096-token context fits.
- `outcome` rebuilds packs, cards, exclusions, image kinds and statuses from the saved answers and the names;
  `score` grades each tree's `checks`. Outcome, never rule text: two rule sets can give the same library.
- Reports and transcripts: `data/evidence/model-check/<run>.json` / `.transcripts.json`. The scratch project is
  removed at the end.

## Rules

- **Only a server on this computer** (`engine_server.checked_url`); nothing of the owner's library or settings is
  touched.
- Add a tree family when a new layout problem is found in real packs; keep names synthetic.
- `tests/test_model_check.py` keeps an oracle (must pass every tree) and an idle model (passes only the fine
  families): a signal or tool change that breaks either changes what a real model can achieve.

## Related

[Pack profiles](../Sources%20and%20Catalog/Pack%20profiles.md) · [MCP tools](MCP%20tools.md).
