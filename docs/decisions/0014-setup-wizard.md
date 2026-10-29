# 0014 — Setup wizard, optional descriptions switch and Blender persistence

**Decision (owner, October 25, 2026).** Assetarium has a setup wizard in the desktop
app (a full-window overlay in the app's own style and components) and the same flow in
the terminal (`local-assets setup`). Both call one module of setup rules,
`setup_core.py`, which returns plain JSON-able dicts and never imports the GUI, so
milestone 3 can wrap it as MCP tools. Setup records and validates choices only: it never
downloads, installs, processes, renders or starts a model. The one program it runs is
Blender, and only when the user asks for a check.

- **First-run rule.** The wizard opens by itself only on a genuinely fresh install: no
  `data/library/setup.json`, no `settings.json` and no registered source (an unreadable
  registry counts as existing). Existing installs are never interrupted; they get
  **Run setup** in Settings → General, pre-filled with current values. **Skip setup**
  saves nothing except a `skipped` record, so setup does not reopen.
- **Setup record.** `data/library/setup.json` (schema 1, under the `setup` lease): state
  (`completed`, `skipped` or `not_run`), times, wizard version, skipped steps, the engine
  hint, and for each value who last set it (`user` or `agent`). Settings → General and
  the CLI update who set a value when they change it. A damaged record is reported and
  kept, never reset.
- **`descriptions_enabled`** (default on) in `settings.json`. Off is enforced by the
  backend: `describe` is refused, a running description run stops after its batch with a
  reason, the caption stage (`incremental.process`, `library-batch.py`) does no work,
  overnight runs refuse to start, and no *ready to generate* notice is raised or seeded
  (existing ones are dropped; *Not now* counts are kept for later). Existing descriptions
  stay stored and searchable; nothing is deleted or re-queued, and the batch size is kept.
- **Blender** is saved as `[tools].blender` in ignored `config.local.toml`
  ([decision 0001](0001-config-local-precedence.md)) by a minimal edit that keeps every
  other line and the line endings, creates the file from the example when absent,
  re-parses the result with `load_config` and replaces the file atomically. Unusual TOML
  shapes are refused with the exact line to add by hand. A path is written only after a
  passing check in the same process (name `blender.exe`/`blender`, version, headless
  start with scripts disabled, glTF/FBX/OBJ importers; versions other than 5.2 warn).
  Choosing the Blender already saved in the configuration writes nothing; a Blender that
  was only discovered is written, because the speed test and render pool use the saved
  `[tools].blender` only (corrected 2026-10-28: treating a discovered Blender as "in use"
  left fresh installs with nothing saved and the speed test blocked). Process assets reads
  the file in its own process and the Speed test card and its start check read it fresh,
  so no restart is needed. **Settings → General → Blender installation** shows the saved
  Blender's state and offers the same check and save on its own (`set_blender`). A failed Blender write is reported on its own
  and keeps the other saved settings.
- **Blender change cost.** The configured path is an inspection fingerprint input, so a
  change marks every finished 3D inspection as pending again. The wizard shows the count
  and requires a confirmation; the CLI requires `--confirm-rerender`.
- **Recommendations are data.** Engine hints (Godot → glTF; Unity, Unreal → FBX;
  Blender/web → glTF; Not sure → all three), the batch-size table from the measured
  benchmark (≥ 10 GiB → 8, ≥ 8 GiB → 4, otherwise 1, plus measured peaks), and the
  budget suggestion (current use + 20 GiB, rounded up to 5 GiB, within 80% of free space).
- **Zero-edit first launch.** An empty project with the shipped example config starts
  every view without a fault (`tests/test_first_launch.py`); a startup scan with no
  sources starts no worker, and a missing base environment names the command to create it.

**Why.** Other people, including Linux users, should be able to run Assetarium with a
guided, honest setup that never surprises an existing install or starts heavy work.

**Keep true.** Setup never starts work or models by itself; nothing in it runs at app
startup except reading the setup state. Rules stay in `setup_core` and the backend, never
in the UI. Do not write an unchecked Blender path, and keep the re-render confirmation
while the path remains a fingerprint input. Turning descriptions off never deletes,
hides or re-queues results.
