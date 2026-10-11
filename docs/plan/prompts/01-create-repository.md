# Step 1 prompt — Create the folder and Git repository

```text
Create the Local Asset Library project. Your first implementation action must be creating C:\BrunoOS\Local-Asset-Library and initializing that new folder as a Git repository. Start from C:\BrunoOS. If the target already exists, inspect it first: reuse an established instance of this project only after identifying it; do not overwrite, reset, delete, or adopt an unrelated populated directory. Never alter the neighboring projects.

Read C:\BrunoOS\Plans\Local-Asset-Library\PROJECT.md. This is a planning package; implement only step 1. Copy that file and its prompts directory into the new repository under docs\plan\ so later chats have the same instructions. Follow applicable AGENTS.md guidance. Do not spawn subagents.

After Git initialization, create a small uv-managed Python package, pyproject.toml, appropriate ignore rules, README, configuration example, catalog schema contract, and docs\progress.md. Keep model/data/cache/environment directories inside the project and ignored. Use the proposed SQLite/FTS5 and NumPy approach unless current evidence establishes a concrete incompatibility; document any deviation before implementing it. Establish a consistent CLI entry point and focused tests for configuration and source/output path boundaries. Avoid a GUI or unrelated framework setup.

Discover the actual GPU, tool versions, Python/uv, installed Blender executable, and local model runtimes. Do not assume Blender is absent because it is not on PATH. Inspect only relevant configuration fields; do not dump credentials. Record verified versus missing versus untested capabilities in docs\environment.md. Do not download models, render assets, or alter the existing Ollama/OpenCode installation in this step.

Configure C:\Users\backup pc\Documents\General game assets\playful-lowpoly-asset-packs as a read-only source. Generated output must stay inside this repository. Leave Play Shapes unchanged.

Run the focused scaffold checks, review Git status for accidental data inclusion, and make an initial local commit if checks pass. Do not configure a remote or push. Record actual commands, results, environment evidence, and step 2 as the next stage in docs\progress.md. Finish with a concise outcome and concrete blockers. Do not implement step 2.
```
