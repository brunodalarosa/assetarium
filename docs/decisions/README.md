# Decisions

Owner-approved decisions that later changes must respect. Each file states the
decision, why it was made, and what future work must keep true. To change one,
ask the owner first, then update the file (do not silently contradict it).

| # | Decision | Date |
| --- | --- | --- |
| [0001](0001-config-local-precedence.md) | `config.local.toml` overrides `config.example.toml` | 2026-10-17 |
| [0002](0002-startup-scan-and-change-detection.md) | Startup scan, stat-token change detection, no manual Scan/Status | 2026-10-17 |
| [0003](0003-per-publication-read-caches.md) | Read paths reuse per-publication caches | 2026-10-17 |
| [0004](0004-stat-identity-hash-reuse.md) | Re-hash files only when their identity changes | 2026-10-17 |
| [0005](0005-embedding-worker-and-prestart.md) | Worker returns vectors; app pre-starts it; 10 min idle | 2026-10-17 |
| [0006](0006-retention.md) | Keep active + 2 generations, 10 launch audits; reusable pytest folder | 2026-10-17 |
| [0007](0007-batched-description-generation.md) | Batched descriptions (default 8); finished ones kept; out of GPU memory stays pending | 2026-10-18 |
| [0008](0008-optional-descriptions-and-notifications.md) | Descriptions are optional; Generate descriptions per source; notifications | 2026-10-18 |
| [0009](0009-general-capabilities.md) | Every fix and processing capability is a reusable system feature | 2026-10-19 |
| [0010](0010-shared-project-dependencies.md) | Verify shared project-layout dependencies across enabled sources | 2026-10-19 |
| [0011](0011-react-desktop-ui.md) | React desktop UI: rail navigation, inspection sidebar, Asset processing, themes | 2026-10-21 |
| [0012](0012-collections-and-tags.md) | Collections (per-collection labels/notes), app-wide tags, agent write tools, confirmed deletions | 2026-10-24 |
| [0013](0013-platform-support.md) | Windows primary; Linux v1 is CLI + MCP (no GUI yet); owner CLI on both platforms; deletions need an interactive owner | 2026-10-24 |
| [0014](0014-setup-wizard.md) | Setup wizard (app + CLI) on `setup_core`; first-run rule; `descriptions_enabled`; Blender in `config.local.toml` | 2026-10-25 |
| [0015](0015-description-engines.md) | Inference ports and adapters; experimental loopback local-server description engine | 2026-10-25 |
| [0016](0016-agent-setup.md) | Agent setup through MCP: user-opened setup session, Blender proposals applied by the user, live connection records, bounded status | 2026-10-25 |
| [0017](0017-license-and-cla.md) | AGPL-3.0-only plus a Contributor License Agreement; third-party licenses unchanged | 2026-10-25 |
