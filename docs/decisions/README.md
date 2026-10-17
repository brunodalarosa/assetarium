# Decisions

Owner-approved decisions that later changes must respect. Each file states the
decision, why it was made, and what future work must keep true. To change one,
ask the owner first, then update the file (do not silently contradict it).

| # | Decision | Date |
| --- | --- | --- |
| [0001](0001-config-local-precedence.md) | `config.local.toml` overrides `config.example.toml` | 2026-10-17 |
| [0002](0002-startup-scan-and-change-detection.md) | Startup scan, stat-token change detection, no manual Scan/Status | 2026-10-17 |
| [0003](0003-per-publication-read-caches.md) | Read paths reuse per-publication caches | 2026-10-17 |
